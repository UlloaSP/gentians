import pytest
from clingo import ast

from gentians.clauses.rule_space import RuleSpace
from gentians.language import InductiveTask, parse_file, parse_text
from gentians.language import parser as task_parser
from gentians.language.lexer import lex


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
    assert task.language_bias_head[0].recall == 1
    assert task.language_bias_head[0].template.elements[0].name == "target"


def test_rule_space_retains_clingo_ast_and_canonical_text() -> None:
    space = RuleSpace.from_clauses([":- p(X), X != 1."])

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


def test_bias_payload_can_span_lines_and_contain_comment_characters() -> None:
    task = parse_text(
        '''
        #bias(
            "bias_active :- selected(head,0,0).\n"
        ).
        '''
    )

    assert tuple(map(str, task.bias)) == ("bias_active :- selected(head,0,0).",)
    assert task.bias[0].ast_type == ast.ASTType.Rule


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
        ('#bias("unterminated).', "unterminated string"),
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
