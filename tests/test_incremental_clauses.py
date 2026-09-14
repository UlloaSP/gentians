import gc
import random
import weakref
from contextlib import contextmanager

import pytest

from gentians.algorithms import incremental_clause_genetic as search
from gentians.algorithms import incremental_clause_pool as clause_pool
from gentians.algorithms import incremental_progress as progress
from gentians.algorithms import search_budget
from gentians.arguments import Arguments
from gentians.clauses import generate_clause_space, incremental_clause_batches
from gentians.language import parse_text
from tests.task_helpers import example, inductive_task, make_clause_space
from benchmarks.synthetic_million import task_text
from gentians import timing
from gentians.clauses import generator as generation




@pytest.mark.parametrize("size", [0, -1, True, 1.5])
def test_invalid_batch_size(size):
    with pytest.raises(ValueError, match="positive integer"):
        with incremental_clause_batches(parse_text(""), Arguments(), size, random.Random(1)):
            pytest.fail("invalid size accepted")




@pytest.mark.parametrize("fail", [False, True])
def test_incremental_close_excludes_consumer_time_and_cancels_solver(monkeypatch, fail):
    clock = [0.0]
    rows = []
    timing.reset()
    monkeypatch.setattr(timing, "_enabled", True)
    monkeypatch.setattr(timing.time, "perf_counter", lambda: clock[0])
    monkeypatch.setattr(generation, "metric_enabled", lambda kind: True)
    monkeypatch.setattr(generation, "record_metric", lambda kind, row: rows.append(row))
    try:
        try:
            with timing.phase("total_execution"):
                with incremental_clause_batches(
                    parse_text(task_text(6)), Arguments(), 2, random.Random(7)
                ) as batches:
                    assert len(next(batches)) == 2
                    assert timing.current_phase() == "total_execution"
                    clock[0] += 100
                    if fail:
                        raise RuntimeError("consumer failed")
        except RuntimeError as error:
            assert fail and str(error) == "consumer failed"
        assert next(batches, None) is None
        assert timing.recorded_seconds("total_execution") == 100
        assert timing.recorded_seconds("clause_generation") == 0
        assert timing._counts["clause_generation.grounding"] == 1
        assert timing._counts["clause_generation.solving"] >= 1
        assert rows[-1]["models"] == 2
    finally:
        timing.reset()


def test_incremental_search_keeps_searching_after_exhaustion(monkeypatch):
    task = parse_text("#maxv(0). #maxbl(0). #modeh(1,p). #pos({q},{}).")
    generations = []
    monkeypatch.setattr(progress, "record_ga_generation", lambda generation, *a, **kw:
                        generations.append(generation))
    args = Arguments(iterations_genetic=4, random_seed=7,
                     incremental={ "batch_size": 2,
                                  "epoch_generations": 1, "elite_count": 1})
    result = search.incremental_clause_genetic_search(args, task)
    assert result.hypothesis == ("p.",)
    assert not result.is_solution
    assert generations == list(range(5))


def test_incremental_search_skips_pruned_batches_until_a_valid_hypothesis(monkeypatch):
    @contextmanager
    def batches(*args, **kwargs):
        yield iter([*[make_clause_space([])] * 64, make_clause_space(["p."])])

    monkeypatch.setattr(clause_pool, "incremental_clause_batches", batches)
    task = parse_text("#maxv(0). #maxbl(0). #modeh(1,p). #pos({p},{}).")
    args = Arguments(iterations_genetic=1, random_seed=7,
                     incremental={ "batch_size": 2,
                                  "epoch_generations": 1, "elite_count": 1})
    assert search.incremental_clause_genetic_search(args, task).is_solution


@pytest.mark.parametrize("head", ["p", "-p", "p;q", "{p}", "1 {p;q} 1"])
def test_incremental_batches_preserve_nonmonotonic_clause_forms(head):
    task = parse_text(f"""
        {{base}}. {{blocked}}.
        #maxv(0). #maxbl(2). #maxhl(2).
        #modeh(1,{head}).
        #modeb(1,base).
        #modeb(1,not blocked).
    """)
    args = Arguments()
    full = generate_clause_space(task, args)
    with incremental_clause_batches(task, args, 2, random.Random(7)) as batches:
        visited = {clause for batch in batches for clause in batch.clauses}
    assert visited == set(full.clauses)
    assert any("not blocked" in clause for clause in visited)


@pytest.mark.parametrize("source", [task_text(6), """
    {base;blocked;q}.
    #maxv(0). #maxbl(3). #maxhl(1).
    #modeh(1,p:base).
    #modeb(1,not blocked).
    #modec(1,q).
"""])
def test_body_size_order_preserves_space_counts_conditions_and_grounds_once(monkeypatch, source):
    task = parse_text(source)
    args = Arguments()
    expected = generate_clause_space(task, args)
    rows = []
    monkeypatch.setattr(generation, "metric_enabled", lambda kind: True)
    monkeypatch.setattr(generation, "record_metric", lambda kind, row: rows.append(row))
    with incremental_clause_batches(task, args, 8, random.Random(5)) as batches:
        materialized = list(batches)
    clauses = [clause for batch in materialized for clause in batch.entries]
    sizes = [clause.body_literals for clause in clauses]
    assert sizes == sorted(sizes)
    assert {clause.text for clause in clauses} == set(expected.clauses)
    assert all(len(batch) <= 8 for batch in materialized)
    assert sum(row["operation_category"] == "grounding" for row in rows) == 1
    assert sum(row.get("models", 0) for row in rows) >= len(expected)
    assert sum(row["operation_category"] == "solving" for row in rows) > 1


def test_bounded_epochs_drop_old_spaces_and_never_enumerate_all(monkeypatch):
    references = []
    batches = []
    original = clause_pool.HypothesisGenerator
    original_population = search.create_population

    def population_factory(config):
        initialize = original_population(config)

        def initialize_current(context):
            gc.collect()
            # Old spaces must be released before evaluating the renewed pool,
            # not just before drawing the next batch.
            assert sum(reference() is not None for reference in references) <= 1
            return initialize(context)

        return initialize_current

    def generator(*args):
        result = original(*args)
        assert len(result.space) <= 6  # Archive, fresh batch, and a two-clause elite.
        references.append(weakref.ref(result))
        return result

    def sample(_task, _args, size, _rng):
        assert size == 2
        gc.collect()
        assert sum(reference() is not None for reference in references) <= 1
        index = len(batches)
        batch = make_clause_space([f"target(a{index}).", f"target(b{index})."])
        batches.append(batch.clauses)
        return batch

    def exhaustive(*_args):
        pytest.fail("sampled search must not enumerate the full ClauseSpace")

    @contextmanager
    def continuous(*args, **kwargs):
        def draw():
            while True:
                yield sample(*args)
        iterator = draw()
        try:
            yield iterator
        finally:
            iterator.close()

    monkeypatch.setattr(clause_pool, "HypothesisGenerator", generator)
    monkeypatch.setattr(clause_pool, "incremental_clause_batches", continuous)
    monkeypatch.setattr(search, "create_population", population_factory)
    task = inductive_task([], [example(("target(z)", ""), True)], [], [], [],
                          max_program_clauses=2)
    args = Arguments(iterations_genetic=4, random_seed=4,
                     evaluation={"scoring": "cov_program", "constraint_inheritance": False},
                     population={"name": "random", "size": 3},
                     incremental={ "batch_size": 2, "archive_size": 2,
                                  "epoch_generations": 1, "elite_count": 1})
    result = search.incremental_clause_genetic_search(args, task)
    assert len(batches) == 4
    assert set(result.hypothesis) <= {text for batch in batches for text in batch}
    gc.collect()
    assert all(reference() is None for reference in references)


def test_time_budget_counts_generation_and_rejects_late_evaluations(monkeypatch):
    source = "incremental"
    from gentians.evaluation.result import EvaluationResult

    clock = [0.0]
    closed = []
    monkeypatch.setattr(search_budget, "net_time", lambda: clock[0])
    space = make_clause_space(["p.", "q."])

    def sample(*args):
        clock[0] += 20.0
        return space

    @contextmanager
    def batches(*args, **kwargs):
        try:
            yield iter([sample()])
        finally:
            closed.append(True)

    calls = []

    def evaluate(program):
        calls.append(tuple(map(str, program)))
        clock[0] += 6.0
        return EvaluationResult(float(len(calls)), False, (0, 0), False, True)

    monkeypatch.setattr(clause_pool, "incremental_clause_batches", batches)
    monkeypatch.setattr(search, "create_evaluator", lambda *a: evaluate)
    monkeypatch.setattr(search, "create_population", lambda *a: lambda ctx: [1, 2])
    args = Arguments(iterations_genetic=0, random_seed=1)
    args.incremental.update(time_limit_seconds=30)
    result = search.incremental_clause_genetic_search(args, parse_text("#maxpl(1)."))
    assert len(calls) == 2
    assert result.score == 1.0  # Second evaluation completed at 32 seconds.
    assert result.hypothesis == calls[0]
    assert closed == ([True] if source == "incremental" else [])


def test_incremental_retains_unclosed_clauses_until_provider_arrives(monkeypatch):
    @contextmanager
    def batches(*args):
        yield iter([make_clause_space(["p :- helper."]),
                    make_clause_space(["helper."])])

    monkeypatch.setattr(clause_pool, "incremental_clause_batches", batches)
    task = parse_text("#maxpl(2). #pos({p},{}).")
    args = Arguments(iterations_genetic=100, random_seed=7)
    args.evaluation["constraint_inheritance"] = False
    result = search.incremental_clause_genetic_search(args, task)
    assert result.is_solution
    assert set(result.hypothesis) == {"p :- helper.", "helper."}


def test_initial_exhaustion_with_overflow_does_not_restart_forever(monkeypatch):
    calls = []

    @contextmanager
    def batches(*args):
        calls.append(True)
        assert len(calls) == 1, "unconstructible initial space must terminate"
        yield iter([make_clause_space(["p :- absent."]),
                    make_clause_space(["q :- absent."])])

    monkeypatch.setattr(clause_pool, "incremental_clause_batches", batches)
    args = Arguments(iterations_genetic=1, random_seed=1)
    args.incremental["archive_size"] = 1
    with pytest.raises(ValueError, match="exhausted"):
        search.incremental_clause_genetic_search(args, parse_text("#pos({p},{})."))


def test_overflow_revisits_finite_stream_after_initialization(monkeypatch):
    passes = []

    @contextmanager
    def batches(*args):
        passes.append(True)
        yield iter([make_clause_space(["p."]), make_clause_space(["q."])])

    monkeypatch.setattr(clause_pool, "incremental_clause_batches", batches)
    args = Arguments(iterations_genetic=5, random_seed=1)
    args.incremental.update(archive_size=1, epoch_generations=1)
    result = search.incremental_clause_genetic_search(args, parse_text("#pos({absent},{})."))
    assert not result.is_solution
    assert len(passes) == 3
