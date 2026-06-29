import sys
import time

from gentians.evolution.algorithms.genetic import genetic_solver
from gentians.evolution.factories import (
    create_crossover,
    create_fitness,
    create_mutation,
    create_population,
    create_replacement,
    create_selection,
)

from .arguments import Arguments
from .rule_generation.hypothesis_space import build_hypothesis_space, read_task
from .rule_generation.program import Program
from .timing import export as export_timings, phase


def solve(program: Program, arguments: Arguments) -> None:
    """
    Main loop.
    """

    start_total_time = time.time()

    try:
        with phase("total_execution"):
            clauses = build_hypothesis_space(
                program,
                arguments,
            )

            if len(clauses) == 0:
                print("\033[91m" + "Error: " + "No clauses found" + "\033[0m")
                sys.exit(-1)

            prg, score, best_found = genetic_solver(
                clauses,
                arguments,
                create_fitness(program, arguments.fitness, clauses),
                create_population(arguments.population),
                create_selection(arguments.selection),
                create_crossover(arguments.crossover),
                create_mutation(arguments.mutation),
                create_replacement(arguments.replacement),
            )

            if best_found:
                print(f"--- Found best program with score {score} ---")
            else:
                print(f"--- Best candidate program with score {score} ---")
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
        print("\033[91m" + "Error: " + "Specify a file with the task" + "\033[0m")
        sys.exit(-1)

    if arguments.automatic_language_bias != 0:
        program.auto_generate_language_bias(arguments.automatic_language_bias)

    if arguments.predicate_invention != 0:
        program.invent_predicates(arguments.predicate_invention)

    solve(program, arguments)
