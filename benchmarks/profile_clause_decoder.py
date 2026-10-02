"""Compare truth probes with batched shown-symbol decoding on identical models."""

import argparse
import json
import platform
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import clingo  # noqa: E402
from clingo._internal import _ffi, _lib  # noqa: E402

from benchmarks.catalog import arguments_for  # noqa: E402
from gentians import timing  # noqa: E402
from gentians.clauses.decoder import _clause_from_model  # noqa: E402
from gentians.clauses.generator import _ClauseGenerator  # noqa: E402
from gentians.clauses.reified_clause import ReifiedClause  # noqa: E402
from gentians.clauses.reified_literal import ReifiedLiteral  # noqa: E402
from gentians.gentians import task_from_arguments  # noqa: E402


class ShownDecoder:
    """Experimental decoder; the production generator is unchanged."""

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
        self.bytes = _ffi.buffer(self.buffer)
        self.zero = bytes(len(self.bytes))
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

    def raw_single_scan(self, model):
        # All displayed values are function-symbol handles. Zero is not among
        # them (checked during preparation), so a cleared unused suffix marks
        # the end without a second native output scan to obtain its length.
        self.bytes[:] = self.zero
        if not _lib.clingo_model_symbols(
            model._rep, _lib.clingo_show_type_shown, self.buffer, self.capacity,
        ):
            raise RuntimeError("clingo could not read shown symbols")

        def handles():
            for value in self.buffer:
                if value == 0:
                    return
                yield value

        return self._decode_flat(handles())


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
    ctl, index, *_ = generator._prepare(None)
    ctl.add("decoder_output", [], "#show selected/3. #show var_at/4.")
    ctl.ground([("decoder_output", [])])
    decoder = ShownDecoder(ctl, index, generator.modes_by_id)
    preparation = time.perf_counter() - started
    methods = {
        "truth_probes": lambda model: _clause_from_model(model, index),
        "shown_public": decoder.public_symbols,
        "shown_raw": decoder.raw_symbols,
        "shown_flat": decoder.raw_flat,
        "shown_single_scan": decoder.raw_single_scan,
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datasets", nargs="+", default=["grandparent"])
    parser.add_argument("--limit", type=int, default=8192, help="Models per task; 0 exhausts enumeration.")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit must be nonnegative")
    rows = []
    for dataset in args.datasets:
        arguments = arguments_for(dataset, [])
        print(f"Comparing decoders on {dataset}...", flush=True)
        row = {"dataset": dataset, **compare_decoders(task_from_arguments(arguments), arguments, args.limit)}
        rows.append(row)
        print(json.dumps(row, indent=2), flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "protocol": "Decoders on the same live models, alternating order; no cProfile; exact reified equality.",
        "python": platform.python_version(), "clingo": clingo.__version__,
        "platform": platform.platform(), "limit": args.limit, "rows": rows,
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
