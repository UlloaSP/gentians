import importlib

from gentians.asp.coverage import Coverage
from gentians.evolution.fitness.coverage_common import cached_fitness
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


def test_coverage_exp_mean_canonicalizes_duplicate_rules_before_clingo(monkeypatch):
    mean_module = importlib.import_module("gentians.evolution.fitness.coverage_exp_mean")
    calls = []

    class FakeSolver:
        def __init__(self, lines, clingo_arguments):
            self.lines = lines
            self.clingo_arguments = clingo_arguments

        def extract_coverage_and_set_clauses(
            self,
            candidate_program,
            interpretation_pos,
            interpretation_neg,
            fixed,
        ):
            calls.append(candidate_program)
            return {}

    monkeypatch.setattr(mean_module, "ClingoInterface", FakeSolver)
    program = Program(["base."], [], [], [], [])

    evaluate_score = mean_module.coverage_exp_mean(program, 0, ["--project"], -2000)
    evaluate_score(["b.", "a.", "a."])
    evaluate_score(["a.", "b."])

    assert calls == [["a.", "b."]]


def test_cached_fitness_maps_canonical_selected_rules_to_original_indexes():
    cache = {}
    calls = []

    def compute(candidate_program):
        calls.append(candidate_program)
        return 1.0, True, [0, 1]

    score, best_found, indexes = cached_fitness(cache, ["b.", "a.", "a."], compute)

    assert (score, best_found) == (1.0, True)
    assert calls == [["a.", "b."]]
    assert indexes == [1, 0]


def test_coverage_exp_mean_reuses_cached_subprogram_coverage(monkeypatch):
    mean_module = importlib.import_module("gentians.evolution.fitness.coverage_exp_mean")
    calls = []

    class FakeSolver:
        def __init__(self, lines, clingo_arguments):
            self.lines = lines
            self.clingo_arguments = clingo_arguments

        def extract_coverage_and_set_clauses(
            self,
            candidate_program,
            interpretation_pos,
            interpretation_neg,
            fixed,
        ):
            calls.append(candidate_program)
            return {
                (): Coverage([], []),
                (0,): Coverage([], []),
                (1,): Coverage([], []),
                (0, 1): Coverage([], []),
            }

    monkeypatch.setattr(mean_module, "ClingoInterface", FakeSolver)
    program = Program(["base."], [], [], [], [])

    evaluate_score = mean_module.coverage_exp_mean(program, 0, ["--project"], -2000)
    evaluate_score(["a.", "b."])
    evaluate_score(["a."])

    assert calls == [["a.", "b."]]
