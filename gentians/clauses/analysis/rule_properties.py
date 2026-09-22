from collections import Counter

from clingo import ast

from ...language.asp import AspProgram, Predicate
from .ast_inspection import _integer_value
from .relation_properties import _key_sets_by_predicate


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
    return _integer_value(guard.term, {})


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
        text = list(terms)
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
        target_text = target_arg
        for index, source_arg in enumerate(source_args):
            if source_arg == target_text:
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


def _inequality_terms(literal: ast.AST) -> tuple[ast.AST, ast.AST] | None:
    terms = _comparison_terms(literal, ast.ComparisonOperator.NotEqual)
    if terms is None:
        return None
    return terms


def _terms_known_distinct(
    left: ast.AST,
    right: ast.AST,
    inequalities: set[tuple[ast.AST, ast.AST]],
) -> bool:
    if (left, right) in inequalities or (right, left) in inequalities:
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
    if left == right:
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
        return "inequality", frozenset(terms)
    return literal


def _square_equality(literal: ast.AST) -> tuple[ast.AST, ast.AST] | None:
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
        return output, expression.left
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
    equalities: list[tuple[ast.AST, ast.AST]],
    functional: set[tuple[Predicate, int, int]],
    functional_set: set[tuple[Predicate, tuple[int, ...], int]],
    keys: set[tuple[Predicate, tuple[int, ...]]],
) -> None:
    head_args = list(head[1])
    body_args = list(body_atom[1])
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
