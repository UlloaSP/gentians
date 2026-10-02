from dataclasses import fields, replace
from itertools import combinations, permutations, product
from random import Random

import pytest

from gentians.clauses.analysis import inference, relation_properties as relations
from gentians.clauses.analysis.ground_relations import ClosedWorld
from gentians.clauses.analysis.properties import ClosedWorldProperties
from gentians.clauses.arithmetic_literal import ArithmeticLiteral
from gentians.clauses.canonicalization.expression import ArithmeticExpression
from gentians.clauses.canonicalization.expression_normalization import _mode_expression
from gentians.clauses.decoder import _clause_from_truth
from gentians.clauses.mode_compiler import _clause_modes
from gentians.clauses.mode_facts import _ordered_conditions, compile_mode_facts, predicate_ids
from gentians.clauses.reified_literal import ReifiedLiteral
from gentians.language import parse_text, terms
from gentians.language.ast_nodes import binding_term
from gentians.language.ir.comparison_literal import ComparisonLiteral


@pytest.mark.parametrize("arity", range(6))
def test_argument_properties_match_independent_pairwise_oracle(arity):
    rng = Random(81 + arity)
    for count in range(35):
        rows = frozenset(tuple(rng.choice((0, 1, "a")) for _ in range(arity)) for _ in range(count))
        predicate = ("-p", arity)
        equal, distinct = set(), set()
        relations._collect_argument_properties(predicate, rows, equal, distinct)
        assert equal == {(predicate, left, right) for left, right in combinations(range(arity), 2)
                         if len(rows) > 1 and all(row[left] == row[right] for row in rows)}
        assert distinct == {(predicate, left, right) for left, right in combinations(range(arity), 2)
                            if all(row[left] != row[right] for row in rows)}


def test_identical_extensions_share_analysis_and_keep_signed_predicates(monkeypatch):
    calls = []
    original = inference._collect_dependency_properties

    def collect(*args):
        calls.append(args[0])
        return original(*args)

    monkeypatch.setattr(inference, "_collect_dependency_properties", collect)
    rows = frozenset({(1, 1), (2, 2), (3, 3)})
    extensions = {("p", 2): rows, ("q", 2): rows, ("-p", 2): rows,
                  ("empty", 2): frozenset(), ("-empty", 2): frozenset(),
                  ("zero", 0): frozenset(), ("nullary", 0): frozenset({()})}
    world = ClosedWorld(extensions, {}, {}, frozenset(), frozenset(), ())
    result = inference._context_properties(world, None, frozenset())
    assert len(calls) == 4
    assert result.symmetric >= {("p", 2), ("q", 2), ("-p", 2)}
    for predicate in (("p", 2), ("q", 2), ("-p", 2)):
        assert (predicate, 0, 1) in result.arg_equal
        assert (predicate, (0,)) in result.keys
        assert (predicate, (1,)) in result.keys
    assert result.empty == frozenset({("empty", 2), ("-empty", 2), ("zero", 0)})
    assert (("empty", 2), 0, 1) in result.arg_distinct
    assert (("-empty", 2), 0, 1) in result.arg_distinct


def test_binary_indexes_and_order_count_match_mixed_domain_oracles():
    rng = Random(17)
    pairs = tuple(product((0, 1, "a", "b"), repeat=2))
    for _ in range(200):
        rows = frozenset(pair for pair in pairs if rng.randrange(2))
        domain = frozenset(value for row in rows for value in row)
        successors = relations._binary_successors(rows)
        snapshot = {value: set(following) for value, following in successors.items()}
        transitive = len(rows) >= 3 and all((left, right) in rows for left, middle in rows
                                          for other, right in rows if middle == other)
        reflexive = bool(domain) and all((value, value) in rows for value in domain)
        antisymmetric = all(left == right or (right, left) not in rows for left, right in rows)
        total = len(domain) >= 2 and transitive and reflexive and antisymmetric and all(
            (left, right) in rows or (right, left) in rows for left, right in permutations(domain, 2))
        assert relations._is_transitive(successors, len(rows)) == transitive
        assert relations._is_reflexive(rows, domain) == reflexive
        assert relations._is_total_order(len(rows), len(domain), transitive, reflexive, antisymmetric) == total
        reachable = set(rows)
        for middle in domain:
            reachable |= {(left, right) for left, right in product(domain, repeat=2)
                          if (left, middle) in reachable and (middle, right) in reachable}
        assert relations._is_acyclic(successors) == (bool(rows) and not any((x, x) in reachable for x in domain))
        assert successors == snapshot


@pytest.mark.parametrize("count", [0, 1, 2, 5, 30])
def test_order_cardinality_retains_reflexivity_transitivity_and_antisymmetry(count):
    for transitive, reflexive, antisymmetric in product((False, True), repeat=3):
        expected = count >= 2 and transitive and reflexive and antisymmetric
        assert relations._is_total_order(count * (count + 1) // 2, count,
                                         transitive, reflexive, antisymmetric) == expected
        assert not relations._is_total_order(count * (count + 1) // 2 + 1, count,
                                             transitive, reflexive, antisymmetric)


@pytest.mark.parametrize("targets", [1, 2, 4])
def test_streaming_projection_checks_match_full_projection_oracle(targets):
    rng = Random(68)
    for _ in range(40):
        source = ("source", 3)
        rows = frozenset(tuple(rng.randrange(3) for _ in range(3)) for _ in range(rng.randrange(15)))
        extensions = {source: rows, **{(f"p{i}", i % 2 + 1): frozenset(
            tuple(rng.randrange(3) for _ in range(i % 2 + 1)) for _ in range(rng.randrange(10)))
            for i in range(targets)}}
        positions = {p: relations._position_values(p[1], values) for p, values in extensions.items()}
        actual = set()
        relations._collect_projection_implications({source: rows}, extensions, actual, positions)
        expected = {(source, target, projection) for target, values in extensions.items()
                    if source[1] > target[1] and values for projection in permutations(range(3), target[1])
                    if {tuple(row[index] for index in projection) for row in rows} <= values}
        assert actual == expected


def test_projection_failure_stops_before_scanning_the_complete_extension():
    visited = []

    class CountingRows(frozenset):
        def __iter__(self):
            for row in super().__iter__():
                visited.append(row)
                yield row

    plain = frozenset((x, x, x) for x in range(30))
    rows = CountingRows(plain)
    target = frozenset((x, y) for x, y in product(range(30), repeat=2) if x != y)
    positions = {("p", 3): relations._position_values(3, plain),
                 ("q", 2): relations._position_values(2, target)}
    actual = set()
    relations._collect_projection_implications({("p", 3): rows}, {("q", 2): target}, actual, positions)
    assert not actual
    assert len(visited) == 6


def test_reduction_builds_one_key_index_after_context_intersection(monkeypatch):
    calls = []
    original = inference._key_sets_by_predicate

    def index(keys):
        calls.append(keys)
        return original(keys)

    monkeypatch.setattr(inference, "_key_sets_by_predicate", index)
    p = ("p", 3)
    properties = replace(ClosedWorldProperties.none(), keys=frozenset({(p, (0,))}),
                         functional=frozenset({(p, 0, 1), (p, 1, 2)}),
                         functional_set=frozenset({(p, (0, 1), 2), (p, (1, 2), 0)}))
    reduced = inference._reduced(properties)
    assert calls == [set(properties.keys)]
    assert reduced.functional == frozenset({(p, 1, 2)})
    assert reduced.functional_set == frozenset({(p, (1, 2), 0)})


@pytest.mark.parametrize("source", [
    "var(numeric,input)*var(numeric,input)=var(numeric,output)",
    "(var(numeric,input)+var(numeric,input))*var(numeric,input)=var(numeric,output)",
    "|var(numeric,input)-var(numeric,input)|=var(numeric,output)",
    "var(numeric,input)/var(numeric,input)=var(numeric,output)",
])
def test_compiled_arithmetic_steps_retain_binding_order_without_rewalking_ast(monkeypatch, source):
    mode = _clause_modes(parse_text(f"#modeb(1,{source})."))[0]
    if isinstance(mode.literal, ComparisonLiteral):
        mode = replace(mode, literal=ArithmeticLiteral(*mode.literal.terms))
    assert isinstance(mode.literal, ArithmeticLiteral)
    inputs = tuple(range(len(mode.bindings) - 1))
    known = {x: ArithmeticExpression.var(x) for x in inputs}
    literal = ReifiedLiteral("body", 0, mode.id, (*inputs, 99))
    expected = _mode_expression(literal, mode, known)
    native = terms.instantiate(mode.literal.expression, iter(binding_term(f"V{x}") for x in inputs))
    assert expected.instantiate() == native

    def no_walk(*_args):
        raise AssertionError("compiled arithmetic mode must not traverse its AST again")

    monkeypatch.setattr(terms, "_postorder", no_walk)
    assert _mode_expression(literal, mode, known) == expected
    assert expected.variables == frozenset(inputs)


def test_condition_order_retains_multiplicity_and_original_deletion_indexes():
    for conditions in ((), ("b",), ("c", "a", "b", "a"), ("x",) * 5):
        ordered, positions = _ordered_conditions(conditions)
        assert ordered == tuple(sorted(conditions, key=repr))
        for index, position in enumerate(positions):
            assert ordered[:position] + ordered[position + 1:] == tuple(sorted(
                conditions[:index] + conditions[index + 1:], key=repr))


def test_conditional_shorter_facts_match_original_ordered_multiset_rule():
    task = parse_text("#modeb(1,p(var(t,any)):q(var(t,input)),r(var(t,input)),q(var(t,input))). "
                      "#modeb(1,p(var(t,any)):q(var(t,input)),r(var(t,input))). "
                      "#modeb(1,p(var(t,any)):q(var(t,input)),q(var(t,input))).")
    modes = _clause_modes(task)
    forms = {(m.section, m.literal.conclusion, tuple(sorted(m.literal.conditions, key=repr))) for m in modes}
    expected = {f"conditional_shorter_mode({m.id},{index})." for m in modes
                for index in range(len(m.literal.conditions)) if (
                    m.section, m.literal.conclusion, tuple(sorted(
                        m.literal.conditions[:index] + m.literal.conditions[index + 1:], key=repr))) in forms}
    actual = {fact for fact in compile_mode_facts(modes, predicate_ids(modes), 1, 4)
              if fact.startswith("conditional_shorter_mode(")}
    assert actual == expected


def test_mode_hash_caches_complete_identity_and_does_not_affect_equality():
    mode = _clause_modes(parse_text("#modeb(1,p(var(t,input)))."))[0]
    equal = replace(mode)
    assert mode._hash is None and equal._hash is None
    expected = hash(tuple(getattr(mode, field.name) for field in fields(mode) if field.compare))
    assert hash(mode) == expected and mode._hash == expected
    assert mode == equal and hash(equal) == hash(mode)
    assert {mode: "value"}[equal] == "value"
    changed = replace(mode, recall=2)
    assert changed._hash is None and changed != mode
    assert hash(changed) == hash(tuple(getattr(changed, field.name) for field in fields(changed) if field.compare))


def test_decoder_bisects_large_sparse_mode_indexes_and_resets_each_section():
    choices = tuple((index * 3, (), 10000 + index) for index in range(2000))
    index = (("body", 0, ((4500, (), 1),), ()), ("body", 1, choices, ()),
             ("body", 2, ((4500, (), 3),), ()), ("body", 3, ((4500, (), 4),), ()),
             ("head", 0, ((0, (), 5),), ()))
    calls = []

    def truth(literal):
        calls.append(literal)
        return literal in {1, 11500, 4, 5}

    clause = _clause_from_truth(truth, index)
    assert [literal.mode_id for literal in clause.body] == [4500, 4500]
    assert [literal.mode_id for literal in clause.head] == [0]
    assert calls == [1, 11500, 3, 5]
