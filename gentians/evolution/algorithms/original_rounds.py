import random
import time

from ...arguments import Arguments
from ...rule_generation.rule_space import RuleSpace
from ...timing import phase, profile_phase, record_ga_generation
from ..crossovers.original_one_point import original_one_point_crossover
from ..individual import Individual, winning_program
from ..mutations.original_random_clause import mutate_by_original_random_clause
from ..populations.original_random import initialize_original_population
from ..replacements.original_oldest_or_worst import replace_original_oldest_or_worst
from ..selections.fittest import pick_two_fittest
from ..selections.tournament import tournament_selection
from ..types import FitnessFn


@profile_phase("genetic")
def original_rounds_solver(
    args: Arguments,
    rule_space: RuleSpace,
    evaluate_score: FitnessFn,
) -> tuple[tuple[str, ...], float, bool]:
    carried_rules: list[str] = []
    best_overall: Individual | None = None

    for round_index in range(args.iterations):
        print(f"Sampling loop: {round_index}")
        round_rules = _sample_round_rules(rule_space, args.sample, carried_rules)
        carried_rules = []
        round_space = RuleSpace.from_clauses(round_rules)

        population, best_found = initialize_original_population(
            args.max_program_clauses,
            int(args.population["size"]),
            evaluate_score,
            round_space,
        )
        if not population:
            continue

        with phase("genetic.bookkeeping"):
            population.sort(key=lambda individual: individual.score, reverse=True)
        best = next((individual for individual in population if individual.is_best), None)
        if best is not None:
            return winning_program(best), best.score, True

        start_time = time.time()
        for generation in range(args.iterations_genetic + 1):
            with phase("genetic.bookkeeping"):
                best_overall = _best_individual(best_overall, population[0])
                record_ga_generation(
                    round_index * (args.iterations_genetic + 1) + generation,
                    best_overall.score,
                    population,
                )
            if generation % 100 == 0:
                print(
                    "Iteration "
                    f"{generation} - taken for 100: {time.time() - start_time} "
                    f"- best: {population[0]}"
                )
                start_time = time.time()

            parent_a, parent_b = _select(args, population)
            crossed = original_one_point_crossover(
                parent_a,
                parent_b,
                evaluate_score,
                float(args.crossover["probability"]),
                {individual.program for individual in population},
                args.max_program_clauses,
            )
            if crossed is None:
                continue
            child_a, child_b = crossed
            for child in (child_a, child_b):
                if child.is_best:
                    return winning_program(child), child.score, True

            mutated = [
                mutate_by_original_random_clause(
                    child,
                    args.max_program_clauses,
                    float(args.mutation["probability"]),
                    evaluate_score,
                    {individual.program for individual in population},
                    round_space,
                )
                for child in (child_a, child_b)
            ]
            for child in mutated:
                if child.is_best:
                    return winning_program(child), child.score, True
                population = replace_original_oldest_or_worst(
                    population,
                    child,
                    {individual.program for individual in population},
                    float(args.replacement["prob_replacing_oldest"]),
                )

        carried_rules = _rules_for_next_round(population, args.k_best_for_next_round)
        best_overall = _best_individual(best_overall, population[0])

    if best_overall is None:
        raise RuntimeError("Could not initialize original-round population")
    return best_overall.program, best_overall.score, best_overall.is_best


def _sample_round_rules(
    rule_space: RuleSpace, sample_size: int, carried_rules: list[str]
) -> tuple[str, ...]:
    rules = list(rule_space.clauses)
    if sample_size > 0 and len(rules) > sample_size:
        rules = random.sample(rules, sample_size)
    rules.extend(carried_rules)
    return tuple(sorted(dict.fromkeys(rules)))


def _select(args: Arguments, population: list[Individual]) -> tuple[Individual, Individual]:
    if str(args.selection["name"]) == "tournament":
        return (
            tournament_selection(
                population,
                int(args.selection["tournament_size"]),
                float(args.selection["prob_selecting_fittest"]),
            ),
            tournament_selection(
                population,
                int(args.selection["tournament_size"]),
                float(args.selection["prob_selecting_fittest"]),
            ),
        )
    return pick_two_fittest(population, bool(args.selection.get("pick_uniform", True)))


def _rules_for_next_round(population: list[Individual], k_best: int) -> list[str]:
    selected = population[1 : k_best + 1] or population[:k_best]
    rules = [rule for individual in selected for rule in individual.program]
    counts = {rule: rules.count(rule) for rule in set(rules)}
    return [
        rule
        for rule, _count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[
            :k_best
        ]
    ]


def _best_individual(current: Individual | None, candidate: Individual) -> Individual:
    if current is None or candidate.score > current.score:
        return candidate
    return current
