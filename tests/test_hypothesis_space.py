import copy
import random

from benchmarks.catalog import CASES
from gentians.arguments import Arguments
from gentians.asp.clingo import ClingoInterface
from gentians import timing
from gentians.rule_generation import hypothesis_space
from gentians.rule_generation import candidates
from gentians.rule_generation.candidates import read_task
from gentians.rule_generation.hypothesis_space import HypothesisSpaceGenerator
from gentians.rule_generation.hypothesis_space import HypothesisCapabilities
from gentians.rule_generation.program import ModeDeclaration, Program


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
    )

    assert "max_body(3)." in facts
    assert "constraints_allowed." not in facts


def test_facts_keeps_full_body_slots_for_constraints():
    facts = hypothesis_space._facts(
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
            return ["p."]

    monkeypatch.setattr(
        candidates, "HypothesisSpaceGenerator", FakeHypothesisSpaceGenerator
    )

    candidates.build_candidate_rule_space(Program([], [], [], [], []), Arguments())

    assert phases == ["hypothesis_space"]
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
        HypothesisSpaceGenerator(program, Arguments(clauses_to_sample=0)).generate()

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
            clauses_to_sample=0,
            aggregates=["sum(el/2)"],
            unbalanced_aggregates=True,
        ),
    ).generate()

    assert not any("#sum{V0:el(V0,V0)}" in clause for clause in clauses)
    assert any("#sum{V0:el(V0,V1)}" in clause for clause in clauses)
    assert any("#sum{V0,V1:el(V0,V1)}" in clause for clause in clauses)
    assert not any(clause.count("#sum{") > 1 for clause in clauses)


def test_atom_parser_handles_nested_arguments():
    assert hypothesis_space._parse_normal_atom("same_row((X1,Y),(X2,Y))") == (
        "same_row",
        ["(X1,Y)", "(X2,Y)"],
    )
    assert hypothesis_space.extract_name_arity("same_row((X1,Y),(X2,Y))") == (
        "same_row",
        2,
    )


def _benchmark_clauses(name: str) -> set[str]:
    args = copy.deepcopy(CASES[name])
    args.clauses_to_sample = 0
    return set(HypothesisSpaceGenerator(read_task(args.filename), args).generate())


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
    set_partition = _benchmark_clauses("set_partition_sum_new")

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
    program = read_task(args.filename)
    clauses = HypothesisSpaceGenerator(program, args).generate()
    random.seed(1)
    candidate = sorted(random.sample(clauses, args.clauses_per_individual))

    ClingoInterface(program.background, args.fitness["clingo_arguments"]).extract_coverage_and_set_clauses(
        candidate,
        program.positive_examples,
        program.negative_examples,
        False,
    )
