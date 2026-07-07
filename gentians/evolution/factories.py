from __future__ import annotations

import random

from .crossovers.set_mix import set_mix_crossover
from .fitness.coverage_fixed import coverage_fixed
from .individual import Individual
from .program_sampler import ProgramSampler
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
from ..timing import instrumentation, metric_enabled, record_metric


def create_fitness(
    program: Program,
    config: dict[str, object],
) -> FitnessFn:
    name = _str(config, "name")
    max_as = _int(config, "max_as")
    clingo_arguments = _str_list(config, "clingo_arguments")
    if name == "coverage_fixed":
        size_penalty = float(config.get("size_penalty", 0.01))
        literal_penalty = float(config.get("literal_penalty", 0.002))
        redundancy_penalty = float(config.get("redundancy_penalty", 0.01))
        return coverage_fixed(
            program,
            max_as,
            clingo_arguments,
            size_penalty,
            literal_penalty,
            redundancy_penalty,
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


def create_crossover(config: dict[str, object], sampler: ProgramSampler) -> CrossoverFn:
    name = _str(config, "name")
    if name == "set_mix":
        probability = _float(config, "probability")

        def crossover(
            best_a: Individual,
            best_b: Individual,
            evaluate_score: FitnessFn,
            known_signatures: set[tuple[str, ...]],
            max_program_clauses: int,
        ) -> tuple[Individual, Individual] | None:
            if random.random() < probability:
                return set_mix_crossover(
                    best_a,
                    best_b,
                    evaluate_score,
                    probability,
                    known_signatures,
                    max_program_clauses,
                    sampler,
                )
            _record_skipped_crossover(best_a, best_b, probability)
            return None

        return crossover
    raise ValueError(f"Unknown crossover operator: {name}")


def create_mutation(config: dict[str, object], sampler: ProgramSampler) -> MutationFn:
    name = _str(config, "name")
    if name == "random_group":
        probability = _float(config, "probability")

        def mutate(
            element: Individual,
            max_program_clauses: int,
            evaluate_score: FitnessFn,
            known_signatures: set[tuple[str, ...]],
            extra_forbidden_signatures: set[tuple[str, ...]],
        ) -> Individual:
            return mutate_by_random_group(
                element,
                max_program_clauses,
                probability,
                evaluate_score,
                known_signatures,
                sampler,
                extra_forbidden_signatures,
            )

        return mutate
    raise ValueError(f"Unknown mutation operator: {name}")


def create_population(config: dict[str, object], sampler: ProgramSampler) -> PopulationInitializerFn:
    name = _str(config, "name")
    if name == "random":
        size = _int(config, "size")

        def initialize(
            max_program_clauses: int,
            evaluate_score: FitnessFn,
        ) -> tuple[list[Individual], bool]:
            return initialize_population(
                max_program_clauses, size, evaluate_score, sampler
            )

        return initialize
    raise ValueError(f"Unknown population operator: {name}")


def create_replacement(config: dict[str, object]) -> ReplacementFn:
    name = _str(config, "name")
    if name == "oldest_or_worst":
        prob_replacing_oldest = _float(config, "prob_replacing_oldest")

        def replace(
            population: list[Individual],
            element: Individual,
            population_signatures: set[tuple[str, ...]],
        ) -> list[Individual]:
            return replace_oldest_or_worst(
                population, element, population_signatures, prob_replacing_oldest
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


def _record_skipped_crossover(
    best_a: Individual, best_b: Individual, probability: float
) -> None:
    if metric_enabled("operator"):
        with instrumentation():
            record_metric(
                "operator",
                {
                    "operator": "crossover",
                    "strategy": "set_mix",
                    "applied": False,
                    "skipped": True,
                    "not_applied": True,
                    "probability": probability,
                    "parent_a_score": best_a.score,
                    "parent_b_score": best_b.score,
                    "child_1_score": "",
                    "child_2_score": "",
                    "slots": 2,
                    "children": 0,
                    "children_valid_new": 0,
                    "children_invalid": 0,
                    "children_improved": 0,
                    "children_best": 0,
                    "children_same_as_parent": 0,
                    "children_duplicate_parent": 0,
                    "children_duplicate_population": 0,
                },
            )

def _distinct_pair(
    population: list[Individual], first: Individual, second: Individual
) -> tuple[Individual, Individual]:
    if first.program != second.program:
        return first, second
    alternative = next(
        (element for element in population if element.program != first.program),
        second,
    )
    return first, alternative
