import clingo
from clingo._internal import _ffi, _lib

from .clause_mode import ClauseMode
from .reified_clause import ReifiedClause
from .reified_literal import ReifiedLiteral


class _ModelDecoder:
    """Prepared bindings and one reusable shown-symbol buffer for a Control.

    The metaprogram displays only selected/3 and var_at/4. Handles are opaque,
    process-local keys; every conversion to slot/binding metadata happens here.
    Use sequentially while the model is valid. Incremental generation disables
    cleanup so these grounded symbols remain valid across size assumptions.
    """

    def __init__(self, atoms: clingo.SymbolicAtoms, modes: dict[int, ClauseMode]) -> None:
        selected: dict[tuple[str, int], list[tuple[int, int]]] = {}
        for atom in atoms.by_signature("selected", 3):
            symbol = atom.symbol
            section, slot, mode = symbol.arguments
            selected.setdefault((section.name, slot.number), []).append((mode.number, symbol._rep))
        self.bindings = {mode_id: mode.binding_positions for mode_id, mode in modes.items()}
        slot_ids = {slot: index for index, slot in enumerate(sorted(selected))}
        slots = []
        self.lookup: dict[int, tuple[int, int]] = {}
        offset = len(slot_ids)
        for (section, slot), index in slot_ids.items():
            choices = selected[section, slot]
            slots.append((section, slot, offset))
            for mode, handle in choices:
                self.lookup[handle] = index, mode
            offset += max(max(self.bindings[mode], default=-1) + 1 for mode, _ in choices)
        self.slots = tuple(slots)
        for atom in atoms.by_signature("var_at", 4):
            symbol = atom.symbol
            section, slot, argument, variable = symbol.arguments
            self.lookup[symbol._rep] = (
                self.slots[slot_ids[section.name, slot.number]][2] + argument.number,
                variable.number,
            )
        if 0 in self.lookup:
            raise ValueError("The decoder output contains the reserved zero handle")
        self.capacity = offset
        self.buffer = _ffi.new("clingo_symbol_t[]", self.capacity)
        self.buffer_bytes = _ffi.buffer(self.buffer)
        self.zero_bytes = bytes(len(self.buffer_bytes))


def _clause_from_model(model: clingo.Model, decoder: _ModelDecoder) -> ReifiedClause:
    # Clingo accepts an oversized buffer and writes the actual output prefix.
    # Clearing its stale suffix plus the verified nonzero handles avoids the
    # separate size call, which otherwise repeats the native output scan.
    decoder.buffer_bytes[:] = decoder.zero_bytes
    if not _lib.clingo_model_symbols(
        model._rep, _lib.clingo_show_type_shown, decoder.buffer, decoder.capacity,
    ):
        raise RuntimeError("clingo could not read shown clause symbols")
    state: list[int | None] = [None] * decoder.capacity
    for handle in decoder.buffer:
        if handle == 0:
            break
        offset, value = decoder.lookup[handle]
        state[offset] = value
    head: list[ReifiedLiteral] = []
    body: list[ReifiedLiteral] = []
    for index, (section, slot, offset) in enumerate(decoder.slots):
        mode = state[index]
        if mode is None:
            continue
        variables: list[int] = []
        for position in decoder.bindings[mode]:
            variable = state[offset + position]
            if variable is None:
                raise RuntimeError("selected literal argument has no variable")
            variables.append(variable)
        literal = ReifiedLiteral(section, slot, mode, tuple(variables))
        (head if section == "head" else body).append(literal)
    return ReifiedClause(tuple(head), tuple(body))
