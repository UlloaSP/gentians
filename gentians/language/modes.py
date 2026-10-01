from collections.abc import Iterable
from dataclasses import replace

import clingo
from clingo import ast

from . import terms as mode_terms
from .asp import add_program, parse_rule, split_top_level_args
from .ast_nodes import (
    AGGREGATE_FUNCTIONS,
    COMPARISON_OPERATORS,
    LOCATION,
    binding_term,
    literal as ast_literal,
)
from .directives import _directive_args, _parse_recall
from .ir.aggregate_element import AggregateElement
from .ir.aggregate_literal import AggregateLiteral
from .ir.atom_literal import AtomLiteral
from .ir.atom_template import AtomTemplate
from .ir.boolean_literal import BooleanLiteral
from .ir.comparison_literal import ComparisonLiteral
from .ir.conditional_literal import ConditionalLiteral
from .ir.head_aggregate_element import HeadAggregateElement
from .ir.head_template import HeadTemplate
from .ir.mode_declaration import ModeDeclaration

_COMPARISON_SYMBOLS = {value: key for key, value in COMPARISON_OPERATORS.items()}
_AGGREGATE_NAMES = {value: key for key, value in AGGREGATE_FUNCTIONS.items()}


def _get_mode_declarations(
    source: str, name: str, *, unpool: bool = False
) -> tuple[ModeDeclaration, ...]:
    parts = split_top_level_args(_directive_args(source, name))
    combinable_head = name in {"#modeha", "#modehd"}
    if combinable_head and len(parts) == 1:
        recall, syntax = -1, parts[0]
    else:
        if len(parts) < 2 or combinable_head and len(parts) != 2:
            raise ValueError(f"invalid {name} declaration: {source}")
        recall, syntax = _parse_recall(parts[0]), ",".join(parts[1:])
    return tuple(
        ModeDeclaration(recall, literal)
        for literal in _get_mode_literals(syntax, source, unpool=unpool)
    )


def _get_body_mode_declaration(s: str) -> ModeDeclaration:
    (declaration,) = _get_mode_declarations(s, "#modeb")
    if isinstance(declaration.literal, ComparisonLiteral):
        literal = _prepare_body_comparison(declaration.literal, s)
        return declaration if literal is declaration.literal else ModeDeclaration(declaration.recall, literal)
    return declaration


def _prepare_body_comparison(
    literal: ComparisonLiteral, declaration: str
) -> ComparisonLiteral:
    bindings = tuple(binding for term in literal.terms for binding in mode_terms.bindings(term))
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
        for binding in mode_terms.bindings(term)
    ) and not prepared_outputs_are_safe and not _comparison_outputs_are_safe(prepared):
        raise ValueError(
            f"comparison outputs are not safe under Clingo grounding: {declaration}"
        )
    return prepared


def _implicit_assignment_output(literal: ComparisonLiteral) -> int | None:
    if len(literal.operators) != 1 or literal.operators[0] != "=":
        return None
    left, right = literal.terms
    left_bindings = len(mode_terms.bindings(left))
    if mode_terms.kind(left) == "variable" and mode_terms.contains_arithmetic(right):
        return 0
    if mode_terms.kind(right) == "variable" and mode_terms.contains_arithmetic(left):
        return left_bindings
    return None


def _with_binding_directions(
    literal: ComparisonLiteral, directions: tuple[str, ...]
) -> ComparisonLiteral:
    direction_iter = iter(directions)

    def update(term: ast.AST) -> ast.AST | None:
        if mode_terms.kind(term) != "variable":
            return None
        metadata = mode_terms.binding(term)
        return mode_terms.variable(metadata.type, next(direction_iter), metadata.label)

    return replace(literal, terms=tuple(mode_terms.transform(term, update) for term in literal.terms))


def _comparison_outputs_are_safe(literal: ComparisonLiteral) -> bool:
    bindings = tuple(
        binding for term in literal.terms for binding in mode_terms.bindings(term)
    )
    outputs = tuple(
        index for index, binding in enumerate(bindings) if binding.direction == "output"
    )
    if not outputs:
        return True
    labels: dict[str, str] = {}
    variable_names = tuple(
        labels.setdefault(binding.label, f"X{index}") if binding.label else f"X{index}"
        for index, binding in enumerate(bindings)
    )

    def validation_term(term: ast.AST) -> ast.AST | None:
        return mode_terms.fixed("0") if mode_terms.kind(term) == "constant" else None

    validation_literal = replace(
        literal,
        terms=tuple(
            mode_terms.transform(term, validation_term) for term in literal.terms
        ),
    )
    relation = validation_literal.instantiate(iter(variable_names))
    inputs = tuple(
        name
        for name, binding in zip(variable_names, bindings, strict=True)
        if binding.direction != "output"
    )

    def atom(name: str, arguments: Iterable[str]) -> ast.AST:
        return ast_literal(
            ast.SymbolicAtom(
                ast.Function(
                    LOCATION,
                    name,
                    [binding_term(value) for value in arguments],
                    False,
                )
            )
        )

    probe = (
        ast.Rule(LOCATION, atom("__gentians_input", ("0",)), []),
        ast.Rule(
            LOCATION,
            atom("__gentians_output", (variable_names[index] for index in outputs)),
            [*(atom("__gentians_input", (name,)) for name in inputs), relation],
        ),
    )
    messages: list[str] = []
    control = clingo.Control(logger=lambda _code, message: messages.append(message))
    try:
        add_program(control, probe)
        control.ground([("base", [])])
    except RuntimeError:
        return False
    return not any("unsafe" in message.lower() for message in messages)


def _get_condition_mode_declarations(source: str) -> tuple[ModeDeclaration, ...]:
    declarations = _get_mode_declarations(source, "#modec", unpool=True)
    if any(not isinstance(item.literal, AtomLiteral | ComparisonLiteral) for item in declarations):
        raise ValueError(f"#modec requires an atom or comparison literal: {source}")
    return declarations


def _get_combinable_head_declarations(
    source: str, name: str
) -> tuple[ModeDeclaration, ...]:
    declarations = _get_mode_declarations(source, name, unpool=True)
    for item in declarations:
        if not isinstance(item.literal, AtomLiteral):
            raise ValueError(f"{name} requires an atom literal: {source}")
        if any(mode_terms.contains_anonymous(term) for term in item.literal.arguments):
            raise ValueError(
                f"anonymous variables cannot occur in a head atom: {source}"
            )
    return declarations


def _get_head_declaration(s: str) -> HeadTemplate:
    parts = split_top_level_args(_directive_args(s, "#modeh"))
    if len(parts) < 2:
        raise ValueError(f"invalid #modeh declaration: {s}")
    try:
        recall = _parse_recall(parts[0])
    except ValueError:
        raise ValueError("complete head modes require recall 1") from None
    if recall != 1:
        raise ValueError("complete head modes require recall 1")
    syntax = ",".join(parts[1:]).strip()
    try:
        head = parse_rule(f"{syntax} :- __modeh_body.").head
    except ValueError as exc:
        raise ValueError(f"invalid #modeh declaration: {s}") from exc
    if head.ast_type in {ast.ASTType.Literal, ast.ASTType.ConditionalLiteral}:
        element = _head_literal(head, s)
        return HeadTemplate.normal(element)
    if head.ast_type in {ast.ASTType.Disjunction, ast.ASTType.Aggregate}:
        elements = tuple(
            _head_literal(element if element.condition else element.literal, s)
            for element in head.elements
        )
    elif head.ast_type == ast.ASTType.HeadAggregate:
        if head.function not in _AGGREGATE_NAMES:
            raise ValueError(f"unsupported #modeh aggregate head: {s}")
        elements = tuple(
            HeadAggregateElement(
                tuple(mode_terms.validate(term, s) for term in element.terms),
                _head_conclusion(element.condition.literal, s),
                _head_conditions(element.condition.condition, s),
            )
            for element in head.elements
        )
    else:
        raise ValueError(f"unsupported #modeh head form: {s}")
    form = head.update(elements=[])
    if head.ast_type in {ast.ASTType.Aggregate, ast.ASTType.HeadAggregate}:
        for guard in (head.left_guard, head.right_guard):
            if guard is not None:
                mode_terms.validate(guard.term, s)
    return HeadTemplate(form, elements)


def _head_literal(
    node: ast.AST, declaration: str
) -> AtomLiteral | BooleanLiteral | ComparisonLiteral | ConditionalLiteral:
    literal = _literal_from_ast(node, declaration)
    if not isinstance(
        literal, AtomLiteral | BooleanLiteral | ComparisonLiteral | ConditionalLiteral
    ):
        raise ValueError(f"unsupported head element: {declaration}")
    return literal


def _head_conclusion(
    node: ast.AST, declaration: str
) -> AtomLiteral | BooleanLiteral | ComparisonLiteral:
    literal = _head_literal(node, declaration)
    if isinstance(literal, ConditionalLiteral):
        raise ValueError(f"unsupported head condition: {declaration}")
    return literal


def _head_conditions(
    nodes: Iterable[ast.AST], declaration: str
) -> tuple[AtomLiteral | BooleanLiteral | ComparisonLiteral, ...]:
    return tuple(_head_conclusion(node, declaration) for node in nodes)


def _get_mode_atom(raw: str, declaration: str) -> AtomTemplate:
    (literal,) = _get_mode_literals(raw, declaration)
    if not isinstance(literal, AtomLiteral) or literal.default_negated:
        raise ValueError(f"invalid mode atom: {declaration}")
    return literal.atom


def _atom_from_ast(symbol: ast.AST, declaration: str) -> AtomTemplate:
    strong = False
    if symbol.ast_type == ast.ASTType.UnaryOperation and symbol.operator_type == ast.UnaryOperator.Minus:
        strong = True
        symbol = symbol.argument
    if symbol.ast_type == ast.ASTType.Pool:
        alternatives = tuple(_atom_from_ast(item, declaration) for item in symbol.arguments)
        first = alternatives[0]
        if any((item.name, item.strong, len(item.terms)) != (first.name, first.strong, len(first.terms)) for item in alternatives):
            raise ValueError(f"pooled mode atoms require one predicate: {declaration}")
        differing = tuple(index for index in range(len(first.terms)) if len({item.terms[index] for item in alternatives}) > 1)
        if len(differing) != 1:
            return AtomTemplate(first.name, first.terms, strong or first.strong, tuple(item.terms for item in alternatives))
        index = differing[0]
        arguments = list(first.terms)
        arguments[index] = ast.Pool(symbol.location, [item.terms[index] for item in alternatives])
        return AtomTemplate(first.name, tuple(arguments), strong or first.strong)
    if symbol.ast_type != ast.ASTType.Function or symbol.external or symbol.name == "not":
        raise ValueError(f"invalid mode atom: {declaration}")
    arguments = tuple(mode_terms.validate(argument, declaration) for argument in symbol.arguments)
    if any(not binding.direction for argument in arguments for binding in mode_terms.bindings(argument)):
        raise ValueError(f"invalid mode argument: {declaration}")
    return AtomTemplate(str(symbol.name), arguments, strong)


def _get_mode_literals(
    raw: str, declaration: str, *, unpool: bool = False
) -> tuple[AggregateLiteral | AtomLiteral | BooleanLiteral | ComparisonLiteral | ConditionalLiteral, ...]:
    try:
        rule = parse_rule(f":- {raw.strip()}.")
    except ValueError as exc:
        raise ValueError(f"invalid mode literal: {declaration}") from exc
    expanded = rule.unpool() if unpool else (rule,)
    if any(len(rule.body) != 1 for rule in expanded):
        raise ValueError(f"mode declaration requires one literal: {declaration}")
    return tuple(_literal_from_ast(rule.body[0], declaration) for rule in expanded)


def _literal_from_ast(
    node: ast.AST, declaration: str
) -> (
    AggregateLiteral
    | AtomLiteral
    | BooleanLiteral
    | ComparisonLiteral
    | ConditionalLiteral
):
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
        if any(
            not isinstance(condition, AtomLiteral | BooleanLiteral | ComparisonLiteral)
            for condition in conditions
        ):
            raise ValueError(f"unsupported conditional condition: {declaration}")
        flat_conditions = tuple(
            condition
            for condition in conditions
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
        operators = _COMPARISON_SYMBOLS
        return ComparisonLiteral(
            (
                mode_terms.validate(node.atom.term, declaration),
                *(
                    mode_terms.validate(guard.term, declaration)
                    for guard in node.atom.guards
                ),
            ),
            tuple(operators[guard.comparison] for guard in node.atom.guards),
            node.sign != ast.Sign.NoSign,
            double_negated=node.sign == ast.Sign.DoubleNegation,
        )
    if node.atom.ast_type != ast.ASTType.SymbolicAtom:
        raise ValueError(f"unsupported mode literal: {declaration}")
    return AtomLiteral(
        _atom_from_ast(node.atom.symbol, declaration),
        node.sign != ast.Sign.NoSign,
        node.sign == ast.Sign.DoubleNegation,
    )


def _aggregate_from_ast(node: ast.AST, declaration: str) -> AggregateLiteral:
    aggregate = node.atom

    functions = _AGGREGATE_NAMES
    try:
        function = functions[aggregate.function]
    except KeyError as exc:
        raise ValueError(f"unsupported aggregate function: {declaration}") from exc

    elements = []
    for element in aggregate.elements:
        tuple_terms = tuple(
            mode_terms.validate(term, declaration) for term in element.terms
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
            for binding in mode_terms.bindings(term):
                if binding.direction not in {"input", "any"}:
                    raise ValueError(
                        "aggregate tuple and condition variables require input or any "
                        f"direction: {declaration}"
                    )
        elements.append(AggregateElement(tuple_terms, tuple(conditions)))

    left, right = aggregate.left_guard, aggregate.right_guard
    for guard in (left, right):
        if guard is not None:
            mode_terms.validate(guard.term, declaration)
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
        for binding in mode_terms.bindings(guard.term):
            if binding.direction == "output" and guard is not literal.output_guard:
                raise ValueError(
                    f"aggregate output requires one equality result guard: {declaration}"
                )
    if literal.output_guard is not None:
        result = literal.output_guard.term
        if function in {"count", "sum", "sum+"} and mode_terms.binding(result).type != "numeric":
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
            for binding in mode_terms.bindings(term)
        ):
            raise ValueError(f"set aggregate elements cannot produce outputs: {declaration}")
        elements.append(AggregateElement(
            (), conditions, conclusion,
        ))
    left, right = aggregate.left_guard, aggregate.right_guard
    for guard in (left, right):
        if guard is not None:
            mode_terms.validate(guard.term, declaration)
    if any(
        binding.direction == "output"
        for guard in (left, right) if guard is not None
        for binding in mode_terms.bindings(guard.term)
    ):
        raise ValueError(f"set aggregate bounds cannot produce outputs: {declaration}")
    return AggregateLiteral(
        "set", tuple(elements), left, right,
        node.sign != ast.Sign.NoSign,
        node.sign == ast.Sign.DoubleNegation,
    )
