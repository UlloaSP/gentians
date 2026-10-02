from bisect import bisect_right
from itertools import chain
from pathlib import Path

from clingo import ast

from . import terms as mode_terms
from .asp import AspProgram, parse_program, split_top_level_args, validate_task_program
from .declarations import (
    _get_constant_declaration,
    _get_invented_declaration,
    _get_limit,
    _get_pos_neg_examples,
)
from .grammar import SourceError, _directive_args, source_position
from .ir.atom_literal import AtomLiteral
from .ir.atom_template import AtomTemplate
from .ir.conditional_literal import ConditionalLiteral
from .ir.comparison_literal import ComparisonLiteral
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
        position = f" (column {error.column})" if error.column is not None else ""
        raise ValueError(f"{origin(error.line)}: {error.message}{position}{related}") from None


@mode_terms.metadata_scope()
def parse_text(source: str) -> InductiveTask:
    """Parse an inductive task from source text."""
    background_statements: list[Statement] = []
    pe: dict[tuple[frozenset[ast.AST], frozenset[ast.AST], AspProgram, bool], Example] = {}
    ne: dict[tuple[frozenset[ast.AST], frozenset[ast.AST], AspProgram, bool], Example] = {}
    example_fields: dict[tuple[bool, str], AspProgram] = {}
    lbh: dict[HeadTemplate, Statement] = {}
    lbha: dict[ModeDeclaration, Statement] = {}
    lbhd: dict[ModeDeclaration, Statement] = {}
    lbb: dict[ModeDeclaration, Statement] = {}
    lbc: dict[ModeDeclaration, Statement] = {}
    inventions: dict[AtomTemplate, tuple[int, Statement]] = {}
    constants: dict[str, dict[ast.AST, None]] = {}
    limits: dict[str, int | None] = {
        "#maxv": 3,
        "#maxbl": 3,
        "#maxhl": 1,
        "#maxpl": 6,
    }
    min_head_literals = 1
    declared_limits: dict[str, int] = {}
    deduplicated_names = {"#modeh", "#modeha", "#modehd", "#modeb", "#modec", "#pos", "#neg", "#constant"}
    seen_declarations: set[str] = set()
    comparison_safety: dict[ComparisonLiteral, bool] = {}
    for statement in lex(source):
        directive = statement.directive
        if directive is None:
            background_statements.append(statement)
            continue
        lc = statement.text
        if directive in deduplicated_names and lc in seen_declarations:
            continue

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
                    lbha.setdefault(mode, statement)
            elif directive == "#modehd":
                for mode in _get_combinable_head_declarations(lc, directive):
                    lbhd.setdefault(mode, statement)
            elif directive == "#modeh":
                lbh.setdefault(_get_head_declaration(lc), statement)
            elif directive == "#modeb":
                lbb.setdefault(_get_body_mode_declaration(lc, comparison_safety), statement)
            elif directive == "#pos":
                res = _get_pos_neg_examples(lc)
                example = Example.parse(res, True, cache=example_fields)
                pe.setdefault(example.deduplication_key, example)
            elif directive == "#neg":
                res = _get_pos_neg_examples(lc)
                example = Example.parse(res, False, cache=example_fields)
                ne.setdefault(example.deduplication_key, example)
            elif directive == "#modec":
                for mode in _get_condition_mode_declarations(lc):
                    lbc.setdefault(mode, statement)
            elif directive == "#invent":
                recall, atom = _get_invented_declaration(lc)
                if atom in inventions:
                    raise SourceError(statement.line, f"duplicate #invent declaration: {lc}", inventions[atom][1].line)
                inventions[atom] = recall, statement
            elif directive == "#constant":
                type_name, value = _get_constant_declaration(lc)
                constants.setdefault(type_name, {})[value] = None
            if directive in deduplicated_names:
                seen_declarations.add(lc)
        except ValueError as error:
            if isinstance(error, SourceError):
                if error.column is not None:
                    raise statement.locate_error(error) from None
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
            for mode, line in chain(lbha.items(), lbhd.items())
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
        line = inventions[atom][1].line
        mode_line = explicit[atom.signature].line
        raise SourceError(
            line, "invented predicates must not also use #modeh/#modeha/#modehd/#modeb: "
            f"{sorted(overlap)}", mode_line,
        )
    for atom, (recall, line) in inventions.items():
        lbh.setdefault(HeadTemplate.normal(AtomLiteral(atom)), line)
        lbb.setdefault(ModeDeclaration(recall, AtomLiteral(atom)), line)
    constant_types: dict[str, tuple[Statement, ast.AST]] = {}
    for terms, declaration in chain(
        ((head.arguments, declaration) for head, declaration in lbh.items()),
        ((mode.literal.arguments, declaration) for mode, declaration in chain(lbha.items(), lbhd.items(), lbc.items(), lbb.items())),
    ):
        for argument in terms:
            for type_name in mode_terms.constant_types(argument):
                if type_name in constants:
                    continue
                previous = constant_types.get(type_name)
                if previous is not None and previous[0].start < declaration.start:
                    continue
                node = next(node for node in mode_terms._walk(argument)
                            if mode_terms.kind(node) == "constant" and str(node.arguments[0]) == type_name)
                position = declaration.start, node.location.begin.line, node.location.begin.column
                if previous is None or position < (previous[0].start, previous[1].location.begin.line, previous[1].location.begin.column):
                    constant_types[type_name] = declaration, node
    missing_constants = constant_types.keys() - constants.keys()
    if missing_constants:
        declaration, node = min(
            (constant_types[name] for name in missing_constants),
            key=lambda item: (item[0].start, item[1].location.begin.line, item[1].location.begin.column),
        )
        text = declaration.text
        name = declaration.directive
        assert name is not None
        spans = split_top_level_args(_directive_args(text, name))
        offset = len(name) + 1 + spans[0 if len(spans) == 1 else 1][0]
        line, column = source_position(text, offset)
        error = SourceError.at_node(node.arguments[0],
                                    f"constant mode types require #constant declarations: {sorted(missing_constants)}")
        error = error.with_origin(line, column if name == "#modeh" else column - 3)
        raise declaration.locate_error(error) from None
    max_head_literals = limits["#maxhl"]
    if (
        (lbha or lbhd)
        and max_head_literals is not None
        and min_head_literals > max_head_literals
    ):
        line = declared_limits.get("#minhl", declared_limits.get("#maxhl", 1))
        maximum_line = declared_limits.get("#maxhl")
        raise SourceError(line, "#minhl cannot exceed #maxhl", maximum_line)
    background_source = _background_source(background_statements)
    background = parse_program(background_source)
    validate_task_program(background_source, background)
    return InductiveTask(
        background=background,
        positive_examples=list(pe.values()),
        negative_examples=list(ne.values()),
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
    line = column = 1
    for statement in statements:
        if statement.line > line:
            parts.append("\n" * (statement.line - line))
            column = 1
        start_column = statement.column
        parts.append(" " * max(0, start_column - column))
        text = statement.source[statement.start:statement.end]
        parts.append(text)
        newlines = text.count("\n")
        line = statement.line + newlines
        column = len(text.rsplit("\n", 1)[-1].encode("utf-8")) + (1 if newlines else start_column)
    return "".join(parts)
