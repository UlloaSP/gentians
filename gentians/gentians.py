import time

from .arguments import Arguments
from .evolution.default import create_default_genetic_strategy
from .rule_generation.candidates import (
    create_program_sampler,
    instantiate_sampled_clauses,
    place_candidate_rules,
    read_task,
    sample_rule_stubs,
)
from .rule_generation.program import Program
from .rule_generation.sampled_clause import Clause
from .rule_generation.variable_placement import VariablePlacer
from .console import print_error_and_exit
from .timing import export as export_timings, profile_phase, set_outer_iteration


@profile_phase("total_execution")
def solve(program: Program, arguments: Arguments) -> None:
    """
    Main loop.
    """

    best_found: bool = False
    best_stub_for_next_round: "list[Clause]" = []

    sampler = create_program_sampler(program, arguments)
    placer = VariablePlacer(arguments)

    start_total_time = time.time()

    try:
        for it in range(arguments.iterations):
            set_outer_iteration(it, arguments.iterations_genetic)
            # Step 0: sample a list of clauses
            cls = sample_rule_stubs(sampler, arguments, best_stub_for_next_round)

            # clean up the best stub
            best_stub_for_next_round = []
            sampled_clauses = instantiate_sampled_clauses(cls)

            placed_list, placed_list_improved = place_candidate_rules(
                placer, sampled_clauses
            )

            if len(placed_list) == 0:
                print_error_and_exit("No clauses found")

            # Step 3: genetic algorithm
            prg, score, best_found, best_index_stub_for_the_next_round = (
                create_default_genetic_strategy(
                    placed_list_improved,
                    program,
                    arguments,
                ).genetic_solver()
            )

            for i in best_index_stub_for_the_next_round:
                best_stub_for_next_round.append(cls[i])

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
