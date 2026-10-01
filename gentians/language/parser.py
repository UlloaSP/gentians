from pathlib import Path

from . import terms as mode_terms
from .asp import parse_program
from .declarations import (
    _get_constant_declaration,
    _get_invented_declaration,
    _get_pos_neg_examples,
)
from .directives import _get_limit
from .ir.atom_literal import AtomLiteral
from .ir.atom_template import AtomTemplate
from .ir.conditional_literal import ConditionalLiteral
from .ir.example import Example
from .ir.head_template import HeadTemplate
from .ir.inductive_task import InductiveTask
from .ir.mode_declaration import ModeDeclaration
from .lexer import Statement, lex
from .modes import (
    _get_body_mode_declaration,
    _get_combinable_head_declarations,
    _get_condition_mode_declarations,
    _get_head_declaration,
)


def parse_file(filename: str) -> InductiveTask:
    path = Path(filename)
    if path.is_dir():
        source = "\n".join(
            (path / name).read_text(encoding="utf-8")
            for name in ("bk.lp", "exs.lp", "bias.lp")
        )
    else:
        source = path.read_text(encoding="utf-8")
    return parse_text(source)


def parse_text(source: str) -> InductiveTask:
    """Parse an inductive task from source text."""
    background_statements: list[Statement] = []
    pe: dict[Example, None] = {}
    ne: dict[Example, None] = {}
    lbh: dict[HeadTemplate, None] = {}
    lbha: dict[ModeDeclaration, None] = {}
    lbhd: dict[ModeDeclaration, None] = {}
    lbb: dict[ModeDeclaration, None] = {}
    lbc: dict[ModeDeclaration, None] = {}
    inventions: list[tuple[int, AtomTemplate]] = []
    constants: dict[str, dict[str, None]] = {}
    limits: dict[str, int | None] = {
        "#maxv": 3,
        "#maxbl": 3,
        "#maxhl": 1,
        "#maxpl": 6,
    }
    min_head_literals = 1
    declared_limits: set[str] = set()
    for statement in lex(source):
        lc = statement.text
        directive = statement.directive

        limit = (
            directive
            if directive in {"#maxv", "#maxbl", "#maxhl", "#maxpl", "#minhl"}
            else None
        )
        if limit is not None:
            if limit in declared_limits:
                raise ValueError(f"duplicate {limit} declaration: {lc}")
            declared_limits.add(limit)
            value = _get_limit(lc, limit, limit in {"#maxv", "#maxbl", "#maxhl"})
            if limit == "#minhl":
                if value is None:
                    raise ValueError(f"invalid #minhl declaration: {lc}")
                min_head_literals = value
            else:
                limits[limit] = value
        elif directive in {
            "#bias",
            "#metarule",
            "#predicate",
            "#modem",
            "#modeedge",
            "#edge",
        }:
            # Retired task directives must fail explicitly, never become BK.
            raise ValueError(
                f"line {statement.line}: {directive} is no longer supported"
            )
        elif directive in {"#modeagg", "#modearith", "#modecmp"}:
            raise ValueError(
                f"line {statement.line}: {directive} was removed; use an explicit #modeb literal"
            )
        elif directive == "#modeha":
            lbha.update(dict.fromkeys(_get_combinable_head_declarations(lc, directive)))
        elif directive == "#modehd":
            lbhd.update(dict.fromkeys(_get_combinable_head_declarations(lc, directive)))
        elif directive == "#modeh":
            lbh[_get_head_declaration(lc)] = None
        elif directive == "#modeb":
            lbb[_get_body_mode_declaration(lc)] = None
        elif directive == "#pos":
            res = _get_pos_neg_examples(lc)
            pe[Example.parse(res, True, statement.line)] = None
        elif directive == "#neg":
            res = _get_pos_neg_examples(lc)
            ne[Example.parse(res, False, statement.line)] = None
        elif directive == "#modec":
            lbc.update(dict.fromkeys(_get_condition_mode_declarations(lc)))
        elif directive == "#invent":
            invention = _get_invented_declaration(lc)
            if any(existing[1] == invention[1] for existing in inventions):
                raise ValueError(f"duplicate #invent declaration: {lc}")
            inventions.append(invention)
        elif directive == "#constant":
            type_name, value = _get_constant_declaration(lc)
            constants.setdefault(type_name, {})[value] = None
        else:
            background_statements.append(statement)

    invented_predicates = tuple(atom.signature for _recall, atom in inventions)
    explicit = (
        {
            literal.atom.signature
            for head in lbh
            for literal in head.conclusions
            if isinstance(literal, AtomLiteral)
        }
        | {
            mode.literal.atom.signature
            for mode in (*lbha, *lbhd)
            if isinstance(mode.literal, AtomLiteral)
        }
        | {
            literal.atom.signature
            for mode in lbb
            for literal in (
                (mode.literal.conclusion,)
                if isinstance(mode.literal, ConditionalLiteral)
                else (mode.literal,)
            )
            if isinstance(literal, AtomLiteral)
        }
    )

    overlap = explicit.intersection(invented_predicates)
    if overlap:
        raise ValueError(
            "invented predicates must not also use #modeh/#modeha/#modeb: "
            f"{sorted(overlap)}"
        )
    for recall, atom in inventions:
        lbh[HeadTemplate.normal(AtomLiteral(atom))] = None
        lbb[ModeDeclaration(recall, AtomLiteral(atom))] = None
    constant_types = {
        type_name
        for terms in (
            *(head.arguments for head in lbh),
            *(mode.literal.arguments for mode in (*lbha, *lbhd, *lbc, *lbb)),
        )
        for argument in terms
        for type_name in mode_terms.constant_types(argument)
    }
    missing_constants = constant_types - constants.keys()
    if missing_constants:
        raise ValueError(
            f"constant mode types require #constant declarations: {sorted(missing_constants)}"
        )
    max_head_literals = limits["#maxhl"]
    if (
        (lbha or lbhd)
        and max_head_literals is not None
        and min_head_literals > max_head_literals
    ):
        raise ValueError("#minhl cannot exceed #maxhl")
    return InductiveTask(
        background=parse_program(_background_source(background_statements)),
        positive_examples=list(pe),
        negative_examples=list(ne),
        language_bias_head=list(lbh),
        language_bias_body=list(lbb),
        language_bias_condition=list(lbc),
        invented_predicates=invented_predicates,
        constants={name: tuple(values) for name, values in constants.items()},
        max_variables=limits["#maxv"],
        max_body_literals=limits["#maxbl"],
        max_head_literals=max_head_literals,
        max_program_clauses=limits["#maxpl"],
        language_bias_aggregate_head=list(lbha),
        language_bias_disjunctive_head=list(lbhd),
        min_aggregate_head_literals=min_head_literals,
    )


def _background_source(statements: list[Statement]) -> str:
    parts: list[str] = []
    line = 1
    for statement in statements:
        parts.append("\n" * max(0, statement.line - line))
        parts.append(statement.text)
        line = statement.line + statement.text.count("\n")
    return "".join(parts)
