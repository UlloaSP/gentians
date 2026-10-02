from unittest.mock import patch

import pytest
from clingo import ast

from gentians.language import asp, modes, parse_text, terms
from gentians.language.ast_nodes import LOCATION, binding_term
from gentians.language.grammar import SourceError, source_position
from gentians.language.ir.head_template import _integer_bounds
from gentians.arguments import Arguments
from gentians.clauses import generate_clause_space


def nested(term, depth):
    for _ in range(depth):
        term = ast.Function(LOCATION, "f", [term], False)
    return term


@pytest.mark.parametrize("values", [(1,), (2,), (1, 2)])
def test_comparison_safety_uses_declared_constant_values(values):
    source = "#modeb(1,const(t)*var(numeric,output)=var(numeric,input))."
    source += " ".join(f"#constant(t,{value})." for value in values)
    task = parse_text(source)
    literal = task.language_bias_body[0].literal
    assert [item.direction for term in literal.terms for item in terms.bindings(term)] == ["output", "input"]
    assert len(tuple(literal.concretizations(task.constants))) == len(values)


@pytest.mark.parametrize("values", [(0,), (1, 0), (0, 2)])
def test_explicit_comparison_outputs_must_be_safe_for_every_constant(values):
    source = " ".join(f"#constant(t,{value})." for value in values)
    with pytest.raises(SourceError, match="outputs are not safe"):
        parse_text(source + " #modeb(1,const(t)*var(numeric,output)=var(numeric,input)).")


def test_real_constant_safety_reaches_generation_without_changing_the_relation():
    source = """seed(2). seed(4). #pos({target(1)},{}).
    #constant(k,1). #constant(k,2). #maxv(2). #maxbl(2). #maxhl(1).
    #modeh(1,target(var(numeric,input))).
    #modeb(1,seed(var(numeric,output))).
    #modeb(1,const(k)*var(numeric,output)=var(numeric,input))."""
    space = generate_clause_space(parse_text(source), Arguments())
    assert "target(V1) :- seed(V0); (2*V1) = V0." in space.clauses
    assert "target(V1) :- seed(V0); V0 = V1." in space.clauses


def test_constant_head_bounds_fail_during_task_parsing_with_source_position():
    source = '#constant(low,0). #constant(low,2). #constant(high,1).\n %* ñ *% #modeh(1,const(low){p}const(high)).'
    with pytest.raises(SourceError, match="lower bound") as caught:
        parse_text(source)
    assert (caught.value.line, caught.value.column) == source_position(source, source.index("const(low)"))


def test_large_constant_recipe_remains_linear_after_metadata_eviction(monkeypatch):
    root = nested(terms.constant("t"), 9000)
    visits = 0
    original = terms._postorder

    class VisitLimit(Exception):
        pass

    def record(*args, **kwargs):
        nonlocal visits
        for node in original(*args, **kwargs):
            visits += 1
            if visits > 30000:
                raise VisitLimit
            yield node

    with terms.metadata_scope():
        assert terms.constant_types(root) == {"t"}
        monkeypatch.setattr(terms, "_postorder", record)
        stream = terms.concretize_terms((root,), {"t": (terms.fixed("a"),)})
        try:
            concrete = next(stream)[0]
        except VisitLimit:
            concrete = None
        stream.close()
    assert visits <= 9001, "recipe preparation revisited large subtrees"
    assert concrete is not None
    assert not terms.constant_types(concrete)


def test_instantiation_reuses_fixed_branches_and_consumes_only_placeholders(monkeypatch):
    fixed = nested(terms.fixed("a"), 300)
    root = ast.Function(LOCATION, "p", [fixed, terms.variable("t", "input")], False)
    with terms.metadata_scope():
        terms.constant_types(root)
        retained_fixed = terms.arguments(root)[0]
        original = terms.arguments

        def arguments(node):
            assert node is not retained_fixed, "instantiation descended into a fixed branch"
            return original(node)

        monkeypatch.setattr(terms, "arguments", arguments)
        variables = iter((binding_term("X"), binding_term("Y")))
        concrete = terms.instantiate(root, variables)
        assert concrete.arguments[0] == fixed
        assert str(concrete.arguments[1]) == "X"
        assert str(next(variables)) == "Y"


def test_ground_shape_formats_only_its_retained_root():
    root = nested(terms.fixed("a"), 300)
    original = ast.AST.__str__
    calls = []

    def record(node):
        calls.append(node)
        return original(node)

    with patch.object(ast.AST, "__str__", record):
        result = terms.shape(root)
    assert result == ("fixed", str(root))
    assert len(calls) == 1
    assert calls[0] is root


@pytest.mark.parametrize("directive, field", [
    ("#modeb", "language_bias_body"), ("#modec", "language_bias_condition"),
    ("#modeha", "language_bias_aggregate_head"), ("#modehd", "language_bias_disjunctive_head"),
])
def test_mode_payload_is_parsed_once_across_distinct_recalls(monkeypatch, directive, field):
    original = ast.parse_string
    calls = []
    validations = []
    validate = terms.validate_labels

    def record(source, *args, **kwargs):
        if source:
            calls.append(source)
        return original(source, *args, **kwargs)

    monkeypatch.setattr(ast, "parse_string", record)
    def record_validation(*args, **kwargs):
        validations.append(None)
        return validate(*args, **kwargs)

    monkeypatch.setattr(terms, "validate_labels", record_validation)
    task = parse_text(" ".join(f"{directive}({recall},p(var(t,input)))." for recall in (1, 2, 3)))
    assert [mode.recall for mode in getattr(task, field)] == [1, 2, 3]
    assert len(calls) == 1
    assert len(validations) == 1
    assert all(mode.literal is getattr(task, field)[0].literal for mode in getattr(task, field))


@pytest.mark.parametrize("recall", [0, -2])
def test_changing_recall_preserves_validation_and_original_declaration(recall):
    mode = parse_text("#modeb(1,p(var(t,input))).").language_bias_body[0]
    with pytest.raises(ValueError, match="recall"):
        mode.with_recall(recall)
    assert mode.recall == 1
    assert mode.with_recall(1) is mode
    other = mode.with_recall(-1)
    assert other.recall == -1 and other.literal is mode.literal


@pytest.mark.parametrize("declaration", [
    "#modec(1,#true).", "#modeha(1,#true).", "#modehd(1,#true).",
    "#modeha(1,p(_)).", "#modehd(1,p(_)).",
])
def test_cached_payloads_retain_category_specific_validation(declaration):
    with pytest.raises(SourceError, match="requires an atom|anonymous variables"):
        parse_text("#modeb(1,p(_)). " + declaration)


@pytest.mark.parametrize("constant", [0, 1, 2])
def test_comparison_safety_uses_background_constant_definitions(constant):
    source = f"#const c={constant}. #constant(t,c). #modeb(1,const(t)*var(numeric,output)=var(numeric,input))."
    if constant == 0:
        with pytest.raises(SourceError, match="outputs are not safe"):
            parse_text(source)
    else:
        assert parse_text(source).language_bias_body[0].literal.terms


def test_implicit_outputs_use_background_constant_definitions():
    task = parse_text("#const c=0. #constant(t,c). #modeb(1,const(t)*var(numeric)=0).")
    assert [binding.direction for term in task.language_bias_body[0].literal.terms
            for binding in terms.bindings(term)] == ["input"]


@pytest.mark.parametrize("source", [
    "#constant(t,2). #modeh(1,(const(t)+1){p}1).",
    "#constant(t,2). #constant(u,2). #modeh(1,const(t){p}(const(u)-1)).",
    "#const c=0. #constant(t,c). #modeh(1,1{p}const(t)).",
    "#const a=2. #const c=a+1. #constant(t,c). #modeh(1,const(t){p}2).",
])
def test_ground_choice_bounds_use_native_arithmetic_and_background_constants(source):
    with pytest.raises(SourceError, match="lower bound") as caught:
        parse_text(source)
    start = source.index("#modeh") + len("#modeh(1,")
    # Native arithmetic locations begin at the first operand, after grouping.
    if source[start] == "(":
        start += 1
    assert (caught.value.line, caught.value.column) == source_position(source, start)


def test_compatible_ground_choice_bounds_keep_native_syntax():
    task = parse_text("#const c=1. #constant(t,c). #modeh(1,(const(t)+1){p}3).")
    head = next(task.language_bias_head[0].concretizations(task.constants))
    assert str(head.form.left_guard.term) == "(c+1)"


def test_native_bound_validation_consumes_one_variant_at_a_time():
    expression = asp.parse_rule("p :- 1+1=2.").body[0].atom.term
    produced = 0

    def expressions():
        nonlocal produced
        for _ in range(3):
            produced += 1
            yield expression

    values = _integer_bounds(expressions(), ())
    assert next(values) == 2
    assert produced == 1
    values.close()


@pytest.mark.parametrize("definitions", ["#const a=b. #const b=a.", "#const c=1. #const c=2."])
def test_invalid_native_bound_definitions_report_the_guard_location(definitions):
    source = definitions + " #modeh(1,(1+1){p}3)."
    with pytest.raises(SourceError, match="invalid head bound") as caught:
        parse_text(source)
    assert (caught.value.line, caught.value.column) == source_position(source, source.index("1+1"))


def test_predicate_extraction_does_not_descend_into_arithmetic_terms(monkeypatch):
    rule = asp.parse_rule("p :- " + "f(" * 300 + "a" + ")" * 300 + "=1,not -q.")
    original = asp._ast_children

    def children(node):
        assert node.ast_type != ast.ASTType.Function, "term functions cannot contain predicates"
        yield from original(node)

    monkeypatch.setattr(asp, "_ast_children", children)
    assert asp.clause_predicates(rule) == (frozenset({("p", 0)}), frozenset({("-q", 0)}), 2)


def test_inferred_placeholders_retain_native_source_locations():
    source = "#modeb(1,\n var(numeric)+1=var(numeric))."
    original = modes._get_mode_declarations(source, "#modeb")[0].literal
    prepared = parse_text(source).language_bias_body[0].literal
    assert prepared.terms[1].location == original.terms[1].location
    assert prepared.terms[1].arguments[0].location == original.terms[1].arguments[0].location


@pytest.mark.parametrize("declaration, head", [
    ("#modeb(1,#sum{const(t):p(const(t))}=const(t)).", False),
    ("#modeb(1,p(const(t)):q(const(t))).", False),
    ("#modeh(1,#sum{const(t):p(const(t)):q(const(t))}=const(t)).", True),
])
def test_flattened_ir_arguments_remain_independent_across_variants(declaration, head):
    task = parse_text("#constant(t,1). #constant(t,2). " + declaration)
    template = task.language_bias_head[0] if head else task.language_bias_body[0].literal
    assert template.arguments is template.arguments
    original = tuple(map(str, template.arguments))
    variants = tuple(template.concretizations(task.constants))
    assert tuple(map(str, template.arguments)) == original
    assert tuple(map(str, variants[0].arguments)) != tuple(map(str, variants[-1].arguments))
    assert all(variant.arguments is variant.arguments for variant in variants)


def test_comment_filtering_preserves_explicit_program_nodes_and_locations():
    program = asp.parse_program("% comment\n#program base.\np. %* @dummy() *%\n#show p/0.")
    assert tuple(node.ast_type for node in program) == (ast.ASTType.Program, ast.ASTType.Rule, ast.ASTType.ShowSignature)
    assert program[1].location.begin.line == 3
