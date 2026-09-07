import random
from dataclasses import replace

import pytest

from gentians.arguments import Arguments
from gentians.clauses import generator as generation
from gentians.clauses.task_analysis import _prune_optional_constraints
from gentians.evaluation import create_evaluator
from gentians.language import parse_text
from gentians.language.asp import parse_program
from tests.task_helpers import example


def task():
    return parse_text("""
        {q}.
        #maxv(0).
        #maxbl(1).
        #modeh(1,p).
        #modeb(1,q).
        #pos({p},{q}).
    """)


def generate(problem, sampled):
    args = Arguments(clause_generation={"clingo_arguments": []})
    if sampled:
        return generation.sample_clause_space(problem, args, 100, random.Random(3))
    return generation.generate_clause_space(problem, args)


@pytest.mark.parametrize("sampled", [False, True])
def test_prunes_inside_enumeration_before_decoder(monkeypatch, sampled):
    decoded = []
    original = generation._clause_from_model

    def decode(*args):
        clause = original(*args)
        assert clause.head, "headless models must never reach the Python decoder"
        decoded.append(clause)
        return clause

    monkeypatch.setattr(generation, "_clause_from_model", decode)
    space = generate(task(), sampled)
    assert decoded and space
    assert "p." in space.clauses
    assert all(entry.heads for entry in space.entries)


@pytest.mark.parametrize("sampled", [False, True])
def test_negative_examples_keep_constraints(sampled):
    problem = task()
    problem.negative_examples = [example(("q", ""), False)]
    assert ":- q." in generate(problem, sampled).clauses


@pytest.mark.parametrize("sampled", [False, True])
def test_constraint_only_language_remains_nonempty(sampled):
    problem = task()
    problem.language_bias_head = []
    problem.max_head_literals = 0
    space = generate(problem, sampled)
    assert space and all(not entry.heads for entry in space.entries)


@pytest.mark.parametrize("sampled", [False, True])
def test_constraint_only_solution_survives_even_with_head_modes(sampled):
    problem = parse_text("""
        {q;r}.
        #maxv(0).
        #maxbl(1).
        #modeh(1,p).
        #modeb(1,r).
        #pos({q},{p}).
    """)
    space = generate(problem, sampled)
    assert ":- r." in space.clauses
    evaluator = create_evaluator(problem, {"scoring": "cov_program"})
    assert evaluator(parse_program(":- r.")).is_solution
    assert not evaluator(parse_program("p.")).is_complete


def test_contexts_are_isolated_and_strong_negation_keeps_its_sign():
    problem = task()
    problem.positive_examples = [example(("p", "", "p."), True)]
    assert not _prune_optional_constraints(problem)
    problem.positive_examples.append(example(("p", "", "-p."), True))
    assert _prune_optional_constraints(problem)


@pytest.mark.parametrize("sampled", [False, True])
@pytest.mark.parametrize("in_context", [False, True])
def test_pooled_heads_disable_early_pruning(monkeypatch, sampled, in_context):
    background = "" if in_context else "q(a;b)."
    context = ",{q(a;b).}" if in_context else ""
    problem = parse_text(background + """
        {r}.
        #maxv(0). #maxbl(1).
        #modeh(1,p). #modeb(1,r).
    """ + "#pos({q(a)},{p}" + context + ").")
    assert not _prune_optional_constraints(problem)
    actual = generate(problem, sampled).clauses
    monkeypatch.setattr(generation, "_prune_optional_constraints", lambda _: False)
    assert actual == generate(problem, sampled).clauses
    evaluator = create_evaluator(problem, {"scoring": "cov_program"})
    assert evaluator(parse_program(":- r.")).is_solution
    assert not evaluator(parse_program("p.")).is_complete


def test_directives_and_empty_positive_side_are_conservative():
    problem = task()
    assert not _prune_optional_constraints(replace(problem, positive_examples=[]))
    assert not _prune_optional_constraints(replace(
        problem, background=parse_program("#external p. {q}.")))


def test_background_and_context_constraints_are_untouched():
    problem = task()
    problem.background = parse_program("{q}. :- not q.")
    problem.positive_examples = [example(("p", "", "{r}. :- r."), True)]
    background, contexts = tuple(map(str, problem.background)), problem.positive_examples[:]
    assert _prune_optional_constraints(problem)
    assert all(entry.heads for entry in generate(problem, False).entries)
    assert tuple(map(str, problem.background)) == background
    assert problem.positive_examples == contexts
