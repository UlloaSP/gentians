from __future__ import annotations

import random
import time

from ...arguments import Arguments
from ...rule_generation.hypothesis_space import build_hypothesis_space
from ...rule_generation.program import Program
from ...rule_generation.rule_space import RuleSpace
from ...timing import (
    instrumentation,
    metric_enabled,
    phase,
    profile_phase,
    record_ga_generation,
    record_metric,
)
from ..crossovers import create_crossover
from ..closures import create_closure
from ..evolution_context import EvolutionContext
from ..fitness import create_fitness
from ..individual import Individual, individual_from_fitness, winning_program
from ..mutations import create_mutation
from ..populations import create_population
from ..replacements import create_replacement
from ..selections import create_selection


@profile_phase("search")
def search_solver(
    args: Arguments,
    program: Program,
    supplied_space: RuleSpace | None = None,
) -> tuple[tuple[str, ...], float, bool]:
    rng = random.Random(args.random_seed)
    population_strategy = create_population(args.population)
    selection = create_selection(args.selection)
    crossover = create_crossover(args.crossover)
    mutation = create_mutation(args.mutation)
    replacement = create_replacement(args.replacement)
    generations = args.iterations_genetic

    space = (
        supplied_space
        if supplied_space is not None
        else build_hypothesis_space(program, args)
    )
    if supplied_space is not None and metric_enabled("candidate"):
        with instrumentation():
            record_metric(
                "candidate",
                {"metric": "hypothesis_space", "clauses": len(space)},
            )
    if not space:
        raise ValueError("No clauses found")
    policy = create_closure(
        str(args.closure["name"]),
        program,
        space,
        args.max_program_clauses,
        rng,
        str(args.fitness["name"]).startswith("cov_subprograms_"),
    )
    space = policy.space
    if not space:
        raise ValueError("No clauses satisfy the closure policy")
    context = EvolutionContext(space, policy, args.max_program_clauses, rng)

    with phase("fitness.setup"):
        evaluate_score = create_fitness(
            program, args.fitness, args.max_program_clauses, space.clauses
        )

    known: set[tuple[str, ...]] = set()
    evaluations = 0
    started = time.perf_counter()

    def admit(proposal: tuple[str, ...], previous: Individual | None = None):
        nonlocal evaluations
        normalized = policy.normalize(proposal)
        if normalized is None:
            return None
        if previous is not None and normalized == previous.program:
            return previous
        if normalized in known:
            return None
        evaluations += 1
        with phase("fitness"):
            score = evaluate_score(normalized)
        individual = individual_from_fitness(normalized, score)
        known.add(normalized)
        return individual

    with phase("population"):
        population = [
            individual
            for proposal in population_strategy(context)
            if (individual := admit(proposal)) is not None
        ]
    if not population:
        raise RuntimeError("Could not initialize population")
    population.sort(key=lambda item: item.score, reverse=True)
    winner = next((item for item in population if item.is_best), None)
    if winner is not None:
        return winning_program(winner), winner.score, True

    best_overall = population[0]
    for generation in range(generations):
        population.sort(key=lambda item: item.score, reverse=True)
        best_overall = _better(best_overall, population[0])
        record_ga_generation(
            generation,
            best_overall.score,
            population,
            epoch=0,
            global_generation=generation,
            elapsed_seconds=time.perf_counter() - started,
            fitness_evaluations=evaluations,
        )
        with phase("selection"):
            first, second = selection(population, rng)
            record_metric(
                "operator",
                {
                    "operator": "selection",
                    "strategy": str(args.selection["name"]),
                    "parent_a_score": first.score,
                    "parent_b_score": second.score,
                    "population_size": len(population),
                },
            )
        with phase("crossover"):
            proposals = crossover(first.program, second.program, context)
        if not proposals:
            record_metric(
                "operator",
                {
                    "operator": "crossover",
                    "strategy": str(args.crossover["name"]),
                    "applied": False,
                    "skipped": True,
                    "children": 0,
                    "population_size": len(population),
                },
            )
            continue
        for proposal in proposals:
            normalized = policy.normalize(proposal)
            existing = next(
                (item for item in population if item.program == normalized), None
            )
            child = admit(proposal, existing)
            if child is None:
                continue
            _operator_metric(
                "crossover",
                args.crossover,
                first if first.score >= second.score else second,
                child,
                duplicate=existing is not None,
            )
            if child.is_best:
                return winning_program(child), child.score, True
            with phase("mutation"):
                mutated_proposal = mutation(child.program, context)
            mutated = admit(mutated_proposal, child)
            if mutated is None:
                continue
            _operator_metric(
                "mutation", args.mutation, child, mutated, duplicate=mutated is child
            )
            if mutated.is_best:
                return winning_program(mutated), mutated.score, True
            with phase("replacement"):
                before = list(population)
                population = replacement(population, mutated, rng)
            accepted = any(item is mutated for item in population)
            duplicate = any(item.program == mutated.program for item in before)
            victim = next(
                (
                    item
                    for item in before
                    if all(item is not kept for kept in population)
                ),
                None,
            )
            record_metric(
                "operator",
                {
                    "operator": "replacement",
                    "strategy": str(args.replacement["name"]),
                    "candidate_score": mutated.score,
                    "accepted": accepted,
                    "duplicate": duplicate,
                    "invalid": False,
                    "not_competitive": not accepted and not duplicate,
                    "reject_reason": (
                        ""
                        if accepted
                        else "duplicate"
                        if duplicate
                        else "not_competitive"
                    ),
                    "victim_score": victim.score if victim is not None else "",
                    "improved_victim": (
                        accepted and victim is not None and mutated.score > victim.score
                    ),
                    "population_size": len(population),
                },
            )
            known = {item.program for item in population}

    population.sort(key=lambda item: item.score, reverse=True)
    best_overall = _better(best_overall, population[0])
    return winning_program(best_overall), best_overall.score, best_overall.is_best


def _better(current: Individual | None, candidate: Individual) -> Individual:
    return candidate if current is None or candidate.score > current.score else current


def _operator_metric(
    operator: str,
    config: dict[str, object],
    parent: Individual,
    child: Individual,
    *,
    duplicate: bool,
) -> None:
    changed = child.program != parent.program
    record_metric(
        "operator",
        {
            "operator": operator,
            "strategy": str(config["name"]),
            "applied": changed,
            "slots": 1,
            "valid_new": changed and not duplicate,
            "duplicate": duplicate,
            "duplicate_population": duplicate,
            "changed": changed,
            "parent_score": parent.score,
            "child_score": child.score,
            "original_score": parent.score,
            "new_score": child.score,
            "improved": child.score > parent.score,
            "best": child.is_best,
            "is_best": child.is_best,
        },
    )
