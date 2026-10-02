"""Compare shared Python analysis against a frozen clauses implementation."""

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
from collections import OrderedDict
from dataclasses import replace
from functools import lru_cache
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import clingo  # noqa: E402

from benchmarks.profile_clause_followups import canonical  # noqa: E402
from gentians import timing  # noqa: E402
from gentians.arguments import Arguments  # noqa: E402
from gentians.clauses.analysis import relation_properties as relations, rule_properties  # noqa: E402
from gentians.clauses.analysis.ground_relations import ClosedWorld  # noqa: E402
from gentians.clauses.analysis.inference import _closed_world_properties, _context_properties  # noqa: E402
from gentians.clauses.canonicalization.arithmetic import canonical_arithmetic_clause  # noqa: E402
from gentians.clauses.canonicalization.expression_normalization import _term_comparison  # noqa: E402
from benchmarks.clause_decoder_reference import _clause_from_truth  # noqa: E402
from gentians.clauses.generator import generate_clause_space, incremental_clause_batches  # noqa: E402
from gentians.clauses.mode_compiler import _clause_modes  # noqa: E402
from gentians.clauses.reified_clause import ReifiedClause  # noqa: E402
from gentians.clauses.reified_literal import ReifiedLiteral  # noqa: E402
from gentians.language import parse_text  # noqa: E402
from gentians.language.asp import parse_program  # noqa: E402


def workloads():
    linear = _clause_modes(parse_text("#modeb(1,var(numeric,input)+var(numeric,input)=var(numeric,output))."))[0].literal
    nonlinear = _clause_modes(parse_text("#modeb(1,var(numeric,input)*var(numeric,input)=var(numeric,output))."))[0].literal
    nested = "f(" * 40 + "var(t,input)" + ")" * 40
    comparison = _clause_modes(parse_text(f"#modeb(1,({nested},var(t,input)) != (f(a),b))."))[0]
    comparison_input = comparison if hasattr(comparison, "comparison_steps") else comparison.literal
    bound = ReifiedLiteral("body", 0, comparison.id, (0, 1))
    modes = _clause_modes(parse_text("#modeh(1,p(var(t,input))). "
        "#modeb(6,d(var(numeric,output),var(t,input))). #modeb(6,not n(var(t,input))). "
        "#modeb(6,var(numeric,input)*var(numeric,input)=var(numeric,output))."))
    by_id = {mode.id: mode for mode in modes}
    head = (ReifiedLiteral("head", 0, modes[0].id, (1,)),)
    body = tuple(ReifiedLiteral("body", index, modes[index % 3 + 1].id, ((0, 1), (1,), (0, 0, 2))[index % 3])
                 for index in range(18))
    clause = ReifiedClause(head, body)
    plain = ReifiedClause(head, tuple(item for item in body if not by_id[item.mode_id].builtin))
    systems = OrderedDict()
    wide = tuple((i * 2, (), 10000 + i) for i in range(3000))
    wide_index = (("body", 0, ((5000, (), 12500),), ()), *(
        ("body", slot, wide, ()) for slot in range(1, 8)))
    small_index = tuple(("body", slot, ((0, (), 1), (1, (), 2)), ()) for slot in range(2))
    shared_rows = [(n, n + 1) for n in range(4000)]
    shared = {(f"p{i}", 2): frozenset(shared_rows) for i in range(12)}
    distinct = {(f"p{i}", 2): frozenset((n + i * 100, n + i * 100 + 1) for n in range(80)) for i in range(6)}
    worlds = {name: ClosedWorld(rows, {}, {}, frozenset(), frozenset(), ())
              for name, rows in (("shared", shared), ("distinct", distinct))}
    sources = {(f"s{i}", 3): frozenset((n, n, n) for n in range(300)) for i in range(20)}
    targets = {(f"t{i}", 2): frozenset((n, n) for n in range(300)) for i in range(12)}
    unique_sources = {(f"s{i}", 3): frozenset((n + i, n % 3, n % 5) for n in range(60)) for i in range(3)}
    unique_targets = {(f"t{i}", 1): frozenset((n + i,) for n in range(60)) for i in range(3)}

    def projection_run(left, right):
        positions = {p: relations._position_values(p[1], rows) for p, rows in {**left, **right}.items()}

        def run():
            result = set()
            relations._collect_projection_implications(left, right, result, positions)
            return result
        return run

    repeated_columns = {(f"p{i}", 3): (frozenset(range(500)), frozenset(range(500)), frozenset()) for i in range(30)}
    repeated_domains = {("universal", (f"d{i}", 2)): (frozenset(range(600)), frozenset(range(400))) for i in range(40)}
    unique_columns = {(f"p{i}", 2): tuple(frozenset(range(i * 200 + j, (i + 1) * 200 + j)) for j in range(2))
                      for i in range(6)}
    unique_domains = {("universal", (f"d{i}", 2)): tuple(frozenset(range(i * 200 + j, (i + 1) * 200 + j + 20)) for j in range(2))
                      for i in range(6)}
    composite = {((f"p{i}", 10), args, 9) for i in range(6) for size in range(2, 9)
                 for args in combinations(range(9), size)}
    antichain = {((f"p{i}", 10), args, 9) for i in range(6) for args in combinations(range(9), 4)}
    program = parse_program("d(1..6). 1 {p(X,Y):d(X),d(Y)} 1. " +
                            "p(X,Y):-p(Y,X),d(X),d(Y),X!=Y. " * 100)
    varied_programs = tuple(parse_program(f"d(1..6). marker({i}). 1 {{p(X,Y):d(X),d(Y)}} 1. " +
                                         "p(X,Y):-p(Y,X),d(X),d(Y),X!=Y. " * 10) for i in range(12))
    partitions = {(f"p{i}", 2): frozenset({(i, i)}) for i in range(60)}
    partition_positions = {p: relations._position_values(2, rows) for p, rows in partitions.items()}
    task = parse_text("d(1..3). #maxv(3). #maxbl(3). #maxhl(1). "
                      "#modeh(1,p(var(node,input))). #modeb(3,d(var(node,output))). "
                      "#modeb(2,r(var(node,input),var(node,output))).")

    def repeat(run, count):
        result = None
        for _ in range(count):
            result = run()
        return result

    def incremental():
        with incremental_clause_batches(task, Arguments(), 64, random.Random(31)) as batches:
            return [batch.clauses for batch in batches]

    def syntax_inspection(programs):
        if hasattr(rule_properties, "_rule_syntax"):
            cached = lru_cache(maxsize=8)(rule_properties._rule_syntax)
            result = None
            for statements in programs:
                syntax = cached(statements)
                result = (syntax.functional, syntax.functional_set, syntax.keys, syntax.project_implies,
                          syntax.cardinality, syntax.arg_distinct, syntax.symmetric)
            return result
        result = None
        for statements in programs:
            functional, composite, keys, projections, cardinality = rule_properties._choice_clause_properties(statements)
            distinct_args, symmetric = set(), set()
            rule_properties._collect_clause_defined_properties(keys, functional, composite, distinct_args, symmetric, statements)
            result = tuple(frozenset(items) for items in (functional, composite, keys, projections,
                                                        cardinality, distinct_args, symmetric))
        return result

    return {
        "coefficients_warm": lambda: repeat(lambda: (linear.coefficients, linear.linear, nonlinear.coefficients, nonlinear.linear), 10000),
        "coefficients_cold": lambda: repeat(lambda: (replace(linear), replace(nonlinear)), 1000),
        "comparison_steps": lambda: repeat(lambda: _term_comparison(bound, comparison_input), 1000),
        "comparison_prepare": lambda: repeat(lambda: replace(comparison).id, 300),
        "traits_arithmetic": lambda: repeat(lambda: canonical_arithmetic_clause(clause, by_id, 3, systems), 2000),
        "traits_plain": lambda: repeat(lambda: canonical_arithmetic_clause(plain, by_id, 3), 2000),
        "decoder_wide": lambda: repeat(lambda: _clause_from_truth(lambda literal: literal == 12500, wide_index), 200),
        "decoder_small": lambda: repeat(lambda: _clause_from_truth(lambda literal: literal == 1, small_index), 1000),
        "pairs_shared": lambda: _context_properties(worlds["shared"], None, frozenset()),
        "pairs_distinct": lambda: _context_properties(worlds["distinct"], None, frozenset()),
        "projection_aliases": projection_run(sources, targets),
        "projection_distinct": projection_run(unique_sources, unique_targets),
        "domains_shared": lambda: tuple(relations._domain_covers(repeated_domains, repeated_columns)),
        "domains_distinct": lambda: tuple(relations._domain_covers(unique_domains, unique_columns)),
        "functional_nested": lambda: relations._without_subsumed_functional_set(composite, set()),
        "functional_antichain": lambda: relations._without_subsumed_functional_set(antichain, set()),
        "syntax_inspection_repeated": lambda: syntax_inspection((program,) * 12),
        "syntax_inspection_distinct": lambda: syntax_inspection(varied_programs),
        "syntax_repeated": lambda: _closed_world_properties((program,) * 12, relevant=frozenset(), negated=frozenset()),
        "syntax_distinct": lambda: _closed_world_properties(varied_programs, relevant=frozenset(), negated=frozenset()),
        "partitions_wide": lambda: relations._partition_properties(partitions, partition_positions),
        "partitions_small": lambda: repeat(lambda: relations._partition_properties(
            dict(list(partitions.items())[:6]), dict(list(partition_positions.items())[:6])), 100),
        "complete": lambda: generate_clause_space(task, Arguments()).clauses,
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
