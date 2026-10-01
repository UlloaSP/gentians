import clingo
import pytest

from gentians.arguments import Arguments
from gentians.clauses import generate_clause_space
from gentians.language import parse_text


def _clauses(background: str, bias: str) -> tuple[str, ...]:
    return generate_clause_space(parse_text(f"{background}\n{bias}"), Arguments()).clauses


def _grounds(background: str, clause: str) -> bool:
    control = clingo.Control(logger=lambda _code, _message: None)
    try:
        control.add("base", [], f"{background}\n{clause}")
        control.ground([("base", [])])
    except RuntimeError:
        return False
    return True


# Each space mixes a construct whose safety or flow used to be misjudged.
SPACES = {
    "relation_any": (
        "d(1). d(2).",
        "#maxv(2).\n#maxbl(2).\n#modeh(1,h(var(numeric,input))).\n"
        "#modeb(1,d(var(numeric,output))).\n"
        "#modeb(1,var(numeric,output)=var(numeric,input)*var(numeric,any)+1).",
    ),
    "aggregate_output": (
        "p(1). p(2).",
        "#maxv(2).\n#maxbl(2).\n#modeh(1,h(var(numeric,input))).\n"
        "#modeb(1,#count{var(numeric,any):p(var(numeric,any)),"
        "var(numeric,any)<3}=var(numeric,output)).",
    ),
    "arithmetic_atom": (
        "q(1). q(2).",
        "#maxv(2).\n#maxbl(1).\n#modeh(1,a(var(numeric,input))).\n"
        "#modeb(1,q(var(numeric,any)+var(numeric,any))).\n"
        "#modeb(1,q(var(numeric,any)+1)).\n#modeb(1,q(|var(numeric,any)|)).",
    ),
}


@pytest.mark.parametrize("name", sorted(SPACES))
def test_every_generated_clause_grounds_in_clingo(name):
    background, bias = SPACES[name]
    clauses = _clauses(background, bias)

    assert clauses
    assert [clause for clause in clauses if not _grounds(background, clause)] == []


def test_relation_output_needs_safe_arguments_not_head_inputs():
    clauses = _clauses(*SPACES["relation_any"])

    assert 'h(V0) :- V0 = ((V0*V0)+1).' not in clauses
    assert 'h(V0) :- d(V0); V1 = ((V0*V1)+1).' not in clauses
    assert 'h(V1) :- d(V0); V1 = ((V0*V0)+1).' in clauses


def test_aggregate_output_cannot_ground_its_own_elements():
    clauses = _clauses(*SPACES["aggregate_output"])

    assert 'h(V0) :- V0 = #count { V0: p(V0), V0 < 3 }.' not in clauses
    assert 'h(V0) :- V0 = #count { V0: p(V1), V1 < 3 }.' not in clauses
    assert 'h(V1) :- V1 = #count { V0: p(V0), V0 < 3 }.' in clauses


def test_only_invertible_arithmetic_in_an_atom_grounds_its_variable():
    clauses = _clauses(*SPACES["arithmetic_atom"])

    assert 'a(V0) :- q((V0+1)).' in clauses
    assert not any("V0+V0" in clause or "|" in clause for clause in clauses)


def test_invented_predicates_respect_layers_inside_set_aggregates():
    clauses = _clauses(
        "d(1). d(2).",
        "#maxv(2).\n#maxbl(2).\n#modeh(1,target(var(t,input))).\n"
        "#modeb(1,d(var(t,output))).\n"
        "#invent(2,ha(var(t,input))).\n#invent(2,hb(var(t,input))).\n"
        "#modeb(1,1<={hb(var(t,any)):d(var(t,any))}).\n"
        "#modeb(1,1<={target(var(t,any)):d(var(t,any))}).",
    )

    assert not any(clause.startswith(":-") and "hb(" in clause for clause in clauses)
    assert not any(
        clause.startswith("ha(") and ("{hb(" in clause or "{target(" in clause)
        for clause in clauses
    )
    assert 'target(V0) :- d(V0); 1 <= { hb(V1): d(V1) }.' in clauses


def test_negated_head_does_not_make_its_atom_learnable():
    clauses = _clauses(
        "e(1). e(2).",
        "#maxv(1).\n#maxbl(1).\n#modeh(1,target(var(node,input))).\n"
        "#modeh(1,not e(var(node,input))).\n#modeb(1,e(var(node,output))).\n"
        "#invent(1,ha(var(node,input))).",
    )

    assert "ha(V0) :- e(V0)." in clauses


def test_conditional_and_aggregate_locals_bind_no_global_input():
    conditional = _clauses(
        "d(1). e(1). f(1).",
        "#maxv(1).\n#maxbl(3).\n#maxhl(0).\n"
        "#modeb(1,d(var(t,any)):e(var(t,any))).\n#modeb(1,f(var(t,input))).",
    )
    aggregate = _clauses(
        "p(1). q(1).",
        "#maxv(1).\n#maxbl(2).\n#maxhl(0).\n"
        "#modeb(1,1=#count{var(t,input):p(var(t,input))}).\n"
        "#modeb(1,1=#count{var(t,any):q(var(t,any))}).",
    )

    assert not any("f(V0)" in clause for clause in conditional)
    assert not any("p(V0)" in clause for clause in aggregate)


def test_head_input_does_not_satisfy_a_body_output():
    clauses = _clauses(
        "d(1). q(1). r(1).",
        "#maxv(1).\n#maxbl(3).\n#modeh(1,h(var(t,input))).\n"
        "#modeb(1,d(var(t,any))).\n#modeb(1,q(var(t,output)):r(var(t,any))).",
    )

    assert 'h(V0) :- d(V0); q(V0): r(V0).' not in clauses
    assert "h(V0) :- d(V0)." in clauses
