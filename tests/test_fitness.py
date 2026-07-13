import math

import pytest

from gentians.asp.coverage import generate_clauses_for_coverage_interpretations
from gentians.asp.coverage_program import build_fixed_coverage_program
from gentians.asp.normal_coverage_solver import NormalCoverageSolver
from gentians.evolution.fitness.cov_program import CovProgram
from gentians.evolution.fitness.cov_subprograms_max import CovSubprogramsMax
from gentians.evolution.fitness.cov_subprograms_mean import CovSubprogramsMean
from gentians.evolution.fitness import create_fitness
from gentians.rule_generation.example import Example
from gentians.rule_generation.program import Program


def _program() -> Program:
    return Program(
        [],
        [Example(("target(p)", ""), True)],
        [Example(("target(n)", ""), False)],
        [],
        [],
    )


def _fitness(
    name: str,
    grounding: str = "normal",
    rules: tuple[str, ...] | None = None,
):
    return create_fitness(
        _program(),
        {
            "name": name,
            "grounding": grounding,
            "max_as": 0,
            "clingo_arguments": [],
        },
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
def test_factory_dispatches_the_three_complete_coverages(name, strategy):
    assert isinstance(_fitness(name), strategy)


def test_factory_rejects_removed_coverage_alias():
    with pytest.raises(ValueError, match="Unknown fitness strategy"):
        _fitness("coverage")


def test_subprogram_mean_and_max_are_distinct_aggregations():
    candidate = ("target(p).", "target(n).")
    mean_score, mean_best, mean_program = _fitness("cov_subprograms_mean")(
        candidate
    )
    max_score, max_best, max_program = _fitness("cov_subprograms_max")(candidate)

    assert math.isclose(mean_score, (1.0 + math.exp(10) + math.exp(-10) + 1.0) / 4)
    assert max_score > mean_score
    assert mean_best is True and max_best is True
    assert mean_program == ("target(p).",)
    assert max_program == ("target(p).",)


def test_whole_program_scores_only_the_individual():
    candidate = ("target(p).", "target(n).")
    score, best, selected = _fitness("cov_program")(candidate)

    assert score == 1.0
    assert best is False
    assert selected == candidate


@pytest.mark.parametrize(
    "name", ["cov_subprograms_mean", "cov_subprograms_max", "cov_program"]
)
def test_removed_scope_and_aggregation_options_are_rejected(name):
    with pytest.raises(ValueError, match="Obsolete fitness options"):
        create_fitness(
            _program(),
            {"name": name, "scope": "subprograms", "aggregation": "mean"},
            2,
            ("target(p).",),
        )


@pytest.mark.parametrize(
    "name", ["cov_subprograms_mean", "cov_subprograms_max", "cov_program"]
)
@pytest.mark.parametrize("grounding", ["externals", "assumptions"])
def test_pregrounding_matches_normal(name, grounding):
    rule_space = ("target(p).", "target(n).")
    candidate = ("target(p).", "target(p).", "target(n).")

    expected = _fitness(name)(candidate)
    actual = _fitness(name, grounding, rule_space)(candidate)

    assert actual == expected


@pytest.mark.parametrize("grounding", ["externals", "assumptions"])
def test_pregrounding_rejects_finite_model_limit(grounding):
    with pytest.raises(ValueError, match="requires max_as=0"):
        create_fitness(
            _program(),
            {
                "name": "cov_program",
                "grounding": grounding,
                "max_as": 2,
                "clingo_arguments": [],
            },
            1,
            ("target(p).",),
        )


def test_pregrounding_rejects_rule_outside_hypothesis_space():
    evaluate = _fitness("cov_program", "externals", ("target(p).",))
    with pytest.raises(ValueError, match="outside pre-grounded rule space"):
        evaluate(("unknown.",))


def test_pregrounding_does_not_create_control_per_candidate(monkeypatch):
    rules = ("target(p).", "target(n).")
    evaluate = _fitness("cov_program", "externals", rules)

    def unexpected_control(*_args, **_kwargs):
        raise AssertionError("candidate evaluation grounded a new Control")

    monkeypatch.setattr(
        "gentians.asp.pregrounded_coverage_solver.clingo.Control",
        unexpected_control,
    )
    assert evaluate(("target(p).",))[0] == math.exp(10)
    assert evaluate(("target(n).",))[0] == math.exp(-10)


def test_excluded_atoms_are_checked_individually():
    clauses = generate_clauses_for_coverage_interpretations(
        [Example(("ok", "bad(1), bad(f(2,3))"), True)],
        True,
    )
    assert "cpe(0):- bad(1)." in clauses
    assert "cpe(0):- bad(f(2,3))." in clauses
    assert "cpe(0):- bad(1), bad(f(2,3))." not in clauses


def test_normal_coverage_does_not_dump_candidates(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    coverage = NormalCoverageSolver(
        ["base."],
        ["0", "--enum-mode=brave"],
        [Example(("target", ""), True)],
        [],
    ).extract_fixed_coverage(("target :- base.",))

    assert coverage.pos_mask == 1
    assert not (tmp_path / ".debug" / "clingo").exists()


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
