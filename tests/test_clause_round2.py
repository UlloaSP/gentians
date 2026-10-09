"""Regressions for the second measured generation optimization round."""

import gc
from dataclasses import replace

import pytest

from gentians import Arguments
from gentians.clauses import generate_clause_space
from gentians.clauses.canonicalization.canonical_clause import CanonicalArithmeticClause
from gentians.clauses.generator import _ClauseGenerator
from gentians.clauses.mode_compiler import _clause_modes
from gentians.clauses.recipes import RuleRecipes
from gentians.clauses.reified_literal import ReifiedLiteral
from gentians.language import parse_text
from gentians.language.asp import parse_rule
from benchmarks.synthetic_million import task_text


def options(**settings):
    args = Arguments()
    args.clause_generation.update(settings)
    return args


@pytest.mark.parametrize("maxv", [1, 2, 5])
@pytest.mark.parametrize("heads", ["", "#modeh(1,h(var(world,input))).", "#modeh(1,h(var(world,any))). #modeh(1,g(var(world,input)))."], ids=["none", "normal", "two"])
@pytest.mark.parametrize("head_limit", [0, 1])
@pytest.mark.parametrize("engine", ["direct", "subsets"])
def test_extended_unary_family_keeps_complete_native_space(maxv, heads, head_limit, engine):
    task = parse_text(task_text(4).replace("#maxv(1).", f"#maxv({maxv}).")
                      .replace("#maxhl(0).", f"#maxhl({head_limit}).").replace("#maxbl(6).", "#maxbl(3).") + heads)
    if heads and not head_limit:
        for policy in ("asp", engine):
            with pytest.raises(ValueError, match="exceeds #maxhl"):
                generate_clause_space(task, options(engine=policy))
        return
    expected = generate_clause_space(task, options(engine="asp", transport="python"))
    actual = generate_clause_space(task, options(engine=engine))
    assert actual.entries == expected.entries
    assert all(str(entry.statement) == entry.text for entry in actual.entries)


def test_direct_headed_family_obeys_positive_only_constraint_proof():
    task = parse_text("1{active(1);active(2)}1. p(X):-active(X). #pos({h(1)},{}). #modeh(1,h(var(x,input))). "
                      "#modeb(1,p(var(x,output))). #maxv(3). #maxbl(1).")
    expected = generate_clause_space(task, options(engine="asp"))
    actual = generate_clause_space(task, options(engine="direct"))
    assert actual.entries == expected.entries
    assert actual.clauses == ("h(V0) :- p(V0).",)


@pytest.mark.parametrize("head", [
    "#modeh(1,h(var(x,input))). #modeb(1,h(var(x,output))).",
    "#modeh(1,{h(var(x,input))}).",
    "#modeh(1,h(var(x,input,a))). #modeb(1,q(var(x,output,b))).",
    "#modeh(1,h(var(y,input))).",
])
def test_unary_direct_proof_rejects_interacting_heads_and_labels(head):
    task = parse_text(head + "#modeb(1,p(var(x,output))). #maxv(3). #maxbl(2).")
    with pytest.raises(ValueError, match="independent unary"):
        generate_clause_space(task, options(engine="direct"))
    assert generate_clause_space(task, options()).entries == generate_clause_space(task, options(engine="asp")).entries


@pytest.mark.parametrize("source", [
    "same(a,a). same(b,b). #modeb(2,same(var(x,output),var(x,output))).",
    "same(a,a). same(b,b). #modeb(2,same(var(x,output),var(y,output))).",
    "same(a,a). same(b,b). #modeb(2,same(var(x,output,a),var(x,output,b))).",
    "same(a,a). same(b,b). #modeb(2,same(var(x,output),var(x,output))). #modeb(1,not same(var(x,input),var(x,input))).",
    "same(a,a,a). same(b,b,b). #modeb(1,same(var(x,output),var(x,output),var(x,output))).",
    "e(a,b). e(b,c). #modeb(2,e(var(x,output),var(x,output))).",
    "e(a,b). e(b,a). #modeh(1,e(var(x,input),var(x,input))). #modeb(1,d(var(x,output))).",
    "e(a,b). #modeb(1,e(a,var(x,output))). #modeb(1,e((var(x,output);var(x,output)),var(x,output))).",
    "e(a,b). #modeb(1,p(var(x,input)): e(var(x,input),var(x,input))). #modeb(1,d(var(x,output))).",
])
def test_property_binding_domains_preserve_sign_types_labels_scopes_and_full_entries(source):
    task = parse_text(source + " #maxv(3). #maxbl(2).")
    expected = generate_clause_space(task, options(engine="asp", transport="python"))
    actual = generate_clause_space(task, options(engine="asp", bindings="properties"))
    assert actual.entries == expected.entries
    assert all(str(entry.statement) == entry.text for entry in actual.entries)


@pytest.mark.parametrize("source", [
    'p("á漢🙂") :- q("a,b\\\"c"), not -r(f(X)).',
    "p(X);q(X) :- r(X).",
    "1 {p(X):q(X); r(X)} 2 :- s(X), #count{Y:t(X,Y)} > 1.",
    "#false :- q(X), X = (Y/2), Y!=0.",
    'p("' + "á🙂" * 3000 + '").',
], ids=["unicode", "disjunction", "aggregate", "division", "large-unicode"])
def test_fused_native_build_and_format_keeps_entire_clingo_syntax(source):
    from clingo._internal import _ffi
    from gentians.clauses.native_syntax import RuleBuilder
    node = parse_rule(source)
    builder = RuleBuilder()
    if builder.renderer is None:
        pytest.skip("optional native extension not built")
    parts = int(_ffi.cast("uintptr_t", node.head._rep)), tuple(int(_ffi.cast("uintptr_t", item._rep)) for item in node.body)
    assert builder.render_parts((parts, parts)) == (str(node), str(node))
    del builder
    gc.collect()
    assert str(node) == str(parse_rule(source))


def test_prepared_native_addresses_keep_owners_after_cache_eviction_and_portable_fallback(monkeypatch):
    from gentians.clauses import native_syntax
    modes = {m.id: m for m in _clause_modes(parse_text("#modeb(*,p(var(x,output))). #maxbl(9000)."))}
    mode_id = next(iter(modes))
    recipe = CanonicalArithmeticClause((), tuple(ReifiedLiteral("body", slot, mode_id, (slot,))
                                                 for slot in range(8300)), ())
    expected = recipe.render(modes)
    actual = RuleRecipes(modes)
    assert actual.render(recipe) == expected
    assert actual.literal_pair.cache_info().currsize <= 8192
    monkeypatch.setattr(native_syntax, "_records", None)
    portable = RuleRecipes(modes)
    assert portable.render(recipe) == expected
    assert str(portable.statement(recipe)) == expected


def test_native_decode_rejects_incomplete_unknown_modes_and_missing_bindings():
    from gentians.clauses.records import _records
    from gentians.clauses.reified_clause import ReifiedClause
    if _records is None:
        pytest.skip("optional native extension not built")
    import struct
    plan = _records.prepare_decode(2, (("body", 0, ((1,),)),), ReifiedLiteral, ReifiedClause)
    with pytest.raises(ValueError, match="incomplete"):
        _records.decode_block(plan, b"x")
    with pytest.raises(RuntimeError, match="unknown"):
        _records.decode_block(plan, struct.pack("qq", 99, 1))
    with pytest.raises(RuntimeError, match="no variable"):
        _records.decode_block(plan, struct.pack("qq", 0, -1))
    expected = ReifiedClause((), (ReifiedLiteral("body", 0, 0, (1,)),))
    assert _records.decode_block(plan, struct.pack("qq", 0, 1)) == [expected]
    with pytest.raises(ValueError, match="plan"):
        _records.prepare_decode(2, (("body", 0, ((3,),)),), ReifiedLiteral, ReifiedClause)


def test_preparation_caches_are_task_local_and_preserve_exact_size_fact_domains(monkeypatch):
    from gentians.clauses import generator
    original = generator._facts
    calls = []

    def facts(*args):
        calls.append(args[5])
        return original(*args)

    monkeypatch.setattr(generator, "_facts", facts)
    task = parse_text("#modeb(1,p(var(x,output))). #maxbl(12). #maxv(2).")
    first = _ClauseGenerator(task, options())
    assert first._fact_text() == first._fact_text()
    assert calls == [12]
    for size in range(11):
        text = first._fact_text(exact_size=size)
        assert f"max_body({size})." in text
        assert f"Size != {size}" in text
    assert len(first.fact_cache) == 8
    second = _ClauseGenerator(replace(task, max_variables=3), options())
    assert "max_vars(3)." in second._fact_text()
    assert first.property_maps is not second.property_maps


def test_metadata_is_interned_only_for_identical_signed_masks_and_source_cost():
    from gentians.clauses.mode_metadata import ModeMetadata
    modes = {m.id: m for m in _clause_modes(parse_text("#modeb(1,p(var(x,output))). #modeb(1,-p(var(x,output)))."))}
    metadata = ModeMetadata(modes)
    positive = next(m.id for m in modes.values() if m.literal.atom.signature == ("p", 1))
    negative = next(m.id for m in modes.values() if m.literal.atom.signature == ("-p", 1))
    a = metadata.for_modes((), (positive,))
    assert metadata.for_modes((), (positive,)) is a
    assert metadata.for_modes((), (negative,)) != a
    assert metadata.from_masks(a.head_mask, a.dep_mask, 2) != a
