"""Compare truth probes with batched shown-symbol decoding on identical models."""

import argparse
import gc
import hashlib
import json
import platform
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import clingo  # noqa: E402
from clingo._internal import _ffi, _lib  # noqa: E402

from benchmarks.catalog import arguments_for, arguments_json  # noqa: E402
from benchmarks.clause_decoder_reference import (  # noqa: E402
    _clause_from_model as _truth_from_model,
    _model_literal_index,
)
from benchmarks.process_resources import peak_rss_bytes  # noqa: E402
from gentians import timing  # noqa: E402
from gentians.clingo_stats import clingo_statistics  # noqa: E402
from gentians.clauses.canonicalization.clauses import ClauseCanonicalizer  # noqa: E402
from gentians.clauses.clause_space import ClauseSpace  # noqa: E402
from gentians.clauses.decoder import _clause_from_model, _ModelDecoder  # noqa: E402
from gentians.clauses.generator import _ClauseGenerator  # noqa: E402
from gentians.clauses import generator as clause_generation  # noqa: E402
from gentians.clauses.reified_clause import ReifiedClause, _instantiate_literal  # noqa: E402
from gentians.clauses.reified_literal import ReifiedLiteral  # noqa: E402
from gentians.gentians import task_from_arguments  # noqa: E402


class ShownDecoder:
    """Alternative two-scan decoders used only for comparisons."""

    def __init__(self, ctl, model_index, modes):
        self.slots = tuple((section, slot) for section, slot, _, _ in model_index)
        slot_ids = {slot: index for index, slot in enumerate(self.slots)}
        self.widths = tuple(len(arguments) for _, _, _, arguments in model_index)
        self.bindings = {mode_id: mode.binding_positions for mode_id, mode in modes.items()}
        self.lookup = {}
        self.flat_lookup = {}
        self.offsets = []
        offset = len(self.slots)
        for width in self.widths:
            self.offsets.append(offset)
            offset += width
        for atom in ctl.symbolic_atoms.by_signature("selected", 3):
            section, slot, mode = atom.symbol.arguments
            self.lookup[atom.symbol._rep] = (slot_ids[section.name, slot.number], -1, mode.number)
            self.flat_lookup[atom.symbol._rep] = (slot_ids[section.name, slot.number], mode.number)
        for atom in ctl.symbolic_atoms.by_signature("var_at", 4):
            section, slot, argument, variable = atom.symbol.arguments
            self.lookup[atom.symbol._rep] = (
                slot_ids[section.name, slot.number], argument.number, variable.number,
            )
            self.flat_lookup[atom.symbol._rep] = (
                self.offsets[slot_ids[section.name, slot.number]] + argument.number,
                variable.number,
            )
        self.capacity = len(self.slots) + sum(self.widths)
        self.buffer = _ffi.new("clingo_symbol_t[]", self.capacity)
        self.size = _ffi.new("size_t*")
        if 0 in self.lookup:
            raise ValueError("The output contains the reserved zero handle")

    def _decode(self, handles):
        selected = [None] * len(self.slots)
        variables = [[None] * width for width in self.widths]
        for handle in handles:
            index, argument, value = self.lookup[handle]
            if argument == -1:
                selected[index] = value
            else:
                variables[index][argument] = value
        head = []
        body = []
        for index, (section, slot) in enumerate(self.slots):
            mode = selected[index]
            if mode is None:
                continue
            values = tuple(variables[index][position] for position in self.bindings[mode])
            if None in values:
                raise RuntimeError("selected literal argument has no variable")
            literal = ReifiedLiteral(section, slot, mode, values)
            (head if section == "head" else body).append(literal)
        return ReifiedClause(tuple(head), tuple(body))

    def _decode_flat(self, handles):
        state = [None] * self.capacity
        for handle in handles:
            offset, value = self.flat_lookup[handle]
            state[offset] = value
        head = []
        body = []
        for index, (section, slot) in enumerate(self.slots):
            mode = state[index]
            if mode is None:
                continue
            offset = self.offsets[index]
            values = tuple(state[offset + position] for position in self.bindings[mode])
            if None in values:
                raise RuntimeError("selected literal argument has no variable")
            literal = ReifiedLiteral(section, slot, mode, values)
            (head if section == "head" else body).append(literal)
        return ReifiedClause(tuple(head), tuple(body))

    def public_symbols(self, model):
        return self._decode(symbol._rep for symbol in model.symbols(shown=True))

    def raw_symbols(self, model):
        if not _lib.clingo_model_symbols_size(model._rep, _lib.clingo_show_type_shown, self.size):
            raise RuntimeError("clingo could not size shown symbols")
        size = self.size[0]
        if size > self.capacity:
            raise RuntimeError("shown symbols exceed the reified clause capacity")
        if not _lib.clingo_model_symbols(
            model._rep, _lib.clingo_show_type_shown, self.buffer, self.capacity,
        ):
            raise RuntimeError("clingo could not read shown symbols")
        return self._decode(self.buffer[index] for index in range(size))

    def raw_flat(self, model):
        if not _lib.clingo_model_symbols_size(model._rep, _lib.clingo_show_type_shown, self.size):
            raise RuntimeError("clingo could not size shown symbols")
        size = self.size[0]
        if size > self.capacity:
            raise RuntimeError("shown symbols exceed the reified clause capacity")
        if not _lib.clingo_model_symbols(
            model._rep, _lib.clingo_show_type_shown, self.buffer, self.capacity,
        ):
            raise RuntimeError("clingo could not read shown symbols")
        return self._decode_flat(self.buffer[index] for index in range(size))

def compare_decoders(task, arguments, limit=0):
    """Alternate decoder order and check exact reified equality for every model.

    Timings isolate decode; this is not an end-to-end generation comparison.
    No Model escapes its callback. The task and all legality/pruning rules stay
    identical; only the display selects existing reified atoms.
    """
    if timing.is_enabled() or timing.metric_enabled("clingo"):
        raise ValueError("Run decoder comparison without generation instrumentation")
    started = time.perf_counter()
    generator = _ClauseGenerator(task, arguments)
    ctl, prepared, *_ = generator._prepare(None)
    index = _model_literal_index(ctl.symbolic_atoms, generator.modes_by_id)
    decoder = ShownDecoder(ctl, index, generator.modes_by_id)
    preparation = time.perf_counter() - started
    methods = {
        "truth_probes": lambda model: _truth_from_model(model, index),
        "shown_public": decoder.public_symbols,
        "shown_raw": decoder.raw_symbols,
        "shown_flat": decoder.raw_flat,
        "shown_single_scan": lambda model: _clause_from_model(model, prepared),
    }
    names = tuple(methods)
    seconds = dict.fromkeys(names, 0.0)
    models = 0

    def compare(model):
        nonlocal models
        values = {}
        offset = models % len(names)
        for name in (*names[offset:], *names[:offset]):
            start = time.perf_counter()
            values[name] = methods[name](model)
            seconds[name] += time.perf_counter() - start
        if any(value != values["truth_probes"] for value in values.values()):
            raise AssertionError(f"Decoder disagreement at model {models}: {values}")
        models += 1
        return not limit or models < limit

    started = time.perf_counter()
    result = ctl.solve(on_model=compare)
    elapsed = time.perf_counter() - started
    return {
        "models": models, "exhausted": result.exhausted,
        "preparationSeconds": preparation, "solveWithComparisonsSeconds": elapsed,
        "decodeSeconds": seconds,
        "microsecondsPerModel": {
            name: value * 1e6 / models if models else None
            for name, value in seconds.items()
        },
        "speedupOverTruthProbes": {
            name: seconds["truth_probes"] / value if value else None
            for name, value in seconds.items()
        },
    }


def space_fingerprint(space):
    """Hash the complete ordered output and metadata, never native handles."""
    digest = hashlib.sha256()
    for entry in space.entries:
        value = (entry.text, sorted(entry.heads), sorted(entry.deps), entry.body_literals)
        digest.update(json.dumps(value, ensure_ascii=False).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def materialize(task, arguments, method):
    """Time one exhaustive run, with the production canonicalizer and storage.

    The candidate adds output before the initial grounding. Its cost is
    included. Both runs clear the literal-instantiation cache beforehand.
    Per-model timers have equal placement; no cProfile is used.
    """
    if timing.is_enabled() or timing.metric_enabled("clingo"):
        raise ValueError("Run materialization comparison without external instrumentation")
    if method not in {"truth_probes", "shown_single_scan"}:
        raise ValueError(f"Unknown decoder: {method}")
    gc.collect()
    _instantiate_literal.cache_clear()
    started = time.perf_counter()
    timing.set_enabled(True)
    try:
        generator = _ClauseGenerator(task, arguments)
        program = clause_generation.CLAUSE_METAPROGRAM
        decoder_factory = _ModelDecoder
        if method == "truth_probes":
            program = tuple(node for node in program if node.ast_type != clingo.ast.ASTType.ShowSignature)
            decoder_factory = _model_literal_index
        with (
            patch.object(clause_generation, "CLAUSE_METAPROGRAM", program),
            patch.object(clause_generation, "_ModelDecoder", decoder_factory),
        ):
            ctl, prepared, _, solver_arguments, grounding = generator._prepare(None)
    finally:
        timing.set_enabled(False)
    if method == "shown_single_scan":
        def decode(model):
            return _clause_from_model(model, prepared)
    else:
        def decode(model):
            return _truth_from_model(model, prepared)
    preparation = time.perf_counter() - started
    canonicalizer = ClauseCanonicalizer(generator.modes_by_id, generator.max_variables)
    models = 0
    decode_seconds = canonical_seconds = callback_seconds = 0.0

    def collect(model):
        nonlocal models, decode_seconds, canonical_seconds, callback_seconds
        callback_start = time.perf_counter()
        clause = decode(model)
        decoded = time.perf_counter()
        canonicalizer.add(clause)
        canonicalized = time.perf_counter()
        models += 1
        decode_seconds += decoded - callback_start
        canonical_seconds += canonicalized - decoded
        callback_seconds += time.perf_counter() - callback_start

    solve_start = time.perf_counter()
    result = ctl.solve(on_model=collect)
    solve_wall = time.perf_counter() - solve_start
    finish_start = time.perf_counter()
    space = ClauseSpace(canonicalizer.finish())
    finish_seconds = time.perf_counter() - finish_start
    total = time.perf_counter() - started
    row = {
        "decoder": method, "models": models, "clauses": len(space),
        "exhausted": result.exhausted, "spaceSha256": space_fingerprint(space),
        "totalSeconds": total, "preparationSeconds": preparation,
        "groundingSeconds": grounding, "decodeSeconds": decode_seconds,
        "canonicalizationSeconds": canonical_seconds,
        "callbackSeconds": callback_seconds, "solveWallSeconds": solve_wall,
        "solvingResidualSeconds": solve_wall - callback_seconds,
        "finishStorageSeconds": finish_seconds,
        "finalClausesPerSecond": len(space) / total if total else None,
        "statistics": clingo_statistics(ctl), "clingoArguments": solver_arguments,
        "peakProcessRssBytes": peak_rss_bytes(),
    }
    return row


def source_hashes(arguments):
    root = Path(__file__).resolve().parents[1]
    files = [root / "gentians" / "arguments.py", root / "gentians" / "timing.py",
             root / "gentians" / "clingo_stats.py", Path(__file__),
             Path(__file__).with_name("clause_decoder_reference.py")]
    for directory in (root / "gentians" / "clauses", root / "gentians" / "language"):
        files.extend(path for path in directory.rglob("*") if path.suffix in {".py", ".lp"})
    task_path = Path(arguments.filename)
    files.extend(sorted(task_path.rglob("*.lp")) if task_path.is_dir() else [task_path])
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(files)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datasets", nargs="+", default=["grandparent"])
    parser.add_argument("--limit", type=int, default=8192, help="Models per task; 0 exhausts enumeration.")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--materialize", action="store_true", help="Exhaustive end-to-end paired runs.")
    parser.add_argument("--repeats", type=int, default=2, help="Paired runs; reverses order on alternate pairs.")
    parser.add_argument("--override", action="append", default=[], help="Arguments override as path=JSON.")
    parser.add_argument("--decoder", choices=("both", "truth_probes", "shown_single_scan"), default="both",
                        help="Materialization methods to run; both gives paired comparisons.")
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit must be nonnegative")
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    rows = []
    output = {
        "protocol": ("Independent exhaustive runs; cold literal cache; "
                     "same canonicalizer; SHA256 of ordered text and all metadata; no cProfile."
                     if args.materialize else
                     "Decoders on the same live models, alternating order; no cProfile; exact reified equality."),
        "python": platform.python_version(), "clingo": clingo.__version__,
        "platform": platform.platform(), "limit": None if args.materialize else args.limit,
        "decoderSelection": args.decoder, "requestedRepeats": args.repeats,
        "rows": rows, "sources": {}, "arguments": {},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    for dataset in args.datasets:
        arguments = arguments_for(dataset, args.override)
        task = task_from_arguments(arguments)
        output["sources"][dataset] = source_hashes(arguments)
        output["arguments"][dataset] = json.loads(arguments_json(arguments))
        expected = None
        for repeat in range(args.repeats if args.materialize else 1):
            methods = ("truth_probes", "shown_single_scan")
            if args.decoder != "both":
                methods = (args.decoder,)
            if repeat % 2:
                methods = tuple(reversed(methods))
            for method in methods if args.materialize else (None,):
                print(f"Comparing {dataset}: {method or 'same live models'}, pair {repeat + 1}...", flush=True)
                row = {"dataset": dataset, "pair": repeat + 1, **(
                    materialize(task, arguments, method) if method else
                    compare_decoders(task, arguments, args.limit)
                )}
                if args.materialize:
                    signature = (row["models"], row["clauses"], row["spaceSha256"], row["exhausted"])
                    if not row["exhausted"] or (expected is not None and expected != signature):
                        raise AssertionError(f"Complete-space disagreement: {expected} != {signature}")
                    expected = signature
                rows.append(row)
                print(json.dumps(row, indent=2), flush=True)
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(json.dumps(output, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
