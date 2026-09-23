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
from .ir.boolean_literal import BooleanLiteral
from .ir.atom_template import AtomTemplate
from .ir.comparison_literal import ComparisonLiteral
from .ir.conditional_literal import ConditionalLiteral
from .ir.head_declaration import HeadDeclaration
from .ir.head_template import HeadTemplate
from .ir.head_aggregate_element import HeadAggregateElement
from .ir.mode_declaration import ModeDeclaration
from .ir.term_template import TermTemplate


def _unpool_mode_declarations(source: str, directive: str) -> tuple[str, ...]:
    if directive in {"#modeh", "#modeb"}:
        return (source,)
    parts = split_top_level_args(_directive_args(source, directive))
    if not parts:
        return (source,)
    if directive == "#modeha" and len(parts) == 1:
        recall = ""
        syntax = parts[0]
    else:
        recall = parts[0] + ","
        syntax = ",".join(parts[1:])
    rules: list[ast.AST] = []
    statement = f":- {syntax}."
    try:
        ast.parse_string(
            statement,
            lambda node: rules.append(node) if node.ast_type == ast.ASTType.Rule else None,
        )
    except RuntimeError as exc:
        raise ValueError(f"invalid {directive} declaration: {source}") from exc
    if len(rules) != 1:
        raise ValueError(f"invalid {directive} declaration: {source}")
    expanded = rules[0].unpool()
    if len(expanded) == 1:
        return (source,)
    if any(len(rule.body) != 1 for rule in expanded):
        raise ValueError(f"pool must expand to one mode literal: {source}")
    syntaxes = (str(rule.body[0]) for rule in expanded)
    return tuple(f"{directive}({recall}{item})." for item in syntaxes)


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
    if not isinstance(declaration.literal, AtomLiteral | ComparisonLiteral):
        raise ValueError(f"#modec requires an atom or comparison literal: {s}")
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
    literal = _get_mode_literal(atom, s)
    if not isinstance(literal, AtomLiteral):
        raise ValueError(f"#modeha requires an atom literal: {s}")
    if any(term.contains_anonymous for term in literal.arguments):
        raise ValueError(f"anonymous variables cannot occur in a head atom: {s}")
    return ModeDeclaration(recall, literal)


def _get_disjunctive_head_declaration(s: str) -> ModeDeclaration:
    declaration = _get_atom_mode_declaration(
        s.replace("#modehd", "#modeb", 1), "#modeb"
    )
    if not isinstance(declaration.literal, AtomLiteral):
        raise ValueError(f"#modehd requires an atom: {s}")
    if any(term.contains_anonymous for term in declaration.literal.arguments):
        raise ValueError(f"anonymous variables cannot occur in a head atom: {s}")
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
        if not isinstance(literal, AtomLiteral | BooleanLiteral | ComparisonLiteral | ConditionalLiteral):
            raise ValueError(f"unsupported #modeh head: {s}")
        conclusion = (
            literal.conclusion if isinstance(literal, ConditionalLiteral) else literal
        )
        conditions = (
            literal.conditions if isinstance(literal, ConditionalLiteral) else ()
        )
        return HeadDeclaration(
            recall,
            HeadTemplate(
                "normal", (conclusion.atom if isinstance(conclusion, AtomLiteral) else conclusion,),
                conditions=(conditions,),
                signs=((2 if conclusion.double_negated else 1 if conclusion.default_negated else 0)
                       if isinstance(conclusion, AtomLiteral) else 0,),
            ),
        )
    if head.ast_type == ast.ASTType.Disjunction:
        literals = tuple(_literal_from_ast(element.literal, s) for element in head.elements)
        atoms = tuple(_head_element(literal, s) for literal in literals)
        signs = tuple(_head_element_sign(literal, s) for literal in literals)
        conditions = tuple(
            _head_conditions(element.condition, s) for element in head.elements
        )
        return HeadDeclaration(
            recall, HeadTemplate("disjunction", atoms, conditions=conditions, signs=signs)
        )
    if head.ast_type == ast.ASTType.Aggregate:
        literals = tuple(_literal_from_ast(element.literal, s) for element in head.elements)
        atoms = tuple(_head_element(literal, s) for literal in literals)
        signs = tuple(_head_element_sign(literal, s) for literal in literals)
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
                signs=signs,
                lower_operator=_guard_operator(head.left_guard),
                upper_operator=_guard_operator(head.right_guard),
            ),
        )
    if head.ast_type == ast.ASTType.HeadAggregate:
        functions = {0: "count", 1: "sum", 2: "sum+", 3: "min", 4: "max"}
        function = functions.get(head.function)
        if function is None:
            raise ValueError(f"unsupported #modeh aggregate head: {s}")
        elements: list[HeadAggregateElement] = []
        for element in head.elements:
            conclusion = _literal_from_ast(element.condition.literal, s)
            if not isinstance(conclusion, AtomLiteral | BooleanLiteral | ComparisonLiteral):
                raise ValueError(f"unsupported aggregate head element: {s}")
            conditions = _head_conditions(element.condition.condition, s)
            if any(
                binding.direction == "output"
                for condition in conditions
                for term in condition.arguments
                for binding in term.bindings()
            ):
                raise ValueError(f"aggregate head conditions cannot produce outputs: {s}")
            elements.append(
                HeadAggregateElement(
                    tuple(_term_from_ast(term, s) for term in element.terms),
                    conclusion.atom if isinstance(conclusion, AtomLiteral) else conclusion,
                    conditions,
                    conclusion.default_negated if isinstance(conclusion, AtomLiteral) else False,
                    conclusion.double_negated if isinstance(conclusion, AtomLiteral) else False,
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
            return AggregateGuard(
                operators[node.comparison], _term_from_ast(node.term, s)
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


def _head_element(
    literal: AggregateLiteral | AtomLiteral | BooleanLiteral | ComparisonLiteral | ConditionalLiteral,
    declaration: str,
) -> AtomTemplate | BooleanLiteral | ComparisonLiteral:
    if isinstance(literal, AtomLiteral):
        return literal.atom
    if isinstance(literal, BooleanLiteral | ComparisonLiteral):
        return literal
    raise ValueError(f"unsupported head element: {declaration}")


def _head_element_sign(
    literal: AggregateLiteral | AtomLiteral | BooleanLiteral | ComparisonLiteral | ConditionalLiteral,
    declaration: str,
) -> int:
    if not isinstance(literal, AtomLiteral | BooleanLiteral | ComparisonLiteral):
        raise ValueError(f"unsupported head element: {declaration}")
    return 2 if literal.double_negated else 1 if literal.default_negated else 0


def _head_conditions(
    nodes: Iterable[ast.AST], declaration: str
) -> tuple[AtomLiteral | BooleanLiteral | ComparisonLiteral, ...]:
    conditions = tuple(_literal_from_ast(item, declaration) for item in nodes)
    if any(not isinstance(condition, AtomLiteral | BooleanLiteral | ComparisonLiteral) for condition in conditions):
        raise ValueError(f"unsupported head condition: {declaration}")
    return tuple(
        condition for condition in conditions
        if isinstance(condition, AtomLiteral | BooleanLiteral | ComparisonLiteral)
    )


def _head_bound(guard: ast.AST | None, declaration: str) -> int | TermTemplate | None:
    if guard is None:
        return None
    try:
        return int(str(guard.term))
    except ValueError:
        return _term_from_ast(guard.term, declaration)


def _guard_operator(guard: ast.AST | None) -> str:
    if guard is None:
        return "<="
    return {
        ast.ComparisonOperator.Equal: "=",
        ast.ComparisonOperator.NotEqual: "!=",
        ast.ComparisonOperator.LessThan: "<",
        ast.ComparisonOperator.LessEqual: "<=",
        ast.ComparisonOperator.GreaterThan: ">",
        ast.ComparisonOperator.GreaterEqual: ">=",
    }[guard.comparison]


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
        nodes: list[ast.AST] = []
        try:
            ast.parse_string(f":- {raw}.", nodes.append)
        except RuntimeError as exc:
            raise ValueError(f"invalid mode atom: {declaration}") from exc
        rules = [node for node in nodes if node.ast_type == ast.ASTType.Rule]
        if len(rules) != 1 or len(rules[0].body) != 1:
            raise ValueError(f"invalid mode atom: {declaration}")
        symbol = rules[0].body[0].atom.symbol
        if symbol.ast_type != ast.ASTType.Pool:
            raise ValueError(f"invalid mode atom: {declaration}")
        alternatives = tuple(_get_mode_atom(str(item), declaration) for item in symbol.arguments)
        first = alternatives[0]
        if any((item.name, item.strong, len(item.terms)) != (first.name, first.strong, len(first.terms)) for item in alternatives):
            raise ValueError(f"pooled mode atoms require one predicate: {declaration}")
        differing = tuple(index for index in range(len(first.terms)) if len({item.terms[index] for item in alternatives}) > 1)
        if len(differing) != 1:
            return AtomTemplate(
                first.name, first.terms, first.strong,
                tuple(item.terms for item in alternatives),
            )
        index = differing[0]
        terms = list(first.terms)
        terms[index] = TermTemplate("pool", arguments=tuple(item.terms[index] for item in alternatives))
        return AtomTemplate(first.name, tuple(terms), first.strong)
    name, raw_arguments = parsed
    if name == "not" or not re.fullmatch(r"[a-z_][A-Za-z0-9_']*", name):
        raise ValueError(f"invalid mode predicate: {declaration}")
    return AtomTemplate(
        name,
        tuple(_get_mode_argument(argument, declaration) for argument in raw_arguments),
        strong,
    )


def _get_mode_argument(raw: str, declaration: str) -> TermTemplate:
    raw = raw.strip()
    nodes: list[ast.AST] = []
    try:
        ast.parse_string(f":- __gentians_argument({raw}).", nodes.append)
    except RuntimeError as exc:
        raise ValueError(f"invalid mode argument: {declaration}") from exc
    rules = [node for node in nodes if node.ast_type == ast.ASTType.Rule]
    if len(rules) != 1 or len(rules[0].body) != 1:
        raise ValueError(f"invalid mode argument: {declaration}")
    symbol = rules[0].body[0].atom.symbol
    if symbol.ast_type == ast.ASTType.Pool:
        alternatives = symbol.arguments
        if any(item.ast_type != ast.ASTType.Function or len(item.arguments) != 1 for item in alternatives):
            raise ValueError(f"invalid mode argument: {declaration}")
        term = TermTemplate("pool", arguments=tuple(_term_from_ast(item.arguments[0], declaration) for item in alternatives))
        if any(not binding.direction for binding in term.bindings()):
            raise ValueError(f"invalid mode argument: {declaration}")
        return term
    if symbol.ast_type != ast.ASTType.Function or len(symbol.arguments) != 1:
        raise ValueError(f"invalid mode argument: {declaration}")
    term = _term_from_ast(symbol.arguments[0], declaration)
    if any(not binding.direction for binding in term.bindings()):
        raise ValueError(f"invalid mode argument: {declaration}")
    return term


def _validate_type(type_name: str, declaration: str) -> None:
    if type_name == "any" or not re.fullmatch(r"[a-z][A-Za-z0-9_]*", type_name):
        raise ValueError(f"invalid mode type in declaration: {declaration}")


def _get_mode_literal(
    raw: str, declaration: str, *, conditional: bool = False
) -> AggregateLiteral | AtomLiteral | BooleanLiteral | ComparisonLiteral | ConditionalLiteral:
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
) -> AggregateLiteral | AtomLiteral | BooleanLiteral | ComparisonLiteral | ConditionalLiteral:
    if node.ast_type == ast.ASTType.ConditionalLiteral:
        conclusion = _literal_from_ast(node.literal, declaration)
        conditions = tuple(
            _literal_from_ast(condition, declaration) for condition in node.condition
        )
        if isinstance(conclusion, ConditionalLiteral) or any(
            isinstance(condition, ConditionalLiteral) for condition in conditions
        ):
            raise ValueError(f"nested conditional literal is invalid: {declaration}")
        if not isinstance(conclusion, AtomLiteral | BooleanLiteral | ComparisonLiteral):
            raise ValueError(f"unsupported conditional conclusion: {declaration}")
        if any(not isinstance(condition, AtomLiteral | BooleanLiteral | ComparisonLiteral) for condition in conditions):
            raise ValueError(f"unsupported conditional condition: {declaration}")
        flat_conditions = tuple(
            condition for condition in conditions
            if isinstance(condition, AtomLiteral | BooleanLiteral | ComparisonLiteral)
        )
        return ConditionalLiteral(
            conclusion, flat_conditions, (-1,) * len(flat_conditions)
        )
    if node.ast_type != ast.ASTType.Literal:
        raise ValueError(f"unsupported mode literal: {declaration}")
    if node.atom.ast_type == ast.ASTType.BodyAggregate:
        return _aggregate_from_ast(node, declaration)
    if node.atom.ast_type == ast.ASTType.Aggregate:
        return _set_aggregate_from_ast(node, declaration)
    if node.atom.ast_type == ast.ASTType.BooleanConstant:
        return BooleanLiteral(
            bool(node.atom.value),
            node.sign != ast.Sign.NoSign,
            node.sign == ast.Sign.DoubleNegation,
        )
    if node.atom.ast_type == ast.ASTType.Comparison:
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
            node.sign != ast.Sign.NoSign,
            double_negated=node.sign == ast.Sign.DoubleNegation,
        )
    raw = str(node)
    negative = node.sign != ast.Sign.NoSign
    if negative:
        raw = re.sub(r"^(?:not\s+){1,2}", "", raw, count=1)
    return AtomLiteral(
        _get_mode_atom(raw, declaration), negative,
        node.sign == ast.Sign.DoubleNegation,
    )


def _aggregate_from_ast(node: ast.AST, declaration: str) -> AggregateLiteral:
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
        tuple_terms = tuple(
            _term_from_ast(term, declaration) for term in element.terms
        )
        conditions: list[AtomLiteral | BooleanLiteral | ComparisonLiteral] = []
        for condition_node in element.condition:
            condition = _literal_from_ast(condition_node, declaration)
            if not isinstance(condition, AtomLiteral | BooleanLiteral | ComparisonLiteral):
                raise ValueError(
                    f"invalid aggregate mode condition: {declaration}"
                )
            conditions.append(condition)
        for term in (*tuple_terms, *(term for condition in conditions for term in condition.arguments)):
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
            _term_from_ast(aggregate.left_guard.term, declaration),
        )
        if aggregate.left_guard is not None else None
    )
    right = (
        AggregateGuard(
            operators[aggregate.right_guard.comparison],
            _term_from_ast(aggregate.right_guard.term, declaration),
        )
        if aggregate.right_guard is not None else None
    )
    literal = AggregateLiteral(
        function, tuple(elements), left, right,
        node.sign != ast.Sign.NoSign,
        node.sign == ast.Sign.DoubleNegation,
    )
    if node.sign != ast.Sign.NoSign and literal.output_guard is not None:
        raise ValueError(f"negated aggregates cannot produce an output: {declaration}")
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


def _set_aggregate_from_ast(node: ast.AST, declaration: str) -> AggregateLiteral:
    aggregate = node.atom
    elements: list[AggregateElement] = []
    for element in aggregate.elements:
        conclusion = _literal_from_ast(element.literal, declaration)
        if not isinstance(conclusion, AtomLiteral | BooleanLiteral | ComparisonLiteral):
            raise ValueError(f"set aggregate elements require basic literals: {declaration}")
        conditions = _head_conditions(element.condition, declaration)
        if any(
            binding.direction == "output"
            for literal in (conclusion, *conditions)
            for term in literal.arguments
            for binding in term.bindings()
        ):
            raise ValueError(f"set aggregate elements cannot produce outputs: {declaration}")
        elements.append(AggregateElement(
            (), conditions, conclusion,
        ))
    left = (
        AggregateGuard(_guard_operator(aggregate.left_guard), _term_from_ast(aggregate.left_guard.term, declaration))
        if aggregate.left_guard is not None else None
    )
    right = (
        AggregateGuard(_guard_operator(aggregate.right_guard), _term_from_ast(aggregate.right_guard.term, declaration))
        if aggregate.right_guard is not None else None
    )
    if any(
        binding.direction == "output"
        for guard in (left, right) if guard is not None
        for binding in guard.term.bindings()
    ):
        raise ValueError(f"set aggregate bounds cannot produce outputs: {declaration}")
    return AggregateLiteral(
        "set", tuple(elements), left, right,
        node.sign != ast.Sign.NoSign,
        node.sign == ast.Sign.DoubleNegation,
    )


def _term_from_ast(node: ast.AST, declaration: str) -> TermTemplate:
    if node.ast_type == ast.ASTType.Variable and node.name == "_":
        return TermTemplate("anonymous")
    if node.ast_type == ast.ASTType.Pool:
        return TermTemplate("pool", arguments=tuple(_term_from_ast(item, declaration) for item in node.arguments))
    if node.ast_type == ast.ASTType.Function:
        if node.external:
            raise ValueError(
                f"external function terms are unsupported: {declaration}"
            )
        raw_arguments = tuple(
            _term_from_ast(item, declaration) for item in node.arguments
        )
        if node.name == "":
            return TermTemplate("tuple", arguments=raw_arguments)
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
