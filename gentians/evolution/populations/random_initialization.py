import random

from ..individual import Individual
from ..types import FitnessFn
from ...rule_generation.placed_clause import PlacedClause
from ...timing import profile_phase


@profile_phase("fitness.initialization")
def initialize_population(
    number_clauses: int,
    # placed_list : 'list[list[str]]',
    placed_list: "list[PlacedClause]",
    population_size: int,
    evaluate_score: FitnessFn,
) -> "tuple[list[Individual],bool]":
    """
    Initialize the population of individuals
    """
    sampled_individuals: "list[Individual]" = []
    best_found = False

    while len(sampled_individuals) < population_size:
        # pick a program
        # TODO: non necessariamente il sampling deve essere senza ripetizioni
        stub_indexes: "list[int]" = sorted(
            random.sample(
                range(len(placed_list)),
                number_clauses
                if len(placed_list) > number_clauses
                else len(placed_list),
            )
        )

        # for every index, select one of the possible variable placement
        program: "list[str]" = []
        prog_indexes: "list[int]" = []
        for i in stub_indexes:
            # el = random.randint(0, len(placed_list[i]) - 1)
            el = random.randint(0, len(placed_list[i].placed_clauses) - 1)
            prog_indexes.append(el)
            # program.append(placed_list[i][el])
            program.append(placed_list[i].placed_clauses[el])

        program = sorted(program)
        # cp is the current program
        # cp, cn, current_score, best_found, l_index = evaluate_score(program)
        # print("evaluate score in init")
        current_score, best_found, l_index = evaluate_score(
            stub_indexes, prog_indexes, program
        )

        if best_found:
            # TODO: restituire anche la combinazione di elementi
            return [
                Individual(
                    [program[i] for i in l_index],
                    stub_indexes,
                    prog_indexes,
                    current_score,
                )
            ], best_found

        sampled_individuals.append(
            Individual(program, stub_indexes, prog_indexes, current_score)
        )

    return sampled_individuals, best_found
