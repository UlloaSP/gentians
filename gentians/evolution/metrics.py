from ..hypotheses import Genome
from ..timing import instrumentation, metric_enabled, record_metric
from .individual import Individual
from .operator_types import MutationProposal


def operator_metrics_enabled() -> bool:
    return metric_enabled("operator")


def record_selection(
    strategy: str,
    first: Individual,
    second: Individual,
    population_size: int,
) -> None:
    if not operator_metrics_enabled():
        return
    with instrumentation():
        record_metric(
            "operator",
            {
                "operator": "selection",
                "strategy": strategy,
                "applied": True,
                "skipped": False,
                "slots": 1,
                "parent_a_score": first.score,
                "parent_b_score": second.score,
                "population_size": population_size,
            },
        )


def record_skipped_crossover(strategy: str, population_size: int) -> None:
    if not operator_metrics_enabled():
        return
    with instrumentation():
        record_metric(
            "operator",
            {
                "operator": "crossover",
                "strategy": strategy,
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
                "population_size": population_size,
            },
        )


def record_crossover(
    strategy: str,
    parent: Individual,
    child: Individual,
    genome: Genome,
    *,
    duplicate: bool,
) -> None:
    if not operator_metrics_enabled():
        return
    with instrumentation():
        changed = genome != parent.genome
        record_metric(
            "operator",
            {
                "operator": "crossover",
                "strategy": strategy,
                "applied": changed,
                "skipped": False,
                "slots": 1,
                "valid_new": changed and not duplicate,
                "duplicate": duplicate,
                "changed": changed,
                "original_score": parent.score,
                "new_score": child.score,
                "improved": child.score > parent.score,
                "is_best": child.is_solution,
            },
        )


def record_mutation(
    strategy: str,
    parent_genome: Genome,
    parent: Individual,
    child: Individual | None,
    proposal: MutationProposal,
    *,
    duplicate: bool,
    crossover_strategy: str,
    crossover_improved: bool,
    lost_crossover_gain: bool,
) -> None:
    if not operator_metrics_enabled():
        return
    with instrumentation():
        changed = proposal.genome != parent_genome
        record_metric(
            "operator",
            {
                "operator": "mutation",
                "strategy": strategy,
                "crossover_strategy": crossover_strategy,
                "crossover_improved": crossover_improved,
                "lost_crossover_gain": lost_crossover_gain,
                "operation": proposal.operation or "",
                "local": proposal.local if proposal.local is not None else "",
                "program_distance": _program_distance(
                    parent_genome, proposal.genome
                ),
                "changed_rules": (parent_genome ^ proposal.genome).bit_count(),
                "applied": changed,
                "skipped": proposal.skipped,
                "slots": 1,
                "valid_new": changed and not duplicate,
                "duplicate": duplicate,
                "changed": changed,
                "invalid": False,
                "original_score": parent.score,
                "new_score": child.score if child is not None else "",
                "improved": child is not None and child.score > parent.score,
                "is_best": child.is_solution if child is not None else False,
            },
        )


def record_replacement(
    strategy: str,
    before: list[Individual],
    after: list[Individual],
    candidate: Individual,
) -> None:
    if not operator_metrics_enabled():
        return
    accepted = any(item is candidate for item in after)
    duplicate = any(item.genome == candidate.genome for item in before)
    victim = next(
        (item for item in before if all(item is not kept for kept in after)),
        None,
    )
    with instrumentation():
        record_metric(
            "operator",
            {
                "operator": "replacement",
                "strategy": strategy,
                "applied": True,
                "skipped": False,
                "slots": 1,
                "candidate_score": candidate.score,
                "accepted": accepted,
                "duplicate": duplicate,
                "invalid": False,
                "not_competitive": not accepted and not duplicate,
                "victim_score": victim.score if victim is not None else "",
                "improved_victim": (
                    accepted
                    and victim is not None
                    and candidate.score > victim.score
                ),
                "population_size": len(after),
            },
        )


def _program_distance(first: Genome, second: Genome) -> float:
    union = (first | second).bit_count()
    return 0.0 if not union else 1.0 - (first & second).bit_count() / union
