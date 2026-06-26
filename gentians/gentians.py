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

    best_found: bool = False
    start_total_time = time.time()

    try:
        for it in range(arguments.iterations):
            set_outer_iteration(it, arguments.iterations_genetic)
            candidate_space = build_candidate_rule_space(
                program,
                arguments,
            )
            placed_list = candidate_space.placed_clause_groups
            placed_list_improved = candidate_space.placed_clauses

            if len(placed_list) == 0:
                print_error_and_exit("No clauses found")

            # Step 3: genetic algorithm
            prg, score, best_found = (
                create_default_genetic_strategy(
                    placed_list_improved,
                    program,
                    arguments,
                ).genetic_solver()
            )

            if best_found:
                print(f"--- Found best program with score {score} ---")
                print("--------------------------")
                print(*prg, sep="\n")
                print("--------------------------")
                break

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
