import re
from functools import lru_cache

from clingo import ast


def split_top_level_args(args: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    pairs = {"(": ")", "[": "]", "{": "}"}
    closing = set(pairs.values())
    stack: list[str] = []
    for index, char in enumerate(args):
        if char in pairs:
            stack.append(pairs[char])
            depth += 1
        elif char in closing and stack and char == stack[-1]:
            stack.pop()
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(args[start:index].strip())
            start = index + 1
    tail = args[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def extract_name_arity(atom: str) -> "tuple[str,int]":
    """
    Extracts name and arity from an atom.
    """
    parsed = parse_atom(atom)
    if parsed is not None:
        function_name, arguments = parsed
        return function_name, len(arguments)
    raise ValueError(f"Error in extract_name_arity: {atom}")


def parse_atom(atom: str) -> tuple[str, list[str]] | None:
    normalized = _normal_atom_text(atom)
    if not normalized or normalized.startswith("#"):
        return None
    match = re.match(r"^([A-Za-z_]\w*)(?:\((.*)\))?$", normalized)
    if match:
        args = match.group(2)
        return match.group(1), split_top_level_args(args) if args else []
    parsed = _parse_atom_cached(normalized)
    if parsed is not None:
        name, arguments = parsed
        return name, list(arguments)
    return None


def _normal_atom_text(atom: str) -> str:
    normalized = atom.strip()
    if normalized.startswith("not "):
        normalized = normalized[4:].strip()
    if normalized.startswith("{") and normalized.endswith("}"):
        normalized = normalized[1:-1].strip()
    return normalized


@lru_cache(maxsize=None)
def _parse_atom_cached(atom: str) -> tuple[str, tuple[str, ...]] | None:
    found: list[tuple[str, tuple[str, ...]]] = []

    def collect(node: ast.AST) -> None:
        if node.ast_type == ast.ASTType.SymbolicAtom:
            symbol = node.symbol
            if symbol.ast_type == ast.ASTType.Function and symbol.name:
                found.append(
                    (
                        str(symbol.name),
                        tuple(
                            str(argument).replace(" ", "")
                            for argument in symbol.arguments
                        ),
                    )
                )
            return
        for key in node.child_keys:
            child = getattr(node, key)
            if isinstance(child, ast.AST):
                collect(child)
            elif isinstance(child, list) or child.__class__.__name__ == "ASTSequence":
                for item in child:
                    if isinstance(item, ast.AST):
                        collect(item)

    try:
        ast.parse_string(f":- {atom}.", collect)
    except RuntimeError:
        return None
    return found[0] if len(found) == 1 else None
