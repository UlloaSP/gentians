from __future__ import annotations

import random
import time

from ...arguments import Arguments
from ...rule_generation.hypothesis_space import (
    build_hypothesis_space,
    hypothesis_space_metrics,
)
from ...rule_generation.program import Program
from ...rule_generation.rule_space import RuleSpace
from ...timing import (
    add,
    current_phase,
    instrumentation,
    metric_enabled,
    net_time,
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
                hypothesis_space_metrics(program, space),
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

    if str(args.fitness.get("grounding", "normal")) == "normal":
        evaluate_score = create_fitness(
            program, args.fitness, args.max_program_clauses, space.clauses
        )
    else:
        with phase("pregrounding"):
            evaluate_score = create_fitness(
                program, args.fitness, args.max_program_clauses, space.clauses
            )

    known: set[tuple[str, ...]] = set()
    evaluations = 0
    started = net_time()

    def admit(normalized: tuple[str, ...], previous: Individual | None = None):
        nonlocal evaluations
        if previous is not None and normalized == previous.program:
            return previous
        if normalized in known:
            return None
        evaluations += 1
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
            elapsed_seconds=net_time() - started,
            fitness_evaluations=evaluations,
        )
        with phase("selection"):
            first, second = selection(population, rng)
            with instrumentation():
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
                with instrumentation():
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
            children = []
            for proposal in proposals:
                normalized = _normalize(policy, proposal)
                if normalized is None:
                    continue
                existing = next(
                    (item for item in population if item.program == normalized), None
                )
                child = admit(normalized, existing)
                if child is not None:
                    children.append((child, existing is not None))
        for child, duplicate in children:
            _operator_metric(
                "crossover",
                args.crossover,
                first if first.score >= second.score else second,
                child,
                duplicate=duplicate,
            )
            if child.is_best:
                return winning_program(child), child.score, True
            with phase("mutation"):
                mutated_proposal = mutation(child.program, context)
                normalized = _normalize(policy, mutated_proposal)
                mutated = admit(normalized, child) if normalized is not None else None
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
            with instrumentation():
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
                            accepted
                            and victim is not None
                            and mutated.score > victim.score
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


def _normalize(policy, proposal: tuple[str, ...]) -> tuple[str, ...] | None:
    started = time.perf_counter()
    normalized = policy.normalize(proposal)
    add(f"{current_phase()}.closure", time.perf_counter() - started)
    return normalized


def _operator_metric(
    operator: str,
    config: dict[str, object],
    parent: Individual,
    child: Individual,
    *,
    duplicate: bool,
) -> None:
    with instrumentation():
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
