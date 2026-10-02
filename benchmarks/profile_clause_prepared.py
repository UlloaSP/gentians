"""Measure prepared modes, extension analysis, fact compilation and decoding."""

import argparse
import hashlib
import json
import os
import platform
import random
import statistics
import sys
import time
import tracemalloc
from dataclasses import replace
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import clingo  # noqa: E402

from benchmarks.profile_clause_followups import canonical  # noqa: E402
from gentians import timing  # noqa: E402
from gentians.arguments import Arguments  # noqa: E402
from gentians.clauses.analysis import relation_properties as relations  # noqa: E402
from gentians.clauses.analysis.ground_relations import ClosedWorld  # noqa: E402
from gentians.clauses.analysis.inference import _context_properties, _reduced  # noqa: E402
from gentians.clauses.analysis.properties import ClosedWorldProperties  # noqa: E402
from gentians.clauses.canonicalization.expression import ArithmeticExpression  # noqa: E402
from gentians.clauses.canonicalization.expression_normalization import _mode_expression  # noqa: E402
from gentians.clauses.decoder import _clause_from_truth  # noqa: E402
from gentians.clauses.generator import generate_clause_space, incremental_clause_batches  # noqa: E402
from gentians.clauses.mode_compiler import _clause_modes  # noqa: E402
from gentians.clauses.mode_facts import compile_mode_facts, predicate_ids  # noqa: E402
from gentians.clauses.reified_clause import _instantiate_literal  # noqa: E402
from gentians.clauses.reified_literal import ReifiedLiteral  # noqa: E402
from gentians.language import parse_text  # noqa: E402


def workloads():
    mode = _clause_modes(parse_text("#modeb(1,var(numeric,input)*var(numeric,input)=var(numeric,output))."))[0]
    arithmetic = ReifiedLiteral("body", 0, mode.id, (0, 1, 2))
    known = {i: ArithmeticExpression.var(i) for i in range(2)}
    same = frozenset((n, n % 2, n % 3) for n in range(300))
    shared = {(f"p{i}", 3): same for i in range(12)}
    distinct = {(f"p{i}", 3): frozenset((n + i * 100, n % 2, n % 3) for n in range(30)) for i in range(6)}
    worlds = {"shared": ClosedWorld(shared, {}, {}, frozenset(), frozenset(), ()),
              "distinct": ClosedWorld(distinct, {}, {}, frozenset(), frozenset(), ())}
    equal_rows = frozenset((n, n, n, n) for n in range(2000))
    rng = random.Random(40)
    mixed_rows = frozenset(tuple(rng.randrange(5) for _ in range(4)) for _ in range(2000))
    path = frozenset((n, n + 1) for n in range(4000))
    order = frozenset((a, b) for a in range(80) for b in range(a, 80))
    source = frozenset((n % 50, n % 50, n + 10000) for n in range(2000))
    failing = frozenset((a, b) for a in range(50) for b in range(50) if a != b)
    success = frozenset((a, a) for a in range(50))
    reduction = replace(ClosedWorldProperties.none(),
                        keys=frozenset(((f"p{i}", 6), (j,)) for i in range(50) for j in range(2)),
                        functional=frozenset(((f"p{i}", 6), a, b) for i in range(50)
                                             for a in range(6) for b in range(6) if a != b),
                        functional_set=frozenset(((f"p{i}", 6), args, output) for i in range(50)
                            for args in combinations(range(6), 3) for output in range(6) if output not in args))
    conditions = tuple(f"q{i}(var(t,input))" for i in range(12))
    variants = (conditions, *(conditions[:i] + conditions[i + 1:] for i in range(len(conditions))))
    task = parse_text("#maxbl(12). " + " ".join(
        f"#modeb({recall},p(var(t,any)):{','.join(items)})." for recall in range(1, 5) for items in variants))
    conditioned = _clause_modes(task)
    identifiers = predicate_ids(conditioned)
    cached_modes = tuple(_clause_modes(parse_text(f"#modeb(1,p{i}(var(t,input)))."))[0] for i in range(100))
    wide = tuple((i * 2, (), 10000 + i) for i in range(3000))
    wide_index = (("body", 0, ((5000, (), 12500),), ()), *(
        ("body", slot, wide, ()) for slot in range(1, 8)))
    small_index = tuple(("body", slot, ((0, (), 1), (1, (), 2)), ()) for slot in range(2))
    small_task = parse_text("d(1..3). #maxv(3). #maxbl(3). #maxhl(1). "
                            "#modeh(1,p(var(node,input))). #modeb(3,d(var(node,output))). "
                            "#modeb(2,r(var(node,input),var(node,output))).")

    def repeat(run, count):
        result = None
        for _ in range(count):
            result = run()
        return result

    def arguments(rows):
        equal, different = set(), set()
        relations._collect_argument_properties(("p", 4), rows, equal, different)
        return equal, different

    def binary_checks():
        if hasattr(relations, "_binary_successors"):
            successors = relations._binary_successors(path)
            domain = frozenset(value for row in path for value in row)
            transitive = relations._is_transitive(successors, len(path))
            reflexive = relations._is_reflexive(path, domain)
            return (transitive, reflexive, relations._is_acyclic(successors),
                    relations._is_total_order(len(path), len(domain), transitive, reflexive, True))
        transitive = relations._is_transitive(path)
        reflexive = relations._is_reflexive(path)
        return transitive, reflexive, relations._is_acyclic(path), relations._is_total_order(path, transitive, reflexive)

    if hasattr(relations, "_binary_successors"):
        def total_order():
            return relations._is_total_order(len(order), 80, True, True, True)
    else:
        def total_order():
            return relations._is_total_order(order, True, True)

    def projections(target):
        values = {("source", 3): source, ("target", 2): target}
        result = set()
        relations._collect_projection_implications({("source", 3): source}, {("target", 2): target}, result,
            {p: relations._position_values(p[1], rows) for p, rows in values.items()})
        return result

    def cache_hits():
        result = None
        for _ in range(10):
            for literal_mode in cached_modes:
                result = _instantiate_literal(literal_mode, (0,))
        return result

    def hashes():
        for _ in range(10000):
            hash(mode)
        return mode.id

    def incremental():
        with incremental_clause_batches(small_task, Arguments(), 64, random.Random(31)) as batches:
            return [batch.clauses for batch in batches]

    return {
        "arithmetic_steps": lambda: repeat(lambda: _mode_expression(arithmetic, mode, known), 1000),
        "intrinsics_shared": lambda: _context_properties(worlds["shared"], None, frozenset()),
        "intrinsics_distinct": lambda: _context_properties(worlds["distinct"], None, frozenset()),
        "arguments_equal": lambda: arguments(equal_rows),
        "arguments_mixed": lambda: repeat(lambda: arguments(mixed_rows), 1000),
        "binary_checks": binary_checks,
        "total_order_preproved": lambda: repeat(total_order, 30),
        "projection_failure": lambda: projections(failing),
        "projection_success": lambda: projections(success),
        "key_reduction": lambda: _reduced(reduction),
        "conditional_forms": lambda: compile_mode_facts(conditioned, identifiers, 1, 12),
        "mode_hash_warm": hashes,
        "literal_cache_multitask": cache_hits,
        "decoder_wide": lambda: repeat(lambda: _clause_from_truth(lambda literal: literal == 12500, wide_index), 200),
        "decoder_small": lambda: repeat(lambda: _clause_from_truth(lambda literal: literal == 1, small_index), 1000),
        "complete": lambda: generate_clause_space(small_task, Arguments()).clauses,
        "incremental": incremental,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--workloads", nargs="+")
    parser.add_argument("--memory", action="store_true")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    timing.set_enabled(False)
    cases = workloads()
    if args.workloads and set(args.workloads) - cases.keys():
        parser.error("unknown workloads: " + ", ".join(sorted(set(args.workloads) - cases.keys())))
    for name in args.workloads or cases:
        run = cases[name]
        run()
        samples = []
        for _ in range(args.repeats):
            start = time.perf_counter()
            result = run()
            samples.append(time.perf_counter() - start)
        row = {"workload": name, "median_seconds": statistics.median(samples), "samples": samples,
               "fingerprint": hashlib.sha256(json.dumps(canonical(result), sort_keys=True).encode()).hexdigest()}
        if args.memory:
            del result
            tracemalloc.start()
            result = run()
            _, row["peak_bytes"] = tracemalloc.get_traced_memory()
            tracemalloc.stop()
        print(json.dumps(row), flush=True)
    print(json.dumps({"python": sys.version, "clingo": clingo.__version__,
                      "python_hash_seed": os.environ.get("PYTHONHASHSEED"),
                      "platform": platform.platform(), "processor": platform.processor()}))


if __name__ == "__main__":
    main()
