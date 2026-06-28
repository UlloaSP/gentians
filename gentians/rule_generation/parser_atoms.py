import re

from ..console import print_error_and_exit


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
    atom = atom.strip()
    if atom.startswith("not "):
        atom = atom[4:].strip()
    elif atom.startswith("not") and len(atom) > 3 and atom[3].isalpha():
        atom = atom[3:]
    pattern = r"\{?([A-Za-z_]\w*)(?:\((.*)\))?\}?"
    match = re.match(pattern, atom)
    if match:
        function_name = match.group(1)  # Extract function name
        args = match.group(2)  # Extract arguments (if any)
        arguments = split_top_level_args(args) if args else []
        return (function_name, len(arguments))

    print_error_and_exit(f"Error in extract_name_arity: {atom}")
    return (atom, -1)
