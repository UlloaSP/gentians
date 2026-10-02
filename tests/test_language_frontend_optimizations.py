"""Regressions for metadata lifetime, example sets and source diagnostics."""

import gc
import weakref
from itertools import product

import clingo
import pytest
from clingo import ast

from gentians.language import asp, parse_file, parse_text, terms
from gentians.language.ast_nodes import LOCATION
from gentians.evaluation import create_evaluator
from gentians.language.grammar import SourceError, source_position


def nested(leaf, depth):
    for _ in range(depth):
        leaf = ast.Function(LOCATION, "f", [leaf], False)
    return leaf


def test_metadata_queries_do_not_hash_native_subtrees(monkeypatch):
    node = nested(terms.variable("t", "input", "x"), 1200)

    def forbidden_hash(_node):
        pytest.fail("metadata lookup must not hash a native AST")

    monkeypatch.setattr(ast.AST, "__hash__", forbidden_hash)
    for _ in range(2):
        assert terms.kind(node) == "function"
        assert len(terms.arguments(node)) == 1
        assert terms.bindings(node)[0].label == "x"
        assert terms.bindings(node, (3,))[0].path == (3,) + (0,) * 1200
        assert terms.constant_types(node) == frozenset()


@pytest.mark.parametrize("fail", [False, True])
def test_metadata_scope_releases_native_nodes(fail):
    node = nested(terms.constant("t"), 20)
    try:
        with terms.metadata_scope():
            cache = weakref.ref(terms._active.get())
            assert terms.constant_types(node) == {"t"}
            if fail:
                raise ValueError("abort parsing")
    except ValueError:
        if not fail:
            raise
    gc.collect()
    assert cache() is None


def test_deep_binding_result_survives_descendant_cache_eviction(monkeypatch):
    node = nested(terms.variable("t", "input"), 1200)
    expected = terms.bindings(node)

    def unexpected_walk(_node):
        pytest.fail("the computed root result must survive descendant eviction")

    monkeypatch.setattr(terms, "_bindings", unexpected_walk)
    assert terms.bindings(node) == expected


@pytest.mark.parametrize("directive", ["#pos", "#neg"])
def test_example_set_deduplication_preserves_first_order_locations_and_context(directive):
    source = f"{directive}({{p,\n-q,p}},{{r,s,r}},{{context.}}).\n"
    source += f"{directive}({{-q,p}},{{s,r}},{{context.}})."
    task = parse_text(source)
    examples = task.positive_examples if directive == "#pos" else task.negative_examples
    assert len(examples) == 1
    assert tuple(map(str, examples[0].included)) == ("p", "-q", "p")
    assert examples[0].included[1].location.begin.line == 2
    assert examples[0].context_text == "context."


def test_example_keys_keep_fields_signs_contexts_and_polarities_distinct():
    task = parse_text(" ".join([
        "#pos({p},{q},{a.}).", "#pos({q},{p},{a.}).",
        "#pos({-p},{q},{a.}).", "#pos({p},{q},{b.}).",
        "#neg({p},{q},{a.}).", "#pos({p},{q,q},{a.}).",
    ]))
    assert len(task.positive_examples) == 4
    assert len(task.negative_examples) == 1


def test_shared_fields_are_parsed_once_without_sharing_context_semantics(monkeypatch):
    original = clingo.ast.parse_string
    calls = []

    def record(source, *args, **kwargs):
        calls.append(source)
        return original(source, *args, **kwargs)

    monkeypatch.setattr(clingo.ast, "parse_string", record)
    task = parse_text("\n".join(f"#pos({{p}},{{q}},{{r({i}).}})." for i in range(5)))
    assert len(task.positive_examples) == 5
    assert len(calls) == 8  # Two shared fields, five contexts, one background.
    assert len({example.context_text for example in task.positive_examples}) == 5
    assert all(example.included[0] is task.positive_examples[0].included[0] for example in task.positive_examples)


def test_shared_fields_and_set_deduplication_preserve_whole_program_coverage():
    task = parse_text(" ".join([
        "#pos({target,ok},{blocked},{ok.}).",
        "#pos({ok,target,ok},{blocked,blocked},{ok.}).",
        "#pos({target},{blocked},{blocked.}).",
        "#pos({},{blocked},{ok.}).",
        "#neg({target},{},{blocked.}).",
        "#neg({target},{blocked},{ok.}).",
    ]))
    evaluate = create_evaluator(task, {"scoring": "cov_program", "clingo_arguments": []})
    result = evaluate(asp.parse_program("target :- not blocked."))
    assert len(task.positive_examples) == 3
    assert result.behavior == (0b101, 0b10)
    assert task.positive_examples[0].context_text == "ok."


def test_invalid_repeated_field_uses_its_current_source_position():
    source = '#pos({p("a")},{},{ok.}).\n#pos({p("a")},{},\n {q(X). #show q/1.}).'
    with pytest.raises(SourceError) as caught:
        parse_text(source)
    assert (caught.value.line, caught.value.column) == source_position(source, source.index("#show"))


def test_fixed_subtrees_are_reused_without_recipe_descent(monkeypatch):
    fixed = nested(terms.fixed("a"), 200)
    changing = nested(terms.constant("t"), 3)
    with terms.metadata_scope():
        assert terms.constant_types(fixed) == frozenset()
        assert terms.constant_types(changing) == {"t"}
        original = terms.arguments

        def arguments(node):
            assert node is not fixed, "the recipe must treat a fixed subtree as one node"
            return original(node)

        monkeypatch.setattr(terms, "arguments", arguments)
        result = tuple(terms.concretize_terms((fixed, changing), {"t": (terms.fixed("b"), terms.fixed("c"))}))
    assert all(variant[0] is fixed for variant in result)
    assert [str(variant[1]) for variant in result] == ["f(f(f(b)))", "f(f(f(c)))"]


def test_sparse_expansion_keeps_cartesian_order_and_previous_variants():
    roots = (nested(terms.constant("t"), 2), nested(terms.constant("t"), 3))
    domain = tuple(terms.fixed(value) for value in ("a", "b", "c"))
    variants = tuple(terms.concretize_terms(roots, {"t": domain}))
    assert [(str(left), str(right)) for left, right in variants] == [
        (f"f(f({left}))", f"f(f(f({right})))")
        for left, right in product(("a", "b", "c"), repeat=2)
    ]
    assert variants[0][0] is variants[1][0] is variants[2][0]
    assert variants[0][0] is not variants[3][0]
    assert tuple(map(str, roots)) == ("f(f(const(t)))", "f(f(f(const(t))))")


@pytest.mark.parametrize("source", [
    'p("@ & #theory").', 'p. % @ & #theory\nq.',
    'p. %* @ %* & *% #theory *% q.',
    r'p("escaped\" @ & #theory").',
])
def test_quoted_or_commented_markers_do_not_trigger_an_ast_walk(monkeypatch, source):
    def forbidden_walk(_node):
        pytest.fail("quoted and commented markers do not require AST inspection")

    monkeypatch.setattr(asp, "_ast_children", forbidden_walk)
    assert parse_text(source).background


@pytest.mark.parametrize("source, marker", [
    ('#pos({\n p,\n q(X)\n},{}).', 'X'),
    ('#neg({},{\n p,\n q(1..2)\n}).', '1..2'),
    ('#modeb(1,\n p(var(t,input,"bad"))).', '"bad"'),
    ('#modeh(1,\n p(var(t,wrong))).', 'wrong'),
    ('#modeb(1,\n p(var("bad",input))).', '"bad"'),
])
def test_semantic_errors_point_to_the_invalid_native_node(source, marker):
    source = 'p("ñ"). %* prefix *%\n' + source
    with pytest.raises(SourceError) as caught:
        parse_text(source)
    assert (caught.value.line, caught.value.column) == source_position(source, source.index(marker))


@pytest.mark.parametrize("directive", ["#modeh", "#modeb", "#modeha", "#modehd", "#modec", "#invent"])
def test_incompatible_labels_keep_the_declaration_origin(directive):
    source = f'q("ñ").\n{directive}(1,\n p(var(t,input,x),var(u,input,x))).'
    with pytest.raises(SourceError, match="incompatible types") as caught:
        parse_text(source)
    assert (caught.value.line, caught.value.column) == source_position(source, source.rindex("x"))


@pytest.mark.parametrize("declaration", [
    "#modeh(1,p(const(missing))).", "#modeb(1,p(const(missing))).",
    "#modec(1,p(const(missing))).", "#modeha(p(const(missing))).",
    "#modehd(2,p(const(missing))).", "#invent(1,p(const(missing))).",
    "#modeh(1,const(missing){p}).",
])
def test_missing_constant_errors_point_to_the_type(declaration):
    source = 'p("ñ"). #modeh(1,ok).\n %* prefix *% ' + declaration
    with pytest.raises(SourceError, match="require #constant") as caught:
        parse_text(source)
    assert (caught.value.line, caught.value.column) == source_position(source, source.index("missing"))


def test_missing_constant_error_uses_the_first_textual_reference():
    source = "#modeb(1,p(const(missing))). #modeh(1,q(const(missing)))."
    with pytest.raises(SourceError) as caught:
        parse_text(source)
    assert (caught.value.line, caught.value.column) == source_position(source, source.index("missing"))


@pytest.mark.parametrize("directive", ["#modeh", "#modeb", "#invent"])
def test_missing_constant_reference_order_ignores_factored_pool_locations(directive):
    source = f'{directive}(1,p(const(x),f(const(a));const(x),f(const(b)))).'
    with pytest.raises(SourceError) as caught:
        parse_text(source)
    assert (caught.value.line, caught.value.column) == source_position(source, source.index("x"))


def test_directory_semantic_error_reports_the_field_file_and_local_column(tmp_path):
    (tmp_path / "bk.lp").write_text("p.", encoding="utf-8")
    (tmp_path / "bias.lp").write_text("", encoding="utf-8")
    examples = tmp_path / "exs.lp"
    examples.write_text("#pos({\n q(X)\n},{}).", encoding="utf-8")
    with pytest.raises(ValueError) as caught:
        parse_file(str(tmp_path))
    assert f"{examples}:line 2:" in str(caught.value)
    assert "column 4" in str(caught.value)


def test_argument_spans_preserve_trimmed_offsets_and_quoted_commas():
    source = ' \n {p("a,b"),q},  {p("a,b"),q}, (a,), '
    with pytest.raises(ValueError, match="empty top-level argument"):
        asp.split_top_level_args(source)
    source = source.rstrip(' ,')
    spans = asp.split_top_level_args(source)
    assert [source[start:end] for start, end in spans] == ['{p("a,b"),q}', '{p("a,b"),q}', '(a,)']
    assert spans[0][0] == 3
    assert spans[1][0] > spans[0][1]
