from collections import Counter
from itertools import combinations, combinations_with_replacement, permutations, product
import json
import os
from random import Random
import subprocess
import sys

import clingo
import pytest

from gentians.arguments import Arguments
from gentians.clauses import generator, mode_compiler, mode_facts, reified_clause
from gentians.clauses.analysis import ground_relations, inference, rule_properties, task as task_analysis
from gentians.clauses.analysis.inference import _closed_world_properties
from gentians.clauses.analysis.relation_properties import (
    _collect_projection_implications,
    _collect_dependency_properties,
    _collect_tuple_mutex,
    _is_reflexive,
    _is_total_order,
    _is_transitive,
    _is_acyclic,
    _binary_successors,
    _position_values,
    _partition_properties,
)
from gentians.clauses.canonicalization import arithmetic, expression as expressions
from gentians.clauses.canonicalization import expression_constraint, expression_normalization
from gentians.clauses.canonicalization import linear_constraint as linear_constraints
from gentians.clauses.canonicalization.arithmetic_system import ArithmeticSystem
from gentians.clauses.canonicalization.clauses import ClauseCanonicalizer
from gentians.clauses.canonicalization.expression import ArithmeticExpression
from gentians.clauses.canonicalization.expression_constraint import ExpressionConstraint
from gentians.clauses.canonicalization.expression_normalization import _term_comparison
from gentians.clauses.canonicalization.linear_constraint import LinearConstraint
from gentians.clauses.canonicalization.linear_normalization import (
    _comparison_linear_template,
    _linear_assignment_expression,
    _orient_linear_constraints,
    _normalize_component,
)
from gentians.clauses.clause_space import ClauseSpace
from gentians.clauses.reified_clause import ReifiedClause, instantiate_head
from gentians.clauses.reified_literal import ReifiedLiteral
from gentians.language import parse_text, terms as mode_terms
from gentians.language.asp import parse_program, parse_rule
from gentians.language.ir.comparison_literal import ComparisonLiteral
from gentians import timing


@pytest.mark.parametrize("coefficient", [1, -1, 2, -2, 1000, -1000, 2**53 + 1, -(2**53 + 1)])
@pytest.mark.parametrize("divisor", [1, -1])
def test_linear_assignments_preserve_exact_integer_coefficients(coefficient, divisor):
    expression = _linear_assignment_expression(LinearConstraint((coefficient, divisor), "eq"), 1)

    def evaluate(node, value):
        if node.variable is not None:
            return value
        if node.constant is not None:
            return node.constant
        left, right = (evaluate(child, value) for child in node.arguments)
        return {"+": lambda: left + right, "-": lambda: left - right, "*": lambda: left * right, "scale": lambda: left * right}[node.operator]()

    for value in (-7, 0, 9):
        assert evaluate(expression, value) == -coefficient * value // divisor
    if abs(coefficient) > 2:
        pending = [expression]
        nodes = 0
        while pending:
            node = pending.pop()
            nodes += 1
            pending.extend(node.arguments)
        assert nodes <= 9


@pytest.mark.parametrize("coefficient", [1000, -1000])
def test_compact_assignments_have_the_same_clingo_models(coefficient):
    expression = _linear_assignment_expression(LinearConstraint((coefficient, -1), "eq"), 1)
    control = clingo.Control(["0"])
    control.add(f"d(-3..3). result(V0,V1) :- d(V0), {expression.render()} = V1.")
    control.ground([("base", [])])
    rows = []
    control.solve(on_model=lambda model: rows.extend(
        tuple(value.number for value in symbol.arguments)
        for symbol in model.symbols(atoms=True) if symbol.name == "result"
    ))
    assert set(rows) == {(value, coefficient * value) for value in range(-3, 4)}


@pytest.mark.parametrize("coefficients", [(3, -1), (-4, -1), (3, -4, 1), (-3, 4, -1)])
def test_compact_linear_assignments_preserve_repeated_addition_canonical_keys(coefficients):
    output = len(coefficients) - 1
    expression = _linear_assignment_expression(LinearConstraint(coefficients, "eq"), output)
    positive, negative = [], []
    for variable, coefficient in enumerate(coefficients[:-1]):
        scaled = -coefficient // coefficients[output]
        (positive if scaled > 0 else negative).extend([ArithmeticExpression.var(variable)] * abs(scaled))
    repeated = positive[0] if positive else ArithmeticExpression.const(0)
    for term in positive[1:]:
        repeated = ArithmeticExpression("+", (repeated, term))
    for term in negative:
        repeated = ArithmeticExpression("-", (repeated, term))
    assert expression.key == repeated.key
    substitution = {0: ArithmeticExpression("+", (ArithmeticExpression.var(7), ArithmeticExpression.var(8)))}
    assert expression.substitute(substitution).key == repeated.substitute(substitution).key
    product = ArithmeticExpression("*", (ArithmeticExpression.const(3), ArithmeticExpression.var(0)))
    assert product.key != ArithmeticExpression("scale", product.arguments).key


def test_derived_coefficients_larger_than_native_integers_generate_valid_asp():
    task = parse_text("""
        #maxv(2). #maxbl(2). #maxhl(1). p(1).
        #modeh(1,q(var(numeric,input,y))).
        #modeb(1,p(var(numeric,output,x))).
        #modeb(1,1073741824*2*var(numeric,input,x)=var(numeric,output,y)).
    """)
    space = generator.generate_clause_space(task, Arguments())
    assignments = [entry for entry in space.entries if entry.heads and entry.body_literals == 2]
    assert assignments
    for entry in assignments:
        control = clingo.Control(["0"])
        control.add("p(1). " + entry.text)
        control.ground([("base", [])])
        models = []
        control.solve(on_model=lambda model: models.append({str(symbol) for symbol in model.symbols(atoms=True)}))
        assert models == [{"p(1)", "q(-2147483648)"}]


def test_deep_expressions_support_hash_equality_keys_remapping_and_native_ast():
    left = ArithmeticExpression.var(0)
    right = ArithmeticExpression.var(0)
    for _ in range(1400):
        left = ArithmeticExpression("function:f", (left,))
        right = ArithmeticExpression("function:f", (right,))
    assert left == right
    assert hash(left) == hash(right)
    assert {left: "same"}[right] == "same"
    assert left.key == right.key
    assert left.variables == frozenset({0})
    assert left.remap({0: 0}) is left
    changed = left.remap({0: 3})
    assert changed.variables == frozenset({3})
    assert changed.render() == "f(" * 1400 + "V3" + ")" * 1400
    fixed = left.substitute({0: ArithmeticExpression.fixed("a")})
    assert fixed.variables == frozenset()
    assert fixed.render() == "f(" * 1400 + "a" + ")" * 1400


def test_deep_comparison_decoding_preserves_left_to_right_binding_order():
    nested = "f(" * 1200 + "var(numeric,input)" + ")" * 1200
    task = parse_text(f"#modeb(1,({nested},var(numeric,input)) < (1,2)).")
    comparison = task.language_bias_body[0].literal
    assert isinstance(comparison, ComparisonLiteral)
    mode = mode_compiler._clause_modes(task)[0]
    relation = _term_comparison(ReifiedLiteral("body", 0, mode.id, (7, 3)), mode)
    assert relation.variables == frozenset({7, 3})
    assert relation.terms[0].render() == "(" + "f(" * 1200 + "V7" + ")" * 1200 + ",V3)"
    assert relation.remap({7: 0, 3: 1}).variables == frozenset({0, 1})
    assert hash(relation.key)


def test_deep_linear_template_and_full_clause_generation():
    nested = "-(" * 1200 + "var(numeric,input)" + ")" * 1200
    task = parse_text(f"""
        d(1). #maxv(2). #maxbl(2).
        #modeh(1,target(var(numeric,input))).
        #modeb(1,d(var(numeric,output))).
        #modeb(1,{nested} = var(numeric,output)).
    """)
    comparison = task.language_bias_body[1].literal
    assert isinstance(comparison, ComparisonLiteral)
    assert _comparison_linear_template(comparison) == ((1, -1), 0)
    space = generator.generate_clause_space(task, Arguments())
    assert "target(V0) :- d(V0)." in space.clauses


@pytest.mark.parametrize("groups,capacities", [
    (((0,), (1,), (2,)), (1, 2, 0)),
    (((0,), (0,), (1,)), (2, 1)),
    (((0, 2), (0, 3), (1, 4)), (3, 2, 1, 2, 1)),
    ((), ()),
])
@pytest.mark.parametrize("length", range(6))
def test_bounded_combinations_preserve_recall_constraints_and_lexicographic_order(groups, capacities, length):
    expected = []
    for indices in combinations_with_replacement(range(len(groups)), length):
        counts = Counter(group for index in indices for group in groups[index])
        if all(count <= capacities[group] for group, count in counts.items()):
            expected.append(indices)
    assert list(mode_compiler._bounded_combinations(groups, capacities, length)) == expected


def test_condition_expansion_shares_recall_across_constants_and_rejects_ground_duplicates():
    task = parse_text("""
        #maxbl(3). #constant(k,a). #constant(k,b).
        #modeb(1,p(var(node,input))).
        #modec(2,c(const(k),var(node,input))). #modec(2,flag).
    """)
    conditions = mode_compiler._Conditions(task)
    conclusion = task.language_bias_body[0].literal
    variants = conditions.expand(conclusion)
    assert len(variants) == 12
    assert conditions.expand(conclusion) is variants
    for variant in variants[1:]:
        assert variant.condition_groups.count(0) <= 2
        assert variant.condition_groups.count(1) <= 1


def test_condition_preparation_and_variants_are_shared_across_mode_sections(monkeypatch):
    task = parse_text("""
        #maxv(1). #maxbl(2). #maxhl(2).
        #modeh(1,p(var(node,input))). #modeha(2,p(var(node,input))).
        #modehd(2,p(var(node,input))). #modeb(2,p(var(node,input))).
        #modec(1,c(var(node,input))).
    """)
    prepared = []
    expanded = []
    original_init = mode_compiler._Conditions.__init__
    original_expand = mode_compiler._Conditions._expand

    def prepare(self, task):
        prepared.append(task)
        original_init(self, task)

    def expand(self, conclusion):
        expanded.append(conclusion)
        return original_expand(self, conclusion)

    monkeypatch.setattr(mode_compiler._Conditions, "__init__", prepare)
    monkeypatch.setattr(mode_compiler._Conditions, "_expand", expand)
    modes = mode_compiler._clause_modes(task)
    assert modes
    assert prepared == [task]
    assert expanded == [task.language_bias_body[0].literal]


def test_open_predicate_worklist_inspects_rules_once_and_preserves_signed_predicates(monkeypatch):
    source = "\n".join(f"p{i + 1}(X) :- not p{i}(X)." for i in reversed(range(180)))
    program = parse_program(source + "\n-p0(a). q(X) :- -p0(X).")
    inspected = []
    original = ground_relations.clause_predicates

    def inspect(rule):
        inspected.append(rule)
        return original(rule)

    monkeypatch.setattr(ground_relations, "clause_predicates", inspect)
    world = ground_relations._closed_world(program, frozenset({("p0", 1)}))
    assert world is not None
    assert world.open == frozenset((f"p{i}", 1) for i in range(181))
    assert world.extension(("-p0", 1)) == frozenset({("a",)})
    assert world.extension(("q", 1)) == frozenset({("a",)})
    assert len(inspected) == 182


def test_indexed_projection_properties_match_tuple_semantics_including_empty_relations():
    extensions = {
        ("p", 3): frozenset({(1, 2, 3), (2, 3, 4)}),
        ("q", 3): frozenset({(3, 2, 1)}),
        ("r", 2): frozenset({(1, 2), (2, 3)}),
        ("uniform", 3): frozenset({(1, 1, 1), (2, 2, 2)}),
        ("uniform_two", 2): frozenset({(1, 1), (2, 2)}),
        ("empty", 3): frozenset(),
        ("one", 1): frozenset({(1,), (2,)}),
        ("true", 0): frozenset({()}),
    }
    mutex = set()
    implies = set()
    _collect_tuple_mutex(extensions, mutex)
    _collect_projection_implications(extensions, extensions, implies, {
        predicate: _position_values(predicate[1], rows) for predicate, rows in extensions.items()
    })
    expected_mutex = set()
    expected_implies = set()
    for (left, rows), (right, other) in product(extensions.items(), repeat=2):
        if left[1] == right[1] and left[1] > 1:
            for projection in permutations(range(left[1])):
                if projection != tuple(range(left[1])) and {tuple(row[i] for i in projection) for row in rows}.isdisjoint(other):
                    expected_mutex.add((left, right, projection))
        if left[1] > right[1] and other:
            for projection in permutations(range(left[1]), right[1]):
                if {tuple(row[i] for i in projection) for row in rows} <= other:
                    expected_implies.add((left, right, projection))
    assert mutex == expected_mutex
    assert implies == expected_implies


def test_projection_properties_are_intersected_across_isolated_contexts():
    contexts = (parse_program("p(a,b). q(a)."), parse_program("p(c,d). q(d)."))
    properties = _closed_world_properties(contexts)
    assert not properties.project_implies
    single = _closed_world_properties(contexts[:1])
    assert (("p", 2), ("q", 1), (0,)) in single.project_implies


def test_indexed_transitivity_and_total_orders_match_all_three_element_relations():
    pairs = tuple(product(range(3), repeat=2))
    for mask in range(1 << len(pairs)):
        rows = frozenset(pair for bit, pair in enumerate(pairs) if mask & (1 << bit))
        transitive = len(rows) >= 3 and all((left, right) in rows for left, middle in rows for other_middle, right in rows if middle == other_middle)
        domain = frozenset(value for pair in rows for value in pair)
        reflexive = _is_reflexive(rows, domain)
        ordered = len(domain) >= 2 and reflexive and transitive and all(
            (left, right) in rows or (right, left) in rows for left, right in permutations(domain, 2)
        ) and not any(left != right and (right, left) in rows for left, right in rows)
        antisymmetric = not any(left != right and (right, left) in rows for left, right in rows)
        assert _is_transitive(_binary_successors(rows), len(rows)) == transitive
        assert _is_total_order(len(rows), len(domain), transitive, reflexive, antisymmetric) == ordered


@pytest.mark.parametrize("diagnostics", [False, True])
def test_capability_diagnostics_are_lazy_and_cached_when_disabled(monkeypatch, diagnostics):
    task = parse_text("d(1). #modeh(1,p(var(numeric,input))). #modeb(1,d(var(numeric,output))).")
    calls = []
    original = generator._predicate_arg_types

    def types(*args):
        calls.append(True)
        return original(*args)

    monkeypatch.setattr(generator, "metric_enabled", lambda category: diagnostics)
    monkeypatch.setattr(generator, "_predicate_arg_types", types)
    compiled = generator._ClauseGenerator(task, Arguments())
    assert len(calls) == int(diagnostics)
    assert compiled.capabilities.has_numeric_evidence
    assert compiled.capabilities is compiled.capabilities
    assert compiled.predicate_arg_types is compiled.predicate_arg_types
    assert len(calls) == 1


@pytest.mark.parametrize("short_first", [False, True])
def test_streaming_canonicalizer_keeps_the_globally_shortest_representative(short_first):
    task = parse_text("#modeb(2,q(var(numeric,input),var(numeric,input),var(numeric,input))). #modeb(2,var(numeric,input)+var(numeric,input)=var(numeric,output)). #modeb(1,var(numeric,input)<var(numeric,input)).")
    modes = {mode.id: mode for mode in mode_compiler._clause_modes(task)}
    short = ReifiedClause((), (ReifiedLiteral("body", 0, 0, (0, 1, 2)), ReifiedLiteral("body", 1, 1, (0, 1, 3)), ReifiedLiteral("body", 2, 2, (3, 2))))
    long = ReifiedClause((), (*short.body, ReifiedLiteral("body", 3, 1, (0, 1, 4)), ReifiedLiteral("body", 4, 2, (4, 2))))
    canonicalizer = ClauseCanonicalizer(modes, 5)
    for clause in (short, long) if short_first else (long, short):
        canonicalizer.add(clause)
    entries = list(canonicalizer.finish())
    assert len(entries) == 1
    assert entries[0].body_literals == 3
    assert entries[0].deps == frozenset({("q", 3)})
    assert "q(V0,V1,V2)" in entries[0].text


@pytest.mark.parametrize("short_first", [False, True])
def test_compact_assignment_keeps_mixed_system_keys_and_minimum_clause_cost(short_first):
    task = parse_text("""
        #modeh(1,target(var(numeric,input))).
        #modeb(1,q(var(numeric,output))).
        #modeb(1,3*var(numeric,input)=var(numeric,output)).
        #modeb(2,var(numeric,input)+var(numeric,input)=var(numeric,output)).
        #modeb(1,var(numeric,input)*var(numeric,input)=var(numeric,output)).
    """)
    modes = {mode.id: mode for mode in mode_compiler._clause_modes(task)}
    head = (ReifiedLiteral("head", 0, 0, (1,)),)
    seed = ReifiedLiteral("body", 0, 1, (0,))
    short = ReifiedClause(head, (seed, ReifiedLiteral("body", 1, 2, (0, 1))))
    mixed = ReifiedClause(head, (
        seed,
        ReifiedLiteral("body", 1, 3, (0, 0, 2)),
        ReifiedLiteral("body", 2, 3, (0, 2, 1)),
        ReifiedLiteral("body", 3, 4, (0, 0, 3)),
    ))
    canonicalizer = ClauseCanonicalizer(modes, 4)
    for clause in (short, mixed) if short_first else (mixed, short):
        canonicalizer.add(clause)
    entries = list(canonicalizer.finish())
    assert len(entries) == 1
    assert entries[0].body_literals == 2
    assert entries[0].text == "target(V1) :- q(V0); (3*V0) = V1."


def test_acyclicity_handles_deep_paths_and_disconnected_cycles():
    path = frozenset((index, index + 1) for index in range(10000))
    assert _is_acyclic(_binary_successors(path))
    assert not _is_acyclic(_binary_successors(path | {(10000, 0)}))
    assert not _is_acyclic(_binary_successors(path | {("a", "b"), ("b", "a")}))
    assert not _is_acyclic(_binary_successors(frozenset({("a", "a")})))
    assert not _is_acyclic(_binary_successors(frozenset()))


def test_acyclicity_matches_all_three_element_relations():
    pairs = tuple(product(range(3), repeat=2))
    for mask in range(1 << len(pairs)):
        rows = frozenset(pair for bit, pair in enumerate(pairs) if mask & (1 << bit))
        reachable = set(rows)
        for middle in range(3):
            reachable |= {(left, right) for left in range(3) for right in range(3)
                          if (left, middle) in reachable and (middle, right) in reachable}
        assert _is_acyclic(_binary_successors(rows)) == (bool(rows) and not any((node, node) in reachable for node in range(3)))


def test_static_ast_analysis_and_variable_substitution_handle_deep_terms():
    nested = "f(" * 1200 + "X" + ")" * 1200
    rule = parse_rule(f"p(X) :- d({nested},Y), X != Y.")
    assert rule_properties._term_variables(rule) == {"X", "Y"}
    swapped = rule_properties._substitute_variables(rule, {"X": "Y", "Y": "X"})
    assert str(swapped) == str(parse_rule(f"p(Y) :- d({'f(' * 1200}Y{')' * 1200},X), Y != X."))
    head = parse_rule(f"p(X): {nested} > 1 :- d(X).").head
    assert ground_relations._head_predicates_known(head)
    assert not ground_relations._head_predicates_known(parse_rule("&unknown{} :- d.").head)


def test_static_tuple_analysis_handles_deep_pairs_and_conflicting_mappings():
    left = "(" * 1200 + "X" + ",a)" * 1200
    right = "(" * 1200 + "Y" + ",a)" * 1200
    rule = parse_rule(f"p({left},{right}) :- X != Y.")
    arguments = rule.head.atom.symbol.arguments
    inequality = rule.body[0].atom
    assert rule_properties._terms_known_distinct(arguments[0], arguments[1], {(inequality.term, inequality.guards[0].term)})
    assert rule_properties._term_pair_mapping(arguments[0], arguments[1]) == {"X": "Y", "Y": "X"}
    conflict = parse_rule("p((X,X),(Y,Z)) :- d(X,Y,Z).").head.atom.symbol.arguments
    assert rule_properties._term_pair_mapping(conflict[0], conflict[1]) is None


def test_shared_arithmetic_subexpressions_are_processed_once_and_remain_shared(monkeypatch):
    left = ArithmeticExpression.var(0)
    right = ArithmeticExpression.var(0)
    for _ in range(24):
        left = ArithmeticExpression("+", (left, left))
        right = ArithmeticExpression("+", (right, right))
    assert left == right
    assert left != right.remap({0: 1})
    assert left.variables == frozenset({0})
    assert len(list(expressions._postorder(left))) == 25
    assert left.key == ("sum", ((("var", 0), 2**24),))
    changed = left.remap({0: 3})
    assert changed.arguments[0] is changed.arguments[1]
    assert changed.variables == frozenset({3})
    substituted = left.substitute({0: ArithmeticExpression.const(7)})
    assert substituted.arguments[0] is substituted.arguments[1]
    calls = []
    original = expressions.binding_term

    def binding(name):
        calls.append(name)
        return original(name)

    monkeypatch.setattr(expressions, "binding_term", binding)
    node = left.instantiate()
    assert node.left == node.right
    assert calls == ["V0"]


@pytest.mark.parametrize("generated_limit,total_limit", [(0, 0), (0, 3), (2, 2), (3, 5), (3, None)])
def test_bounded_head_conditions_match_filtered_product_order(generated_limit, total_limit):
    task = parse_text("""
        #maxbl(3). #modeh(1,p:q;r;s;t).
        #modec(1,c). #modec(1,d). #modec(1,e).
    """)
    conditions = mode_compiler._Conditions(task)
    alternatives = tuple(conditions.expand(literal) for literal in task.language_bias_head[0].elements)
    expected = []
    for choice in product(*alternatives):
        generated = sum(sum(group >= 0 for group in literal.condition_groups)
                        for literal in choice if hasattr(literal, "condition_groups"))
        total = sum(len(literal.conditions) for literal in choice if hasattr(literal, "conditions"))
        if generated <= generated_limit and (total_limit is None or total <= total_limit):
            expected.append(choice)
    assert list(mode_compiler._bounded_condition_product(alternatives, generated_limit, total_limit)) == expected
    assert list(mode_compiler._bounded_condition_product((), generated_limit, total_limit)) == [()]
    assert list(mode_compiler._bounded_condition_product(((),), generated_limit, total_limit)) == []


@pytest.mark.parametrize("violated", [False, True])
def test_identical_property_proofs_are_shared_without_losing_acceptance(monkeypatch, violated):
    source = "d(1..3). 1 {p(X,Y):d(Y)} 1 :- d(X)."
    if violated:
        source += " p(1,4). p(1,5)."
    world = ground_relations._closed_world(parse_program(source), frozenset())
    assert world is not None
    calls = []
    original = inference._hold_in_every_model

    def prove(program, violations):
        calls.extend(violations)
        return original(program, violations)

    monkeypatch.setattr(inference, "_hold_in_every_model", prove)
    keys, functional = set(), set()
    inference._syntactic_properties(world, keys, functional, set(), set(), set(), set())
    assert len(calls) == len(set(calls)) == 2
    assert ((("p", 2), (0,)) in keys) == (not violated)
    assert ((("p", 2), 0, 1) in functional) == (not violated)


def test_context_intersection_keeps_dependencies_hidden_by_a_local_key():
    first = parse_program("p(a,b,1). p(c,d,2).")
    second = parse_program("p(a,b,1). p(a,b,2). p(c,d,3).")
    assert not _closed_world_properties((first,)).functional
    common = _closed_world_properties((first, second))
    assert (("p", 3), 0, 1) in common.functional
    assert (("p", 3), (0,)) not in common.keys
    assert _closed_world_properties(()) == _closed_world_properties((parse_program(":-."),))
    assert common == _closed_world_properties((first, parse_program(":-."), second))


def test_bounded_arithmetic_cache_eviction_preserves_results_including_rejections(monkeypatch):
    task = parse_text("#modeb(1,q(var(numeric,any),var(numeric,any))). #modeb(1,var(numeric,input)=var(numeric,input)). #modeb(1,var(numeric,input)<var(numeric,input)).")
    modes = {mode.id: mode for mode in mode_compiler._clause_modes(task)}
    monkeypatch.setattr(arithmetic, "MAX_CACHED_SYSTEMS", 2)
    cache = arithmetic._ArithmeticSystemsCache()
    results = []
    for left, right, contradictory in ((0, 1, True), (0, 1, True), (0, 1, False), (1, 2, False), (0, 1, True)):
        second = (left, right) if contradictory else (left, 3)
        clause = ReifiedClause((), (
            ReifiedLiteral("body", 0, 0, (left, right)),
            ReifiedLiteral("body", 1, 1, (left, right)),
            ReifiedLiteral("body", 2, 2, second),
        ))
        cached = arithmetic.canonical_arithmetic_clause(clause, modes, 4, cache)
        uncached = arithmetic.canonical_arithmetic_clause(clause, modes, 4)
        assert cached == uncached
        assert len(cache) <= 2
        results.append(cached)
    assert results[0] is results[1] is results[-1] is None


def test_dependency_grouping_matches_tuple_semantics_before_context_reduction():
    for arity in range(2, 5):
        predicate = ("p", arity)
        rows = tuple(product(range(2), repeat=arity))
        cases = [frozenset(), frozenset(rows[:1]), frozenset(rows), frozenset(rows[::3]),
                 frozenset(tuple(value for _ in range(arity)) for value in ("a", "b"))]
        for tuples in cases:
            functional, composite, keys = set(), set(), set()
            _collect_dependency_properties(predicate, tuples, functional, composite, keys)
            expected_functional, expected_composite, expected_keys = set(), set(), set()
            if len(tuples) >= 2:
                for size in range(1, arity):
                    for inputs in combinations(range(arity), size):
                        if len({tuple(row[i] for i in inputs) for row in tuples}) == len(tuples) and not any(set(existing) <= set(inputs) for _, existing in expected_keys):
                            expected_keys.add((predicate, inputs))
                        for output in set(range(arity)) - set(inputs):
                            if all(left[output] == right[output] for left in tuples for right in tuples
                                   if all(left[i] == right[i] for i in inputs)):
                                if size == 1:
                                    expected_functional.add((predicate, inputs[0], output))
                                else:
                                    expected_composite.add((predicate, inputs, output))
            assert (functional, composite, keys) == (expected_functional, expected_composite, expected_keys)


def test_compiled_binding_offsets_separate_head_elements_conditions_and_guards():
    task = parse_text("""
        #modeh(1,var(numeric,input,n) {p(f(var(node,any,x))):q(var(node,any,x))} var(numeric,input,n)).
        #modeb(1,#sum{var(numeric,any,w):q(var(node,any,x)),r(var(numeric,any,w))}=var(numeric,output,n)).
        #modeb(1,var(numeric,input,x)<var(numeric,input,y)<3).
    """)
    modes = {mode.id: mode for mode in mode_compiler._clause_modes(task)}
    for mode in modes.values():
        counts = [len(mode_terms.bindings(term)) for term in mode.arguments]
        assert mode.argument_offsets == tuple(sum(counts[:index]) for index in range(len(counts) + 1))
    head_mode = next(mode for mode in modes.values() if mode.section == "head")
    head = (ReifiedLiteral("head", 0, head_mode.id, (0, 1, 2, 2)),)
    assert str(instantiate_head(head, modes)) == "V2 <= { p(f(V0)): q(V1) } <= V2"


def test_clause_space_owns_final_order_and_text_deduplication():
    task = parse_text("#modeh(1,z). #modeh(1,a).")
    modes = {mode.id: mode for mode in mode_compiler._clause_modes(task)}
    canonicalizer = ClauseCanonicalizer(modes, 0)
    for mode in modes.values():
        canonicalizer.add(ReifiedClause((ReifiedLiteral("head", 0, mode.id, ()),), ()))
    entries = list(canonicalizer.finish())
    assert [entry.text for entry in entries] == ["z.", "a."]
    space = ClauseSpace(iter((*entries, entries[0])))
    assert space.clauses == ("a.", "z.")


@pytest.mark.parametrize("predicate", ["violation", "gentians_violation", "gentians_violation_1"])
def test_property_probes_do_not_change_the_background_models(predicate):
    program = parse_program(f"a :- {predicate}(0). b :- not a.")
    assert ground_relations._hold_in_every_model(program, ["b", "a"]) == {1}
    program = parse_program(f"{predicate}(0). a :- {predicate}(0). b :- not a.")
    assert ground_relations._hold_in_every_model(program, ["b", "a"]) == {0}


def test_property_probe_name_avoids_directives_macros_signed_atoms_and_fixed_terms():
    program = parse_program("""
        #external gentians_violation(0).
        #show gentians_violation_1/1.
        #const gentians_violation_2 = 7.
        -gentians_violation_3(0). keep(f(gentians_violation_4)).
    """)
    assert ground_relations._fresh_violation_name(program) == "gentians_violation_5"
    assert ground_relations._hold_in_every_model(program, ["-gentians_violation_3(0)", "missing"]) == {1}
    assert ground_relations._hold_in_every_model((), ["not gentians_violation(0)"]) == set()
    assert ground_relations._hold_in_every_model((), []) == set()
    assert ground_relations._hold_in_every_model(
        parse_program("b. #program unused. p."), ["b", "p"],
    ) == {1}


def test_diagnostic_type_names_are_reproducible_across_hash_seeds():
    script = """
import json
from gentians.language import parse_text
from gentians.clauses.analysis.task import _predicate_arg_types, _task_nodes
task = parse_text('p(a). q(b). r(c). p(X) :- q(X).')
print(json.dumps(list(_predicate_arg_types(task, _task_nodes(task)).items())))
"""
    results = [subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True,
        env={**os.environ, "PYTHONHASHSEED": str(seed)},
    ).stdout for seed in (1, 2, 3)]
    assert len(set(results)) == 1
    assert json.loads(results[0]) == [
        [["p", 1, 0], "type_0"], [["q", 1, 0], "type_0"], [["r", 1, 0], "type_1"],
    ]


@pytest.mark.parametrize("term,numeric", [
    ("1", True), ("-1", True), ("~1", True), ("|1|", True),
    ("a", False), ("-a", False), ("f(1)", False), ("1+2", False),
    ("a..b", True), ("-a..b", False), ("1..3", True), ("1..f(3)", False),
])
def test_diagnostic_numeric_classification_preserves_term_and_interval_roles(term, numeric):
    node = parse_rule(f"p({term}).").head.atom.symbol.arguments[0]
    assert task_analysis._is_numeric_term(node) == numeric


def test_diagnostic_types_handle_deep_numeric_terms():
    task = parse_text("p(" + "-(" * 1200 + "1" + ")" * 1200 + ").")
    assert task_analysis._predicate_arg_types(task, task_analysis._task_nodes(task)) == {("p", 1, 0): "numeric"}


def test_native_literal_cache_reuses_bindings_independently_of_body_slot():
    task = parse_text("#modeb(2,p(var(node,any))). #modeb(1,not p(var(node,input))).")
    modes = {mode.id: mode for mode in mode_compiler._clause_modes(task)}
    reified_clause._instantiate_literal.cache_clear()
    nodes = []
    for slot in range(20):
        clause = arithmetic.canonical_arithmetic_clause(
            ReifiedClause((), (ReifiedLiteral("body", slot, 0, (0,)),)), modes, 1,
        )
        assert clause is not None
        nodes.append(clause.instantiate(modes).body[0])
    assert all(node == nodes[0] for node in nodes)
    info = reified_clause._instantiate_literal.cache_info()
    assert (info.misses, info.hits, info.maxsize) == (1, 19, 8192)
    first = reified_clause._instantiate_literal(modes[0], (0,))
    assert first is reified_clause._instantiate_literal(modes[0], (0,))
    assert str(reified_clause._instantiate_literal(modes[0], (1,))) == "p(V1)"
    assert str(reified_clause._instantiate_literal(modes[1], (0,))) == "not p(V0)"


def test_contexts_share_syntax_analysis_but_keep_their_relations_isolated(monkeypatch):
    background = parse_program("p(a,b). -p(c,d). q(X,Y) :- p(X,Y).")
    contexts = tuple(background + parse_program(source) for source in (
        "p(b,a).", "p(a,a).", ":-.", "-p(d,c).",
    ))
    calls = Counter()
    original = ground_relations.clause_predicates

    def inspect(rule):
        calls[rule] += 1
        return original(rule)

    monkeypatch.setattr(ground_relations, "clause_predicates", inspect)
    common = _closed_world_properties(contexts)
    assert all(calls[rule] == 1 for rule in background)
    assert ("p", 2) not in common.symmetric
    assert ("p", 2) not in common.arg_distinct
    # A separate task owns a fresh syntax memo; no global state survives.
    assert common == _closed_world_properties(contexts)
    assert all(calls[rule] == 2 for rule in background)
    first = ground_relations._closed_world(contexts[0], frozenset())
    second = ground_relations._closed_world(contexts[1], frozenset())
    assert first is not None and second is not None
    assert first.extension(("p", 2)) == frozenset({("a", "b"), ("b", "a")})
    assert second.extension(("p", 2)) == frozenset({("a", "b"), ("a", "a")})
    assert first.extension(("-p", 2)) == second.extension(("-p", 2)) == frozenset({("c", "d")})


def test_mode_facts_reuse_term_shapes_and_keep_all_fact_variants(monkeypatch):
    task = parse_text("""
        #maxv(1). #maxhl(2). #maxbl(2).
        #modeh(1,p(var(node,any));q(var(node,any))).
        #modec(1,c(var(node,any))). #modec(1,d(var(node,any))).
        #modeb(1,not -p(var(node,input))).
        #modeb(1,var(numeric,input)<3).
    """)
    modes = mode_compiler._clause_modes(task)
    ids = mode_facts.predicate_ids(modes)
    expected = mode_facts.compile_mode_facts(modes, ids, 2, 2)
    calls = Counter()
    original = mode_terms.shape

    def shape(term):
        calls[term] += 1
        return original(term)

    monkeypatch.setattr(mode_terms, "shape", shape)
    assert mode_facts.compile_mode_facts(modes, ids, 2, 2) == expected
    assert calls and max(calls.values()) == 1
    assert mode_facts.compile_mode_facts(modes, ids, 2, 2) == expected
    assert max(calls.values()) == 2


def test_arithmetic_readiness_preserves_scan_order_with_redefinitions_and_cycles(monkeypatch):
    task = parse_text("#modeb(10,var(numeric,input)*var(numeric,input)=var(numeric,output)).")
    modes = {mode.id: mode for mode in mode_compiler._clause_modes(task)}
    original = expression_normalization._mode_expression
    seen = []

    def expression(literal, mode, known):
        seen.append(literal.slot)
        return original(literal, mode, known)

    monkeypatch.setattr(expression_normalization, "_mode_expression", expression)
    rng = Random(23)
    for _ in range(250):
        literals = [ReifiedLiteral("body", index, 0, tuple(rng.randrange(7) for _ in range(3)))
                    for index in range(rng.randrange(1, 15))]
        safe = {variable for variable in range(7) if rng.randrange(3) == 0}
        available = set(safe)
        pending = list(literals)
        expected = []
        while pending:
            ready = False
            for literal in pending[:]:
                if set(literal.variables[:-1]) <= available:
                    expected.append(literal.slot)
                    available.add(literal.variables[-1])
                    pending.remove(literal)
                    ready = True
            if not ready:
                break
        seen.clear()
        system = expression_normalization._expression_system(literals, modes, set(range(7)), safe, set(range(7)))
        assert seen == expected
        assert (system is None) == bool(pending)


def test_reverse_arithmetic_chain_does_not_rescan_every_unready_assignment():
    task = parse_text("#modeb(1,var(numeric,input)*var(numeric,input)=var(numeric,output)).")

    class CountModes(dict):
        reads = 0

        def __getitem__(self, key):
            self.reads += 1
            return super().__getitem__(key)

    modes = CountModes({mode.id: mode for mode in mode_compiler._clause_modes(task)})
    literals = [ReifiedLiteral("body", index, 0, (index, 0, index + 1)) for index in reversed(range(100))]
    system = expression_normalization._expression_system(literals, modes, {100}, {0}, set(range(101)))
    assert system is not None and system.variables == frozenset({0, 100})
    assert modes.reads <= 4 * len(literals)


@pytest.mark.parametrize("operator", ["/", "\\"])
def test_arithmetic_readiness_keeps_inherited_divisor_guards(operator):
    task = parse_text(f"#modeb(2,var(numeric,input){operator}var(numeric,input)=var(numeric,output)).")
    modes = {mode.id: mode for mode in mode_compiler._clause_modes(task)}
    literals = [ReifiedLiteral("body", 0, 0, (2, 1, 3)), ReifiedLiteral("body", 1, 0, (0, 1, 2))]
    system = expression_normalization._expression_system(literals, modes, {3}, {0, 1}, set(range(4)))
    assert system is not None
    assert system.render() == (f"((V0{operator}V1){operator}V1) = V3", "V1 != 0")


def test_arithmetic_literal_dedup_keeps_constraint_and_guard_order():
    variable = ArithmeticExpression.var(0)
    relation = ExpressionConstraint(variable, "ne")
    guarded = ExpressionConstraint(variable, "eq", guards=(variable, variable))
    system = ArithmeticSystem((relation, guarded, relation, guarded))
    # Guard insertion follows guard keys even when a prior main literal equals it.
    assert system.render() == ("V0 != 0", "V0 = 0", "V0 != 0")
    reverse = ArithmeticSystem((guarded, relation))
    assert reverse.render() == ("V0 = 0", "V0 != 0")


def test_arithmetic_literal_membership_uses_native_hashes(monkeypatch):
    comparisons = 0
    original = clingo.ast.AST.__eq__

    def equal(left, right):
        nonlocal comparisons
        comparisons += 1
        return original(left, right)

    monkeypatch.setattr(clingo.ast.AST, "__eq__", equal)
    system = ArithmeticSystem(tuple(LinearConstraint((1, index), "eq") for index in range(100)))
    assert len(system.instantiate()) == 100
    assert comparisons < 100


def test_expression_guards_are_sorted_once_and_remapped_independently(monkeypatch):
    sorts = []

    def ordered(values, **kwargs):
        sorts.append(tuple(values))
        return sorted(values, **kwargs)

    monkeypatch.setattr(expression_constraint, "sorted", ordered, raising=False)
    guards = (ArithmeticExpression.var(2), ArithmeticExpression.var(1))
    relation = ExpressionConstraint(ArithmeticExpression.var(0), "eq", guards=guards)
    initial_hash = hash(relation)
    assert relation.guard_keys == (("var", 1), ("var", 2))
    assert relation.key == relation.key
    assert relation.rendered_guards == ("V1 != 0", "V2 != 0")
    assert sorts == [guards]
    changed = relation.remap({0: 4, 1: 5, 2: 3})
    assert changed.rendered_guards == ("V3 != 0", "V5 != 0")
    assert len(sorts) == 2
    assert hash(relation) == initial_hash
    assert relation.guards == guards


def test_native_arithmetic_system_is_shared_only_within_its_own_lifetime(monkeypatch):
    task = parse_text("#modeh(1,target(var(numeric,input))). " + " ".join(
        f"#modeb(1,q{index}(var(numeric,any)))." for index in range(20)
    ) + " #modeb(1,var(numeric,input)*var(numeric,input)=var(numeric,output)).")
    modes = {mode.id: mode for mode in mode_compiler._clause_modes(task)}
    calls = []
    original = ExpressionConstraint.instantiate

    def instantiate(relation):
        calls.append(relation)
        return original(relation)

    monkeypatch.setattr(ExpressionConstraint, "instantiate", instantiate)
    outputs = []
    for _batch in range(2):
        canonicalizer = ClauseCanonicalizer(modes, 2)
        for index in range(20):
            canonicalizer.add(ReifiedClause((ReifiedLiteral("head", 0, 0, (1,)),), (
                ReifiedLiteral("body", 0, index + 1, (0,)),
                ReifiedLiteral("body", 1, 21, (0, 0, 1)),
            )))
        entries = list(canonicalizer.finish())
        assert len(entries) == 20
        outputs.append([entry.text for entry in entries])
    assert len(calls) == 2
    assert outputs[0] == outputs[1]
    system = ArithmeticSystem((calls[0],))
    original_hash = hash(system)
    nodes = system.instantiate()
    assert nodes is system.instantiate()
    changed = system.remap({0: 2, 1: 3}, 4)
    assert changed.render() == ("(V2*V2) = V3",)
    assert system.render() == ("(V0*V0) = V1",)
    assert hash(system) == original_hash


def test_singleton_native_system_needs_no_ast_hashing(monkeypatch):
    relation = LinearConstraint((1, -1), "lt")
    expected = relation.instantiate()

    def no_hash(_node):
        raise AssertionError("one unguarded relation needs no native deduplication")

    monkeypatch.setattr(clingo.ast.AST, "__hash__", no_hash)
    system = ArithmeticSystem((relation,))
    assert system.instantiate() == (expected,)
    assert system.instantiate() is system.instantiate()


def test_local_comparison_variants_share_safe_and_unsafe_probes_within_compilation(monkeypatch):
    task = parse_text("""
        #maxhl(2). #maxbl(2).
        #modeh(1,p(var(numeric,any,x));q(var(numeric,any,x))).
        #modeh(1,r(var(numeric,any,x));s(var(numeric,any,x))).
        #modeb(1,d(var(numeric,any,x))).
        #modec(1,var(numeric,input,x)=var(numeric,input,y)+1).
    """)
    modes = mode_compiler._clause_modes(task)
    calls = Counter()
    results = set()
    original = mode_facts._comparison_outputs_are_safe

    def inspect(literal):
        calls[literal] += 1
        result = original(literal)
        results.add(result)
        return result

    monkeypatch.setattr(mode_facts, "_comparison_outputs_are_safe", inspect)
    first = mode_facts.compile_mode_facts(modes, mode_facts.predicate_ids(modes), 2, 2)
    assert len(calls) == 3 and set(calls.values()) == {1}
    assert results == {True, False}
    assert sum(fact.startswith("local_comparison_variant(") for fact in first) > 2
    assert mode_facts.compile_mode_facts(modes, mode_facts.predicate_ids(modes), 2, 2) == first
    assert set(calls.values()) == {2}


def test_pool_binding_summaries_do_not_rescan_deep_subtrees(monkeypatch):
    term = parse_text("#modeb(1,p(" + "f(" * 1200 + "var(node,any)" + ")" * 1200 + ")).").language_bias_body[0].literal.atom.terms[0]
    monkeypatch.setattr(mode_terms, "bindings", lambda *_: pytest.fail("subtree bindings rescanned"))
    assert mode_facts._term_alternative_positions(term, 7) == (frozenset({7}),)


def test_pool_position_cache_is_local_and_reuses_condition_atoms(monkeypatch):
    task = parse_text("""
        #maxhl(2). #maxbl(2).
        #modeh(1,p(var(node,any,x)):d(f(var(node,any,x);var(node,any,y)))).
        #modeh(1,q(var(node,any,x)):d(f(var(node,any,x);var(node,any,y)))).
        #modeb(1,r(var(node,any,x)):d(f(var(node,any,x);var(node,any,y)))).
    """)
    modes = mode_compiler._clause_modes(task)
    calls = Counter()
    original = mode_facts._pool_alternative_positions

    def inspect(atom):
        calls[atom] += 1
        return original(atom)

    monkeypatch.setattr(mode_facts, "_pool_alternative_positions", inspect)
    facts = mode_facts.compile_mode_facts(modes, mode_facts.predicate_ids(modes), 2, 2)
    assert calls and set(calls.values()) == {1}
    assert any(fact.startswith("local_pool_alternative_arg(") for fact in facts)
    assert mode_facts.compile_mode_facts(modes, mode_facts.predicate_ids(modes), 2, 2) == facts
    assert set(calls.values()) == {2}


@pytest.mark.parametrize("direction,shorter", [("output", True), ("input", False)])
def test_aggregate_shorter_index_preserves_conditions_functions_and_output_guard(direction, shorter):
    task = parse_text(f"""
        #modeb(1,#sum{{var(numeric,any,x):p(var(numeric,any,x),var(numeric,any,y))}}=var(numeric,{direction})).
        #modeb(1,#sum{{var(numeric,any,x),var(numeric,any,y):p(var(numeric,any,x),var(numeric,any,y))}}=var(numeric,output)).
        #modeb(1,#sum{{var(numeric,any,x),var(numeric,any,y):q(var(numeric,any,x),var(numeric,any,y))}}=var(numeric,output)).
        #modeb(1,#count{{var(numeric,any,x),var(numeric,any,y):p(var(numeric,any,x),var(numeric,any,y))}}=var(numeric,output)).
    """)
    modes = mode_compiler._clause_modes(task)
    facts = mode_facts.compile_mode_facts(modes, mode_facts.predicate_ids(modes), 1, 3)
    assert {fact for fact in facts if fact.startswith("aggregate_has_shorter_mode(")} == (
        {"aggregate_has_shorter_mode(1)."} if shorter else set()
    )


def test_combined_head_templates_are_consumed_lazily_in_existing_order(monkeypatch):
    task = parse_text("#maxhl(2). #maxbl(0). #modeha(2,p(var(node,input))).")
    calls = []
    original = mode_compiler.HeadTemplate

    def construct(*args):
        calls.append(args)
        return original(*args)

    monkeypatch.setattr(mode_compiler, "HeadTemplate", construct)
    templates = mode_compiler._combined_head_templates(task, task.language_bias_aggregate_head, "choice", mode_compiler._Conditions(task))
    assert iter(templates) is templates and not calls
    first = next(templates)
    assert len(calls) == 1 and first.width == 1
    rest = list(templates)
    assert [head.width for head in rest] == [2, 2, 2]


def test_partition_prefix_pruning_matches_rectangular_tuple_semantics():
    rng = Random(91)
    for arity in (0, 1, 2):
        universe = tuple(product(range(3), repeat=arity))
        for _ in range(60):
            relations = {(f"p{index}", arity): frozenset(row for row in universe if rng.randrange(4) == 0) for index in range(7)}
            expected = set()
            predicates = [predicate for predicate, rows in relations.items() if rows]
            for size in range(3, min(len(predicates), 6) + 1):
                for group in combinations(predicates, size):
                    if any(not relations[left].isdisjoint(relations[right]) for left, right in combinations(group, 2)):
                        continue
                    if any(set(other) < set(group) for other in expected):
                        continue
                    union = frozenset().union(*(relations[predicate] for predicate in group))
                    columns = tuple({row[index] for row in union} for index in range(arity))
                    if union == frozenset(product(*columns)):
                        expected.add(group)
            assert _partition_properties(relations, {
                predicate: _position_values(arity, rows) for predicate, rows in relations.items()
            }) == expected


def test_projection_prefixes_only_reach_compatible_complete_mappings(monkeypatch):
    sources = {("source", 8): frozenset({tuple(range(8))})}
    targets = {("target", 5): frozenset({(0, 1, 2, 3, 4)}), ("empty", 0): frozenset(), ("true", 0): frozenset({()})}
    reached = []
    from gentians.clauses.analysis import relation_properties
    original = relation_properties._projection_matches

    def inspect(*args):
        for projection, matches in original(*args):
            reached.append(projection)
            yield projection, matches

    monkeypatch.setattr(relation_properties, "_projection_matches", inspect)
    result = set()
    _collect_projection_implications(sources, targets, result, {
        predicate: _position_values(predicate[1], rows) for predicate, rows in {**sources, **targets}.items()
    })
    assert result == {(("source", 8), ("target", 5), (0, 1, 2, 3, 4)), (("source", 8), ("true", 0), ())}
    assert reached == [(0, 1, 2, 3, 4), ()]


def test_linear_readiness_matches_original_priority_for_duplicates_cycles_and_nonunit_outputs():
    def reference(constraints, safe):
        pending = list(constraints)
        oriented = []
        safe = set(safe)
        while pending:
            ready = next((constraint for constraint in pending if constraint.variables <= safe), None)
            if ready is not None:
                oriented.append(ready)
                pending.remove(ready)
                continue
            assignment = next(((constraint, next(iter(constraint.variables - safe))) for constraint in pending
                               if constraint.relation == "eq" and len(constraint.variables - safe) == 1
                               and abs(constraint.coefficients[next(iter(constraint.variables - safe))]) == 1), None)
            if assignment is None:
                return None
            constraint, output = assignment
            oriented.append(ExpressionConstraint(_linear_assignment_expression(constraint, output), "eq", output, False))
            safe.add(output)
            pending.remove(constraint)
        return tuple(oriented)

    rng = Random(42)
    for _ in range(400):
        constraints = tuple(LinearConstraint(tuple(rng.randrange(-2, 3) for _ in range(5)), rng.choice(("eq", "le", "ne"))) for _ in range(rng.randrange(8)))
        safe = {index for index in range(5) if rng.randrange(2)}
        assert _orient_linear_constraints(constraints, sum(1 << variable for variable in safe)) == reference(constraints, safe)
    chain = (LinearConstraint((0, 1, -1), "eq"), LinearConstraint((1, -1, 0), "eq"))
    assert _orient_linear_constraints((*chain, *chain), 1) == reference((*chain, *chain), {0})


def test_linear_readiness_inspects_each_variable_mask_once(monkeypatch):
    calls = []
    original = LinearConstraint.variable_mask.fget

    def variables(constraint):
        calls.append(constraint)
        return original(constraint)

    monkeypatch.setattr(LinearConstraint, "variable_mask", property(variables))
    constraints = tuple(LinearConstraint(tuple(-1 if variable == index else 1 if variable == index + 1 else 0 for variable in range(101)), "eq") for index in reversed(range(100)))
    assert _orient_linear_constraints(constraints, 1) is not None
    assert len(calls) == len(constraints)


def test_linear_masks_follow_nonzero_coefficients_and_keep_hashes_after_materialization():
    constraint = LinearConstraint((0,) * 100 + (2, -1), "eq")
    original_hash = hash(constraint)
    assert constraint.variable_mask == (1 << 100) | (1 << 101)
    assert constraint.variables == frozenset({100, 101})
    assert hash(constraint) == original_hash
    assert constraint == LinearConstraint(constraint.coefficients, "eq")


@pytest.mark.parametrize("comparison", ["<", ">", "!="])
@pytest.mark.parametrize("scale", [-1, 1])
def test_linear_conflict_facts_pair_proportional_templates_without_asp_coefficients(comparison, scale):
    modes = mode_compiler._clause_modes(parse_text(f"""
        #modeb(1,2*var(numeric,input)=var(numeric,output)).
        #modeb(1,{4*scale}*var(numeric,input){comparison}{2*scale}*var(numeric,input)).
        #modeb(1,var(numeric,input)*var(numeric,input)=var(numeric,output)).
    """))
    facts = mode_facts.compile_mode_facts(modes, {}, 1, 4)
    assert [fact for fact in facts if fact.startswith("numeric_linear_conflict(")] == ["numeric_linear_conflict(0,1)."]
    assert [fact for fact in facts if fact.startswith("nonlinear_builtin_mode(")] == ["nonlinear_builtin_mode(2)."]


def test_linear_conflict_pairing_excludes_zero_coefficients_that_cannot_anchor_a_row():
    modes = mode_compiler._clause_modes(parse_text("""
        #modeb(1,0*var(numeric,input)+2*var(numeric,input)=var(numeric,output)).
        #modeb(1,0*var(numeric,input)+4*var(numeric,input)<2*var(numeric,input)).
    """))
    assert not mode_facts._linear_conflict_facts(modes)


@pytest.mark.parametrize("row,requires_distinct", [
    ("2*var(numeric,input)-var(numeric,input)", False),
    ("var(numeric,input)+var(numeric,input)", False),
    ("2*var(numeric,input)", False),
    ("2*var(numeric,input)-2*var(numeric,input)", True),
    ("var(numeric,input)-var(numeric,input)+var(numeric,input)", True),
])
def test_linear_conflict_compiler_marks_only_rows_whose_anchor_can_cancel(row, requires_distinct):
    modes = mode_compiler._clause_modes(parse_text(f"#modeb(1,{row}=0). #modeb(1,{row}<0)."))
    facts = mode_facts._linear_conflict_facts(modes)
    assert "numeric_linear_conflict(0,1)." in facts
    assert ("numeric_linear_distinct_mode(0)." in facts) == requires_distinct


@pytest.mark.parametrize("coefficients,relation,auxiliary,expected", [
    ((2, -4), "eq", (), ((1, -2), "eq")),
    ((-2, 4), "eq", (), ((1, -2), "eq")),
    ((-2, 4), "lt", (), ((-1, 2), "lt")),
    ((-2, 4), "ne", (), ((1, -2), "ne")),
    ((1, -3), "eq", (0,), ()),
    ((2, -4), "eq", (0,), ((1, -2), "eq")),
    ((1, -3), "le", (0,), ((1, -3), "le")),
    ((0, 0), "eq", (), ()),
    ((0, 0), "le", (), ()),
    ((0, 0), "lt", (), None),
    ((0, 0), "ne", (), None),
])
def test_single_linear_row_preserves_signs_and_integer_auxiliary_elimination(
    coefficients, relation, auxiliary, expected,
):
    result = _normalize_component(
        (LinearConstraint(coefficients, relation),), sum(1 << variable for variable in auxiliary), len(coefficients),
    )
    assert result == (None if expected is None else () if not expected
                      else (LinearConstraint(*expected),))


def test_equal_linear_rows_share_native_syntax_without_merging_relations(monkeypatch):
    calls = []
    original = linear_constraints.binding_term

    def binding(value):
        calls.append(value)
        return original(value)

    LinearConstraint.instantiate.cache_clear()
    monkeypatch.setattr(linear_constraints, "binding_term", binding)
    try:
        first = LinearConstraint((2, -1), "eq").instantiate()
        count = len(calls)
        for _ in range(10):
            assert LinearConstraint((2, -1), "eq").instantiate() is first
        assert len(calls) == count
        less = LinearConstraint((2, -1), "lt").instantiate()
        reversed_row = LinearConstraint((-2, 1), "eq").instantiate()
        assert str(first) == "((2*V0)-V1) = 0"
        assert str(less) == "((2*V0)-V1) < 0"
        assert reversed_row != first
        changed = first.update(sign=clingo.ast.Sign.Negation)
        assert str(changed) != str(first)
        assert str(first) == "((2*V0)-V1) = 0"
        assert LinearConstraint.instantiate.cache_info().maxsize == 8192
    finally:
        LinearConstraint.instantiate.cache_clear()


@pytest.mark.parametrize("body_equality", [False, True])
def test_numeric_equality_facts_exclude_heads_and_keep_directed_outputs(body_equality):
    task = parse_text("""
        #modeh(1,var(numeric,input)=var(numeric,input)).
        #modeb(1,var(numeric,input)<var(numeric,input)).
        #modeb(1,var(numeric,input)*var(numeric,input)=var(numeric,output)).
    """ + ("#modeb(1,var(numeric,output)=var(numeric,input))." if body_equality else ""))
    modes = mode_compiler._clause_modes(task)
    facts = mode_facts.compile_mode_facts(modes, mode_facts.predicate_ids(modes), 1, 3)
    equalities = [fact for fact in facts if fact.startswith("numeric_equality_mode(")]
    complex_modes = [fact for fact in facts if fact.startswith("complex_numeric_builtin_mode(")]
    if body_equality:
        assert equalities == [f"numeric_equality_mode({modes[-1].id})."]
        assert complex_modes == [f"complex_numeric_builtin_mode({modes[-2].id})."]
    else:
        assert not equalities and not complex_modes


def test_strict_self_comparison_facts_keep_chains_without_duplicating_simple_policy():
    task = parse_text("""
        #modeb(1,var(numeric,input)<var(numeric,input)).
        #modeb(1,var(numeric,input)<var(numeric,input)<3).
    """)
    modes = mode_compiler._clause_modes(task)
    simple = mode_facts._comparison_facts(modes[0], modes[0].literal)
    chained = mode_facts._comparison_facts(modes[1], modes[1].literal)
    assert f"comparison_operator({modes[0].id},lt)." in simple
    assert not any(fact.startswith("strict_comparison_args(") for fact in simple)
    assert f"strict_comparison_args({modes[1].id},0,1)." in chained


def test_context_indexes_are_reused_and_numeric_signs_preserve_empty_relations(monkeypatch):
    calls = Counter()
    original = inference._position_values

    def positions(arity, rows):
        calls[arity, rows] += 1
        return original(arity, rows)

    monkeypatch.setattr(inference, "_position_values", positions)
    world = ground_relations.ClosedWorld({
        ("p", 2): frozenset({(1, 0), (2, 3)}),
        ("q", 2): frozenset({("a", -1)}),
        ("empty", 2): frozenset(),
    }, {}, {}, frozenset(), frozenset(), ())
    properties = inference._context_properties(world, None, None)
    assert set(calls.values()) == {1}
    assert properties.positive_args == frozenset({(("p", 2), 0), (("empty", 2), 0), (("empty", 2), 1)})
    assert properties.nonnegative_args == properties.positive_args | {(("p", 2), 1)}


def test_arithmetic_system_key_is_lazy_shared_and_independent_after_remapping(monkeypatch):
    calls = []
    original = LinearConstraint.key.fget

    def key(relation):
        calls.append(relation)
        return original(relation)

    monkeypatch.setattr(LinearConstraint, "key", property(key))
    system = ArithmeticSystem((LinearConstraint((1, -1), "eq"),))
    before = hash(system)
    assert not calls
    assert system.key is system.key
    assert len(calls) == 1 and hash(system) == before
    changed = system.remap({0: 1, 1: 0}, 2)
    assert changed.key == (("eq", (-1, 1)),)
    assert system.key == (("eq", (1, -1)),) and len(calls) == 2


@pytest.mark.parametrize("enabled,metrics", [(False, False), (True, False), (False, True), (True, True)])
@pytest.mark.parametrize("incremental", [False, True])
def test_generation_only_reads_its_clock_when_timings_or_clingo_metrics_are_enabled(monkeypatch, enabled, metrics, incremental):
    ticks = []
    rows = []
    timing.reset()
    monkeypatch.setattr(timing, "_enabled", enabled)
    monkeypatch.setattr(generator, "metric_enabled", lambda _: metrics)
    monkeypatch.setattr(generator, "record_metric", lambda _, row: rows.append(row))

    def tick():
        assert enabled or metrics
        ticks.append(True)
        return float(len(ticks))

    monkeypatch.setattr(generator, "net_time", tick)
    task = parse_text("#maxv(0). #maxbl(0). #modeh(1,p).")
    try:
        if incremental:
            with generator.incremental_clause_batches(task, Arguments(), 1, Random(12)) as batches:
                clauses = tuple(clause for batch in batches for clause in batch.clauses)
        else:
            clauses = generator.generate_clause_space(task, Arguments()).clauses
        assert clauses == ("p.",)
        assert bool(ticks) == (enabled or metrics)
        assert bool(rows) == metrics
        assert all(row["seconds"] > 0 for row in rows)
    finally:
        timing.reset()
