import copy
from pathlib import Path
import random
import re

import clingo
import pytest
from benchmarks.catalog import CASES
from gentians.arguments import Arguments
from gentians.asp.normal_coverage_solver import NormalCoverageSolver
from gentians import timing
from gentians.rule_generation import hypothesis_space
from gentians.rule_generation.parser import extract_name_arity, fragment_atoms, parse_atom
from gentians.rule_generation.reader import read_program
from gentians.rule_generation.hypothesis_space import (
    HypothesisSpaceGenerator,
    _hypothesis_space_args,
)
from gentians.rule_generation.hypothesis_capabilities import HypothesisCapabilities
from gentians.rule_generation.hypothesis_mode import HypothesisMode
from gentians.rule_generation.aggregate_declaration import AggregateDeclaration
from gentians.rule_generation.example import Example
from gentians.rule_generation.mode_declaration import ModeDeclaration
from gentians.rule_generation.operator_declaration import OperatorDeclaration
from gentians.rule_generation.program import Program
from gentians.rule_generation.rule_space import RuleSpace


def test_valid_aggregate_specs_skips_predicate_scan_without_aggregates(monkeypatch):
    def fail_if_called(program):
        raise AssertionError("predicate scan should not run without aggregate specs")

    monkeypatch.setattr(hypothesis_space, "_available_predicates", fail_if_called)

    assert hypothesis_space._valid_aggregate_specs(Program(["p(1)."], [], [], [], [])) == []


def test_hypothesis_generator_computes_valid_aggregate_specs_once(monkeypatch):
    calls = 0

    def aggregate_specs(program, fragments):
        nonlocal calls
        calls += 1
        return [AggregateDeclaration(1, "sum", (("p", 1),), False)]

    monkeypatch.setattr(hypothesis_space, "_valid_aggregate_specs", aggregate_specs)

    hypothesis_space.HypothesisSpaceGenerator(
        Program(
            ["p(1)."],
            [],
            [],
            [ModeDeclaration(("1", "target", "1"), True)],
            [ModeDeclaration(("1", "p", "1", "positive"), False)],
            [AggregateDeclaration(1, "sum", (("p", 1),), False)],
        ),
        Arguments(),
    )

    assert calls == 1


def test_facts_do_not_emit_redundant_control_flags():
    facts = hypothesis_space._facts(
        Program([], [], [], [], []),
        Arguments(max_depth=4),
        [],
        {},
    )

    assert "max_depth(4)." in facts
    assert "max_body(4)." not in facts
    assert "constraints_allowed." not in facts
    assert "canonical_prune." not in facts
    assert "prune_arithmetic_identities." not in facts
    assert "normal_mode(0)." not in facts


def test_facts_do_not_emit_redundant_strict_comparison_mode():
    program = Program(
        [],
        [],
        [],
        [],
        [],
        [],
        [OperatorDeclaration(1, "lt")],
    )
    modes = [
        HypothesisMode(
            0,
            0,
            "body",
            "comparison",
            "",
            2,
            1,
            True,
            operator="<",
            arg_types=("numeric", "numeric"),
        )
    ]
    facts = hypothesis_space._facts(
        program,
        Arguments(),
        modes,
        {},
    )

    fact_lines = set(facts.splitlines())

    assert "less_than_comparison_mode(0)." in fact_lines
    assert "comparison_mode(0)." not in fact_lines
    assert "symmetric_comparison_mode(0)." not in fact_lines
    assert "strict_comparison_mode(0)." not in fact_lines
    assert "strict_comparison_available." not in fact_lines


def test_facts_do_not_emit_redundant_arithmetic_mode():
    modes = [
        HypothesisMode(
            0,
            0,
            "body",
            "arithmetic",
            "",
            3,
            1,
            True,
            operator="+",
            arg_types=("numeric", "numeric", "numeric"),
        )
    ]
    facts = hypothesis_space._facts(
        Program([], [], [], [], [], [], [], [OperatorDeclaration(1, "add")]),
        Arguments(),
        modes,
        {},
    )

    fact_lines = set(facts.splitlines())

    assert "add_mode(0)." in fact_lines
    assert "arithmetic_mode(0)." not in fact_lines


def test_facts_do_not_emit_derived_numeric_domain_args():
    facts = hypothesis_space._facts(
        Program([], [], [], [], []),
        Arguments(),
        [
        HypothesisMode(
                0,
                0,
                "body",
                "normal",
                "p",
                2,
                1,
                arg_types=("numeric", "any"),
            )
        ],
        {("p", 2, 0): "numeric"},
    )

    fact_lines = set(facts.splitlines())

    assert "mode_arg_type(0,0,numeric)." in fact_lines
    assert "mode_arg_type(0,1,any)." not in fact_lines
    assert "domain_numeric_arg(0,2,0)." not in fact_lines


def test_facts_emit_only_strong_positive_numeric_domain_property():
    facts = hypothesis_space._facts(
        Program(["p(1).", "p(2)."], [], [], [], []),
        Arguments(),
        [],
        {},
    )

    assert "numeric_domain_positive." in facts
    assert "numeric_domain_nonnegative." not in facts
    assert "zero_not_in_numeric_domain." not in facts


def _reset_timing_state() -> None:
    timing.reset()


def test_candidate_rule_space_runs_inside_hypothesis_space_phase(monkeypatch):
    _reset_timing_state()
    monkeypatch.setattr(timing, "_enabled", True)
    phases = []

    class FakeHypothesisSpaceGenerator:
        def __init__(self, program, args):
            pass

        def generate(self):
            phases.append(timing.current_phase())
            return RuleSpace.from_clauses(["p."])

    monkeypatch.setattr(
        hypothesis_space, "HypothesisSpaceGenerator", FakeHypothesisSpaceGenerator
    )

    clauses = hypothesis_space.build_hypothesis_space(
        Program([], [], [], [], []), Arguments()
    )

    assert phases == ["hypothesis_space"]
    assert clauses.clauses == ("p.",)
    assert "hypothesis_space" in timing._totals
    assert "total_execution.grounding" not in timing._totals
    _reset_timing_state()


def test_hypothesis_space_clingo_times_use_current_phase(monkeypatch):
    _reset_timing_state()
    monkeypatch.setattr(timing, "_enabled", True)
    program = Program(
        ["p(1)."],
        [],
        [],
        [ModeDeclaration(("1", "target", "1"), True)],
        [ModeDeclaration(("1", "p", "1", "positive"), False)],
    )

    with timing.phase("outer"):
        HypothesisSpaceGenerator(program, Arguments(max_candidate_clauses=0)).generate()

    assert "outer.grounding" in timing._totals
    assert "outer.solving" in timing._totals
    assert "hypothesis_space.solving" not in timing._totals
    _reset_timing_state()


def test_unbalanced_aggregate_variants_share_recall():
    program = Program(
        ["el(1,2).", "el(2,3)."],
        [],
        [],
        [ModeDeclaration(("1", "ok", "1"), True)],
        [],
        [AggregateDeclaration(1, "sum", (("el", 2),), True)],
    )
    clauses = HypothesisSpaceGenerator(
        program,
        Arguments(
            max_depth=6,
            max_variables=8,
            max_candidate_clauses=0,
        ),
    ).generate().clauses

    assert not any("#sum{V0:el(V0,V0)}" in clause for clause in clauses)
    assert any("#sum{V0:el(V0,V1)}" in clause for clause in clauses)
    assert not any("#sum{V0,V1:el(V0,V1)}" in clause for clause in clauses)
    assert not any(clause.count("#sum{") > 1 for clause in clauses)


def test_atom_parser_handles_nested_arguments():
    assert parse_atom("same_row((X1,Y),(X2,Y))") == (
        "same_row",
        ["(X1,Y)", "(X2,Y)"],
    )
    assert extract_name_arity("same_row((X1,Y),(X2,Y))") == (
        "same_row",
        2,
    )


def test_closed_world_extensions_ignore_compound_variable_terms():
    extensions = hypothesis_space._closed_world_extensions(
        [
            "cell((1..4,1..4)).",
            "same_row((X1,Y),(X2,Y)) :- cell((X1,Y)), cell((X2,Y)).",
        ]
    )

    assert ("cell", 1) not in extensions
    assert ("same_row", 2) not in extensions


def test_atom_parser_does_not_treat_not_prefix_as_negation():
    assert parse_atom("notable(X)") == ("notable", ["X"])
    assert parse_atom("not notable(X)") == ("notable", ["X"])


def test_hypothesis_space_args_keep_numeric_strings():
    args = Arguments(hypothesis_space={"clingo_arguments": ["0", "--project"]})

    assert _hypothesis_space_args(args) == ["0", "--project"]


def test_hypothesis_space_args_reject_string():
    args = Arguments(hypothesis_space={"clingo_arguments": "--project"})

    try:
        _hypothesis_space_args(args)
    except ValueError as exc:
        assert "clingo_arguments" in str(exc)
    else:
        raise AssertionError("string clingo_arguments should fail")


def test_star_recall_uses_max_depth():
    mode = ModeDeclaration(("*", "p", "1"), True)
    facts = hypothesis_space._facts(
        Program([], [], [], [mode], []),
        Arguments(max_depth=2),
        [
        HypothesisMode(
                0,
                0,
                "head",
                "normal",
                "p",
                1,
                mode.recall,
            )
        ],
        {},
    )

    assert "mode(head,0,0,1,2)." in facts
    assert "group_recall(0,2)." not in facts
    assert "\nrecall(" not in facts
    assert "positive_mode(0)." not in facts
    assert "normal_mode(0)." not in facts


def test_group_recall_uses_tightest_mode_recall():
    facts = hypothesis_space._facts(
        Program([], [], [], [], []),
        Arguments(max_depth=5),
        [
            HypothesisMode(0, 7, "body", "normal", "p", 1, 3),
            HypothesisMode(1, 7, "body", "normal", "q", 1, 1),
        ],
        {("p", 1): 0, ("q", 1): 1},
    )

    assert "mode(body,0,0,1,3)." in facts
    assert "mode(body,1,1,1,1)." in facts
    assert "group_recall(7,1)." not in facts
    assert "group_recall(7,3)." not in facts


def test_reader_deduplicates_equal_directives(tmp_path):
    task = tmp_path / "task.txt"
    task.write_text(
        "\n".join(
            [
                "#pos({ a(1) }, {}).",
                "#pos({ a(1) }, {}).",
                "#neg({ b(1) }, {}).",
                "#neg({ b(1) }, {}).",
                "#modeh(1, a, 1).",
                "#modeh(1, a, 1).",
                "#modeb(1, b, 1, positive).",
                "#modeb(1, b, 1, positive).",
            ]
        ),
        encoding="utf-8",
    )

    program = read_program(str(task))

    assert len(program.positive_examples) == 1
    assert len(program.negative_examples) == 1
    assert len(program.language_bias_head) == 1
    assert len(program.language_bias_body) == 1


def test_invent_replaces_head_and_body_modes(tmp_path):
    task = tmp_path / "task.txt"
    task.write_text(
        "#invent(2,helper,2).\n",
        encoding="utf-8",
    )

    program = read_program(str(task))

    assert program.invented_predicates == (("helper", 2),)
    assert [
        (mode.recall, mode.name, mode.arity)
        for mode in program.language_bias_head
    ] == [(1, "helper", 2)]
    assert [
        (mode.recall, mode.name, mode.arity, mode.positive)
        for mode in program.language_bias_body
    ] == [(2, "helper", 2, True)]


def test_invent_rejects_duplicate_explicit_modes(tmp_path):
    task = tmp_path / "task.txt"
    task.write_text(
        "#invent(2,helper,2).\n#modeh(1,helper,2).\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must not also use"):
        read_program(str(task))


def test_invent_rejects_duplicate_signature(tmp_path):
    task = tmp_path / "task.txt"
    task.write_text(
        "#invent(1,helper,2).\n#invent(2,helper,2).\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate #invent"):
        read_program(str(task))


def test_invent_rejects_observed_predicate(tmp_path):
    task = tmp_path / "task.txt"
    task.write_text(
        "helper(a).\n#invent(1,helper,1).\n",
        encoding="utf-8",
    )
    program = read_program(str(task))

    with pytest.raises(ValueError, match="must not be observed"):
        HypothesisSpaceGenerator(program, Arguments()).generate()


def test_invented_predicates_are_stratified_and_excluded_from_constraints(tmp_path):
    task = tmp_path / "task.txt"
    task.write_text(
        "\n".join(
            [
                "base(a).",
                "#pos({target(a)},{}).",
                "#modeh(1,target,1).",
                "#modeb(1,base,1,positive).",
                "#modeb(1,target,1,positive).",
                "#invent(1,early,1).",
                "#invent(1,late,1).",
            ]
        ),
        encoding="utf-8",
    )
    program = read_program(str(task))

    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=3, max_variables=1)
    ).generate().clauses

    assert "late(V0) :- early(V0)." in clauses
    assert "early(V0) :- late(V0)." not in clauses
    assert "early(V0) :- early(V0)." not in clauses
    assert "early(V0) :- target(V0)." not in clauses
    assert "late(V0) :- target(V0)." not in clauses
    assert not any(
        clause.startswith(":-") and ("early(" in clause or "late(" in clause)
        for clause in clauses
    )


def test_invented_definition_cannot_call_target_through_aggregate(tmp_path):
    task = tmp_path / "task.txt"
    task.write_text(
        "\n".join(
            [
                "target(a).",
                "#modeh(1,target,1).",
                "#modeagg(1,count(target/1),balanced).",
                "#invent(1,helper,1).",
            ]
        ),
        encoding="utf-8",
    )
    program = read_program(str(task))

    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=3, max_variables=2)
    ).generate().clauses

    assert not any(
        clause.startswith("helper(") and ":target(" in clause
        for clause in clauses
    )


def test_hypothesis_space_prunes_arg_distinct_modes_before_rendering():
    program = Program(
        ["edge(1,2)."],
        [],
        [],
        [ModeDeclaration(("1", "target", "2"), True)],
        [ModeDeclaration(("1", "edge", "2", "positive"), False)],
    )
    clauses = HypothesisSpaceGenerator(
        program,
        Arguments(max_depth=2),
    ).generate().clauses

    assert not any("edge(V0,V0)" in clause for clause in clauses)
    assert "target(V0,V1) :- edge(V0,V1)." in clauses


def test_arg_distinct_still_prunes_body_self_pair_without_irreflexive_property():
    program = Program(
        ["p(a,b).", "p(b,a).", "guard(a).", "guard(b)."],
        [],
        [],
        [],
        [
            ModeDeclaration(("2", "p", "2", "positive"), False),
            ModeDeclaration(("2", "guard", "1", "positive"), False),
        ],
    )
    clauses = HypothesisSpaceGenerator(
        program,
        Arguments(max_depth=2, max_variables=2),
    ).generate().clauses

    assert not any("p(V0,V0)" in clause or "p(V1,V1)" in clause for clause in clauses)


def test_auto_body_bias_does_not_enable_recursion():
    program = Program(["p(1,2)."], [], [], [], [])
    program.complete_language_bias()

    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=2, max_variables=2)
    ).generate().clauses

    assert not any(clause.startswith("p(") and " :- p(" in clause for clause in clauses)


def test_explicit_body_bias_enables_recursion():
    program = Program(
        ["p(1,2)."],
        [],
        [],
        [ModeDeclaration(("1", "p", "2"), True)],
        [ModeDeclaration(("1", "p", "2", "positive"), False)],
    )

    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=2, max_variables=2)
    ).generate().clauses

    assert "p(V1,V0) :- p(V0,V1)." in clauses


def test_hypothesis_space_prunes_unobserved_body_modes():
    program = Program(
        ["base(a)."],
        [Example(("target(a)", ""), True)],
        [],
        [ModeDeclaration(("1", "target", "1"), True)],
        [
            ModeDeclaration(("1", "base", "1", "positive"), False),
            ModeDeclaration(("1", "ghost", "1", "positive"), False),
            ModeDeclaration(("1", "ghost", "1", "negative"), False),
        ],
    )

    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=3, max_variables=1)
    ).generate().clauses

    assert "target(V0) :- base(V0)." in clauses
    assert not any("ghost(" in clause for clause in clauses)


def test_hypothesis_space_prunes_reversed_symmetric_comparisons_before_rendering():
    program = Program(
        ["p(1).", "p(2)."],
        [],
        [],
        [],
        [ModeDeclaration(("2", "p", "1", "positive"), False)],
        [],
        [OperatorDeclaration(2, "neq")],
    )
    clauses = HypothesisSpaceGenerator(
        program,
        Arguments(
            max_depth=4,
            max_variables=2,
        ),
    ).generate().clauses

    assert not any("V0!=V1,V1!=V0" in clause for clause in clauses)
    assert any("V0!=V1" in clause for clause in clauses)


def test_hypothesis_space_prunes_comparison_redundancy_before_rendering():
    program = Program(
        ["p(1).", "p(2)."],
        [],
        [],
        [],
        [ModeDeclaration(("2", "p", "1", "positive"), False)],
        [],
        [OperatorDeclaration(1, "lt"), OperatorDeclaration(1, "leq"), OperatorDeclaration(1, "neq")],
    )
    clauses = HypothesisSpaceGenerator(
        program,
        Arguments(max_depth=4, max_variables=2),
    ).generate().clauses

    assert not any("V0<V1,V0!=V1" in clause for clause in clauses)
    assert not any("V0<V1,V0<=V1" in clause for clause in clauses)
    assert not any("V0<=V1,V1<=V0" in clause for clause in clauses)


def test_hypothesis_space_does_not_generate_equality_comparison():
    program = Program(
        ["p(1)."],
        [],
        [],
        [ModeDeclaration(("1", "target", "1"), True)],
        [ModeDeclaration(("1", "p", "1", "positive"), False)],
        [],
        [OperatorDeclaration(1, "eq")],
    )
    clauses = HypothesisSpaceGenerator(
        program,
        Arguments(max_depth=3, max_variables=2),
    ).generate().clauses

    assert clauses
    assert not any("==" in clause for clause in clauses)
    assert "target(V0) :- p(V0)." in clauses


def test_hypothesis_space_prunes_leq_neq_when_strict_comparison_exists():
    program = Program(
        ["p(1).", "p(2)."],
        [],
        [],
        [],
        [ModeDeclaration(("2", "p", "1", "positive"), False)],
        [],
        [
            OperatorDeclaration(1, "lt"),
            OperatorDeclaration(1, "leq"),
            OperatorDeclaration(1, "neq"),
        ],
    )
    clauses = HypothesisSpaceGenerator(
        program,
        Arguments(max_depth=4, max_variables=2),
    ).generate().clauses

    assert not any(
        "V0<=V1" in clause and "V0!=V1" in clause for clause in clauses
    )


def test_hypothesis_space_prunes_transitive_comparison_redundancy():
    program = Program(
        ["p(1).", "p(2).", "p(3)."],
        [],
        [],
        [],
        [ModeDeclaration(("3", "p", "1", "positive"), False)],
        [],
        [OperatorDeclaration(3, "lt"), OperatorDeclaration(3, "neq")],
    )
    clauses = HypothesisSpaceGenerator(
        program,
        Arguments(max_depth=6, max_variables=3),
    ).generate().clauses

    assert not any(
        "V0<V1" in clause and "V1<V2" in clause and "V0<V2" in clause
        for clause in clauses
    )
    assert not any(
        "V0<V1" in clause and "V1<V2" in clause and "V0!=V2" in clause
        for clause in clauses
    )


def test_hypothesis_space_prunes_duplicate_arithmetic_inputs_before_rendering():
    program = Program(
        ["q(1,2)."],
        [],
        [],
        [ModeDeclaration(("1", "target", "2"), True)],
        [ModeDeclaration(("1", "q", "2", "positive"), False)],
        [],
        [],
        [OperatorDeclaration(2, "add")],
    )
    clauses = HypothesisSpaceGenerator(
        program,
        Arguments(max_depth=4, max_variables=4),
    ).generate().clauses

    assert not any(
        "V0+V1=V2" in clause and "V0+V1=V3" in clause for clause in clauses
    )


def test_positive_domain_prunes_impossible_mul_and_div_comparisons():
    program = Program(
        ["q(1,1,1).", "q(2,2,2).", "q(3,3,3)."],
        [],
        [],
        [],
        [ModeDeclaration(("1", "q", "3", "positive"), False)],
        [],
        [OperatorDeclaration(1, "lt")],
        [OperatorDeclaration(1, "mul"), OperatorDeclaration(1, "div")],
    )
    clauses = HypothesisSpaceGenerator(
        program,
        Arguments(max_depth=3, max_variables=3),
    ).generate().clauses

    assert not any(
        "V0*V1=V2" in clause and "V2<V0" in clause for clause in clauses
    )
    assert not any(
        "V0*V1=V2" in clause and "V2<V1" in clause for clause in clauses
    )
    assert not any(
        "V0/V1=V2" in clause and "V0<V2" in clause for clause in clauses
    )


def test_hypothesis_space_prunes_duplicate_aggregate_inputs_before_rendering():
    program = Program(
        ["el(1).", "el(2)."],
        [],
        [],
        [ModeDeclaration(("1", "target", "2"), True)],
        [],
        [AggregateDeclaration(2, "sum", (("el", 1),), False)],
    )
    clauses = HypothesisSpaceGenerator(
        program,
        Arguments(max_depth=3, max_variables=4),
    ).generate().clauses

    assert not any(
        "#sum{V0:el(V0)}=V1" in clause and "#sum{V0:el(V0)}=V2" in clause
        for clause in clauses
    )


def test_count_aggregate_tuple_variables_are_canonicalized():
    program = Program(
        ["edge(a,b).", "edge(b,a)."],
        [],
        [],
        [ModeDeclaration(("1", "target", "1"), True)],
        [],
        [AggregateDeclaration(1, "count", (("edge", 2),), False)],
    )
    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=2, max_variables=4)
    ).generate().clauses

    assert clauses
    assert not any(
        int(left) > int(right)
        for clause in clauses
        for left, right in re.findall(r"#count\{V(\d+),V(\d+):", clause)
    )


def test_hypothesis_space_prunes_arithmetic_identities_before_cap():
    args = copy.deepcopy(CASES["4queens"])
    args.max_candidate_clauses = 10000
    clauses = HypothesisSpaceGenerator(read_program(args.filename), args).generate().clauses

    assert len(clauses) < args.max_candidate_clauses
    assert not any("V0+V1=V2,V2-V0=V1" in clause for clause in clauses)


def test_canonicalization_prevents_reversed_add_operands_by_default():
    program_without_zero = Program(
        ["#const n = 2.", "number(1..n).", "q(1,1)."],
        [],
        [],
        [],
        [ModeDeclaration(("1", "q", "2", "positive"), False)],
        [],
        [],
        [OperatorDeclaration(1, "add")],
    )
    clauses = HypothesisSpaceGenerator(
        program_without_zero,
        Arguments(
            max_depth=4,
            max_variables=3,
        ),
    ).generate().clauses

    assert clauses
    assert not any(
        left > right
        for clause in clauses
        for left, right in re.findall(r"V(\d+)\+V(\d+)=", clause)
    )


def test_domain_arithmetic_prune_removes_impossible_zero_result_by_default():
    program_without_zero = Program(
        ["#const n = 2.", "number(1..n).", "q(1,1)."],
        [],
        [],
        [],
        [ModeDeclaration(("1", "q", "2", "positive"), False)],
        [],
        [],
        [OperatorDeclaration(1, "sub")],
    )
    program_with_zero = Program(
        ["number(0..2).", "q(0,0)."],
        [],
        [],
        [],
        [ModeDeclaration(("1", "q", "2", "positive"), False)],
        [],
        [],
        [OperatorDeclaration(1, "sub")],
    )
    args = Arguments(
        max_depth=4,
        max_variables=3,
    )
    without_zero = HypothesisSpaceGenerator(program_without_zero, args).generate().clauses
    with_zero = HypothesisSpaceGenerator(program_with_zero, args).generate().clauses

    assert not any("V0-V0=V1" in clause and "q(V0,V1)" in clause for clause in without_zero)
    assert any("V0-V0=V1" in clause and "q(V0,V1)" in clause for clause in with_zero)


def test_domain_arithmetic_prune_propagates_zero_and_positive_values():
    program = Program(
        ["#const n = 2.", "number(1..n).", "q(1,1)."],
        [],
        [],
        [],
        [ModeDeclaration(("1", "q", "2", "positive"), False)],
        [],
        [OperatorDeclaration(1, "lt")],
        [OperatorDeclaration(1, "add"), OperatorDeclaration(1, "sub")],
    )
    clauses = HypothesisSpaceGenerator(
        program,
        Arguments(max_depth=4, max_variables=3),
    ).generate().clauses

    assert ":- q(V0,V0),V1<V2,V0+V0=V1,V0-V0=V2." not in clauses
    assert ":- q(V0,V0),V1+V1=V0,V0-V0=V1." not in clauses
    assert ":- q(V0,V0),V1<V0,V0-V0=V1." not in clauses
    assert ":- q(V0,V1),V1+V2=V0,V1-V1=V2." not in clauses
    assert ":- q(V0,V0),V1<V2,V0+V0=V2,V2-V1=V0." not in clauses
    assert ":- q(V0,V0),V1<V0,V0+V0=V1." not in clauses
    assert ":- q(V0,V1),V1<V2,V1-V0=V2." not in clauses
    assert ":- q(V0,V1),V1<V2,V2+V2=V1,V1-V0=V2." not in clauses
    assert ":- q(V0,V1),V1<V0,V1+V1=V0." not in clauses
    assert ":- q(V0,V1),V2<V0,V0-V1=V2." not in clauses
    assert ":- q(V0,V1),V0+V1=V2,V0-V1=V2." not in clauses
    assert ":- q(V0,V1),V0+V1=V2,V1-V0=V2." not in clauses
    assert ":- q(V0,V1),V0+V1=V2,V0-V2=V1." not in clauses
    assert ":- q(V0,V1),V0+V1=V2,V1-V2=V0." not in clauses
    assert ":- q(V0,V1),V1<V0,V1+V1=V2,V2-V1=V0." not in clauses
    assert ":- q(V0,V1),V0<V1,V0+V2=V1,V0-V1=V2." not in clauses
    assert ":- q(V0,V1),V0<V1,V1+V1=V2,V0-V1=V2." not in clauses
    assert ":- q(V0,V1),V0+V0=V2,V2-V0=V1." not in clauses
    assert ":- q(V0,V1),V1<V0,V1+V1=V2,V2-V0=V1." not in clauses
    assert ":- q(V0,V1),V0<V1,V2+V2=V1,V0-V1=V2." not in clauses
    assert ":- q(V0,V1),V1<V2,V0+V3=V2,V1-V0=V3." not in clauses
    assert ":- q(V0,V1),q(V2,V3),V1<V2,V3+V3=V1,V3-V0=V2." not in clauses


def test_closed_world_properties_prune_symmetric_predicate_orientation():
    program = Program(
        ["edge(1,2).", "edge(2,1)."],
        [],
        [],
        [ModeDeclaration(("1", "target", "2"), True)],
        [ModeDeclaration(("1", "edge", "2", "positive"), False)],
    )
    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=2, max_variables=2)
    ).generate().clauses

    assert "target(V0,V1) :- edge(V0,V1)." in clauses
    assert "target(V0,V1) :- edge(V1,V0)." not in clauses


def test_closed_world_properties_prune_implied_and_mutex_literals():
    program = Program(
        ["p(1).", "q(1).", "q(2).", "r(2)."],
        [],
        [],
        [],
        [
            ModeDeclaration(("1", "p", "1", "positive"), False),
            ModeDeclaration(("1", "q", "1", "positive"), False),
            ModeDeclaration(("1", "q", "1", "negative"), False),
            ModeDeclaration(("1", "r", "1", "positive"), False),
        ],
    )
    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=2, max_variables=1)
    ).generate().clauses

    assert ":- p(V0),q(V0)." not in clauses
    assert ":- p(V0),not q(V0)." not in clauses
    assert ":- p(V0),r(V0)." not in clauses


def test_closed_world_properties_prune_functional_dependency():
    program = Program(
        ["parent(a,b).", "parent(c,d)."],
        [],
        [],
        [],
        [ModeDeclaration(("2", "parent", "2", "positive"), False)],
    )
    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=2, max_variables=3)
    ).generate().clauses

    assert ":- parent(V0,V1),parent(V0,V2)." not in clauses


def test_closed_world_properties_prune_projection_implication():
    program = Program(
        ["edge(a,b).", "edge(b,c).", "node(a).", "node(b).", "node(c)."],
        [],
        [],
        [],
        [
            ModeDeclaration(("2", "edge", "2", "positive"), False),
            ModeDeclaration(("1", "node", "1", "positive"), False),
            ModeDeclaration(("1", "node", "1", "negative"), False),
        ],
    )
    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=2, max_variables=2)
    ).generate().clauses

    assert ":- edge(V0,V1),node(V0)." not in clauses
    assert ":- edge(V0,V1),not node(V0)." not in clauses


def test_closed_world_properties_prune_tuple_mutex_permutation():
    program = Program(
        ["father(a,b).", "mother(c,a)."],
        [],
        [],
        [],
        [
            ModeDeclaration(("2", "father", "2", "positive"), False),
            ModeDeclaration(("2", "mother", "2", "positive"), False),
        ],
    )
    fragments = hypothesis_space._closed_world_fragments(program)
    properties = hypothesis_space._closed_world_properties(
        fragments,
        hypothesis_space._predicate_arg_types(program, fragments),
        hypothesis_space._closed_body_predicates(program),
    )
    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=2, max_variables=2)
    ).generate().clauses

    assert ((("father", 2), ("mother", 2), (1, 0))) in properties.tuple_mutex
    assert ":- father(V0,V1),mother(V1,V0)." not in clauses


def test_count_aggregate_full_local_condition_is_canonical():
    program = Program(
        ["p(a,b).", "p(a,c).", "p(d,b).", "p(d,c)."],
        [],
        [],
        [ModeDeclaration(("1", "out", "1"), True)],
        [],
        [AggregateDeclaration(1, "count", (("p", 2),), True)],
    )
    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=2, max_variables=3)
    ).generate().clauses

    assert "out(V2) :- #count{V0,V1:p(V0,V1)}=V2." in clauses
    assert "out(V2) :- #count{V0,V1:p(V1,V0)}=V2." not in clauses


def test_sum_aggregate_full_local_non_weight_condition_is_canonical():
    program = Program(
        [
            "p(1,3,5).",
            "p(1,3,6).",
            "p(1,4,5).",
            "p(1,4,6).",
            "p(2,3,5).",
            "p(2,3,6).",
            "p(2,4,5).",
            "p(2,4,6).",
        ],
        [],
        [],
        [ModeDeclaration(("1", "out", "1"), True)],
        [],
        [AggregateDeclaration(1, "sum", (("p", 3),), True)],
    )
    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=2, max_variables=4)
    ).generate().clauses

    assert "out(V3) :- #sum{V0,V1,V2:p(V0,V1,V2)}=V3." in clauses
    assert "out(V3) :- #sum{V0,V1,V2:p(V0,V2,V1)}=V3." not in clauses
    assert "out(V3) :- #sum{V0,V1,V2:p(V1,V0,V2)}=V3." in clauses


def test_unbalanced_aggregate_prunes_key_determined_discriminator():
    program = Program(
        [
            "val(1).",
            "val(2).",
            "part(a).",
            "part(b).",
            "1 { p(P,V) : part(P) } 1 :- val(V).",
        ],
        [],
        [],
        [ModeDeclaration(("1", "out", "1"), True)],
        [],
        [AggregateDeclaration(1, "sum", (("p", 2),), True)],
    )
    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=2, max_variables=3)
    ).generate().clauses

    assert "out(V2) :- #sum{V0:p(V1,V0)}=V2." in clauses
    assert "out(V2) :- #sum{V0,V1:p(V1,V0)}=V2." not in clauses


def test_balanced_aggregate_keeps_key_determined_discriminator():
    program = Program(
        [
            "val(1).",
            "val(2).",
            "part(a).",
            "part(b).",
            "1 { p(P,V) : part(P) } 1 :- val(V).",
        ],
        [],
        [],
        [ModeDeclaration(("1", "out", "1"), True)],
        [],
        [AggregateDeclaration(1, "sum", (("p", 2),), False)],
    )
    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=2, max_variables=3)
    ).generate().clauses

    assert "out(V2) :- #sum{V0,V1:p(V1,V0)}=V2." in clauses


def test_closed_world_properties_prune_composite_functional_dependency():
    program = Program(
        [
            "assign(r1,c1,v1).",
            "assign(r1,c2,v2).",
            "assign(r2,c1,v3).",
        ],
        [],
        [],
        [],
        [ModeDeclaration(("2", "assign", "3", "positive"), False)],
    )
    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=2, max_variables=4)
    ).generate().clauses

    assert ":- assign(V0,V1,V2),assign(V0,V1,V3)." not in clauses


def test_closed_world_properties_prune_acyclic_body_cycle():
    program = Program(
        ["edge(a,b).", "edge(b,c).", "edge(c,d)."],
        [],
        [],
        [],
        [ModeDeclaration(("3", "edge", "2", "positive"), False)],
    )
    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=3, max_variables=3)
    ).generate().clauses

    assert ":- edge(V0,V1),edge(V1,V2),edge(V2,V0)." not in clauses


def test_closed_world_properties_prune_complement_negative_pair():
    program = Program(
        ["p(a).", "q(b).", "safe(a,a).", "safe(b,b)."],
        [],
        [],
        [],
        [
            ModeDeclaration(("1", "p", "1", "negative"), False),
            ModeDeclaration(("1", "q", "1", "negative"), False),
            ModeDeclaration(("1", "safe", "2", "positive"), False),
        ],
    )
    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=3, max_variables=2)
    ).generate().clauses

    assert ":- not p(V0),not q(V0),safe(V0,V1)." not in clauses


def test_closed_world_properties_infer_generic_atom_relations():
    properties = hypothesis_space._closed_world_properties(
        [
            "p(a).",
            "q(a).",
            "r(b).",
            "color_red(a).",
            "color_green(b).",
            "color_blue(c).",
            "rel(a,b,c).",
            "rel(d,e,f).",
            "before(a,b).",
            "before(b,c).",
            "before(a,c).",
            "le(a,a).",
            "le(a,b).",
            "le(b,b).",
        ]
    )

    assert (("p", 1), ("q", 1)) in properties.equivalent
    assert (("p", 1), 0, ("rel", 3), 1) in properties.disjoint_projection
    assert tuple(sorted((("color_red", 1), ("color_green", 1), ("color_blue", 1)))) in properties.partitions
    assert ((("rel", 3), (0,))) in properties.keys
    assert ("le", 2) not in properties.antisymmetric
    assert ("before", 2) in properties.strict_order
    assert (("before", 2), 0, 1) not in properties.arg_distinct
    assert ("le", 2) in properties.total_order
    assert ("le", 2) not in properties.reflexive


def test_closed_world_extensions_derive_simple_alias_rules():
    properties = hypothesis_space._closed_world_properties(
        [
            "edge(a,b).",
            "node(a).",
            "node(b).",
            "e(X,Y) :- edge(X,Y).",
            "e(Y,X) :- edge(X,Y).",
        ]
    )

    assert ("e", 2) in properties.symmetric
    assert (("e", 2), 0, 1) in properties.arg_distinct


def test_closed_world_extensions_derive_finite_complement_rules():
    properties = hypothesis_space._closed_world_properties(
        [
            "v(a).",
            "v(b).",
            "e(a,b).",
            "e(b,a).",
            "ne(X,Y) :- not e(X,Y), v(X), v(Y).",
        ]
    )

    assert ("ne", 2) in properties.reflexive
    assert ((("ne", 2), ("v", 1), (0,))) in properties.project_implies
    assert ((("ne", 2), ("v", 1), (1,))) in properties.project_implies


def test_closed_world_extensions_do_not_assume_unknown_negative_empty():
    extensions = hypothesis_space._closed_world_extensions(
        ["v(a).", "p(X) :- not q(X), v(X)."]
    )

    assert ("p", 1) not in extensions


def test_rule_defined_inequality_derives_arg_distinct():
    properties = hypothesis_space._closed_world_properties(
        [
            "same_block(C1,C2) :- block(C1,B), block(C2,B), C1 != C2.",
            "same_row((X1,Y),(X2,Y)) :- cell((X1,Y)), cell((X2,Y)), X1 != X2.",
            "parent_child(P,C) :- parent(P,C).",
        ]
    )

    assert (("same_block", 2), 0, 1) in properties.arg_distinct
    assert (("same_row", 2), 0, 1) in properties.arg_distinct
    assert ("same_block", 2) in properties.symmetric
    assert ("same_row", 2) in properties.symmetric
    assert ("parent_child", 2) not in properties.symmetric


def test_closed_world_properties_emit_new_property_facts():
    fragments = [
        "p(a).",
        "q(a).",
        "r(b).",
        "color_red(a).",
        "color_green(b).",
        "color_blue(c).",
        "rel(a,b,c).",
        "rel(d,e,f).",
        "other(a,b,c).",
        "le(a,a).",
        "le(a,b).",
        "le(b,b).",
    ]
    properties = hypothesis_space._closed_world_properties(
        fragments,
        closed_body_predicates={("rel", 3), ("other", 3)},
    )
    ids = {
        ("p", 1): 0,
        ("q", 1): 1,
        ("r", 1): 2,
        ("color_red", 1): 3,
        ("color_green", 1): 4,
        ("color_blue", 1): 5,
        ("rel", 3): 6,
        ("other", 3): 7,
        ("le", 2): 8,
    }
    facts = set(hypothesis_space._closed_world_property_facts(properties, ids))

    assert "equivalent_pred(0,1)." in facts
    assert "disjoint_arg(0,0,6,1)." in facts
    assert any(fact.startswith("tuple_mutex_pred(6,7,") for fact in facts)
    assert not any(fact.startswith("partition_size(") for fact in facts)
    assert "key_pred(6,0)." in facts
    assert "total_order_pred(8)." in facts
    assert "antisymmetric_pred(8)." not in facts
    assert "reflexive_pred(8)." not in facts


def test_partition_subsumes_pairwise_mutex_facts():
    program = Program(
        ["a(1).", "b(2).", "c(3)."],
        [],
        [],
        [],
        [
            ModeDeclaration(("1", "a", "1", "positive"), False),
            ModeDeclaration(("1", "b", "1", "positive"), False),
            ModeDeclaration(("1", "c", "1", "positive"), False),
        ],
    )
    program.complete_language_bias()
    fragments = hypothesis_space._closed_world_fragments(program)
    arg_types = hypothesis_space._predicate_arg_types(program, fragments)
    properties = hypothesis_space._closed_world_properties(
        fragments,
        arg_types,
        hypothesis_space._closed_body_predicates(program),
    )

    assert properties.partitions == frozenset({(("a", 1), ("b", 1), ("c", 1))})
    assert properties.mutex == frozenset()


def test_functional_set_facts_subsumed_by_smaller_dependencies_are_dropped():
    program = Program(
        ["r(1,a,x,z).", "r(1,a,y,z).", "r(1,b,q,z).", "r(2,a,x,w)."],
        [],
        [],
        [],
        [ModeDeclaration(("1", "r", "4", "positive"), False)],
    )
    program.complete_language_bias()
    fragments = hypothesis_space._closed_world_fragments(program)
    arg_types = hypothesis_space._predicate_arg_types(program, fragments)
    properties = hypothesis_space._closed_world_properties(
        fragments,
        arg_types,
        hypothesis_space._closed_body_predicates(program),
    )

    assert (("r", 4), 0, 3) in properties.functional
    assert (("r", 4), (0, 1), 3) not in properties.functional_set
    assert (("r", 4), (1, 3), 0) not in properties.functional_set


def test_choice_rules_infer_modelwise_keys():
    properties = hypothesis_space._closed_world_properties(
        [
            "#const n = 5.",
            "number(1..n).",
            "1 { q(X,Y) : number(Y) } 1 :- number(X).",
            "1 { q(X,Y) : number(X) } 1 :- number(Y).",
            "1 { x(R,C,N) : val(N) } 1 :- cell(R), cell(C).",
            "3 { in(X) : v(X) } 3.",
        ]
    )

    assert (("q", 2), (0,)) in properties.keys
    assert (("q", 2), (1,)) in properties.keys
    assert (("x", 3), (0, 1)) in properties.keys
    assert not any(predicate == ("in", 1) for predicate, _args in properties.keys)
    assert ("q", 2) not in properties.universal
    assert ((("q", 2), ("number", 1), (1,))) in properties.project_implies
    assert ((("q", 2), ("number", 1), (0,))) in properties.project_implies
    assert ((("in", 1), ("v", 1), (0,))) in properties.project_implies
    assert ((("in", 1), 3)) in properties.cardinality_upper


def test_closed_world_extensions_expand_numeric_ranges():
    extensions = hypothesis_space._closed_world_extensions(
        ["#const n = 3.", "number(1..n).", "pair(1..2,3..4)."]
    )

    assert extensions[("number", 1)] == {("1",), ("2",), ("3",)}
    assert extensions[("pair", 2)] == {
        ("1", "3"),
        ("1", "4"),
        ("2", "3"),
        ("2", "4"),
    }


def test_rule_defined_square_properties_propagate_choice_key():
    properties = hypothesis_space._closed_world_properties(
        [
            "part(a).",
            "val(1).",
            "val(2).",
            "1 { p(P,V) : val(V) } 1 :- part(P).",
            "sq(P,S) :- p(P,V), S = V*V.",
        ]
    )

    assert ((("sq", 2), (0,))) in properties.keys
    assert ((("sq", 2), 0, 1)) not in properties.functional


def test_cardinality_upper_facts_are_emitted():
    properties = hypothesis_space._closed_world_properties(
        ["val(1).", "val(2).", "1 { in(X) : val(X) } 1."]
    )
    facts = set(
        hypothesis_space._closed_world_property_facts(
            properties,
            {
                ("in", 1): 0,
                ("val", 1): 1,
            },
        )
    )

    assert "cardinality_upper_pred(0,1)." in facts


def test_choice_rule_keys_prune_conflicting_positive_literals():
    program = Program(
        [
            "number(1..5).",
            "1 { q(X,Y) : number(Y) } 1 :- number(X).",
            "1 { q(X,Y) : number(X) } 1 :- number(Y).",
        ],
        [],
        [],
        [],
        [ModeDeclaration(("2", "q", "2", "positive"), False)],
    )
    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=2, max_variables=3)
    ).generate().clauses

    assert ":- q(V0,V1),q(V0,V2)." not in clauses
    assert ":- q(V0,V1),q(V2,V1)." not in clauses


def test_choice_projection_prunes_redundant_domain_literal():
    program = Program(
        [
            "number(1..5).",
            "1 { q(X,Y) : number(Y) } 1 :- number(X).",
        ],
        [],
        [],
        [],
        [
            ModeDeclaration(("1", "q", "2", "positive"), False),
            ModeDeclaration(("1", "number", "1", "positive"), False),
        ],
    )
    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=2, max_variables=2)
    ).generate().clauses

    assert ":- q(V0,V1),number(V1)." not in clauses


def test_partition_prunes_all_negative_partition_literals():
    program = Program(
        [
            "red(a).",
            "green(b).",
            "blue(c).",
            "node(a).",
            "node(b).",
            "node(c).",
        ],
        [],
        [],
        [],
        [
            ModeDeclaration(("1", "node", "1", "positive"), False),
            ModeDeclaration(("1", "red", "1", "negative"), False),
            ModeDeclaration(("1", "green", "1", "negative"), False),
            ModeDeclaration(("1", "blue", "1", "negative"), False),
        ],
    )
    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=4, max_variables=1)
    ).generate().clauses

    assert ":- node(V0),not red(V0),not green(V0)." in clauses
    assert ":- node(V0),not red(V0),not green(V0),not blue(V0)." not in clauses


def test_mutex_complement_and_partition_prune_positive_negative_redundancy():
    program = Program(
        ["p(a).", "q(b).", "safe(a).", "safe(b)."],
        [],
        [],
        [],
        [
            ModeDeclaration(("1", "safe", "1", "positive"), False),
            ModeDeclaration(("1", "p", "1", "positive"), False),
            ModeDeclaration(("1", "p", "1", "negative"), False),
            ModeDeclaration(("1", "q", "1", "positive"), False),
            ModeDeclaration(("1", "q", "1", "negative"), False),
        ],
    )
    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=3, max_variables=1)
    ).generate().clauses

    assert ":- safe(V0),q(V0),not p(V0)." not in clauses
    assert ":- safe(V0),not p(V0),not q(V0)." not in clauses


def test_inverse_and_transitive_negative_closure_prune():
    inverse = Program(
        ["p(a,b).", "q(b,a)."],
        [],
        [],
        [],
        [
            ModeDeclaration(("1", "p", "2", "positive"), False),
            ModeDeclaration(("1", "q", "2", "negative"), False),
        ],
    )
    transitive = Program(
        ["p(a,b).", "p(b,c).", "p(a,c)."],
        [],
        [],
        [],
        [
            ModeDeclaration(("2", "p", "2", "positive"), False),
            ModeDeclaration(("1", "p", "2", "negative"), False),
        ],
    )

    inverse_clauses = HypothesisSpaceGenerator(
        inverse, Arguments(max_depth=2, max_variables=2)
    ).generate().clauses
    transitive_clauses = HypothesisSpaceGenerator(
        transitive, Arguments(max_depth=3, max_variables=3)
    ).generate().clauses

    assert ":- p(V0,V1),not q(V1,V0)." not in inverse_clauses
    assert ":- p(V0,V1),p(V1,V2),not p(V0,V2)." not in transitive_clauses


def test_acyclic_negative_back_edge_prune():
    program = Program(
        ["edge(a,b).", "edge(b,c)."],
        [],
        [],
        [],
        [
            ModeDeclaration(("2", "edge", "2", "positive"), False),
            ModeDeclaration(("1", "edge", "2", "negative"), False),
        ],
    )
    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=3, max_variables=3)
    ).generate().clauses

    assert ":- edge(V0,V1),edge(V1,V2),not edge(V2,V0)." not in clauses


def test_universal_empty_and_complement_facts_are_emitted():
    universal_program = Program(
        ["dom(a).", "dom(b).", "p(a).", "p(b)."],
        [],
        [],
        [],
        [
            ModeDeclaration(("1", "dom", "1", "positive"), False),
            ModeDeclaration(("1", "p", "1", "positive"), False),
            ModeDeclaration(("1", "missing", "1", "positive"), False),
        ],
    )
    domain_program = Program(
        ["left(a).", "right(b)."],
        [],
        [],
        [],
        [
            ModeDeclaration(("1", "left", "1", "positive"), False),
            ModeDeclaration(("1", "right", "1", "positive"), False),
        ],
    )
    universal_program.complete_language_bias()
    domain_program.complete_language_bias()
    universal_fragments = hypothesis_space._closed_world_fragments(universal_program)
    domain_fragments = hypothesis_space._closed_world_fragments(domain_program)
    universal_arg_types = hypothesis_space._predicate_arg_types(
        universal_program, universal_fragments
    )
    domain_arg_types = hypothesis_space._predicate_arg_types(
        domain_program, domain_fragments
    )
    universal_properties = hypothesis_space._closed_world_properties(
        universal_fragments,
        universal_arg_types,
        hypothesis_space._closed_body_predicates(universal_program),
    )
    domain_properties = hypothesis_space._closed_world_properties(
        domain_fragments,
        domain_arg_types,
        hypothesis_space._closed_body_predicates(domain_program),
    )
    universal_ids = {
        ("dom", 1): 0,
        ("p", 1): 1,
        ("missing", 1): 2,
    }
    domain_ids = {
        ("left", 1): 2,
        ("right", 1): 3,
    }
    facts = set(
        hypothesis_space._closed_world_property_facts(universal_properties, universal_ids)
    ) | set(hypothesis_space._closed_world_property_facts(domain_properties, domain_ids))

    assert "universal_pred(1)." in facts
    assert "empty_pred(2)." in facts
    assert "complement_pred(2,3)." in facts


def test_universal_binary_predicate_derives_reflexive_property():
    rule_dir = Path(hypothesis_space.__file__).with_name("rules")
    rules = (rule_dir / "properties" / "universal.lp").read_text() + """
universal_pred(1).
mode(body,0,1,2,1).
#show reflexive_pred/1.
"""
    ctl = clingo.Control(["--warn=none"])
    ctl.add("base", [], rules)
    ctl.ground([("base", [])])

    with ctl.solve(yield_=True) as handle:
        symbols = {str(symbol) for model in handle for symbol in model.symbols(shown=True)}

    assert "reflexive_pred(1)" in symbols


def test_empty_predicate_prunes_positive_and_negative_literals():
    program = Program(
        ["safe(a)."],
        [],
        [],
        [],
        [
            ModeDeclaration(("1", "safe", "1", "positive"), False),
            ModeDeclaration(("1", "missing", "1", "positive"), False),
            ModeDeclaration(("1", "missing", "1", "negative"), False),
        ],
    )
    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=2, max_variables=1)
    ).generate().clauses

    assert not any("missing(" in clause for clause in clauses)


def test_functional_negative_redundancy_with_inequality_prunes():
    program = Program(
        ["parent(a,b).", "parent(c,d).", "child(b).", "child(d)."],
        [],
        [],
        [],
        [
            ModeDeclaration(("1", "parent", "2", "positive"), False),
            ModeDeclaration(("1", "parent", "2", "negative"), False),
            ModeDeclaration(("1", "child", "1", "positive"), False),
        ],
        [],
        [OperatorDeclaration(1, "neq")],
    )
    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=4, max_variables=3)
    ).generate().clauses

    assert not any(
        "parent(V0,V1)" in clause
        and "not parent(V0,V2)" in clause
        and "child(V2)" in clause
        and "V1!=V2" in clause
        for clause in clauses
    )


def test_functional_negative_redundancy_uses_strict_comparison():
    program = Program(
        ["p(1,1).", "p(2,2).", "value(1).", "value(2)."],
        [],
        [],
        [],
        [
            ModeDeclaration(("1", "p", "2", "positive"), False),
            ModeDeclaration(("1", "p", "2", "negative"), False),
            ModeDeclaration(("1", "value", "1", "positive"), False),
        ],
        [],
        [OperatorDeclaration(1, "lt")],
    )
    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=4, max_variables=3)
    ).generate().clauses

    assert not any(
        "p(V0,V1)" in clause
        and "not p(V0,V2)" in clause
        and "value(V2)" in clause
        and "V1<V2" in clause
        for clause in clauses
    )


def test_cardinality_upper_prunes_pairwise_distinct_positive_tuples():
    program = Program(
        ["value(a).", "value(b).", "1 { in(X) : value(X) } 1."],
        [],
        [],
        [],
        [ModeDeclaration(("2", "in", "1", "positive"), False)],
        [],
        [OperatorDeclaration(1, "neq")],
    )
    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=3, max_variables=2)
    ).generate().clauses

    assert ":- in(V0),in(V1),V0!=V1." not in clauses


def test_empty_join_and_total_order_prune_impossible_bodies():
    empty_join = Program(
        ["p(a).", "q(b).", "safe(a).", "safe(b)."],
        [],
        [],
        [],
        [
            ModeDeclaration(("1", "safe", "1", "positive"), False),
            ModeDeclaration(("1", "p", "1", "positive"), False),
            ModeDeclaration(("1", "q", "1", "positive"), False),
        ],
    )
    order = Program(
        ["le(a,a).", "le(a,b).", "le(b,b).", "pair(a,b)."],
        [],
        [],
        [],
        [
            ModeDeclaration(("1", "pair", "2", "positive"), False),
            ModeDeclaration(("2", "le", "2", "negative"), False),
        ],
    )

    empty_clauses = HypothesisSpaceGenerator(
        empty_join, Arguments(max_depth=3, max_variables=1)
    ).generate().clauses
    order_clauses = HypothesisSpaceGenerator(
        order, Arguments(max_depth=3, max_variables=2)
    ).generate().clauses

    assert ":- safe(V0),p(V0),q(V0)." not in empty_clauses
    assert ":- pair(V0,V1),not le(V0,V1),not le(V1,V0)." not in order_clauses


def test_reflexive_key_antisymmetric_and_subsumption_prunes():
    reflexive = Program(
        ["le(a,a).", "le(a,b).", "le(b,b).", "node(a).", "node(b)."],
        [],
        [],
        [],
        [
            ModeDeclaration(("1", "node", "1", "positive"), False),
            ModeDeclaration(("1", "le", "2", "positive"), False),
            ModeDeclaration(("1", "le", "2", "negative"), False),
        ],
    )
    key = Program(
        ["rel(a,b,c).", "rel(d,e,f)."],
        [],
        [],
        [],
        [ModeDeclaration(("2", "rel", "3", "positive"), False)],
    )
    subsumption = Program(
        ["p(a,a).", "p(a,b)."],
        [],
        [],
        [],
        [ModeDeclaration(("2", "p", "2", "positive"), False)],
    )

    reflexive_clauses = HypothesisSpaceGenerator(
        reflexive, Arguments(max_depth=3, max_variables=2)
    ).generate().clauses
    key_clauses = HypothesisSpaceGenerator(
        key, Arguments(max_depth=2, max_variables=5)
    ).generate().clauses
    subsumption_clauses = HypothesisSpaceGenerator(
        subsumption, Arguments(max_depth=2, max_variables=2)
    ).generate().clauses

    assert ":- node(V0),le(V0,V0)." not in reflexive_clauses
    assert ":- node(V0),not le(V0,V0)." not in reflexive_clauses
    assert ":- le(V0,V1),le(V1,V0)." not in reflexive_clauses
    assert ":- rel(V0,V1,V2),rel(V0,V3,V4)." not in key_clauses
    assert ":- p(V0,V1),p(V0,V0)." not in subsumption_clauses


def test_equivalent_head_body_redundancy_is_pruned():
    program = Program(
        ["p(a).", "q(a)."],
        [],
        [],
        [ModeDeclaration(("1", "p", "1"), True)],
        [ModeDeclaration(("1", "q", "1", "positive"), False)],
    )
    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=2, max_variables=1)
    ).generate().clauses

    assert "p(V0) :- q(V0)." not in clauses


def test_closed_world_properties_apply_to_aggregate_condition_atoms():
    program = Program(
        ["edge(a,b).", "edge(b,a)."],
        [],
        [],
        [ModeDeclaration(("1", "target", "1"), True)],
        [],
        [AggregateDeclaration(1, "count", (("edge", 2),), True)],
    )
    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=2, max_variables=4)
    ).generate().clauses

    for clause in clauses:
        for left, right in re.findall(r"edge\(V(\d+),V(\d+)\)", clause):
            assert int(left) <= int(right)


def test_mul_and_abs_operands_are_canonicalized():
    program = Program(
        ["q(1,2)."],
        [],
        [],
        [],
        [ModeDeclaration(("1", "q", "2", "positive"), False)],
        [],
        [],
        [OperatorDeclaration(1, "mul"), OperatorDeclaration(1, "abs")],
    )
    clauses = HypothesisSpaceGenerator(
        program, Arguments(max_depth=3, max_variables=3)
    ).generate().clauses

    assert not any(
        left > right
        for clause in clauses
        for left, right in re.findall(r"V(\d+)\*V(\d+)=", clause)
    )
    assert not any(
        left > right
        for clause in clauses
        for left, right in re.findall(r"\|V(\d+)-V(\d+)\|=", clause)
    )


def test_reader_parses_directives_without_regex_space_loss(tmp_path):
    task = tmp_path / "task.txt"
    task.write_text(
        "\n".join(
            [
                "",
                "% comment",
                "edge(1,2).",
                "#pos({ red(1), blue(f(2,3)) }, { green(1) }, { ctx((1,2)) }).",
                "#neg({ bad(1) }, {}).",
                "#modeh(1, red, 1).",
                "#modeb(2, edge, 2, positive).",
                "#modeagg(1, sum(edge/2), unbalanced).",
                "#modecmp(2, neq).",
                "#modearith(1, add).",
            ]
        ),
        encoding="utf-8",
    )

    program = read_program(str(task))

    assert program.background == ["edge(1,2)."]
    assert program.positive_examples[0].included == "red(1), blue(f(2,3))"
    assert program.positive_examples[0].excluded == "green(1)"
    assert program.positive_examples[0].context == "ctx((1,2))"
    assert program.negative_examples[0].included == "bad(1)"
    assert program.language_bias_head[0].name == "red"
    assert program.language_bias_body[0].name == "edge"
    assert program.aggregate_modes == [
        AggregateDeclaration(1, "sum", (("edge", 2),), True)
    ]
    assert program.comparison_modes == [OperatorDeclaration(2, "neq")]
    assert program.arithmetic_modes == [OperatorDeclaration(1, "add")]


def test_language_bias_auto_generates_head_and_closed_body_when_bias_is_missing():
    program = Program(
        ["a :- b, not c."],
        [],
        [],
        [],
        [],
    )

    program.complete_language_bias()

    heads = {(mode.name, mode.arity) for mode in program.language_bias_head}
    bodies = {
        (mode.name, mode.arity, mode.positive) for mode in program.language_bias_body
    }

    assert heads == {("a", 0), ("b", 0), ("c", 0)}
    assert bodies == {
        ("a", 0, True),
        ("b", 0, True),
        ("c", 0, True),
        ("c", 0, False),
    }


def test_language_bias_auto_keeps_explicit_head_and_generates_missing_body():
    program = Program(
        ["coin(c1)."],
        [Example(("heads(c1)", "tails(c1)"), True)],
        [],
        [
            ModeDeclaration(("1", "heads", "1"), True),
            ModeDeclaration(("1", "tails", "1"), True),
        ],
        [],
    )

    program.complete_language_bias()

    assert {(mode.name, mode.arity) for mode in program.language_bias_head} == {
        ("heads", 1),
        ("tails", 1),
    }
    assert {
        (mode.name, mode.arity, mode.positive) for mode in program.language_bias_body
    } == {
        ("coin", 1, True),
        ("heads", 1, True),
        ("tails", 1, True),
        ("tails", 1, False),
    }


def test_language_bias_auto_does_not_generate_head_when_body_is_explicit():
    program = Program(
        ["target(1)."],
        [],
        [],
        [],
        [ModeDeclaration(("1", "target", "1", "positive"), False)],
    )

    program.complete_language_bias()

    assert program.language_bias_head == []
    assert {
        (mode.name, mode.arity, mode.positive) for mode in program.language_bias_body
    } == {("target", 1, True)}


def test_ast_atom_extraction_handles_choice_rules():
    atoms = {
        (name, arguments)
        for name, arguments, _negative in fragment_atoms(
            "1 { p(P,I) : partition(P) } 1 :- number(I)."
        )
    }

    assert ("p", ("P", "I")) in atoms
    assert ("partition", ("P",)) in atoms
    assert ("number", ("I",)) in atoms


def _benchmark_clauses(name: str) -> set[str]:
    args = copy.deepcopy(CASES[name])
    args.max_candidate_clauses = 0
    return set(HypothesisSpaceGenerator(read_program(args.filename), args).generate().clauses)


def test_coloring_hypothesis_space_contains_target_rules():
    clauses = _benchmark_clauses("coloring")

    assert "red(V0);green(V0);blue(V0) :- node(V0)." in clauses
    assert ":- e(V0,V1),red(V0),red(V1)." in clauses
    assert ":- e(V0,V1),green(V0),green(V1)." in clauses
    assert ":- e(V0,V1),blue(V0),blue(V1)." in clauses


def test_coin_hypothesis_space_contains_target_rules():
    clauses = _benchmark_clauses("coin")

    assert "heads(V0) :- coin(V0),not tails(V0)." in clauses
    assert "tails(V0) :- coin(V0),not heads(V0)." in clauses


def test_even_odd_hypothesis_space_contains_mutual_recursion():
    clauses = _benchmark_clauses("even_odd")

    assert "even(V1) :- odd(V0),prev(V1,V0)." in clauses
    assert "odd(V1) :- even(V0),prev(V1,V0)." in clauses


def test_grandparent_hypothesis_space_contains_invented_predicate_solution():
    args = copy.deepcopy(CASES["grandparent"])
    program = read_program(args.filename)
    clauses = set(HypothesisSpaceGenerator(program, args).generate().clauses)

    assert program.invented_predicates == (("target_1", 2),)
    assert len(program.positive_examples) == 7
    assert "target(V0,V2) :- target_1(V0,V1),target_1(V1,V2)." in clauses
    assert "target_1(V0,V1) :- mother(V0,V1)." in clauses
    assert "target_1(V0,V1) :- father(V0,V1)." in clauses
    assert not any(
        clause.startswith("target_1(") and "target_1(" in clause.split(" :- ", 1)[1]
        for clause in clauses
    )


def test_fixed_benchmark_definitions_expose_real_target_shapes():
    queens = _benchmark_clauses("8queens")
    euclid = _benchmark_clauses("euclid")
    subset_double = _benchmark_clauses("subset_sum_double")
    subset_sum = _benchmark_clauses("subset_sum_double_and_sum")
    set_partition = _benchmark_clauses("set_partition_sum")

    assert any(clause.startswith(":- ") and clause.count("q(") == 2 and "+" in clause for clause in queens)
    assert any(clause.startswith(":- ") and clause.count("q(") == 2 and "-" in clause for clause in queens)
    assert any("\\" in clause and "eucl(" in clause for clause in euclid)
    assert "ok(V0) :- s0(V0),s1(V0)." in subset_double
    assert any(
        clause.startswith("ok(") and clause.count("#sum{") >= 2 and "+" in clause
        for clause in subset_sum
    )
    assert any(
        clause.startswith(":- ")
        and clause.count("sum_partition(") >= 2
        and "!=" in clause
        for clause in set_partition
    )


def test_normal_mode_recall_prevents_duplicate_head_literals():
    clauses = _benchmark_clauses("coloring")

    assert not any(clause.startswith("blue(") and ";blue(" in clause for clause in clauses)


def test_unbalanced_aggregate_random_seed_program_is_clingo_safe():
    args = copy.deepcopy(CASES["subset_sum_double_and_prod_unbalanced"])
    program = read_program(args.filename)
    clauses = HypothesisSpaceGenerator(program, args).generate()
    random.seed(1)
    candidate = tuple(sorted(random.sample(clauses.clauses, args.max_program_clauses)))

    NormalCoverageSolver(
        program.background,
        args.fitness["clingo_arguments"],
        program.positive_examples,
        program.negative_examples,
    ).extract_fixed_coverage(candidate)
