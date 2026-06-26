import random

from ..individual import Individual
from ..types import FitnessFn
from ...rule_generation.placed_clause import PlacedClause
from ...timing import profile_phase


@profile_phase("fitness.initialization")
def initialize_population(
    number_clauses: int,
    placed_list: list[PlacedClause],
    population_size: int,
    evaluate_score: FitnessFn,
) -> tuple[list[Individual],bool]:
    """
    Initialize the population of individuals
    """
    sampled_individuals: list[Individual] = []
    best_found = False
    seen_signatures: set[tuple[str, ...]] = set()
    attempts = 0
    max_unique_attempts = population_size * 20

    while len(sampled_individuals) < population_size:
        attempts += 1
        # pick a program
        # TODO: non necessariamente il sampling deve essere senza ripetizioni
        group_indexes: list[int] = sorted(
            random.sample(
                range(len(placed_list)),
                number_clauses
                if len(placed_list) > number_clauses
                else len(placed_list),
            )
        )

        # for every index, select one of the possible variable placement
        program: list[str] = []
        prog_indexes: list[int] = []
        for i in group_indexes:
            # el = random.randint(0, len(placed_list[i]) - 1)
            el = random.randint(0, len(placed_list[i].placed_clauses) - 1)
            prog_indexes.append(el)
            # program.append(placed_list[i][el])
            program.append(placed_list[i].placed_clauses[el])

        program = sorted(program)
        signature = tuple(program)
        if signature in seen_signatures and attempts < max_unique_attempts:
            continue
        seen_signatures.add(signature)
        # cp is the current program
        # cp, cn, current_score, best_found, l_index = evaluate_score(program)
        # print("evaluate score in init")
        current_score, best_found, l_index = evaluate_score(
            group_indexes, prog_indexes, program
        )

        if best_found:
            # TODO: restituire anche la combinazione di elementi
            return [
                Individual(
                    [program[i] for i in l_index],
                    group_indexes,
                    prog_indexes,
                    current_score,
                    False,
                    [],
                )
            ], best_found

        sampled_individuals.append(
            Individual(program, group_indexes, prog_indexes, current_score, False, [])
        )

    return sampled_individuals, best_found
