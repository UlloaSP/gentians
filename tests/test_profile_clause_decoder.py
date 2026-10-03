from pathlib import Path

import pytest

from benchmarks.profile_clause_decoder import compare_decoders, materialize, space_fingerprint
from gentians import timing
from gentians.arguments import Arguments
from gentians.clauses.generator import generate_clause_space
from gentians.language import parse_file, parse_text


@pytest.fixture(autouse=True)
def no_external_instrumentation(monkeypatch):
    enabled = timing.is_enabled()
    timing.set_enabled(False)
    monkeypatch.delenv("GENTIANS_CLINGO_METRICS_PATH", raising=False)
    try:
        yield
    finally:
        timing.set_enabled(enabled)


@pytest.mark.parametrize("case", [
    "heads/fact_constant.lp",
    "heads/constraint.lp",
    "heads/disjunction_exact.lp",
    "heads/disjunction_modehd.lp",
    "heads/choice_modeha.lp",
    "heads/cardinality_variable_bounds.lp",
    "heads/aggregate_count.lp",
    "heads/empty_choice.lp",
    "heads/empty_count_aggregate.lp",
    "heads/function_and_tuple_terms.lp",
    "heads/modec_conditions.lp",
    "heads/strong_negation.lp",
    "heads/default_negation.lp",
    "bodies/default_negated_strong_negation.lp",
    "bodies/conditional_literal.lp",
    "bodies/modec_comparison_condition.lp",
    "aggregates/set_aggregate.lp",
])
def test_all_decoders_agree_on_complete_syntax_spaces(case):
    task = parse_file(Path(__file__).parent / "syntax_matrix" / "cases" / case)
    result = compare_decoders(task, Arguments(), limit=0)
    assert result["exhausted"] and result["models"] > 0
    assert not timing.is_enabled()


def test_complete_space_and_metadata_match_production():
    task = parse_text("""
        #maxv(2). #maxbl(2). #maxhl(1).
        #modeh(1,p(var(t,input))).
        #modeb(2,q(var(t,any),var(t,any))).
        #modeb(1,not -r(var(t,input))).
        #pos({p(a)},{},{q(a,b). -r(b).}).
        #neg({p(b)},{},{q(b,b).}).
    """)
    arguments = Arguments()
    expected = generate_clause_space(task, arguments)
    baseline = materialize(task, arguments, "truth_probes")
    candidate = materialize(task, arguments, "shown_single_scan")
    assert baseline["exhausted"] and candidate["exhausted"]
    assert baseline["models"] == candidate["models"]
    assert baseline["clauses"] == candidate["clauses"] == len(expected) > 0
    assert baseline["spaceSha256"] == candidate["spaceSha256"] == space_fingerprint(expected)
    for row in (baseline, candidate):
        assert row["statistics"]["models"] == row["models"]
        assert row["totalSeconds"] >= row["preparationSeconds"] + row["solveWallSeconds"]
    assert not timing.is_enabled()


def test_reused_single_scan_buffer_clears_previous_longer_model(monkeypatch):
    from benchmarks import profile_clause_decoder
    from clingo._internal import _ffi

    original = profile_clause_decoder._clause_from_model
    lengths = set()

    def poisoned(model, decoder):
        # Simulate a previous larger output in every unused buffer position.
        value = next(iter(decoder.lookup))
        for index in range(decoder.capacity):
            decoder.buffer[index] = value
        result = original(model, decoder)
        lengths.add(len(result.head) + len(result.body))
        assert _ffi.sizeof(decoder.buffer) == decoder.capacity * _ffi.sizeof("clingo_symbol_t")
        return result

    monkeypatch.setattr(profile_clause_decoder, "_clause_from_model", poisoned)
    task = parse_text("#maxv(0). #maxbl(2). #modeh(1,p). #modeb(1,q). #modeb(1,r). "
                      "#pos({p},{},{q.}). #neg({p},{},{r.}).")
    result = compare_decoders(task, Arguments(), limit=0)
    assert result["exhausted"] and len(lengths) > 1


def test_bounded_comparison_marks_unexhausted_enumeration():
    task = parse_text("#maxv(0). #maxbl(2). #modeh(1,p). #modeb(1,q). #modeb(1,r). "
                      "#pos({p},{},{q.}). #neg({p},{},{r.}).")
    result = compare_decoders(task, Arguments(), limit=2)
    assert result["models"] == 2 and not result["exhausted"]


def test_prepared_decoder_survives_incremental_size_solves():
    from benchmarks.clause_decoder_reference import _clause_from_model as truth_from_model, _model_literal_index
    from gentians.clauses import generator as generation
    from gentians.clauses.decoder import _clause_from_model

    task = parse_text("#maxv(0). #maxbl(2). #modeh(1,p). #modeb(1,q). #modeb(1,r). "
                      "#pos({p},{},{q.}). #neg({p},{},{r.}).")
    generator = generation._ClauseGenerator(task, Arguments())
    ctl, decoder, *_ = generator._prepare(19, by_size=True)
    index = _model_literal_index(ctl.symbolic_atoms, generator.modes_by_id)
    sizes = sorted(ctl.symbolic_atoms.by_signature("clause_body_size", 1),
                   key=lambda atom: atom.symbol.arguments[0].number)
    seen = []
    for size in sizes:
        with ctl.solve(yield_=True, assumptions=[size.literal]) as handle:
            for model in handle:
                candidate = _clause_from_model(model, decoder)
                assert candidate == truth_from_model(model, index)
                seen.append(len(candidate.body))
            assert handle.get().exhausted
    assert seen and seen == sorted(seen) and len(set(seen)) > 1


def test_literal_reuse_preserves_slots_bindings_and_decoder_lifetimes():
    import clingo

    from gentians.clauses.decoder import _ModelDecoder, _clause_from_model
    from gentians.clauses.mode_compiler import _clause_modes

    modes = _clause_modes(parse_text("#modeh(1,p(var(t,input))). #modeb(1,q(var(t,any)))."))
    head, body = modes
    control = clingo.Control(["0"])
    control.add("base", [], f"""
        selected(head,0,{head.id}). selected(body,0,{body.id}). selected(body,1,{body.id}).
        var_at(head,0,0,0). var_at(body,1,0,1).
        1 {{ var_at(body,0,0,0); var_at(body,0,0,1) }} 1.
        #show selected/3. #show var_at/4.
    """)
    control.ground([("base", [])])
    lookup = {mode.id: mode for mode in modes}
    decoder = _ModelDecoder(control.symbolic_atoms, lookup)
    other = _ModelDecoder(control.symbolic_atoms, lookup)
    retained = []

    def collect(model):
        first = _clause_from_model(model, decoder)
        again = _clause_from_model(model, decoder)
        independent = _clause_from_model(model, other)
        assert first == again == independent
        for left, right, separate in zip((*first.head, *first.body),
                                          (*again.head, *again.body),
                                          (*independent.head, *independent.body), strict=True):
            assert left is right and left is not separate
        retained.append(first)

    assert control.solve(on_model=collect).exhausted
    assert len(retained) == 2
    assert retained[0].head[0] is retained[1].head[0]
    assert retained[0].body[1] is retained[1].body[1]
    assert retained[0].body[0].variables != retained[1].body[0].variables
    assert {(literal.section, literal.slot, literal.mode_id, literal.variables)
            for clause in retained for literal in (*clause.head, *clause.body)} == {
        ("head", 0, head.id, (0,)), ("body", 0, body.id, (0,)),
        ("body", 0, body.id, (1,)), ("body", 1, body.id, (1,)),
    }


def test_production_decoder_uses_exactly_one_native_copy_per_model(monkeypatch):
    from types import SimpleNamespace

    from gentians.clauses import decoder

    native = decoder._lib
    copies = []

    def copy(*args):
        copies.append(1)
        return native.clingo_model_symbols(*args)

    def forbidden(*args):
        pytest.fail("production decode must not query a size or individual literals")

    monkeypatch.setattr(decoder, "_lib", SimpleNamespace(
        clingo_model_symbols=copy, clingo_show_type_shown=native.clingo_show_type_shown,
        clingo_model_symbols_size=forbidden, clingo_model_is_true=forbidden,
    ))
    task = parse_text("#maxv(0). #maxbl(2). #modeh(1,p). #modeb(1,q). #modeb(1,r). "
                      "#pos({p},{},{q.}). #neg({p},{},{r.}).")
    result = compare_decoders(task, Arguments(), limit=0)
    assert result["exhausted"] and result["models"] == len(copies) > 0


@pytest.mark.parametrize("projection", ["--project=show", "--project=auto", "--project=project"])
@pytest.mark.parametrize("case", ["heads/empty_choice.lp", "heads/aggregate_count.lp",
                                   "heads/cardinality_variable_bounds.lp", "bodies/conditional_literal.lp"])
def test_projection_preserves_reference_space_and_metadata(projection, case):
    task = parse_file(Path(__file__).parent / "syntax_matrix" / "cases" / case)
    arguments = Arguments(clause_generation={"clingo_arguments": [projection]})
    baseline = materialize(task, arguments, "truth_probes")
    candidate = materialize(task, arguments, "shown_single_scan")
    assert baseline["exhausted"] and candidate["exhausted"]
    assert candidate["spaceSha256"] == baseline["spaceSha256"]
    assert candidate["clauses"] == baseline["clauses"] > 0
