"""Learning annotations and substitutions over Clingo's native term syntax."""

import re
from collections.abc import Callable, Iterable, Iterator
from functools import lru_cache
from itertools import product

import clingo
from clingo import ast

from .ast_nodes import BINARY_OPERATORS, LOCATION, UNARY_OPERATORS
from .ir.term_binding import TermBinding

_BINARY_NAMES = {value: key for key, value in BINARY_OPERATORS.items()}
_UNARY_NAMES = {value: key for key, value in UNARY_OPERATORS.items()}

# Mode syntax is immutable: substitutions use AST.update(). These bounded
# caches avoid repeated native attribute reads when compiling the same terms.


@lru_cache(maxsize=8192)
def kind(term: ast.AST) -> str:
    match term.ast_type:
        case ast.ASTType.Function:
            if term.name in {"var", "const"}:
                return "variable" if term.name == "var" else "constant"
            if not term.name:
                return "tuple"
            return "function" if term.arguments else "fixed"
        case ast.ASTType.BinaryOperation | ast.ASTType.UnaryOperation:
            return "arithmetic"
        case ast.ASTType.Interval:
            return "interval"
        case ast.ASTType.Pool:
            return "pool"
        case ast.ASTType.Variable:
            return "anonymous"
        case ast.ASTType.SymbolicTerm:
            return "fixed"
    raise ValueError(f"unsupported mode term: {term}")


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


@lru_cache(maxsize=8192)
def arguments(term: ast.AST) -> tuple[ast.AST, ...]:
    if term.ast_type in {ast.ASTType.BinaryOperation, ast.ASTType.Interval}:
        return term.left, term.right
    if term.ast_type == ast.ASTType.UnaryOperation:
        return (term.argument,)
    if term.ast_type == ast.ASTType.Pool or (
        term.ast_type == ast.ASTType.Function and term.name not in {"var", "const"}
    ):
        return tuple(term.arguments)
    return ()


def with_arguments(term: ast.AST, children: tuple[ast.AST, ...]) -> ast.AST:
    if children == arguments(term):
        return term
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


@lru_cache(maxsize=8192)
def binding(term: ast.AST, path: tuple[int, ...] = ()) -> TermBinding:
    values = tuple(str(item) for item in term.arguments)
    return TermBinding(
        path,
        values[0],
        values[1] if len(values) > 1 else "",
        values[2] if len(values) > 2 else "",
    )


@lru_cache(maxsize=8192)
def bindings(term: ast.AST, path: tuple[int, ...] = ()) -> tuple[TermBinding, ...]:
    if kind(term) == "variable":
        return (binding(term, path),)
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
                result.append(binding(node, (*path, *indices, index)))
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


def _postorder(term: ast.AST) -> Iterator[tuple[ast.AST, int]]:
    pending = [(term, iter(arguments(term)))]
    while pending:
        child = next(pending[-1][1], None)
        if child is None:
            node, _children = pending.pop()
            children = arguments(node)
            yield node, len(children)
        else:
            children = arguments(child)
            if children:
                pending.append((child, iter(children)))
            else:
                yield child, 0


@lru_cache(maxsize=8192)
def constant_types(term: ast.AST) -> frozenset[str]:
    return frozenset(
        str(node.arguments[0]) for node in _walk(term) if kind(node) == "constant"
    )


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
    children = arguments(term)
    if not children or not constant_types(term):
        yield term
        return
    if all(kind(child) == "constant" or not constant_types(child) for child in children):
        for concrete in product(*(concretizations(child, constants) for child in children)):
            yield with_arguments(term, concrete)
        return

    # A postorder recipe retains one current value per node, never the product
    # of a nested subtree. Dirty paths reuse the previous combination's nodes.
    values: list[ast.AST] = []
    changing: list[bool] = []
    result: list[int] = []
    leaves: list[int] = []
    choices: list[tuple[ast.AST, ...]] = []
    updates: list[tuple[int, ast.AST, tuple[int, ...]]] = []
    for node, count in _postorder(term):
        indices = tuple(result[-count:]) if count else ()
        if count:
            del result[-count:]
        index = len(values)
        values.append(node)
        if kind(node) == "constant":
            leaves.append(index)
            choices.append(constants[str(node.arguments[0])])
            changing.append(True)
        else:
            changing.append(any(changing[child] for child in indices))
            if changing[-1]:
                updates.append((index, node, indices))
        result.append(index)
    dirty = [False] * len(values)
    for concrete in product(*choices):
        for index, replacement in zip(leaves, concrete, strict=True):
            dirty[index] = values[index] != replacement
            values[index] = replacement
        for index, node, indices in updates:
            dirty[index] = any(dirty[child] for child in indices)
            if dirty[index]:
                values[index] = with_arguments(node, tuple(values[child] for child in indices))
        yield values[result[0]]


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
        term_kind = kind(node)
        if node.ast_type == ast.ASTType.Variable and node.name != "_":
            raise ValueError(f"unsupported arithmetic term: {declaration}")
        if node.ast_type == ast.ASTType.Function:
            if node.external:
                raise ValueError(f"external function terms are unsupported: {declaration}")
            if node.name in {"var", "const"}:
                count = len(node.arguments)
                if (node.name == "var" and count not in {1, 2, 3}) or (
                    node.name == "const" and count != 1
                ):
                    raise ValueError(f"invalid arithmetic placeholder: {declaration}")
                type_name = str(node.arguments[0])
                validate_type(type_name, declaration)
                if term_kind == "variable":
                    metadata = binding(node)
                    if metadata.direction not in {"", "input", "output", "any"}:
                        raise ValueError(
                            "variables require input, output, or any direction"
                        )
                    if metadata.label and not re.fullmatch(
                        r"[a-z][A-Za-z0-9_]*", metadata.label
                    ):
                        raise ValueError(f"invalid variable label: {metadata.label}")
            elif node.name == "not":
                raise ValueError(f"invalid arithmetic placeholder: {declaration}")
    return term


def validate_type(type_name: str, declaration: str) -> None:
    if type_name == "any" or not re.fullmatch(r"[a-z][A-Za-z0-9_]*", type_name):
        raise ValueError(f"invalid mode type in declaration: {declaration}")


def validate_labels(terms: Iterable[ast.AST], context: str) -> None:
    """A declaration-local label must retain its nominal type."""
    labels: dict[str, str] = {}
    for term in terms:
        for item in bindings(term):
            if item.label and labels.setdefault(item.label, item.type) != item.type:
                raise ValueError(
                    f"{context} variable label {item.label} has incompatible types"
                )
