from pathlib import Path

from clingo import ast

from .asp import parse_program
from .declarations import (
    _get_aggregate_declaration,
    _get_arithmetic_declaration,
    _get_constant_declaration,
    _get_invented_declaration,
    _get_modem_declaration,
    _get_pos_neg_examples,
    _get_predicate_declaration,
)
from .directives import _get_limit
from .ir.aggregate_declaration import AggregateDeclaration
from .ir.atom_literal import AtomLiteral
from .ir.atom_template import AtomTemplate
from .ir.conditional_literal import ConditionalLiteral
from .ir.example import Example
from .ir.head_declaration import HeadDeclaration
from .ir.head_template import HeadTemplate
from .ir.mode_declaration import ModeDeclaration
from .ir.operator_declaration import OperatorDeclaration
from .ir.inductive_task import InductiveTask
from .ir.term_template import TermTemplate
from .lexer import lex
from .metarules import _get_bias, _get_metarule, _instantiate_metarules
from .modes import (
    _get_aggregate_head_declaration,
    _get_body_mode_declaration,
    _get_condition_mode_declaration,
    _get_disjunctive_head_declaration,
    _get_head_declaration,
)


def parse_file(filename: str) -> InductiveTask:
    return parse_text(Path(filename).read_text(encoding="utf-8"))


def parse_text(source: str) -> InductiveTask:
    """Parse an inductive task from source text."""
    bg: list[ast.AST] = []
    pe: list[Example] = []
    ne: list[Example] = []
    lbh: list[HeadDeclaration] = []
    lbha: list[ModeDeclaration] = []
    lbhd: list[ModeDeclaration] = []
    lbb: list[ModeDeclaration] = []
    lbc: list[ModeDeclaration] = []
    aggregates: list[AggregateDeclaration] = []
    arithmetic: list[OperatorDeclaration | ModeDeclaration] = []
    inventions: list[tuple[int, str, tuple[TermTemplate, ...]]] = []
    constants: dict[str, list[str]] = {}
    limits: dict[str, int | None] = {
        "#maxv": 3,
        "#maxbl": 3,
        "#maxhl": 1,
        "#maxpl": 6,
    }
    min_head_literals = 1
    declared_limits: set[str] = set()
    bias: list[ast.AST] = []
    metarule_definitions: dict[str, str] = {}
    predicate_pools: dict[str, list[tuple[str, int]]] = {}
    modem_declarations: list[tuple[str, tuple[tuple[str, int], ...]]] = []
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
        elif directive == "#bias":
            bias.extend(_get_bias(lc))
        elif directive == "#metarule":
            name, payload = _get_metarule(lc)
            if name in metarule_definitions:
                raise ValueError(f"duplicate #metarule declaration: {name}")
            metarule_definitions[name] = payload
        elif directive == "#modeha":
            md = _get_aggregate_head_declaration(lc)
            if md not in lbha:
                lbha.append(md)
        elif directive == "#modehd":
            md = _get_disjunctive_head_declaration(lc)
            if md not in lbhd:
                lbhd.append(md)
        elif directive == "#modeh":
            md = _get_head_declaration(lc)
            if md not in lbh:
                lbh.append(md)
        elif directive == "#modeb":
            md = _get_body_mode_declaration(lc)
            if md not in lbb:
                lbb.append(md)
        elif directive == "#pos":
            res = _get_pos_neg_examples(lc)
            ex = Example(res, True)
            if ex not in pe:
                pe.append(ex)
        elif directive == "#neg":
            res = _get_pos_neg_examples(lc)
            ex = Example(res, False)
            if ex not in ne:
                ne.append(ex)
        elif directive == "#modeagg":
            aggregate = _get_aggregate_declaration(lc)
            if aggregate not in aggregates:
                aggregates.append(aggregate)
        elif directive == "#modecmp":
            raise ValueError("#modecmp was removed; use #modearith")
        elif directive == "#modec":
            md = _get_condition_mode_declaration(lc)
            if md not in lbc:
                lbc.append(md)
        elif directive == "#modearith":
            operator = _get_arithmetic_declaration(lc)
            if operator not in arithmetic:
                arithmetic.append(operator)
        elif directive == "#predicate":
            pool, signature = _get_predicate_declaration(lc)
            values = predicate_pools.setdefault(pool, [])
            if signature not in values:
                values.append(signature)
        elif directive == "#modem":
            modem = _get_modem_declaration(lc)
            if modem not in modem_declarations:
                modem_declarations.append(modem)
        elif directive == "#invent":
            invention = _get_invented_declaration(lc)
            if any(existing[1:] == invention[1:] for existing in inventions):
                raise ValueError(f"duplicate #invent declaration: {lc}")
            inventions.append(invention)
        elif directive == "#constant":
            type_name, value = _get_constant_declaration(lc)
            values = constants.setdefault(type_name, [])
            if value not in values:
                values.append(value)
        else:
            bg.extend(parse_program(lc, statement.line))

    invented_predicates = tuple(
        (name, len(arguments)) for _recall, name, arguments in inventions
    )
    explicit = (
        {atom.signature for head in lbh for atom in head.template.elements}
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
    for recall, name, arguments in inventions:
        lbh.append(
            HeadDeclaration(1, HeadTemplate("normal", (AtomTemplate(name, arguments),)))
        )
        lbb.append(ModeDeclaration(recall, AtomLiteral(AtomTemplate(name, arguments))))
    constant_types = {
        type_name
        for terms in [
            *(atom.terms for head in lbh for atom in head.template.elements),
            *(
                condition.arguments
                for head in lbh
                for conditions in head.template.conditions
                for condition in conditions
            ),
            *(mode.literal.arguments for mode in (*lbha, *lbhd, *lbc)),
            *(mode.literal.arguments for mode in lbb),
            *(
                mode.literal.arguments
                for mode in arithmetic
                if isinstance(mode, ModeDeclaration)
            ),
        ]
        for argument in terms
        for type_name in argument.constant_types()
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
        background=tuple(bg),
        positive_examples=pe,
        negative_examples=ne,
        language_bias_head=lbh,
        language_bias_body=lbb,
        aggregate_modes=aggregates,
        arithmetic_modes=arithmetic,
        language_bias_condition=lbc,
        invented_predicates=invented_predicates,
        constants={name: tuple(values) for name, values in constants.items()},
        max_variables=limits["#maxv"],
        max_body_literals=limits["#maxbl"],
        max_head_literals=max_head_literals,
        max_program_clauses=limits["#maxpl"],
        language_bias_aggregate_head=lbha,
        language_bias_disjunctive_head=lbhd,
        min_aggregate_head_literals=min_head_literals,
        bias=tuple(bias),
        metarule_programs=_instantiate_metarules(
            metarule_definitions, predicate_pools, modem_declarations
        ),
    )
