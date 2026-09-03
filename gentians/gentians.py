import time

from gentians.evolution.algorithms.search import search_solver

from .arguments import Arguments
from .language.ir.inductive_task import InductiveTask
from .language import parse_file
from .clauses import ClauseSpace
from .timing import (
    export as export_timings,
)
from .timing import (
    phase,
    recorded_seconds,
)


def solve(
    task: InductiveTask,
    arguments: Arguments,
    clause_space: ClauseSpace | None = None,
    start_total_time: float | None = None,
) -> None:
    """
    Main loop.
    """

    start_total_time = time.time() if start_total_time is None else start_total_time

    prg: tuple[str, ...] | list[str]
    score: float
    best_found: bool

    try:
        with phase("total_execution"):
            prg, score, best_found = search_solver(arguments, task, clause_space)
        total_seconds = recorded_seconds("total_execution")
        if total_seconds is None:
            total_seconds = time.time() - start_total_time
        if best_found:
            print(f"--- Found best program with score {score} ---")
        else:
            print(f"--- Best candidate program with score {score} ---")
        print(*prg, sep="\n")
        print("--------------------------")
        print(f"Total time: {total_seconds}")
    finally:
        export_timings()


def task_from_arguments(arguments: Arguments) -> InductiveTask:
    """
    SDK entry point.
    """

    if arguments.filename:
        task = parse_file(arguments.filename)
    else:
        raise ValueError("Specify a file with the task")

    return task


def main(arguments: Arguments) -> None:
    """
    SDK entry point.
    """

    task = task_from_arguments(arguments)
    solve(task, arguments)
