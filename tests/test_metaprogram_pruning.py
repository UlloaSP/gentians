from pathlib import Path

import clingo
import pytest

from gentians.arguments import Arguments
from gentians.clauses import generate_clause_space, generator
from gentians.language import parse_text


@pytest.mark.parametrize(("context", "rejected", "retained"), [
    (
        "addition(0,0,1,2). positive_value(0..2).",
        "selected_leq(2,0).",
        "selected_leq(0,2).",
    ),
    (
        "addition(0,0,1,2). positive_value(0..2).",
        "selected_leq(2,1).",
        "selected_leq(1,2).",
    ),
    (
        "addition(0,0,1,2). positive_value(1).",
        "selected_lt(2,0).",
        "selected_lt(0,2).",
    ),
    (
        "addition(0,0,1,2). positive_value(0).",
        "selected_lt(2,1).",
        "selected_lt(1,2).",
    ),
    (
        "selected_lt(0,1).",
        "selected_lt(1,0).",
        "selected_lt(1,2).",
    ),
], ids=["positive-left", "positive-right", "sum-left-cycle", "sum-right-cycle", "comparison-cycle"])
def test_numeric_contradictions_reject_impossible_orders(context, rejected, retained):
    root = Path(generator.__file__).with_name("metaprogram")

    def satisfiable(fragment):
        # This slice exercises inference and contradiction checks. Other pruning
        # families may reject an entailed comparison even when it is consistent.
        control = clingo.Control(["--warn=none"])
        control.load(str(root / "inference/numeric.lp"))
        control.load(str(root / "pruning/contradictions/numeric.lp"))
        control.load(str(root / "pruning/contradictions/comparisons.lp"))
        control.add("base", [], context + fragment)
        control.ground([("base", [])])
        return control.solve().satisfiable

    assert not satisfiable(rejected)
    assert satisfiable(retained)


def test_sum_below_an_operand_needs_the_other_operand_nonnegative():
    root = Path(generator.__file__).with_name("metaprogram")

    def satisfiable(context):
        control = clingo.Control(["--warn=none"])
        control.load(str(root / "inference/numeric.lp"))
        control.load(str(root / "pruning/contradictions/numeric.lp"))
        control.add("base", [], "addition(0,0,1,2). selected_lt(2,0). " + context)
        control.ground([("base", [])])
        return control.solve().satisfiable

    # R = L + Rt with R < L only needs Rt < 0; the sign of L and R is irrelevant.
    assert satisfiable("positive_value(0). positive_value(2).")
    assert not satisfiable("nonnegative_value(1).")


def _clauses(text):
    return generate_clause_space(parse_text(text), Arguments()).clauses


def test_disequality_is_oriented_only_between_interchangeable_operands():
    clauses = _clauses(
        "a(1). b(2).\n#maxv(2).\n#maxbl(3).\n"
        "#modeh(1,p(var(b,input),var(a,input))).\n"
        "#modeb(1,b(var(b,output))).\n#modeb(1,a(var(a,output))).\n"
        "#modeb(1,var(a,input)!=var(b,input))."
    )

    assert "p(V0,V1) :- b(V0),a(V1),V1!=V0." in clauses


def test_strict_replacement_needs_a_strict_mode_for_the_same_type():
    base = (
        "p(1,2).\n#maxv(2).\n#maxbl(3).\n#modeh(1,h(var(t,input))).\n"
        "#modeb(1,p(var(t,output),var(t,output))).\n"
        "#modeb(1,var(t,input)<=var(t,input)).\n"
        "#modeb(1,var(t,input)!=var(t,input)).\n"
    )
    other_type = _clauses(base + "#modeb(1,var(u,input)<var(u,input)).")
    same_type = _clauses(base + "#modeb(1,var(t,input)<var(t,input)).")

    assert "h(V0) :- p(V0,V1),V0<=V1,V0!=V1." in other_type
    assert "h(V0) :- p(V0,V1),V0<=V1,V0!=V1." not in same_type
    assert "h(V0) :- p(V0,V1),V0<V1." in same_type


def test_repeated_condition_stays_without_a_shorter_template():
    clauses = _clauses(
        "e(1,1). d(1).\n#maxv(1).\n#maxbl(3).\n#maxhl(0).\n"
        "#modeb(1,e(var(t,input),var(t,any)):d(var(t,any)),d(var(t,any)))."
    )

    assert ":- e(V0,V0):d(V0),d(V0)." in clauses


def test_non_interchangeable_addition_keeps_its_arithmetic_view():
    task = parse_text(
        "n(1).\n#maxv(3).\n#maxbl(2).\n#maxhl(0).\n"
        "#modeb(1,var(numeric,input,a)+var(numeric,input,b)=var(numeric,output))."
    )
    generator_ = generator._ClauseGenerator(task, Arguments())
    _control, _index, facts, *_ = generator_._prepare(None)
    lines = {str(fact) for fact in facts}

    assert "add_mode(0)." in lines
    assert "interchangeable_operands(0)." not in lines
