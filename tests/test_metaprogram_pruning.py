from dataclasses import replace
from pathlib import Path

import clingo
import pytest

from gentians.arguments import Arguments
from gentians.clauses import generate_clause_space, generator, mode_facts, property_facts
from gentians.clauses.analysis.properties import ClosedWorldProperties
from gentians.language import parse_text


@pytest.mark.parametrize(("left", "right", "left_vars", "right_vars", "satisfiable"), [
    ("p", "q", (0, 1), (0, 1), False),
    ("p", "q", (0, 1), (1, 0), False),
    ("p", "q", (0, 1), (0, 2), True),
    ("p", "q", (0, 1), (1, 2), True),
    ("r", "s", (0, 1), (0, 1), False),
    ("r", "s", (0, 1), (0, 2), True),
    ("r", "s", (0, 1), (1, 0), True),
    ("p", "s", (0, 1), (0, 1), True),
    ("r", "q", (0, 1), (0, 1), True),
    ("-p", "q", (0, 1), (0, 1), True),
], ids=["identity", "reverse", "partial-identity", "partial-reverse", "second-pair",
        "second-pair-mismatch", "second-pair-reverse", "unrelated-target", "unrelated-source",
        "signed-source"])
def test_tuple_mutex_projections_keep_predicate_pairs_and_complete_bindings(
    left, right, left_vars, right_vars, satisfiable,
):
    # Two pairs share the identity mapping; only p/q also has the reverse.
    # Sharing mapping descriptions must never export one pair's exclusion to
    # another pair, or confuse a partial binding match with a complete one.
    properties = replace(ClosedWorldProperties.none(), tuple_mutex=frozenset({
        (("p", 2), ("q", 2), (0, 1)),
        (("p", 2), ("q", 2), (1, 0)),
        (("r", 2), ("s", 2), (0, 1)),
    }))
    identifiers = {(name, 2): index for index, name in enumerate(("p", "q", "r", "s", "-p"))}
    facts = property_facts.compile_property_facts(properties, identifiers)
    for slot, (name, variables) in enumerate(((left, left_vars), (right, right_vars))):
        pred = identifiers[name, 2]
        facts.append(f"positive_body_literal({slot},{pred},{pred},2).")
        for argument, variable in enumerate(variables):
            facts.extend((f"arg(body,{slot},{argument}).", f"var_at(body,{slot},{argument},{variable})."))
    control = clingo.Control(["--warn=none"])
    root = Path(generator.__file__).with_name("metaprogram")
    control.load(str(root / "pruning/properties/disjoint.lp"))
    control.add("base", [], "\n".join(facts))
    control.ground([("base", [])])

    assert control.solve().satisfiable == satisfiable


@pytest.mark.parametrize(("property_name", "edges", "extra", "satisfiable"), [
    ("transitive", [(0, 1, True, (0, 1)), (1, 1, True, (1, 2)), (2, 1, True, (0, 2))], "", False),
    ("transitive", [(0, 1, True, (0, 1)), (1, 1, True, (1, 2)), (2, 1, True, (0, 2))], "flow_needed(2).", True),
    ("transitive", [(0, 1, True, (0, 1)), (1, 1, True, (1, 1))], "", True),
    ("transitive", [(0, 1, True, (0, 1)), (1, 1, True, (1, 2)), (2, 1, False, (0, 2))], "", False),
    ("transitive", [(0, 1, True, (0, 1)), (1, 1, True, (1, 2)), (2, 1, False, (2, 0))], "", True),
    ("acyclic", [(0, 1, True, (0, 1)), (1, 1, True, (1, 2)), (2, 1, True, (2, 0))], "", False),
    ("acyclic", [(0, 1, True, (0, 1)), (1, 1, True, (2, 0)), (2, 1, True, (1, 2))], "", True),
    ("acyclic", [(0, 1, True, (0, 1)), (1, 1, True, (1, 2)), (2, 1, False, (2, 0))], "", False),
    ("acyclic", [(0, 1, True, (0, 1)), (1, 1, True, (1, 2)), (2, 1, False, (0, 2))], "", True),
    ("transitive", [(0, 1, True, (0, 1)), (1, 2, True, (1, 2)), (2, 1, True, (0, 2))], "", True),
    ("transitive", [(0, 1, True, (0, 1)), (1, 1, True, (1, 2)), (2, 2, False, (0, 2))], "", True),
    ("transitive", [(0, 1, True, (None, 1)), (1, 1, True, (1, 2)), (2, 1, True, (0, 2))], "", True),
], ids=["shortcut", "needed-shortcut", "shortcut-is-path-atom", "negative-shortcut",
        "negative-other-edge", "ordered-triangle", "other-slot-order", "negative-back-edge",
        "negative-forward-edge", "different-path-predicate", "different-negative-predicate",
        "constant-source-position"])
def test_path_pruning_preserves_slot_order_flow_and_binding_conditions(
    property_name, edges, extra, satisfiable,
):
    # Predicate ids stand for signed signatures. These pinned models isolate
    # the existing constraints, including their deliberately limited slot order.
    facts = [f"{property_name}_pred(1).", extra]
    for slot, predicate, positive, variables in edges:
        polarity = "positive" if positive else "negative"
        facts.append(f"{polarity}_body_literal({slot},{slot},{predicate},2).")
        for argument, variable in enumerate(variables):
            facts.append(f"arg(body,{slot},{argument}).")
            if variable is not None:
                facts.append(f"var_at(body,{slot},{argument},{variable}).")
    control = clingo.Control(["--warn=none"])
    root = Path(generator.__file__).with_name("metaprogram")
    control.load(str(root / "representation/tuples.lp"))
    control.load(str(root / f"pruning/properties/{property_name}.lp"))
    control.add("base", [], "\n".join(facts))
    control.ground([("base", [])])

    assert control.solve().satisfiable == satisfiable


@pytest.mark.parametrize(("facts", "count", "retained"), [
    (
        "var(0..5). body_slot(0..1). mode_section(0,body). mode_section(1,body). "
        "mode_variable_arg(0,0). mode_variable_arg(0,3). mode_variable_arg(1,0..2). "
        "mode_variable_arg(2,0..1). head_form_member(0,0,2). "
        "selected(body,0,0). selected(body,1,1). selected(head,0,2).",
        876, (0, 1, 2, 3, 4, 5, 0),
    ),
    (
        "var(0..4). body_slot(0..1). mode_section(0,body). "
        "mode_variable_arg(0,0..2). mode_variable_arg(1,0..1). "
        "head_form_member(0,0,1). selected(body,1,0). selected(head,0,1).",
        52, (0, 1, 2, 3, 4),
    ),
    (
        "var(0..2). mode_variable_arg(0,0). mode_variable_arg(0,4). mode_variable_arg(1,7). "
        "head_form_member(0,0,0). head_form_member(0,1,1). "
        "selected(head,0,0). selected(head,1,1).",
        5, (0, 1, 2),
    ),
    ("body_slot(0). mode_section(0,body). selected(body,0,0).", 1, ()),
], ids=["body-before-head-and-sparse-positions", "empty-earlier-slot",
        "bodyless-compound-head", "no-variable-placeholders"])
def test_variable_domains_preserve_all_first_occurrence_assignments(facts, count, retained):
    # Canonical assignments are set partitions, with blocks numbered by their
    # first occurrence. Seven positions with at most six ids give Bell(7)-1;
    # five and three positions give Bell(5) and Bell(3). Sparse source positions
    # and unused earlier slots must not remove any of these representatives.
    root = Path(generator.__file__).with_name("metaprogram")
    control = clingo.Control(["0", "--warn=none"])
    for name in ("representation/arguments.lp", "representation/variables.lp", "symmetry/variables.lp"):
        control.load(str(root / name))
    control.add("base", [], facts)
    control.ground([("base", [])])
    assignments = set()

    def collect(model):
        positions = sorted(
            (symbol.arguments[0].name, *(argument.number for argument in symbol.arguments[1:]))
            for symbol in model.symbols(shown=True) if symbol.match("var_at", 4)
        )
        assignments.add(tuple(variable for _section, _slot, _argument, variable in positions))

    assert control.solve(on_model=collect).exhausted
    assert len(assignments) == count
    assert retained in assignments


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


THETA_COMPARISON_TASK = (
    "r(1,2). r(1,3). s(1,2).\n#maxv(4).\n#maxbl(4).\n#maxhl(0).\n"
    "#modeb(2,r(var(t,output),var(t,output))).\n"
    "#modeb(1,s(var(t,output),var(t,output))).\n"
    "#modeb(1,var(t,input)!=var(t,input))."
)


def test_theta_reduction_moves_only_variables_outside_fixed_literals():
    clauses = _clauses(THETA_COMPARISON_TASK)

    # V2 occurs only in r(V0,V2): V2 -> V1 folds it onto r(V0,V1).
    assert '#false :- r(V0,V1); r(V0,V2); s(V0,V3); V1 != V3.' not in clauses
    # The comparison fixes V2, so no substitution can fold r(V0,V2).
    assert '#false :- r(V0,V1); r(V0,V2); V1 != V2.' in clauses
    assert '#false :- r(V0,V1); r(V1,V2); s(V0,V3); V1 != V3.' in clauses


def _theta_space(text, limit, monkeypatch):
    monkeypatch.setattr(mode_facts, "THETA_OFFSET_LIMIT", limit)
    task = parse_text(text)
    clause_generator = generator._ClauseGenerator(task, Arguments())
    control, _index, facts, *_ = clause_generator._prepare(None)
    control.solve()
    clauses = generate_clause_space(task, Arguments()).clauses
    return clauses, int(control.statistics["problem"]["lp"]["disjunctions"]), facts


@pytest.mark.parametrize("text", [
    THETA_COMPARISON_TASK,
    "edge(a,b). edge(a,c).\n#maxv(3).\n#maxbl(3).\n#maxhl(1).\n"
    "#modeh(1,target(var(node,any))).\n#modeb(3,edge(var(node,any),var(node,any))).",
])
def test_theta_offsets_match_saturation_without_disjunction(text, monkeypatch):
    offsets, offset_disjunctions, offset_facts = _theta_space(text, 1024, monkeypatch)
    saturated, saturated_disjunctions, saturated_facts = _theta_space(text, 0, monkeypatch)

    assert offsets == saturated
    assert any(str(fact).startswith("theta_sigma(") for fact in offset_facts)
    assert offset_disjunctions == 0
    assert any(str(fact).startswith("theta_saturated_section(") for fact in saturated_facts)
    assert saturated_disjunctions > 0


def test_disequality_is_oriented_only_between_interchangeable_operands():
    clauses = _clauses(
        "a(1). b(2).\n#maxv(2).\n#maxbl(3).\n"
        "#modeh(1,p(var(b,input),var(a,input))).\n"
        "#modeb(1,b(var(b,output))).\n#modeb(1,a(var(a,output))).\n"
        "#modeb(1,var(a,input)!=var(b,input))."
    )

    assert 'p(V0,V1) :- b(V0); a(V1); V1 != V0.' in clauses


def test_strict_replacement_needs_a_strict_mode_for_the_same_type():
    base = (
        "p(1,2).\n#maxv(2).\n#maxbl(3).\n#modeh(1,h(var(t,input))).\n"
        "#modeb(1,p(var(t,output),var(t,output))).\n"
        "#modeb(1,var(t,input)<=var(t,input)).\n"
        "#modeb(1,var(t,input)!=var(t,input)).\n"
    )
    other_type = _clauses(base + "#modeb(1,var(u,input)<var(u,input)).")
    same_type = _clauses(base + "#modeb(1,var(t,input)<var(t,input)).")

    assert 'h(V0) :- p(V0,V1); V0 <= V1; V0 != V1.' in other_type
    assert 'h(V0) :- p(V0,V1); V0 <= V1; V0 != V1.' not in same_type
    assert 'h(V0) :- p(V0,V1); V0 < V1.' in same_type


def test_repeated_condition_stays_without_a_shorter_template():
    clauses = _clauses(
        "e(1,1). d(1).\n#maxv(1).\n#maxbl(3).\n#maxhl(0).\n"
        "#modeb(1,e(var(t,input),var(t,any)):d(var(t,any)),d(var(t,any)))."
    )

    assert '#false :- e(V0,V0): d(V0), d(V0).' in clauses


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


def test_subsumption_needs_a_shared_variable_at_the_same_argument():
    clauses = _clauses(
        "p(1,2,3). p(2,2,1). p(3,1,1). p(1,1,1). p(2,3,2). p(3,3,3). p(1,3,2). p(2,1,3).\n"
        "#maxv(3).\n#maxbl(2).\n#maxhl(0).\n"
        "#modeb(2,p(var(t,any),var(t,any),var(t,any)))."
    )

    # V1 is argument 2 of the first atom and argument 0 of the second, so no
    # substitution maps p(V1,V0,V2) onto p(V0,V0,V1): the second atom is a join.
    assert '#false :- p(V0,V0,V1); p(V1,V0,V2).' in clauses
    # V2 occurs only in the second atom: V2 -> V0 maps it onto the first.
    assert '#false :- p(V0,V0,V1); p(V0,V2,V1).' not in clauses


def test_subsumption_prunes_across_modes_of_one_predicate():
    # Each mode occurs once, so theta reduction moves neither atom.
    clauses = _clauses(
        "p(1,2). p(2,2). p(3,1). p(1,1). p(2,3).\n#maxv(3).\n#maxbl(2).\n"
        "#modeh(1,h(var(t,any))).\n"
        "#modeb(1,p(var(t,any,a),var(t,any,b))).\n"
        "#modeb(1,p(var(t,any),var(t,any)))."
    )

    # V1 -> V0 maps p(V0,V1) onto p(V0,V0) unless the head needs V1.
    assert 'h(V0) :- p(V0,V1); p(V0,V0).' not in clauses
    assert 'h(V1) :- p(V0,V1); p(V0,V0).' in clauses
    assert "h(V0) :- p(V0,V0)." in clauses


TRANSITIVE_TASK = (
    "p(1,2). p(2,2). p(3,4). p(4,5). p(3,5).\n#maxv(3).\n#maxbl(3).\n"
    "#modeh(1,h(var(n,any))).\n#modeb(3,p(var(n,any),var(n,any)))."
)


def test_transitive_shortcut_is_pruned_wherever_slot_order_puts_it():
    clauses = _clauses(TRANSITIVE_TASK)

    # Tuple order puts the shortcut p(V0,V2) between the two path atoms.
    assert '#false :- p(V0,V1); p(V0,V2); p(V1,V2).' not in clauses
    assert 'h(V0) :- p(V0,V1); p(V0,V2); p(V1,V2).' not in clauses
    assert '#false :- p(V0,V1); p(V1,V2).' in clauses


def test_transitive_shortcut_must_be_a_third_atom():
    clauses = _clauses(TRANSITIVE_TASK)

    # p(V0,V1),p(V1,V1) is a path whose "shortcut" is its own first atom.
    assert 'h(V0) :- p(V0,V1); p(V1,V1).' in clauses
    assert 'h(V1) :- p(V0,V0); p(V0,V1); p(V1,V2).' in clauses


def test_symmetric_orientation_needs_interchangeable_arguments():
    facts = "friend(1,2). friend(2,1). friend(3,4). friend(4,3). q(1). q(3). r(2). r(4). r(5).\n"
    directed = _clauses(
        facts + "#maxv(2).\n#maxbl(3).\n#maxhl(0).\n"
        "#modeb(1,q(var(t,input))).\n#modeb(1,r(var(t,any))).\n"
        "#modeb(1,friend(var(t,input),var(t,output)))."
    )
    undirected = _clauses(
        facts + "#maxv(2).\n#maxbl(3).\n#maxhl(0).\n"
        "#modeb(2,r(var(t,any))).\n#modeb(1,friend(var(t,any),var(t,any)))."
    )

    # r binds V1 and friend outputs V0 for q. The swapped atom needs V0 bound
    # first, so it is not in the language and cannot stand in for this one.
    assert '#false :- q(V0); r(V1); friend(V1,V0).' in directed
    assert '#false :- q(V0); r(V1); friend(V0,V1).' not in directed
    # Arguments that may swap keep a single orientation.
    assert '#false :- r(V0); r(V1); friend(V0,V1).' in undirected
    assert '#false :- r(V0); r(V1); friend(V1,V0).' not in undirected


def test_arg_equal_shares_a_variable_only_where_the_template_allows():
    facts = "same(1,1). same(2,2). a(1). b(2).\n#maxv(2).\n#maxbl(2).\n#maxhl(0).\n"
    typed = _clauses(
        facts + "#modeb(1,same(var(a,any),var(b,any))).\n#modeb(1,a(var(a,any)))."
    )
    labelled = _clauses(
        facts + "#modeb(1,same(var(a,any,x),var(a,any,y))).\n#modeb(1,a(var(a,any)))."
    )
    shareable = _clauses(
        facts + "#modeb(1,same(var(a,any),var(a,any))).\n#modeb(1,a(var(a,any)))."
    )

    # Different types or labels forbid same(V0,V0); two ids must stay legal.
    assert '#false :- same(V0,V1); a(V0).' in typed
    assert '#false :- same(V0,V1); a(V0).' in labelled
    assert '#false :- same(V0,V0).' in shareable
    assert '#false :- same(V0,V1).' not in shareable


DIRECTED_FILTER_TASK = (
    "node(1). node(2). node(3). red(1). red(3). big(3). big(2).\n"
    "#maxv(1).\n#maxbl(3).\n#modeh(1,h(var(t,{direction}))).\n"
    "#modeb(1,node(var(t,{generator}))).\n"
    "#modeb(1,red(var(t,{filter}))).\n#modeb(1,big(var(t,{filter})))."
)


def test_redundant_atom_stays_when_directed_flow_needs_it():
    clauses = _clauses(
        DIRECTED_FILTER_TASK.format(direction="output", generator="output", filter="input")
    )

    # red implies node, but node(V0) is the only producer of the input of red:
    # without it no clause could say that h is what is red.
    assert 'h(V0) :- node(V0); red(V0).' in clauses
    assert "h(V0) :- red(V0)." not in clauses
    assert 'h(V0) :- node(V0); red(V0); big(V0).' in clauses


def test_redundant_atom_is_pruned_when_flow_does_not_need_it():
    clauses = _clauses(
        DIRECTED_FILTER_TASK.format(direction="any", generator="any", filter="any")
    )

    assert "h(V0) :- red(V0)." in clauses
    assert 'h(V0) :- node(V0); red(V0).' not in clauses


def test_count_orders_only_arguments_the_template_lets_swap():
    facts = "assigned(red,1). assigned(blue,2). assigned(red,3). r(1). r(2).\n"
    limits = "#maxv(4).\n#maxbl(2).\n#maxhl(0).\n#modeb(1,r(var(numeric,any))).\n"
    typed = _clauses(
        facts + limits
        + "#modeb(1,#count{var(node,any),var(colour,any):"
        "assigned(var(colour,any),var(node,any))}=var(numeric,output))."
    )
    untyped = _clauses(
        facts + limits
        + "#modeb(1,#count{var(t,any),var(t,any):"
        "assigned(var(t,any),var(t,any))}=var(numeric,output))."
    )

    # The types fix which variable each position holds: no other spelling exists.
    assert '#false :- r(V0); V0 = #count { V1,V2: assigned(V2,V1) }.' in typed
    assert '#false :- r(V0); V0 = #count { V1,V2: assigned(V1,V2) }.' in untyped
    assert '#false :- r(V0); V0 = #count { V1,V2: assigned(V2,V1) }.' not in untyped


def test_conditions_of_different_types_do_not_trade_places():
    clauses = _clauses(
        "na(1). nb(2). q(1). q(2). e(1).\n#maxv(2).\n#maxbl(4).\n#maxhl(0).\n"
        "#modeb(1,nb(var(b,any))).\n#modeb(1,na(var(a,any))).\n"
        "#modeb(1,e(var(a,any)):q(var(a,any)),q(var(b,any)))."
    )

    # V0 has type b, so it can only fill the second condition.
    assert '#false :- nb(V0); e(V1): q(V1), q(V0).' in clauses
