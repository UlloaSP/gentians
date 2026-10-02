from dataclasses import replace
from itertools import product

import clingo
import pytest
from clingo import ast

from gentians.arguments import Arguments
from gentians.clauses import generate_clause_space
from gentians.clauses.clause_mode import ClauseMode
from gentians.language import InductiveTask, parse_file, parse_text
from gentians.language import parser as task_parser
from gentians.language import modes as mode_parsers
from gentians.language import terms as mode_terms
from gentians.language import ast_nodes
from gentians.language.asp import clause_predicates, has_variable, parse_program, parse_rule, split_top_level_args
from gentians.language.ast_nodes import binding_terms
from gentians.clauses.reified_clause import instantiate_literal
from gentians.language.ir.atom_template import AtomTemplate
from gentians.language.grammar import SourceError, source_position
from gentians.language.lexer import lex
from tests.task_helpers import make_clause_space


@pytest.mark.parametrize("declaration", [
    '#bias(":- selected_slot(head,_).").',
    '#bias("\n bias_active.\n").',
    '#metarule(chain,"P(X) :- Q(X).").',
    '#predicate(target,p/1).',
    '#modem(chain(target/1,base/1)).',
    '#modeagg(1,p).',
    '#modearith(1,p).',
    '#modecmp(1,p).',
])
def test_removed_meta_directives_fail_before_background_parsing(monkeypatch, declaration):
    def unexpected(*args, **kwargs):
        pytest.fail("removed directives must not reach the background parser")

    monkeypatch.setattr(task_parser, "parse_program", unexpected)
    with pytest.raises(ValueError, match="line 2: .* (is no longer supported|was removed)"):
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

    (term,) = task.constants["word"]
    assert term.ast_type == ast.ASTType.SymbolicTerm
    assert str(term) == value
    assert term.symbol == clingo.String(text)


@pytest.mark.parametrize("value", [
    "box(red)", "(a,)", "(a,2)", "()", "-box(red)", "-red", "-1",
    'box((a,-2),nested("a,b"))',
])
@pytest.mark.parametrize("container", ["{}", "outer({})", "({},tail)"])
def test_fixed_term_shapes_match_direct_and_constant_syntax_without_reparsing(
    value, container, monkeypatch,
):
    direct = container.format(value)
    placeholder = container.format("const(word)")
    task = parse_text(
        f"#constant(word,{value}). #modeh(1,p({direct})). #modeb(1,p({placeholder}))."
    )
    head = task.language_bias_head[0].conclusions[0].atom
    (body,) = tuple(task.language_bias_body[0].literal.atom.concretizations(task.constants))

    def unexpected(*args, **kwargs):
        pytest.fail("fixed-term shapes must not reparse native nodes")

    monkeypatch.setattr(clingo, "parse_term", unexpected)
    monkeypatch.setattr(ast, "parse_string", unexpected)
    assert tuple(map(mode_terms.shape, head.terms)) == tuple(map(mode_terms.shape, body.terms))


@pytest.mark.parametrize("value", [
    "box(red)", "(a,)", "(a,2)", "()", "-box(red)", "-red", "-1",
    'box((a,-2),nested("a,b"))',
])
def test_constant_representation_does_not_hide_head_body_tautologies(value):
    task = parse_text(
        f"#constant(word,{value}). #modeh(1,p({value})). #modeb(1,p(const(word))). "
        "#maxv(0). #maxbl(1)."
    )
    clauses = generate_clause_space(task, Arguments()).clauses

    assert str(parse_rule(f"p({value}).")) in clauses
    assert str(parse_rule(f":- p({value}).")) in clauses
    assert str(parse_rule(f"p({value}) :- p({value}).")) not in clauses


def test_constant_representation_does_not_hide_contradictory_bodies():
    task = parse_text(
        "#constant(word,box(red)). #modeh(1,p(box(red))). #modeh(1,q). "
        "#modeb(1,p(box(red))). #modeb(1,not p(const(word))). "
        "#maxv(0). #maxbl(2)."
    )
    clauses = generate_clause_space(task, Arguments()).clauses

    assert str(parse_rule("q :- p(box(red)).")) in clauses
    assert str(parse_rule("q :- not p(box(red)).")) in clauses
    assert str(parse_rule("q :- p(box(red)),not p(box(red)).")) not in clauses


@pytest.mark.parametrize("head", ["{p(box(red))}", "not p(box(red))", "-p(box(red))"])
def test_fixed_shape_matching_preserves_choice_default_and_strong_heads(head):
    task = parse_text(
        f"#constant(word,box(red)). #modeh(1,{head}). #modeh(1,p(box(red))). "
        "#modeb(1,p(const(word))). "
        "#maxv(0). #maxbl(1)."
    )
    clauses = generate_clause_space(task, Arguments()).clauses

    assert str(parse_rule(f"{head} :- p(box(red)).")) in clauses


@pytest.mark.parametrize("other", ["box(blue)", '"box(red)"', "(red,)", "-box(red)"])
def test_fixed_shape_matching_keeps_distinct_ground_values(other):
    task = parse_text(
        f"#constant(word,{other}). #modeh(1,p(box(red))). #modeb(1,p(const(word))). "
        "#maxv(0). #maxbl(1)."
    )
    clauses = generate_clause_space(task, Arguments()).clauses

    assert str(parse_rule(f"p(box(red)) :- p({other}).")) in clauses


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


@pytest.mark.parametrize("recall", ["-1", "0", "2", "*"])
def test_complete_heads_require_recall_one(recall):
    with pytest.raises(ValueError, match="complete head modes require recall 1"):
        parse_text(f"#modeh({recall},p).")


@pytest.mark.parametrize("directive", ["#modeb", "#modec", "#modeha", "#modehd"])
@pytest.mark.parametrize("recall", ["-2", "-1", "0"])
def test_textual_mode_recalls_require_a_positive_integer_or_star(directive, recall):
    with pytest.raises(ValueError, match="mode recall must be positive or unbounded"):
        parse_text(f"{directive}({recall},p).")


@pytest.mark.parametrize("directive, field", [
    ("#modeb", "language_bias_body"),
    ("#modec", "language_bias_condition"),
    ("#modeha", "language_bias_aggregate_head"),
    ("#modehd", "language_bias_disjunctive_head"),
])
def test_star_remains_the_textual_unbounded_recall(directive, field):
    task = parse_text(f"{directive}(*,p).")

    assert getattr(task, field)[0].recall == -1


@pytest.mark.parametrize("source", [
    f"{directive}(1,p. {extra})."
    for directive in ("#modeb", "#modec", "#modeha", "#modehd", "#invent")
    for extra in ("#show q/0", "#const value=1", "#program ignored", "q")
] + [
    f"#modeh(1,{extra}. p)."
    for extra in ("#show q/0", "#const value=1", "#program ignored", "q")
])
def test_modes_reject_additional_asp_statements_in_the_payload(source):
    with pytest.raises(ValueError, match="invalid (mode literal|#modeh declaration)"):
        parse_text(source)


@pytest.mark.parametrize("directive", [
    "#modeh", "#modeb", "#modec", "#modeha", "#modehd", "#invent",
])
def test_invalid_mode_syntax_is_parsed_once_without_stderr(directive, monkeypatch, capsys):
    original = ast.parse_string
    calls = []

    def record(source, *args, **kwargs):
        calls.append(source)
        return original(source, *args, **kwargs)

    monkeypatch.setattr(ast, "parse_string", record)
    with pytest.raises(ValueError, match="invalid (mode literal|#modeh declaration)"):
        parse_text(f"{directive}(1,p(,)).")

    assert len(calls) == 1
    assert capsys.readouterr().err == ""


def test_directive_text_in_mode_strings_remains_data_and_background_remains_asp():
    text = 'period. #show q/0. #const value=1. #program ignored.'
    task = parse_text(
        '#const value=1. #show q/0. '
        f'#modeh(1,q({clingo.String(text)})). '
        f'#modeb(1,p({clingo.String(text)})).'
    )
    space = generate_clause_space(task, Arguments())

    assert [node.ast_type for node in task.background] == [
        ast.ASTType.Definition, ast.ASTType.ShowSignature,
    ]
    assert any(str(clingo.String(text)) in clause for clause in space.clauses)


@pytest.mark.parametrize("directive, field", [
    ("#modeha", "language_bias_aggregate_head"),
    ("#modehd", "language_bias_disjunctive_head"),
])
@pytest.mark.parametrize("atom", [
    "p",
    "p(1;2)",
    "-p(var(node,input,x))",
    "not p(var(node,input,x))",
])
def test_combinable_head_recall_defaults_to_unbounded(directive, field, atom):
    task = parse_text(f"{directive}({atom}).")
    explicit = parse_text(f"{directive}(*,{atom}).")

    assert getattr(task, field) == getattr(explicit, field)
    assert all(mode.recall == -1 for mode in getattr(task, field))


@pytest.mark.parametrize("directive", ["#modeha", "#modehd"])
def test_combinable_heads_reject_extra_top_level_arguments(directive):
    with pytest.raises(ValueError, match=f"invalid {directive} declaration"):
        parse_text(f"{directive}(1,p,q).")


@pytest.mark.parametrize("directive", ["#modeha", "#modehd"])
def test_omitted_combinable_recall_requires_a_finite_head_budget(directive):
    task = parse_text(f"#maxhl(*). {directive}(p).")

    with pytest.raises(ValueError, match=f"requires finite recalls for every {directive}"):
        generate_clause_space(task, Arguments())


def test_invalid_asp_is_parsed_once_and_reports_the_offset_line(monkeypatch, capsys):
    original = ast.parse_string
    calls = []

    def record(source, *args, **kwargs):
        calls.append(source)
        return original(source, *args, **kwargs)

    monkeypatch.setattr(ast, "parse_string", record)
    with pytest.raises(ValueError, match="line 9: invalid ASP program"):
        parse_program("p.\nq(,).", line=8)

    assert calls == ["p.\nq(,)."]
    assert capsys.readouterr().err == ""


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


@pytest.mark.parametrize("source", [
    "#modeb(1,p).",
    "#modeb(1,-p(box(var(node,input,x)))).",
    "#modeb(1,not -p(var(node,input,x))).",
    "#modeb(1,not not p(var(node,input,x))).",
    "#modeb(1,p(1;2)).",
    "#modeb(1,p(1,red;2,blue)).",
    "#modeb(1,p(var(node,input,x),red;var(node,input,x),blue)).",
    "#modeh(1,p(var(node,input,x))).",
    "#modeh(1,p(var(node,input,x));q(var(node,input,x))).",
    "#modeh(1,1{p(var(node,any,x)):q(var(node,any,x))}1).",
    "#modeh(1,p(var(node,any,x)):q(var(node,any,x))).",
    "#modeh(1,#count{var(node,any,x):p(var(node,any,x)):q(var(node,any,x))}=1).",
    "#modeh(1,{}).",
    "#modeh(1,#count{}=0).",
    "#modeh(1,p(1,red;2,blue)).",
    "#modeb(1,var(numeric,input)<2).",
    "#modeb(1,not var(numeric,input)=2).",
    "#modeb(1,p(var(node,any)):q(var(node,any))).",
    "#modeb(1,#false:q(var(node,any))).",
    "#modeb(1,var(numeric,input)<2:q(var(node,any))).",
    "#modeb(1,#count{var(node,any):p(var(node,any))}=1).",
    "#modeb(1,1<=#sum{2:p(var(node,any))}<=3).",
    "#modeb(1,not #count{var(node,any):p(var(node,any))}=1).",
    "#modeb(1,1{p(var(node,any)):q(var(node,any))}2).",
    "#modeh(1,var(numeric,input)<2).",
    "#modeh(1,{p(var(node,any)):q(var(node,any))}!=1).",
    "#modeh(1,1<=#sum{2:p(var(node,any)):q(var(node,any))}<=3).",
])
def test_reused_expansions_allow_independent_instantiation_without_mutating_syntax(source):
    task = parse_text("#constant(unused,extra). " + source)
    is_head = bool(task.language_bias_head)
    template = task.language_bias_head[0] if is_head else task.language_bias_body[0].literal
    before = repr(template)
    (concrete,) = tuple(template.concretizations(task.constants))
    assert concrete is template

    rendered = []
    for offset in (0, 4, 0):
        if is_head:
            elements = tuple(
                instantiate_literal(element, (offset,) * sum(
                    len(mode_terms.bindings(term)) for term in element.arguments
                ))
                for element in concrete.elements
            )
            rendered.append(str(concrete.instantiate(elements)))
        else:
            count = sum(len(mode_terms.bindings(term)) for term in concrete.arguments)
            rendered.append(str(instantiate_literal(concrete, (offset,) * count)))

    assert rendered[0] == rendered[2]
    if any(mode_terms.bindings(term) for term in concrete.arguments):
        assert rendered[0] != rendered[1]
    assert repr(template) == before


@pytest.mark.parametrize("directive", ["#modeh", "#modeb"])
def test_changed_constant_expansions_stay_independent_between_calls(directive):
    task = parse_text(
        "#constant(word,red). "
        f"{directive}(1,-p(box(var(node,input,x)),const(word),red;"
        "box(var(node,input,x)),blue,const(word)))."
    )
    is_head = bool(task.language_bias_head)
    template = task.language_bias_head[0] if is_head else task.language_bias_body[0].literal
    before = repr(template)
    red = tuple(template.concretizations(task.constants))
    blue = tuple(template.concretizations({"word": (mode_terms.fixed("blue"),)}))

    assert all(concrete is not template for concrete in (*red, *blue))
    assert red != blue
    assert tuple(template.concretizations(task.constants)) == red
    assert repr(template) == before


@pytest.mark.parametrize("source, assignments, expected", [
    (
        "#modeb(1,p(box(var(node,input,x),(_,var(node,any,y))),var(node,any,x))).",
        (4, 1, 4), "p(box(V4,(_,V1)),V4)",
    ),
    (
        "#modeb(1,not -p(box(var(node,input,x)),var(node,input,y))).",
        (4, 1), "not -p(box(V4),V1)",
    ),
    (
        "#modeb(1,p((var(numeric,input)+1)*var(numeric,input),"
        "-var(numeric,any),var(numeric,input)..9)).",
        (4, 1, 8, 3), "p((V4+1)*V1,-V8,V3..9)",
    ),
    (
        "#modeb(1,-p(box(var(node,input,x)),red;wrap(var(node,input,x)),blue)).",
        (4, 4), "-p(box(V4),red;wrap(V4),blue)",
    ),
])
def test_nested_instantiation_preserves_bindings_and_native_syntax(
    source, assignments, expected, monkeypatch,
):
    template = parse_text(source).language_bias_body[0].literal
    expected_node = parse_rule(f":- {expected}.").body[0]
    before = repr(template)

    def unexpected_parse(*args, **kwargs):
        pytest.fail("instantiating variable bindings must not parse text")

    monkeypatch.setattr(ast, "parse_string", unexpected_parse)
    monkeypatch.setattr(clingo, "parse_term", unexpected_parse)
    assert instantiate_literal(template, assignments) == expected_node
    instantiate_literal(template, tuple(index + 5 for index in assignments))
    assert instantiate_literal(template, assignments) == expected_node
    assert repr(template) == before


@pytest.mark.parametrize("source", ["red", 'box(("a,b",-2),red)', "()", "_", "1..9"])
def test_fixed_instantiation_reuses_syntax_without_consuming_bindings(source):
    term = parse_rule(f":- p({source}).").body[0].atom.symbol.arguments[0]
    variables = iter(("V7",))

    assert mode_terms.instantiate(term, binding_terms(variables)) is term
    assert next(variables) == "V7"


@pytest.mark.parametrize("value", ["V7", "_", "red", "-2", 'wrapped("a,b",(c,))'])
def test_variable_instantiation_accepts_native_validation_values(value):
    term = mode_terms.variable("node", "input")
    variables = iter((value, "V8"))

    result = mode_terms.instantiate(term, binding_terms(variables))

    assert str(result) == value
    assert result.ast_type == (
        ast.ASTType.Variable if value in {"V7", "_"} else ast.ASTType.SymbolicTerm
    )
    assert next(variables) == "V8"
    assert str(term) == "var(node,input)"


@pytest.mark.parametrize("source", ["const(node)", "box(const(node),var(node,input))"])
def test_instantiation_rejects_unexpanded_constants_before_later_bindings(source):
    term = parse_rule(f":- p({source}).").body[0].atom.symbol.arguments[0]
    variables = iter(("V7",))

    with pytest.raises(ValueError, match="constant placeholder must be concretized"):
        mode_terms.instantiate(term, binding_terms(variables))
    assert next(variables) == "V7"


def test_literal_instantiation_rejects_surplus_bindings():
    template = parse_text("#modeb(1,p(box(var(node,input)))).").language_bias_body[0].literal

    with pytest.raises(ValueError, match="literal has more variables than syntax bindings"):
        instantiate_literal(template, (0, 1))


@pytest.mark.parametrize("source", ["var(node,input)", "box(var(node,input))"])
def test_literal_instantiation_rejects_missing_bindings(source):
    template = parse_text(f"#modeb(1,p({source})).").language_bias_body[0].literal

    with pytest.raises((StopIteration, RuntimeError)):
        instantiate_literal(template, ())


def test_deep_mode_terms_preserve_expansion_bindings_and_substitution():
    depth = 600
    prefix, suffix = "f(" * depth, ")" * depth
    source = prefix + "pair(var(node,input,x),const(colour))" + suffix
    task = parse_text(
        "#constant(colour,red). #constant(colour,blue). "
        f"#modeb(1,p({source}))."
    )
    term = task.language_bias_body[0].literal.arguments[0]
    before = str(term)

    assert mode_terms.bindings(term)[0].path == (0,) * (depth + 1)
    assert mode_terms.constant_types(term) == {"colour"}
    assert not mode_terms.contains_anonymous(term)
    assert not mode_terms.contains_arithmetic(term)
    concrete = tuple(mode_terms.concretizations(term, task.constants))
    assert tuple(str(mode_terms.instantiate(value, binding_terms(iter(("V7",))))) for value in concrete) == (
        prefix + "pair(V7,red)" + suffix, prefix + "pair(V7,blue)" + suffix,
    )
    shape = mode_terms.shape(concrete[0])
    for _ in range(depth):
        assert shape[:2] == ("function", "f")
        shape = shape[2][0]
    assert shape == ("function", "pair", (("variable",), ("fixed", "red")))
    assert str(term) == before


def test_deep_transform_keeps_preorder_and_skips_replaced_subtrees():
    term = parse_rule(":- p(" + "f(" * 600 + "var(node,input)" + ")" * 600 + ").").body[0].atom.symbol.arguments[0]
    visited = []

    def replace(node):
        visited.append(node)
        return mode_terms.fixed("stop") if len(visited) == 301 else None

    result = mode_terms.transform(term, replace)

    assert str(result) == "f(" * 300 + "stop" + ")" * 300
    assert len(visited) == 301
    assert len(mode_terms.bindings(term)[0].path) == 600


@pytest.mark.parametrize("source", ["var(node,input)", "red", "2", "_", '"a,b"'])
def test_leaf_constant_expansion_does_not_build_a_cartesian_product(source, monkeypatch):
    term = parse_rule(f":- p({source}).").body[0].atom.symbol.arguments[0]

    def unexpected_expansion(*args, **kwargs):
        pytest.fail("a leaf without a constant placeholder needs no expansion recipe")

    monkeypatch.setattr(mode_terms, "concretize_terms", unexpected_expansion)
    (concrete,) = tuple(mode_terms.concretizations(term, {}))
    assert concrete is term


def test_annotation_construction_does_not_parse_identifiers(monkeypatch):
    expected = mode_terms.variable("node", "input", "x")

    def unexpected_parse(*args, **kwargs):
        pytest.fail("known annotation identifiers must be constructed directly")

    monkeypatch.setattr(clingo, "parse_term", unexpected_parse)
    assert mode_terms.variable("node", "input", "x") == expected
    assert str(mode_terms.variable("numeric", "")) == "var(numeric)"


@pytest.mark.parametrize("source, expected", [
    ("box((red,2),\"X\")", False),
    ("box((red,X),2)", True),
    ("var(X,input)", True),
    ("const(X)", True),
    ("var(node,input)", False),
    ("box(1..3)", False),
    ("box(1..X)", True),
    ("box(-X)", True),
    ("box(X+1)", True),
    ("@f(X)", True),
    ("@f(red)", False),
    ("red;X", True),
])
def test_native_asp_variable_inspection_preserves_term_syntax(source, expected):
    symbol = parse_rule(f":- p({source}).").body[0].atom.symbol
    assert has_variable(symbol) is expected
    if expected:
        with pytest.raises(ValueError, match="examples require ground symbolic atoms"):
            parse_text(f"#pos({{p({source})}},{{}}).")


def test_deep_example_terms_stay_ground_and_reject_nested_variables():
    prefix, suffix = "f(" * 600, ")" * 600
    task = parse_text(f"#pos({{p({prefix}red{suffix})}},{{}}).")
    assert not has_variable(task.positive_examples[0].included[0].atom.symbol)
    with pytest.raises(ValueError, match="line 1: invalid example"):
        parse_text(f"#pos({{p({prefix}X{suffix})}},{{}}).")


def test_inventions_preserve_order_signs_recalls_and_duplicate_policy():
    task = parse_text(
        "#invent(2,z(var(node,input))). #invent(3,-z(var(node,input))). "
        "#invent(1,a(var(node,output)))."
    )
    assert task.invented_predicates == (("z", 1), ("-z", 1), ("a", 1))
    assert [mode.recall for mode in task.language_bias_body] == [2, 3, 1]
    with pytest.raises(ValueError, match="line 2: duplicate #invent"):
        parse_text("#invent(1,z(var(node,input))).\n#invent(2,z(var(node,input))).")


@pytest.mark.parametrize("declaration", [
    "#maxv(bad).", "#maxpl(0).", "#minhl(*).", "#constant(any,red).",
    "#constant(node,X).", "#modeh(2,p).", "#modeb(0,p).", "#modeb(1,p(X)).",
    "#modec(1,#true).", "#modeha(1,p(_)).", "#modehd(1,p(_)).", "#invent(0,p).",
    "#pos({p(X)},{}).", "#neg({p(X)},{}).", "#modecmp(1,p).",
])
def test_directive_errors_report_the_original_statement_line_once(declaration):
    with pytest.raises(ValueError) as result:
        parse_text("% heading\n\nbk.\n  " + declaration)
    message = str(result.value)
    assert message.startswith("line 4: ")
    assert message.count("line 4: ") == 1


def test_unchanged_comparison_modes_do_not_rebuild_their_declaration(monkeypatch):
    declaration = mode_parsers._get_body_mode_declaration("#modeb(1,var(numeric,input)<2).")
    monkeypatch.setattr(mode_parsers, "_get_mode_declarations", lambda *args: (declaration,))
    assert mode_parsers._get_body_mode_declaration("#modeb(1,var(numeric,input)<2).") is declaration


@pytest.mark.parametrize("source, expected", [
    (
        "#modeh(1,var(numeric,input,n){selected(var(node,any,x))}var(numeric,input,n)).",
        "V1{selected(V0)}V1",
    ),
    (
        "#modeh(1,var(numeric,input,n)<=#sum{1:selected(var(node,any,x)):"
        "node(var(node,any,x))}<=var(numeric,input,n)).",
        "V1<=#sum{1:selected(V0):node(V0)}<=V1",
    ),
])
def test_head_instantiation_preserves_element_and_guard_binding_order(source, expected):
    head = parse_text(source).language_bias_head[0]
    before = repr(head)
    elements = tuple(instantiate_literal(element, (0,) * sum(
        len(mode_terms.bindings(term)) for term in element.arguments
    )) for element in head.elements)

    assert head.instantiate(elements, ("V1", "V1")) == parse_rule(expected + ".").head
    with pytest.raises(ValueError, match="more variables than syntax bindings"):
        head.instantiate(elements, ("V1", "V1", "V2"))
    assert repr(head) == before


def test_multiline_directive_syntax_errors_report_the_token_line():
    with pytest.raises(ValueError, match="^line 6: invalid mode literal"):
        parse_text("bk.\n% comment\n\n#modeb(\n  1,\n  p(,)\n).")


def test_clause_space_retains_clingo_ast_and_canonical_text() -> None:
    space = make_clause_space([":- p(X), X != 1."])

    assert space.clauses == (":- p(X), X != 1.",)
    assert space.statements[0].ast_type == ast.ASTType.Rule


def test_lexer_separates_multiple_statements_and_weak_constraints() -> None:
    statements = tuple(lex("value(1). value(2). :~ value(X). [1@1,X]"))

    assert [statement.text for statement in statements] == [
        "value(1).",
        "value(2).",
        ":~ value(X). [1@1,X]",
    ]


def test_lexer_keeps_all_clingo_annotations_with_their_statements() -> None:
    statements = tuple(lex(
        "#heuristic p(X): q(X). [1@2,true]\n"
        "#external enabled. % annotation follows a comment\n[false]"
    ))

    assert [statement.text for statement in statements] == [
        "#heuristic p(X): q(X). [1@2,true]",
        "#external enabled. \n[false]",
    ]


def test_lexer_removes_multiline_block_comments_without_corrupting_asp() -> None:
    statements = tuple(lex("before. %* first line\nsecond line *% after."))

    assert [statement.text for statement in statements] == ["before.", "after."]


def test_lexer_supports_nested_clingo_block_comments() -> None:
    statements = tuple(lex("%* outer %* nested *% outer *% fact."))

    assert [statement.text for statement in statements] == ["fact."]


@pytest.mark.parametrize("source", [
    "%*%* nested *%*% fact.",
    "%*%**%*% fact.",
    "%* %*%* nested *%*% *% fact.",
    "before. %*%* nested *% *% after.",
    "p%*%* nested *%*%(a).",
    "%* outer % ignore this closing marker *%\nouter *% fact.",
    ":~ p. %*%* nested *%*% [1@1]",
    ":~ p. %* outer % ignore *%\nouter *% [1@1]",
])
def test_lexer_comments_agree_with_clingo(source):
    expected = tuple(
        str(node) for node in parse_program(source)
        if node.ast_type != ast.ASTType.Comment
    )
    framed = "\n".join(statement.text for statement in tuple(lex(source)))

    assert tuple(map(str, parse_program(framed))) == expected


@pytest.mark.parametrize("source", [
    "%*%* nested *%",
    "%* outer % this closing marker is in a line comment *%",
])
def test_lexer_rejects_unclosed_nested_or_line_commented_blocks(source):
    with pytest.raises(ValueError, match="unterminated block comment"):
        tuple(lex(source))


def test_nested_comments_preserve_background_source_lines():
    task = parse_text("before.\n%*%* nested\n*%*%\nafter.")

    assert tuple(map(str, task.background)) == ("before.", "after.")
    assert [node.location.begin.line for node in task.background] == [1, 4]


@pytest.mark.parametrize("comment", [
    "% ignored",
    "%* block % ignored closing marker *%\n*%",
])
def test_comments_preserve_lines_inside_a_background_rule(comment):
    source = f"p :-\n{comment}\nq."
    task = parse_text(source)
    expected_line = source.count("\n") + 1

    assert task.background[0].body[0].location.begin.line == expected_line
    with pytest.raises(ValueError, match=f"line {expected_line}: invalid ASP program"):
        parse_text(source.replace("q.", "q(,)."))


def test_example_deduplication_keeps_the_first_ast_locations_and_context():
    first = "#pos({p,\nq},{},{first.})."
    task = parse_text(first + "\n#pos({p,q},{},{first.}).\n#pos({p,q},{},{second.}).")

    assert len(task.positive_examples) == 2
    assert task.positive_examples[0].included[1].location.begin.line == 2
    assert [example.context_text for example in task.positive_examples] == [
        "first.", "second.",
    ]


@pytest.mark.parametrize("directive, field", [
    ("#modeh(1,{p;q}).", "language_bias_head"),
    ("#modeb(1,#count{1:p}=1).", "language_bias_body"),
    ("#modec(1,p(1;2)).", "language_bias_condition"),
    ("#modeha(1,p(1;2)).", "language_bias_aggregate_head"),
    ("#modehd(1,p(1;2)).", "language_bias_disjunctive_head"),
    ("#pos({p},{q},{context.}).", "positive_examples"),
    ("#neg({p},{q},{context.}).", "negative_examples"),
])
def test_declarations_keep_first_occurrence_after_deduplication(directive, field):
    task = parse_text(f"{directive}\n{directive}")
    original = getattr(parse_text(directive), field)
    actual = getattr(task, field)

    assert actual == original
    if field.endswith("examples"):
        assert actual[0].included[0].location.begin.line == 1


def test_mode_deduplication_retains_order_recalls_labels_and_signs():
    sources = [
        "#modeb(2,p(var(node,input,x))).",
        "#modeb(1,p(var(node,input,x))).",
        "#modeb(1,not p(var(node,input,x))).",
        "#modeb(1,-p(var(node,input,x))).",
        "#modeb(1,p(var(node,input,y))).",
    ]
    task = parse_text("\n".join([*sources, *reversed(sources)]))

    assert task.language_bias_body == [
        parse_text(source).language_bias_body[0] for source in sources
    ]


def test_constant_deduplication_preserves_type_and_value_order():
    task = parse_text(
        "#constant(word,z). #constant(number,2). #constant(word,a). "
        "#constant(word,z). #constant(number,1). #constant(number,2)."
    )

    assert list(task.constants) == ["word", "number"]
    assert {name: tuple(map(str, values)) for name, values in task.constants.items()} == {
        "word": ("z", "a"), "number": ("2", "1"),
    }


def test_native_constants_keep_canonical_values_order_and_nominal_types():
    task = parse_text(
        '#constant(number,1+1). #constant(number,2). #constant(number,-3). '
        '#constant(node,2). #constant(symbol,-red). #constant(symbol,(a,)). '
        '#constant(symbol,wrapped("a,b",2)). #constant(symbol,#inf). '
        '#constant(symbol,#sup).'
    )

    assert list(task.constants) == ["number", "node", "symbol"]
    assert {name: tuple(map(str, values)) for name, values in task.constants.items()} == {
        "number": ("2", "-3"),
        "node": ("2",),
        "symbol": ("-red", "(a,)", 'wrapped("a,b",2)', "#inf", "#sup"),
    }
    assert all(term.ast_type == ast.ASTType.SymbolicTerm
               for values in task.constants.values() for term in values)


def test_nested_constant_expansion_reuses_native_values_without_reparsing(monkeypatch):
    task = parse_text(
        '#constant(word,wrapped("a,b",(c,))). '
        '#modeh(1,p(var(node,any),const(word))). '
        '#modeb(1,q(f(const(word)),var(node,any),const(word))).'
    )
    original = tuple(map(str, task.constants["word"]))

    def unexpected_parse(*args, **kwargs):
        pytest.fail("expanding a declared constant must reuse its native term")

    monkeypatch.setattr(clingo, "parse_term", unexpected_parse)
    head = tuple(task.language_bias_head[0].concretizations(task.constants))[0]
    body = tuple(task.language_bias_body[0].literal.concretizations(task.constants))[0]

    placeholder = task.language_bias_head[0].arguments[1]
    assert tuple(mode_terms.concretizations(placeholder, task.constants)) == task.constants["word"]
    assert str(instantiate_literal(head.elements[0], (0,))) == 'p(V0,wrapped("a,b",(c,)))'
    assert str(instantiate_literal(head.elements[0], (1,))) == 'p(V1,wrapped("a,b",(c,)))'
    assert str(instantiate_literal(body, (2,))) == 'q(f(wrapped("a,b",(c,))),V2,wrapped("a,b",(c,)))'
    assert tuple(map(str, task.constants["word"])) == original


@pytest.mark.parametrize("source", [
    "#constant(word,a,).",
    "#pos({p},{},).",
    "#neg({p},{},{context.},).",
    "#modeh(1,p,).",
    "#modeb(1,p,).",
    "#modec(1,p,).",
    "#modeha(1,p,).",
    "#modehd(1,p,).",
    "#invent(1,p,).",
])
def test_task_directives_reject_missing_final_arguments(source):
    with pytest.raises(ValueError, match="empty top-level argument"):
        parse_text(source)


def test_singleton_tuples_and_quoted_commas_are_not_missing_arguments():
    task = parse_text(
        '#constant(word,(a,)). #constant(word,"a,"). '
        '#modeh(1,p(const(word))). #pos({p((a,))},{p("a,")}).'
    )

    assert tuple(map(str, task.constants["word"])) == ("(a,)", '"a,"')
    assert task.positive_examples[0].included_text == "p((a,))"
    assert task.positive_examples[0].excluded_text == 'p("a,")'


@pytest.mark.parametrize("syntax, expected", [
    (
        "-p(f(const(word))):not q(const(word))",
        [f"-p(f({a})):not q({b})" for a, b in product(("a", "b"), repeat=2)],
    ),
    (
        "const(low)<=#count{const(word):not p(const(word))}<=const(high)",
        [f"{low}<=#count{{{a}:not p({b})}}<={high}"
         for a, b, low, high in product(("a", "b"), ("a", "b"), (0, 1), (2, 3))],
    ),
    (
        "const(low){not -p(const(word)):q(const(word))}const(high)",
        [f"{low}{{not -p({a}):q({b})}}{high}"
         for a, b, low, high in product(("a", "b"), ("a", "b"), (0, 1), (2, 3))],
    ),
    ("#count{}=const(low)", [f"#count{{}}={low}" for low in (0, 1)]),
])
def test_body_constant_expansion_preserves_cartesian_order_and_exact_literals(syntax, expected):
    task = parse_text(
        "#constant(word,a). #constant(word,b). "
        "#constant(low,0). #constant(low,1). #constant(high,2). #constant(high,3). "
        f"#modeb(1,{syntax})."
    )
    expanded = tuple(task.language_bias_body[0].literal.concretizations(task.constants))

    assert [instantiate_literal(literal, ()) for literal in expanded] == [
        parse_rule(f":- {literal}.").body[0] for literal in expected
    ]


@pytest.mark.parametrize("syntax, expected", [
    (
        "-p(f(const(word))):not q(const(word))",
        [f"-p(f({a})):not q({b})" for a, b in product(("a", "b"), repeat=2)],
    ),
    (
        "p(const(word));-q(const(word))",
        [f"p({a});-q({b})" for a, b in product(("a", "b"), repeat=2)],
    ),
    (
        "const(low){-p(const(word)):not q(const(word))}const(high)",
        [f"{low}{{-p({a}):not q({b})}}{high}"
         for low, high, a, b in product((0, 1), (2, 3), ("a", "b"), ("a", "b"))],
    ),
    (
        "const(low)<=#count{const(word): -p(const(word)):not q(const(word))}<=const(high)",
        [f"{low}<=#count{{{a}: -p({b}):not q({c})}}<={high}"
         for low, high, a, b, c in product((0, 1), (2, 3), ("a", "b"), ("a", "b"), ("a", "b"))],
    ),
    (
        "const(low){}const(high)",
        [f"{low}{{}}{high}" for low, high in product((0, 1), (2, 3))],
    ),
])
def test_head_constant_expansion_preserves_cartesian_order_and_exact_forms(syntax, expected):
    task = parse_text(
        "#constant(word,a). #constant(word,b). "
        "#constant(low,0). #constant(low,1). #constant(high,2). #constant(high,3). "
        f"#modeh(1,{syntax})."
    )
    expanded = tuple(task.language_bias_head[0].concretizations(task.constants))

    assert [
        head.instantiate(tuple(instantiate_literal(element, ()) for element in head.elements))
        for head in expanded
    ] == [parse_rule(f"{head}.").head for head in expected]


def test_lexer_allows_comment_before_weak_constraint_annotation() -> None:
    statements = tuple(lex(":~ p(X). % cost\n[1@1,X]"))

    assert [statement.text for statement in statements] == [":~ p(X). \n[1@1,X]"]


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
        tuple(lex("#script (python)\nx = 1.0\n#end."))


def test_predicate_inspection_handles_deep_comparisons_and_signed_scopes():
    term = "f(" * 1200 + "a" + ")" * 1200
    rule = parse_rule(f"-q:guard;not r:condition :- -p,{term}=a.")

    assert clause_predicates(rule) == (
        frozenset({("-q", 0)}),
        frozenset({("guard", 0), ("r", 0), ("condition", 0), ("-p", 0)}),
        2,
    )


def test_lexer_delivers_complete_statements_before_inspecting_later_input():
    statements = lex("p.\nq(].")

    assert next(statements).text == "p."
    with pytest.raises(ValueError, match="line 2: unmatched"):
        next(statements)
    with pytest.raises(ValueError, match="line 2: unmatched"):
        parse_text("p.\nq(].")


def test_constant_expansion_constructs_variants_as_they_are_consumed(monkeypatch):
    task = parse_text(
        "#constant(t,a). #constant(t,b). #constant(t,c). "
        "#modeb(1,p(const(t),const(t)))."
    )
    template = task.language_bias_body[0].literal.atom
    original = AtomTemplate.__post_init__
    constructed = []

    def record(self):
        constructed.append(self)
        original(self)

    monkeypatch.setattr(AtomTemplate, "__post_init__", record)
    variants = template.concretizations(task.constants)
    assert constructed == []
    first = next(variants)
    assert constructed == [first]
    assert tuple(map(str, first.terms)) == ("a", "a")
    remaining = tuple(variants)
    assert [tuple(map(str, item.terms)) for item in (first, *remaining)] == list(
        product(("a", "b", "c"), repeat=2)
    )
    assert len(constructed) == 9
    assert tuple(map(str, template.terms)) == ("const(t)", "const(t)")


def test_repeated_variables_share_native_nodes_only_within_one_instantiation(monkeypatch):
    template = parse_text(
        "#modeb(1,p(var(node,any),box(var(node,any)),var(node,any)))."
    ).language_bias_body[0].literal
    original = ast_nodes.binding_term
    constructed = []

    def record(value):
        node = original(value)
        constructed.append(node)
        return node

    monkeypatch.setattr(ast_nodes, "binding_term", record)
    node = instantiate_literal(template, (0, 0, 1))
    assert str(node) == "p(V0,box(V0),V1)"
    assert [str(value) for value in constructed] == ["V0", "V1"]
    first_nodes = tuple(constructed)
    instantiate_literal(template, (0, 0, 1))
    assert [str(value) for value in constructed] == ["V0", "V1", "V0", "V1"]
    assert all(a is not b for a, b in zip(first_nodes, constructed[2:], strict=True))


def test_fixed_guards_are_retained_during_head_and_body_instantiation(monkeypatch):
    task = parse_text("#modeh(1,1{p}2). #modeb(1,1<=#count{}<=2).")
    head = task.language_bias_head[0]
    body = task.language_bias_body[0].literal
    expected_head = parse_rule("1{p}2.").head
    expected_body = parse_rule(":- 1<=#count{}<=2.").body[0]
    original = ast.AST.update

    def checked(self, **kwargs):
        if self.ast_type == ast.ASTType.Guard:
            pytest.fail("fixed guards must not be reconstructed")
        return original(self, **kwargs)

    monkeypatch.setattr(ast.AST, "update", checked)
    assert head.instantiate((instantiate_literal(head.elements[0], ()),)) == expected_head
    assert instantiate_literal(body, ()) == expected_body


def test_compiled_metadata_is_rederived_when_a_literal_is_replaced():
    first = parse_text("#modeb(1,p(var(node,any))).").language_bias_body[0].literal
    second = parse_text(
        "#modeb(1,-q(box(var(node,any),var(node,any))))."
    ).language_bias_body[0].literal
    mode = ClauseMode(0, 0, "body", 1, first)
    changed = replace(mode, literal=second)

    assert mode.arguments == first.arguments
    assert changed.arguments == second.arguments
    assert changed.binding_positions == (0, 1)
    assert tuple(binding.path for binding in changed.bindings) == ((0, 0), (0, 1))
    assert changed.dependencies == frozenset({("-q", 1)})
    assert mode.dependencies == frozenset({("p", 1)})


@pytest.mark.parametrize(("source", "line", "message"), [
    ("\n\n#modeb(1,p(const(t))).", 3, "constant mode types require"),
    ("\n#modeh(1,p(var(t,input))).\n#invent(1,p(var(t,input))).", 3, "invented predicates"),
    ("#modeha(p(var(t,input))).\n#maxhl(1).\n#minhl(2).", 3, "#minhl cannot exceed"),
    ("#minhl(2).\n#modehd(p(var(t,input))).", 1, "#minhl cannot exceed"),
])
def test_cross_declaration_errors_report_the_responsible_source_line(source, line, message):
    with pytest.raises(ValueError) as caught:
        parse_text(source)
    assert str(caught.value).startswith(f"line {line}: {message}")


@pytest.mark.parametrize("file_name", ["bk.lp", "exs.lp", "bias.lp"])
@pytest.mark.parametrize("preceding", ["", "fact.", "fact.\n"])
def test_directory_errors_report_the_original_file_and_local_line(tmp_path, file_name, preceding):
    for name in ("bk.lp", "exs.lp", "bias.lp"):
        (tmp_path / name).write_text(preceding, encoding="utf-8")
    source = "\n#modeh(1,p(\"line 999\") + )."
    (tmp_path / file_name).write_text(source, encoding="utf-8")

    with pytest.raises(ValueError) as caught:
        parse_file(str(tmp_path))
    message = str(caught.value)
    assert message.startswith(f"{tmp_path / file_name}:line 2: invalid #modeh")
    assert "syntax error" in message
    assert "line 999" in message


def test_file_error_reports_the_file_and_clingo_explanation(tmp_path, capsys):
    path = tmp_path / "task.lp"
    path.write_text("p.\nq(,).", encoding="utf-8")

    with pytest.raises(ValueError) as caught:
        parse_file(str(path))
    assert str(caught.value).startswith(f"{path}:line 2: invalid ASP program")
    assert "syntax error, unexpected" in str(caught.value)
    assert capsys.readouterr().err == ""


def test_directory_error_reports_both_conflicting_declarations(tmp_path):
    (tmp_path / "bk.lp").write_text("#maxhl(1).", encoding="utf-8")
    (tmp_path / "exs.lp").write_text("", encoding="utf-8")
    (tmp_path / "bias.lp").write_text(
        "#modeha(p(var(t,input))).\n#minhl(2).", encoding="utf-8"
    )

    with pytest.raises(ValueError) as caught:
        parse_file(str(tmp_path))
    message = str(caught.value)
    assert message.startswith(f"{tmp_path / 'bias.lp'}:line 2: #minhl cannot exceed")
    assert f"{tmp_path / 'bk.lp'}:line 1" in message


def test_invalid_constant_retains_clingo_explanation_without_duplicate_locations(capsys):
    with pytest.raises(ValueError) as caught:
        parse_text("\n#constant(t,a;b).")
    message = str(caught.value)
    assert message.startswith("line 2: #constant value must be a ground term")
    assert "unexpected token" in message
    assert ";" in message
    assert message.count("line ") == 1
    assert "<string>" not in message
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("declaration", [
    "#maxbl(1).", "#invent(1,p(var(t,input))).",
])
def test_duplicate_declaration_errors_report_both_source_files(tmp_path, declaration):
    (tmp_path / "bk.lp").write_text(declaration, encoding="utf-8")
    (tmp_path / "exs.lp").write_text("", encoding="utf-8")
    (tmp_path / "bias.lp").write_text("\n" + declaration, encoding="utf-8")

    with pytest.raises(ValueError) as caught:
        parse_file(str(tmp_path))
    message = str(caught.value)
    assert message.startswith(f"{tmp_path / 'bias.lp'}:line 2: duplicate")
    assert f"{tmp_path / 'bk.lp'}:line 1" in message


def test_diagnostic_location_stripping_preserves_quoted_location_text():
    from gentians.language.asp import _diagnostic_detail

    assert _diagnostic_detail(
        '<string>:1:3: error: unexpected token "<string>:123:4: payload"'
    ) == 'error: unexpected token "<string>:123:4: payload"'


@pytest.mark.parametrize("directive, field", [
    ("#modeh", "language_bias_head"),
    ("#modeha", "language_bias_aggregate_head"),
    ("#modehd", "language_bias_disjunctive_head"),
    ("#modeb", "language_bias_body"),
    ("#modec", "language_bias_condition"),
])
def test_identical_modes_are_parsed_once_per_task(monkeypatch, directive, field):
    original = ast.parse_string
    calls = []

    def record(source, *args, **kwargs):
        if source:
            calls.append(source)
        return original(source, *args, **kwargs)

    monkeypatch.setattr(ast, "parse_string", record)
    source = f"{directive}(1,-p(var(node,input,x))).\n"
    task = parse_text(source * 3)

    assert len(getattr(task, field)) == 1
    assert len(calls) == 1
    parse_text(source)
    assert len(calls) == 2


@pytest.mark.parametrize("relation, probes", [
    ("var(numeric)+1=var(numeric)", 2),
    ("var(numeric)<var(numeric)", 1),
    ("var(numeric)=1..3", 1),
])
def test_comparison_safety_cache_retains_false_results_and_distinct_recalls(monkeypatch, relation, probes):
    original = mode_parsers._comparison_outputs_are_safe
    results = []

    def record(literal):
        result = original(literal)
        results.append(result)
        return result

    monkeypatch.setattr(mode_parsers, "_comparison_outputs_are_safe", record)
    source = f"#modeb(1,{relation}). #modeb(2,{relation})."
    task = parse_text(source)

    assert [mode.recall for mode in task.language_bias_body] == [1, 2]
    assert len(results) == probes
    if probes == 2:
        assert results == [False, True]
    parse_text(source)
    assert len(results) == probes * 2


def test_comparison_safety_cache_keeps_labels_and_operators_distinct(monkeypatch):
    original = mode_parsers._comparison_outputs_are_safe
    calls = []

    def record(literal):
        calls.append(literal)
        return original(literal)

    monkeypatch.setattr(mode_parsers, "_comparison_outputs_are_safe", record)
    task = parse_text(
        "#modeb(1,var(numeric,output,x)=1..3). "
        "#modeb(2,var(numeric,output,x)=1..3). "
        "#modeb(1,var(numeric,output,y)=1..3). "
        "#modeb(1,1<var(numeric,output,x)<3)."
    )

    assert len(task.language_bias_body) == 4
    assert len(calls) == 3
    assert len(set(calls)) == 3


def test_bounded_implicit_comparison_builds_only_the_accepted_direction(monkeypatch):
    original = mode_parsers._with_binding_directions
    directions = []

    def record(literal, values):
        directions.append(values)
        return original(literal, values)

    monkeypatch.setattr(mode_parsers, "_with_binding_directions", record)
    task = parse_text("#modeb(1,var(numeric)=1..3).")

    assert directions == [("output",)]
    assert mode_terms.bindings(task.language_bias_body[0].literal.arguments[0])[0].direction == "output"


@pytest.mark.parametrize("syntax", ["const(low)<const(high)", "not const(low)=const(high)", "not not const(low)=const(high)"])
def test_comparison_constants_expand_with_order_and_exact_negation(syntax):
    task = parse_text(
        "#constant(low,0). #constant(low,1). #constant(high,2). #constant(high,3). "
        f"#modeb(1,{syntax})."
    )
    template = task.language_bias_body[0].literal
    concrete = tuple(template.concretizations(task.constants))
    expected = [syntax.replace("const(low)", str(low)).replace("const(high)", str(high))
                for low, high in product((0, 1), (2, 3))]

    assert [instantiate_literal(literal, ()) for literal in concrete] == [
        parse_rule(f":- {literal}.").body[0] for literal in expected
    ]
    assert all(literal is not template for literal in concrete)


def test_nested_constant_expansion_is_progressive_and_preserves_cartesian_order(monkeypatch):
    task = parse_text(
        "#constant(t,a). #constant(t,b). #constant(t,c). "
        "#modeh(1,p(f(g(const(t),const(t)))))."
    )
    term = task.language_bias_head[0].arguments[0]
    original = mode_terms._replace_arguments
    calls = []

    def record(node, children):
        calls.append(node)
        return original(node, children)

    monkeypatch.setattr(mode_terms, "_replace_arguments", record)
    variants = mode_terms.concretizations(term, task.constants)
    first = next(variants)

    assert str(first) == "f(g(a,a))"
    assert len(calls) == 2
    assert list(map(str, (first, *variants))) == [f"f(g({a},{b}))" for a, b in product(("a", "b", "c"), repeat=2)]
    assert str(term) == "f(g(const(t),const(t)))"
    assert str(first) == "f(g(a,a))"


def test_nested_constant_expansion_reuses_unchanged_branches(monkeypatch):
    task = parse_text("#constant(t,a). #constant(t,b). #modeh(1,p(f(g(const(t)),h(const(t))))).")
    term = task.language_bias_head[0].arguments[0]
    original = mode_terms._replace_arguments
    updated = []

    def record(node, children):
        updated.append(node.name)
        return original(node, children)

    monkeypatch.setattr(mode_terms, "_replace_arguments", record)
    variants = mode_terms.concretizations(term, task.constants)
    assert str(next(variants)) == "f(g(a),h(a))"
    updated.clear()
    assert str(next(variants)) == "f(g(a),h(b))"
    assert updated == ["h", "f"]


def test_deep_constant_expansion_has_no_python_recursion_limit():
    depth = 1200
    source = "#constant(t,a). #constant(t,b). #modeh(1,p(" + "f(" * depth + "const(t)" + ")" * depth + "))."
    task = parse_text(source)
    variants = tuple(mode_terms.concretizations(task.language_bias_head[0].arguments[0], task.constants))

    assert tuple(map(str, variants)) == tuple("f(" * depth + value + ")" * depth for value in ("a", "b"))


def test_constant_expansion_does_not_treat_missing_or_empty_domains_as_fixed():
    task = parse_text("#constant(t,a). #modeb(1,const(t)=1).")
    template = task.language_bias_body[0].literal

    with pytest.raises(KeyError, match="t"):
        tuple(template.concretizations({}))
    assert tuple(template.concretizations({"t": ()})) == ()


@pytest.mark.parametrize("value", ['"a,.(b)[c]{d}"', r'"a\"b,c"', r'"a\\,b"', "(a,)"])
def test_statement_and_argument_scanners_preserve_nested_and_quoted_commas(value):
    statement = f"p({value},f(1,2))."

    assert [item.text for item in lex(statement + "q.")] == [statement, "q."]
    arguments = f"{value},f(1,2)"
    assert [arguments[start:end] for start, end in split_top_level_args(arguments)] == [value, "f(1,2)"]


@pytest.mark.parametrize("source", ["p(]", "p(a", '"a,b', "p(a),"])
def test_argument_scanner_rejects_unbalanced_or_incomplete_fields(source):
    with pytest.raises(ValueError):
        split_top_level_args(source)


@pytest.mark.parametrize("directive", ["#modeh", "#modeha", "#modehd", "#modeb", "#modec", "#invent"])
@pytest.mark.parametrize("comment", ["", "%* \u00f1 nested %* inner *% *%"])
def test_native_mode_errors_use_original_token_line_and_byte_column(directive, comment):
    source = f'p("\u00f1").\n   {directive}(1,\n  {comment} p(,)\n).'

    with pytest.raises(SourceError) as caught:
        parse_text(source)

    assert (caught.value.line, caught.value.column) == source_position(source, source.index(",)"))
    assert "syntax error" in caught.value.message


@pytest.mark.parametrize("example", [
    '#pos({\n p(,)\n},{}).',
    '#neg({},{\n p(,)\n}).',
    '#pos({},{},{p("\u00f1").\n p(,).}).',
    '#neg({},{},{p. %* \u00f1 *% q(,).}).',
])
def test_native_example_errors_use_original_field_line_and_byte_column(example):
    source = "\n\n   " + example

    with pytest.raises(SourceError) as caught:
        parse_text(source)

    assert (caught.value.line, caught.value.column) == source_position(source, source.index(",)"))


@pytest.mark.parametrize("separator", ["\u2028", "\u0085", "\r"])
def test_error_remapping_counts_only_newlines(separator):
    source = f'#pos({{}},{{}},{{q("a{separator}b").\nr(,).}}).'

    with pytest.raises(SourceError) as caught:
        parse_text(source)

    assert (caught.value.line, caught.value.column) == (2, 3)


def test_synthetic_mode_suffix_error_stops_at_original_payload_boundary():
    source = "#modeh(1,\n p(a)\n +\n)."

    with pytest.raises(SourceError) as caught:
        parse_text(source)

    assert (caught.value.line, caught.value.column) == (4, 1)


def test_background_errors_preserve_columns_after_comments_and_task_directives():
    source = '#modeh(1,p). p("\u00f1"). %* ignored *% q(,).'

    with pytest.raises(SourceError) as caught:
        parse_text(source)

    assert (caught.value.line, caught.value.column) == source_position(source, source.index(",)"))


def test_background_ast_retains_original_byte_columns_and_omits_comment_nodes():
    source = '#modeh(1,p). p("\u00f1"). %* ignored *% q.'
    task = parse_text(source)

    assert [node.ast_type for node in task.background] == [ast.ASTType.Rule] * 2
    assert [(node.location.begin.line, node.location.begin.column) for node in task.background] == [
        source_position(source, source.index('p("')), source_position(source, source.index("q.")),
    ]


def test_directory_fragment_error_retains_original_file_token_line_and_column(tmp_path):
    (tmp_path / "bk.lp").write_text('p("\u00f1").\n', encoding="utf-8")
    (tmp_path / "exs.lp").write_text("", encoding="utf-8")
    bias = tmp_path / "bias.lp"
    bias.write_text("#modeb(1,\n    p(,)\n).", encoding="utf-8")

    with pytest.raises(ValueError) as caught:
        parse_file(str(tmp_path))

    assert str(caught.value).startswith(f"{bias}:line 2:")
    assert str(caught.value).endswith("(column 7)")


@pytest.mark.parametrize("source, position", [
    ("#constant(t,\n a;b\n).", (2, 4)),
    ("#constant(t,\n f(a) +\n).", (3, 2)),
    ('#constant(t,\n f("\u00f1") ;\n).', (2, 11)),
])
def test_constant_errors_preserve_the_native_cursor_position(source, position, capsys):
    with pytest.raises(SourceError) as caught:
        parse_text(source)

    assert (caught.value.line, caught.value.column) == position
    assert "#constant value must be a ground term" in caught.value.message
    assert capsys.readouterr().err == ""
