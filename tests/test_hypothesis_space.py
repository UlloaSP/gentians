import copy
import random
import re

from benchmarks.catalog import CASES
from gentians.arguments import Arguments
from gentians.asp.clingo import ClingoInterface
from gentians import timing
from gentians.rule_generation import hypothesis_space
from gentians.rule_generation.parser import extract_name_arity, parse_atom
from gentians.rule_generation.reader import read_program
from gentians.rule_generation.hypothesis_space import (
    HypothesisSpaceGenerator,
    _hypothesis_space_args,
)
from gentians.rule_generation.hypothesis_space import HypothesisCapabilities
from gentians.rule_generation.program import ModeDeclaration, Program
from gentians.rule_generation.rule_space import RuleSpace


def test_valid_aggregate_specs_skips_predicate_scan_without_aggregates(monkeypatch):
    def fail_if_called(program):
        raise AssertionError("predicate scan should not run without aggregate specs")

    monkeypatch.setattr(hypothesis_space, "_available_predicates", fail_if_called)

    assert hypothesis_space._valid_aggregate_specs(
        Program(["p(1)."], [], [], [], []),
        Arguments(),
    ) == []


def test_hypothesis_generator_computes_valid_aggregate_specs_once(monkeypatch):
    calls = 0

    def aggregate_specs(program, args):
        nonlocal calls
        calls += 1
        return [("sum", [("p", 1)])]

    monkeypatch.setattr(hypothesis_space, "_valid_aggregate_specs", aggregate_specs)

    hypothesis_space.HypothesisSpaceGenerator(
        Program(
            ["p(1)."],
            [],
            [],
            [ModeDeclaration(("1", "target", "1"), True)],
            [ModeDeclaration(("1", "p", "1", "positive"), False)],
        ),
        Arguments(aggregates=["sum(p/1)"]),
    )

    assert calls == 1


def test_facts_reduces_body_slots_when_head_is_required():
    facts = hypothesis_space._facts(
        Program([], [], [], [], []),
        Arguments(max_depth=4),
        [],
        HypothesisCapabilities(
            has_numeric_evidence=False,
            allow_numeric_comparison=False,
            allow_equality_comparison=False,
            allow_arithmetic=False,
            allow_aggregates=False,
            allow_recursion=False,
            allow_constraints=False,
        ),
        {},
    )

    assert "max_body(3)." in facts
    assert "constraints_allowed." not in facts


def test_facts_keeps_full_body_slots_for_constraints():
    facts = hypothesis_space._facts(
        Program([], [], [], [], []),
        Arguments(max_depth=4),
        [],
        HypothesisCapabilities(
            has_numeric_evidence=False,
            allow_numeric_comparison=False,
            allow_equality_comparison=False,
            allow_arithmetic=False,
            allow_aggregates=False,
            allow_recursion=False,
            allow_constraints=True,
        ),
        {},
    )

    assert "max_body(4)." in facts
    assert "constraints_allowed." in facts


def _reset_timing_state() -> None:
    timing._totals.clear()
    timing._counts.clear()
    timing._stack.clear()
    timing._ga_rows.clear()
    timing._timings_dirty = False
    timing._ga_dirty = False


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
    assert clauses.clauses == ["p."]
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
    )
    clauses = HypothesisSpaceGenerator(
        program,
        Arguments(
            max_depth=6,
            max_variables=8,
            max_candidate_clauses=0,
            aggregates=["sum(el/2)"],
            unbalanced_aggregates=True,
        ),
    ).generate().clauses

    assert not any("#sum{V0:el(V0,V0)}" in clause for clause in clauses)
    assert any("#sum{V0:el(V0,V1)}" in clause for clause in clauses)
    assert any("#sum{V0,V1:el(V0,V1)}" in clause for clause in clauses)
    assert not any(clause.count("#sum{") > 1 for clause in clauses)


def test_atom_parser_handles_nested_arguments():
    assert hypothesis_space._parse_normal_atom("same_row((X1,Y),(X2,Y))") == (
        "same_row",
        ["(X1,Y)", "(X2,Y)"],
    )
    assert extract_name_arity("same_row((X1,Y),(X2,Y))") == (
        "same_row",
        2,
    )


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
            hypothesis_space.HypothesisMode(
                0,
                0,
                "head",
                "normal",
                "p",
                1,
                mode.recall,
            )
        ],
        hypothesis_space.HypothesisCapabilities(
            False,
            False,
            False,
            False,
            False,
            False,
            False,
        ),
        {},
    )

    assert "recall(0,2)." in facts
    assert "unbounded_recall" not in facts


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


def test_hypothesis_space_prunes_irreflexive_modes_before_rendering():
    program = Program(
        ["edge(1,2)."],
        [],
        [],
        [ModeDeclaration(("1", "target", "2"), True)],
        [ModeDeclaration(("1", "edge", "2", "positive"), False)],
    )
    clauses = HypothesisSpaceGenerator(
        program,
        Arguments(max_depth=2, hypothesis_space={"irreflexive": ["edge/2"]}),
    ).generate().clauses

    assert not any("edge(V0,V0)" in clause for clause in clauses)
    assert "target(V0,V1) :- edge(V0,V1)." in clauses


def test_hypothesis_space_prunes_reversed_symmetric_comparisons_before_rendering():
    program = Program(
        ["p(1).", "p(2)."],
        [],
        [],
        [],
        [ModeDeclaration(("2", "p", "1", "positive"), False)],
    )
    clauses = HypothesisSpaceGenerator(
        program,
        Arguments(
            max_depth=4,
            max_variables=2,
            comparison_operators=["neq", "neq"],
        ),
    ).generate().clauses

    assert not any("V0!=V1,V1!=V0" in clause for clause in clauses)
    assert any("V0!=V1" in clause for clause in clauses)


def test_hypothesis_space_prunes_arithmetic_identities_before_cap():
    args = copy.deepcopy(CASES["4queens"])
    args.max_candidate_clauses = 10000
    clauses = HypothesisSpaceGenerator(read_program(args.filename), args).generate().clauses

    assert len(clauses) < args.max_candidate_clauses
    assert not any("V0+V1=V2,V2-V0=V1" in clause for clause in clauses)


def test_canonical_prune_prevents_reversed_add_operands():
    program_without_zero = Program(
        ["#const n = 2.", "number(1..n).", "q(1,1)."],
        [],
        [],
        [],
        [ModeDeclaration(("1", "q", "2", "positive"), False)],
    )
    clauses = HypothesisSpaceGenerator(
        program_without_zero,
        Arguments(
            max_depth=4,
            max_variables=3,
            arithmetic_operators=["add"],
            hypothesis_space={"canonical_prune": True},
        ),
    ).generate().clauses

    assert clauses
    assert not any(
        left > right
        for clause in clauses
        for left, right in re.findall(r"V(\d+)\+V(\d+)=", clause)
    )


def test_domain_arithmetic_prune_removes_impossible_zero_result_only_when_domain_excludes_zero():
    program_without_zero = Program(
        ["#const n = 2.", "number(1..n).", "q(1,1)."],
        [],
        [],
        [],
        [ModeDeclaration(("1", "q", "2", "positive"), False)],
    )
    program_with_zero = Program(
        ["number(0..2).", "q(0,0)."],
        [],
        [],
        [],
        [ModeDeclaration(("1", "q", "2", "positive"), False)],
    )
    args = Arguments(
        max_depth=4,
        max_variables=3,
        arithmetic_operators=["sub"],
        hypothesis_space={"domain_arithmetic_prune": True},
    )
    without_zero = HypothesisSpaceGenerator(program_without_zero, args).generate().clauses
    with_zero = HypothesisSpaceGenerator(program_with_zero, args).generate().clauses

    assert not any("V0-V0=V1" in clause and "q(V0,V1)" in clause for clause in without_zero)
    assert any("V0-V0=V1" in clause and "q(V0,V1)" in clause for clause in with_zero)


def test_reader_parses_directives_without_regex_space_loss(tmp_path):
    task = tmp_path / "task.txt"
    task.write_text(
        "\n".join(
            [
                "edge(1,2).",
                "#pos({ red(1), blue(f(2,3)) }, { green(1) }, { ctx((1,2)) }).",
                "#neg({ bad(1) }, {}).",
                "#modeh(1, red, 1).",
                "#modeb(2, edge, 2, positive).",
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


def test_ast_atom_extraction_handles_choice_rules():
    atoms = hypothesis_space._atoms_in_fragment(
        "1 { p(P,I) : partition(P) } 1 :- number(I)."
    )

    assert "p(P,I)" in atoms
    assert "partition(P)" in atoms
    assert "number(I)" in atoms


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


def test_even_odd_hypothesis_space_contains_mutual_recursion():
    clauses = _benchmark_clauses("even_odd")

    assert "even(V1) :- odd(V0),prev(V1,V0)." in clauses
    assert "odd(V1) :- even(V0),prev(V1,V0)." in clauses


def test_grandparent_hypothesis_space_contains_invented_predicate_solution():
    clauses = _benchmark_clauses("grandparent")

    assert "target(V0,V2) :- target_1(V0,V1),target_1(V1,V2)." in clauses
    assert "target_1(V0,V1) :- mother(V0,V1)." in clauses
    assert "target_1(V0,V1) :- father(V0,V1)." in clauses


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
    candidate = sorted(random.sample(clauses.clauses, args.max_program_clauses))

    ClingoInterface(program.background, args.fitness["clingo_arguments"]).extract_fixed_coverage(
        candidate,
        program.positive_examples,
        program.negative_examples,
    )
