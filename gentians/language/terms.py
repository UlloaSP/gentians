"""Learning annotations and substitutions over Clingo's native term syntax."""

import re
from collections import OrderedDict
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

import clingo
from clingo import ast

from .ast_nodes import BINARY_OPERATORS, LOCATION, UNARY_OPERATORS
from .grammar import SourceError
from .ir.term_binding import TermBinding

_BINARY_NAMES = {value: key for key, value in BINARY_OPERATORS.items()}
_UNARY_NAMES = {value: key for key, value in UNARY_OPERATORS.items()}

@dataclass(slots=True)
class _Metadata:
    node: ast.AST
    node_type: ast.ASTType
    name: str
    kind: str | None = None
    arguments: tuple[ast.AST, ...] | None = None
    binding: TermBinding | None = None
    bindings: tuple[TermBinding, ...] | None = None
    constant_types: frozenset[str] | None = None


# Native nodes cannot be weakly referenced. One bounded identity cache owns all
# metadata; parsing uses a temporary cache that releases its nodes on exit.
_recent: OrderedDict[int, _Metadata] = OrderedDict()
_active: ContextVar[OrderedDict[int, _Metadata] | None] = ContextVar("term_metadata", default=None)
_NO_CONSTANTS: frozenset[str] = frozenset()


@contextmanager
def metadata_scope() -> Iterator[None]:
    if _active.get() is not None:
        yield
        return
    token = _active.set(OrderedDict())
    try:
        yield
    finally:
        _active.reset(token)


def _metadata(term: ast.AST) -> _Metadata:
    cache = _active.get()
    limit = 8192 if cache is not None else 1024
    if cache is None:
        cache = _recent
    identity = id(term)
    if (cached := cache.get(identity)) is not None:
        return cached
    if len(cache) == limit:
        cache.popitem(last=False)
    cached = _recent.get(identity) if cache is not _recent else None
    if cached is None:
        node_type = term.ast_type
        cached = _Metadata(term, node_type, str(term.name) if node_type == ast.ASTType.Function else "")
    cache[identity] = cached
    return cached


def kind(term: ast.AST) -> str:
    cached = _metadata(term)
    if cached.kind is not None:
        return cached.kind
    match cached.node_type:
        case ast.ASTType.Function:
            if cached.name in {"var", "const"}:
                result = "variable" if cached.name == "var" else "constant"
            elif not cached.name:
                result = "tuple"
            else:
                result = "function" if term.arguments else "fixed"
        case ast.ASTType.BinaryOperation | ast.ASTType.UnaryOperation:
            result = "arithmetic"
        case ast.ASTType.Interval:
            result = "interval"
        case ast.ASTType.Pool:
            result = "pool"
        case ast.ASTType.Variable:
            result = "anonymous"
        case ast.ASTType.SymbolicTerm:
            result = "fixed"
        case _:
            raise ValueError(f"unsupported mode term: {term}")
    cached.kind = result
    return result


def value(term: ast.AST) -> str:
    if term.ast_type == ast.ASTType.BinaryOperation:
        return _BINARY_NAMES[term.operator_type]
    if term.ast_type == ast.ASTType.UnaryOperation:
        return _UNARY_NAMES[term.operator_type]
    if term.ast_type == ast.ASTType.Interval:
        return ".."
    if term.ast_type == ast.ASTType.Function and kind(term) == "function":
        return str(term.name)
    return str(term) if kind(term) == "fixed" else ""


def arguments(term: ast.AST) -> tuple[ast.AST, ...]:
    cached = _metadata(term)
    if cached.arguments is not None:
        return cached.arguments
    if cached.node_type in {ast.ASTType.BinaryOperation, ast.ASTType.Interval}:
        result = term.left, term.right
    elif cached.node_type == ast.ASTType.UnaryOperation:
        result = (term.argument,)
    elif cached.node_type == ast.ASTType.Pool or (
        cached.node_type == ast.ASTType.Function and cached.name not in {"var", "const"}
    ):
        result = tuple(term.arguments)
    else:
        result = ()
    cached.arguments = result
    return result


def with_arguments(term: ast.AST, children: tuple[ast.AST, ...]) -> ast.AST:
    if children == arguments(term):
        return term
    return _replace_arguments(term, children)


def _replace_arguments(term: ast.AST, children: tuple[ast.AST, ...]) -> ast.AST:
    """Rebuild a term whose children are already known to have changed."""
    if term.ast_type in {ast.ASTType.BinaryOperation, ast.ASTType.Interval}:
        return term.update(left=children[0], right=children[1])
    if term.ast_type == ast.ASTType.UnaryOperation:
        return term.update(argument=children[0])
    return term.update(arguments=children)


def variable(type_name: str, direction: str, label: str = "") -> ast.AST:
    values = (
        (type_name, direction, label)
        if label
        else (type_name, direction)
        if direction
        else (type_name,)
    )
    return ast.Function(
        LOCATION, "var",
        [ast.SymbolicTerm(LOCATION, clingo.Function(item)) for item in values], False,
    )


def constant(type_name: str) -> ast.AST:
    return ast.Function(LOCATION, "const", [fixed(type_name)], False)


def fixed(text: str) -> ast.AST:
    return ast.SymbolicTerm(LOCATION, clingo.parse_term(text))


def binding(term: ast.AST, path: tuple[int, ...] = ()) -> TermBinding:
    cached = _metadata(term)
    if cached.binding is None:
        values = tuple(str(item) for item in term.arguments)
        cached.binding = TermBinding(
            (), values[0], values[1] if len(values) > 1 else "",
            values[2] if len(values) > 2 else "",
        )
    item = cached.binding
    return TermBinding(path, item.type, item.direction, item.label) if path else item


def bindings(term: ast.AST, path: tuple[int, ...] = ()) -> tuple[TermBinding, ...]:
    cached = _metadata(term)
    if cached.bindings is None:
        result = _bindings(term)
        cached = _metadata(term)  # A large traversal may have evicted its root.
        cached.bindings = result
    if not path:
        return cached.bindings
    return tuple(TermBinding(path + item.path, item.type, item.direction, item.label) for item in cached.bindings)


def _bindings(term: ast.AST) -> tuple[TermBinding, ...]:
    if kind(term) == "variable":
        return (binding(term),)
    result: list[TermBinding] = []
    pending = [iter(enumerate(arguments(term)))]
    indices: list[int] = []
    while pending:
        child = next(pending[-1], None)
        if child is None:
            pending.pop()
            if indices:
                indices.pop()
        else:
            index, node = child
            if kind(node) == "variable":
                result.append(binding(node, (*indices, index)))
            elif children := arguments(node):
                indices.append(index)
                pending.append(iter(enumerate(children)))
    return tuple(result)


def _walk(term: ast.AST) -> Iterator[ast.AST]:
    pending = [term]
    while pending:
        node = pending.pop()
        yield node
        pending.extend(reversed(arguments(node)))


def _postorder(term: ast.AST, *, prune_fixed: bool = False) -> Iterator[tuple[ast.AST, int]]:
    if prune_fixed and not constant_types(term):
        yield term, 0
        return
    pending = [(term, iter(arguments(term)))]
    while pending:
        child = next(pending[-1][1], None)
        if child is None:
            node, _children = pending.pop()
            children = arguments(node)
            yield node, len(children)
        else:
            children = () if prune_fixed and not constant_types(child) else arguments(child)
            if children:
                pending.append((child, iter(children)))
            else:
                yield child, 0


def constant_types(term: ast.AST) -> frozenset[str]:
    cached = _metadata(term)
    if cached.constant_types is not None:
        return cached.constant_types
    result: list[frozenset[str]] = []
    for node, count in _postorder(term):
        children = result[-count:] if count else []
        if count:
            del result[-count:]
        types = (
            frozenset((str(node.arguments[0]),)) if kind(node) == "constant"
            else children[0] if count == 1
            else _NO_CONSTANTS.union(*children) if any(children)
            else _NO_CONSTANTS
        )
        _metadata(node).constant_types = types
        result.append(types)
    cached.constant_types = result[0]
    return result[0]


def contains_anonymous(term: ast.AST) -> bool:
    return any(node.ast_type == ast.ASTType.Variable for node in _walk(term))


def contains_arithmetic(term: ast.AST) -> bool:
    return any(kind(node) in {"arithmetic", "interval"} for node in _walk(term))


def shape(term: ast.AST) -> tuple[object, ...]:
    term_kind = kind(term)
    if term_kind == "variable":
        return ("variable",)
    if term_kind == "fixed":
        return ("fixed", value(term))
    result: list[tuple[object, ...]] = []
    for node, count in _postorder(term):
        children = tuple(result[-count:]) if count else ()
        if count:
            del result[-count:]
        node_kind = kind(node)
        if node_kind == "variable":
            result.append(("variable",))
        elif node_kind == "fixed" or (
            node_kind in {"function", "tuple"}
            or node.ast_type == ast.ASTType.UnaryOperation
            and node.operator_type == ast.UnaryOperator.Minus
        ) and all(child[0] == "fixed" for child in children):
            # Direct syntax and #constant values keep the same ground shape.
            result.append(("fixed", str(node)))
        else:
            result.append((node_kind, value(node), children))
    return result[0]


def transform(term: ast.AST, replace: Callable[[ast.AST], ast.AST | None]) -> ast.AST:
    pending = [(term, False)]
    result: list[ast.AST] = []
    while pending:
        node, visited = pending.pop()
        if not visited and (replacement := replace(node)) is not None:
            result.append(replacement)
            continue
        children = arguments(node)
        if not children:
            result.append(node)
        elif visited:
            count = len(children)
            concrete = tuple(result[-count:])
            del result[-count:]
            result.append(with_arguments(node, concrete))
        else:
            pending.append((node, True))
            pending.extend((child, False) for child in reversed(children))
    return result[0]


def concretizations(
    term: ast.AST, constants: dict[str, tuple[ast.AST, ...]]
) -> Iterator[ast.AST]:
    if kind(term) == "constant":
        yield from constants[str(term.arguments[0])]
        return
    if not constant_types(term):
        yield term
        return
    for concrete in concretize_terms((term,), constants):
        yield concrete[0]


def concretize_terms(
    terms: tuple[ast.AST, ...], constants: dict[str, tuple[ast.AST, ...]]
) -> Iterator[tuple[ast.AST, ...]]:
    """Expand a term forest over declared constant domains, never subtree pools."""
    has_constants = False
    for term in terms:
        has_constants |= bool(constant_types(term))
    if not has_constants:
        yield terms
        return
    # Recipe metadata lives only during preparation, never across a yield.
    values: list[ast.AST] = []
    parents: list[int | None] = []
    result: list[int] = []
    leaves: list[int] = []
    choices: list[tuple[ast.AST, ...]] = []
    updates: dict[int, tuple[ast.AST, tuple[int, ...]]] = {}
    with metadata_scope():
        for term in terms:
            for node, count in _postorder(term, prune_fixed=True):
                indices = tuple(result[-count:]) if count else ()
                if count:
                    del result[-count:]
                index = len(values)
                values.append(node)
                parents.append(None)
                if kind(node) == "constant":
                    leaves.append(index)
                    choices.append(constants[str(node.arguments[0])])
                elif count:
                    updates[index] = node, indices
                    for child in indices:
                        parents[child] = index
                result.append(index)
    if not choices:
        yield terms
        return
    if any(not domain for domain in choices):
        return
    positions = [0] * len(choices)
    changed = range(len(choices))
    while True:
        dirty: set[int] = set()
        for position in changed:
            index = leaves[position]
            replacement = choices[position][positions[position]]
            if values[index] == replacement:
                continue
            values[index] = replacement
            ancestor: int | None = index
            while ancestor is not None and ancestor not in dirty:
                dirty.add(ancestor)
                ancestor = parents[ancestor]
        for index in sorted(dirty):
            if (recipe := updates.get(index)) is not None:
                node, indices = recipe
                values[index] = _replace_arguments(node, tuple(values[child] for child in indices))
        yield tuple(values[index] for index in result)
        # The rightmost domain advances first, matching itertools.product.
        for position in range(len(positions) - 1, -1, -1):
            positions[position] += 1
            if positions[position] < len(choices[position]):
                changed = range(position, len(positions))
                break
            positions[position] = 0
        else:
            return


def replace_guard_term(guard: ast.AST | None, terms: Iterator[ast.AST]) -> ast.AST | None:
    if guard is None:
        return None
    term = next(terms)
    return guard if term == guard.term else guard.update(term=term)


def instantiate(term: ast.AST, variables: Iterator[ast.AST]) -> ast.AST:
    term_kind = kind(term)
    if term_kind == "variable":
        return next(variables)
    if term_kind == "constant":
        raise ValueError("constant placeholder must be concretized before instantiation")
    children = arguments(term)
    if not children:
        return term
    pending: list[tuple[ast.AST, tuple[ast.AST, ...], list[ast.AST]]] = [(term, children, [])]
    node = children[0]
    while True:
        node_kind = kind(node)
        if node_kind == "variable":
            concrete = next(variables)
        elif node_kind == "constant":
            raise ValueError(
                "constant placeholder must be concretized before instantiation"
            )
        elif children := arguments(node):
            pending.append((node, children, []))
            node = children[0]
            continue
        else:
            concrete = node
        while pending:
            parent, children, completed = pending[-1]
            completed.append(concrete)
            if len(completed) < len(children):
                node = children[len(completed)]
                break
            pending.pop()
            concrete = with_arguments(parent, tuple(completed))
        else:
            return concrete


def instantiate_guard(guard: ast.AST | None, variables: Iterator[ast.AST]) -> ast.AST | None:
    if guard is None:
        return None
    original = guard.term
    term = instantiate(original, variables)
    return guard if term == original else guard.update(term=term)


def validate(term: ast.AST, declaration: str) -> ast.AST:
    """Validate learning annotations without constructing a second syntax tree."""
    for node in _walk(term):
        metadata = _metadata(node)
        term_kind = kind(node)
        if metadata.node_type == ast.ASTType.Variable and node.name != "_":
            raise SourceError.at_node(node, f"unsupported arithmetic term: {declaration}")
        if metadata.node_type == ast.ASTType.Function:
            if node.external:
                raise SourceError.at_node(node, f"external function terms are unsupported: {declaration}")
            if metadata.name in {"var", "const"}:
                count = len(node.arguments)
                if (metadata.name == "var" and count not in {1, 2, 3}) or (
                    metadata.name == "const" and count != 1
                ):
                    raise SourceError.at_node(node, f"invalid arithmetic placeholder: {declaration}")
                type_name = str(node.arguments[0])
                try:
                    validate_type(type_name, declaration)
                except ValueError as error:
                    raise SourceError.at_node(node.arguments[0], str(error)) from None
                if term_kind == "variable":
                    metadata = binding(node)
                    if metadata.direction not in {"", "input", "output", "any"}:
                        raise SourceError.at_node(node.arguments[1],
                            "variables require input, output, or any direction"
                        )
                    if metadata.label and not re.fullmatch(
                        r"[a-z][A-Za-z0-9_]*", metadata.label
                    ):
                        raise SourceError.at_node(node.arguments[2], f"invalid variable label: {metadata.label}")
            elif metadata.name == "not":
                raise SourceError.at_node(node, f"invalid arithmetic placeholder: {declaration}")
    return term


def validate_type(type_name: str, declaration: str) -> None:
    if type_name == "any" or not re.fullmatch(r"[a-z][A-Za-z0-9_]*", type_name):
        raise ValueError(f"invalid mode type in declaration: {declaration}")


def validate_labels(terms: Iterable[ast.AST], context: str) -> None:
    """A declaration-local label must retain its nominal type."""
    labels: dict[str, str] = {}
    for term in terms:
        for node in _walk(term):
            if kind(node) != "variable":
                continue
            item = binding(node)
            if item.label and labels.setdefault(item.label, item.type) != item.type:
                raise SourceError.at_node(node.arguments[2],
                    f"{context} variable label {item.label} has incompatible types"
                )
