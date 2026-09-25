from ..hypotheses import Genome
from ..evaluation.result import EvaluationResult
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
    genome: Genome,
    *,
    duplicate: bool,
    result: EvaluationResult | None = None,
) -> None:
    """Record one crossover against its best parent.

    The child is scored only when some evaluation already covered it, such as
    mutation classification; otherwise its score stays unknown.
    """
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
                "new_score": result.score if result is not None else "",
                "improved": result is not None and result.score > parent.score,
            },
        )


def record_mutation(
    strategy: str,
    parent_genome: Genome,
    proposal: MutationProposal,
    *,
    duplicate: bool,
    before: EvaluationResult | None = None,
    after: EvaluationResult | None = None,
    crossover_strategy: str = "",
    crossover_parent_score: float | None = None,
) -> None:
    """Record one mutation of a crossover child.

    Scores need both the crossover child and the mutated program evaluated.
    A crossover gain is a child scored above its best parent; mutation loses
    it when the mutated program scores below that child.
    """
    if not operator_metrics_enabled():
        return
    with instrumentation():
        changed = proposal.genome != parent_genome
        scores = {}
        if before is not None and after is not None:
            scores = {
                "original_score": before.score,
                "new_score": after.score,
                "improved": after.score > before.score,
            }
        crossover_improved = (
            before is not None
            and crossover_parent_score is not None
            and before.score > crossover_parent_score
        )
        effects = {}
        if before is not None and after is not None:
            pos_before, neg_before = before.behavior
            pos_after, neg_after = after.behavior
            effects = {
                "positive_recovered": (pos_after & ~pos_before).bit_count(),
                "positive_lost": (pos_before & ~pos_after).bit_count(),
                "negative_removed": (neg_before & ~neg_after).bit_count(),
                "negative_introduced": (neg_after & ~neg_before).bit_count(),
            }
        record_metric(
            "operator",
            {
                "operator": "mutation",
                "strategy": strategy,
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
                "semantic_effect_known": bool(effects),
                **effects,
                **scores,
                "crossover_strategy": crossover_strategy,
                "crossover_improved": crossover_improved,
                "lost_crossover_gain": (
                    crossover_improved and after is not None and before is not None
                    and after.score < before.score
                ),
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
