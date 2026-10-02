from dataclasses import fields, replace
from itertools import combinations, permutations, product
from math import prod
from random import Random

import pytest

from gentians.clauses import arithmetic_literal
from gentians.clauses.analysis import inference, relation_properties as relations, rule_properties
from gentians.clauses.analysis.ground_relations import ClosedWorld
from gentians.clauses.canonicalization import arithmetic
from gentians.clauses.canonicalization.expression_normalization import _term_comparison
from benchmarks.clause_decoder_reference import _clause_from_truth
from gentians.clauses.mode_compiler import _clause_modes
from gentians.clauses.reified_clause import ReifiedClause
from gentians.clauses.reified_literal import ReifiedLiteral
from gentians.language import parse_text, terms
from gentians.language.asp import parse_program
from gentians.language.ast_nodes import binding_term


@pytest.mark.parametrize("operator,expected", [("+", (1, 1, -1)), ("-", (1, -1, -1)), ("*", None)])
def test_coefficient_metadata_including_none_is_immutable_and_not_recomputed(monkeypatch, operator, expected):
    mode = _clause_modes(parse_text(f"#modeb(1,var(numeric,input){operator}var(numeric,input)=var(numeric,output))."))[0]
    literal = mode.literal
    assert isinstance(literal, arithmetic_literal.ArithmeticLiteral)
    clone = replace(literal)
    prior_hash = hash(literal)
    assert literal.coefficients == expected and clone.coefficients == expected

    def no_walk(*_args):
        raise AssertionError("prepared coefficients must not walk their template again")

    monkeypatch.setattr(arithmetic_literal, "_linear_coefficients", no_walk)
    fresh = replace(literal)
    assert fresh == literal and hash(fresh) == prior_hash
    for _ in range(3):
        assert literal.coefficients == expected
        assert literal.linear == (expected is not None)
    assert hash(literal) == prior_hash and clone == literal
    assert not next(field for field in fields(literal) if field.name == "_coefficients").compare


@pytest.mark.parametrize("expression", [
    '(f(var(t,input)),var(t,input)) < (a,"x")',
    'var(numeric,input)+1 <= |var(numeric,input)-2|',
    '1 < var(numeric,input) < 5',
    'var(numeric,input) = 1..9',
    '~var(numeric,input) != -3',
])
def test_prepared_comparisons_match_native_instantiation_without_rewalking(monkeypatch, expression):
    mode = _clause_modes(parse_text(f"#modeb(1,{expression})."))[0]
    variables = tuple(range(len(mode.bindings)))
    bindings = iter(binding_term(f"V{i}") for i in variables)
    expected = tuple(terms.instantiate(term, bindings) for term in mode.literal.terms)

    def no_walk(*_args):
        raise AssertionError("comparison decoding must use compiled instructions")

    monkeypatch.setattr(terms, "_postorder", no_walk)
    comparison = _term_comparison(ReifiedLiteral("body", 0, mode.id, variables), mode)
    assert tuple(term.instantiate() for term in comparison.terms) == expected
    assert comparison.operators == mode.literal.operators
    with pytest.raises(ValueError, match="more assigned variables"):
        _term_comparison(ReifiedLiteral("body", 0, mode.id, (*variables, 99)), mode)


def test_fused_clause_traits_keep_external_safe_numeric_sets_and_literal_order(monkeypatch):
    modes = _clause_modes(parse_text("#modeh(1,p(var(t,input))). "
        "#modeb(1,d(var(numeric,output),var(t,input))). "
        "#modeb(1,not n(var(t,input))). "
        "#modeb(1,#count{var(t,any):q(var(t,any))}=var(numeric,output)). "
        "#modeb(1,var(numeric,input)*var(numeric,input)=var(numeric,output))."))
    by_id = {mode.id: mode for mode in modes}
    head = (ReifiedLiteral("head", 0, modes[0].id, (4,)),)
    body = tuple(ReifiedLiteral("body", index, mode.id, variables) for index, (mode, variables) in enumerate(zip(
        modes[1:], ((0, 4), (7,), (6, 5, 2), (0, 2, 3)), strict=True)))
    clause = ReifiedClause(head, body)
    builtin = tuple(literal for literal in body if by_id[literal.mode_id].builtin)
    non_builtin = tuple(literal for literal in body if not by_id[literal.mode_id].builtin)
    external = frozenset(variable for literal in (*head, *non_builtin) for variable in literal.variables)
    safe = frozenset(variable for literal in body if by_id[literal.mode_id].positive_atom for variable in literal.variables)
    safe |= frozenset(literal.variables[-1] for literal in body if by_id[literal.mode_id].output_guard)
    numeric = frozenset(variable for literal in (*head, *body) for index, variable in enumerate(literal.variables)
                        if by_id[literal.mode_id].numeric_builtin or index in by_id[literal.mode_id].numeric_positions)
    calls = []

    def systems(literals, _modes, ext, bound, numbers, width):
        calls.append((literals, ext, bound, numbers, width))
        return ()

    monkeypatch.setattr(arithmetic, "_canonical_systems", systems)
    result = arithmetic.canonical_arithmetic_clause(clause, by_id, 8)
    assert calls == [(builtin, external, safe, numeric, 8)]
    assert result is not None and result.head == head and result.body == non_builtin
    calls.clear()
    plain = arithmetic.canonical_arithmetic_clause(ReifiedClause(head, non_builtin), by_id, 8)
    assert plain is not None and plain.body == non_builtin and calls == []


@pytest.mark.parametrize("negation", [None, frozenset(), frozenset({("-a", 2), ("m", 2), ("z", 2)})])
def test_grouped_pair_properties_match_predicate_pair_oracle(negation):
    rng = Random(19)
    for _ in range(35):
        first = frozenset(row for row in product((0, 1, "a"), repeat=2) if rng.randrange(2))
        second = frozenset(row for row in product((0, 1, "a"), repeat=2) if rng.randrange(2))
        extensions = {("z", 2): first, ("b", 2): second, ("-a", 2): first, ("m", 2): second,
                      ("empty", 2): frozenset(), ("nil", 0): frozenset(), ("yes", 0): frozenset({()}),
                      ("one", 1): frozenset({(0,)}), ("other", 1): frozenset({("a",)})}
        positions = {p: tuple(frozenset(row[i] for row in rows) for i in range(p[1])) for p, rows in extensions.items()}
        equivalent, implies, mutex, inverse, complement, disjoint = set(), set(), set(), set(), set(), set()
        for left, right in combinations(sorted(extensions), 2):
            a, b = extensions[left], extensions[right]
            if left[1] == right[1]:
                if a == b:
                    equivalent.add((left, right))
                elif a <= b:
                    implies.add((left, right))
                elif b <= a:
                    implies.add((right, left))
                if a.isdisjoint(b):
                    mutex.add((left, right))
                    columns = tuple(x | y for x, y in zip(positions[left], positions[right], strict=True))
                    count = len(a) + len(b)
                    if (negation is None or {left, right} <= negation) and count and prod(map(len, columns)) == count:
                        complement.add((left, right))
                if left[1] == 2 and a == frozenset((y, x) for x, y in b):
                    inverse.add((left, right))
            if all(positions[left]) and all(positions[right]) and not left[1] == right[1] == 1:
                for i, a_values in enumerate(positions[left]):
                    for j, b_values in enumerate(positions[right]):
                        if a_values.isdisjoint(b_values):
                            disjoint.update({(left, i, right, j), (right, j, left, i)})
        actual = inference._context_properties(ClosedWorld(extensions, {}, {}, frozenset(), frozenset(), ()), None, negation)
        assert (actual.equivalent, actual.implies, actual.mutex, actual.inverse, actual.complement, actual.disjoint_projection) == (
            equivalent, implies, mutex, inverse, complement, disjoint)


def test_projected_inclusion_is_proven_once_for_all_source_and_target_aliases():
    visits = []

    class CountingRows(frozenset):
        def __iter__(self):
            for row in super().__iter__():
                visits.append(row)
                yield row

    plain = frozenset((n, n, n) for n in range(10))
    rows = CountingRows(plain)
    sources = {(f"s{i}", 3): rows for i in range(4)}
    targets = {(f"-t{i}", 2): frozenset((n, n) for n in range(10)) for i in range(5)}
    positions = {p: relations._position_values(p[1], plain if p in sources else values)
                 for p, values in {**sources, **targets}.items()}
    actual = set()
    relations._collect_projection_implications(sources, targets, actual, positions)
    expected = {(source, target, projection) for source in sources for target in targets
                for projection in permutations(range(3), 2)}
    assert actual == expected and len(visits) == 60


def test_domain_inclusion_shares_value_proofs_but_keeps_original_yield_order():
    comparisons = []

    class CountingValues(frozenset):
        def __le__(self, other):
            comparisons.append((self, other))
            return super().__le__(other)

    positions = {(f"p{i}", 2): (CountingValues({1, 2}), CountingValues()) for i in range(8)}
    domains = {("universal", (f"d{i}", 1)): (frozenset({1, 2, 3}), frozenset()) for i in range(6)}
    expected = [(key, offset, p, i) for key, columns in domains.items() for offset, domain in enumerate(columns)
                for p, values in positions.items() for i, column in enumerate(values) if frozenset(column) <= domain]
    actual = list(relations._domain_covers(domains, positions))
    assert actual == expected and len(comparisons) == 4


def test_minimal_dependency_determinants_match_all_pairs_including_equal_sets():
    rng = Random(55)
    p, q = ("p", 6), ("-p", 6)
    for _ in range(60):
        single = {(predicate, source, output) for predicate in (p, q) for source, output in permutations(range(6), 2)
                  if rng.randrange(8) == 0}
        composite = {(predicate, inputs, output) for predicate in (p, q) for count in range(4)
                     for inputs in combinations(range(6), count) for output in range(6)
                     if output not in inputs and rng.randrange(3) == 0}
        composite |= {(predicate, tuple(reversed(inputs)), output) for predicate, inputs, output in tuple(composite)}
        expected = {item for item in composite if not any(predicate == item[0] and output == item[2] and source in item[1]
                    for predicate, source, output in single) and not any(predicate == item[0] and output == item[2]
                    and set(inputs) < set(item[1]) for predicate, inputs, output in composite)}
        assert relations._without_subsumed_functional_set(composite, single) == expected


def test_rule_syntax_cache_reuses_hints_while_clingo_proves_every_context(monkeypatch):
    inspected, proved = [], []
    inspect, prove = inference._rule_syntax, inference._hold_in_every_model

    def syntax(program):
        inspected.append(program)
        return inspect(program)

    def proofs(program, violations):
        proved.append(program)
        return prove(program, violations)

    monkeypatch.setattr(inference, "_rule_syntax", syntax)
    monkeypatch.setattr(inference, "_hold_in_every_model", proofs)
    program = parse_program("1 {p(1);p(2)} 1.")
    result = inference._closed_world_properties((program,) * 3)
    assert result.cardinality_upper == frozenset({(("p", 1), 1)})
    assert inspected == [program] and proved == [program] * 3
    changed = parse_program("1 {p(1);p(2)} 1. p(3).")
    assert not inference._closed_world_properties((program, changed)).cardinality_upper
    assert inspected[-2:] == [program, changed]


def test_rule_syntax_cache_is_bounded_and_local_to_one_analysis(monkeypatch):
    calls = []
    original = inference._rule_syntax

    def inspect(program):
        calls.append(program)
        return original(program)

    monkeypatch.setattr(inference, "_rule_syntax", inspect)
    programs = tuple(parse_program(f"q({i}).") for i in range(9))
    inference._closed_world_properties((*programs, programs[0]))
    assert len(calls) == 10
    inference._closed_world_properties((programs[0],))
    assert len(calls) == 11


def test_cached_rule_syntax_keeps_context_dependent_key_propagation():
    syntax = rule_properties._rule_syntax(parse_program("r(A,B,C) :- q(A,B),C=B*B."))
    for inputs, expected in (((0,), (0,)), ((1,), (1, 2))):
        keys = {(("q", 2), inputs)}
        rule_properties._collect_clause_defined_properties(keys, set(), set(), set(), set(), syntax)
        assert (("r", 3), expected) in keys


@pytest.mark.parametrize("threshold", [0, 1, 6, 10000])
def test_partition_capacity_preserves_bruteforce_minimal_groups_and_limit(monkeypatch, threshold):
    monkeypatch.setattr(relations, "MAX_PRODUCT_SIZE", threshold)
    rng = Random(42)
    for _ in range(12):
        extensions = {(f"p{i}", 2): frozenset(row for row in product(range(3), repeat=2) if rng.randrange(7) == i)
                      for i in range(6)}
        positions = {p: relations._position_values(2, rows) for p, rows in extensions.items()}
        minimal, expected = [], set()
        predicates = [p for p, rows in extensions.items() if rows]
        for count in range(3, min(len(predicates), 6) + 1):
            for group in combinations(predicates, count):
                if any(set(prior) <= set(group) for prior in minimal):
                    continue
                if any(not extensions[a].isdisjoint(extensions[b]) for a, b in combinations(group, 2)):
                    continue
                union = frozenset().union(*(extensions[p] for p in group))
                columns = tuple({row[i] for row in union} for i in range(2))
                if len(union) <= threshold and set(product(*columns)) == union:
                    expected.add(group)
                    minimal.append(group)
        assert relations._partition_properties(extensions, positions) == expected


def test_decoder_does_not_slice_candidate_tuples_and_keeps_truth_probe_order():
    class NoSlices(tuple):
        def __getitem__(self, index):
            assert not isinstance(index, slice)
            return super().__getitem__(index)

    calls = []
    choices = NoSlices((mode, (), 1000 + mode) for mode in range(100))

    def truth(literal):
        calls.append(literal)
        return literal in {1, 1098}

    result = _clause_from_truth(truth, (("body", 0, ((98, (), 1),), ()), ("body", 1, choices, ())))
    assert [literal.mode_id for literal in result.body] == [98, 98]
    assert calls == [1, 1098]
