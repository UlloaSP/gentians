from collections.abc import Iterable
from dataclasses import replace

import clingo
from clingo import ast

from . import terms as mode_terms
from .asp import AspProgram, add_program, parse_rule, split_top_level_args, validate_task_program
from .ast_nodes import (
    AGGREGATE_FUNCTIONS,
    COMPARISON_OPERATORS,
    LOCATION,
    binding_term,
    binding_terms,
    literal as ast_literal,
)
from .grammar import SourceError, _directive_args, _parse_recall, source_position
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
    source: str, name: str, *, unpool: bool = False,
    cache: dict[tuple[str, str], tuple[ModeDeclaration, ...]] | None = None,
) -> tuple[ModeDeclaration, ...]:
    payload = _directive_args(source, name)
    parts = split_top_level_args(payload)
    combinable_head = name in {"#modeha", "#modehd"}
    if combinable_head and len(parts) == 1:
        recall, offset = -1, len(name) + 1 + parts[0][0]
    else:
        if len(parts) < 2 or combinable_head and len(parts) != 2:
            raise ValueError(f"invalid {name} declaration: {source}")
        recall = _parse_recall(payload[slice(*parts[0])])
        offset = len(name) + 1 + parts[1][0]
    syntax = source[offset:-2]
    key = name, syntax
    if cache is not None and key in cache:
        return tuple(item.with_recall(recall) for item in cache[key])
    literals = _get_mode_literals(syntax, source, offset=offset, unpool=unpool)
    line, column = source_position(source, offset)
    try:
        declarations = tuple(ModeDeclaration(recall, literal) for literal in literals)
    except SourceError as error:
        raise error.with_origin(line, column - 3) from None
    if name == "#modec" and any(not isinstance(item.literal, AtomLiteral | ComparisonLiteral) for item in declarations):
        raise ValueError(f"#modec requires an atom or comparison literal: {source}")
    if combinable_head:
        for item in declarations:
            if not isinstance(item.literal, AtomLiteral):
                raise ValueError(f"{name} requires an atom literal: {source}")
            if any(mode_terms.contains_anonymous(term) for term in item.literal.arguments):
                raise ValueError(f"anonymous variables cannot occur in a head atom: {source}")
    if cache is not None:
        cache[key] = declarations
    return declarations


def _get_body_mode_declaration(
    s: str, cache: dict[tuple[str, str], tuple[ModeDeclaration, ...]] | None = None,
) -> ModeDeclaration:
    (declaration,) = _get_mode_declarations(s, "#modeb", cache=cache)
    return declaration


def _prepare_body_comparison(
    literal: ComparisonLiteral, declaration: str,
    constants: dict[str, tuple[ast.AST, ...]], safety: dict[ComparisonLiteral, bool],
    definitions: AspProgram = (),
) -> ComparisonLiteral:
    def outputs_are_safe(candidate: ComparisonLiteral) -> bool:
        for concrete in candidate.concretizations(constants):
            result = safety.get(concrete)
            if result is None:
                result = safety[concrete] = _comparison_outputs_are_safe(concrete, definitions)
            if not result:
                return False
        return True

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
        if not literal.default_negated:
            inferred_outputs = tuple(
                binding.direction or "output" for binding in bindings
            )
            all_outputs = _with_binding_directions(literal, inferred_outputs)
            if outputs_are_safe(all_outputs):
                prepared = all_outputs
                prepared_outputs_are_safe = True
            elif (assignment := _implicit_assignment_output(literal)) in unspecified:
                directions = list(inferred_inputs)
                directions[assignment] = "output"
                candidate = _with_binding_directions(literal, tuple(directions))
                if outputs_are_safe(candidate):
                    prepared = candidate
                    prepared_outputs_are_safe = True
        if not prepared_outputs_are_safe:
            prepared = _with_binding_directions(literal, inferred_inputs)
        prepared = replace(
            prepared, fully_implicit_directions=fully_implicit
        )

    if any(
        binding.direction == "output"
        for term in prepared.terms
        for binding in mode_terms.bindings(term)
    ) and not prepared_outputs_are_safe and not outputs_are_safe(prepared):
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
        direction = next(direction_iter)
        if direction == metadata.direction:
            return term
        values = list(term.arguments)
        location = values[1].location if len(values) > 1 else term.location
        replacement = mode_terms.fixed(direction).update(location=location)
        if len(values) > 1:
            values[1] = replacement
        else:
            values.append(replacement)
        return term.update(arguments=values)

    return replace(literal, terms=tuple(mode_terms.transform(term, update) for term in literal.terms))


def _comparison_outputs_are_safe(literal: ComparisonLiteral, definitions: AspProgram = ()) -> bool:
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

    relation = literal.instantiate(binding_terms(variable_names))
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
        add_program(control, (*definitions, *probe))
        control.ground([("base", [])])
    except RuntimeError:
        return False
    return not any("unsafe" in message.lower() for message in messages)


def _get_condition_mode_declarations(
    source: str, cache: dict[tuple[str, str], tuple[ModeDeclaration, ...]] | None = None,
) -> tuple[ModeDeclaration, ...]:
    return _get_mode_declarations(source, "#modec", unpool=True, cache=cache)


def _get_combinable_head_declarations(
    source: str, name: str, cache: dict[tuple[str, str], tuple[ModeDeclaration, ...]] | None = None,
) -> tuple[ModeDeclaration, ...]:
    return _get_mode_declarations(source, name, unpool=True, cache=cache)


def _get_head_declaration(s: str) -> HeadTemplate:
    payload = _directive_args(s, "#modeh")
    parts = split_top_level_args(payload)
    if len(parts) < 2:
        raise ValueError(f"invalid #modeh declaration: {s}")
    try:
        recall = _parse_recall(payload[slice(*parts[0])])
    except ValueError:
        raise ValueError("complete head modes require recall 1") from None
    if recall != 1:
        raise ValueError("complete head modes require recall 1")
    offset = len("#modeh(") + parts[1][0]
    syntax = s[offset:-2]
    line, column = source_position(s, offset)
    try:
        rule = parse_rule(f"{syntax} :- __modeh_body.", line, column)
        validate_task_program(syntax, (rule,), line, column)
        head = rule.head
    except ValueError as exc:
        detail = exc.message if isinstance(exc, SourceError) else str(exc)
        message = f"invalid #modeh declaration: {s}: {detail}"
        if isinstance(exc, SourceError):
            end = source_position(s, offset + len(syntax))
            line, column = min((exc.line, exc.column or 1), end)
            raise SourceError(line, message, column=column) from None
        raise ValueError(message) from None
    try:
        return _head_from_ast(head, s)
    except SourceError as error:
        raise error.with_origin(line, column) from None


def _head_from_ast(head: ast.AST, s: str) -> HeadTemplate:
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


def _get_mode_atom(raw: str, declaration: str, offset: int) -> AtomTemplate:
    (literal,) = _get_mode_literals(raw, declaration, offset=offset)
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
    raw: str, declaration: str, *, offset: int, unpool: bool = False
) -> tuple[AggregateLiteral | AtomLiteral | BooleanLiteral | ComparisonLiteral | ConditionalLiteral, ...]:
    try:
        line, column = source_position(declaration, offset)
        rule = parse_rule(f":- {raw}.", line, column - 3)
        validate_task_program(raw, (rule,), line, column - 3)
    except ValueError as exc:
        detail = exc.message if isinstance(exc, SourceError) else str(exc)
        message = f"invalid mode literal: {declaration}: {detail}"
        if isinstance(exc, SourceError):
            end = source_position(declaration, offset + len(raw))
            line, column = min((exc.line, exc.column or 1), end)
            raise SourceError(line, message, column=column) from None
        raise ValueError(message) from None
    expanded = rule.unpool() if unpool else (rule,)
    if any(len(rule.body) != 1 for rule in expanded):
        raise ValueError(f"mode declaration requires one literal: {declaration}")
    try:
        return tuple(_literal_from_ast(rule.body[0], declaration) for rule in expanded)
    except SourceError as error:
        raise error.with_origin(line, column - 3) from None


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
    output_guard = literal.output_guard
    if node.sign != ast.Sign.NoSign and output_guard is not None:
        raise ValueError(f"negated aggregates cannot produce an output: {declaration}")
    for guard in (left, right):
        if guard is None:
            continue
        for binding in mode_terms.bindings(guard.term):
            if binding.direction == "output" and guard is not output_guard:
                raise ValueError(
                    f"aggregate output requires one equality result guard: {declaration}"
                )
    if output_guard is not None:
        result = output_guard.term
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
