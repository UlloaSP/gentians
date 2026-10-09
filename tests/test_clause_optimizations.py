import gc

from clingo import ast
import pytest

from gentians.clauses.native_syntax import RuleBuilder
from gentians.clauses.canonicalization import clauses as canonicalization
from gentians.clauses.canonicalization.arithmetic_system import ArithmeticSystem
from gentians.clauses.canonicalization.canonical_clause import CanonicalArithmeticClause
from gentians.clauses.canonicalization.expression import ArithmeticExpression
from gentians.clauses.canonicalization.expression_constraint import ExpressionConstraint
from gentians.clauses.mode_compiler import _clause_modes
from gentians.clauses.reified_clause import ReifiedClause
from gentians.clauses.reified_literal import ReifiedLiteral
from gentians.language import parse_text
from gentians.language.asp import parse_rule
from gentians.language.ast_nodes import LOCATION
from gentians import Arguments
from gentians.clauses import generate_clause_space, incremental_clause_batches
from benchmarks.synthetic_million import task_text
import random
from gentians.clauses.mode_facts import theta_facts
from gentians.clauses.binding_facts import nominal_binding_facts
from gentians.clauses.execution import generation_gc


def configured(**settings):
    args = Arguments()
    args.clause_generation.update(settings)
    return args


def _error_during_partition_write(data, ids, include_empty, path):
    """Keep another worker's output open while one partition fails."""
    from pathlib import Path
    import time
    target = Path(path)
    if include_empty:
        deadline = time.monotonic() + 15
        while not list(target.parent.glob("*.ready")):
            if time.monotonic() >= deadline:
                raise RuntimeError("other worker failed to start")
            time.sleep(0.02)
        raise RuntimeError("partition failed during another output write")
    with target.open("wb") as output:
        output.write(b"incomplete")
        output.flush()
        target.with_suffix(".ready").touch()
        time.sleep(30)


def test_partition_error_reaps_writers_before_removing_temporary_directory(monkeypatch):
    from gentians.clauses import partitions
    monkeypatch.setattr(partitions, "_worker", _error_during_partition_write)
    with pytest.raises(RuntimeError, match="partition failed during another output write"):
        generate_clause_space(parse_text(task_text(3)), configured(workers=2))


def test_native_records_keep_full_block_and_final_tail_in_model_order():
    from gentians.clauses.records import _records, ModelRecords
    from gentians.clauses.generator import _ClauseGenerator
    from gentians.clauses.decoder import _clause_from_model
    if _records is None:
        pytest.skip("optional native extension not built")
    generator = _ClauseGenerator(parse_text(task_text(8)), configured(
        engine="asp", clingo_arguments=["--parallel-mode=1"]))
    ctl, decoder, *_ = generator._prepare(None)
    records = ModelRecords(decoder)
    expected, actual, sizes = [], [], []

    def consume(block):
        clauses = list(records.clauses(block))
        sizes.append(len(clauses))
        actual.extend(clauses)

    def collect(model):
        expected.append(_clause_from_model(model, decoder))
        block = records.push(model)
        if block is not None:
            consume(block)

    ctl.solve(on_model=collect)
    tail = records.flush()
    assert tail is not None
    consume(tail)
    assert sizes == [128, 118]
    assert len(actual) == 246
    assert actual == expected
    assert records.flush() is None


@pytest.mark.parametrize("engine", ["asp", "subsets"])
def test_exhaustive_configuration_preserves_space_and_ignores_finite_model_limit(engine):
    task = parse_text(task_text(4))
    expected = generate_clause_space(task, configured(engine="asp"))
    actual = generate_clause_space(task, configured(engine=engine, configuration="frumpy",
                                                   clingo_arguments=["--models=1", "--parallel-mode=1"]))
    assert actual.entries == expected.entries


@pytest.mark.parametrize("engine", ["auto", "direct", "subsets"])
def test_independent_subset_engine_preserves_every_entry_and_lazy_native_statement(engine):
    task = parse_text(task_text(6))
    expected = generate_clause_space(task, configured(engine="asp", transport="python"))
    actual = generate_clause_space(task, configured(engine=engine))
    assert actual.entries == expected.entries
    assert actual.clauses == expected.clauses
    assert all(str(entry.statement) == entry.text for entry in actual.entries)


@pytest.mark.parametrize("source", [
    "p(a). q(a). #modeb(1,p(var(x,output))). #modeb(1,q(var(x,output))).",
    "#modeb(1,-p(var(x,output))).", "#modeb(1,not p(var(x,input))).",
    "#modeb(2,p(var(x,output))).", "#modeb(1,p(a)).",
    "#modeb(1,p(var(x,input))).", "#modeh(1,p(var(x,input))).",
])
def test_direct_engine_rejects_unproved_families_and_auto_keeps_full_asp(source):
    task = parse_text(source + " #maxv(1). #maxbl(2).")
    with pytest.raises(ValueError, match="independent unary"):
        generate_clause_space(task, configured(engine="direct"))
    assert generate_clause_space(task, configured()).entries == generate_clause_space(task, configured(engine="asp")).entries


@pytest.mark.parametrize("source", [task_text(5),
    "#modeh(1,h(var(x,input))). #modeb(2,p(var(x,output),var(y,output))). #maxv(3). #maxbl(2).",
    "#modeh(1,h(var(numeric,input))). #modeb(1,p(var(numeric,output))). #modeb(1,var(numeric,input)*var(numeric,input)=var(numeric,output)). #maxv(3). #maxbl(2).",
])
def test_native_records_deliver_same_raw_models_and_complete_entries(source):
    from gentians.clauses.records import _records
    if _records is None:
        pytest.skip("optional native extension is not built")
    task = parse_text(source)
    actual = generate_clause_space(task, configured(engine="asp", transport="native"))
    expected = generate_clause_space(task, configured(engine="asp", transport="python"))
    assert actual.entries == expected.entries
    assert all(str(entry.statement) == entry.text for entry in actual.entries)


def test_theta_work_fallback_keeps_small_normal_domain():
    modes = _clause_modes(parse_text(" ".join(f"#modeb(2,p{i}(var(x,output)))." for i in range(40))))
    facts = theta_facts(modes, 1, 3)
    assert "theta_sigma_section(body)." in facts
    assert "theta_saturated_section(body)." not in facts
    assert sum(fact.startswith("theta_sigma(") for fact in facts) <= 8


@pytest.mark.parametrize("source", [
    "#modeh(1,h(var(x,input))). #modeb(2,p(var(x,output),var(y,output))).",
    "#modeh(1,h(var(x,input))). #modeb(2,p(var(x,output))). #modeb(1,q(var(x,input),var(y,output))).",
    "#modeh(1,h(var(numeric,input))). #modeb(1,var(numeric,output) = #count{var(x,any):p(var(x,any))}).",
    "#modeb(2,p(var(x,output))). #modec(1,q(var(x,input))).",
])
def test_counts_and_nominal_bindings_preserve_general_clause_space(source):
    task = parse_text("{p(1,a);p(2,b);p(2,a);p(1);p(2);q(1);q(2)}. " + source + " #maxv(3). #maxbl(2).")
    expected = generate_clause_space(task, configured(engine="asp", transport="python"))
    assert expected
    for body, bindings in (("counts", "standard"), ("slots", "nominal"), ("counts", "nominal")):
        actual = generate_clause_space(task, configured(engine="asp", body=body, bindings=bindings))
        assert actual.entries == expected.entries


def test_nominal_domains_fall_back_for_local_aggregate_names():
    task = parse_text("#modeb(1,var(numeric,output) = #count{var(x,any):p(var(x,any))}). #modeb(1,q(var(y,output))).")
    assert nominal_binding_facts(_clause_modes(task)) == []


def test_grounded_strata_preserve_complete_union_and_attached_condition_cost():
    task = parse_text("{q;r;b;d}. #maxv(0). #maxbl(2). "
                      "#modeh(1,p:q). #modeb(1,b). #modeb(1,r:d).")
    expected = generate_clause_space(task, configured(engine="asp"))
    with incremental_clause_batches(task, configured(strata="ground"), 7, random.Random(4)) as batches:
        entries = [entry for batch in batches for entry in batch.entries]
    from gentians.clauses.clause_space import ClauseSpace
    assert ClauseSpace(entries).entries == expected.entries
    assert len(expected) == 4
    assert {entry.body_literals for entry in expected.entries} == {1, 2}
    assert "p: q :- r: d." not in expected.clauses


def test_gc_policy_restores_disabled_and_enabled_states_after_errors():
    original = gc.isenabled()
    try:
        for enabled in (False, True):
            (gc.enable if enabled else gc.disable)()
            with pytest.raises(RuntimeError):
                with generation_gc("defer"):
                    assert not gc.isenabled()
                    raise RuntimeError("abort")
            assert gc.isenabled() == enabled
    finally:
        (gc.enable if original else gc.disable)()


@pytest.mark.parametrize("reverse", [False, True])
def test_text_collision_between_legal_arithmetic_keys_keeps_cheapest_source(reverse):
    from gentians.clauses.clause_space import ClauseSpace
    from gentians.clauses.generator import _ClauseGenerator
    from gentians.clauses.decoder import _clause_from_model
    from gentians.clauses.canonicalization.arithmetic import canonical_arithmetic_clause
    task = parse_text("{p(1,2);p(2,3)}. #maxv(2). #maxbl(4). "
                      "#modeh(1,h(var(numeric,input))). "
                      "#modeb(1,p(var(numeric,output),var(numeric,output))). "
                      "#modeb(1,var(numeric)<var(numeric)). "
                      "#modeb(1,var(numeric)>var(numeric)). "
                      "#modeb(1,var(numeric)\\var(numeric)=var(numeric)).")
    generator = _ClauseGenerator(task, configured(clingo_arguments=["--parallel-mode=1"]))
    ctl, decoder, *_ = generator._prepare(None)
    target = "#false :- p(V0,V1); ((V1\\V0)-V0) = 0; V0 != 0; (V1-V0) < 0."
    sources = {}

    def collect(model):
        source = _clause_from_model(model, decoder)
        canonical = canonical_arithmetic_clause(source, generator.modes_by_id, 2)
        if canonical is not None and canonical.render(generator.modes_by_id) == target:
            sources[len(source.body)] = source

    ctl.solve(on_model=collect)
    assert sources.keys() == {3, 4}
    canonicalizer = canonicalization.ClauseCanonicalizer(generator.modes_by_id, 2)
    entries = []
    for size in ((4, 3) if reverse else (3, 4)):
        canonicalizer.add(sources[size])
        single = canonicalization.ClauseCanonicalizer(generator.modes_by_id, 2)
        single.add(sources[size])
        entries.extend(single.finish())
    # Exercise final text deduplication separately from component-key folding.
    assert {entry.body_literals for entry in entries} == {3, 4}
    assert ClauseSpace(entries).entries[0].body_literals == 3
    space = ClauseSpace(canonicalizer.finish())
    assert space.clauses == (target,)
    assert space.entries[0].body_literals == 3


@pytest.mark.parametrize("extra", ["", "#modeb(1,var(numeric)<=var(numeric)). #modeb(1,var(numeric)!=var(numeric)).",
    "#modeb(1,var(numeric,input,a)<var(numeric,input,b)).",
    "#modeb(1,not var(numeric)<var(numeric))."])
def test_canonical_comparison_skeletons_preserve_complete_space_and_fallback(extra):
    from gentians.clauses.component_facts import comparison_component_facts
    from gentians.clauses.generator import _ClauseGenerator
    from gentians.clauses.decoder import _clause_from_model
    from gentians.clauses.clause_space import ClauseSpace
    task = parse_text("{p(1,2);p(2,3)}. #maxv(2). #maxbl(4). "
                      "#modeh(1,h(var(numeric,input))). "
                      "#modeb(1,p(var(numeric,output),var(numeric,output))). "
                      "#modeb(1,var(numeric)<var(numeric)). "
                      "#modeb(1,var(numeric)>var(numeric)). "
                      "#modeb(1,var(numeric)\\var(numeric)=var(numeric)). " + extra)
    spaces, counts = [], []
    for policy in ("standard", "components"):
        generator = _ClauseGenerator(task, configured(arithmetic=policy, clingo_arguments=["--parallel-mode=1"]))
        ctl, decoder, *_ = generator._prepare(None)
        canonicalizer = canonicalization.ClauseCanonicalizer(generator.modes_by_id, 2)

        def collect(model):
            canonicalizer.add(_clause_from_model(model, decoder))

        ctl.solve(on_model=collect)
        counts.append(ctl.statistics["summary"]["models"]["enumerated"])
        spaces.append(ClauseSpace(canonicalizer.finish()))
    assert spaces[0].entries == spaces[1].entries
    if extra:
        assert comparison_component_facts(generator.modes) == []
        assert counts[0] == counts[1]
    else:
        assert len(spaces[0]) == 92
        assert counts[1] < counts[0] == 212


@pytest.mark.parametrize("extra,expected_size", [
    ("#modeh(1,var(numeric,input,n){h(var(numeric,input,x))}var(numeric,input,n)).", 91),
    ("#modeh(1,h(var(numeric,input))). #modeb(1,q(var(numeric,input);1)).", 274),
    ("#modeh(1,h(f(var(numeric,input)))).", 92),
])
def test_comparison_components_preserve_full_heads_guards_pools_and_nested_terms(extra, expected_size):
    from gentians.clauses.component_facts import comparison_component_facts
    from gentians.clauses.generator import _ClauseGenerator
    task = parse_text("{p(1,2);p(2,3);q(1);q(2);q(f(1,2));q(f(2,3))}. "
                      "#maxv(2). #maxbl(5). #maxhl(2). "
                      "#modeb(1,p(var(numeric,output),var(numeric,output))). "
                      "#modeb(1,var(numeric)<var(numeric)). "
                      "#modeb(1,var(numeric)>var(numeric)). "
                      "#modeb(1,var(numeric)\\var(numeric)=var(numeric)). " + extra)
    generator = _ClauseGenerator(task, configured(arithmetic="components"))
    assert comparison_component_facts(generator.modes)
    expected = generate_clause_space(task, configured(arithmetic="standard"))
    actual = generate_clause_space(task, configured(arithmetic="components"))
    assert actual.entries == expected.entries
    assert len(actual) == expected_size
    assert all(str(entry.statement) == entry.text for entry in actual.entries)


@pytest.mark.parametrize("source", [task_text(5),
    "{p(1);p(2);q(1);q(2)}. #modeh(1,h(var(x,input))). #modeb(2,p(var(x,output))). #modeb(1,q(var(x,input))). #maxv(2). #maxbl(2).",
    "{p(1);p(2)}. #modeh(1,h(var(numeric,input))). #modeb(1,p(var(numeric,output))). #modeb(1,var(numeric,input)*var(numeric,input)=var(numeric,output)). #maxv(3). #maxbl(2).",
])
def test_process_partitions_preserve_complete_space_and_global_representatives(source):
    task = parse_text(source)
    actual = generate_clause_space(task, configured(engine="asp", workers=2))
    expected = generate_clause_space(task, configured(engine="asp", workers=1))
    assert actual.entries == expected.entries
    assert all(str(entry.statement) == entry.text for entry in actual.entries)


def test_structural_ipc_preserves_native_ast_sign_locations_and_symbol_shapes():
    import clingo
    from gentians.clauses.serialization import recipe_bytes, read_recipe
    value = (parse_rule('-p("á",f(X)) :- q(X), not r(X).'), clingo.Function("f", [clingo.Number(2)], False),
             clingo.Infimum, clingo.Supremum)
    actual = read_recipe(recipe_bytes(value))
    assert actual == value
    assert actual[0].location == value[0].location


def test_flat_ipc_keeps_deep_ast_and_expression_recipes_without_python_recursion():
    from gentians.clauses.serialization import recipe_bytes, read_recipe
    term = ast.Variable(LOCATION, "X")
    expression = ArithmeticExpression.var(0)
    for _ in range(2600):
        term = ast.Function(LOCATION, "f", [term], False)
        expression = ArithmeticExpression("abs", (expression,))
    actual_term, actual_expression = read_recipe(recipe_bytes((term, expression)))
    assert actual_term == term
    assert actual_expression == expression


@pytest.mark.parametrize("key,value", [("engine", "bogus"), ("transport", "bogus"), ("bindings", []),
    ("body", "bogus"), ("arithmetic", "bogus"), ("strata", "bogus"), ("gc", []), ("configuration", []), ("workers", True)])
@pytest.mark.parametrize("workers", [1, 2])
def test_generation_options_are_validated_before_engine_dispatch(key, value, workers):
    args = configured(workers=workers)
    args.clause_generation[key] = value
    with pytest.raises(ValueError):
        generate_clause_space(parse_text(task_text(3)), args)


def test_explicit_native_transport_cannot_silently_fall_back(monkeypatch):
    from gentians.clauses import generator
    monkeypatch.setattr(generator, "_records", None)
    for workers in (1, 2):
        with pytest.raises(RuntimeError, match="unavailable"):
            generate_clause_space(parse_text(task_text(3)), configured(workers=workers, transport="native"))


def test_explicit_solver_arguments_override_the_enumeration_preset():
    from gentians.clauses.generator import _ClauseGenerator
    args = configured(configuration="frumpy", clingo_arguments=["--configuration=jumpy"])
    generator = _ClauseGenerator(parse_text(task_text(3)), args)
    assert generator.solver_arguments() == ["--configuration=jumpy"]
    assert generate_clause_space(generator.task, configured(**{
        **args.clause_generation, "engine": "subsets",
    })).entries == generate_clause_space(generator.task, configured()).entries


@pytest.mark.parametrize("budget", [3, 129])
def test_native_incremental_budget_and_same_seed_prefix_match_python_decoder(budget):
    from gentians.clauses.records import _records
    if _records is None:
        pytest.skip("optional native extension not built")
    task = parse_text(task_text(10))
    results = []
    for transport in ("python", "native"):
        with incremental_clause_batches(task, configured(transport=transport), budget, random.Random(5)) as batches:
            results.append([batch.entries for batch in batches])
    assert results[0] == results[1]


@pytest.mark.parametrize("source", [
    "p(X) :- q(X), not -r(X).",
    "p(X); -q(X) :- r(X).",
    "1 {p(X):q(X); r(X)} 2 :- s(X).",
    ":- q(X), #count{Y:r(X,Y)} > 1.",
    'p("áñ漢🙂") :- q("a,b\\\"c").',
    'p("' + "á🙂" * 3000 + '").',
], ids=["normal", "disjunctive", "choice", "aggregate", "unicode", "large-unicode"])
def test_native_builder_and_growing_formatter_keep_clingo_syntax(source):
    original = parse_rule(source)
    builder = RuleBuilder()
    node = builder.rule(original.head, original.body)
    assert builder.render(node) == str(original)
    assert node == ast.Rule(LOCATION, original.head, original.body)
    # Reusing and growing the buffers must not invalidate previous ASTs.
    other = parse_rule("other :- " + ",".join(f"p({i})" for i in range(50)) + ".")
    second = builder.rule(other.head, other.body)
    assert builder.render(second) == str(other)
    del builder, original, other
    gc.collect()
    assert str(node) == str(parse_rule(source))


def test_repeated_nonlinear_render_reuses_exact_syntax_but_not_output_safety(monkeypatch):
    modes = {m.id: m for m in _clause_modes(parse_text(
        "#modeb(1,var(numeric,input)*var(numeric,input)=var(numeric,output))."
        "#maxv(3). #maxbl(1)."
    ))}
    mode_id = next(iter(modes))
    raw = ReifiedClause((), (ReifiedLiteral("body", 0, mode_id, (0, 1, 2)),))
    expression = ArithmeticExpression("*", (ArithmeticExpression.var(0), ArithmeticExpression.var(1)))
    safe = CanonicalArithmeticClause((), (), (ArithmeticSystem((
        ExpressionConstraint(expression, "eq", 2, True),
    )),))
    unsafe = CanonicalArithmeticClause((), (), (ArithmeticSystem((
        ExpressionConstraint(expression, "eq", 2, False),
    )),))
    assert safe.key == unsafe.key
    assert safe.render(modes) != unsafe.render(modes)
    variants = iter((safe, safe, unsafe))
    monkeypatch.setattr(canonicalization, "canonical_arithmetic_clause", lambda *_args: next(variants))
    calls = []
    from gentians.clauses.recipes import RuleRecipes
    original = RuleRecipes.render

    def tracked(builder, *args):
        calls.append(None)
        return original(builder, *args)

    monkeypatch.setattr(RuleRecipes, "render", tracked)
    canonicalizer = canonicalization.ClauseCanonicalizer(modes, 3)
    canonicalizer.add(raw)
    canonicalizer.add(raw)
    assert len(calls) == 1
    canonicalizer.add(raw)
    assert len(calls) == 2
    assert [c.text for c in canonicalizer.finish()] == [min(safe.render(modes), unsafe.render(modes))]
