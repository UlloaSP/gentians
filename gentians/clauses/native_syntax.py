"""Reusable buffers for Clingo's native rule builder and formatter.

The returned AST owns its references. Only input arrays are reused; no pointers
to models or Controls survive a callback. Clingo remains the syntax authority.
"""

from collections.abc import Sequence

from clingo import ast
from clingo._internal import _ffi, _handle_error, _lib

try:
    from . import _records
except ImportError:
    _records = None


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
        self.native = _records
        self.renderer = None
        if _records is not None:
            functions = [int(_ffi.cast("uintptr_t", _ffi.addressof(_lib, name))) for name in (
                "clingo_ast_build", "clingo_ast_to_string", "clingo_ast_to_string_size", "clingo_ast_release",
            )]
            self.renderer = _records.prepare_renderer(functions[0], functions[1], functions[2], functions[3],
                                                       _lib.clingo_ast_type_rule)

    def render_parts(self, parts: tuple[tuple[int, tuple[int, ...]], ...]) -> tuple[str, ...]:
        if self.renderer is None or self.native is None:
            raise RuntimeError("native rule rendering is unavailable")
        return self.native.render_rules(self.renderer, parts)

    def rule(self, head: ast.AST, body: Sequence[ast.AST]) -> ast.AST:
        if len(body) > self.body_capacity:
            self.body_capacity = max(len(body), self.body_capacity * 2)
            self.body = _ffi.new("clingo_ast_t*[]", self.body_capacity)
        for index, node in enumerate(body):
            self.body[index] = node._rep
        _handle_error(_lib.clingo_ast_build(
            _lib.clingo_ast_type_rule, self.result, self.location[0], head._rep,
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
