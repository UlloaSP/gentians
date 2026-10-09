"""Proved small comparison skeletons for pre-enumeration canonical components."""

from ..language.ir.atom_literal import AtomLiteral
from ..language.ir.comparison_literal import ComparisonLiteral
from .arithmetic_literal import ArithmeticLiteral
from .clause_mode import ClauseMode


# Source witnesses still satisfy every legality/pruning rule. Strict inputs
# have no providers/dependencies and duplicate edges are already excluded, so
# all witnesses in one projected class have identical source cost/metadata.
# Non-comparison occurrences retain their exact slots, modes and bindings.
PROJECTED_COMPONENTS = """
projected_components.
component_edge(Left,Right) :- canonical_strict_literal(_,Left,Right).
component_source(Section,Slot,Mode) :- selected(Section,Slot,Mode), not canonical_strict_mode(Mode,_).
component_binding(Section,Slot,Arg,Var) :- component_source(Section,Slot,_), var_at(Section,Slot,Arg,Var).
#project component_edge/2.
#project component_source/3.
#project component_binding/4.
"""


def comparison_component_facts(modes: list[ClauseMode]) -> list[str]:
    comparisons = []
    for mode in modes:
        literal = mode.literal
        if mode.condition_count:
            return []
        if isinstance(literal, ComparisonLiteral):
            # Removing a duplicate can free recall and enable replacement of
            # <= plus != by a strict literal. That family is deliberately not
            # admitted. Nor may the removed literal bind a variable or label.
            if (mode.section != "body" or not literal.simple
                    or literal.operators not in {("<",), (">",)}
                    or len(mode.bindings) != 2
                    or any(binding.type != "numeric" or binding.direction != "input" or binding.label
                           for binding in mode.bindings)):
                return []
            comparisons.append((mode.id, int(literal.operators == (">",))))
        elif not isinstance(literal, AtomLiteral) and not (
            mode.section == "body" and isinstance(literal, ArithmeticLiteral)
        ):
            return []
    if not comparisons:
        return []
    return ["canonical_components.", *(f"canonical_strict_mode({mode},{swap})." for mode, swap in comparisons)]
