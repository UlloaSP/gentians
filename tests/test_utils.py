import pytest
from gentians.clauses.parser import clause_predicates, fragment_atoms


class TestUnit:
    @pytest.mark.parametrize(
        "rule, expected_heads, expected_deps, expected_body_literals",
        [
            (
                ":- blue(V1),blue(V1),e(V0,V0),green(V0).",
                frozenset(),
                frozenset({("blue", 1), ("e", 2), ("green", 1)}),
                4,
            ),
            (
                "a:- blue(V1),blue(V1),e(V0,V0),green(V0).",
                frozenset({("a", 0)}),
                frozenset({("blue", 1), ("e", 2), ("green", 1)}),
                4,
            ),
        ],
    )
    def test_clause_predicates(self, rule, expected_heads, expected_deps, expected_body_literals):
        assert clause_predicates(rule) == (
            expected_heads,
            expected_deps,
            expected_body_literals,
        )

    def test_fragment_atoms_keeps_duplicate_literals(self):
        assert fragment_atoms("blue(V1),blue(V1),e(V0,V0),green(V0)") == (
            ("blue", ("V1",), False),
            ("blue", ("V1",), False),
            ("e", ("V0", "V0"), False),
            ("green", ("V0",), False),
        )

