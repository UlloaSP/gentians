from __future__ import annotations

import random

from ...arguments import Arguments
from ...rule_generation.hypothesis_space import (
    build_hypothesis_space,
    hypothesis_space_metrics,
)
from ...rule_generation.program import Program
from ...rule_generation.rule_space import RuleSpace
from ...timing import (
    instrumentation,
    metric_enabled,
    net_time,
    phase,
    profile_phase,
    record_ga_generation,
    record_metric,
)
from ..crossovers import create_crossover
from ..evolution_context import EvolutionContext
from ..fitness import create_fitness
from ..individual import Individual, individual_from_fitness, winning_program
from ..mutations import create_mutation
from ..operator_types import MutationProposal
from ..populations import create_population
from ..program_generators import ProgramGenerator
from ..replacements import create_replacement
from ..selections import create_selection
from ..types import Genome


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
    generator = ProgramGenerator(
        program,
        space,
        args.max_program_clauses,
        rng,
        str(args.fitness["name"]).startswith("cov_subprograms_"),
    )
    space = generator.space
    if not space:
        raise ValueError("No clauses satisfy the program generator")
    context = EvolutionContext(space, generator, args.max_program_clauses, rng)

    with phase("initialization"):
        evaluate_score = create_fitness(
            program, args.fitness, args.max_program_clauses, space
        )

    evaluated: dict[Genome, Individual] = {}
    evaluations = 0
    started = net_time()

    def admit(candidate: Genome):
        nonlocal evaluations
        if candidate in evaluated:
            return None
        evaluations += 1
        result = evaluate_score(generator.render(candidate))
        individual = individual_from_fitness(candidate, result)
        evaluated[candidate] = individual
        return individual

    with phase("initialization"):
        mutation = create_mutation(args.mutation, context)
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
        return winning_program(winner, generator.render(winner.program)), winner.score, True

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
                children = [(first, False, False), (second, False, False)]
            else:
                children = []
                for proposal in proposals:
                    existing = evaluated.get(proposal)
                    child = existing or admit(proposal)
                    if child is not None:
                        children.append((child, existing is None, True))
        for child, base_is_new, crossed in children:
            if crossed:
                _operator_metric(
                    "crossover",
                    args.crossover,
                    first if first.score >= second.score else second,
                    child,
                    child.program,
                    duplicate=not base_is_new,
                )
            if child.is_best:
                return (
                    winning_program(child, generator.render(child.program)),
                    child.score,
                    True,
                )
            with phase("mutation"):
                proposal = mutation(child.program, context)
                duplicate = proposal.program in evaluated
                unchanged = proposal.program == child.program
                if unchanged:
                    mutated = child
                elif duplicate:
                    mutated = None
                else:
                    mutated = admit(proposal.program)
            _mutation_metric(
                args.mutation,
                child.program,
                child,
                mutated,
                proposal,
                duplicate=duplicate,
            )
            if mutated is None:
                continue
            if unchanged and not base_is_new:
                continue
            if mutated.is_best:
                return (
                    winning_program(mutated, generator.render(mutated.program)),
                    mutated.score,
                    True,
                )
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
    population.sort(key=lambda item: item.score, reverse=True)
    best_overall = _better(best_overall, population[0])
    return (
        winning_program(best_overall, generator.render(best_overall.program)),
        best_overall.score,
        best_overall.is_best,
    )


def _better(current: Individual | None, candidate: Individual) -> Individual:
    return candidate if current is None or candidate.score > current.score else current


def _operator_metric(
    operator: str,
    config: dict[str, object],
    parent: Individual,
    child: Individual | None,
    child_program: Genome,
    *,
    duplicate: bool,
) -> None:
    with instrumentation():
        changed = child_program != parent.program
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
                "child_score": child.score if child is not None else "",
                "original_score": parent.score,
                "new_score": child.score if child is not None else "",
                "improved": child is not None and child.score > parent.score,
                "best": child.is_best if child is not None else False,
                "is_best": child.is_best if child is not None else False,
            },
        )


def _mutation_metric(
    config: dict[str, object],
    parent_program: Genome,
    parent: Individual | None,
    child: Individual | None,
    proposal: MutationProposal,
    *,
    duplicate: bool,
) -> None:
    with instrumentation():
        changed = proposal.program != parent_program
        record_metric(
            "operator",
            {
                "operator": "mutation",
                "strategy": str(config["name"]),
                "operation": proposal.operation or "",
                "local": proposal.local if proposal.local is not None else "",
                "structural_distance": (
                    proposal.structural_distance
                    if proposal.structural_distance is not None
                    else ""
                ),
                "candidate_pool_size": proposal.candidate_pool_size,
                "program_distance": _program_distance(
                    parent_program, proposal.program
                ),
                "changed_rules": (parent_program ^ proposal.program).bit_count(),
                "applied": changed,
                "slots": 1,
                "valid_new": changed and not duplicate,
                "duplicate": duplicate,
                "duplicate_population": duplicate,
                "changed": changed,
                "invalid": False,
                "parent_score": parent.score if parent is not None else "",
                "child_score": child.score if child is not None else "",
                "original_score": parent.score if parent is not None else "",
                "new_score": child.score if child is not None else "",
                "improved": (
                    child is not None
                    and parent is not None
                    and child.score > parent.score
                ),
                "best": child.is_best if child is not None else False,
                "is_best": child.is_best if child is not None else False,
            },
        )


def _program_distance(first: Genome, second: Genome) -> float:
    union = (first | second).bit_count()
    return 0.0 if not union else 1.0 - (first & second).bit_count() / union
