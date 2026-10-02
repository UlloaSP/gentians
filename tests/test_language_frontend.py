"""Task-front-end regressions, independent of benchmark task files."""

from itertools import product

import clingo
import pytest
from clingo import ast

from gentians.arguments import Arguments
from gentians.clauses import generate_clause_space
from gentians.language import parse_file, parse_text, terms
from gentians.language import lexer
from gentians.language.asp import symbolic_literal_predicate
from gentians.language.grammar import SourceError, source_position


@pytest.mark.parametrize("source", [
    "#theory t { term {}; &a/0 : term, head }.",
    "&a{1:p}.", "q :- &a{1:p}.",
    "#pos({},{},{&a{1:p}.}).", "#neg({},{},{q :- &a{1:p}.}).",
    "#modeh(1,&a{1:p}).", "#modeb(1,&a{1:p}).",
])
def test_task_rejects_theory_syntax(source):
    with pytest.raises(SourceError, match="theory .*unsupported"):
        parse_text(source)


@pytest.mark.parametrize("source", [
    "p(@f()).", "q :- p(@f()).",
    "#pos({p(@f())},{}).", "#neg({},{p(@f())}).",
    "#pos({},{},{p(@f()).}).", "#neg({},{},{q :- p(@f()).}).",
    "#modeh(1,p(@f())).", "#modeb(1,p(@f())).",
])
def test_task_rejects_external_calls_at_their_original_position(source):
    source = 'p("@f() is text").\n  ' + source
    with pytest.raises(SourceError, match="external function terms are unsupported") as caught:
        parse_text(source)
    assert (caught.value.line, caught.value.column) == source_position(source, source.rindex("@f()"))


def test_unsupported_syntax_in_strings_remains_data():
    task = parse_text('p("@f() &a{1:p} #theory"). #pos({p("@f() &a{1:p} #theory")},{}).')
    assert len(task.background) == len(task.positive_examples) == 1


@pytest.mark.parametrize("atom", ["p(1;2)", "p(f(1;2))", "p(1..2)", "p(f(1..2))"])
@pytest.mark.parametrize("example", ["#pos({ATOM},{}).", "#neg({},{ATOM})."])
def test_examples_require_single_ground_atoms(atom, example):
    with pytest.raises(SourceError, match="examples require ground symbolic atoms"):
        parse_text(example.replace("ATOM", atom))


def test_single_ground_example_terms_keep_native_asp_meaning():
    task = parse_text('#pos({p(1+1),-p(f((a,),"1;2 @f()")),var(const(a))},{}).')
    assert [symbolic_literal_predicate(node) for node in task.positive_examples[0].included] == [
        ("p", 1), ("-p", 1), ("var", 1),
    ]


@pytest.mark.parametrize("directive", ["#maxv", "#maxbl", "#minhl", "#maxhl", "#maxpl"])
@pytest.mark.parametrize("number", ["1_0", "+1", "\u0663", "-0"])
def test_limits_require_ascii_decimal_integers(directive, number):
    with pytest.raises(SourceError):
        parse_text(f"{directive}({number}).")


@pytest.mark.parametrize("directive", ["#modeh", "#modeb", "#modec", "#modeha", "#modehd", "#invent"])
@pytest.mark.parametrize("number", ["1_0", "+1", "\u0663"])
def test_recalls_require_ascii_decimal_integers(directive, number):
    with pytest.raises(SourceError):
        parse_text(f"{directive}({number},p).")


def test_unbounded_invention_matches_finite_recall_under_body_budget():
    source = (
        "d(a). #maxv(1). #maxbl(2). #maxhl(1). "
        "#modeh(1,p(var(t,input))). #modeb(2,d(var(t,output))). "
        "#invent(RECALL,helper(var(t,input)))."
    )
    unbounded = parse_text(source.replace("RECALL", "*"))
    finite = parse_text(source.replace("RECALL", "2"))
    assert unbounded.language_bias_body[-1].recall == -1
    clauses = generate_clause_space(unbounded, Arguments()).clauses
    assert clauses == generate_clause_space(finite, Arguments()).clauses
    assert any("helper(" in clause for clause in clauses)


def test_unbounded_invention_still_requires_a_finite_body_space():
    task = parse_text("#maxbl(*). #invent(*,helper(var(t,input))).")
    with pytest.raises(ValueError, match="finite"):
        generate_clause_space(task, Arguments())


def test_example_shortcuts_keep_polarity_fields_and_contexts_distinct():
    task = parse_text(
        "#pos({p},{q},{r.}). #pos({p},{q},{r.}). "
        "#pos({p},{q},{}). #pos({p},{s},{r.}). "
        "#neg({p},{q},{r.}). #neg({p},{q},{r.})."
    )
    assert len(task.positive_examples) == 3
    assert len(task.negative_examples) == 1
    assert [(item.excluded_text, item.context_text) for item in task.positive_examples] == [
        ("q", "r."), ("q", ""), ("s", "r."),
    ]
    assert task.negative_examples[0].positive is False


@pytest.mark.parametrize("example", ["#pos", "#neg"])
def test_identical_examples_skip_repeated_native_parsing(monkeypatch, example):
    original = ast.parse_string
    calls = []

    def record(source, *args, **kwargs):
        calls.append(source)
        return original(source, *args, **kwargs)

    monkeypatch.setattr(ast, "parse_string", record)
    task = parse_text((example + "({p},{q},{r.}).\n") * 5)
    examples = task.positive_examples if example == "#pos" else task.negative_examples
    assert len(examples) == 1
    assert len(calls) == 4  # Three fields and the one background parse.


@pytest.mark.parametrize("directive", ["#maxbl(1).", "#invent(1,p)."])
def test_duplicate_errors_are_not_suppressed_by_declaration_shortcuts(directive):
    with pytest.raises(SourceError, match="duplicate"):
        parse_text(directive + "\n" + directive)


def test_identical_constants_skip_repeated_term_parsing(monkeypatch):
    original = clingo.parse_term
    calls = []

    def record(source, *args, **kwargs):
        calls.append(source)
        return original(source, *args, **kwargs)

    monkeypatch.setattr(clingo, "parse_term", record)
    task = parse_text('#constant(t,f("a,b")).\n' * 5)
    assert tuple(map(str, task.constants["t"])) == ('f("a,b")',)
    assert calls == ['f("a,b")']


def test_kind_inspection_does_not_hash_native_subtrees(monkeypatch):
    term = parse_text("#modeb(1,p(" + "f(" * 1200 + "var(t,input)" + ")" * 1200 + ")).").language_bias_body[0].literal.arguments[0]

    def forbidden_hash(node):
        pytest.fail("kind inspection must not hash a native subtree")

    monkeypatch.setattr(ast.AST, "__hash__", forbidden_hash)
    assert terms.kind(term) == terms.kind(term) == "function"
    assert terms.kind(terms.variable("t", "input")) == "variable"
    assert terms.kind(term.update(name="")) == "tuple"


@pytest.mark.parametrize("declaration", [
    "#modeb(1,p(f(const(t),const(t),const(t)))).",
    "#modeb(1,f(const(t),const(t),const(t))=1).",
    "#modeb(1,p:f(const(t),const(t),const(t))=1).",
    "#modeb(1,#sum{f(const(t),const(t),const(t)):p}=1).",
    "#modeb(1,1{p:f(const(t),const(t),const(t))=1}1).",
    "#modeh(1,p(f(const(t),const(t),const(t)))).",
    "#modeh(1,{p:f(const(t),const(t),const(t))=1}).",
    "#modeh(1,#sum{f(const(t),const(t),const(t)):p}=1).",
])
def test_nested_template_expansion_does_not_consume_future_variants(monkeypatch, declaration):
    task = parse_text("#constant(t,a). #constant(t,b). #constant(t,c). " + declaration)
    template = task.language_bias_head[0] if task.language_bias_head else task.language_bias_body[0].literal
    original = terms.with_arguments
    expanded = []

    def record(term, children):
        if term.ast_type == ast.ASTType.Function and term.name == "f":
            expanded.append(tuple(map(str, children)))
        return original(term, children)

    monkeypatch.setattr(terms, "with_arguments", record)
    stream = template.concretizations(task.constants)
    assert expanded == []
    first = next(stream)
    assert expanded == [("a", "a", "a")]
    remaining = tuple(stream)
    assert len(remaining) == 26
    assert expanded == list(product(("a", "b", "c"), repeat=3))
    assert len(tuple(template.concretizations(task.constants))) == 27
    assert first != remaining[-1]


def test_background_framing_does_not_normalize_payloads(monkeypatch):
    # Accessing background text during task parsing defeats span-only storage.
    original = lexer.Statement.text

    def text(statement):
        assert statement.directive is not None
        return original.__get__(statement)

    if not isinstance(original, property):
        pytest.fail("background statements must retain source spans, not copied payloads")
    monkeypatch.setattr(lexer.Statement, "text", property(text))
    task = parse_text('p("% quoted"). %* comment *% q. #maxbl(1).')
    assert tuple(map(str, task.background)) == ('p("% quoted").', "q.")


def test_distinct_statement_tokens_do_not_compare_equal():
    first, second = lexer.lex("p. q.")
    assert first != second
    assert len({first, second}) == 2


@pytest.mark.parametrize("source, marker, message", [
    ('q.\np(\n  "unterminated', '"', "unterminated string"),
    ("q.\np(\n  f(a", "(", "unclosed delimiter"),
    ("q.\n  %* comment\nmore", "%*", "unterminated block comment"),
])
def test_lexer_reports_the_opening_location(source, marker, message):
    offset = source.rindex(marker) if marker == "(" else source.index(marker)
    with pytest.raises(SourceError, match=message) as caught:
        tuple(lexer.lex(source))
    assert (caught.value.line, caught.value.column) == source_position(source, offset)


def test_directory_lexer_errors_keep_the_original_file_and_byte_column(tmp_path):
    (tmp_path / "bk.lp").write_text('p("\u00f1").', encoding="utf-8")
    (tmp_path / "exs.lp").write_text("", encoding="utf-8")
    path = tmp_path / "bias.lp"
    path.write_text('#modeb(1,\n  p("unterminated', encoding="utf-8")
    with pytest.raises(ValueError) as caught:
        parse_file(str(tmp_path))
    assert str(caught.value) == f"{path}:line 2: unterminated string (column 5)"
