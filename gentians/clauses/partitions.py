"""Exhaustive first-body-mode partitions in independent one-thread Controls."""

import os
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import lru_cache
from multiprocessing import get_context
from pathlib import Path

import clingo
from clingo.configuration import Configuration
from typing import cast

from ..language.asp import add_program
from ..timing import add, record_metric, metric_enabled, instrumentation
from .canonicalization.clauses import ClauseCanonicalizer
from .canonicalization.canonical_clause import CanonicalArithmeticClause
from .clause_space import ClauseSpace
from .decoder import _ModelDecoder, _clause_from_model
from .serialization import recipe_bytes, read_recipe, read_recipe_file, RecipePickler


def partition_constraints(ids: tuple[int, ...], include_empty: bool) -> str:
    allowed = "\n".join(f"partition_mode({identifier})." for identifier in ids)
    return allowed + "\n:- selected(body,0,M), not partition_mode(M)." + (
        "" if include_empty else "\n:- not selected_slot(body,0)."
    )


def _worker(data: bytes, ids: tuple[int, ...], include_empty: bool, path: str):
    from .generator import CLAUSE_METAPROGRAM
    from ..clingo_stats import clingo_statistics
    from .records import ModelRecords, _records
    modes, max_variables, facts, arguments, transport, callback_policy, projected = read_recipe(data)
    modes_by_id = {mode.id: mode for mode in modes}
    ctl = clingo.Control(arguments)
    cast(Configuration, ctl.configuration.solve).parallel_mode = "1"
    cast(Configuration, ctl.configuration.solve).models = "0"
    if projected:
        cast(Configuration, ctl.configuration.solve).project = "project"
    ctl.add("base", [], facts + "\n" + partition_constraints(ids, include_empty))
    add_program(ctl, CLAUSE_METAPROGRAM)
    start = time.perf_counter()
    ctl.ground([("base", [])])
    grounding = time.perf_counter() - start
    decoder = _ModelDecoder(ctl.symbolic_atoms, modes_by_id)
    canonicalizer = ClauseCanonicalizer(modes_by_id, max_variables)
    records = ModelRecords(decoder) if transport != "python" and _records is not None else None
    callback = 0.0

    def collect(model):
        nonlocal callback
        started = time.perf_counter()
        if records is None:
            canonicalizer.add(_clause_from_model(model, decoder))
        else:
            block = records.push(model)
            if block is not None:
                for clause in records.clauses(block):
                    canonicalizer.add(clause)
        callback += time.perf_counter() - started

    start = time.perf_counter()
    if records is not None and callback_policy == "native":
        def consume(block):
            for clause in records.clauses(block):
                canonicalizer.add(clause)
        _models, callback = records.solve(ctl, consume, measure=True)
    else:
        ctl.solve(on_model=collect)
    solving = time.perf_counter() - start - callback
    if records is not None:
        started = time.perf_counter()
        block = records.flush()
        if block is not None:
            for clause in records.clauses(block):
                canonicalizer.add(clause)
        callback += time.perf_counter() - started
    # Native recipe AST fields are serialized structurally; pointers never cross.
    with Path(path).open("wb", buffering=1024 * 1024) as file:
        pickler = RecipePickler(file, protocol=5)
        for key, current in canonicalizer.representatives.items():
            if current is not None:
                text, canonical, (raw_count, metadata) = current
                pickler.dump((key, (text, canonical, (raw_count, metadata.head_mask, metadata.dep_mask, metadata.body_literals))))
                pickler.clear_memo()
        pickler.dump(None)
    return grounding, solving, callback, clingo_statistics(ctl)


def partitioned_space(generator, workers: int) -> ClauseSpace:
    body = tuple(mode.id for mode in generator.modes if mode.section == "body")
    count = min(workers, max(1, len(body)))
    if workers < 1 or workers > (os.cpu_count() or 1):
        raise ValueError("clause_generation.workers must fit the available CPU count")
    # Static contiguous ranges preserve order; more shards than workers reduce
    # skew without consulting a previous space or benchmark name.
    shards = min(len(body), count * 4) if body else 1
    groups = [body[len(body) * index // shards:len(body) * (index + 1) // shards]
              for index in range(shards)]
    data = recipe_bytes((generator.modes, generator.max_variables,
                         generator._fact_text(), generator.solver_arguments(),
                         generator.args.clause_generation.get("transport", "auto"),
                         generator.args.clause_generation.get("callback", "native"),
                         generator.projected_components))
    results = {}
    with tempfile.TemporaryDirectory(prefix="gentians-clauses-") as directory:
        paths = [str(Path(directory) / f"part-{i}.pickle") for i in range(shards)]
        executor = ProcessPoolExecutor(max_workers=count, mp_context=get_context("spawn"))
        try:
            futures = [executor.submit(_worker, data, group, index == 0, path)
                       for index, (group, path) in enumerate(zip(groups, paths, strict=True))]
            indices = {future: index for index, future in enumerate(futures)}
            for future in as_completed(futures):
                results[indices[future]] = future.result()
        except BaseException:
            processes = tuple((getattr(executor, "_processes", None) or {}).values())
            try:
                executor.terminate_workers()
            finally:
                # Windows TerminateProcess can return before open output files
                # close. Reap workers before TemporaryDirectory removes files.
                for process in processes:
                    process.join()
            raise
        else:
            executor.shutdown()
        rows = [results[index] for index in range(shards)]
        canonicalizer = ClauseCanonicalizer(generator.modes_by_id, generator.max_variables)
        intern_literal = lru_cache(maxsize=8192)(lambda literal: literal)
        intern_system = lru_cache(maxsize=8192)(lambda system: system)
        for path in paths:
            with Path(path).open("rb") as file:
                while (record := read_recipe_file(file)) is not None:
                    key, current = record
                    old = canonicalizer.representatives.get(key)
                    if old is None or (current[2][0], current[0]) < (old[2][0], old[0]):
                        text, canonical, source = current
                        canonical = CanonicalArithmeticClause(
                            tuple(map(intern_literal, canonical.head)), tuple(map(intern_literal, canonical.body)),
                            tuple(map(intern_system, canonical.systems)))
                        raw_count, head_mask, dep_mask, cost = source
                        source = raw_count, canonicalizer.metadata.from_masks(head_mask, dep_mask, cost)
                        canonicalizer.representatives[key] = text, canonical, source
        space = ClauseSpace(canonicalizer.finish(), pack=generator.args.clause_generation.get("storage", "auto") == "packed")
    # These are process-work seconds, which overlap across workers. Never put
    # their sums into wall-time grounding/solving fields or dashboard charts.
    if metric_enabled("clingo"):
        with instrumentation():
            for ordinal, (grounding, solving, callback, stats) in enumerate(rows):
                record_metric("clingo", {
                    "operation_category": "generation_worker", "phase_context": "clause_generation",
                    "worker_partition": ordinal, "seconds": grounding + solving + callback,
                    "grounding_work_seconds": grounding, "solving_work_seconds": solving,
                    "python_work_seconds": callback, "models": stats["models"],
                    "stats_atoms": stats["atoms"], "stats_rules": stats["rules"],
                    "stats_choices": stats["choices"], "stats_conflicts": stats["conflicts"],
                })
    add("clause_generation.worker_grounding_work", sum(row[0] for row in rows))
    add("clause_generation.worker_solving_work", sum(row[1] for row in rows))
    return space
