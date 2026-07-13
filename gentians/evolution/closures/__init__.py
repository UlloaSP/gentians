import random

from ...rule_generation.program import Program
from ...rule_generation.rule_space import RuleSpace
from .dependency_closure import DependencyClosure
from .no_closure import NoClosure


def create_closure(
    name: str,
    program: Program,
    space: RuleSpace,
    max_clauses: int,
    rng: random.Random,
    fixed_size: bool = False,
):
    if name == "none":
        return NoClosure(program, space, max_clauses, rng, fixed_size)
    if name == "dependency":
        return DependencyClosure(program, space, max_clauses, rng, fixed_size)
    raise ValueError(f"Unknown closure strategy: {name}")
