from gentians.arguments import Arguments
from gentians.rule_generation import hypothesis_space
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
