import time

from .arguments import Arguments
from .evolution.default import create_default_genetic_strategy
from .rule_generation.candidates import (
    build_candidate_rule_space,
    read_task,
)
from .rule_generation.program import Program
from .console import print_error_and_exit
from .timing import export as export_timings, profile_phase, set_outer_iteration


@profile_phase("total_execution")
def solve(program: Program, arguments: Arguments) -> None:
    """
    Main loop.
    """

    start_total_time = time.time()

    try:
        candidate_space = build_candidate_rule_space(
            program,
            arguments,
        )
        placed_list = candidate_space.placed_clause_groups
        placed_list_improved = candidate_space.placed_clauses

        if len(placed_list) == 0:
            print_error_and_exit("No clauses found")

        set_outer_iteration(0, arguments.iterations_genetic)
        prg, score, best_found = create_default_genetic_strategy(
            placed_list_improved,
            program,
            arguments,
        ).genetic_solver()

        if best_found:
            print(f"--- Found best program with score {score} ---")
        else:
            print(f"--- Best candidate program with score {score} ---")
        print("--------------------------")
        print(*prg, sep="\n")
        print("--------------------------")

        print(f"Total time: {time.time() - start_total_time}")
    finally:
        export_timings()


def main(arguments: Arguments) -> None:
    """
    SDK entry point.
    """

    if arguments.filename:
        program = read_task(arguments.filename)
    else:
        print_error_and_exit("Specify a file with the task")

    if arguments.automatic_language_bias != 0:
        program.auto_generate_language_bias(arguments.automatic_language_bias)

    if arguments.predicate_invention != 0:
        program.invent_predicates(arguments.predicate_invention)

    solve(program, arguments)
