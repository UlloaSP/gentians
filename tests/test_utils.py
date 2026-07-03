import pytest
from gentians.asp.rule_analysis import get_atoms


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

