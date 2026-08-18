import time

from gentians.evolution.algorithms.search import search_solver

from .arguments import Arguments
from .rule_generation.program import Program
from .rule_generation.reader import read_program
from .rule_generation.rule_space import RuleSpace
from .timing import (
    export as export_timings,
)
from .timing import (
    phase,
    recorded_seconds,
)


def solve(
    program: Program,
    arguments: Arguments,
    rule_space: RuleSpace | None = None,
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
            prg, score, best_found = search_solver(arguments, program, rule_space)
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


def program_from_arguments(arguments: Arguments) -> Program:
    """
    SDK entry point.
    """

    if arguments.filename:
        program = read_program(arguments.filename)
    else:
        raise ValueError("Specify a file with the task")

    return program


def main(arguments: Arguments) -> None:
    """
    SDK entry point.
    """

    program = program_from_arguments(arguments)
    solve(program, arguments)
