import clingo
import pytest
from clingo import ast

from gentians.language import InductiveTask, parse_file, parse_text
from gentians.language import parser as task_parser
from gentians.language import terms as mode_terms
from gentians.language.lexer import lex
from tests.task_helpers import make_clause_space


@pytest.mark.parametrize("declaration", [
    '#bias(":- selected_slot(head,_).").',
    '#bias("\n bias_active.\n").',
    '#metarule(chain,"P(X) :- Q(X).").',
    '#predicate(target,p/1).',
    '#modem(chain(target/1,base/1)).',
])
def test_removed_meta_directives_fail_before_background_parsing(monkeypatch, declaration):
    def unexpected(*args, **kwargs):
        pytest.fail("removed directives must not reach the background parser")

    monkeypatch.setattr(task_parser, "parse_program", unexpected)
    with pytest.raises(ValueError, match="line 2: .* is no longer supported"):
        parse_text("fact.\n" + declaration)


def test_removed_directive_text_in_comments_and_strings_is_ordinary_asp():
    task = parse_text('% #bias("ignored.").\ntext("#metarule").')
    assert tuple(map(str, task.background)) == ('text("#metarule").',)


def test_task_ir_has_no_meta_program_payloads():
    assert "bias" not in InductiveTask.__dataclass_fields__
    assert "metarule_programs" not in InductiveTask.__dataclass_fields__


def test_parser_accepts_multiline_directives_and_preserves_asp_ranges() -> None:
    task = parse_text(
        """
        % The top-level lexer must not confuse a range with two terminators.
        node(1..3).
        #modeh(
            1,
            target(var(node,input))
        ).
        #modeb(1, node(var(node,input))).
        """
    )

    assert tuple(map(str, task.background)) == ("node((1..3)).",)
    assert task.background[0].ast_type == ast.ASTType.Rule
    assert isinstance(task, InductiveTask)
    assert task.language_bias_head[0].conclusions[0].atom.name == "target"


@pytest.mark.parametrize("text", [
    "a,b",
    "unmatched ) ], } and ({[",
    'a quote: ", then a comma',
    "a backslash: \\, then a comma",
    '%* comment *% and a period. inside a string',
])
def test_constant_strings_preserve_delimiters_and_escapes(text):
    value = str(clingo.String(text))
    task = parse_text(f"#constant(word,{value}). #modeh(1,p(const(word))).")

    assert task.constants == {"word": (value,)}
    assert clingo.parse_term(task.constants["word"][0]).string == text


def test_example_fields_preserve_string_delimiters_and_isolated_contexts():
    task = parse_text(
        '#pos({p("a},b")},{q("c],d")},{local("e),f").}). '
        '#neg({q("g{,h")},{p("i[,j")},{}).'
    )

    positive, negative = task.positive_examples[0], task.negative_examples[0]
    assert positive.included_text == 'p("a},b")'
    assert positive.excluded_text == 'q("c],d")'
    assert positive.context_text == 'local("e),f").'
    assert negative.included_text == 'q("g{,h")'
    assert negative.excluded_text == 'p("i[,j")'
    assert negative.context == ()


@pytest.mark.parametrize("source", [
    "#modeh(1,p(_)).",
    "#modeh(1,{p(_)}).",
    "#modeh(1,#count{_:p}=1).",
    "#modeh(1,{p:not q(_)}).",
    "#modeh(1,_ {p}).",
    "#modeb(1,p(_):q(_)).",
    "#modeb(1,#count{_:q}=1).",
    "#modeb(1,not p(_)).",
    "#modeb(1,var(numeric,input)=_).",
])
def test_anonymous_variables_require_a_positive_grounding_atom(source):
    with pytest.raises(ValueError, match="anonymous variables"):
        parse_text(source)


@pytest.mark.parametrize("source", [
    "#modeb(1,p(_)).",
    "#modeh(1,{p:q(_)}).",
    "#modeh(1,#count{1:p:q(_)}=1).",
    "#modeb(1,#count{1:q(_)}=1).",
    "#modeb(1,p:q(_)).",
])
def test_anonymous_variables_remain_valid_in_positive_conditions(source):
    parse_text(source)


@pytest.mark.parametrize("source", [
    "#modeh(1,var(bound,input,x){p(var(node,any,x))}).",
    "#modeh(1,#count{var(tag,any,x):p(var(node,any,x))}=1).",
    "#modeh(1,p(var(node,any,x)):q(var(other,any,x))).",
    "#modeb(1,p(var(node,any,x)):q(var(other,any,x))).",
])
def test_variable_labels_retain_their_type_across_a_declaration(source):
    with pytest.raises(ValueError, match="variable label x has incompatible types"):
        parse_text(source)


def test_variable_labels_are_local_to_each_declaration():
    task = parse_text(
        "#modeh(1,p(var(node,any,x))). #modeh(1,q(var(other,any,x))). "
        "#modeb(1,r(var(node,any,x))). #modeb(1,s(var(other,any,x)))."
    )

    assert len(task.language_bias_head) == len(task.language_bias_body) == 2


def test_body_conditionals_still_require_a_condition():
    with pytest.raises(ValueError, match="conditional literals require at least one condition"):
        parse_text("#modeb(1,p:).")


@pytest.mark.parametrize("recall", ["0", "2", "*"])
def test_complete_heads_require_recall_one(recall):
    with pytest.raises(ValueError, match="complete head modes require recall 1"):
        parse_text(f"#modeh({recall},p).")


@pytest.mark.parametrize("relation, expected", [
    ("var(numeric)+1=var(numeric)", ("input", "output")),
    ("var(numeric)=1..3", ("output",)),
    ("1<var(numeric)<4", ("output",)),
])
def test_comparison_safety_uses_native_ast_without_text_loading(monkeypatch, relation, expected):
    def unexpected_add(*args, **kwargs):
        pytest.fail("the safety probe must load AST, not reparse text")

    monkeypatch.setattr(clingo.Control, "add", unexpected_add)
    task = parse_text(f"#modeb(1,{relation}).")
    literal = task.language_bias_body[0].literal

    assert tuple(binding.direction for term in literal.arguments
                 for binding in mode_terms.bindings(term)) == expected


def test_native_comparison_safety_still_rejects_unsafe_outputs(monkeypatch):
    def unexpected_add(*args, **kwargs):
        pytest.fail("the safety probe must load AST, not reparse text")

    monkeypatch.setattr(clingo.Control, "add", unexpected_add)
    with pytest.raises(ValueError, match="comparison outputs are not safe"):
        parse_text("#modeb(1,var(numeric,output)=var(numeric,output)).")


def test_clause_space_retains_clingo_ast_and_canonical_text() -> None:
    space = make_clause_space([":- p(X), X != 1."])

    assert space.clauses == (":- p(X), X != 1.",)
    assert space.statements[0].ast_type == ast.ASTType.Rule


def test_lexer_separates_multiple_statements_and_weak_constraints() -> None:
    statements = lex("value(1). value(2). :~ value(X). [1@1,X]")

    assert [statement.text for statement in statements] == [
        "value(1).",
        "value(2).",
        ":~ value(X). [1@1,X]",
    ]


def test_lexer_keeps_all_clingo_annotations_with_their_statements() -> None:
    statements = lex(
        "#heuristic p(X): q(X). [1@2,true]\n"
        "#external enabled. % annotation follows a comment\n[false]"
    )

    assert [statement.text for statement in statements] == [
        "#heuristic p(X): q(X). [1@2,true]",
        "#external enabled. [false]",
    ]


def test_lexer_removes_multiline_block_comments_without_corrupting_asp() -> None:
    statements = lex("before. %* first line\nsecond line *% after.")

    assert [statement.text for statement in statements] == ["before.", "after."]


def test_lexer_supports_nested_clingo_block_comments() -> None:
    statements = lex("%* outer %* nested *% outer *% fact.")

    assert [statement.text for statement in statements] == ["fact."]


def test_lexer_allows_comment_before_weak_constraint_annotation() -> None:
    statements = lex(":~ p(X). % cost\n[1@1,X]")

    assert [statement.text for statement in statements] == [":~ p(X). [1@1,X]"]


def test_parse_file_reads_utf8_and_parses_the_task(tmp_path) -> None:
    task = tmp_path / "task.lp"
    task.write_text("fact(a).\n#maxpl(2).", encoding="utf-8")

    parsed = parse_file(str(task))

    assert tuple(map(str, parsed.background)) == ("fact(a).",)
    assert parsed.max_program_clauses == 2


def test_parser_parses_all_background_statements_in_one_clingo_call(monkeypatch) -> None:
    calls: list[str] = []
    parse_program = task_parser.parse_program

    def record(source: str, line: int = 1):
        calls.append(source)
        return parse_program(source, line)

    monkeypatch.setattr(task_parser, "parse_program", record)

    parsed = task_parser.parse_text("a.\n#maxpl(2).\nb.")

    assert tuple(map(str, parsed.background)) == ("a.", "b.")
    assert len(calls) == 1


def test_background_ast_preserves_task_source_lines() -> None:
    parsed = parse_text(
        "\n#maxpl(2).\n%* comment\ncontinued *%\np(a).\n#modeh(1,p).\nq(a)."
    )

    assert [statement.location.begin.line for statement in parsed.background] == [5, 7]


def test_background_parse_error_reports_original_task_line() -> None:
    with pytest.raises(ValueError, match="line 3: invalid ASP program"):
        parse_text("a.\n#maxpl(2).\np(,).")


def test_example_parse_error_reports_original_task_line() -> None:
    with pytest.raises(ValueError, match="line 2: invalid example"):
        parse_text("a.\n#pos({p(X)},{}).")


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("#modeh bad.", "invalid directive"),
        ("#modeh(1, p(var(node,input))).\n#modeb(", "line 2"),
        ('p("unterminated).', "unterminated string"),
    ],
)
def test_language_errors_reject_malformed_statements(source: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_text(source)


@pytest.mark.parametrize("source", ["p(,).", "p(a) :- not.", "#unknown(foo)."])
def test_parser_rejects_invalid_background_asp(source: str) -> None:
    with pytest.raises(ValueError, match="line 1: invalid ASP program"):
        parse_text(source)


def test_lexer_rejects_script_blocks_instead_of_fragmenting_them() -> None:
    with pytest.raises(ValueError, match="#script blocks are not supported"):
        lex("#script (python)\nx = 1.0\n#end.")
