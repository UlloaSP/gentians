import importlib
import math

from benchmarks.catalog import arguments_for
from gentians.asp.coverage import Coverage
from gentians.asp.coverage import generate_clauses_for_coverage_interpretations
from gentians.evolution.fitness.coverage_fixed import coverage_fixed
from gentians.evolution.fitness.coverage_common import cached_fitness
from gentians.evolution.fitness.coverage_exp_max import coverage_exp_max
from gentians.rule_generation.hypothesis_space import read_task
from gentians.rule_generation.program import Example, Program
from gentians.rule_generation.rule_space import RuleSpace


def test_excluded_atoms_are_checked_individually():
    clauses = generate_clauses_for_coverage_interpretations(
        [Example(("ok", "bad(1), bad(f(2,3))"), True)],
        True,
    )

    assert "cpe(0):- bad(1)." in clauses
    assert "cpe(0):- bad(f(2,3))." in clauses
    assert "cpe(0):- bad(1), bad(f(2,3))." not in clauses


def test_coverage_fixed_penalizes_brave_negative_violation():
    program = Program(
        ["1 { a; b } 1."],
        [Example(("a", ""), True)],
        [Example(("a", ""), False)],
        [],
        [],
    )

    score, best_found, indexes = coverage_fixed(
        program, 0, [], -2000, 0.01, 0.002, 0.01, RuleSpace.from_clauses([])
    )([])

    assert score == math.exp(10)
    assert best_found is False
    assert indexes == []


def test_coverage_fixed_uses_brave_positive_coverage():
    program = Program(
        ["1 { a; b } 1."],
        [Example(("a", ""), True), Example(("b", ""), True)],
        [],
        [],
        [],
    )

    score, best_found, indexes = coverage_fixed(
        program, 0, [], -2000, 0.01, 0.002, 0.01, RuleSpace.from_clauses([])
    )([])

    assert score == math.exp(15)
    assert best_found is True
    assert indexes == []


def test_coverage_fixed_prefers_positive_coverage_over_clean_overconstraint():
    program = Program(
        ["1 { a; b } 1."],
        [Example(("a", ""), True)],
        [Example(("b", ""), False)],
        [],
        [],
    )
    rule_space = RuleSpace.from_clauses([":- b.", ":- a."])
    evaluate = coverage_fixed(program, 0, [], -2000, 0.01, 0.002, 0.01, rule_space)

    covering_score, _, _ = evaluate([1])
    overconstrained_score, _, _ = evaluate([0, 1])

    assert covering_score > overconstrained_score


def test_coverage_fixed_uses_pregrounded_rule_space(monkeypatch):
    def fail_fallback(*args, **kwargs):
        raise AssertionError("fixed coverage should use pregrounded rule space")

    monkeypatch.setattr(
        "gentians.asp.clingo.ClingoInterface.extract_fixed_coverage",
        fail_fallback,
    )
    program = Program(
        ["1 { a; b } 1."],
        [Example(("a", ""), True)],
        [Example(("b", ""), False)],
        [],
        [],
    )

    score, best_found, indexes = coverage_fixed(
        program,
        0,
        [],
        -2000,
        0.01,
        0.002,
        0.01,
        rule_space=RuleSpace.from_clauses([":- b."]),
    )([0])

    assert math.isclose(score, math.exp(14.94))
    assert best_found is True
    assert indexes == [0]


def test_coverage_fixed_uses_one_normal_search_for_fixed_coverage(monkeypatch):
    fixed_module = importlib.import_module("gentians.evolution.fitness.coverage_fixed")
    instances = []
    calls = []

    class FakeSolver:
        def __init__(self, lines, clingo_arguments):
            self.clingo_arguments = clingo_arguments
            instances.append(self)

        def fixed_coverage_solver(self, rule_space, interpretation_pos, interpretation_neg):
            calls.append((tuple(self.clingo_arguments), bool(interpretation_pos), bool(interpretation_neg)))

            class FakePreGrounded:
                def extract_fixed_coverage_by_id(self, candidate_program):
                    calls.append(tuple(candidate_program))
                    return Coverage([0], [0])

            return FakePreGrounded()

    monkeypatch.setattr(fixed_module, "ClingoInterface", FakeSolver)
    program = Program(
        [],
        [Example(("p", ""), True)],
        [Example(("n", ""), False)],
        [],
        [],
    )

    score, best_found, indexes = fixed_module.coverage_fixed(
        program,
        0,
        ["--project"],
        -2000,
        0.0,
        0.0,
        0.0,
        RuleSpace.from_clauses([]),
    )([])

    assert instances[0].clingo_arguments == ["0", "--project"]
    assert calls == [
        (("0", "--project"), True, True),
        (),
    ]
    assert (score, best_found, indexes) == (math.exp(10), False, [])


def test_coverage_fixed_rejects_sudoku_without_row_constraint():
    rules = [
        ":- same_row(V0,V0),same_col(V0,V0),same_block(V1,V1).",
        ":- same_row(V0,V0),same_col(V1,V1),same_block(V1,V1).",
        ":- same_row(V0,V1),same_col(V0,V0),same_block(V1,V1).",
        ":- same_row(V0,V1),same_col(V1,V0),same_block(V1,V1).",
        ":- value(V0,V1),value(V2,V1),same_block(V0,V2).",
        ":- value(V0,V1),value(V2,V1),same_col(V0,V2).",
    ]
    args = arguments_for("sudoku")
    program = read_task(args.filename)

    rule_space = RuleSpace.from_clauses(rules)
    _, best_found, _ = coverage_fixed(
        program,
        int(args.fitness["max_as"]),
        list(args.fitness["clingo_arguments"]),
        float(args.fitness["empty_score"]),
        float(args.fitness["size_penalty"]),
        float(args.fitness["literal_penalty"]),
        float(args.fitness["redundancy_penalty"]),
        rule_space=rule_space,
    )(rule_space.ids)

    assert best_found is False


def test_coverage_fixed_penalizes_literals_and_redundancy():
    program = Program(
        ["ok.", "p(1).", "q(2)."],
        [Example(("ok", ""), True)],
        [],
        [],
        [],
    )
    rule_space = RuleSpace.from_clauses(
        [
            "target :- ok,p(1),q(2).",
            "target :- ok,p(V0),q(V1),V0!=V1,V1!=V0.",
        ]
    )
    evaluate = coverage_fixed(program, 0, [], -2000, 0.01, 0.002, 0.01, rule_space)

    small_score, small_best, _ = evaluate([0])
    redundant_score, redundant_best, _ = evaluate([1])

    assert small_best is True
    assert redundant_best is True
    assert small_score > redundant_score


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


def test_coverage_exp_mean_canonicalizes_rule_order_before_clingo(monkeypatch):
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

    assert calls == [["a.", "a.", "b."], ["a.", "b."]]


def test_cached_fitness_maps_canonical_selected_rules_to_original_indexes():
    cache = {}
    calls = []

    def compute(candidate_program):
        calls.append(candidate_program)
        return 1.0, True, [0, 1]

    score, best_found, indexes = cached_fitness(cache, [1, 0, 0], compute)

    assert (score, best_found) == (1.0, True)
    assert calls == [[0, 0, 1]]
    assert indexes == [1, 2]


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
