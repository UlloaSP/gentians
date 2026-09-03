
import clingo

from ..language.ir.atom_literal import AtomLiteral
from .clause_mode import ClauseMode
from .reified_clause import ReifiedClause
from .reified_literal import ReifiedLiteral
from .mode_compiler import _binding_positions

_ValueLiteral = tuple[int, int]
_ModeLiteral = tuple[int, tuple[int, ...], int]
_ModelSlot = tuple[
    str,
    int,
    tuple[_ModeLiteral, ...],
    tuple[tuple[_ValueLiteral, ...], ...],
]

def _model_literal_index(
    atoms: clingo.SymbolicAtoms,
    modes: dict[int, ClauseMode],
) -> tuple[_ModelSlot, ...]:
    selected: dict[tuple[str, int], list[tuple[int, int]]] = {}
    variables: dict[tuple[str, int, int], list[tuple[int, int]]] = {}
    for atom in atoms.by_signature("selected", 3):
        section, slot, mode = atom.symbol.arguments
        selected.setdefault((section.name, slot.number), []).append(
            (mode.number, atom.literal)
        )
    for atom in atoms.by_signature("var_at", 4):
        section, slot, argument, variable = atom.symbol.arguments
        variables.setdefault((section.name, slot.number, argument.number), []).append(
            (variable.number, atom.literal)
        )
    return tuple(
        (
            section,
            slot,
            tuple(
                (
                    mode_id,
                    _binding_positions(modes[mode_id]),
                    literal,
                )
                for mode_id, literal in sorted(mode_choices)
            ),
            tuple(
                tuple(sorted(variables.get((section, slot, argument), ())))
                for argument in range(
                    max(
                        max(_binding_positions(modes[mode_id]), default=-1) + 1
                        for mode_id, _literal in mode_choices
                    )
                )
            ),
        )
        for (section, slot), mode_choices in sorted(selected.items())
    )


def _clause_from_model(
    model: clingo.Model,
    model_index: tuple[_ModelSlot, ...],
) -> ReifiedClause:
    is_true = model.is_true
    head: list[ReifiedLiteral] = []
    body: list[ReifiedLiteral] = []
    current_section = ""
    minimum_mode = -1
    section_empty = False
    for section, slot, mode_choices, argument_choices in model_index:
        if section != current_section:
            current_section = section
            minimum_mode = -1
            section_empty = False
        if section_empty:
            continue
        mode_id = None
        variable_positions: tuple[int, ...] = ()
        for candidate_mode, candidate_positions, program_literal in mode_choices:
            if candidate_mode < minimum_mode:
                continue
            if is_true(program_literal):
                mode_id = candidate_mode
                variable_positions = candidate_positions
                break
        if mode_id is None:
            section_empty = True
            continue
        minimum_mode = mode_id
        variables: list[int] = []
        for argument in variable_positions:
            choices = argument_choices[argument]
            for variable, program_literal in choices:
                if is_true(program_literal):
                    variables.append(variable)
                    break
            else:
                raise RuntimeError("selected literal argument has no variable")
        literal = ReifiedLiteral(section, slot, mode_id, tuple(variables))
        (head if section == "head" else body).append(literal)
    return ReifiedClause(head=tuple(head), body=tuple(body))


def _theta_reduced(
    clause: ReifiedClause,
    modes: dict[int, ClauseMode],
) -> bool:
    """Reject normal clauses θ-equivalent to one of their proper subclauses."""
    literals = (*clause.head, *clause.body)
    if any(
        not isinstance(modes[literal.mode_id].literal, AtomLiteral)
        for literal in literals
    ):
        return True
    signatures = tuple((literal.section, literal.mode_id) for literal in literals)
    repeated = {
        signature for signature in signatures if signatures.count(signature) > 1
    }
    if not repeated:
        return True
    return not any(
        _theta_subsumes(literals, literals[:index] + literals[index + 1 :])
        for index in range(len(literals))
        if signatures[index] in repeated
    )


def _theta_subsumes(
    source: tuple[ReifiedLiteral, ...],
    target: tuple[ReifiedLiteral, ...],
) -> bool:
    candidates = {
        literal: tuple(
            candidate
            for candidate in target
            if (candidate.section, candidate.mode_id)
            == (literal.section, literal.mode_id)
        )
        for literal in source
    }
    if any(not matches for matches in candidates.values()):
        return False
    ordered = sorted(source, key=lambda literal: len(candidates[literal]))

    def match(index: int, substitution: dict[int, int]) -> bool:
        if index == len(ordered):
            return True
        literal = ordered[index]
        for candidate in candidates[literal]:
            extended = substitution.copy()
            if all(
                extended.setdefault(variable, target_variable) == target_variable
                for variable, target_variable in zip(
                    literal.variables, candidate.variables, strict=True
                )
            ) and match(index + 1, extended):
                return True
        return False

    return match(0, {})
