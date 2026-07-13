import random

from gentians.arguments import Arguments
from gentians.evolution.algorithms.search import search_solver
from gentians.evolution.closures import create_closure
from gentians.evolution.crossovers import create_crossover
from gentians.evolution.mutations import create_mutation
from gentians.evolution.selections import create_selection
from gentians.evolution.evolution_context import EvolutionContext
from gentians.rule_generation.program import Program
from gentians.rule_generation.rule_space import RuleSpace


def _context(rules, *, closure="none", max_clauses=3):
    program = Program(["base."], [], [], [], [])
    space = RuleSpace.from_clauses(list(rules))
    rng = random.Random(7)
    policy = create_closure(closure, program, space, max_clauses, rng)
    return EvolutionContext(policy.space, policy, max_clauses, rng)


def test_all_mutations_share_genome_contract():
    context = _context(["a.", "b.", "c."])
    genome = ("a.", "b.")
    result = create_mutation({"name": "random_group", "probability": 1.0})(
        genome, context
    )
    assert isinstance(result, tuple)
    assert set(result) <= set(context.space.clauses)


def test_all_crossovers_share_genome_contract():
    context = _context(["a.", "b.", "c."])
    children = create_crossover({"name": "set_mix", "probability": 1.0})(
        ("a.", "b."), ("b.", "c."), context
    )
    assert isinstance(children, tuple)
    assert all(isinstance(child, tuple) for child in children)


def test_tournament_has_one_canonical_strategy_name():
    try:
        create_selection(
            {
                "name": "original_tournament",
                "tournament_size": 3,
                "prob_selecting_fittest": 1.0,
            }
        )
    except ValueError as error:
        assert "Unknown selection strategy" in str(error)
    else:
        raise AssertionError("legacy tournament alias was accepted")


def test_dependency_policy_closes_every_proposal():
    rules = (
        "heads(V0):- coin(V0),not tails(V0).",
        "tails(V0):- coin(V0),not heads(V0).",
    )
    program = Program(["coin(c1)."], [], [], [], [])
    space = RuleSpace.from_clauses(list(rules))
    policy = create_closure("dependency", program, space, 2, random.Random(1))
    assert policy.normalize((rules[0],)) == tuple(sorted(rules))


def test_no_closure_keeps_valid_proposal_without_repair():
    context = _context(["target :- missing."])
    assert context.policy.normalize(("target :- missing.",)) == ("target :- missing.",)


def test_subprogram_closure_repairs_every_genome_to_fixed_size():
    program = Program([], [], [], [], [])
    space = RuleSpace.from_clauses(["a.", "b.", "c."])
    policy = create_closure(
        "none", program, space, 3, random.Random(1), fixed_size=True
    )

    assert len(policy.normalize(("b.",))) == 3


def test_whole_program_closure_preserves_variable_size():
    program = Program([], [], [], [], [])
    space = RuleSpace.from_clauses(["a.", "b.", "c."])
    policy = create_closure("none", program, space, 3, random.Random(1))

    assert policy.normalize(("b.",)) == ("b.",)


def test_single_engine_accepts_supplied_hypothesis_space(monkeypatch):
    args = Arguments(
        max_program_clauses=1,
        random_seed=3,
        iterations_genetic=0,
        closure={"name": "none"},
        population={"name": "random", "size": 1},
    )
    monkeypatch.setattr(
        "gentians.evolution.algorithms.search.create_fitness",
        lambda program, config, max_program_clauses, rule_space: lambda candidate: (
            1.0,
            True,
        ),
    )
    result, score, best = search_solver(
        args,
        Program([], [], [], [], []),
        RuleSpace.from_clauses(["good."]),
    )
    assert result == ("good.",)
    assert score == 1.0
    assert best is True
