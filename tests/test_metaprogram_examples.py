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
