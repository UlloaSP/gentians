from .algorithms.genetic import Strategy
from .crossovers.one_point import one_point_crossover
from .fitness.evaluator import FitnessEvaluator
from .mutations.random_stub import mutate_by_random_stub
from .populations.random_initialization import initialize_population
from .replacements.oldest_or_worst import replace_oldest_or_worst
from .selections.fittest import pick_two_fittest
from .selections.tournament import tournament_selection
from ..arguments import Arguments
from ..rule_generation.placed_clause import PlacedClause
from ..rule_generation.program import Program


def create_default_genetic_strategy(
    placed_list: list[PlacedClause],
    program: Program,
    arguments: Arguments,
) -> Strategy:
    fitness_evaluator = FitnessEvaluator(program, 10000)
    return Strategy(
        placed_list,
        program,
        arguments,
        fitness_evaluator.evaluate_score,
        initialize_population,
        tournament_selection,
        pick_two_fittest,
        one_point_crossover,
        mutate_by_random_stub,
        replace_oldest_or_worst,
    )
