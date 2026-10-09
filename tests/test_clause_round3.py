"""Differential checks for native callbacks, owned compact recipes and domains."""

import gc
import subprocess
import sys

import pytest

from gentians import Arguments
from gentians.clauses import generate_clause_space
from gentians.clauses.generator import _ClauseGenerator
from gentians.clauses.mode_compiler import _clause_modes
from gentians.clauses.packed_recipe import PackedRecipe
from gentians.clauses.records import ModelRecords, _records
from gentians.language import parse_text
from benchmarks.synthetic_million import task_text


def options(**settings):
    args = Arguments()
    args.clause_generation.update(settings)
    return args


SOURCES = [
    "#modeh(1,h(var(a,input))). #modeb(2,p(var(a,output))).",
    "#modeh(1,h(var(a,input),var(b,input))). #modeb(2,p(var(a,input),var(b,output))). #modeb(2,q(var(b,input),var(a,output))).",
    "#modeh(1,h(var(a,any))). #modeb(2,p(var(a,any),var(b,any))). #modeb(1,q(var(b,output))).",
    "#modeh(1,-h(var(a,input))). #modeb(2,-p(var(a,output))).",
    "#modeh(1,h(var(a,input))). #modeb(2,p(var(a,output))). #modeb(1,not q(var(a,input))).",
    "#modeh(1,h(var(a,input,x),var(a,input,y))). #modeb(2,p(var(a,output,x),var(a,output,y))).",
    "#modeh(1,h(var(a,input))). #modeb(1,p(var(a,output),const(colour))). #constant(colour,red).",
    "#modeh(1,{h(var(a,input)): q(var(b,any))}). #modeb(2,p(var(a,output))).",
    "#modeb(1,p(box(var(a,output)))).",
    "#modeb(1,p(var(a,output);var(a,output))).",
    "#modeb(1,#count{var(a,any):p(var(a,any))}=var(numeric,output)). #modeb(1,n(var(numeric,output))).",
    "#modeb(1,p(var(a,any)):q(var(b,any))). #modeb(1,r(var(a,output))).",
    "#maxv(0). #modeh(1,p).",
    "#modeh(1,h(var(numeric,input))). #modeb(2,n(var(numeric,output))). #modeb(1,var(numeric)+var(numeric)=var(numeric)).",
]


def make_task(source):
    parsed = parse_text(source)
    modes = _clause_modes(parsed)
    predicates = {predicate for mode in modes for predicate in (*mode.head_predicates, *mode.dependencies)}
    background = " ".join("{" + predicate + ("(" + ",".join(["1..3"] * arity) + ")" if arity else "")
                          + "}." for predicate, arity in sorted(predicates))
    return parse_text(background + source)


@pytest.mark.parametrize("source", SOURCES)
@pytest.mark.parametrize("bindings", ["standard", "connected"])
def test_owned_routes_match_full_signed_metadata_and_native_statements(source, bindings):
    task = make_task(source + " #maxbl(3).")
    expected = generate_clause_space(task, options(engine="asp", transport="python", storage="recipes"))
    actual = generate_clause_space(task, options(engine="asp", bindings=bindings, storage="packed"))
    assert actual.entries == expected.entries
    assert all(str(entry.statement) == entry.text for entry in actual.entries)
    gc.collect()
    assert all(str(entry.statement) == entry.text for entry in actual.entries)


@pytest.mark.parametrize("body_limit", [2, 3, 4])
@pytest.mark.parametrize("extra", ["", "#modeb(1,var(numeric)\\var(numeric)=var(numeric)).",
                                     "#modeb(1,var(numeric)<=var(numeric))."])
def test_projected_strict_components_preserve_source_cost_and_exact_syntax(body_limit, extra):
    task = make_task(f"#maxv(3). #maxbl({body_limit}). #modeh(1,h(var(numeric,input))). "
                      "#modeb(3,n(var(numeric,output))). #modeb(1,var(numeric)<var(numeric)). "
                      "#modeb(2,var(numeric)>var(numeric)). " + extra)
    expected = generate_clause_space(task, options(engine="asp", arithmetic="standard"))
    actual = generate_clause_space(task, options(engine="asp", arithmetic="projected"))
    assert actual.entries == expected.entries
    assert all(str(entry.statement) == entry.text for entry in actual.entries)


@pytest.mark.skipif(_records is None, reason="optional native extension")
@pytest.mark.parametrize("parallel", ["1", "4,split"])
def test_native_delivery_propagates_exception_closes_handle_and_resets_rows(parallel):
    task = parse_text(task_text(8))
    generator = _ClauseGenerator(task, options(clingo_arguments=[f"--parallel-mode={parallel}"]))
    ctl, decoder, *_ = generator._prepare(None)
    records = ModelRecords(decoder)
    blocks = []

    def fail(block):
        blocks.append(block)
        raise LookupError("delivery failed")

    with pytest.raises(LookupError, match="delivery failed"):
        records.solve(ctl, fail)
    assert blocks and records.flush() is None
    # The failed handle must be closed: the same grounded Control can solve again.
    rows = []
    models, _ = records.solve(ctl, lambda block: rows.extend(records.clauses(block)))
    tail = records.flush()
    if tail is not None:
        rows.extend(records.clauses(tail))
    assert len(rows) == models
    assert models > 128


def test_pool_owners_survive_original_space_and_interleaved_materialization():
    first = generate_clause_space(make_task(SOURCES[1] + "#maxbl(3)."), options(storage="packed"))
    second = generate_clause_space(make_task(SOURCES[0] + "#maxbl(3)."), options(storage="packed"))
    entries = tuple(first.entries) + tuple(second.entries)
    del first, second
    gc.collect()
    assert entries and all(isinstance(entry.syntax, PackedRecipe) for entry in entries)
    assert all(str(entry.statement) == entry.text for entry in reversed(entries))


def test_projection_reduces_witness_models_before_python_delivery():
    task = make_task("#maxv(3). #maxbl(4). #modeb(3,n(var(numeric,output))). "
                      "#modeb(2,var(numeric)<var(numeric)). #modeb(2,var(numeric)>var(numeric)).")
    counts = []
    for arithmetic in ("standard", "projected"):
        ctl, *_ = _ClauseGenerator(task, options(arithmetic=arithmetic))._prepare(None)
        count = 0
        with ctl.solve(yield_=True) as models:
            for _ in models:
                count += 1
        counts.append(count)
    assert counts[1] < counts[0]


def test_projection_activation_uses_the_encoding_and_guard_not_user_text():
    task = parse_text('{p("projected_components.",1..3)}. #maxbl(1). '
                      '#modeh(1,h(var(a,input))). '
                      '#modeb(1,p("projected_components.",var(a,output))).')
    for arithmetic in ("standard", "projected"):
        generator = _ClauseGenerator(task, options(engine="asp", arithmetic=arithmetic))
        ctl, *_ = generator._prepare(None)
        assert ctl.configuration.solve.project == "no"
        assert generate_clause_space(task, options(engine="asp", arithmetic=arithmetic)).clauses == (
            '#false :- p("projected_components.",V0).',
            'h(V0) :- p("projected_components.",V0).',
        )


@pytest.mark.skipif(_records is None, reason="optional native extension")
@pytest.mark.parametrize("parallel", ["1", "4,split"])
def test_native_signal_cancellation_closes_handle_and_allows_reuse(parallel):
    # Deliver SIGINT in an isolated process so a broken cancellation path cannot
    # interrupt pytest itself. The timeout checks termination, not throughput.
    script = '''
import signal
import threading
from benchmarks.synthetic_million import task_text
from gentians import Arguments
from gentians.language import parse_text
from gentians.clauses.generator import _ClauseGenerator
from gentians.clauses.records import ModelRecords
args = Arguments()
args.clause_generation["clingo_arguments"] = ["--parallel-mode=@PARALLEL@"]
ctl, decoder, *_ = _ClauseGenerator(parse_text(task_text(32)), args)._prepare(None)
records = ModelRecords(decoder)
timer = threading.Timer(.05, signal.raise_signal, args=(signal.SIGINT,))
timer.start()
try:
    records.solve(ctl, lambda block: None)
except KeyboardInterrupt:
    pass
else:
    raise AssertionError("SIGINT did not interrupt native solving")
finally:
    timer.cancel()
    timer.join()
assert records.flush() is None
ctl.configuration.solve.models = "1"
models, _ = records.solve(ctl, lambda block: None)
assert models == 1
assert records.flush() is not None
print("cancelled and reused")
'''.replace("@PARALLEL@", parallel)
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "cancelled and reused" in result.stdout


@pytest.mark.skipif(_records is None, reason="optional native extension")
def test_native_parallel_profile_captures_every_materialized_model(tmp_path):
    from benchmarks.clause_python_profile import profile_clause_python

    task = parse_text(task_text(8))
    args = options(engine="asp", clingo_arguments=["--parallel-mode=4,split"])
    ctl, *_ = _ClauseGenerator(task, args)._prepare(None)
    ctl.solve()
    model_count = int(ctl.statistics["summary"]["models"]["enumerated"])
    expected = generate_clause_space(task, args)
    summary = profile_clause_python(task, args, expected, model_count, tmp_path / "native-parallel.prof")
    assert summary["decodeCalls"] == model_count


@pytest.mark.parametrize("callback", ["python", "native"])
def test_worker_callback_policies_and_projection_guard_preserve_entries(callback):
    task = parse_text('{p("projected_components.",1..3); q(1..3)}. #maxbl(2). '
                      '#modeh(1,h(var(a,input))). #modeb(1,q(var(a,output))). '
                      '#modeb(1,p("projected_components.",var(a,output))).')
    expected = generate_clause_space(task, options(engine="asp", callback="python", storage="recipes"))
    actual = generate_clause_space(task, options(engine="asp", workers=2, callback=callback,
                                                arithmetic="projected", storage="packed"))
    assert actual.entries == expected.entries
    assert all(str(entry.statement) == entry.text for entry in actual.entries)


def test_pool_shares_syntax_across_source_slots_without_changing_tuple_order():
    from gentians.clauses.canonicalization.canonical_clause import CanonicalArithmeticClause
    from gentians.clauses.reified_literal import ReifiedLiteral
    from gentians.clauses.recipes import RuleRecipes

    modes = {mode.id: mode for mode in _clause_modes(make_task(SOURCES[0]))}
    mode_id = next(mode.id for mode in modes.values() if mode.section == "body")
    recipes = RuleRecipes(modes)
    first = recipes.pack(CanonicalArithmeticClause((), (ReifiedLiteral("body", 0, mode_id, (0,)),), ()))
    second = recipes.pack(CanonicalArithmeticClause((), (ReifiedLiteral("body", 7, mode_id, (0,)),), ()))
    assert first.codes == second.codes
    assert len(recipes.pool) == 1
    assert str(recipes.statement(first)) == str(recipes.statement(second)) == "#false :- p(V0)."


def test_compact_direct_fallback_preserves_native_syntax_without_renderer(monkeypatch):
    from gentians.clauses import native_syntax

    task = parse_text(task_text(4))
    expected = generate_clause_space(task, options(engine="direct", storage="recipes"))
    monkeypatch.setattr(native_syntax, "_records", None)
    actual = generate_clause_space(task, options(engine="direct", storage="packed"))
    assert actual.entries == expected.entries
    assert all(isinstance(entry.syntax, PackedRecipe) for entry in actual.entries)
    assert all(str(entry.statement) == entry.text for entry in actual.entries)


def test_auto_storage_tracks_the_proved_engine_and_preserves_incremental_recipes():
    import random
    from gentians.clauses import incremental_clause_batches
    from gentians.clauses.clause_space import ClauseSpace

    task = parse_text(task_text(4))
    expected = generate_clause_space(task, options(storage="recipes"))
    for engine in ("direct", "asp", "subsets"):
        actual = generate_clause_space(task, options(engine=engine))
        assert actual.entries == expected.entries
        assert all(isinstance(entry.syntax, PackedRecipe) == (engine == "direct" and _records is not None)
                   for entry in actual.entries)
        rebuilt = ClauseSpace(actual.entries)
        assert all(left is right for left, right in zip(actual.entries, rebuilt.entries, strict=True))
    entries = []
    with incremental_clause_batches(task, options(), 2, random.Random(7)) as batches:
        for batch in batches:
            assert all(not isinstance(entry.syntax, PackedRecipe) for entry in batch.entries)
            entries.extend(batch.entries)
    assert ClauseSpace(entries).entries == expected.entries
