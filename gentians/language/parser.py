from bisect import bisect_right
from pathlib import Path

from clingo import ast

from . import terms as mode_terms
from .asp import parse_program
from .declarations import (
    _get_constant_declaration,
    _get_invented_declaration,
    _get_pos_neg_examples,
)
from .directives import _get_limit
from .grammar import SourceError
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
    paths = [path / name for name in ("bk.lp", "exs.lp", "bias.lp")] if path.is_dir() else [path]
    sources = [item.read_text(encoding="utf-8") for item in paths]
    starts = [1]
    for source in sources[:-1]:
        starts.append(starts[-1] + source.count("\n") + 1)
    try:
        return parse_text("\n".join(sources))
    except SourceError as error:
        def origin(line: int) -> str:
            index = bisect_right(starts, line) - 1
            return f"{paths[index]}:line {line - starts[index] + 1}"

        related = (
            f" (related declaration at {origin(error.related_line)})"
            if error.related_line else ""
        )
        raise ValueError(f"{origin(error.line)}: {error.message}{related}") from None


def parse_text(source: str) -> InductiveTask:
    """Parse an inductive task from source text."""
    background_statements: list[Statement] = []
    pe: dict[Example, None] = {}
    ne: dict[Example, None] = {}
    lbh: dict[HeadTemplate, int] = {}
    lbha: dict[ModeDeclaration, int] = {}
    lbhd: dict[ModeDeclaration, int] = {}
    lbb: dict[ModeDeclaration, int] = {}
    lbc: dict[ModeDeclaration, int] = {}
    inventions: dict[AtomTemplate, tuple[int, int]] = {}
    constants: dict[str, dict[ast.AST, None]] = {}
    limits: dict[str, int | None] = {
        "#maxv": 3,
        "#maxbl": 3,
        "#maxhl": 1,
        "#maxpl": 6,
    }
    min_head_literals = 1
    declared_limits: dict[str, int] = {}
    for statement in lex(source):
        lc = statement.text
        directive = statement.directive

        try:
            limit = (
                directive
                if directive in {"#maxv", "#maxbl", "#maxhl", "#maxpl", "#minhl"}
                else None
            )
            if limit is not None:
                if limit in declared_limits:
                    raise SourceError(statement.line, f"duplicate {limit} declaration: {lc}", declared_limits[limit])
                declared_limits[limit] = statement.line
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
                    f"{directive} is no longer supported"
                )
            elif directive in {"#modeagg", "#modearith", "#modecmp"}:
                raise ValueError(
                    f"{directive} was removed; use an explicit #modeb literal"
                )
            elif directive == "#modeha":
                for mode in _get_combinable_head_declarations(lc, directive):
                    lbha.setdefault(mode, statement.line)
            elif directive == "#modehd":
                for mode in _get_combinable_head_declarations(lc, directive):
                    lbhd.setdefault(mode, statement.line)
            elif directive == "#modeh":
                lbh.setdefault(_get_head_declaration(lc), statement.line)
            elif directive == "#modeb":
                lbb.setdefault(_get_body_mode_declaration(lc), statement.line)
            elif directive == "#pos":
                res = _get_pos_neg_examples(lc)
                pe[Example.parse(res, True, statement.line)] = None
            elif directive == "#neg":
                res = _get_pos_neg_examples(lc)
                ne[Example.parse(res, False, statement.line)] = None
            elif directive == "#modec":
                for mode in _get_condition_mode_declarations(lc):
                    lbc.setdefault(mode, statement.line)
            elif directive == "#invent":
                recall, atom = _get_invented_declaration(lc)
                if atom in inventions:
                    raise SourceError(statement.line, f"duplicate #invent declaration: {lc}", inventions[atom][1])
                inventions[atom] = recall, statement.line
            elif directive == "#constant":
                type_name, value = _get_constant_declaration(lc)
                constants.setdefault(type_name, {})[value] = None
            else:
                background_statements.append(statement)
        except ValueError as error:
            if isinstance(error, SourceError):
                raise
            raise SourceError(statement.line, str(error)) from None

    invented_predicates = tuple(atom.signature for atom in inventions)
    explicit = (
        {
            literal.atom.signature: line
            for head, line in lbh.items()
            for literal in head.conclusions
            if isinstance(literal, AtomLiteral)
        }
        | {
            mode.literal.atom.signature: line
            for mode, line in (*lbha.items(), *lbhd.items())
            if isinstance(mode.literal, AtomLiteral)
        }
        | {
            literal.atom.signature: line
            for mode, line in lbb.items()
            for literal in (
                (mode.literal.conclusion,)
                if isinstance(mode.literal, ConditionalLiteral)
                else (mode.literal,)
            )
            if isinstance(literal, AtomLiteral)
        }
    )

    overlap = explicit.keys() & set(invented_predicates)
    if overlap:
        atom = next(atom for atom in inventions if atom.signature in overlap)
        line = inventions[atom][1]
        mode_line = explicit[atom.signature]
        raise SourceError(
            line, "invented predicates must not also use #modeh/#modeha/#modehd/#modeb: "
            f"{sorted(overlap)}", mode_line,
        )
    for atom, (recall, line) in inventions.items():
        lbh.setdefault(HeadTemplate.normal(AtomLiteral(atom)), line)
        lbb.setdefault(ModeDeclaration(recall, AtomLiteral(atom)), line)
    constant_types: dict[str, int] = {}
    for terms, line in (
        *((head.arguments, line) for head, line in lbh.items()),
        *((mode.literal.arguments, line) for mode, line in (*lbha.items(), *lbhd.items(), *lbc.items(), *lbb.items())),
    ):
        for argument in terms:
            for type_name in mode_terms.constant_types(argument):
                constant_types.setdefault(type_name, line)
    missing_constants = constant_types.keys() - constants.keys()
    if missing_constants:
        line = min(constant_types[name] for name in missing_constants)
        raise SourceError(
            line, f"constant mode types require #constant declarations: {sorted(missing_constants)}"
        )
    max_head_literals = limits["#maxhl"]
    if (
        (lbha or lbhd)
        and max_head_literals is not None
        and min_head_literals > max_head_literals
    ):
        line = declared_limits.get("#minhl", declared_limits.get("#maxhl", 1))
        maximum_line = declared_limits.get("#maxhl")
        raise SourceError(line, "#minhl cannot exceed #maxhl", maximum_line)
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
