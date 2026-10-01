from collections import Counter
from itertools import combinations, combinations_with_replacement, permutations, product

import clingo
import pytest

from gentians.arguments import Arguments
from gentians.clauses import generator, mode_compiler
from gentians.clauses.analysis import ground_relations, inference, rule_properties
from gentians.clauses.analysis.inference import _closed_world_properties
from gentians.clauses.analysis.relation_properties import (
    _collect_projection_implications,
    _collect_dependency_properties,
    _collect_tuple_mutex,
    _is_reflexive,
    _is_total_order,
    _is_transitive,
    _is_acyclic,
)
from gentians.clauses.canonicalization import arithmetic, expression as expressions
from gentians.clauses.canonicalization.clauses import ClauseCanonicalizer
from gentians.clauses.canonicalization.expression import ArithmeticExpression
from gentians.clauses.canonicalization.expression_normalization import _term_comparison
from gentians.clauses.canonicalization.linear_constraint import LinearConstraint
from gentians.clauses.canonicalization.linear_normalization import (
    _comparison_linear_template,
    _linear_assignment_expression,
)
from gentians.clauses.clause_space import ClauseSpace
from gentians.clauses.reified_clause import ReifiedClause, instantiate_head
from gentians.clauses.reified_literal import ReifiedLiteral
from gentians.language import parse_text, terms as mode_terms
from gentians.language.asp import parse_program, parse_rule
from gentians.language.ir.comparison_literal import ComparisonLiteral


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
    relation = _term_comparison(ReifiedLiteral("body", 0, 0, (7, 3)), comparison)
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
        ("empty", 3): frozenset(),
        ("one", 1): frozenset({(1,), (2,)}),
        ("true", 0): frozenset({()}),
    }
    mutex = set()
    implies = set()
    _collect_tuple_mutex(extensions, mutex)
    _collect_projection_implications(extensions, extensions, implies)
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
        reflexive = _is_reflexive(rows)
        domain = {value for pair in rows for value in pair}
        ordered = len(domain) >= 2 and reflexive and transitive and all(
            (left, right) in rows or (right, left) in rows for left, right in permutations(domain, 2)
        ) and not any(left != right and (right, left) in rows for left, right in rows)
        assert _is_transitive(rows) == transitive
        assert _is_total_order(rows, transitive, reflexive) == ordered


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
    assert _is_acyclic(path)
    assert not _is_acyclic(path | {(10000, 0)})
    assert not _is_acyclic(path | {("a", "b"), ("b", "a")})
    assert not _is_acyclic(frozenset({("a", "a")}))
    assert not _is_acyclic(frozenset())


def test_acyclicity_matches_all_three_element_relations():
    pairs = tuple(product(range(3), repeat=2))
    for mask in range(1 << len(pairs)):
        rows = frozenset(pair for bit, pair in enumerate(pairs) if mask & (1 << bit))
        reachable = set(rows)
        for middle in range(3):
            reachable |= {(left, right) for left in range(3) for right in range(3)
                          if (left, middle) in reachable and (middle, right) in reachable}
        assert _is_acyclic(rows) == (bool(rows) and not any((node, node) in reachable for node in range(3)))


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
