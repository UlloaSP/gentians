import math

import pytest

from gentians.asp.coverage import generate_clauses_for_coverage_interpretations
from gentians.asp.coverage_program import build_fixed_coverage_program
from gentians.evolution.fitness import create_fitness
from gentians.evolution.fitness.cov_program import CovProgram
from gentians.evolution.fitness.cov_subprograms_max import CovSubprogramsMax
from gentians.evolution.fitness.cov_subprograms_mean import CovSubprogramsMean
from gentians.rule_generation.example import Example
from gentians.rule_generation.program import Program
from gentians.rule_generation.rule_space import RuleSpace


RULES = RuleSpace.from_clauses(["target(p).", "target(n)."])


def _program() -> Program:
    return Program(
        [],
        [Example(("target(p)", ""), True)],
        [Example(("target(n)", ""), False)],
        [],
        [],
    )


def _fitness(name: str, rules: RuleSpace = RULES):
    return create_fitness(
        _program(),
        {"name": name, "max_as": 0, "clingo_arguments": []},
        3,
        rules,
    )


@pytest.mark.parametrize(
    ("name", "strategy"),
    [
        ("cov_subprograms_mean", CovSubprogramsMean),
        ("cov_subprograms_max", CovSubprogramsMax),
        ("cov_program", CovProgram),
    ],
)
def test_factory_dispatches_complete_coverages(name, strategy):
    assert isinstance(_fitness(name), strategy)


def test_factory_rejects_unknown_strategy():
    with pytest.raises(ValueError, match="Unknown fitness strategy"):
        _fitness("coverage")


def test_subprogram_mean_and_max_use_exponential_score():
    candidate = ("target(n).", "target(p).")
    mean = _fitness("cov_subprograms_mean")(candidate)
    maximum = _fitness("cov_subprograms_max")(candidate)

    assert mean.score == pytest.approx((2.0 + math.exp(10) + math.exp(-10)) / 4)
    assert maximum.score == pytest.approx(math.exp(10))
    assert mean.is_best is True and maximum.is_best is True
    assert mean.best_program == ("target(p).",)
    assert maximum.best_program == ("target(p).",)


def test_whole_program_scores_only_individual():
    candidate = ("target(n).", "target(p).")
    result = _fitness("cov_program")(candidate)

    assert result.score == 1.0
    assert result.is_best is False
    assert result.best_program == candidate
    assert result.behavior == (1, 1)


@pytest.mark.parametrize(
    "name", ["cov_subprograms_mean", "cov_subprograms_max"]
)
def test_subprogram_fitness_exposes_best_coverage_behavior(name):
    result = _fitness(name)(("target(n).", "target(p)."))

    assert result.behavior == (1, 0)


@pytest.mark.parametrize(
    "name", ["cov_subprograms_mean", "cov_subprograms_max", "cov_program"]
)
@pytest.mark.parametrize("option", ["scope", "aggregation", "grounding"])
def test_obsolete_fitness_options_are_rejected(name, option):
    with pytest.raises(ValueError, match="Obsolete fitness options"):
        create_fitness(
            _program(),
            {"name": name, option: "obsolete"},
            2,
            RULES,
        )


def test_normal_solver_grounds_each_evaluation(monkeypatch):
    evaluate = _fitness("cov_program")
    solver = evaluate.solver
    calls = 0
    ground = solver._ground

    def counted(program):
        nonlocal calls
        calls += 1
        return ground(program)

    monkeypatch.setattr(solver, "_ground", counted)

    assert evaluate(("target(p).",)).score == pytest.approx(math.exp(10))
    assert evaluate(("target(n).",)).score == pytest.approx(math.exp(-10))
    assert calls == 2


def test_whole_program_forces_brave_consequences():
    solver = _fitness("cov_program").solver
    assert "--enum-mode=brave" in solver.clingo_arguments


def test_finite_model_limit_is_rejected():
    with pytest.raises(ValueError, match="max_as=0"):
        create_fitness(
            _program(),
            {"name": "cov_program", "max_as": 2},
            1,
            RULES,
        )


def test_internal_selection_does_not_collide_with_user_program():
    program = Program(
        ["selected(0).", "r(0)."],
        [Example(("target(p)", ""), True)],
        [Example(("target(n)", ""), False)],
        [],
        [],
    )
    evaluate = create_fitness(
        program,
        {"name": "cov_program", "max_as": 0, "clingo_arguments": []},
        2,
        RULES,
    )
    assert evaluate(("target(n).",)).score == pytest.approx(math.exp(-10))


def test_undefined_atoms_are_false_without_log_noise(capsys):
    _fitness("cov_subprograms_mean")(("target(n).",))
    assert capsys.readouterr().err == ""


def test_excluded_atoms_are_checked_individually():
    clauses = generate_clauses_for_coverage_interpretations(
        [Example(("ok", "bad(1), bad(f(2,3))"), True)],
        True,
    )
    assert "cpe(0):- bad(1)." in clauses
    assert "cpe(0):- bad(f(2,3))." in clauses
    assert "cpe(0):- bad(1), bad(f(2,3))." not in clauses


def test_fixed_program_builder_combines_static_program_and_rules():
    dump = build_fixed_coverage_program(
        ["base."],
        ("target :- base.",),
        [Example(("target", ""), True)],
        [],
    )
    assert "base." in dump
    assert "pos_exs(0..0)." in dump
    assert "target :- base." in dump
