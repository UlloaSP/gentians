from dataclasses import replace
from itertools import combinations, permutations, product
from random import Random

import clingo
from clingo import ast
import pytest

from gentians.clauses.analysis import ground_relations, inference
from gentians.clauses.analysis.relation_properties import _collect_dependency_properties, _collect_tuple_mutex
from gentians.clauses.analysis.rule_properties import _substitute_variables
from gentians.clauses.arithmetic_literal import ArithmeticLiteral, _linear_coefficients
from gentians.clauses.canonicalization.canonical_clause import CanonicalArithmeticClause
from gentians.clauses.canonicalization.clauses import _clause_from_reified
from gentians.clauses.canonicalization.expression import ArithmeticExpression
from gentians.clauses.canonicalization.expression_normalization import _mode_expression
from gentians.clauses.canonicalization.linear_constraint import LinearConstraint
from gentians.clauses.canonicalization.linear_normalization import _normalize_component
from gentians.clauses.mode_compiler import _clause_modes
from gentians.clauses.pruning import _known_head
from gentians.clauses.reified_clause import ReifiedClause
from gentians.clauses.reified_literal import ReifiedLiteral
from gentians.language import parse_text
from gentians.language.asp import add_program, parse_program, parse_rule, without_show
from gentians.language.ast_nodes import LOCATION


def test_dependencies_with_known_keys_preserve_all_context_facts():
    rng = Random(197)
    for arity in range(1, 6):
        universe = tuple(product(range(2), repeat=arity))
        for _ in range(25):
            rows = frozenset(row for row in universe if rng.randrange(3) == 0)
            predicate = "p", arity
            functional, composite, keys = set(), set(), set()
            _collect_dependency_properties(predicate, rows, functional, composite, keys)
            expected_functional, expected_composite, expected_keys = set(), set(), set()
            if len(rows) >= 2:
                for width in range(1, arity):
                    for inputs in combinations(range(arity), width):
                        for output in set(range(arity)) - set(inputs):
                            if all(left[output] == right[output] for left, right in product(rows, repeat=2)
                                   if all(left[arg] == right[arg] for arg in inputs)):
                                if width == 1:
                                    expected_functional.add((predicate, inputs[0], output))
                                else:
                                    expected_composite.add((predicate, inputs, output))
                        if (len({tuple(row[arg] for arg in inputs) for row in rows}) == len(rows)
                                and not any(set(prior) <= set(inputs) for _, prior in expected_keys)):
                            expected_keys.add((predicate, inputs))
            assert (functional, composite, keys) == (expected_functional, expected_composite, expected_keys)


def test_mutex_grouping_preserves_signed_predicates_and_empty_relations():
    rng = Random(41)
    for arity in (0, 1, 2, 3, 4):
        universe = tuple(product(range(2), repeat=arity))
        for _ in range(15):
            shared = frozenset(row for row in universe if rng.randrange(3) == 0)
            relations = {("p", arity): shared, ("-p", arity): shared, ("empty", arity): frozenset(),
                         ("q", arity): frozenset(row for row in universe if rng.randrange(3) == 0)}
            actual = set()
            _collect_tuple_mutex(relations, actual)
            expected = {
                (left, right, projection)
                for left, rows in relations.items() if arity > 1
                for projection in permutations(range(arity)) if projection != tuple(range(arity))
                for right, other in relations.items()
                if {tuple(row[arg] for arg in projection) for row in rows}.isdisjoint(other)
            }
            assert actual == expected


@pytest.mark.parametrize("source", [
    "p(1..4). -q(a). nested(f(1),\"a,b\"). #show missing/0.",
    "{p(1..4)}. q :- not p(1). -r :- p(1).",
    "p :- not q. q :- not p. r :- p. r :- q.",
    "p; q. :- p,q.",
    "", "p. :- p.", "#const n=3. p(1..n).", "#external p. q :- not p.",
])
def test_native_consequences_match_union_and_intersection_of_stable_models(source):
    program = parse_program(source)
    control = clingo.Control(["--models=0"], logger=lambda *_args: None)
    add_program(control, without_show(program))
    control.ground([("base", [])])
    atoms = [(atom.symbol, atom.literal) for atom in control.symbolic_atoms]
    models = []
    with control.solve(yield_=True) as handle:
        for model in handle:
            models.append({symbol for symbol, literal in atoms if model.is_true(literal)})
    expected = None if not models else (
        ground_relations._by_predicate(tuple(set().union(*models))),
        ground_relations._by_predicate(tuple(set.intersection(*models))),
    )
    assert ground_relations._consequences(program) == expected


def test_effective_consequence_reuse_is_exact_and_local_to_one_analysis(monkeypatch):
    original = inference._consequences
    calls = []

    def inspect(program):
        calls.append(program)
        return original(program)

    monkeypatch.setattr(inference, "_consequences", inspect)
    background = parse_program("d(1..3).")
    contexts = tuple(background + parse_program(f"p({i}) :- p({i}).") for i in range(4))
    learned = frozenset({("p", 1)})
    common = inference._closed_world_properties(contexts, learned)
    assert len(calls) == 1 and ("d", 1) in common.universal
    assert inference._closed_world_properties(contexts, learned) == common
    assert len(calls) == 2
    # Open facts are part of the lower-bound input; closed contexts never merge.
    different = (parse_program("d(1). p(1)."), parse_program("d(2). p(3)."))
    result = inference._closed_world_properties(different, learned)
    assert len(calls) == 4 and (("d", 1), ("p", 1)) not in result.implies


def test_effective_consequence_cache_keeps_unsat_and_has_bounded_history(monkeypatch):
    original = inference._consequences
    calls = []

    def inspect(program):
        calls.append(program)
        return original(program)

    monkeypatch.setattr(inference, "_consequences", inspect)
    learned = frozenset({("p", 1)})
    unsat = parse_program("d. :- d.")
    contexts = tuple(unsat + parse_program(f"p({i}) :- p({i}).") for i in range(3))
    assert inference._closed_world_properties(contexts, learned) == inference.ClosedWorldProperties.none()
    assert len(calls) == 1
    distinct = tuple(parse_program(f"d({i}). p({i}) :- p({i}).") for i in range(9))
    inference._closed_world_properties((*distinct, distinct[0]), learned)
    assert len(calls) == 11


@pytest.mark.parametrize("relation", ["eq", "le", "lt", "ne"])
@pytest.mark.parametrize("pivot_sign", [-1, 1])
def test_zero_factor_rows_preserve_exact_integer_normalization(relation, pivot_sign):
    constraints = (LinearConstraint((pivot_sign, -1, 0, 0), "eq"),
                   LinearConstraint((0, 0, 1, -1), relation),
                   LinearConstraint((1, 0, 0, -1), relation))
    actual = _normalize_component(constraints, frozenset({0}), 4)
    reduced = (LinearConstraint((0, 0, 1, -1), relation),
               LinearConstraint((0, pivot_sign, 0, -1), relation))
    assert actual == _normalize_component(reduced, frozenset(), 4)


def test_variable_caches_preserve_hash_equality_empty_sets_and_remapping():
    for value in (ArithmeticExpression("*", (ArithmeticExpression.var(2), ArithmeticExpression.var(4))),
                  LinearConstraint((0, 0, 1, 0, -2), "eq")):
        prior_hash = hash(value)
        assert value.variables == frozenset({2, 4})
        assert value.variables is value.variables
        assert hash(value) == prior_hash and value == replace(value)
        remapped = value.remap({2: 1, 4: 0}, 5) if isinstance(value, LinearConstraint) else value.remap({2: 1, 4: 0})
        assert remapped.variables == frozenset({0, 1}) and value.variables == frozenset({2, 4})
    for empty in (ArithmeticExpression.const(0), LinearConstraint((0, 0), "eq")):
        assert empty.variables == frozenset() and empty.variables is empty.variables


@pytest.mark.parametrize("head,heads,deps,cost", [
    ("p(var(node,any)):d(var(node,any)),not -q(var(node,input))", {("p", 1)}, {("d", 1), ("-q", 1)}, 2),
    ("not -p(var(node,any)):d(var(node,any))", set(), {("-p", 1), ("d", 1)}, 1),
    ("#count{var(node,any,x):p(var(node,any,x)):d(var(node,any,x))}=1", {("p", 1)}, {("d", 1)}, 1),
    ("#false", set(), set(), 0), ("{}", set(), set(), 0), ("p;not -p", {("p", 0)}, {("-p", 0)}, 0),
])
def test_precomputed_head_metadata_preserves_providers_dependencies_and_cost(head, heads, deps, cost):
    modes = _clause_modes(parse_text(f"#maxhl(2). #modeh(1,{head})."))
    lookup = {mode.id: mode for mode in modes}
    reified = ReifiedClause(tuple(ReifiedLiteral("head", slot, mode.id, tuple(range(len(mode.bindings))))
                                 for slot, mode in enumerate(modes) if mode.section == "head"), ())
    statement = CanonicalArithmeticClause(reified.head, (), ()).instantiate(lookup)
    clause = _clause_from_reified(str(statement), statement, reified, lookup)
    assert (clause.heads, clause.deps, clause.body_literals) == (frozenset(heads), frozenset(deps), cost)


def test_substitution_reuses_unchanged_native_nodes_and_preserves_source():
    node = parse_rule("p(X) :- q(Y),not -r(X),s(f(Y),1).")
    original = str(node)
    for mapping in ({}, {"Missing": "Z"}, {"X": "X", "Y": "Y"}):
        assert _substitute_variables(node, mapping) is node
    changed = _substitute_variables(node, {"X": "Z"})
    assert changed == parse_rule("p(Z) :- q(Y),not -r(Z),s(f(Y),1).")
    assert str(node) == original


def test_mode_expression_and_coefficient_walks_support_deep_terms_in_binding_order():
    mode = _clause_modes(parse_text("#modeb(1,var(numeric,input)*var(numeric,input)=var(numeric,output))."))[0]
    assert isinstance(mode.literal, ArithmeticLiteral)
    leaf = mode.literal.expression.left
    deep = leaf
    for _ in range(1400):
        deep = ast.UnaryOperation(LOCATION, ast.UnaryOperator.Minus, deep)
    template = replace(mode.literal, expression=mode.literal.expression.update(left=deep))
    compiled = replace(mode, literal=template)
    known = {4: ArithmeticExpression.var(4), 2: ArithmeticExpression.var(2)}
    expression = _mode_expression(ReifiedLiteral("body", 0, compiled.id, (4, 2, 9)), compiled, known)
    assert expression.variables == frozenset({4, 2}) and expression.arguments[1] is known[2]
    left = expression.arguments[0]
    for _ in range(1400):
        assert left.operator == "neg"
        left = left.arguments[0]
    assert left is known[4]
    # Unsupported fixed terms still return None after a deep additive prefix.
    deep = leaf
    for _ in range(1400):
        deep = ast.BinaryOperation(LOCATION, ast.BinaryOperator.Plus, deep, ast.SymbolicTerm(LOCATION, clingo.Number(1)))
    assert _linear_coefficients(deep, 1) is None
    simple = ast.BinaryOperation(LOCATION, ast.BinaryOperator.Minus, leaf,
                                ast.BinaryOperation(LOCATION, ast.BinaryOperator.Minus, leaf, leaf))
    assert _linear_coefficients(simple, 2) == (2, -2, 2)


def test_known_head_walk_supports_deep_guards_and_rejects_unknown_theory_heads():
    guard = ast.SymbolicTerm(LOCATION, clingo.Number(1))
    for _ in range(1400):
        guard = ast.Function(LOCATION, "f", [guard], False)
    head = ast.Aggregate(LOCATION, ast.Guard(ast.ComparisonOperator.LessEqual, guard), [], None)
    assert _known_head(head)
    theory = ast.TheoryAtom(LOCATION, ast.Function(LOCATION, "t", [], False), [], None)
    assert not _known_head(theory)
