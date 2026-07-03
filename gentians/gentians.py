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
from .rule_generation.hypothesis_space import build_hypothesis_space
from .rule_generation.reader import read_program
from .rule_generation.program import Program
from .rule_generation.rule_space import RuleSpace
from .evolution.program_sampler import ProgramSampler
from .timing import export as export_timings, phase, record_metric


def solve(
    program: Program, arguments: Arguments, rule_space: RuleSpace | None = None
) -> None:
    """
    Main loop.
    """

    start_total_time = time.time()

    try:
        with phase("total_execution"):
            if rule_space is None:
                rule_space = build_hypothesis_space(
                    program,
                    arguments,
                )
            else:
                record_metric(
                    "candidate",
                    {
                        "metric": "hypothesis_space",
                        "clauses": len(rule_space),
                    },
                )

            if len(rule_space) == 0:
                print("\033[91m" + "Error: " + "No clauses found" + "\033[0m")
                sys.exit(-1)

            with phase("fitness.setup"):
                sampler = ProgramSampler(program, rule_space)
                evaluate_score = create_fitness(program, arguments.fitness)

            prg, score, best_found = genetic_solver(
                arguments,
                evaluate_score,
                create_population(arguments.population, sampler),
                create_selection(arguments.selection),
                create_crossover(arguments.crossover, sampler),
                create_mutation(arguments.mutation, sampler),
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


def program_from_arguments(arguments: Arguments) -> Program:
    """
    SDK entry point.
    """

    if arguments.filename:
        program = read_program(arguments.filename)
    else:
        print("\033[91m" + "Error: " + "Specify a file with the task" + "\033[0m")
        sys.exit(-1)

    if arguments.automatic_language_bias != 0:
        program.auto_generate_language_bias(arguments.automatic_language_bias)

    if arguments.predicate_invention != 0:
        program.invent_predicates(arguments.predicate_invention)

    return program


def main(arguments: Arguments) -> None:
    """
    SDK entry point.
    """

    program = program_from_arguments(arguments)
    solve(program, arguments)
