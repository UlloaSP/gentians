import pytest

from gentians.asp.aggregate_analysis import (
    contains_arithmetic,
    contains_comparison,
    get_aggregates,
    get_arithmetic_or_comparison_position,
)
from gentians.asp.answer_sets import (
    find_symmetric_answer_sets,
    from_as_to_list,
    from_list_to_as,
)
from gentians.asp.coverage import generate_clauses_for_coverage_interpretations
from gentians.asp.rule_analysis import get_atoms, get_duplicated_positions, get_same_atoms, is_valid_rule

class TestUnit:
    @pytest.mark.parametrize("l_in, expected_atoms", [
        ([[0,3],[1,5],[2,4]], "v0(0) v0(3) v1(1) v1(5) v2(2) v2(4)"),
        ([[0,3],[1,5]], "v0(0) v0(3) v1(1) v1(5)"),
        ([[0,3],[1,5],[2]], "v0(0) v0(3) v1(1) v1(5) v2(2)")
    ])
    def test_from_list_to_as(self, l_in, expected_atoms):
        computed = from_list_to_as(l_in)
        assert expected_atoms == computed
    
    @pytest.mark.parametrize("atoms_in, expected_list", [
        ("v0(0) v0(3) v1(1) v1(5) v2(2) v2(4)", [[0,3],[1,5],[2,4]]),
        ("v0(0) v0(3) v1(1) v1(5)", [[0,3],[1,5]]),
        ("v0(0) v0(3) v1(1) v1(5) v2(2)", [[0,3],[1,5],[2]]),
        ("v1(1) v1(7) v1(5) v0(0) v0(3) v2(2) v2(4)", [[0,3],[1,5,7],[2,4]])
    ])
    def test_from_as_to_list(self, atoms_in, expected_list):
        computed = from_as_to_list(atoms_in)
        assert expected_list == computed

    def test_find_symmetric_answer_sets(self):
        s = "v0(0) v0(3) v1(1) v1(5) v1(7) v2(2) v2(4)"
        expected = ["v0(0) v0(3) v1(1) v1(5) v1(7) v2(2) v2(4)", "v0(0) v0(3) v2(1) v2(5) v2(7) v1(2) v1(4)"]
        assert find_symmetric_answer_sets(s) == expected
    
    @pytest.mark.parametrize("rule, expected_list", [
        (":- blue(V1),blue(V1),e(V0,V0),green(V0).", ['#false', 'blue(V1)', 'blue(V1)', 'e(V0,V0)', 'green(V0)']),
        ("a:- blue(V1),blue(V1),e(V0,V0),green(V0).", ['a', 'blue(V1)', 'blue(V1)', 'e(V0,V0)', 'green(V0)'])
    ])
    def test_get_atoms(self, rule, expected_list):
        assert get_atoms(rule) == expected_list

    @pytest.mark.skip("Skipped since the result may be in different order.")
    def test_get_duplicated_positions(self):
        clause = ":- a(_____),q(_____,_____),q(_____,_____),a(_____),q(_____,_____)."
        expected = [[['0'], ['5']], [['1', '2'], ['3', '4'], ['6', '7']]]
        res = get_duplicated_positions(clause)
        obt = sorted(list(map(sorted,res)))

        assert  obt == expected
    
    @pytest.mark.skip("Skipped since the result may be in different order.")
    def test_get_same_atoms(self):
        clause = ":- a(_____),q(_____,_____),q(_____,_____),a(_____),q(_____,_____)."
        expected = (['same1(1,0).', 'same1(1,1).', 'same2(0,2,3).', 'same2(0,4,5).', 'same2(0,6,7).'], 2)
        res = get_same_atoms(clause)
        # obt_list = sorted(obt[0])
        # res = (obt_list, obt[1])
        assert res == expected
    
    @pytest.mark.skip("Deprecated")
    @pytest.mark.parametrize("interpretations, positive, expected", [
        ([['odd(1) odd(3) even(2)', 'odd(2)', 'cd(4)']], True, "cpi(0):-odd(1),odd(3),even(2).cpe(0):-odd(2).cd(4)."),
        ([['odd(1) odd(3) even(2)', 'odd(2)', 'cd(4)']], False, "cni(0):-odd(1),odd(3),even(2).cne(0):-odd(2).cd(4).")
    ])
    def test_generate_clauses_for_coverage_interpretations(self, interpretations, positive, expected):
        res = generate_clauses_for_coverage_interpretations(interpretations=interpretations, positive=positive)
        assert res.replace("\n","").replace(" ","") == expected

    def test_get_aggregates(self):
        # TODO: implement
        assert True
    
    def test_contains_arithmetic(self):
        # TODO: implement
        assert True

    def test_contains_comparison(self):
        # TODO: implement
        assert True
    
    def test_get_arithmetic_or_comparison_position(self):
        # TODO: implement
        assert True

class TestIntegration:
    @pytest.mark.parametrize("rule, is_valid", [
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
        ("a:- V = #sum{X : a(X)}.", True)
    ])
    def test_is_valid_rule(self, rule, is_valid):
        assert is_valid_rule(rule) == is_valid
