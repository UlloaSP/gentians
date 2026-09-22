from pathlib import Path

import clingo
import pytest

from gentians.clauses import generator


@pytest.mark.parametrize(("context", "rejected", "retained"), [
    (
        "addition(0,0,1,2). numeric_domain_positive. numeric_argument_var(0..2).",
        "selected_leq(2,0).",
        "selected_leq(0,2).",
    ),
    (
        "addition(0,0,1,2). numeric_domain_positive. numeric_argument_var(0..2).",
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
