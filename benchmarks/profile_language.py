"""Synthetic front-end workloads; no task files or search/solver timings."""

import argparse
import gc
import hashlib
import importlib.util
import json
import platform
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import clingo  # noqa: E402

from gentians.language import parse_text, terms  # noqa: E402
from gentians.language.lexer import lex  # noqa: E402


def workloads(parse_task=parse_text, term_helpers=terms, lexer=lex):
    constants = " ".join(f"#constant(t,c{i})." for i in range(5))
    task = parse_task(constants + " #modeh(1,p(f(" + ",".join(["const(t)"] * 5) + "))).")
    template = task.language_bias_head[0]
    deep_source = "#modeb(1,p(" + "f(" * 600 + "var(t,input)" + ")" * 600 + "))."
    deep = parse_task(deep_source).language_bias_body[0].literal.arguments[0]
    shallow = parse_task("#modeb(1,p(var(t,input))).").language_bias_body[0].literal.arguments[0]
    repeated = '#pos({p("a")},{q("b")},{r("c").}).\n' * 300
    background = "\n".join(f'p({i},"value"). %* trailing comment *%' for i in range(3000))
    shared_fields = "\n".join(f'#pos({{p("a")}},{{q("b")}},{{r({i}).}}).' for i in range(300))
    quoted_background = background + '\np("@ & #theory").'
    fixed_forest = parse_task(constants + " #modeb(1,p(" + "f(" * 300 + "a" + ")" * 300 + ",const(t))).").language_bias_body[0].literal.arguments
    sparse_forest = parse_task(constants + " #modeb(1,p(" + ",".join("f(" * 20 + "const(t)" + ")" * 20 for _ in range(8)) + ")).").language_bias_body[0].literal.arguments

    def metadata(operation):
        for _ in range(1000):
            operation(deep)
        return len(operation(deep))

    def shared_examples():
        parsed = parse_task(shared_fields)
        return [(item.included_text, item.excluded_text, item.context_text) for item in parsed.positive_examples]

    def first_fixed_forest_variant():
        stream = term_helpers.concretize_terms(fixed_forest, task.constants)
        try:
            return tuple(map(str, next(stream)))
        finally:
            stream.close()

    def sparse_variants():
        return tuple(term_helpers.concretize_terms(sparse_forest, {"t": task.constants["t"][:2]}))

    def first_variant():
        stream = template.concretizations(task.constants)
        try:
            return str(next(stream).elements[0].atom.terms[0])
        finally:
            stream.close()

    def kinds(term):
        return [term_helpers.kind(term) for _ in range(1000)]

    def parse_examples():
        parsed = parse_task(repeated)
        return [(item.included_text, item.excluded_text, item.context_text) for item in parsed.positive_examples]

    def lex_background():
        return [(item.start, item.end, item.line, item.column, item.directive) for item in lexer(background)]

    def parse_background():
        return [str(node) for node in parse_task(background).background]

    return {
        "first_nested_variant": first_variant,
        "deep_kind": lambda: kinds(deep),
        "shallow_kind": lambda: kinds(shallow),
        "deep_parse": lambda: len(parse_task(deep_source).language_bias_body),
        "repeated_examples": parse_examples,
        "background_lex": lex_background,
        "background_parse": parse_background,
        "deep_arguments": lambda: metadata(term_helpers.arguments),
        "deep_bindings": lambda: metadata(term_helpers.bindings),
        "deep_constant_types": lambda: metadata(term_helpers.constant_types),
        "shared_example_fields": shared_examples,
        "first_fixed_forest_variant": first_fixed_forest_variant,
        "sparse_forest_variants": sparse_variants,
        "quoted_marker_background": lambda: [str(node) for node in parse_task(quoted_background).background],
    }


def metadata_lifetime(parse_task):
    sources = ["#modeb(1,p(" + "f(" * 300 + f"var(t{i},input)" + ")" * 300 + "))." for i in range(20)]
    gc.collect()
    tracemalloc.start()
    for source in sources:
        assert len(parse_task(source).language_bias_body) == 1
    gc.collect()
    retained, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {"tasks": len(sources), "depth": 300, "python_retained_bytes": retained, "python_peak_bytes": peak}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=7)
    parser.add_argument("--baseline-root", type=Path, help="Checkout whose language package is loaded as an isolated control")
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be positive")
    operations = {}
    lifetimes = {}
    if args.baseline_root is not None:
        entry = args.baseline_root / "gentians" / "language" / "__init__.py"
        spec = importlib.util.spec_from_file_location("gentians_language_control", entry, submodule_search_locations=[str(entry.parent)])
        if spec is None or spec.loader is None:
            parser.error("--baseline-root must contain gentians/language/__init__.py")
        control = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = control
        spec.loader.exec_module(control)
        lifetimes["control"] = metadata_lifetime(control.parse_text)
        operations["control"] = workloads(control.parse_text, control.terms, control.lexer.lex)
    lifetimes["treatment"] = metadata_lifetime(parse_text)
    operations["treatment"] = workloads()
    results = {side: {} for side in operations}
    for name in operations["treatment"]:
        expected = operations["treatment"][name]()
        for side in operations:
            assert operations[side][name]() == expected
        samples = {side: [] for side in operations}
        for sample in range(args.repeat):
            sides = list(operations)
            if sample % 2:
                sides.reverse()
            for side in sides:
                gc.collect()
                start = time.perf_counter()
                actual = operations[side][name]()
                samples[side].append(time.perf_counter() - start)
                assert actual == expected
        for side in operations:
            gc.collect()
            tracemalloc.start()
            actual = operations[side][name]()
            _current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            assert actual == expected
            results[side][name] = {
                "median_seconds": statistics.median(samples[side]),
                "samples_seconds": samples[side],
                "python_peak_bytes": peak,
                "output_sha256": hashlib.sha256(json.dumps(expected, sort_keys=True, default=str).encode()).hexdigest(),
            }
    print(json.dumps({
        "python": platform.python_version(), "clingo": clingo.__version__,
        "platform": platform.platform(), "repeat": args.repeat,
        "baseline_root": str(args.baseline_root) if args.baseline_root else None,
        "metadata_lifetime": lifetimes,
        "workloads": results,
    }, indent=2))


if __name__ == "__main__":
    main()
