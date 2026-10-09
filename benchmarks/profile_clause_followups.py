"""Reproducible workloads for the second set of clause Python optimizations."""

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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import clingo  # noqa: E402
from clingo import ast  # noqa: E402

from benchmarks.profile_clause_python import canonical as _canonical  # noqa: E402
from gentians import timing  # noqa: E402
from gentians.arguments import Arguments  # noqa: E402
from gentians.clauses.analysis.ground_relations import _consequences  # noqa: E402
from gentians.clauses.analysis.inference import _closed_world_properties  # noqa: E402
from gentians.clauses.analysis.relation_properties import (  # noqa: E402
    _collect_dependency_properties,
    _collect_tuple_mutex,
)
from gentians.clauses.analysis.rule_properties import _substitute_variables  # noqa: E402
from gentians.clauses.canonicalization.canonical_clause import CanonicalArithmeticClause  # noqa: E402
from gentians.clauses.canonicalization.clauses import _clause_metadata  # noqa: E402
from gentians.clauses.clause import Clause  # noqa: E402
from gentians.clauses.metadata import ClauseMetadata  # noqa: E402
from gentians.clauses.canonicalization.expression import ArithmeticExpression  # noqa: E402
from gentians.clauses.canonicalization.expression_normalization import _mode_expression  # noqa: E402
from gentians.clauses.canonicalization.linear_constraint import LinearConstraint  # noqa: E402
from gentians.clauses.canonicalization.linear_normalization import _normalize_component  # noqa: E402
from gentians.clauses.generator import generate_clause_space, incremental_clause_batches  # noqa: E402
from gentians.clauses.mode_compiler import _clause_modes  # noqa: E402
from gentians.clauses.pruning import _known_head  # noqa: E402
from gentians.clauses.reified_clause import ReifiedClause  # noqa: E402
from gentians.clauses.reified_literal import ReifiedLiteral  # noqa: E402
from gentians.language import parse_text  # noqa: E402
from gentians.language.asp import parse_program, parse_rule  # noqa: E402
from gentians.language.ast_nodes import LOCATION  # noqa: E402


def canonical(value):
    if isinstance(value, dict):
        return sorted(([canonical(key), canonical(item)] for key, item in value.items()), key=repr)
    if isinstance(value, tuple | list):
        return [canonical(item) for item in value]
    return _canonical(value)


def workloads():
    keyed = frozenset((n, n % 2, n % 3, n % 5, n % 7, n % 11, n % 13) for n in range(500))
    unkeyed = frozenset((a, b, c, d) for a in range(3) for b in range(3) for c in range(3) for d in range(3))
    shared_rows = frozenset(tuple(n + arg for arg in range(5)) for n in range(150))
    shared = {(f"p{i}", 5): shared_rows for i in range(12)}
    distinct = {(f"p{i}", 3): frozenset({(i, i + 1, i + 2)}) for i in range(6)}
    consequence_program = parse_program("p(1..1000). -q(1..1000). {r(1..30)}. #show r/1.")
    background = parse_program("d(1..40).")
    repeated_contexts = tuple(background + parse_program(f"p({i}) :- p({i}).") for i in range(20))
    distinct_contexts = tuple(parse_program(f"d({i}). p({i}) :- p({i}).") for i in range(12))

    width = 129
    equations = tuple(LinearConstraint(tuple(
        1 if arg == index else -1 if arg == 64 else 0 for arg in range(width)
    ), "eq") for index in range(64))
    comparisons = tuple(LinearConstraint(tuple(
        1 if arg == index else -1 if arg == 64 else 0 for arg in range(width)
    ), "le") for index in range(65, width))
    expression = ArithmeticExpression.var(0)
    for index in range(100):
        expression = ArithmeticExpression("+", (expression, ArithmeticExpression.var(index % 7)))
    constraint = LinearConstraint(tuple(1 if i % 17 == 0 else 0 for i in range(1000)), "eq")
    substitution = parse_rule("h(X) :- " + ",".join(f"p{i}(Y)" for i in range(80)) + ".")
    guard = ast.SymbolicTerm(LOCATION, clingo.Number(1))
    for _ in range(180):
        guard = ast.Function(LOCATION, "f", [guard], False)
    head = ast.Aggregate(LOCATION, ast.Guard(ast.ComparisonOperator.LessEqual, guard), [], None)

    modes = _clause_modes(parse_text("#maxbl(12). #modeh(1,p(var(node,any)):" +
                                    ",".join(f"c{i}(var(node,any))" for i in range(10)) + ")."))
    modes_by_id = {mode.id: mode for mode in modes}
    head_mode = next(mode for mode in modes if mode.section == "head")
    reified = ReifiedClause((ReifiedLiteral("head", 0, head_mode.id, tuple(range(len(head_mode.bindings)))),), ())
    statement = CanonicalArithmeticClause(reified.head, (), ()).instantiate(modes_by_id)
    rendered = str(statement)
    arithmetic_mode = _clause_modes(parse_text(
        "#modeb(1,var(numeric,input)*var(numeric,input)=var(numeric,output))."
    ))[0]
    arithmetic = ReifiedLiteral("body", 0, arithmetic_mode.id, (4, 2, 9))
    known = {4: ArithmeticExpression.var(4), 2: ArithmeticExpression.var(2)}
    task = parse_text("d(1..3). #maxv(3). #maxbl(3). #maxhl(1). "
                      "#modeh(1,p(var(node,input))). #modeb(3,d(var(node,output))). "
                      "#modeb(2,r(var(node,input),var(node,output))).")

    def dependencies(rows, arity):
        functional, composite, keys = set(), set(), set()
        _collect_dependency_properties(("p", arity), rows, functional, composite, keys)
        return functional, composite, keys

    def mutex(relations):
        result = set()
        _collect_tuple_mutex(relations, result)
        return result

    def normalize():
        _normalize_component.cache_clear()
        return _normalize_component((*equations, *comparisons), (1 << 64) - 1, width)

    def variables(value):
        result = None
        for _ in range(1000):
            result = value.variables
        return result

    def metadata():
        result = None
        for _ in range(1000):
            heads, deps, cost = _clause_metadata(
                tuple(literal.mode_id for literal in reified.head),
                tuple(literal.mode_id for literal in reified.body), modes_by_id,
            )
            result = Clause(rendered, statement, ClauseMetadata.from_predicates(heads, deps, cost))
        return result

    def mode_expression():
        result = None
        for _ in range(1000):
            result = _mode_expression(arithmetic, arithmetic_mode, known)
        return result

    def incremental():
        with incremental_clause_batches(task, Arguments(), 64, random.Random(31)) as batches:
            return [batch.clauses for batch in batches]

    return {
        "dependencies_keyed": lambda: dependencies(keyed, 7),
        "dependencies_unkeyed": lambda: dependencies(unkeyed, 4),
        "mutex_shared": lambda: mutex(shared),
        "mutex_distinct": lambda: mutex(distinct),
        "consequences": lambda: _consequences(consequence_program),
        "contexts_repeated_effective": lambda: _closed_world_properties(repeated_contexts, frozenset({("p", 1)})),
        "contexts_distinct_effective": lambda: _closed_world_properties(distinct_contexts, frozenset({("p", 1)})),
        "sparse_elimination": normalize,
        "expression_variables": lambda: variables(expression),
        "linear_variables": lambda: variables(constraint),
        "head_metadata": metadata,
        "substitution_noop": lambda: _substitute_variables(substitution, {"Missing": "Z"}),
        "substitution_sparse": lambda: _substitute_variables(substitution, {"X": "Z"}),
        "mode_expression_small": mode_expression,
        "head_guard_walk": lambda: _known_head(head),
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
            started = time.perf_counter()
            result = run()
            samples.append(time.perf_counter() - started)
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
