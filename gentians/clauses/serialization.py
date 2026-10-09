"""Flat structural IPC of recipes; no native pointers, text parser or recursion."""

import io
import pickle
from dataclasses import fields, is_dataclass
from enum import Enum

import clingo
from clingo import ast


def _shape(value):
    if isinstance(value, ast.AST):
        names = value.keys()
        return "ast", (value.ast_type.name, names), [getattr(value, name) for name in names]
    if isinstance(value, clingo.Symbol):
        kind = value.type.name
        if kind == "Number":
            return "symbol", kind, [value.number]
        if kind == "String":
            return "symbol", kind, [value.string]
        if kind == "Function":
            return "symbol", kind, [value.name, value.arguments, value.positive]
        return "extreme", kind, []
    if isinstance(value, ast.ASTSequence):
        return "list", None, list(value)
    if not isinstance(value, type) and is_dataclass(value):
        names = tuple(field.name for field in fields(value) if field.init)
        return "value", (type(value), names), [getattr(value, name) for name in names]
    if isinstance(value, tuple):
        return "tuple", type(value), list(value)
    if isinstance(value, list):
        return "list", None, value
    if isinstance(value, dict):
        return "dict", None, [child for pair in value.items() for child in pair]
    if isinstance(value, frozenset | set):
        return "set", type(value), list(value)
    if value is None or isinstance(value, bool | int | float | str | bytes | type | Enum):
        return "atom", value, []
    raise TypeError(f"unsupported clause recipe value: {type(value).__name__}")


def _flat(value):
    nodes = []
    order = []
    ids = {}
    # Keep fresh native wrappers alive so Python cannot reuse their ids.
    originals = {}
    active = set()
    pending = [(value, None)]
    while pending:
        current, prepared = pending.pop()
        identity = id(current)
        if prepared is None:
            if identity in active:
                raise ValueError("clause recipes must be acyclic")
            if identity in ids:
                continue
            ids[identity] = len(nodes)
            originals[identity] = current
            nodes.append(None)
            active.add(identity)
            kind, metadata, children = _shape(current)
            pending.append((current, (kind, metadata, children)))
            pending.extend((child, None) for child in reversed(children))
        else:
            kind, metadata, children = prepared
            index = ids[identity]
            nodes[index] = kind, metadata, tuple(ids[id(child)] for child in children)
            order.append(index)
            active.remove(identity)
    return nodes, order


def _restore(data):
    nodes, order = data
    values = [None] * len(nodes)
    for index in order:
        kind, metadata, references = nodes[index]
        children = [values[reference] for reference in references]
        if kind == "atom":
            result = metadata
        elif kind in {"ast", "value"}:
            cls, names = metadata
            constructor = getattr(ast, cls) if kind == "ast" else cls
            result = constructor(**dict(zip(names, children, strict=True)))
        elif kind == "symbol":
            result = getattr(clingo, metadata)(*children)
        elif kind == "extreme":
            result = getattr(clingo, metadata)
        elif kind == "tuple":
            result = tuple(children) if metadata is tuple else metadata(*children)
        elif kind == "list":
            result = children
        elif kind == "dict":
            result = dict(zip(children[::2], children[1::2], strict=True))
        elif kind == "set":
            result = metadata(children)
        else:
            raise ValueError(f"unknown clause recipe record: {kind}")
        values[index] = result
    return values[0]


class RecipePickler(pickle.Pickler):
    def dump(self, value):
        super().dump(_flat(value))


def recipe_bytes(value) -> bytes:
    stream = io.BytesIO()
    RecipePickler(stream, protocol=5).dump(value)
    return stream.getvalue()


def read_recipe(data: bytes):
    return _restore(pickle.loads(data))


def read_recipe_file(file):
    return _restore(pickle.load(file))
