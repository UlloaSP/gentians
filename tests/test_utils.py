import pytest
from gentians.asp.rule_analysis import (
    get_atoms,
    is_valid_rule,
)


class TestUnit:
    @pytest.mark.parametrize(
        "rule, expected_list",
        [
            (
                ":- blue(V1),blue(V1),e(V0,V0),green(V0).",
                ["#false", "blue(V1)", "blue(V1)", "e(V0,V0)", "green(V0)"],
            ),
            (
                "a:- blue(V1),blue(V1),e(V0,V0),green(V0).",
                ["a", "blue(V1)", "blue(V1)", "e(V0,V0)", "green(V0)"],
            ),
        ],
    )
    def test_get_atoms(self, rule, expected_list):
        assert get_atoms(rule) == expected_list

class TestIntegration:
    @pytest.mark.parametrize(
        "rule, is_valid",
        [
            (":- blue(V1),blue(V1),e(V0,V0),green(V0).", False),
            (":- blue(V1),blue(V0),e(V0,V1),green(V0).", True),
            (":- e(V0,V1),V0>V1.", True),
            (":- e(V0,V1),V0>V0.", False),
            (":- e(V0,V1),V0>=V0.", False),
            (":- e(V0,V1),V0>=V1.", True),
            (":- e(V0,V1),V0+V1=V2.", True),
            (":- e(V0,V1),V0+V0=V2.", True),
            (":- e(V0,V1),V0+V0=V0.", False),
            (":- e(V0,V1),V0+V0=V2.", True),
            (":- e(V0,V1),V0+V0=V2, not a(V2).", True),
            (":- e(V0,V1),V0+V0=V2, not a(V3).", False),
            ("a:- V = #sum{X : a(X)}.", True),
        ],
    )
    def test_is_valid_rule(self, rule, is_valid):
        assert is_valid_rule(rule) == is_valid
