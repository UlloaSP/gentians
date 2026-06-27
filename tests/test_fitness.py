import importlib

from gentians.evolution.fitness.coverage_exp_max import coverage_exp_max
from gentians.rule_generation.program import Example, Program


def test_coverage_exp_max_checks_all_models_before_best_found():
    program = Program(
        ["base."],
        [Example(("target", ""), True)],
        [Example(("target", ""), False)],
        [],
        [],
    )

    score, best_found, indexes = coverage_exp_max(program, 0, [], -2000)(
        ["target :- base."],
    )

    assert score == 1.0
    assert best_found is False
    assert indexes == []


def test_coverage_exp_mean_reuses_solver_for_evaluations(monkeypatch):
    mean_module = importlib.import_module("gentians.evolution.fitness.coverage_exp_mean")
    instances = []

    class FakeSolver:
        def __init__(self, lines, clingo_arguments):
            self.lines = lines
            self.clingo_arguments = clingo_arguments
            instances.append(self)

        def extract_coverage_and_set_clauses(
            self,
            candidate_program,
            interpretation_pos,
            interpretation_neg,
            fixed,
        ):
            return {}

    monkeypatch.setattr(mean_module, "ClingoInterface", FakeSolver)
    program = Program(["base."], [], [], [], [])

    evaluate_score = mean_module.coverage_exp_mean(program, 7, ["--project"], -2000)
    evaluate_score(["a."])
    evaluate_score(["b."])

    assert len(instances) == 1
    assert instances[0].lines == ["base."]
    assert instances[0].clingo_arguments == ["7", "--project"]
