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
from .rule_generation.placed_clause import PlacedClause
from .rule_generation.program import Program
from .rule_generation.sampled_clause import Clause
from .rule_generation.variable_placement import VariablePlacer
from .console import print_error_and_exit
from .timing import export as export_timings, phase


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
        with phase("total_execution"):
            for it in range(arguments.iterations):
                # Step 0: sample a list of clauses
                print(f"Sampling loop: {it}")
                start_time = time.time()
                print("Sampling clauses")
                with phase("sampling"):
                    cls = sample_rule_stubs(
                        sampler, arguments, best_stub_for_next_round
                    )
                sample_time = time.time() - start_time

                # clean up the best stub
                best_stub_for_next_round = []
                sampled_clauses = instantiate_sampled_clauses(cls)
                print(
                    f"Sampled {len(sampled_clauses)} different clauses in {sample_time} seconds"
                )

                if arguments.verbosity >= 1:
                    print("Sampled clauses:")
                    sampled_clauses.sort(key=lambda x: len(x))
                    for index, current_cl in enumerate(sampled_clauses):
                        print(f"{index}) {current_cl}")

                start_time = time.time()
                with phase("variable_placement"):
                    placed_list, placed_list_improved = (
                        place_candidate_rules(placer, sampled_clauses)
                    )
                placing_time = time.time() - start_time
                print(f"Placed variables in {placing_time} seconds")

                print(f"Total clauses stub: {len(placed_list)}")
                print(
                    f"Total number of possible clauses: {sum(len(pl) for pl in placed_list)}"
                )

                if len(placed_list) == 0:
                    print_error_and_exit("No clauses found")

                if arguments.verbosity >= 2:
                    for el in placed_list:
                        print(f"{len(el)}: {el}")

                # Step 3: genetic algorithm
                start_time = time.time()
                prg, score, best_found, best_index_stub_for_the_next_round = (
                    create_default_genetic_strategy(
                        placed_list_improved,
                        program,
                        arguments,
                    ).genetic_solver()
                )

                genetic_time = time.time() - start_time

                for i in best_index_stub_for_the_next_round:
                    best_stub_for_next_round.append(cls[i])

                print(f"Evolutionary cycle {it} - Time {genetic_time}")
                if best_found:
                    print("--- Found best program ---")
                else:
                    print(f"Current best with score: {score}")
                print("--------------------------")
                print(*prg, sep="\n")
                print("--------------------------")

                if best_found:
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
