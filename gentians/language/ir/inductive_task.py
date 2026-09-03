from dataclasses import dataclass, field

from clingo import ast

from .aggregate_declaration import AggregateDeclaration
from .example import Example
from .head_declaration import HeadDeclaration
from .mode_declaration import ModeDeclaration
from .operator_declaration import OperatorDeclaration

Signature = tuple[str, int]


@dataclass(slots=True)
class InductiveTask:
    """Parsed inductive task: background ASP, examples, bias, and limits."""

    background: tuple[ast.AST, ...]
    positive_examples: list[Example]
    negative_examples: list[Example]
    language_bias_head: list[HeadDeclaration]
    language_bias_body: list[ModeDeclaration]
    aggregate_modes: list[AggregateDeclaration] = field(default_factory=list)
    arithmetic_modes: list[OperatorDeclaration | ModeDeclaration] = field(
        default_factory=list
    )
    language_bias_condition: list[ModeDeclaration] = field(default_factory=list)
    invented_predicates: tuple[Signature, ...] = ()
    constants: dict[str, tuple[str, ...]] = field(default_factory=dict)
    max_variables: int | None = 3
    max_body_literals: int | None = 3
    max_head_literals: int | None = 1
    max_program_clauses: int | None = 6
    language_bias_aggregate_head: list[ModeDeclaration] = field(default_factory=list)
    language_bias_disjunctive_head: list[ModeDeclaration] = field(default_factory=list)
    min_aggregate_head_literals: int = 1
    bias: tuple[ast.AST, ...] = ()
    metarule_programs: tuple[tuple[ast.AST, ...], ...] = ()
