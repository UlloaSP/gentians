import re
from functools import lru_cache

from clingo import ast
from clingo import Control

from .callbacks import CheckSanityRulesCallback, RuleCallback


@lru_cache(maxsize=None)
def _get_atoms_cached(clause: str) -> tuple[str, ...]:
    """
    Get the atoms from a clause.
    """
    r = RuleCallback()
    ast.parse_string(clause, r.process)
    return tuple(r.head + r.body)


def get_atoms(clause: str) -> "list[str]":
    return list(_get_atoms_cached(clause))


@lru_cache(maxsize=None)
def is_unsound(clause: str) -> bool:
    """
    Returns true if the rule is unsafe.
    """
    l = CheckSanityRulesCallback()
    ctl = Control(logger=l.sink)
    ctl.add("base", [], clause)
    try:
        ctl.ground([("base", [])])
    except:
        pass

    return l.unsound_rule


@lru_cache(maxsize=None)
def is_valid_rule(clause: str) -> bool:
    """
    Checks whether a rule is valid:
    - safe and sound rule
    - no two or more equal atoms
    - comparison operators applied to two different variables
    - result of arithmetic operations different from input variables
    TODO: can this be done with an ASP constraint to avoid generating
    invalid rules?
    """

    if is_unsound(clause):
        return False

    comparison_operators = ["<=", ">=", "!=", "==", ">", "<"]
    arithmetic_operators = ["+", "-", "*", "/", "\\"]

    atoms_list: "list[str]" = get_atoms(clause)

    if len(atoms_list) != len(list(set(atoms_list))):
        return False

    for atom in atoms_list:
        if any(op in atom for op in comparison_operators):
            matches = re.findall(r"V\d+", atom)
            v0, v1 = matches
            if v0 == v1:
                return False

        elif any(op in atom for op in arithmetic_operators):
            matches = re.findall(r"V\d+", atom)
            v0, v1, v2 = matches
            # this is ok since the structure of arithmetic operators is
            # fixed to be _ op _ = _
            # v0 and v1 can be the same, V0 + V0 = V1 is valid
            if v0 == v2 or v1 == v2:
                return False

    return True
