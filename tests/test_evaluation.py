import json
import math
from dataclasses import FrozenInstanceError

import pytest

from gentians.evaluation import create_evaluator
from gentians.evaluation.compiler import compile_coverage_program
from gentians.evaluation.coverage import Coverage
from gentians.evaluation.evaluator import CandidateEvaluator
from gentians.evaluation.scoring import coverage_score
from gentians.language.ir.inductive_task import InductiveTask
from gentians.language.asp import parse_program, render_program
from tests.task_helpers import example, inductive_task, make_clause_space


def _program() -> InductiveTask:
    return inductive_task(
        [],
        [example(("target(p)", ""), True)],
        [example(("target(n)", ""), False)],
        [],
        [],
    )


def _evaluator(name: str):
    return create_evaluator(
        _program(),
        {"scoring": name, "clingo_arguments": []},
    )


def _coverage(positive, negative) -> Coverage:
    return Coverage(
        sum(1 << value for value in positive),
        sum(1 << value for value in negative),
    )


def _asp(*rules: str):
    return parse_program("\n".join(rules))


def test_coverage_is_an_immutable_value():
    coverage = Coverage(1, 0)

    with pytest.raises(FrozenInstanceError):
        coverage.pos_mask = 0


def test_factory_builds_shared_evaluator():
    assert isinstance(_evaluator("cov_program"), CandidateEvaluator)


def test_factory_rejects_unknown_strategy():
    with pytest.raises(ValueError, match="Unknown scoring strategy"):
        _evaluator("coverage")


def test_whole_program_scores_only_individual():
    candidate = ("target(n).", "target(p).")
    result = _evaluator("cov_program")(_asp(*candidate))

    assert result.score == 1.0
    assert result.is_solution is False
    assert result.behavior == (1, 1)
    assert result.is_complete is True
    assert result.is_consistent is False


@pytest.mark.parametrize(
    ("candidate", "is_complete", "is_consistent"),
    [
        (("target(p).",), True, True),
        ((), False, True),
        (("target(n).", "target(p)."), True, False),
        (("target(n).",), False, False),
    ],
)
def test_evaluation_reports_completeness_and_consistency(
    candidate, is_complete, is_consistent
):
    result = _evaluator("cov_program")(_asp(*candidate))

    assert result.is_complete is is_complete
    assert result.is_consistent is is_consistent
    assert result.is_solution is (is_complete and is_consistent)


def test_quality_metric_records_which_examples_the_candidate_covers(tmp_path, monkeypatch):
    path = tmp_path / "quality.jsonl"
    monkeypatch.setenv("GENTIANS_QUALITY_METRICS_PATH", str(path))
    task = inductive_task(
        [],
        [example(("target(p1)", ""), True), example(("target(p2)", ""), True)],
        [example(("target(n1)", ""), False), example(("target(n2)", ""), False)],
        [],
        [],
    )
    evaluator = create_evaluator(task, {"scoring": "cov_program", "clingo_arguments": []})

    evaluator(_asp("target(p2).", "target(n1)."))

    row = json.loads(path.read_text(encoding="utf-8").splitlines()[-1])
    # Bit i is example i of each kind: p2 is bit 1, n1 is bit 0.
    assert (row["positive_mask"], row["negative_mask"]) == ("2", "1")
    assert (row["covered_positive"], row["covered_negative"]) == (1, 1)


def test_whole_program_normalizes_positive_and_negative_examples_separately():
    program = inductive_task(
        [],
        [
            example(("target(p1)", ""), True),
            example(("target(p2)", ""), True),
        ],
        [
            example(("target(n1)", ""), False),
            example(("target(n2)", ""), False),
            example(("target(n3)", ""), False),
            example(("target(n4)", ""), False),
        ],
        [],
        [],
    )
    rules = make_clause_space(["target(p1).", "target(n1)."])
    evaluate = create_evaluator(
        program,
        {"scoring": "cov_program", "clingo_arguments": []},
    )

    result = evaluate(rules.statements)

    assert result.score == pytest.approx(math.exp(2.5))


def test_coverage_scores_preserve_mathematically_equal_scores_exactly():
    program = inductive_task(
        [],
        [example((f"positive({index})", ""), True) for index in range(10)],
        [example((f"negative({index})", ""), False) for index in range(35)],
        [],
        [],
    )

    first = coverage_score(program, _coverage(range(3), range(9)))
    second = coverage_score(program, _coverage(range(9), range(30)))

    assert first == second


def test_positive_weight_changes_ranking_without_changing_coverage_or_success():
    task = inductive_task(
        [], [example((f"p({i})", ""), True) for i in range(10)],
        [example((f"n({i})", ""), False) for i in range(10)], [], [],
    )
    candidates = (
        _asp(*(f"p({i})." for i in range(7))),
        _asp(*(f"p({i})." for i in range(10)), *(f"n({i})." for i in range(8))),
    )
    balanced = create_evaluator(task, {"scoring": "cov_program"})
    positive = create_evaluator(task, {"scoring": "cov_program", "positive_weight": 10})
    first, second = (balanced(candidate) for candidate in candidates)
    weighted_first, weighted_second = (positive(candidate) for candidate in candidates)
    assert first.score > second.score
    assert weighted_first.score < weighted_second.score
    assert first.behavior == weighted_first.behavior
    assert second.behavior == weighted_second.behavior
    assert not any(result.is_solution for result in (first, second, weighted_first, weighted_second))
    perfect = positive(_asp(*(f"p({i})." for i in range(10))))
    assert perfect.is_solution and perfect.score == math.exp(10)


@pytest.mark.parametrize("key", ["positive_weight", "negative_weight"])
@pytest.mark.parametrize("value", [0, -1, True, "10", float("nan"), float("inf")])
def test_evaluation_rejects_invalid_coverage_weights(key, value):
    with pytest.raises(ValueError, match=key):
        create_evaluator(_program(), {"scoring": "cov_program", key: value})


@pytest.mark.parametrize("counts", [(3, 0), (0, 3), (0, 0)])
def test_weights_preserve_scores_when_one_example_class_is_absent(counts):
    positive, negative = counts
    task = inductive_task(
        [], [example((f"p({i})", ""), True) for i in range(positive)],
        [example((f"n({i})", ""), False) for i in range(negative)], [], [],
    )
    coverage = Coverage(int(bool(positive)), int(bool(negative)))
    assert coverage_score(task, coverage, positive_weight=10) == coverage_score(task, coverage)


def test_coverage_weight_ratios_are_scale_invariant_and_numerically_bounded():
    task = _program()
    candidate = _asp("target(p).", "target(n).")
    scores = [create_evaluator(task, {
        "scoring": "cov_program", "positive_weight": positive, "negative_weight": negative,
    })(candidate).score for positive, negative in ((10, 1), (20, 2), (1e308, 1e307))]
    assert scores[0] == scores[1] == scores[2]


def test_normal_solver_grounds_each_evaluation(monkeypatch):
    evaluate = _evaluator("cov_program")
    solver = evaluate.solver
    calls = 0
    ground = solver._ground

    def counted(program):
        nonlocal calls
        calls += 1
        return ground(program)

    monkeypatch.setattr(solver, "_ground", counted)

    assert evaluate(_asp("target(p).")).score == pytest.approx(math.exp(10))
    assert evaluate(_asp("target(n).")).score == pytest.approx(math.exp(-10))
    assert calls == 2


def test_whole_program_forces_brave_consequences():
    solver = _evaluator("cov_program").solver
    assert "--enum-mode=brave" in solver.clingo_arguments


def test_evaluator_discards_split_enum_mode_override():
    evaluate = create_evaluator(
        _program(),
        {
            "scoring": "cov_program",
            "clingo_arguments": ["--enum-mode", "cautious"],
        },
    )

    assert evaluate.solver.clingo_arguments == ["0", "--enum-mode=brave"]


def test_undefined_atoms_are_false_without_log_noise(capsys):
    _evaluator("cov_program")(_asp("target(n)."))
    assert capsys.readouterr().err == ""


def test_excluded_atoms_are_checked_individually():
    clauses = render_program(
        compile_coverage_program(
            [example(("ok", "bad(1), bad(f(2,3))"), True)],
            [],
        )
    )
    assert "cpe(0) :- bad(1)." in clauses
    assert "cpe(0) :- bad(f(2,3))." in clauses
    assert "cpe(0) :- bad(1); bad(f(2,3))." not in clauses


def test_static_program_builder_includes_examples():
    dump = compile_coverage_program(
        [example(("target", ""), True)],
        [],
    )
    assert "pos_exs((0..0))." in render_program(dump)


def test_contexts_do_not_leak_between_examples():
    program = inductive_task(
        [],
        [
            example(("target(a)", "", "seed(a). ctx(X) :- seed(X)."), True),
            example(("target(b)", "", "seed(b). ctx(X) :- seed(X)."), True),
        ],
        [],
        [],
        [],
    )
    rules = make_clause_space(["target(a) :- ctx(b)."])
    evaluate = create_evaluator(
        program,
        {"scoring": "cov_program", "clingo_arguments": []},
    )

    result = evaluate(rules.statements)

    assert result.score == pytest.approx(1.0)
    assert result.is_solution is False
    assert result.behavior == (0, 0)


def test_context_constraint_does_not_disable_other_examples():
    program = inductive_task(
        [],
        [
            example(("target(a)", "", "ctx(a)"), True),
            example(("target(b)", "", "ctx(b). :- ctx(b)."), True),
        ],
        [],
        [],
        [],
    )
    rules = make_clause_space(["target(a) :- ctx(a)."])
    evaluate = create_evaluator(
        program,
        {"scoring": "cov_program", "clingo_arguments": []},
    )

    result = evaluate(rules.statements)

    assert result.score == pytest.approx(math.exp(5))
    assert result.behavior == (1, 0)


def test_positive_context_does_not_leak_into_negative_example():
    program = inductive_task(
        [],
        [example(("target(a)", "", "ctx(a)"), True)],
        [example(("target(a)", "", "ctx(b)"), False)],
        [],
        [],
    )
    rules = make_clause_space(["target(a) :- ctx(a)."])
    evaluate = create_evaluator(
        program,
        {"scoring": "cov_program", "clingo_arguments": []},
    )

    result = evaluate(rules.statements)

    assert result.score == pytest.approx(math.exp(10))
    assert result.is_solution is True
    assert result.is_complete is True
    assert result.is_consistent is True
    assert result.behavior == (1, 0)


@pytest.mark.parametrize("context", ["", "ctx(a)"])
def test_example_with_empty_inclusion_is_covered(context):
    program = inductive_task(
        [],
        [example(("", "", context), True)],
        [],
        [],
        [],
    )
    evaluate = create_evaluator(
        program,
        {"scoring": "cov_program", "clingo_arguments": []},
    )

    result = evaluate(())

    assert result.score == pytest.approx(math.exp(10))
    assert result.is_solution is True
    assert result.behavior == (1, 0)


def test_context_free_empty_inclusion_stays_covered_in_mixed_task():
    program = inductive_task(
        [],
        [
            example(("", "", ""), True),
            example(("target", "", "ctx(a)"), True),
        ],
        [],
        [],
        [],
    )
    evaluate = create_evaluator(
        program,
        {"scoring": "cov_program", "clingo_arguments": []},
    )

    result = evaluate(())

    assert result.score == pytest.approx(math.exp(5))
    assert result.behavior == (1, 0)


@pytest.mark.parametrize("context", [":~ cost(X). [1@1,X]", "#const n=1."])
def test_context_rejects_non_isolatable_statements(context):
    with pytest.raises(ValueError, match="unsupported statement"):
        compile_coverage_program(
            [example(("target", "", context), True)],
            [],
        )
