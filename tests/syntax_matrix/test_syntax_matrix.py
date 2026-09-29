"""End-to-end regression matrix for the supported ASP syntax.

Each ``cases/<axis>/<name>.lp`` file is a complete inductive task whose
reference hypothesis depends on one construct, or on a combination of
constructs, of the task language. Header comments declare the reference:

    % expect: <canonical clause>      (one line per clause)
    % xfail: <reason>                 (known, documented gap)

Every case walks the whole chain separately so a failure names its layer:
parsing, clause generation plus dependency closure, whole-program semantics
of the reference hypothesis, and evolutionary search with a fixed seed.
Theory atoms, weak constraints and non-ASP directives such as ``#heuristic``
or ``#edge`` are outside the matrix on purpose.
"""

from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest

from gentians.algorithms import (
    incremental_clause_genetic_search,
    steady_state_genetic_search,
)
from gentians.arguments import Arguments
from gentians.clauses import generate_clause_space
from gentians.evaluation import create_evaluator
from gentians.hypotheses import HypothesisGenerator
from gentians.language import parse_text
from gentians.language.ir.inductive_task import InductiveTask

CASES_DIR = Path(__file__).parent / "cases"
SEARCH_ITERATIONS = 2000


@dataclass(frozen=True)
class Case:
    path: Path
    expected: tuple[str, ...]
    xfail: str | None

    @property
    def id(self) -> str:
        return self.path.relative_to(CASES_DIR).with_suffix("").as_posix()

    def text(self) -> str:
        return self.path.read_text(encoding="utf-8")


def _load(path: Path) -> Case:
    expected, xfail = [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("% expect:"):
            expected.append(line.removeprefix("% expect:").strip())
        elif line.startswith("% xfail:"):
            xfail = line.removeprefix("% xfail:").strip()
    if not expected:
        raise ValueError(f"{path} declares no '% expect:' clause")
    return Case(path, tuple(expected), xfail)


CASES = [_load(path) for path in sorted(CASES_DIR.rglob("*.lp"))]


def _params(cases: list[Case]):
    return [
        pytest.param(
            case,
            id=case.id,
            marks=[pytest.mark.xfail(reason=case.xfail, strict=True)] if case.xfail else [],
        )
        for case in cases
    ]


def _arguments(algorithm: str = "steady_state") -> Arguments:
    return Arguments(
        random_seed=0,
        iterations_genetic=SEARCH_ITERATIONS,
        algorithm=algorithm,
    )


@cache
def _prepared(case: Case) -> tuple[InductiveTask, HypothesisGenerator]:
    task = parse_text(case.text())
    space = generate_clause_space(task, _arguments())
    limit = len(space) if task.max_program_clauses is None else task.max_program_clauses
    return task, HypothesisGenerator(task, space, limit)


@pytest.mark.parametrize("case", _params(CASES))
def test_reference_clauses_survive_generation_and_closure(case: Case) -> None:
    _, hypotheses = _prepared(case)
    missing = [clause for clause in case.expected if clause not in hypotheses.clause_ids]
    assert not missing, f"missing {missing}; prepared space: {list(hypotheses.clauses)}"


@pytest.mark.parametrize("case", _params(CASES))
def test_reference_hypothesis_is_perfect(case: Case) -> None:
    task, hypotheses = _prepared(case)
    evaluator = create_evaluator(task, _arguments().evaluation, space=hypotheses.space)
    result = evaluator(hypotheses.program(hypotheses.encode(case.expected)))
    assert result.is_solution, result


@pytest.mark.parametrize("case", _params(CASES))
@pytest.mark.parametrize(
    "algorithm, search",
    [
        ("steady_state", steady_state_genetic_search),
        ("incremental", incremental_clause_genetic_search),
    ],
)
def test_search_learns_a_perfect_hypothesis(case: Case, algorithm, search) -> None:
    task = parse_text(case.text())
    result = search(_arguments(algorithm), task)
    assert result.is_solution, result.hypothesis
