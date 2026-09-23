import re
from collections.abc import Iterable
from dataclasses import replace

import clingo
from clingo import ast

from .asp import parse_atom, split_top_level_args
from .directives import _directive_args, _parse_recall
from .ir.aggregate_element import AggregateElement
from .ir.aggregate_guard import AggregateGuard
from .ir.aggregate_literal import AggregateLiteral
from .ir.atom_literal import AtomLiteral
from .ir.atom_template import AtomTemplate
from .ir.comparison_literal import ComparisonLiteral
from .ir.conditional_literal import ConditionalLiteral
from .ir.head_declaration import HeadDeclaration
from .ir.head_template import HeadTemplate
from .ir.head_aggregate_element import HeadAggregateElement
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
        literal = _prepare_body_comparison(declaration.literal, s)
        return ModeDeclaration(declaration.recall, literal)
    return declaration


def _prepare_body_comparison(
    literal: ComparisonLiteral, declaration: str
) -> ComparisonLiteral:
    bindings = tuple(binding for term in literal.terms for binding in term.bindings())
    if literal.default_negated and any(
        binding.direction == "output" for binding in bindings
    ):
        raise ValueError(
            f"default-negated comparisons cannot produce variables: {declaration}"
        )

    prepared = literal
    unspecified = tuple(
        index for index, binding in enumerate(bindings) if not binding.direction
    )
    fully_implicit = bool(bindings) and len(unspecified) == len(bindings)
    prepared_outputs_are_safe = False
    if unspecified:
        inferred_inputs = tuple(binding.direction or "input" for binding in bindings)
        prepared = _with_binding_directions(literal, inferred_inputs)
        if not literal.default_negated:
            inferred_outputs = tuple(
                binding.direction or "output" for binding in bindings
            )
            all_outputs = _with_binding_directions(literal, inferred_outputs)
            if _comparison_outputs_are_safe(all_outputs):
                prepared = all_outputs
                prepared_outputs_are_safe = True
            elif (assignment := _implicit_assignment_output(literal)) in unspecified:
                directions = list(inferred_inputs)
                directions[assignment] = "output"
                candidate = _with_binding_directions(literal, tuple(directions))
                if _comparison_outputs_are_safe(candidate):
                    prepared = candidate
                    prepared_outputs_are_safe = True
        prepared = replace(
            prepared, fully_implicit_directions=fully_implicit
        )

    if any(
        binding.direction == "output"
        for term in prepared.terms
        for binding in term.bindings()
    ) and not prepared_outputs_are_safe and not _comparison_outputs_are_safe(prepared):
        raise ValueError(
            f"comparison outputs are not safe under Clingo grounding: {declaration}"
        )
    return prepared


def _implicit_assignment_output(literal: ComparisonLiteral) -> int | None:
    if len(literal.operators) != 1 or literal.operators[0] != "=":
        return None
    left, right = literal.terms
    left_bindings = len(left.bindings())
    if left.kind == "variable" and right.contains_arithmetic:
        return 0
    if right.kind == "variable" and left.contains_arithmetic:
        return left_bindings
    return None


def _with_binding_directions(
    literal: ComparisonLiteral, directions: tuple[str, ...]
) -> ComparisonLiteral:
    direction_iter = iter(directions)

    def update(term: TermTemplate) -> TermTemplate:
        if term.kind == "variable":
            return replace(term, direction=next(direction_iter))
        if not term.arguments:
            return term
        return replace(term, arguments=tuple(update(arg) for arg in term.arguments))

    return replace(literal, terms=tuple(update(term) for term in literal.terms))


def _comparison_outputs_are_safe(literal: ComparisonLiteral) -> bool:
    bindings = tuple(binding for term in literal.terms for binding in term.bindings())
    outputs = tuple(
        index for index, binding in enumerate(bindings) if binding.direction == "output"
    )
    if not outputs:
        return True
    labels: dict[str, str] = {}
    variable_names = tuple(
        labels.setdefault(binding.label, f"X{index}")
        if binding.label
        else f"X{index}"
        for index, binding in enumerate(bindings)
    )
    def validation_term(term: TermTemplate) -> TermTemplate:
        if term.kind == "constant":
            return TermTemplate.fixed("0")
        if not term.arguments:
            return term
        return replace(
            term,
            arguments=tuple(validation_term(argument) for argument in term.arguments),
        )

    validation_literal = replace(
        literal, terms=tuple(validation_term(term) for term in literal.terms)
    )
    relation = validation_literal.render(iter(variable_names))
    inputs = tuple(
        name
        for name, binding in zip(variable_names, bindings, strict=True)
        if binding.direction != "output"
    )
    head = f"__gentians_output({','.join(variable_names[index] for index in outputs)})"
    body = ",".join((*[f"__gentians_input({name})" for name in inputs], relation))
    source = f"__gentians_input(0). {head} :- {body}."
    messages: list[str] = []
    control = clingo.Control(logger=lambda _code, message: messages.append(message))
    try:
        control.add("base", [], source)
        control.ground([("base", [])])
    except RuntimeError:
        return False
    return not any("unsafe" in message.lower() for message in messages)


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
    if head.ast_type == ast.ASTType.HeadAggregate:
        functions = {0: "count", 1: "sum", 2: "sum+", 3: "min", 4: "max"}
        function = functions.get(head.function)
        if function is None or not head.elements:
            raise ValueError(f"unsupported #modeh aggregate head: {s}")
        elements: list[HeadAggregateElement] = []
        for element in head.elements:
            conclusion = _literal_from_ast(element.condition.literal, s)
            if not isinstance(conclusion, AtomLiteral) or conclusion.default_negated:
                raise ValueError(f"aggregate head elements require positive atoms: {s}")
            conditions = _head_conditions(element.condition.condition, s)
            if any(
                not isinstance(condition, AtomLiteral) or condition.default_negated
                for condition in conditions
            ):
                raise ValueError(f"aggregate head conditions require positive atoms: {s}")
            elements.append(
                HeadAggregateElement(
                    tuple(_aggregate_term_from_ast(term, s) for term in element.terms),
                    conclusion.atom,
                    tuple(
                        condition.atom
                        for condition in conditions
                        if isinstance(condition, AtomLiteral)
                    ),
                )
            )
        operators = {
            ast.ComparisonOperator.Equal: "=",
            ast.ComparisonOperator.NotEqual: "!=",
            ast.ComparisonOperator.LessThan: "<",
            ast.ComparisonOperator.LessEqual: "<=",
            ast.ComparisonOperator.GreaterThan: ">",
            ast.ComparisonOperator.GreaterEqual: ">=",
        }

        def guard(node: ast.AST | None) -> AggregateGuard | None:
            if node is None:
                return None
            try:
                value = int(str(node.term))
            except ValueError as exc:
                raise ValueError(
                    f"#modeh aggregate guards require fixed integers: {s}"
                ) from exc
            return AggregateGuard(
                operators[node.comparison], TermTemplate.fixed(str(value))
            )

        return HeadDeclaration(
            recall,
            HeadTemplate(
                "aggregate",
                tuple(element.atom for element in elements),
                aggregate_elements=tuple(elements),
                aggregate_function=function,
                aggregate_left_guard=guard(head.left_guard),
                aggregate_right_guard=guard(head.right_guard),
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
) -> AggregateLiteral | AtomLiteral | ComparisonLiteral | ConditionalLiteral:
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
) -> AggregateLiteral | AtomLiteral | ComparisonLiteral | ConditionalLiteral:
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
    if node.atom.ast_type == ast.ASTType.BodyAggregate:
        return _aggregate_from_ast(node, declaration)
    if node.atom.ast_type == ast.ASTType.Comparison:
        if node.sign == ast.Sign.DoubleNegation:
            raise ValueError(f"invalid arithmetic relation: {declaration}")
        operators = {
            ast.ComparisonOperator.Equal: "=",
            ast.ComparisonOperator.NotEqual: "!=",
            ast.ComparisonOperator.LessThan: "<",
            ast.ComparisonOperator.LessEqual: "<=",
            ast.ComparisonOperator.GreaterThan: ">",
            ast.ComparisonOperator.GreaterEqual: ">=",
        }
        return ComparisonLiteral(
            (
                _term_from_ast(node.atom.term, declaration),
                *(
                    _term_from_ast(guard.term, declaration)
                    for guard in node.atom.guards
                ),
            ),
            tuple(operators[guard.comparison] for guard in node.atom.guards),
            node.sign == ast.Sign.Negation,
        )
    raw = str(node)
    negative = node.sign == ast.Sign.Negation
    if node.sign == ast.Sign.DoubleNegation:
        raise ValueError(f"double default negation is unsupported: {declaration}")
    if negative:
        raw = re.sub(r"^not\s+", "", raw, count=1)
    return AtomLiteral(_get_mode_atom(raw, declaration), negative)


def _aggregate_from_ast(node: ast.AST, declaration: str) -> AggregateLiteral:
    if node.sign != ast.Sign.NoSign:
        raise ValueError(f"aggregate modes cannot use default negation: {declaration}")
    aggregate = node.atom

    functions = {
        0: "count",
        1: "sum",
        2: "sum+",
        3: "min",
        4: "max",
    }
    try:
        function = functions[aggregate.function]
    except KeyError as exc:
        raise ValueError(f"unsupported aggregate function: {declaration}") from exc

    elements = []
    for element in aggregate.elements:
        if not element.terms or not element.condition:
            raise ValueError(
                f"aggregate modes require a nonempty tuple and condition: {declaration}"
            )
        tuple_terms = tuple(
            _aggregate_term_from_ast(term, declaration) for term in element.terms
        )
        conditions: list[AtomTemplate] = []
        for condition_node in element.condition:
            condition = _literal_from_ast(condition_node, declaration)
            if not isinstance(condition, AtomLiteral) or condition.default_negated:
                raise ValueError(
                    f"aggregate mode conditions must be positive atoms: {declaration}"
                )
            conditions.append(condition.atom)
        for term in (*tuple_terms, *(term for atom in conditions for term in atom.terms)):
            for binding in term.bindings():
                if binding.direction not in {"input", "any"}:
                    raise ValueError(
                        "aggregate tuple and condition variables require input or any "
                        f"direction: {declaration}"
                    )
        elements.append(AggregateElement(tuple_terms, tuple(conditions)))

    operators = {
        ast.ComparisonOperator.Equal: "=",
        ast.ComparisonOperator.NotEqual: "!=",
        ast.ComparisonOperator.LessThan: "<",
        ast.ComparisonOperator.LessEqual: "<=",
        ast.ComparisonOperator.GreaterThan: ">",
        ast.ComparisonOperator.GreaterEqual: ">=",
    }
    left = (
        AggregateGuard(
            operators[aggregate.left_guard.comparison],
            _aggregate_term_from_ast(aggregate.left_guard.term, declaration),
        )
        if aggregate.left_guard is not None else None
    )
    right = (
        AggregateGuard(
            operators[aggregate.right_guard.comparison],
            _aggregate_term_from_ast(aggregate.right_guard.term, declaration),
        )
        if aggregate.right_guard is not None else None
    )
    literal = AggregateLiteral(function, tuple(elements), left, right)
    for guard in (left, right):
        if guard is None:
            continue
        for binding in guard.term.bindings():
            if binding.direction == "output" and guard is not literal.output_guard:
                raise ValueError(
                    f"aggregate output requires one equality result guard: {declaration}"
                )
    if literal.output_guard is not None:
        result = literal.output_guard.term
        if function in {"count", "sum", "sum+"} and result.type != "numeric":
            raise ValueError(
                f"{function} aggregate result must have numeric type: {declaration}"
            )
    return literal


def _aggregate_term_from_ast(node: ast.AST, declaration: str) -> TermTemplate:
    term = _term_from_ast(node, declaration)
    if len(term.bindings()) > 1:
        raise ValueError(
            f"aggregate tuple and condition terms support one variable at most: {declaration}"
        )
    return term


def _term_from_ast(node: ast.AST, declaration: str) -> TermTemplate:
    if node.ast_type == ast.ASTType.Function:
        if node.external:
            raise ValueError(
                f"external function terms are unsupported: {declaration}"
            )
        raw_arguments = tuple(
            _term_from_ast(item, declaration) for item in node.arguments
        )
        if node.name == "var" and len(node.arguments) in {1, 2, 3}:
            values = tuple(str(item) for item in node.arguments)
            _validate_type(values[0], declaration)
            return TermTemplate.variable(
                values[0],
                values[1] if len(values) >= 2 else "",
                values[2] if len(values) == 3 else "",
            )
        if node.name == "const" and len(node.arguments) == 1:
            type_name = str(node.arguments[0])
            _validate_type(type_name, declaration)
            return TermTemplate.constant(type_name)
        if node.name in {"var", "const", "not"}:
            raise ValueError(f"invalid arithmetic placeholder: {declaration}")
        if not raw_arguments:
            return TermTemplate.fixed(str(node))
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
    if node.ast_type == ast.ASTType.Interval:
        return TermTemplate(
            "interval",
            "..",
            (
                _term_from_ast(node.left, declaration),
                _term_from_ast(node.right, declaration),
            ),
        )
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
