from __future__ import annotations

import random

from .crossovers.set_mix import set_mix_crossover
from .fitness.coverage_fixed import coverage_fixed
from .fitness.coverage_exp_max import coverage_exp_max
from .fitness.coverage_exp_mean import coverage_exp_mean
from .individual import Individual
from .mutations.random_group import mutate_by_random_group
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
from ..rule_generation.program import Program
from ..rule_generation.rule_space import RuleId, RuleSpace
from ..timing import profile_phase, record_metric


def create_fitness(
    program: Program,
    config: dict[str, object],
    rule_space: RuleSpace,
) -> FitnessFn:
    name = _str(config, "name")
    max_as = _int(config, "max_as")
    clingo_arguments = _str_list(config, "clingo_arguments")
    empty_score = _float(config, "empty_score")
    if name == "coverage_exp_mean":
        return _rendering_fitness(
            rule_space, coverage_exp_mean(program, max_as, clingo_arguments, empty_score)
        )
    if name == "coverage_exp_max":
        return _rendering_fitness(
            rule_space, coverage_exp_max(program, max_as, clingo_arguments, empty_score)
        )
    if name == "coverage_fixed":
        size_penalty = float(config.get("size_penalty", 0.01))
        literal_penalty = float(config.get("literal_penalty", 0.002))
        redundancy_penalty = float(config.get("redundancy_penalty", 0.01))
        return coverage_fixed(
            program,
            max_as,
            clingo_arguments,
            empty_score,
            size_penalty,
            literal_penalty,
            redundancy_penalty,
            rule_space,
        )
    raise ValueError(f"Unknown fitness operator: {name}")


def create_selection(config: dict[str, object]) -> SelectionFn:
    name = _str(config, "name")
    if name == "tournament":
        tournament_size = _int(config, "tournament_size")
        prob_selecting_fittest = _float(config, "prob_selecting_fittest")

        def select(population: list[Individual]) -> tuple[Individual, Individual]:
            return _distinct_pair(
                population,
                tournament_selection(
                    population, tournament_size, prob_selecting_fittest
                ),
                tournament_selection(
                    population, tournament_size, prob_selecting_fittest
                ),
            )

        return select
    if name == "fittest":
        pick_uniform = _bool(config, "pick_uniform")

        def select(population: list[Individual]) -> tuple[Individual, Individual]:
            best_a, best_b = pick_two_fittest(population, pick_uniform)
            return _distinct_pair(population, best_a, best_b)

        return select
    raise ValueError(f"Unknown selection operator: {name}")


def create_crossover(config: dict[str, object]) -> CrossoverFn:
    name = _str(config, "name")
    if name == "set_mix":
        probability = _float(config, "probability")

        def crossover(
            best_a: Individual,
            best_b: Individual,
            evaluate_score: FitnessFn,
            known_signatures: set[tuple[RuleId, ...]],
            max_program_clauses: int,
        ) -> tuple[Individual, Individual]:
            if random.random() < probability:
                return set_mix_crossover(
                    best_a,
                    best_b,
                    evaluate_score,
                    probability,
                    known_signatures,
                    max_program_clauses,
                )
            return _clone_parents_without_crossover(best_a, best_b, probability)

        return crossover
    raise ValueError(f"Unknown crossover operator: {name}")


def create_mutation(config: dict[str, object]) -> MutationFn:
    name = _str(config, "name")
    if name == "random_group":
        probability = _float(config, "probability")

        def mutate(
            element: Individual,
            rule_space: RuleSpace,
            max_program_clauses: int,
            evaluate_score: FitnessFn,
            known_signatures: set[tuple[RuleId, ...]],
        ) -> Individual:
            return mutate_by_random_group(
                element,
                rule_space,
                max_program_clauses,
                probability,
                evaluate_score,
                known_signatures,
            )

        return mutate
    raise ValueError(f"Unknown mutation operator: {name}")


def create_population(config: dict[str, object]) -> PopulationInitializerFn:
    name = _str(config, "name")
    if name == "random":
        size = _int(config, "size")

        def initialize(
            max_program_clauses: int,
            rule_space: RuleSpace,
            evaluate_score: FitnessFn,
        ) -> tuple[list[Individual], bool]:
            return initialize_population(
                max_program_clauses, rule_space, size, evaluate_score
            )

        return initialize
    raise ValueError(f"Unknown population operator: {name}")


def create_replacement(config: dict[str, object]) -> ReplacementFn:
    name = _str(config, "name")
    if name == "oldest_or_worst":
        prob_replacing_oldest = _float(config, "prob_replacing_oldest")

        def replace(population: list[Individual], element: Individual) -> list[Individual]:
            return replace_oldest_or_worst(
                population, element, prob_replacing_oldest
            )

        return replace
    raise ValueError(f"Unknown replacement operator: {name}")


def _value(config: dict[str, object], key: str) -> object:
    if key not in config:
        raise ValueError(f"Missing operator config key: {key}")
    return config[key]


def _str(config: dict[str, object], key: str) -> str:
    return str(_value(config, key))


def _int(config: dict[str, object], key: str) -> int:
    return int(_value(config, key))


def _float(config: dict[str, object], key: str) -> float:
    return float(_value(config, key))


def _bool(config: dict[str, object], key: str) -> bool:
    value = _value(config, key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _str_list(config: dict[str, object], key: str) -> list[str]:
    value = _value(config, key)
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    raise ValueError(f"Operator config key must be a list[str] or str: {key}")


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
            "strategy": "set_mix",
            "applied": False,
            "not_applied": True,
            "probability": probability,
            "parent_a_score": best_a.score,
            "parent_b_score": best_b.score,
            "child_1_score": child_a.score,
            "child_2_score": child_b.score,
            "children": 2,
            "children_improved": 0,
            "children_best": int(child_a.is_best) + int(child_b.is_best),
            "children_same_as_parent": 2,
            "children_duplicate_parent": 2,
            "children_duplicate_population": 0,
        },
    )
    return child_a, child_b


def _clone_individual(individual: Individual) -> Individual:
    return Individual(
        list(individual.program),
        individual.score,
        individual.is_best,
        list(individual.l_best_indexes),
    )


def _rendering_fitness(rule_space: RuleSpace, evaluate_text_program):
    def evaluate(program: list[RuleId]) -> tuple[float, bool, list[int]]:
        return evaluate_text_program(rule_space.render(program))

    return evaluate


def _distinct_pair(
    population: list[Individual], first: Individual, second: Individual
) -> tuple[Individual, Individual]:
    if first.signature != second.signature:
        return first, second
    alternative = next(
        (element for element in population if element.signature != first.signature),
        second,
    )
    return first, alternative
