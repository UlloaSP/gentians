from collections import Counter
from itertools import combinations, permutations

from clingo import ast

from .closed_world_properties import ClosedWorldProperties
from ..language.asp import (
    AspProgram,
    Predicate,
)
from .extensions import (
    AstKey,
    GroundTuple,
    _ast_key,
    _closed_world_extensions,
    _defined_predicates,
    _integer_value,
    _type_domains,
    _unary_type_domains,
    _universal_predicates,
)

def _closed_world_properties(
    nodes: tuple[ast.AST, ...],
    predicate_arg_types: dict[tuple[str, int, int], str] | None = None,
    closed_body_predicates: set[Predicate] | None = None,
    statements: AspProgram | None = None,
) -> ClosedWorldProperties:
    extensions = _closed_world_extensions(nodes)
    property_program = statements or tuple(
        node for node in nodes if node.ast_type == ast.ASTType.Rule
    )
    symmetric: set[Predicate] = set()
    asymmetric: set[Predicate] = set()
    antisymmetric: set[Predicate] = set()
    acyclic: set[Predicate] = set()
    reflexive: set[Predicate] = set()
    strict_order: set[Predicate] = set()
    total_order: set[Predicate] = set()
    inverse: set[tuple[Predicate, Predicate]] = set()
    implies: set[tuple[Predicate, Predicate]] = set()
    equivalent: set[tuple[Predicate, Predicate]] = set()
    project_implies: set[tuple[Predicate, Predicate, tuple[int, ...]]] = set()
    disjoint_projection: set[tuple[Predicate, int, Predicate, int]] = set()
    tuple_mutex: set[tuple[Predicate, Predicate, tuple[int, ...]]] = set()
    mutex: set[tuple[Predicate, Predicate]] = set()
    complement: set[tuple[Predicate, Predicate]] = set()
    partitions: set[tuple[Predicate, ...]] = set()
    universal: set[Predicate] = set()
    empty: set[Predicate] = set()
    arg_equal: set[tuple[Predicate, int, int]] = set()
    arg_distinct: set[tuple[Predicate, int, int]] = set()
    functional: set[tuple[Predicate, int, int]] = set()
    functional_set: set[tuple[Predicate, tuple[int, ...], int]] = set()
    keys: set[tuple[Predicate, tuple[int, ...]]] = set()
    cardinality_upper: set[tuple[Predicate, int]] = set()
    transitive: set[Predicate] = set()
    tuple_universe_by_arity: dict[int, set[GroundTuple]] = {}
    (
        choice_functional,
        choice_functional_set,
        choice_keys,
        choice_project_implies,
        choice_cardinality_upper,
    ) = _choice_clause_properties(property_program)
    for predicate, tuples in extensions.items():
        tuple_universe_by_arity.setdefault(predicate[1], set()).update(tuples)

    for predicate, tuples in extensions.items():
        _collect_argument_properties(predicate, tuples, arg_equal, arg_distinct)
        _collect_functional_properties(predicate, tuples, functional)
        _collect_composite_functional_properties(predicate, tuples, functional_set)
        _collect_key_properties(predicate, tuples, keys)
        if predicate[1] == 2:
            reversed_tuples = {(right, left) for left, right in tuples}
            if tuples == reversed_tuples:
                symmetric.add(predicate)
            if tuples.isdisjoint(reversed_tuples):
                asymmetric.add(predicate)
            if all(
                left == right or (right, left) not in tuples for left, right in tuples
            ):
                antisymmetric.add(predicate)
            if _is_acyclic(tuples):
                acyclic.add(predicate)
            transitive_pred = _is_transitive(tuples)
            if transitive_pred:
                transitive.add(predicate)
            if _is_reflexive(tuples):
                reflexive.add(predicate)
            if tuples and tuples.isdisjoint(reversed_tuples) and transitive_pred:
                strict_order.add(predicate)
            if _is_total_order(tuples):
                total_order.add(predicate)

    for left, right in combinations(sorted(extensions), 2):
        left_tuples = extensions[left]
        right_tuples = extensions[right]
        if left[1] == right[1]:
            if left_tuples == right_tuples:
                equivalent.add((min(left, right), max(left, right)))
            elif left_tuples <= right_tuples:
                implies.add((left, right))
            elif right_tuples <= left_tuples:
                implies.add((right, left))
            if left_tuples.isdisjoint(right_tuples):
                universe = tuple_universe_by_arity[left[1]]
                if left_tuples | right_tuples == universe:
                    complement.add((min(left, right), max(left, right)))
                else:
                    mutex.add((min(left, right), max(left, right)))
            if left[1] == 2 and left_tuples == {(b, a) for a, b in right_tuples}:
                inverse.add((min(left, right), max(left, right)))
        _collect_disjoint_projections(
            left, left_tuples, right, right_tuples, disjoint_projection
        )
        _collect_projection_implications(
            left, left_tuples, right, right_tuples, project_implies
        )
        _collect_projection_implications(
            right, right_tuples, left, left_tuples, project_implies
        )
    if closed_body_predicates:
        _collect_tuple_mutex(extensions, closed_body_predicates, tuple_mutex)
    functional.update(choice_functional)
    functional_set.update(choice_functional_set)
    keys.update(choice_keys)
    project_implies.update(choice_project_implies)
    cardinality_upper.update(choice_cardinality_upper)
    _collect_clause_defined_properties(
        keys,
        functional,
        functional_set,
        arg_distinct,
        symmetric,
        property_program,
    )
    partitions.update(_partition_properties(extensions, tuple_universe_by_arity))
    if predicate_arg_types:
        type_domains = _type_domains(nodes, predicate_arg_types)
        unary_type_domains = _unary_type_domains(nodes, predicate_arg_types)
        universal.update(
            _universal_predicates(
                extensions,
                predicate_arg_types,
                type_domains,
                unary_type_domains,
            )
        )
    if closed_body_predicates:
        empty.update(
            predicate
            for predicate in closed_body_predicates
            if predicate not in extensions
            and predicate not in _defined_predicates(nodes)
        )
    asymmetric -= acyclic | strict_order | total_order
    acyclic -= strict_order
    antisymmetric -= acyclic | strict_order | total_order
    reflexive -= total_order | universal
    transitive -= strict_order | total_order
    mutex -= complement
    arg_distinct = _without_irreflexive_subsumed_arg_distinct(
        arg_distinct,
        asymmetric | acyclic | strict_order,
    )
    mutex = _without_partition_subsumed_mutex(mutex, partitions)
    functional = _without_key_subsumed_functional(functional, keys)
    functional_set = _without_key_subsumed_functional_set(functional_set, keys)
    functional_set = _without_subsumed_functional_set(functional_set, functional)

    return ClosedWorldProperties(
        frozenset(symmetric),
        frozenset(asymmetric),
        frozenset(antisymmetric),
        frozenset(acyclic),
        frozenset(reflexive),
        frozenset(strict_order),
        frozenset(total_order),
        frozenset(inverse),
        frozenset(implies),
        frozenset(equivalent),
        frozenset(project_implies),
        frozenset(disjoint_projection),
        frozenset(tuple_mutex),
        frozenset(mutex),
        frozenset(complement),
        frozenset(partitions),
        frozenset(universal),
        frozenset(empty),
        frozenset(arg_equal),
        frozenset(arg_distinct),
        frozenset(functional),
        frozenset(functional_set),
        frozenset(keys),
        frozenset(cardinality_upper),
        frozenset(transitive),
    )


def _choice_clause_properties(
    statements: AspProgram,
) -> tuple[
    set[tuple[Predicate, int, int]],
    set[tuple[Predicate, tuple[int, ...], int]],
    set[tuple[Predicate, tuple[int, ...]]],
    set[tuple[Predicate, Predicate, tuple[int, ...]]],
    set[tuple[Predicate, int]],
]:
    functional: set[tuple[Predicate, int, int]] = set()
    functional_set: set[tuple[Predicate, tuple[int, ...], int]] = set()
    keys: set[tuple[Predicate, tuple[int, ...]]] = set()
    project_implies: set[tuple[Predicate, Predicate, tuple[int, ...]]] = set()
    cardinality_upper: dict[Predicate, int] = {}

    def collect(node: ast.AST) -> None:
        if node.ast_type != ast.ASTType.Rule:
            return
        head = node.head
        if head.ast_type != ast.ASTType.Aggregate:
            return
        if not node.body and (upper := _aggregate_upper(head)) is not None:
            predicate = _choice_predicate(head.elements)
            if predicate is not None:
                cardinality_upper[predicate] = (
                    cardinality_upper.get(predicate, 0) + upper
                )
        predicate = _choice_predicate(head.elements)
        if predicate is not None:
            project_implies.update(
                _choice_project_implies(predicate, head.elements, node.body)
            )
        if not _aggregate_upper_at_most_one(head):
            return
        result = _choice_key(node.body, head.elements)
        if result is None:
            return
        predicate, inputs, outputs = result
        keys.add((predicate, inputs))
        for output in outputs:
            if len(inputs) == 1:
                functional.add((predicate, inputs[0], output))
            else:
                functional_set.add((predicate, inputs, output))

    for statement in statements:
        collect(statement)
    return (
        functional,
        functional_set,
        keys,
        project_implies,
        set(cardinality_upper.items()),
    )


def _choice_predicate(elements: list[ast.AST]) -> Predicate | None:
    predicates: set[Predicate] = set()
    for element in elements:
        atom = _positive_symbolic_atom(element.literal)
        if atom is None:
            return None
        predicates.add((atom[0], len(atom[1])))
    return next(iter(predicates)) if len(predicates) == 1 else None


def _aggregate_upper_at_most_one(head: ast.AST) -> bool:
    return _aggregate_upper(head) == 1


def _aggregate_upper(head: ast.AST) -> int | None:
    guard = head.right_guard
    if guard is None:
        return None
    return _numeric_term_value(guard.term)


def _numeric_term_value(term: ast.AST) -> int | None:
    return _integer_value(term, {})


def _choice_key(
    body: list[ast.AST],
    elements: list[ast.AST],
) -> tuple[Predicate, tuple[int, ...], tuple[int, ...]] | None:
    atoms: list[tuple[str, tuple[ast.AST, ...]]] = []
    for element in elements:
        atom = _positive_symbolic_atom(element.literal)
        if atom is None:
            return None
        atoms.append(atom)
    if not atoms:
        return None
    name = atoms[0][0]
    arity = len(atoms[0][1])
    if any(
        atom_name != name or len(arguments) != arity for atom_name, arguments in atoms
    ):
        return None

    body_vars = set().union(*(_term_variables(literal) for literal in body), set())
    input_args: list[int] = []
    output_args: list[int] = []
    for index in range(arity):
        terms = [arguments[index] for _, arguments in atoms]
        text = [_ast_key(term) for term in terms]
        variables = set().union(*(_term_variables(term) for term in terms), set())
        if len(set(text)) == 1 and variables <= body_vars:
            input_args.append(index)
        else:
            output_args.append(index)

    if not input_args or not output_args:
        return None
    return (name, arity), tuple(input_args), tuple(output_args)


def _choice_project_implies(
    predicate: Predicate,
    elements: list[ast.AST],
    body: list[ast.AST],
) -> set[tuple[Predicate, Predicate, tuple[int, ...]]]:
    result: set[tuple[Predicate, Predicate, tuple[int, ...]]] = set()
    element_vars: set[str] = set()
    for element in elements:
        atom = _positive_symbolic_atom(element.literal)
        if atom is None:
            continue
        for argument in atom[1]:
            element_vars.update(_term_variables(argument))
        for condition in element.condition:
            condition_atom = _positive_symbolic_atom(condition)
            if condition_atom is not None:
                _collect_atom_projection(predicate, atom[1], condition_atom, result)
    for literal in body:
        body_atom = _positive_symbolic_atom(literal)
        if body_atom is not None and _term_variables(literal) <= element_vars:
            continue
        if body_atom is not None:
            atom = _positive_symbolic_atom(elements[0].literal)
            if atom is not None:
                _collect_atom_projection(predicate, atom[1], body_atom, result)
    return result


def _collect_atom_projection(
    source: Predicate,
    source_args: tuple[ast.AST, ...],
    target: tuple[str, tuple[ast.AST, ...]],
    result: set[tuple[Predicate, Predicate, tuple[int, ...]]],
) -> None:
    projection: list[int] = []
    for target_arg in target[1]:
        target_text = _ast_key(target_arg)
        for index, source_arg in enumerate(source_args):
            if _ast_key(source_arg) == target_text:
                projection.append(index)
                break
        else:
            return
    result.add((source, (target[0], len(target[1])), tuple(projection)))


def _collect_clause_defined_properties(
    keys: set[tuple[Predicate, tuple[int, ...]]],
    functional: set[tuple[Predicate, int, int]],
    functional_set: set[tuple[Predicate, tuple[int, ...], int]],
    arg_distinct: set[tuple[Predicate, int, int]],
    symmetric: set[Predicate],
    statements: AspProgram,
) -> None:
    key_by_predicate = _key_sets_by_predicate(keys)
    clauses_by_head: dict[Predicate, list[ast.AST]] = {}

    def collect(node: ast.AST) -> None:
        if node.ast_type != ast.ASTType.Rule:
            return
        head = _positive_symbolic_atom(node.head)
        if head is None:
            return
        clauses_by_head.setdefault((head[0], len(head[1])), []).append(node)

    for statement in statements:
        collect(statement)

    for clauses in clauses_by_head.values():
        if len(clauses) != 1:
            continue
        node = clauses[0]
        head = _positive_symbolic_atom(node.head)
        if head is None:
            continue
        body_atoms = [
            atom for literal in node.body if (atom := _positive_symbolic_atom(literal))
        ]
        equalities = [_square_equality(literal) for literal in node.body]
        equalities = [equality for equality in equalities if equality is not None]
        if not equalities:
            continue
        for body_atom in body_atoms:
            for key in key_by_predicate.get((body_atom[0], len(body_atom[1])), ()):
                _propagate_key_through_clause(
                    head, body_atom, key, equalities, functional, functional_set, keys
                )

    for predicate, clauses in clauses_by_head.items():
        if predicate[1] == 2 and all(_clause_head_args_distinct(clause) for clause in clauses):
            arg_distinct.add((predicate, 0, 1))
        if predicate[1] == 2 and all(_clause_head_args_symmetric(clause) for clause in clauses):
            symmetric.add(predicate)


def _clause_head_args_distinct(node: ast.AST) -> bool:
    head = _positive_symbolic_atom(node.head)
    if head is None or len(head[1]) != 2:
        return False
    inequalities = {
        inequality
        for literal in node.body
        if (inequality := _inequality_terms(literal)) is not None
    }
    if not inequalities:
        return False
    return _terms_known_distinct(head[1][0], head[1][1], inequalities)


def _inequality_terms(literal: ast.AST) -> tuple[AstKey, AstKey] | None:
    terms = _comparison_terms(literal, ast.ComparisonOperator.NotEqual)
    if terms is None:
        return None
    return _ast_key(terms[0]), _ast_key(terms[1])


def _terms_known_distinct(
    left: ast.AST,
    right: ast.AST,
    inequalities: set[tuple[AstKey, AstKey]],
) -> bool:
    left_text = _ast_key(left)
    right_text = _ast_key(right)
    if (left_text, right_text) in inequalities or (right_text, left_text) in inequalities:
        return True
    left_parts = _tuple_parts(left)
    right_parts = _tuple_parts(right)
    return (
        left_parts is not None
        and right_parts is not None
        and len(left_parts) == len(right_parts)
        and any(
            _terms_known_distinct(a, b, inequalities)
            for a, b in zip(left_parts, right_parts)
        )
    )


def _tuple_parts(term: ast.AST) -> tuple[ast.AST, ...] | None:
    if term.ast_type != ast.ASTType.Function or term.name:
        return None
    parts = tuple(term.arguments)
    return parts if len(parts) > 1 else None


def _clause_head_args_symmetric(node: ast.AST) -> bool:
    head = _positive_symbolic_atom(node.head)
    if head is None or len(head[1]) != 2:
        return False
    mapping = _term_pair_mapping(head[1][0], head[1][1])
    if mapping is None:
        return False
    body = Counter(_canonical_literal_key(literal) for literal in node.body)
    swapped = Counter(
        _canonical_literal_key(_substitute_variables(literal, mapping))
        for literal in node.body
    )
    return body == swapped


def _term_pair_mapping(left: ast.AST, right: ast.AST) -> dict[str, str] | None:
    if _ast_key(left) == _ast_key(right):
        return {}
    if left.ast_type == right.ast_type == ast.ASTType.Variable:
        left_name = str(left.name)
        right_name = str(right.name)
        return {left_name: right_name, right_name: left_name}
    left_parts = _tuple_parts(left)
    right_parts = _tuple_parts(right)
    if left_parts is None or right_parts is None or len(left_parts) != len(right_parts):
        return None
    mapping: dict[str, str] = {}
    for left_part, right_part in zip(left_parts, right_parts):
        part_mapping = _term_pair_mapping(left_part, right_part)
        if part_mapping is None:
            return None
        for source, target in part_mapping.items():
            if source in mapping and mapping[source] != target:
                return None
            mapping[source] = target
    return mapping


class _VariableSubstitution(ast.Transformer):
    def __init__(self, mapping: dict[str, str]) -> None:
        self.mapping = mapping

    def visit_Variable(self, node: ast.AST) -> ast.AST:
        return node.update(name=self.mapping.get(str(node.name), str(node.name)))


def _substitute_variables(node: ast.AST, mapping: dict[str, str]) -> ast.AST:
    return _VariableSubstitution(mapping).visit(node)


def _canonical_literal_key(literal: ast.AST) -> object:
    terms = _comparison_terms(literal, ast.ComparisonOperator.NotEqual)
    if terms is not None:
        return "inequality", frozenset((_ast_key(terms[0]), _ast_key(terms[1])))
    return _ast_key(literal)


def _square_equality(literal: ast.AST) -> tuple[AstKey, AstKey] | None:
    terms = _comparison_terms(literal, ast.ComparisonOperator.Equal)
    if terms is None:
        return None
    output, expression = terms
    if (
        output.ast_type == ast.ASTType.Variable
        and expression.ast_type == ast.ASTType.BinaryOperation
        and expression.operator_type == ast.BinaryOperator.Multiplication
        and expression.left.ast_type == ast.ASTType.Variable
        and expression.right.ast_type == ast.ASTType.Variable
        and expression.left.name == expression.right.name
    ):
        return _ast_key(output), _ast_key(expression.left)
    return None


def _comparison_terms(
    literal: ast.AST, operator: ast.ComparisonOperator
) -> tuple[ast.AST, ast.AST] | None:
    if (
        literal.ast_type != ast.ASTType.Literal
        or literal.sign != ast.Sign.NoSign
        or literal.atom.ast_type != ast.ASTType.Comparison
        or len(literal.atom.guards) != 1
        or literal.atom.guards[0].comparison != operator
    ):
        return None
    return literal.atom.term, literal.atom.guards[0].term


def _propagate_key_through_clause(
    head: tuple[str, tuple[ast.AST, ...]],
    body_atom: tuple[str, tuple[ast.AST, ...]],
    body_key: set[int],
    equalities: list[tuple[AstKey, AstKey]],
    functional: set[tuple[Predicate, int, int]],
    functional_set: set[tuple[Predicate, tuple[int, ...], int]],
    keys: set[tuple[Predicate, tuple[int, ...]]],
) -> None:
    head_args = [_ast_key(argument) for argument in head[1]]
    body_args = [_ast_key(argument) for argument in body_atom[1]]
    head_predicate = (head[0], len(head[1]))
    determinant_vars = {body_args[arg] for arg in body_key}
    determinant_vars |= {
        square for square, root in equalities if root in determinant_vars
    }
    determinant_positions = tuple(
        index
        for index, argument in enumerate(head_args)
        if argument in determinant_vars
    )
    if not determinant_positions:
        return
    output_positions = tuple(
        index
        for index, argument in enumerate(head_args)
        if argument not in determinant_vars
    )
    if not output_positions:
        return
    keys.add((head_predicate, determinant_positions))
    for output in output_positions:
        if len(determinant_positions) == 1:
            functional.add((head_predicate, determinant_positions[0], output))
        else:
            functional_set.add((head_predicate, determinant_positions, output))


def _positive_symbolic_atom(literal: ast.AST) -> tuple[str, tuple[ast.AST, ...]] | None:
    if literal.ast_type != ast.ASTType.Literal or literal.sign != ast.Sign.NoSign:
        return None
    atom = literal.atom
    if atom.ast_type != ast.ASTType.SymbolicAtom:
        return None
    symbol = atom.symbol
    strong = False
    if symbol.ast_type == ast.ASTType.UnaryOperation:
        if symbol.operator_type != ast.UnaryOperator.Minus:
            return None
        strong = True
        symbol = symbol.argument
    if symbol.ast_type != ast.ASTType.Function or not symbol.name:
        return None
    name = f"-{symbol.name}" if strong else str(symbol.name)
    return name, tuple(symbol.arguments)


def _term_variables(node: ast.AST) -> set[str]:
    variables: set[str] = set()
    if node.ast_type == ast.ASTType.Variable:
        variables.add(str(node.name))
        return variables
    for key in node.child_keys:
        child = getattr(node, key)
        if isinstance(child, ast.AST):
            variables.update(_term_variables(child))
        elif isinstance(child, (list, ast.ASTSequence)):
            for item in child:
                if isinstance(item, ast.AST):
                    variables.update(_term_variables(item))
    return variables


def _collect_argument_properties(
    predicate: Predicate,
    tuples: set[GroundTuple],
    arg_equal: set[tuple[Predicate, int, int]],
    arg_distinct: set[tuple[Predicate, int, int]],
) -> None:
    for left, right in combinations(range(predicate[1]), 2):
        if len(tuples) > 1 and all(values[left] == values[right] for values in tuples):
            arg_equal.add((predicate, left, right))
        if all(values[left] != values[right] for values in tuples):
            arg_distinct.add((predicate, left, right))


def _collect_functional_properties(
    predicate: Predicate,
    tuples: set[GroundTuple],
    functional: set[tuple[Predicate, int, int]],
) -> None:
    for input_arg in range(predicate[1]):
        if len(tuples) < 2:
            continue
        for output_arg in range(predicate[1]):
            if input_arg == output_arg:
                continue
            outputs: dict[AstKey, AstKey] = {}
            valid = True
            for values in tuples:
                previous = outputs.setdefault(values[input_arg], values[output_arg])
                if previous != values[output_arg]:
                    valid = False
                    break
            if valid:
                functional.add((predicate, input_arg, output_arg))


def _collect_composite_functional_properties(
    predicate: Predicate,
    tuples: set[GroundTuple],
    functional_set: set[tuple[Predicate, tuple[int, ...], int]],
) -> None:
    arity = predicate[1]
    if arity < 3 or len(tuples) < 2:
        return
    for size in range(2, arity):
        for input_args in combinations(range(arity), size):
            for output_arg in range(arity):
                if output_arg in input_args:
                    continue
                outputs: dict[GroundTuple, AstKey] = {}
                valid = True
                for values in tuples:
                    key = tuple(values[arg] for arg in input_args)
                    previous = outputs.setdefault(key, values[output_arg])
                    if previous != values[output_arg]:
                        valid = False
                        break
                if valid:
                    functional_set.add((predicate, input_args, output_arg))


def _without_key_subsumed_functional(
    functional: set[tuple[Predicate, int, int]],
    keys: set[tuple[Predicate, tuple[int, ...]]],
) -> set[tuple[Predicate, int, int]]:
    key_sets = _key_sets_by_predicate(keys)
    return {
        (predicate, input_arg, output_arg)
        for predicate, input_arg, output_arg in functional
        if not any(key <= {input_arg} for key in key_sets.get(predicate, ()))
    }


def _without_key_subsumed_functional_set(
    functional_set: set[tuple[Predicate, tuple[int, ...], int]],
    keys: set[tuple[Predicate, tuple[int, ...]]],
) -> set[tuple[Predicate, tuple[int, ...], int]]:
    key_sets = _key_sets_by_predicate(keys)
    return {
        (predicate, input_args, output_arg)
        for predicate, input_args, output_arg in functional_set
        if not any(key <= set(input_args) for key in key_sets.get(predicate, ()))
    }


def _without_subsumed_functional_set(
    functional_set: set[tuple[Predicate, tuple[int, ...], int]],
    functional: set[tuple[Predicate, int, int]],
) -> set[tuple[Predicate, tuple[int, ...], int]]:
    single_inputs: dict[tuple[Predicate, int], set[int]] = {}
    for predicate, input_arg, output_arg in functional:
        single_inputs.setdefault((predicate, output_arg), set()).add(input_arg)

    composite_inputs: dict[tuple[Predicate, int], list[set[int]]] = {}
    for predicate, input_args, output_arg in functional_set:
        composite_inputs.setdefault((predicate, output_arg), []).append(set(input_args))

    return {
        (predicate, input_args, output_arg)
        for predicate, input_args, output_arg in functional_set
        if not _functional_set_is_subsumed(
            predicate,
            set(input_args),
            output_arg,
            single_inputs,
            composite_inputs,
        )
    }


def _functional_set_is_subsumed(
    predicate: Predicate,
    input_args: set[int],
    output_arg: int,
    single_inputs: dict[tuple[Predicate, int], set[int]],
    composite_inputs: dict[tuple[Predicate, int], list[set[int]]],
) -> bool:
    key = (predicate, output_arg)
    if input_args & single_inputs.get(key, set()):
        return True
    return any(other < input_args for other in composite_inputs.get(key, ()))


def _without_irreflexive_subsumed_arg_distinct(
    arg_distinct: set[tuple[Predicate, int, int]],
    irreflexive_sources: set[Predicate],
) -> set[tuple[Predicate, int, int]]:
    return {
        (predicate, left, right)
        for predicate, left, right in arg_distinct
        if not (
            predicate in irreflexive_sources
            and predicate[1] == 2
            and {left, right} == {0, 1}
        )
    }


def _without_partition_subsumed_mutex(
    mutex: set[tuple[Predicate, Predicate]],
    partitions: set[tuple[Predicate, ...]],
) -> set[tuple[Predicate, Predicate]]:
    partition_pairs = {
        tuple(sorted((left, right)))
        for group in partitions
        for left, right in combinations(group, 2)
    }
    return {pair for pair in mutex if tuple(sorted(pair)) not in partition_pairs}


def _key_sets_by_predicate(
    keys: set[tuple[Predicate, tuple[int, ...]]],
) -> dict[Predicate, list[set[int]]]:
    result: dict[Predicate, list[set[int]]] = {}
    for predicate, args in keys:
        result.setdefault(predicate, []).append(set(args))
    return result


def _collect_key_properties(
    predicate: Predicate,
    tuples: set[GroundTuple],
    keys: set[tuple[Predicate, tuple[int, ...]]],
) -> None:
    arity = predicate[1]
    if arity < 2 or len(tuples) < 2:
        return
    found: list[tuple[int, ...]] = []
    for size in range(1, arity):
        for args in combinations(range(arity), size):
            if any(set(existing) <= set(args) for existing in found):
                continue
            projected = {tuple(values[arg] for arg in args) for values in tuples}
            if len(projected) == len(tuples):
                found.append(args)
                keys.add((predicate, args))


def _collect_disjoint_projections(
    left: Predicate,
    left_tuples: set[GroundTuple],
    right: Predicate,
    right_tuples: set[GroundTuple],
    disjoint_projection: set[tuple[Predicate, int, Predicate, int]],
) -> None:
    if not left_tuples or not right_tuples:
        return
    for left_arg in range(left[1]):
        left_values = {values[left_arg] for values in left_tuples}
        for right_arg in range(right[1]):
            right_values = {values[right_arg] for values in right_tuples}
            if left_values.isdisjoint(right_values):
                if left[1] == right[1] == 1:
                    continue
                disjoint_projection.add((left, left_arg, right, right_arg))
                disjoint_projection.add((right, right_arg, left, left_arg))


def _partition_properties(
    extensions: dict[Predicate, set[GroundTuple]],
    tuple_universe_by_arity: dict[int, set[GroundTuple]],
) -> set[tuple[Predicate, ...]]:
    partitions: set[tuple[Predicate, ...]] = set()
    for arity, universe in tuple_universe_by_arity.items():
        predicates = [
            predicate
            for predicate, tuples in extensions.items()
            if predicate[1] == arity and tuples and tuples < universe
        ]
        for size in range(3, min(len(predicates), 6) + 1):
            for group in combinations(predicates, size):
                covered: set[GroundTuple] = set()
                valid = True
                for predicate in group:
                    tuples = extensions[predicate]
                    if covered & tuples:
                        valid = False
                        break
                    covered.update(tuples)
                if valid and covered == universe:
                    partitions.add(tuple(sorted(group)))
    return {
        group
        for group in partitions
        if not any(set(other) < set(group) for other in partitions)
    }


def _collect_tuple_mutex(
    extensions: dict[Predicate, set[GroundTuple]],
    closed_body_predicates: set[Predicate],
    tuple_mutex: set[tuple[Predicate, Predicate, tuple[int, ...]]],
) -> None:
    closed_extensions = {
        predicate: tuples
        for predicate, tuples in extensions.items()
        if predicate in closed_body_predicates and predicate[1] > 1
    }
    for left, left_tuples in closed_extensions.items():
        for right, right_tuples in closed_extensions.items():
            if left[1] != right[1]:
                continue
            for projection in permutations(range(left[1])):
                if projection == tuple(range(left[1])):
                    continue
                projected = {
                    tuple(values[arg] for arg in projection) for values in left_tuples
                }
                if projected.isdisjoint(right_tuples):
                    tuple_mutex.add((left, right, projection))


def _collect_projection_implications(
    source: Predicate,
    source_tuples: set[GroundTuple],
    target: Predicate,
    target_tuples: set[GroundTuple],
    project_implies: set[tuple[Predicate, Predicate, tuple[int, ...]]],
) -> None:
    if source[1] <= target[1] or not target_tuples:
        return
    for projection in permutations(range(source[1]), target[1]):
        projected = {
            tuple(values[arg] for arg in projection) for values in source_tuples
        }
        if projected <= target_tuples:
            project_implies.add((source, target, projection))


def _is_transitive(tuples: set[GroundTuple]) -> bool:
    if len(tuples) < 3:
        return False
    for left, middle in tuples:
        for other_middle, right in tuples:
            if middle == other_middle and (left, right) not in tuples:
                return False
    return True


def _is_reflexive(tuples: set[GroundTuple]) -> bool:
    domain = {value for row in tuples for value in row}
    return bool(domain) and all((value, value) in tuples for value in domain)


def _is_total_order(tuples: set[GroundTuple]) -> bool:
    domain = {value for row in tuples for value in row}
    if (
        len(domain) < 2
        or not _is_reflexive(tuples)
        or not _is_transitive(tuples)
        or any(left != right and (right, left) in tuples for left, right in tuples)
    ):
        return False
    for left, right in permutations(domain, 2):
        if (left, right) not in tuples and (right, left) not in tuples:
            return False
    return True


def _is_acyclic(tuples: set[GroundTuple]) -> bool:
    graph: dict[AstKey, set[AstKey]] = {}
    for left, right in tuples:
        graph.setdefault(left, set()).add(right)
        graph.setdefault(right, set())
    visiting: set[AstKey] = set()
    visited: set[AstKey] = set()

    def visit(node: AstKey) -> bool:
        if node in visiting:
            return False
        if node in visited:
            return True
        visiting.add(node)
        for next_node in graph[node]:
            if not visit(next_node):
                return False
        visiting.remove(node)
        visited.add(node)
        return True

    return bool(tuples) and all(visit(node) for node in graph)
