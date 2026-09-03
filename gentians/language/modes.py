import re
from collections.abc import Iterable

from clingo import ast

from .asp import parse_atom, split_top_level_args
from .directives import _directive_args, _parse_recall
from .ir.atom_literal import AtomLiteral
from .ir.atom_template import AtomTemplate
from .ir.comparison_literal import ComparisonLiteral
from .ir.conditional_literal import ConditionalLiteral
from .ir.head_declaration import HeadDeclaration
from .ir.head_template import HeadTemplate
from .ir.mode_declaration import ModeDeclaration
from .ir.term_template import TermTemplate


def _get_atom_mode_declaration(s: str, name: str) -> ModeDeclaration:
    parts = split_top_level_args(_directive_args(s, name))
    if len(parts) < 2:
        raise ValueError(f"invalid {name} declaration: {s}")
    recall = _parse_recall(parts[0])
    literal = _get_mode_literal(",".join(parts[1:]), s, conditional=True)
    return ModeDeclaration(recall, literal)


def _get_body_mode_declaration(s: str) -> ModeDeclaration:
    declaration = _get_atom_mode_declaration(s, "#modeb")
    if isinstance(declaration.literal, ComparisonLiteral):
        raise ValueError(f"#modeb comparisons belong in #modearith: {s}")
    return declaration


def _get_condition_mode_declaration(s: str) -> ModeDeclaration:
    declaration = _get_atom_mode_declaration(s, "#modec")
    if isinstance(declaration.literal, ConditionalLiteral):
        raise ValueError(f"#modec cannot contain a nested conditional literal: {s}")
    return declaration


def _get_aggregate_head_declaration(s: str) -> ModeDeclaration:
    parts = split_top_level_args(_directive_args(s, "#modeha"))
    if len(parts) == 1:
        recall = -1
        atom = parts[0]
    elif len(parts) == 2:
        recall = _parse_recall(parts[0])
        atom = parts[1]
    else:
        raise ValueError(f"invalid #modeha declaration: {s}")
    template = _get_mode_atom(atom, s)
    return ModeDeclaration(recall, AtomLiteral(template))


def _get_disjunctive_head_declaration(s: str) -> ModeDeclaration:
    declaration = _get_atom_mode_declaration(
        s.replace("#modehd", "#modeb", 1), "#modeb"
    )
    if (
        not isinstance(declaration.literal, AtomLiteral)
        or declaration.literal.default_negated
    ):
        raise ValueError(f"#modehd requires a positive atom: {s}")
    return declaration


def _get_head_declaration(s: str) -> HeadDeclaration:
    parts = split_top_level_args(_directive_args(s, "#modeh"))
    if len(parts) < 2:
        raise ValueError(f"invalid #modeh declaration: {s}")
    recall = _parse_recall(parts[0])
    syntax = ",".join(parts[1:]).strip()
    rules: list[ast.AST] = []
    try:
        ast.parse_string(
            f"{syntax} :- __modeh_body.",
            lambda node: (
                rules.append(node) if node.ast_type == ast.ASTType.Rule else None
            ),
        )
    except RuntimeError as exc:
        raise ValueError(f"invalid #modeh declaration: {s}") from exc
    if len(rules) != 1:
        raise ValueError(f"invalid #modeh declaration: {s}")
    head = rules[0].head
    if head.ast_type in {ast.ASTType.Literal, ast.ASTType.ConditionalLiteral}:
        literal = _literal_from_ast(head, s)
        if not isinstance(literal, AtomLiteral | ConditionalLiteral):
            raise ValueError(f"#modeh requires atom heads: {s}")
        conclusion = (
            literal.conclusion if isinstance(literal, ConditionalLiteral) else literal
        )
        if not isinstance(conclusion, AtomLiteral) or conclusion.default_negated:
            raise ValueError(f"#modeh requires positive atom heads: {s}")
        conditions = (
            literal.conditions if isinstance(literal, ConditionalLiteral) else ()
        )
        return HeadDeclaration(
            recall,
            HeadTemplate("normal", (conclusion.atom,), conditions=(conditions,)),
        )
    if head.ast_type == ast.ASTType.Disjunction:
        atoms = tuple(_head_atom(str(element.literal), s) for element in head.elements)
        conditions = tuple(
            _head_conditions(element.condition, s) for element in head.elements
        )
        return HeadDeclaration(
            recall, HeadTemplate("disjunction", atoms, conditions=conditions)
        )
    if head.ast_type == ast.ASTType.Aggregate:
        atoms = tuple(_head_atom(str(element.literal), s) for element in head.elements)
        conditions = tuple(
            _head_conditions(element.condition, s) for element in head.elements
        )
        return HeadDeclaration(
            recall,
            HeadTemplate(
                "choice",
                atoms,
                _head_bound(head.left_guard, s),
                _head_bound(head.right_guard, s),
                conditions,
            ),
        )
    raise ValueError(f"unsupported #modeh head form: {s}")


def _head_atom(raw: str, declaration: str) -> AtomTemplate:
    return _get_mode_atom(raw, declaration)


def _head_conditions(
    nodes: Iterable[ast.AST], declaration: str
) -> tuple[AtomLiteral | ComparisonLiteral, ...]:
    conditions = tuple(_literal_from_ast(item, declaration) for item in nodes)
    if any(isinstance(condition, ConditionalLiteral) for condition in conditions):
        raise ValueError(f"nested conditional literal is invalid: {declaration}")
    return tuple(
        condition
        for condition in conditions
        if isinstance(condition, AtomLiteral | ComparisonLiteral)
    )


def _head_bound(guard: ast.AST | None, declaration: str) -> int | None:
    if guard is None:
        return None
    if guard.comparison != ast.ComparisonOperator.LessEqual:
        raise ValueError(f"#modeh cardinality bounds must use <=: {declaration}")
    try:
        return int(str(guard.term))
    except ValueError as exc:
        raise ValueError(
            f"#modeh cardinality bounds must be integers: {declaration}"
        ) from exc


def _get_mode_atom(raw: str, declaration: str) -> AtomTemplate:
    raw = raw.strip()
    if raw == "not" or re.match(r"not\s+", raw):
        raise ValueError(f"invalid mode atom: {declaration}")
    strong = raw.startswith("-")
    if strong:
        raw = raw[1:].strip()
    if raw.startswith("-"):
        raise ValueError(f"invalid mode atom: {declaration}")
    parsed = parse_atom(raw)
    if parsed is None:
        raise ValueError(f"invalid mode atom: {declaration}")
    name, raw_arguments = parsed
    if name == "not" or not re.fullmatch(r"[a-z][A-Za-z0-9_]*", name):
        raise ValueError(f"invalid mode predicate: {declaration}")
    return AtomTemplate(
        name,
        tuple(_get_mode_argument(argument, declaration) for argument in raw_arguments),
        strong,
    )


def _get_mode_argument(raw: str, declaration: str) -> TermTemplate:
    raw = raw.strip()
    if raw.startswith("(") and raw.endswith(")"):
        inner = raw[1:-1].strip()
        parts = split_top_level_args(inner)
        if len(parts) == 1 and not inner.endswith(","):
            raise ValueError(f"invalid mode tuple: {declaration}")
        return TermTemplate(
            "tuple",
            arguments=tuple(_get_mode_argument(part, declaration) for part in parts),
        )
    parsed = parse_atom(raw)
    if parsed is None:
        raise ValueError(f"invalid mode argument: {declaration}")
    kind, parts = parsed
    if kind == "var" and len(parts) in {2, 3}:
        type_name, direction = (part.strip() for part in parts[:2])
        label = parts[2].strip() if len(parts) == 3 else ""
        _validate_type(type_name, declaration)
        return TermTemplate.variable(type_name, direction, label)
    if kind == "const" and len(parts) == 1:
        type_name = parts[0].strip()
        _validate_type(type_name, declaration)
        return TermTemplate.constant(type_name)
    if kind in {"var", "const", "not"} or not parts:
        raise ValueError(f"invalid mode argument: {declaration}")
    if not re.fullmatch(r"[a-z][A-Za-z0-9_]*", kind):
        raise ValueError(f"invalid mode function: {declaration}")
    return TermTemplate(
        "function",
        kind,
        tuple(_get_mode_argument(part, declaration) for part in parts),
    )


def _validate_type(type_name: str, declaration: str) -> None:
    if type_name == "any" or not re.fullmatch(r"[a-z][A-Za-z0-9_]*", type_name):
        raise ValueError(f"invalid mode type in declaration: {declaration}")


def _get_mode_literal(
    raw: str, declaration: str, *, conditional: bool = False
) -> AtomLiteral | ComparisonLiteral | ConditionalLiteral:
    nodes: list[ast.AST] = []
    try:
        ast.parse_string(f":- {raw.strip()}.", nodes.append)
    except RuntimeError as exc:
        raise ValueError(f"invalid mode literal: {declaration}") from exc
    rules = [node for node in nodes if node.ast_type == ast.ASTType.Rule]
    if len(rules) != 1 or len(rules[0].body) != 1:
        raise ValueError(f"mode declaration requires one literal: {declaration}")
    literal = _literal_from_ast(rules[0].body[0], declaration)
    if isinstance(literal, ConditionalLiteral) and not conditional:
        raise ValueError(f"conditional literal is not allowed here: {declaration}")
    return literal


def _literal_from_ast(
    node: ast.AST, declaration: str
) -> AtomLiteral | ComparisonLiteral | ConditionalLiteral:
    if node.ast_type == ast.ASTType.ConditionalLiteral:
        conclusion = _literal_from_ast(node.literal, declaration)
        conditions = tuple(
            _literal_from_ast(condition, declaration) for condition in node.condition
        )
        if isinstance(conclusion, ConditionalLiteral) or any(
            isinstance(condition, ConditionalLiteral) for condition in conditions
        ):
            raise ValueError(f"nested conditional literal is invalid: {declaration}")
        if not isinstance(conclusion, AtomLiteral):
            raise ValueError(f"conditional conclusions must be atoms: {declaration}")
        flat_conditions = tuple(
            condition
            for condition in conditions
            if isinstance(condition, AtomLiteral | ComparisonLiteral)
        )
        return ConditionalLiteral(
            conclusion, flat_conditions, (-1,) * len(flat_conditions)
        )
    if node.ast_type != ast.ASTType.Literal:
        raise ValueError(f"unsupported mode literal: {declaration}")
    if node.atom.ast_type == ast.ASTType.Comparison:
        if node.sign != ast.Sign.NoSign or len(node.atom.guards) != 1:
            raise ValueError(f"invalid arithmetic relation: {declaration}")
        guard = node.atom.guards[0]
        operators = {
            ast.ComparisonOperator.Equal: "=",
            ast.ComparisonOperator.NotEqual: "!=",
            ast.ComparisonOperator.LessThan: "<",
            ast.ComparisonOperator.LessEqual: "<=",
            ast.ComparisonOperator.GreaterThan: ">",
            ast.ComparisonOperator.GreaterEqual: ">=",
        }
        return ComparisonLiteral(
            operators[guard.comparison],
            (
                _term_from_ast(node.atom.term, declaration),
                _term_from_ast(guard.term, declaration),
            ),
            False,
        )
    raw = str(node)
    negative = node.sign == ast.Sign.Negation
    if node.sign == ast.Sign.DoubleNegation:
        raise ValueError(f"double default negation is unsupported: {declaration}")
    if negative:
        raw = re.sub(r"^not\s+", "", raw, count=1)
    return AtomLiteral(_get_mode_atom(raw, declaration), negative)


def _term_from_ast(node: ast.AST, declaration: str) -> TermTemplate:
    if node.ast_type == ast.ASTType.Function:
        raw_arguments = tuple(
            _term_from_ast(item, declaration) for item in node.arguments
        )
        if node.name == "var" and len(node.arguments) in {2, 3}:
            values = tuple(str(item) for item in node.arguments)
            _validate_type(values[0], declaration)
            return TermTemplate.variable(
                values[0], values[1], values[2] if len(values) == 3 else ""
            )
        if node.name == "const" and len(node.arguments) == 1:
            type_name = str(node.arguments[0])
            _validate_type(type_name, declaration)
            return TermTemplate.constant(type_name)
        if node.name in {"var", "const", "not"}:
            raise ValueError(f"invalid arithmetic placeholder: {declaration}")
        return TermTemplate("function", node.name, raw_arguments)
    if node.ast_type == ast.ASTType.BinaryOperation:
        operators = {
            ast.BinaryOperator.XOr: "^",
            ast.BinaryOperator.Or: "?",
            ast.BinaryOperator.And: "&",
            ast.BinaryOperator.Plus: "+",
            ast.BinaryOperator.Minus: "-",
            ast.BinaryOperator.Multiplication: "*",
            ast.BinaryOperator.Division: "/",
            ast.BinaryOperator.Modulo: "\\",
            ast.BinaryOperator.Power: "**",
        }
        operator = operators.get(node.operator_type)
        if operator is None:
            raise ValueError(f"unsupported arithmetic operator: {declaration}")
        return TermTemplate(
            "arithmetic",
            operator,
            (
                _term_from_ast(node.left, declaration),
                _term_from_ast(node.right, declaration),
            ),
        )
    if node.ast_type == ast.ASTType.SymbolicTerm:
        return TermTemplate.fixed(str(node.symbol))
    if node.ast_type == ast.ASTType.UnaryOperation:
        operator = {
            ast.UnaryOperator.Minus: "neg",
            ast.UnaryOperator.Negation: "bitnot",
            ast.UnaryOperator.Absolute: "absolute",
        }.get(node.operator_type)
        if operator is None:
            raise ValueError(f"unsupported unary arithmetic operator: {declaration}")
        return TermTemplate(
            "arithmetic", operator, (_term_from_ast(node.argument, declaration),)
        )
    raise ValueError(f"unsupported arithmetic term: {declaration}")
