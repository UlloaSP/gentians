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
    arithmetic_operators = ["+", "-", "*", "/"]

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


@lru_cache(maxsize=None)
def _get_duplicated_positions_cached(
    clause: str, wildcard: str
) -> tuple[tuple[tuple[str, ...], ...], ...]:
    """
    Returns the positions with the same atoms:
    :- a(__VAR__),q(__VAR__,__VAR__),q(__VAR__,__VAR__),a(__VAR__),q(__VAR__,__VAR__) gets
    [[['0'], ['5']], [['1', '2'], ['3', '4'], ['6', '7']]]
    """
    atoms_list = get_atoms(
        clause.replace(wildcard, "_")
    )  # replace otherwise error
    uniques = list(set(atoms_list))
    dup_pos: "list[list[list[str]]]" = []
    for el in uniques:
        current_variable_position = 0
        ld: "list[list[str]]" = []
        for atom in atoms_list:
            n_vars = atom.count("_")
            if atom == el:
                # duplicated
                lt: "list[str]" = []
                for nv in range(n_vars):
                    lt.append(str(nv + current_variable_position))
                if len(lt) > 0:
                    ld.append(lt)
            current_variable_position += n_vars
        if len(ld) > 0:
            dup_pos.append(ld)
    return tuple(tuple(tuple(pos) for pos in group) for group in dup_pos)


def get_duplicated_positions(
    clause: str, wildcard: str
) -> "list[list[list[str]]]":
    return [
        [list(position) for position in group]
        for group in _get_duplicated_positions_cached(clause, wildcard)
    ]


@lru_cache(maxsize=None)
def _get_same_atoms_cached(sampled_stub: str, wildcard: str) -> tuple[tuple[str, ...], int]:
    """
    Returns the samei/n atoms for ASP to prune solutions with repeated atoms
    % same2(Id,PosV0,posV1)
    % indica che l'atomo di id ha 2 variabili le cui posizioni sono
    % (0,1) e (2,3)
    same2(0,0,1).
    same2(0,2,3).
    """
    dp = get_duplicated_positions(sampled_stub, wildcard)
    to_add: "list[str]" = []
    max_p = 0
    for index, position_list_list in enumerate(dp):
        if len(position_list_list) > 1:
            for dup_pos in position_list_list:
                s = f"same{len(dup_pos)}({index},{','.join(dup_pos)})."
                to_add.append(s)
                if len(dup_pos) > max_p:
                    max_p = len(dup_pos)
    return tuple(to_add), max_p


def get_same_atoms(sampled_stub: str, wildcard: str) -> "tuple[list[str],int]":
    same_atoms, max_p = _get_same_atoms_cached(sampled_stub, wildcard)
    return list(same_atoms), max_p
