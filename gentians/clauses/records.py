"""Optional native numeric model copying, with bounded Python block delivery."""

from clingo._internal import _ffi, _lib

from .decoder import _ModelDecoder
from .reified_clause import ReifiedClause
from .reified_literal import ReifiedLiteral

try:
    from . import _records
except ImportError:
    _records = None


class ModelRecords:
    def __init__(self, decoder: _ModelDecoder):
        if _records is None:
            raise RuntimeError("native clause records are unavailable in this installation")
        self.decoder = decoder
        self.native = _records
        address = int(_ffi.cast("uintptr_t", _ffi.addressof(_lib, "clingo_model_symbols")))
        self.state = _records.create(address, decoder.capacity, 128,
                                     [(handle, offset, value) for handle, (offset, value) in decoder.lookup.items()])
        self.plan = _records.prepare_decode(decoder.capacity, tuple(
            (section, slot, decoder.plans[index])
            for index, (section, slot, _offset) in enumerate(decoder.slots)
        ), ReifiedLiteral, ReifiedClause) if decoder.capacity else None

    def push(self, model):
        return self.native.push(self.state, int(_ffi.cast("uintptr_t", model._rep)))

    def flush(self):
        return self.native.flush(self.state)

    def solve(self, control, consume, measure=False):
        addresses = tuple(int(_ffi.cast("uintptr_t", _ffi.addressof(_lib, name))) for name in (
            "clingo_control_solve", "clingo_solve_handle_get", "clingo_solve_handle_close",
            "clingo_error_message", "clingo_set_error",
        ))
        return self.native.solve(self.state, int(_ffi.cast("uintptr_t", control._rep)), addresses, consume, measure)

    def clauses(self, block: bytes):
        if self.plan is None:
            return ()
        return self.native.decode_block(self.plan, block)


def _clause_from_record(state, decoder: _ModelDecoder) -> ReifiedClause:
    head, body = decoder.head, decoder.body
    head.clear()
    body.clear()
    for index, (section, slot, _offset) in enumerate(decoder.slots):
        mode = state[index]
        if mode < 0:
            continue
        variables = tuple(state[position] for position in decoder.plans[index][mode])
        if any(variable < 0 for variable in variables):
            raise RuntimeError("selected numeric literal argument has no variable")
        literal = decoder.literal(section, slot, mode, variables)
        (head if section == "head" else body).append(literal)
    return ReifiedClause(tuple(head), tuple(body))
