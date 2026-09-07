from itertools import combinations

import pytest

from gentians.evaluation import create_evaluator
from gentians.language.asp import parse_program
from tests.task_helpers import example, inductive_task, make_clause_space


@pytest.mark.parametrize("sides", ["both", "positive", "negative", "empty"])
def test_inheritance_matches_fresh_solver_for_all_constraint_subsets(sides):
    examples = [
        ("p", "q", "a."),
        ("q", "p", "b."),
        ("-r", "", ""),
        ("", "p,q", ":- a."),
    ]
    task = inductive_task(
        ["p :- a, not q.", "q :- b, not p.", "{p;q}.", "-r :- not p."],
        [example(e, True) for e in examples] if sides in ("both", "positive") else [],
        [example(e, False) for e in reversed(examples)] if sides in ("both", "negative") else [],
        [], [],
    )
    plain = create_evaluator(task, {"scoring": "cov_program"})
    inherited = create_evaluator(task, {"scoring": "cov_program", "constraint_inheritance": True})
    clauses = parse_program(":- p. :- q. :- not p, not q. :- -r.")
    programs = [tuple(group) for n in range(5) for group in combinations(clauses, n)]
    # Both subset directions, arbitrary replacements, and headed-block changes.
    for headed in ((), parse_program("r | s."), parse_program("p.")):
        for constraints in [*programs, *reversed(programs)]:
            candidate = headed + constraints
            assert inherited(candidate) == plain(candidate)
    assert len(inherited.solver._evidence) <= 64
    assert len(inherited.solver._partial) <= 32


def test_inheritance_skips_control_when_all_coverage_proven(monkeypatch):
    task = inductive_task(["{p}."], [example(("p", ""), True)], [], [], [])
    evaluate = create_evaluator(task, {"scoring": "cov_program", "constraint_inheritance": True})
    assert evaluate(parse_program(":- p.")).behavior == (0, 0)

    def unexpected(_):
        pytest.fail("No Control needed for this descendant")

    monkeypatch.setattr(evaluate.solver, "_extract", unexpected)
    assert evaluate(parse_program(":- p. :- not p.")).behavior == (0, 0)
    assert evaluate.solver.skipped_controls == 1


def test_inheritance_rejects_non_boolean_configuration():
    with pytest.raises(ValueError, match="boolean"):
        create_evaluator(inductive_task([], [], [], [], []), {
            "scoring": "cov_program", "constraint_inheritance": 1,
        })


@pytest.mark.parametrize("clauses, enabled", [(["p."], False), ([":- p."], True)])
def test_space_without_constraints_avoids_inheritance_bookkeeping(clauses, enabled):
    evaluator = create_evaluator(
        inductive_task([], [], [], [], []),
        {"scoring": "cov_program", "constraint_inheritance": True},
        space=make_clause_space(clauses),
    )
    assert evaluator.solver.constraint_inheritance is enabled


@pytest.mark.parametrize("arguments, message", [
    ([], "brave"),
    (["0", "--enum-mode=cautious"], "brave"),
    (["0", "--enum-mode=brave", "--solve-limit=0"], "exhaustive"),
])
def test_incomplete_solve_never_becomes_absence_evidence(arguments, message):
    from gentians.evaluation.solver import CoverageSolver

    solver = CoverageSolver(
        parse_program("{p}."), arguments, [example(("p", ""), True)], [],
        constraint_inheritance=True,
    )
    with pytest.raises(RuntimeError, match=message):
        solver.extract_coverage(())
    assert not solver._evidence
