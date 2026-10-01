"""Learning annotations and substitutions over Clingo's native term syntax."""

import re
from collections.abc import Callable, Iterable, Iterator
from functools import lru_cache
from itertools import product

import clingo
from clingo import ast

from .ast_nodes import BINARY_OPERATORS, LOCATION, UNARY_OPERATORS, binding_term
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
    return ast.Function(LOCATION, "var", [fixed(item) for item in values], False)


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
    return tuple(
        item
        for index, child in enumerate(arguments(term))
        for item in bindings(child, (*path, index))
    )


def constant_types(term: ast.AST) -> frozenset[str]:
    if kind(term) == "constant":
        return frozenset((str(term.arguments[0]),))
    return frozenset(
        item for child in arguments(term) for item in constant_types(child)
    )


def contains_anonymous(term: ast.AST) -> bool:
    return term.ast_type == ast.ASTType.Variable or any(
        map(contains_anonymous, arguments(term))
    )


def contains_arithmetic(term: ast.AST) -> bool:
    return kind(term) in {"arithmetic", "interval"} or any(
        map(contains_arithmetic, arguments(term))
    )


def shape(term: ast.AST) -> tuple[object, ...]:
    term_kind = kind(term)
    if term_kind == "variable":
        return ("variable",)
    if term_kind == "fixed":
        return ("fixed", value(term))
    return term_kind, value(term), tuple(map(shape, arguments(term)))


def transform(term: ast.AST, replace: Callable[[ast.AST], ast.AST | None]) -> ast.AST:
    replacement = replace(term)
    if replacement is not None:
        return replacement
    return with_arguments(
        term, tuple(transform(child, replace) for child in arguments(term))
    )


def concretizations(
    term: ast.AST, constants: dict[str, tuple[str, ...]]
) -> tuple[ast.AST, ...]:
    if kind(term) == "constant":
        return tuple(fixed(item) for item in constants[str(term.arguments[0])])
    return tuple(
        with_arguments(term, children)
        for children in product(
            *(concretizations(child, constants) for child in arguments(term))
        )
    )


def instantiate(term: ast.AST, variables: Iterator[str]) -> ast.AST:
    def substitute(node: ast.AST) -> ast.AST | None:
        if kind(node) == "variable":
            return binding_term(next(variables))
        if kind(node) == "constant":
            raise ValueError(
                "constant placeholder must be concretized before instantiation"
            )
        return None

    return transform(term, substitute)


def validate(term: ast.AST, declaration: str) -> ast.AST:
    """Validate learning annotations without constructing a second syntax tree."""
    term_kind = kind(term)
    if term.ast_type == ast.ASTType.Variable and term.name != "_":
        raise ValueError(f"unsupported arithmetic term: {declaration}")
    if term.ast_type == ast.ASTType.Function:
        if term.external:
            raise ValueError(f"external function terms are unsupported: {declaration}")
        if term.name in {"var", "const"}:
            count = len(term.arguments)
            if (term.name == "var" and count not in {1, 2, 3}) or (
                term.name == "const" and count != 1
            ):
                raise ValueError(f"invalid arithmetic placeholder: {declaration}")
            type_name = str(term.arguments[0])
            validate_type(type_name, declaration)
            if term_kind == "variable":
                metadata = binding(term)
                if metadata.direction not in {"", "input", "output", "any"}:
                    raise ValueError(
                        "variables require input, output, or any direction"
                    )
                if metadata.label and not re.fullmatch(
                    r"[a-z][A-Za-z0-9_]*", metadata.label
                ):
                    raise ValueError(f"invalid variable label: {metadata.label}")
        elif term.name == "not":
            raise ValueError(f"invalid arithmetic placeholder: {declaration}")
    for child in arguments(term):
        validate(child, declaration)
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
