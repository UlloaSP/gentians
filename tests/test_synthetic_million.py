from pathlib import Path

from benchmarks.synthetic_million import clause_count, scaling_task_text, task_parts, task_text
from gentians.arguments import Arguments
from gentians.clauses import generate_clause_space
from gentians.evaluation import create_evaluator
from gentians.language import parse_text
from gentians.language.asp import parse_program


def test_reduced_synthetic_space_has_every_feature_subset():
    for features in (6, 8):
        space = generate_clause_space(parse_text(task_text(features)), Arguments())
        assert len(space) == clause_count(features)
        assert all(not clause.heads and 1 <= len(clause.statement.body) <= 6
                   for clause in space.entries)
    assert clause_count() == 1_149_016


def test_million_task_has_a_perfect_six_clause_reference_and_rejects_empty():
    task = parse_text(task_text())
    evaluator = create_evaluator(task, Arguments().evaluation)
    reference = parse_program("\n".join(
        f":- f{2 * pair}(X), f{2 * pair + 1}(X)." for pair in range(6)))
    assert evaluator(reference).is_solution
    assert not evaluator(()).is_solution
    fixture = Path(__file__).parents[1] / "benchmarks/gentians/synthetic_million"
    assert {name: (fixture / name).read_text(encoding="utf-8")
            for name in ("bk.lp", "exs.lp", "bias.lp")} == task_parts(task_text())


def test_scaling_changes_only_body_limit_and_keeps_reference_solution():
    source = task_text()
    fixed = [line for line in source.splitlines()
             if not line.startswith(("% Legal clauses:", "#maxbl"))]
    reference = parse_program("\n".join(
        f":- f{2 * pair}(X), f{2 * pair + 1}(X)." for pair in range(6)))
    for max_body in range(2, 7):
        scaled = scaling_task_text(max_body)
        assert [line for line in scaled.splitlines()
                if not line.startswith(("% Legal clauses:", "#maxbl"))] == fixed
        task = parse_text(scaled)
        assert len(task.language_bias_body) == 32
        assert task.max_body_literals == max_body
        assert create_evaluator(task, Arguments().evaluation)(reference).is_solution
    assert scaling_task_text(6) == source




