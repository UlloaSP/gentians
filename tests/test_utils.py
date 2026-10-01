import pytest
from clingo import ast

from gentians.clauses.analysis.ast_inspection import _node_atoms
from gentians.language.asp import clause_predicates, parse_rule


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
            ("p(a;b,c).", frozenset({("p", 1), ("p", 2)}), frozenset(), 0),
            ("-p(a;b).", frozenset({("-p", 1)}), frozenset(), 0),
            ("p :- q(1;2).", frozenset({("p", 0)}), frozenset({("q", 1)}), 1),
            ("not p :- q.", frozenset(), frozenset({("p", 0), ("q", 0)}), 1),
            ("sel(X):node(X).", frozenset({("sel", 1)}), frozenset({("node", 1)}), 0),
            (
                "1{not b;s(X):n(X)}1.",
                frozenset({("s", 1)}),
                frozenset({("b", 0), ("n", 1)}),
                0,
            ),
            (
                "#count{X:s(X):n(X),not b(X)}=1.",
                frozenset({("s", 1)}),
                frozenset({("b", 1), ("n", 1)}),
                0,
            ),
        ],
    )
    def test_clause_predicates(self, rule, expected_heads, expected_deps, expected_body_literals):
        assert clause_predicates(parse_rule(rule)) == (
            expected_heads,
            expected_deps,
            expected_body_literals,
        )

    def test_ast_atom_inspection_keeps_duplicate_literals(self):
        statement = parse_rule(":- blue(V1),blue(V1),e(V0,V0),green(V0).")
        assert tuple((name, tuple(map(str, arguments)), sign != ast.Sign.NoSign)
                     for name, arguments, sign in _node_atoms(statement)) == (
            ("blue", ("V1",), False),
            ("blue", ("V1",), False),
            ("e", ("V0", "V0"), False),
            ("green", ("V0",), False),
        )


@pytest.mark.parametrize("text", ["hello world", "a,b", "a ) { [", 'an escaped "quote"'])
def test_ast_atom_inspection_preserves_string_values(text):
    import clingo

    statement = parse_rule(f"p({clingo.String(text)}).")
    name, arguments, sign = _node_atoms(statement)[0]

    assert name == "p"
    assert sign == ast.Sign.NoSign
    assert arguments[0].symbol.string == text

