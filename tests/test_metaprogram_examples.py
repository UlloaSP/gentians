from pathlib import Path

import clingo
import pytest


EXAMPLES = Path(__file__).resolve().parents[1] / "docs/metaprogram/examples"


def solve_example(name, *arguments):
    control = clingo.Control(["0", *arguments])
    control.load(str(EXAMPLES / f"{name}.lp"))
    control.ground([("base", [])])
    models = []
    with control.solve(yield_=True) as handle:
        for model in handle:
            models.append({str(atom) for atom in model.symbols(shown=True)})
    return models


def test_flow_example_produces_head_output_from_ready_body():
    assert solve_example("flow") == [{
        "ready_literal(0)", "flow_bound(0)", "flow_bound(1)",
        "flow_produced(0)", "flow_produced(1)",
    }]


def test_arithmetic_example_derives_positive_result_and_operand_order():
    models = solve_example("arithmetic")
    assert len(models) == 1
    assert {"addition(0,0,1,2)", "positive_value(2)",
            "inferred_lt(0,2)", "inferred_lt(1,2)"} <= models[0]


def test_aggregate_example_exposes_condition_local_positions():
    assert solve_example("aggregate") == [{
        "aggregate_tuple_binding(0,0,0)", "aggregate_tuple_binding(0,1,1)",
        "aggregate_condition_binding(0,0,0,0)",
        "aggregate_condition_binding(0,0,1,1)",
        "aggregate_result_var(0,2)", "count_condition_orderable(0)",
    }]


@pytest.mark.parametrize(("name", "override"), [
    ("flow", "source=2"),
    ("arithmetic", "reverse=1"),
    ("aggregate", "swap=1"),
])
def test_examples_reject_unbound_contradictory_or_symmetric_variants(name, override):
    assert solve_example(name, "-c", override) == []


def test_role_views_use_declared_positions_instead_of_storage_offsets():
    root = EXAMPLES.parents[2] / "gentians/clauses/metaprogram/representation"
    control = clingo.Control(["0", "--warn=none"])
    control.load(str(root / "arithmetic.lp"))
    control.load(str(root / "aggregates.lp"))
    control.add("base", [], """
selected(body,0,0). add_mode(0).
mode_arithmetic_operand(0,left,8). mode_arithmetic_operand(0,right,3).
mode_arithmetic_result(0,5).
var_at(body,0,8,10). var_at(body,0,3,11). var_at(body,0,5,12).
selected(body,1,1).
mode_aggregate_tuple_arg(1,0,7).
mode_aggregate_condition_arg(1,0,0,2).
mode_aggregate_condition_arg(1,1,0,6).
mode_aggregate_result_arg(1,4).
aggregate_condition_atom(1,0,p,1). aggregate_condition_atom(1,1,p,1).
var_at(body,1,7,20). var_at(body,1,2,21).
var_at(body,1,6,22). var_at(body,1,4,23).
#show addition/4.
#show aggregate_tuple_binding/3.
#show aggregate_condition_binding/4.
#show aggregate_result_var/2.
#show aggregate_internal_arg/2.
""")
    control.ground([("base", [])])
    with control.solve(yield_=True) as handle:
        assert [set(map(str, model.symbols(shown=True))) for model in handle] == [{
            "addition(0,10,11,12)", "aggregate_tuple_binding(1,0,20)",
            "aggregate_condition_binding(1,0,0,21)",
            "aggregate_condition_binding(1,1,0,22)",
            "aggregate_result_var(1,23)", "aggregate_internal_arg(1,2)",
            "aggregate_internal_arg(1,6)", "aggregate_internal_arg(1,7)",
        }]
