from ..language.ir.atom_literal import AtomLiteral
from ..language.ir.inductive_task import InductiveTask
from .analysis.properties import ClosedWorldProperties
from .clause_mode import ClauseMode
from .mode_facts import compile_mode_facts, predicate_ids
from .property_facts import compile_property_facts


def _facts(
    task: InductiveTask,
    modes: list[ClauseMode],
    properties: ClosedWorldProperties,
    max_variables: int,
    max_head_literals: int,
    max_body_literals: int,
    *,
    numeric_domain: set[int],
) -> str:
    identifiers = predicate_ids(modes)
    structured_predicates = {
        mode.literal.atom.signature
        for mode in modes
        if isinstance(mode.literal, AtomLiteral)
        and any(term.kind in {"function", "tuple"} for term in mode.literal.atom.terms)
    }
    parts = [
        f"max_body({max_body_literals}).",
        f"max_vars({max_variables}).",
    ]
    parts.extend(
        f"condition_group_recall({group},{max_body_literals if mode.recall < 0 else mode.recall})."
        for group, mode in enumerate(task.language_bias_condition)
    )
    all_positive = bool(numeric_domain) and all(value > 0 for value in numeric_domain)
    if numeric_domain and all(value >= 0 for value in numeric_domain) and not all_positive:
        parts.append("numeric_domain_nonnegative.")
    if all_positive:
        parts.append("numeric_domain_positive.")
    parts.extend(
        compile_property_facts(
            properties,
            {
                predicate: identifier
                for predicate, identifier in identifiers.items()
                if predicate not in structured_predicates
            },
        )
    )
    for predicate, predicate_id in identifiers.items():
        complement = (f"-{predicate[0]}", predicate[1])
        complement_id = identifiers.get(complement)
        if not predicate[0].startswith("-") and complement_id is not None:
            parts.append(f"strong_complement_pred({predicate_id},{complement_id}).")
    parts.extend(
        f"invented_pred({identifiers[predicate]},{layer})."
        for layer, predicate in enumerate(task.invented_predicates)
    )
    parts.extend(
        compile_mode_facts(
            modes,
            identifiers,
            max_head_literals,
            max_body_literals,
        )
    )
    return "\n".join(parts)
