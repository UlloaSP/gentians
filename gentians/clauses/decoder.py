import clingo

from .clause_mode import ClauseMode
from .reified_clause import ReifiedClause
from .reified_literal import ReifiedLiteral

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
                    modes[mode_id].binding_positions,
                    literal,
                )
                for mode_id, literal in sorted(mode_choices)
            ),
            tuple(
                tuple(sorted(variables.get((section, slot, argument), ())))
                for argument in range(
                    max(
                        max(modes[mode_id].binding_positions, default=-1) + 1
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
