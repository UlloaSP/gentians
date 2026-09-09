from pathlib import Path

from benchmarks.synthetic_million import clause_count, task_text
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
    fixture = Path(__file__).parents[1] / "benchmarks/gentians/synthetic_million.txt"
    assert fixture.read_text(encoding="utf-8") == task_text()




