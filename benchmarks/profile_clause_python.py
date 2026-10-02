"""Reproducible Python workloads for clause compilation (no task-file edits)."""

import argparse
from dataclasses import fields, is_dataclass
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

from gentians import timing  # noqa: E402
from gentians.arguments import Arguments  # noqa: E402
from gentians.clauses import mode_compiler, mode_facts  # noqa: E402
from gentians.clauses.analysis.ground_relations import _closed_world  # noqa: E402
from gentians.clauses.analysis.inference import _context_properties  # noqa: E402
from gentians.clauses.analysis.relation_properties import (  # noqa: E402
    _collect_projection_implications,
    _partition_properties,
    _position_values,
)
from gentians.clauses.canonicalization.arithmetic_system import ArithmeticSystem  # noqa: E402
from gentians.clauses.canonicalization.linear_constraint import LinearConstraint  # noqa: E402
from gentians.clauses.canonicalization.linear_normalization import _orient_linear_constraints  # noqa: E402
from gentians.clauses.generator import generate_clause_space, incremental_clause_batches  # noqa: E402
from gentians.language import parse_text  # noqa: E402
from gentians.language import terms as mode_terms  # noqa: E402
from gentians.language.asp import parse_program  # noqa: E402
from gentians.language.ir.atom_literal import AtomLiteral  # noqa: E402


def workloads():
    comparisons = parse_text("#maxhl(2). #maxbl(2). " + " ".join(
        f"#modeh(1,p{i}(var(numeric,any,x));q{i}(var(numeric,any,x)))." for i in range(16)
    ) + " #modeb(1,d(var(numeric,any,x))). #modec(1,var(numeric,input,x)=var(numeric,input,y)+1).")
    comparison_modes = mode_compiler._clause_modes(comparisons)
    aggregates = parse_text(" ".join(
        f"#modeb(1,#sum{{var(numeric,any,x),var(numeric,any,y):p{i}(var(numeric,any,x),var(numeric,any,y))}}=var(numeric,output))."
        for i in range(100)
    ))
    aggregate_modes = mode_compiler._clause_modes(aggregates)
    pool_task = parse_text("#modeb(1,p(" + "f(" * 180 + "var(node,any)" + ")" * 180 + ")).")
    pool = pool_task.language_bias_body[0].literal
    assert isinstance(pool, AtomLiteral)
    heads = parse_text("#maxhl(3). #maxbl(0). " + " ".join(
        f"#constant(colour,c{i})." for i in range(5)
    ) + " #modeha(3,p(var(node,input),const(colour))).")
    relations = {(f"p{i}", 2): frozenset({(i, i)}) for i in range(20)}
    sources = {("source", 8): frozenset(tuple(i * 100 + n for i in range(8)) for n in range(30))}
    targets = {("target", 5): frozenset(tuple(i * 100 + n for i in range(5)) for n in range(30))}
    uniform_sources = {("source", 8): frozenset((n,) * 8 for n in range(30))}
    uniform_targets = {("target", 5): frozenset((n,) * 5 for n in range(30))}
    linear = tuple(LinearConstraint(tuple(
        -1 if variable == index else 1 if variable == index + 1 else 0
        for variable in range(181)
    ), "eq") for index in reversed(range(180)))
    system = ArithmeticSystem(tuple(LinearConstraint((1, index), "eq") for index in range(100)))
    context = parse_program(" ".join(f"p{i}(1..15,1..15)." for i in range(8)))
    world = _closed_world(context, frozenset())
    assert world is not None
    task = parse_text("d(1..3). #maxv(3). #maxbl(3). #maxhl(1). "
                      "#modeh(1,p(var(node,input))). #modeb(3,d(var(node,output))). "
                      "#modeb(2,r(var(node,input),var(node,output))).")

    def facts(modes):
        return mode_facts.compile_mode_facts(modes, mode_facts.predicate_ids(modes), 2, 2)

    def projections(source_relations, target_relations):
        result = set()
        _collect_projection_implications(source_relations, target_relations, result, {
            predicate: _position_values(predicate[1], rows)
            for predicate, rows in {**source_relations, **target_relations}.items()
        })
        return sorted(result)

    def modes():
        return mode_compiler._clause_modes(heads)

    def pool_bindings():
        mode_terms.bindings.cache_clear()
        return mode_facts._pool_alternative_positions(pool.atom)

    def keys():
        result = None
        for _ in range(10000):
            result = system.key
        return result

    def complete():
        return generate_clause_space(task, Arguments()).clauses

    def incremental():
        import random
        with incremental_clause_batches(task, Arguments(), 64, random.Random(31)) as batches:
            return [batch.clauses for batch in batches]

    return {
        "comparison_facts": lambda: facts(comparison_modes),
        "pool_bindings": pool_bindings,
        "aggregate_facts": lambda: facts(aggregate_modes),
        "head_modes": modes,
        "partitions": lambda: sorted(_partition_properties(relations, {
            predicate: _position_values(predicate[1], rows) for predicate, rows in relations.items()
        })),
        "projections": lambda: projections(sources, targets),
        "projections_uniform": lambda: projections(uniform_sources, uniform_targets),
        "linear_readiness": lambda: _orient_linear_constraints(linear, {0}),
        "system_keys": keys,
        "context_properties": lambda: _context_properties(world, None, None),
        "complete": complete,
        "incremental": incremental,
    }


def canonical(value):
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: canonical(getattr(value, field.name)) for field in fields(value) if field.compare}
    if isinstance(value, clingo.ast.AST):
        return str(value)
    if isinstance(value, set | frozenset):
        return sorted((canonical(item) for item in value), key=repr)
    if isinstance(value, tuple | list):
        return [canonical(item) for item in value]
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=7)
    cases = workloads()
    parser.add_argument("--workloads", nargs="+", choices=tuple(cases))
    parser.add_argument("--memory", action="store_true", help="Measure peak allocations separately from time.")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    timing.set_enabled(False)
    rows = []
    for name in args.workloads or cases:
        run = cases[name]
        run()
        samples = []
        for _ in range(args.repeats):
            started = time.perf_counter()
            result = run()
            samples.append(time.perf_counter() - started)
        row = {"workload": name, "median_seconds": statistics.median(samples), "samples": samples}
        # Fingerprints complement semantic tests; they are not equivalence proofs.
        row["fingerprint"] = hashlib.sha256(json.dumps(canonical(result), sort_keys=True).encode()).hexdigest()
        if args.memory:
            del result
            tracemalloc.start()
            result = run()
            _, row["peak_bytes"] = tracemalloc.get_traced_memory()
            tracemalloc.stop()
        rows.append(row)
        print(json.dumps(row), flush=True)
    print(json.dumps({"python": sys.version, "clingo": clingo.__version__,
                      "platform": platform.platform(), "processor": platform.processor()}))


if __name__ == "__main__":
    main()
