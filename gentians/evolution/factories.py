from __future__ import annotations

import math
import random

from .crossovers.one_point import one_point_crossover
from .fitness.evaluator import FitnessEvaluator
from .individual import Individual
from .mutations.random_stub import mutate_by_random_stub
from .populations.random_initialization import initialize_population
from .replacements.oldest_or_worst import replace_oldest_or_worst
from .selections.fittest import pick_two_fittest
from .selections.tournament import tournament_selection
from .types import (
    CrossoverFn,
    FitnessFn,
    MutationFn,
    PopulationInitializerFn,
    ReplacementFn,
    SelectionFn,
)
from ..rule_generation.placed_clause import PlacedClause
from ..rule_generation.program import Program
from ..timing import profile_phase, record_metric


def create_fitness(program: Program, config: dict[str, object]) -> FitnessFn:
    name = _str(config, "name", "coverage_exp_mean")
    max_as = _int(config, "max_as", 10000)
    clingo_arguments = _str_list(config, "clingo_arguments", ["--project"])
    empty_score = _float(config, "empty_score", -2000.0)
    if name == "coverage_exp_mean":
        evaluator = FitnessEvaluator(
            program,
            max_as,
            clingo_arguments,
            empty_score,
            name,
            _coverage_exp_score,
            _mean,
            select_best_by_score=False,
        )
        return evaluator.evaluate_score
    if name == "coverage_exp_max":
        evaluator = FitnessEvaluator(
            program,
            max_as,
            clingo_arguments,
            empty_score,
            name,
            _coverage_exp_score,
            max,
            select_best_by_score=True,
        )
        return evaluator.evaluate_score
    raise ValueError(f"Unknown fitness operator: {name}")


def create_selection(config: dict[str, object]) -> SelectionFn:
    name = _str(config, "name", "tournament")
    if name == "tournament":
        tournament_size = _int(config, "tournament_size", 12)
        prob_selecting_fittest = _float(config, "prob_selecting_fittest", 0.9)

        def select(population: list[Individual]) -> tuple[Individual, Individual]:
            return (
                tournament_selection(
                    population, tournament_size, prob_selecting_fittest
                ),
                tournament_selection(
                    population, tournament_size, prob_selecting_fittest
                ),
            )

        return select
    if name == "fittest":
        pick_uniform = _bool(config, "pick_uniform", True)

        def select(population: list[Individual]) -> tuple[Individual, Individual]:
            return pick_two_fittest(population, pick_uniform)

        return select
    raise ValueError(f"Unknown selection operator: {name}")


def create_crossover(config: dict[str, object]) -> CrossoverFn:
    name = _str(config, "name", "one_point")
    if name == "one_point":
        probability = _float(config, "probability", 1.0)

        def crossover(
            best_a: Individual,
            best_b: Individual,
            evaluate_score: FitnessFn,
        ) -> tuple[Individual, Individual]:
            if random.random() < probability:
                return one_point_crossover(
                    best_a, best_b, evaluate_score, probability
                )
            return _clone_parents_without_crossover(best_a, best_b, probability)

        return crossover
    raise ValueError(f"Unknown crossover operator: {name}")


def create_mutation(config: dict[str, object]) -> MutationFn:
    name = _str(config, "name", "random_stub")
    if name == "random_stub":
        probability = _float(config, "probability", 0.2)
        change_stub = _bool(config, "change_stub", True)

        def mutate(
            element: Individual,
            placed_list: list[PlacedClause],
            evaluate_score: FitnessFn,
        ) -> Individual:
            return mutate_by_random_stub(
                element, placed_list, probability, evaluate_score, change_stub
            )

        return mutate
    raise ValueError(f"Unknown mutation operator: {name}")


def create_population(config: dict[str, object]) -> PopulationInitializerFn:
    name = _str(config, "name", "random")
    if name == "random":
        size = _int(config, "size", 50)

        def initialize(
            number_clauses: int,
            placed_list: list[PlacedClause],
            evaluate_score: FitnessFn,
        ) -> tuple[list[Individual], bool]:
            return initialize_population(
                number_clauses, placed_list, size, evaluate_score
            )

        return initialize
    raise ValueError(f"Unknown population operator: {name}")


def create_replacement(config: dict[str, object]) -> tuple[ReplacementFn, int]:
    name = _str(config, "name", "oldest_or_worst")
    if name == "oldest_or_worst":
        prob_replacing_oldest = _float(config, "prob_replacing_oldest", 0.5)
        k_best_for_next_round = _int(config, "k_best_for_next_round", 5)

        def replace(population: list[Individual], element: Individual) -> list[Individual]:
            return replace_oldest_or_worst(
                population, element, prob_replacing_oldest
            )

        return replace, k_best_for_next_round
    raise ValueError(f"Unknown replacement operator: {name}")


def _str(config: dict[str, object], key: str, default: str) -> str:
    return str(config.get(key, default))


def _int(config: dict[str, object], key: str, default: int) -> int:
    return int(config.get(key, default))


def _float(config: dict[str, object], key: str, default: float) -> float:
    return float(config.get(key, default))


def _bool(config: dict[str, object], key: str, default: bool) -> bool:
    value = config.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _str_list(config: dict[str, object], key: str, default: list[str]) -> list[str]:
    value = config.get(key, default)
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    return list(default)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _coverage_exp_score(positive_rate: float, negative_rate: float) -> float:
    return math.exp((positive_rate - negative_rate) * 10)


@profile_phase("crossover")
def _clone_parents_without_crossover(
    best_a: Individual, best_b: Individual, probability: float
) -> tuple[Individual, Individual]:
    child_a = _clone_individual(best_a)
    child_b = _clone_individual(best_b)
    record_metric(
        "operator",
        {
            "operator": "crossover",
            "strategy": "one_point",
            "applied": False,
            "probability": probability,
            "parent_a_score": best_a.score,
            "parent_b_score": best_b.score,
            "child_1_score": child_a.score,
            "child_2_score": child_b.score,
            "children": 2,
            "children_improved": 0,
            "children_best": int(child_a.is_best) + int(child_b.is_best),
            "children_duplicate_parent": 2,
        },
    )
    return child_a, child_b


def _clone_individual(individual: Individual) -> Individual:
    return Individual(
        list(individual.program),
        list(individual.stub_indexes),
        list(individual.prog_indexes),
        individual.score,
        individual.is_best,
        list(individual.l_best_indexes),
    )
