from benchmarks.profile_pool_evaluator import candidate_sequence, replay
from gentians import timing
from gentians.hypotheses import HypothesisGenerator
from tests.task_helpers import example, inductive_task, make_clause_space


def test_replay_reuses_identical_valid_candidates_and_counts_rebuilds():
    task = inductive_task(
        [], [example(("target(p)", ""), True)],
        [example(("target(n)", ""), False)], [], [],
    )
    hypotheses = HypothesisGenerator(
        task, make_clause_space(["target(p).", "target(n)."]), 2,
    )
    genomes = candidate_sequence(hypotheses, 7, 9)
    assert genomes == candidate_sequence(hypotheses, 7, 9)
    config = {"scoring": "cov_program", "clingo_arguments": []}
    try:
        fresh, fresh_metrics = replay(task, config, hypotheses, genomes, 4, False)
        pooled, pool_metrics = replay(task, config, hypotheses, genomes, 4, True)
        assert fresh == pooled
        assert fresh_metrics["ground_calls"] == 9
        assert pool_metrics["ground_calls"] == 3
        assert pool_metrics["solve_calls"] == fresh_metrics["solve_calls"] == 9
        assert pool_metrics["grounding_seconds"] > 0
        assert pool_metrics["solving_seconds"] > 0
    finally:
        timing.reset()
        timing.set_enabled(False)
