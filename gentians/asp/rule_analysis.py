from functools import lru_cache

from clingo import ast

from .callbacks import RuleCallback


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
