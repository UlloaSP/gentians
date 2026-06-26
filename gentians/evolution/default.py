from .algorithms.genetic import Strategy
from .factories import (
    create_crossover,
    create_fitness,
    create_mutation,
    create_population,
    create_replacement,
    create_selection,
)
from ..arguments import Arguments
from ..rule_generation.placed_clause import PlacedClause
from ..rule_generation.program import Program


def create_default_genetic_strategy(
    placed_list: list[PlacedClause],
    program: Program,
    arguments: Arguments,
) -> Strategy:
    replacement = create_replacement(arguments.replacement)
    return Strategy(
        placed_list,
        program,
        arguments,
        create_fitness(program, arguments.fitness),
        create_population(arguments.population),
        create_selection(arguments.selection),
        create_crossover(arguments.crossover),
        create_mutation(arguments.mutation),
        replacement,
    )
