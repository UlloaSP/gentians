import random
from itertools import count

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
from ..individual import Individual
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
    generations = (
        count() if args.iterations_genetic == 0 else range(args.iterations_genetic)
    )

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
    max_program_clauses = (
        len(space) if program.max_program_clauses is None else program.max_program_clauses
    )
    generator = ProgramGenerator(
        program,
        space,
        max_program_clauses,
        rng,
    )
    space = generator.space
    if not space:
        raise ValueError("No clauses satisfy the program generator")
    context = EvolutionContext(generator, rng)

    with phase("initialization"):
        evaluate_score = create_fitness(program, args.fitness)

    evaluated: dict[Genome, Individual] = {}
    evaluations = 0
    started = net_time()

    def admit(candidate: Genome):
        nonlocal evaluations
        if candidate in evaluated:
            return None
        evaluations += 1
        result = evaluate_score(generator.render(candidate))
        individual = Individual(
            candidate, result.score, result.is_best, result.behavior
        )
        evaluated[candidate] = individual
        return individual

    with phase("initialization"):
        mutation = create_mutation(args.mutation)
        population = [
            individual
            for proposal in population_strategy(context)
            if (individual := admit(proposal)) is not None
        ]
    if not population:
        raise RuntimeError("Could not initialize population")
    population.sort(key=lambda item: item.score, reverse=True)
    best_overall = population[0]
    winner = next((item for item in population if item.is_best), None)
    if winner is not None:
        record_ga_generation(
            0,
            best_overall.score,
            population,
            elapsed_seconds=net_time() - started,
            fitness_evaluations=evaluations,
        )
        return (
            generator.render(winner.program),
            winner.score,
            True,
        )

    record_ga_generation(
        0,
        best_overall.score,
        population,
        elapsed_seconds=net_time() - started,
        fitness_evaluations=evaluations,
    )
    for generation in generations:
        population.sort(key=lambda item: item.score, reverse=True)
        best_overall = _better(best_overall, population[0])
        with phase("selection"):
            first, second = selection(population, rng)
            with instrumentation():
                record_metric(
                    "operator",
                    {
                        "operator": "selection",
                        "strategy": str(args.selection["name"]),
                        "applied": True,
                        "skipped": False,
                        "slots": 1,
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
                            "slots": 1,
                            "valid_new": False,
                            "duplicate": False,
                            "changed": False,
                            "invalid": False,
                            "original_score": "",
                            "new_score": "",
                            "improved": False,
                            "is_best": False,
                            "population_size": len(population),
                        },
                    )
                children = []
            else:
                children = []
                for proposal in proposals:
                    existing = evaluated.get(proposal)
                    child = existing or admit(proposal)
                    if child is not None:
                        children.append((child, existing is None, True))
        for child, base_is_new, crossed in children:
            best_parent = first if first.score >= second.score else second
            crossover_improved = crossed and child.score > best_parent.score
            if crossed:
                _operator_metric(
                    "crossover",
                    args.crossover,
                    best_parent,
                    child,
                    child.program,
                    duplicate=not base_is_new,
                )
            if child.is_best:
                best_overall = _better(best_overall, child)
                terminal_population = replacement(list(population), child, rng)
                if all(item is not child for item in terminal_population):
                    terminal_population = [*population[:-1], child]
                record_ga_generation(
                    generation + 1,
                    best_overall.score,
                    terminal_population,
                    elapsed_seconds=net_time() - started,
                    fitness_evaluations=evaluations,
                )
                return (
                    generator.render(child.program),
                    child.score,
                    True,
                )
            with phase("mutation"):
                proposal = mutation(child.program, context)
                duplicate = not proposal.skipped and proposal.program in evaluated
                unchanged = proposal.program == child.program
                if unchanged:
                    mutated = child
                elif duplicate:
                    mutated = None
                else:
                    mutated = admit(proposal.program)
            scored_mutation = (
                evaluated.get(proposal.program) if mutated is None else mutated
            )
            _mutation_metric(
                args.mutation,
                child.program,
                child,
                mutated,
                proposal,
                duplicate=duplicate,
                crossover_strategy=str(args.crossover["name"]),
                crossover_improved=crossover_improved,
                lost_crossover_gain=(
                    crossover_improved
                    and scored_mutation is not None
                    and scored_mutation.score < child.score
                    and all(item.program != child.program for item in population)
                ),
            )
            if mutated is None:
                continue
            if unchanged and not base_is_new:
                continue
            if mutated.is_best:
                best_overall = _better(best_overall, mutated)
                terminal_population = replacement(list(population), mutated, rng)
                if all(item is not mutated for item in terminal_population):
                    terminal_population = [*population[:-1], mutated]
                record_ga_generation(
                    generation + 1,
                    best_overall.score,
                    terminal_population,
                    elapsed_seconds=net_time() - started,
                    fitness_evaluations=evaluations,
                )
                return (
                    generator.render(mutated.program),
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
                        "applied": True,
                        "skipped": False,
                        "slots": 1,
                        "candidate_score": mutated.score,
                        "accepted": accepted,
                        "duplicate": duplicate,
                        "invalid": False,
                        "not_competitive": not accepted and not duplicate,
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
        record_ga_generation(
            generation + 1,
            best_overall.score,
            population,
            elapsed_seconds=net_time() - started,
            fitness_evaluations=evaluations,
        )
    population.sort(key=lambda item: item.score, reverse=True)
    best_overall = _better(best_overall, population[0])
    return (
        generator.render(best_overall.program),
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
                "skipped": False,
                "slots": 1,
                "valid_new": changed and not duplicate,
                "duplicate": duplicate,
                "changed": changed,
                "original_score": parent.score,
                "new_score": child.score if child is not None else "",
                "improved": child is not None and child.score > parent.score,
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
    crossover_strategy: str,
    crossover_improved: bool,
    lost_crossover_gain: bool,
) -> None:
    with instrumentation():
        changed = proposal.program != parent_program
        record_metric(
            "operator",
            {
                "operator": "mutation",
                "strategy": str(config["name"]),
                "crossover_strategy": crossover_strategy,
                "crossover_improved": crossover_improved,
                "lost_crossover_gain": lost_crossover_gain,
                "operation": proposal.operation or "",
                "local": proposal.local if proposal.local is not None else "",
                "program_distance": _program_distance(parent_program, proposal.program),
                "changed_rules": (parent_program ^ proposal.program).bit_count(),
                "applied": changed,
                "skipped": proposal.skipped,
                "slots": 1,
                "valid_new": changed and not duplicate,
                "duplicate": duplicate,
                "changed": changed,
                "invalid": False,
                "original_score": parent.score if parent is not None else "",
                "new_score": child.score if child is not None else "",
                "improved": (
                    child is not None
                    and parent is not None
                    and child.score > parent.score
                ),
                "is_best": child.is_best if child is not None else False,
            },
        )


def _program_distance(first: Genome, second: Genome) -> float:
    union = (first | second).bit_count()
    return 0.0 if not union else 1.0 - (first & second).bit_count() / union
