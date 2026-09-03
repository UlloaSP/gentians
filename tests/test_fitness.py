import math

import pytest

from gentians.asp.coverage import (
    Coverage,
    generate_clauses_for_coverage_interpretations,
)
from gentians.asp.coverage_program import build_coverage_static_program
from gentians.evolution.fitness import create_fitness
from gentians.evolution.fitness.cov_balanced import CovBalanced
from gentians.evolution.fitness.cov_program import CovProgram
from gentians.evolution.fitness.coverage_common import (
    balanced_coverage_score,
    coverage_score,
)
from gentians.language.ir.example import Example
from gentians.language.ir.inductive_task import InductiveTask
from gentians.clauses.rule_space import RuleSpace


def _program() -> InductiveTask:
    return InductiveTask(
        [],
        [Example(("target(p)", ""), True)],
        [Example(("target(n)", ""), False)],
        [],
        [],
    )


def _fitness(name: str):
    return create_fitness(
        _program(),
        {"name": name, "clingo_arguments": []},
    )


def _coverage(positive, negative) -> Coverage:
    coverage = Coverage()
    coverage.extend_masks(
        sum(1 << value for value in positive),
        sum(1 << value for value in negative),
    )
    return coverage


@pytest.mark.parametrize(
    ("name", "strategy"),
    [("cov_program", CovProgram), ("cov_balanced", CovBalanced)],
)
def test_factory_dispatches_complete_coverages(name, strategy):
    assert isinstance(_fitness(name), strategy)


def test_factory_rejects_unknown_strategy():
    with pytest.raises(ValueError, match="Unknown fitness strategy"):
        _fitness("coverage")


def test_whole_program_scores_only_individual():
    candidate = ("target(n).", "target(p).")
    result = _fitness("cov_program")(candidate)

    assert result.score == 1.0
    assert result.is_best is False
    assert result.behavior == (1, 1)


@pytest.mark.parametrize(
    ("candidate", "score", "perfect"),
    [
        (("target(p).",), 1.0, True),
        ((), 0.5, False),
        (("target(n).", "target(p)."), 0.5, False),
        (("target(n).",), 0.0, False),
    ],
)
def test_balanced_coverage_uses_balanced_accuracy(candidate, score, perfect):
    result = _fitness("cov_balanced")(candidate)

    assert result.score == pytest.approx(score)
    assert result.is_best is perfect


def test_balanced_coverage_normalizes_positive_and_negative_examples_separately():
    program = InductiveTask(
        [],
        [
            Example(("target(p1)", ""), True),
            Example(("target(p2)", ""), True),
        ],
        [
            Example(("target(n1)", ""), False),
            Example(("target(n2)", ""), False),
            Example(("target(n3)", ""), False),
            Example(("target(n4)", ""), False),
        ],
        [],
        [],
    )
    rules = RuleSpace.from_clauses(["target(p1).", "target(n1)."])
    evaluate = create_fitness(
        program,
        {"name": "cov_balanced", "clingo_arguments": []},
    )

    result = evaluate(rules.clauses)

    assert result.score == pytest.approx(0.625)


@pytest.mark.parametrize("score", [balanced_coverage_score, coverage_score])
def test_coverage_scores_preserve_mathematically_equal_scores_exactly(score):
    program = InductiveTask(
        [],
        [Example((f"positive({index})", ""), True) for index in range(10)],
        [Example((f"negative({index})", ""), False) for index in range(35)],
        [],
        [],
    )

    first = score(program, _coverage(range(3), range(9)))
    second = score(program, _coverage(range(9), range(30)))

    assert first == second


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


@pytest.mark.parametrize("name", ["cov_program", "cov_balanced"])
def test_fitness_discards_split_enum_mode_override(name):
    evaluate = create_fitness(
        _program(),
        {
            "name": name,
            "clingo_arguments": ["--enum-mode", "cautious"],
        },
    )

    assert evaluate.solver.clingo_arguments == ["0", "--enum-mode=brave"]


def test_undefined_atoms_are_false_without_log_noise(capsys):
    _fitness("cov_program")(("target(n).",))
    assert capsys.readouterr().err == ""


def test_excluded_atoms_are_checked_individually():
    clauses = generate_clauses_for_coverage_interpretations(
        [Example(("ok", "bad(1), bad(f(2,3))"), True)],
        True,
    )
    assert "cpe(0):- bad(1)." in clauses
    assert "cpe(0):- bad(f(2,3))." in clauses
    assert "cpe(0):- bad(1), bad(f(2,3))." not in clauses


def test_static_program_builder_includes_background_and_examples():
    dump = build_coverage_static_program(
        ["base."],
        [Example(("target", ""), True)],
        [],
    )
    assert "base." in dump
    assert "pos_exs(0..0)." in dump


def test_contexts_do_not_leak_between_examples():
    program = InductiveTask(
        [],
        [
            Example(("target(a)", "", "seed(a). ctx(X) :- seed(X)."), True),
            Example(("target(b)", "", "seed(b). ctx(X) :- seed(X)."), True),
        ],
        [],
        [],
        [],
    )
    rules = RuleSpace.from_clauses(["target(a) :- ctx(b)."])
    evaluate = create_fitness(
        program,
        {"name": "cov_program", "clingo_arguments": []},
    )

    result = evaluate(rules.clauses)

    assert result.score == pytest.approx(1.0)
    assert result.is_best is False
    assert result.behavior == (0, 0)


def test_context_constraint_does_not_disable_other_examples():
    program = InductiveTask(
        [],
        [
            Example(("target(a)", "", "ctx(a)"), True),
            Example(("target(b)", "", "ctx(b). :- ctx(b)."), True),
        ],
        [],
        [],
        [],
    )
    rules = RuleSpace.from_clauses(["target(a) :- ctx(a)."])
    evaluate = create_fitness(
        program,
        {"name": "cov_program", "clingo_arguments": []},
    )

    result = evaluate(rules.clauses)

    assert result.score == pytest.approx(math.exp(5))
    assert result.behavior == (1, 0)


def test_positive_context_does_not_leak_into_negative_example():
    program = InductiveTask(
        [],
        [Example(("target(a)", "", "ctx(a)"), True)],
        [Example(("target(a)", "", "ctx(b)"), False)],
        [],
        [],
    )
    rules = RuleSpace.from_clauses(["target(a) :- ctx(a)."])
    evaluate = create_fitness(
        program,
        {"name": "cov_program", "clingo_arguments": []},
    )

    result = evaluate(rules.clauses)

    assert result.score == pytest.approx(math.exp(10))
    assert result.is_best is True
    assert result.behavior == (1, 0)


@pytest.mark.parametrize("context", ["", "ctx(a)"])
def test_example_with_empty_inclusion_is_covered(context):
    program = InductiveTask(
        [],
        [Example(("", "", context), True)],
        [],
        [],
        [],
    )
    evaluate = create_fitness(
        program,
        {"name": "cov_program", "clingo_arguments": []},
    )

    result = evaluate(())

    assert result.score == pytest.approx(math.exp(10))
    assert result.is_best is True
    assert result.behavior == (1, 0)


def test_context_free_empty_inclusion_stays_covered_in_mixed_task():
    program = InductiveTask(
        [],
        [
            Example(("", "", ""), True),
            Example(("target", "", "ctx(a)"), True),
        ],
        [],
        [],
        [],
    )
    evaluate = create_fitness(
        program,
        {"name": "cov_program", "clingo_arguments": []},
    )

    result = evaluate(())

    assert result.score == pytest.approx(math.exp(5))
    assert result.behavior == (1, 0)


@pytest.mark.parametrize("context", [":~ cost(X). [1@1,X]", "#const n=1."])
def test_context_rejects_non_isolatable_statements(context):
    with pytest.raises(ValueError, match="unsupported statement"):
        build_coverage_static_program(
            [],
            [Example(("target", "", context), True)],
            [],
        )
