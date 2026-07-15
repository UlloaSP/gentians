import math
import time

import pytest

from gentians.asp.coverage import Coverage, generate_clauses_for_coverage_interpretations
from gentians.asp.coverage_program import build_fixed_coverage_program
from gentians.asp.external_activation import ExternalActivation
from gentians.asp.normal_coverage_solver import NormalCoverageSolver
from gentians.asp.pregrounded_coverage_solver import PregroundedCoverageSolver
from gentians.evolution.fitness.cov_program import CovProgram
from gentians.evolution.fitness.cov_subprograms_max import CovSubprogramsMax
from gentians.evolution.fitness.cov_subprograms_mean import CovSubprogramsMean
from gentians.evolution.fitness import create_fitness
from gentians.rule_generation.example import Example
from gentians.rule_generation.program import Program
from gentians import timing


def _program() -> Program:
    return Program(
        [],
        [Example(("target(p)", ""), True)],
        [Example(("target(n)", ""), False)],
        [],
        [],
    )


def test_normal_solver_solving_excludes_python_and_metrics(monkeypatch, tmp_path):
    class Model:
        @staticmethod
        def symbols(shown=True):
            time.sleep(0.02)
            return []

    class Handle:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def __iter__(self):
            return iter((Model(),))

    class Control:
        statistics = {
            "problem": {"lp": {"atoms": 1, "rules": 1}},
            "summary": {"models": {"enumerated": 1}},
        }

        def __init__(self, *_args, **_kwargs):
            pass

        def add(self, *_args):
            pass

        def ground(self, *_args):
            pass

        def solve(self, **_kwargs):
            return Handle()

    timing.reset()
    monkeypatch.setattr(timing, "_enabled", True)
    monkeypatch.setenv(
        "GENTIANS_CLINGO_METRICS_PATH", str(tmp_path / "clingo.jsonl")
    )
    monkeypatch.setattr("gentians.asp.normal_coverage_solver.clingo.Control", Control)
    extend_masks = Coverage.extend_masks
    calls = 0

    def measured_extend(self, pos_mask, neg_mask):
        nonlocal calls
        calls += 1
        if calls == 2:
            time.sleep(0.02)
        return extend_masks(self, pos_mask, neg_mask)

    monkeypatch.setattr(Coverage, "extend_masks", measured_extend)

    with timing.phase("population"):
        NormalCoverageSolver([], [], [], []).extract_subset_coverage(())

    assert timing._totals["population.solving"] < 0.01
    assert timing._totals["population.self"] >= 0.02
    assert timing._totals["population.self"] < 0.035
    timing.reset()


def test_normal_solver_records_fresh_solve_statistics(monkeypatch):
    rows = []
    monkeypatch.setattr(
        "gentians.asp.normal_coverage_solver.metric_enabled", lambda _name: True
    )
    monkeypatch.setattr(
        "gentians.asp.normal_coverage_solver.record_metric",
        lambda _name, row: rows.append(row),
    )

    NormalCoverageSolver(
        ["{base}."],
        ["0"],
        [Example(("target", ""), True)],
        [],
    ).extract_fixed_coverage(("target :- base.",))

    grounding = next(row for row in rows if row["operation_category"] == "grounding")
    solving = next(row for row in rows if row["operation_category"] == "solving")
    assert grounding["stats_atoms"] > 0
    assert grounding["stats_rules"] > 0
    assert solving["models"] == 2
    assert solving["stats_models_enumerated"] == 2
    assert solving["stats_choices"] > 0


def test_pregrounded_solver_refreshes_statistics_between_solves(monkeypatch):
    rows = []
    monkeypatch.setattr(
        "gentians.asp.pregrounded_coverage_solver.metric_enabled", lambda _name: True
    )
    monkeypatch.setattr(
        "gentians.asp.pregrounded_coverage_solver.record_metric",
        lambda _name, row: rows.append(row),
    )
    solver = PregroundedCoverageSolver(
        ["{base}."], ["0"], [], [], ("{extra}.",), ExternalActivation(), 1
    )

    solver.extract_fixed_coverage(("{extra}.",))
    solver.extract_fixed_coverage(())

    grounding = [row for row in rows if row["operation_category"] == "grounding"]
    solving = [row for row in rows if row["operation_category"] == "solving"]
    assert len(grounding) == 1
    assert [row["models"] for row in solving] == [4, 2]
    assert [row["stats_models_enumerated"] for row in solving] == [4, 2]


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
@pytest.mark.parametrize(
    "candidate", [("target(p).", "target(n)."), ("target(n).",)]
)
def test_pregrounding_matches_normal(name, grounding, candidate):
    rule_space = ("target(p).", "target(n).")

    expected = _fitness(name)(candidate)
    actual = _fitness(name, grounding, rule_space)(candidate)

    assert actual == expected


def test_pregrounding_guards_each_rule_once_not_once_per_slot(monkeypatch):
    captured = {}

    class Control:
        def __init__(self, *_args, **_kwargs):
            pass

        def add(self, _name, _parameters, program):
            captured["program"] = program

        def ground(self, _parts):
            pass

    monkeypatch.setattr(
        "gentians.asp.pregrounded_coverage_solver.clingo.Control", Control
    )
    monkeypatch.setattr(
        "gentians.asp.pregrounded_coverage_solver.metric_enabled", lambda _name: False
    )

    PregroundedCoverageSolver(
        [], [], [], [], ("left.", "right."), ExternalActivation(), 8
    )

    generated = captured["program"]
    assert generated.count("left :- gentians_internal_selected(0).") == 1
    assert generated.count("right :- gentians_internal_selected(1).") == 1
    assert "#external gentians_internal_active(0..1)." in generated
    assert "active(0..7," not in generated


def test_pregrounding_rejects_duplicate_candidate_rules():
    evaluate = _fitness(
        "cov_program", "externals", ("target(p).", "target(n).")
    )

    with pytest.raises(ValueError, match="must not contain duplicate rules"):
        evaluate(("target(p).", "target(p)."))


@pytest.mark.parametrize(
    "name", ["cov_subprograms_mean", "cov_subprograms_max", "cov_program"]
)
@pytest.mark.parametrize("grounding", ["externals", "assumptions"])
def test_pregrounding_internal_selection_does_not_collide_with_user_program(
    name, grounding,
):
    program = Program(
        ["selected(0).", "r(0)."],
        [Example(("target(p)", ""), True)],
        [Example(("target(n)", ""), False)],
        [],
        [],
    )
    rule_space = ("target(p).", "target(n).")
    normal = create_fitness(
        program, {"name": name, "max_as": 0}, 2, rule_space
    )
    pregrounded = create_fitness(
        program,
        {
            "name": name,
            "grounding": grounding,
            "max_as": 0,
            "clingo_arguments": [],
        },
        2,
        rule_space,
    )

    assert pregrounded(("target(n).",)) == normal(("target(n).",))


def test_coverage_undefined_atoms_are_false_without_log_noise(capsys):
    _fitness("cov_subprograms_mean")(("target(n).",))

    assert capsys.readouterr().err == ""


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
