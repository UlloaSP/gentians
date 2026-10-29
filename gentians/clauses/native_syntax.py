"""Reusable buffers for Clingo's native rule builder and formatter.

The returned AST owns its references. Only input arrays are reused; no pointers
to models or Controls survive a callback. Clingo remains the syntax authority.
"""

from collections.abc import Sequence

from clingo import ast
from clingo._internal import _ffi, _handle_error, _lib


def rule_text(head: str, body: Sequence[str]) -> str:
    """Clingo's rule frame around elements that Clingo itself rendered.

    Clingo prints a rule as its head, then ` :- ` and the body elements joined
    by `; `, then a period; a bodyless rule omits the separator. Element syntax,
    including conditions, aggregates and escaping, stays Clingo's output.
    """
    return f"{head} :- {'; '.join(body)}." if body else f"{head}."


class RuleBuilder:
    def __init__(self) -> None:
        self.filename = _ffi.new("char[]", b"<gentians>")
        self.location = _ffi.new("clingo_location_t*", (
            self.filename, self.filename, 1, 1, 1, 1,
        ))
        self.result = _ffi.new("clingo_ast_t**")
        self.body_capacity = 16
        self.body = _ffi.new("clingo_ast_t*[]", self.body_capacity)
        self.text_capacity = 1024
        self.text = _ffi.new("char[]", self.text_capacity)
        self.text_size = _ffi.new("size_t*")

    def rule(self, head: ast.AST, body: Sequence[ast.AST]) -> ast.AST:
        if len(body) > self.body_capacity:
            self.body_capacity = max(len(body), self.body_capacity * 2)
            self.body = _ffi.new("clingo_ast_t*[]", self.body_capacity)
        for index, node in enumerate(body):
            self.body[index] = node._rep
        _handle_error(_lib.clingo_ast_build(
            _lib.clingo_ast_type_rule, self.result, self.location, head._rep,
            self.body, _ffi.cast("size_t", len(body)),
        ))
        return ast.AST(self.result[0])

    def render(self, node: ast.AST) -> str:
        if not _lib.clingo_ast_to_string(node._rep, self.text, self.text_capacity):
            _handle_error(_lib.clingo_ast_to_string_size(node._rep, self.text_size))
            if self.text_size[0] <= self.text_capacity:
                # An error other than insufficient capacity still goes through
                # Clingo's normal diagnostic handling.
                _handle_error(_lib.clingo_ast_to_string(node._rep, self.text, self.text_capacity))
            else:
                self.text_capacity = max(self.text_capacity * 2, self.text_size[0])
                self.text = _ffi.new("char[]", self.text_capacity)
                _handle_error(_lib.clingo_ast_to_string(node._rep, self.text, self.text_capacity))
        return _ffi.string(self.text).decode("utf-8")
