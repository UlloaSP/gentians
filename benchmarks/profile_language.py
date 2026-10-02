"""Synthetic front-end workloads; no task files or search/solver timings."""

import argparse
import gc
import hashlib
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


def workloads():
    constants = " ".join(f"#constant(t,c{i})." for i in range(5))
    task = parse_text(constants + " #modeh(1,p(f(" + ",".join(["const(t)"] * 5) + "))).")
    template = task.language_bias_head[0]
    deep_source = "#modeb(1,p(" + "f(" * 600 + "var(t,input)" + ")" * 600 + "))."
    deep = parse_text(deep_source).language_bias_body[0].literal.arguments[0]
    shallow = parse_text("#modeb(1,p(var(t,input))).").language_bias_body[0].literal.arguments[0]
    repeated = '#pos({p("a")},{q("b")},{r("c").}).\n' * 300
    background = "\n".join(f'p({i},"value"). %* trailing comment *%' for i in range(3000))

    def first_variant():
        stream = template.concretizations(task.constants)
        try:
            return str(next(stream).elements[0].atom.terms[0])
        finally:
            stream.close()

    def kinds(term):
        return [terms.kind(term) for _ in range(1000)]

    def parse_examples():
        parsed = parse_text(repeated)
        return [(item.included_text, item.excluded_text, item.context_text) for item in parsed.positive_examples]

    def lex_background():
        return [(item.start, item.end, item.line, item.column, item.directive) for item in lex(background)]

    def parse_background():
        return [str(node) for node in parse_text(background).background]

    return {
        "first_nested_variant": first_variant,
        "deep_kind": lambda: kinds(deep),
        "shallow_kind": lambda: kinds(shallow),
        "deep_parse": lambda: len(parse_text(deep_source).language_bias_body),
        "repeated_examples": parse_examples,
        "background_lex": lex_background,
        "background_parse": parse_background,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=7)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be positive")
    results = {}
    for name, operation in workloads().items():
        expected = operation()  # Warm caches; compare every measured output.
        samples = []
        for _ in range(args.repeat):
            gc.collect()
            start = time.perf_counter()
            actual = operation()
            samples.append(time.perf_counter() - start)
            assert actual == expected
        gc.collect()
        tracemalloc.start()
        actual = operation()
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert actual == expected
        results[name] = {
            "median_seconds": statistics.median(samples),
            "samples_seconds": samples,
            "python_peak_bytes": peak,
            "output_sha256": hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest(),
        }
    print(json.dumps({
        "python": platform.python_version(), "clingo": clingo.__version__,
        "platform": platform.platform(), "repeat": args.repeat,
        "workloads": results,
    }, indent=2))


if __name__ == "__main__":
    main()
