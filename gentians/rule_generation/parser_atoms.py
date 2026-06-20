import re

from ..console import print_error_and_exit


def extract_name_arity(atom: str) -> "tuple[str,int]":
    """
    Extracts name and arity from an atom.
    """
    pattern = r"\{?(\w+)(?:\((.*?)\))?\}?"
    match = re.match(pattern, atom)
    if match:
        function_name = match.group(1)  # Extract function name
        args = match.group(2)  # Extract arguments (if any)
        if args:
            # Split arguments while keeping nested parentheses intact
            arguments = re.findall(r"\w+\(.*?\)|\w+", args)
        else:
            arguments = []

        if function_name.startswith(
            "not"
        ):  # to support literal, space after not is removed
            function_name = function_name[3:]
        return (function_name, len(arguments))

    print_error_and_exit(f"Error in extract_name_arity: {atom}")
    return (atom, -1)
