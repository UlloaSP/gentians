import time

from .arguments import Arguments
from .program_sampler import ProgramSampler, Clause
from .strategies import Strategy, PlacedClause
from .utils import print_error_and_exit
from .parser import Parser, Program
from .variable_placer import VariablePlacer
from .timing import export as export_timings, phase


def solve(program: Program, arguments: Arguments) -> None:
    """
    Main loop.
    """

    best_found: bool = False
    best_stub_for_next_round: "list[Clause]" = []

    sampler = ProgramSampler(
        program.language_bias_head,
        program.language_bias_body,
        arguments,
    )

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
                    cls = sampler.sample_clauses_stub(arguments.clauses_to_sample)
                sample_time = time.time() - start_time

                # add the best from the previous rounds
                cls.extend(best_stub_for_next_round)
                # clean up the best stub
                best_stub_for_next_round = []
                # Step 1: remove duplicates
                instantiated_clauses = [c.instantiated for c in cls]
                sampled_clauses = [
                    item for sublist in instantiated_clauses for item in sublist
                ]
                print(
                    f"Sampled {len(sampled_clauses)} different clauses in {sample_time} seconds"
                )

                if arguments.verbosity >= 1:
                    print("Sampled clauses:")
                    sampled_clauses.sort(key=lambda x: len(x))
                    for index, current_cl in enumerate(sampled_clauses):
                        print(f"{index}) {current_cl}")

                # Step 2: place the variables
                # This is THE bottleneck: generation of all the
                # possible locations, which are #n_vars^#n_pos in the
                # worst case
                start_time = time.time()
                with phase("variable_placement"):
                    placed_list: "list[list[str]]" = (
                        placer.place_variables_list_of_clauses(sampled_clauses)
                    )
                placing_time = time.time() - start_time
                print(f"Placed variables in {placing_time} seconds")

                placed_list_improved: "list[PlacedClause]" = list(
                    map(PlacedClause, placed_list)
                )

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
                current_strategy = Strategy(placed_list_improved, program, arguments)

                prg, score, best_found, best_index_stub_for_the_next_round = (
                    current_strategy.genetic_solver()
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
        program = Parser(arguments.filename).read_from_file()
    else:
        print_error_and_exit("Specify a file with the task")

    if arguments.automatic_language_bias != 0:
        program.auto_generate_language_bias(arguments.automatic_language_bias)

    if arguments.predicate_invention != 0:
        program.invent_predicates(arguments.predicate_invention)

    solve(program, arguments)
