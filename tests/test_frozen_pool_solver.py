import pytest

from gentians.evaluation import EpochPoolCoverageSolver
from gentians.evaluation import pool_solver
from gentians.evaluation.coverage import Coverage
from gentians.evaluation.solver import CoverageSolver
from gentians.language.asp import parse_program
from tests.task_helpers import example, inductive_task, make_clause_space


def _solver(background, positive, negative, clauses):
    task = inductive_task(background, positive, negative, [], [])
    pool = make_clause_space(clauses)
    return EpochPoolCoverageSolver(
        task,
        ["0", "--enum-mode=brave"],
        pool,
    )


def test_frozen_pool_switches_exactly_between_programs():
    solver = _solver(
        [],
        [example(("target(p)", ""), True)],
        [example(("target(n)", ""), False)],
        ["target(p).", "target(n)."],
    )

    assert solver.extract_coverage(solver.pool.statements[1:]) == Coverage(1, 0)
    assert solver.extract_coverage(solver.pool.statements[:1]) == Coverage(0, 1)
    assert solver.extract_coverage(()) == Coverage(0, 0)


def test_frozen_pool_grounds_bk_contexts_and_clause_dependencies_together():
    solver = _solver(
        ["target(X) :- invented(X)."],
        [example(("target(a)", "", "seed(a)."), True)],
        [example(("target(b)", "", "seed(b)."), False)],
        ["invented(X) :- seed(X)."],
    )

    assert solver.extract_coverage(solver.pool.statements) == Coverage(1, 1)
    assert solver.extract_coverage(()) == Coverage(0, 0)


def test_frozen_pool_preserves_disjunctive_brave_coverage():
    solver = _solver(
        [],
        [example(("target(a)", ""), True)],
        [],
        ["target(a); other(a)."],
    )

    assert solver.extract_coverage(solver.pool.statements) == Coverage(1, 0)


def test_frozen_pool_rejects_clauses_outside_pool():
    solver = _solver([], [], [], ["target(a)."])

    with pytest.raises(ValueError, match="outside frozen pool"):
        solver.extract_coverage(make_clause_space(["target(b)."]).statements)


def test_frozen_pool_matches_fresh_solver_for_every_pool_subset():
    positive = [example(("target(a)", "", "seed(a)."), True)]
    negative = [example(("target(b)", "", "seed(b)."), False)]
    task = inductive_task(
        ["target(X) :- invented(X), not blocked(X)."],
        positive,
        negative,
        [],
        [],
    )
    pool = make_clause_space(["invented(X) :- seed(X).", "blocked(b).", "blocked(a)."])
    pooled = EpochPoolCoverageSolver(task, ["0", "--enum-mode=brave"], pool)
    fresh = CoverageSolver(
        task.background,
        ["0", "--enum-mode=brave"],
        task.positive_examples,
        task.negative_examples,
    )

    for mask in range(1 << len(pool)):
        program = tuple(
            statement
            for index, statement in enumerate(pool.statements)
            if mask & (1 << index)
        )
        assert pooled.extract_coverage(program) == fresh.extract_coverage(program)


def test_frozen_pool_records_one_grounding_and_each_solve(monkeypatch):
    rows = []
    monkeypatch.setattr(pool_solver, "metric_enabled", lambda _kind: True)
    monkeypatch.setattr(
        pool_solver,
        "record_metric",
        lambda _kind, row: rows.append(row),
    )

    solver = _solver([], [example(("target(a)", ""), True)], [], ["target(a)."])
    solver.extract_coverage(solver.pool.statements)
    solver.extract_coverage(())

    assert [row["operation_category"] for row in rows] == [
        "grounding",
        "solving",
        "solving",
    ]
    assert rows[0]["program_size"] == 1


@pytest.mark.parametrize(
    ("background", "clauses"),
    [
        ([], ["p; q.", "target :- p, not q.", ":- p.", ":- q."]),
        (
            ["dom(1..2)."],
            [
                "1 { p(X) : dom(X) } 1.",
                "target :- 1 = #count { X : p(X) }.",
                ":- p(1).",
                ":- p(2).",
            ],
        ),
        (
            [],
            ["p :- not q.", "q :- not p.", "-p.", "target :- -p, q."],
        ),
        (
            ["edge(a,b).", "edge(b,c)."],
            [
                "reach(a).",
                "reach(Y) :- reach(X), edge(X,Y).",
                "target :- reach(c), not blocked.",
                "blocked :- target.",
            ],
        ),
        (
            ["dom(1..2)."],
            [
                "{ p(X) } :- dom(X).",
                "target :- p(X) : dom(X).",
                ":- not p(1).",
                ":- p(2).",
            ],
        ),
    ],
)
def test_frozen_pool_all_subsets_preserve_general_asp(background, clauses):
    task = inductive_task(
        background,
        [example(("target", "q"), True), example(("", "target"), True)],
        [example(("target", ""), False)],
        [],
        [],
    )
    pool = make_clause_space(clauses)
    pooled = EpochPoolCoverageSolver(task, ["0", "--enum-mode=brave"], pool)
    fresh = CoverageSolver(
        task.background,
        ["0", "--enum-mode=brave"],
        task.positive_examples,
        task.negative_examples,
    )
    masks = range(1 << len(pool))
    # Revisit earlier candidates after inconsistent subsets and changed activators.
    for mask in [*masks, *reversed(masks)]:
        program = tuple(
            statement
            for index, statement in enumerate(pool.statements)
            if mask & (1 << index)
        )
        assert pooled.extract_coverage(program) == fresh.extract_coverage(program)


def test_frozen_pool_context_constraints_and_reactivation():
    positive = [
        example(("target(a)", "target(b)", "seed(a). :- target(b)."), True),
        example(("target(b)", "target(a)", "seed(b). :- target(a)."), True),
        example(("", "target(a)"), True),
    ]
    solver = _solver(
        [], positive, [], ["target(X) :- seed(X).", ":- seed(X)."]
    )
    assert solver.extract_coverage(solver.pool.statements[1:]) == Coverage(7, 0)
    assert solver.extract_coverage(solver.pool.statements) == Coverage(4, 0)
    assert solver.extract_coverage(solver.pool.statements[1:]) == Coverage(7, 0)


def test_frozen_pool_handles_inconsistent_background():
    solver = _solver([":-."], [], [example(("target", ""), False)], ["target."])
    assert solver.extract_coverage(()) == Coverage(0, 0)
    assert solver.extract_coverage(solver.pool.statements) == Coverage(0, 0)
    assert solver.extract_coverage(()) == Coverage(0, 0)


def test_frozen_pool_only_assigns_changed_externals(monkeypatch):
    solver = _solver([], [], [], ["p.", "q.", "r."])
    calls = []
    assign = solver.control.assign_external

    def record(literal, value):
        calls.append((literal, value))
        assign(literal, value)

    monkeypatch.setattr(solver.control, "assign_external", record)
    solver.extract_coverage(solver.pool.statements[:2])
    assert len(calls) == 2
    solver.extract_coverage(solver.pool.statements[:2])
    assert len(calls) == 2
    solver.extract_coverage(solver.pool.statements[1:])
    assert len(calls) == 4
    solver.extract_coverage(())
    assert len(calls) == 6


def test_frozen_pool_accepts_equal_ast_from_different_source_location():
    solver = _solver([], [example(("target", ""), True)], [], ["target."])
    reparsed = parse_program("\n\n  target.")
    assert reparsed[0] == solver.pool.statements[0]
    assert hash(reparsed[0]) == hash(solver.pool.statements[0])
    assert solver.extract_coverage(reparsed) == Coverage(1, 0)


def test_frozen_pool_can_reuse_compiled_coverage_between_epochs(monkeypatch):
    task = inductive_task([], [example(("target", ""), True)], [], [], [])
    coverage_program = pool_solver.compile_coverage_program(
        task.positive_examples, task.negative_examples
    )

    def unexpected_compile(*args):
        pytest.fail("coverage was compiled again")

    monkeypatch.setattr(pool_solver, "compile_coverage_program", unexpected_compile)
    for clauses in (["target."], ["target :- p.", "p."]):
        pool = make_clause_space(clauses)
        solver = EpochPoolCoverageSolver(
            task, ["0", "--enum-mode=brave"], pool, coverage_program=coverage_program
        )
        assert solver.extract_coverage(pool.statements) == Coverage(1, 0)
