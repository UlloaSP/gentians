import random
import importlib
from contextlib import contextmanager


from gentians.algorithms.incremental_clause_pool import activate_clauses
from gentians.algorithms.incremental_population import retain_population
from gentians.algorithms import incremental_clause_pool as clause_pool
from gentians.evolution.individual import Individual
from gentians.hypotheses import HypothesisGenerator

import pytest

from gentians import gentians as entrypoint
from gentians.algorithms import incremental_clause_genetic as incremental_search
from gentians.algorithms.result import SearchResult
from gentians.arguments import Arguments
from gentians.algorithms.incremental_clause_genetic import incremental_clause_genetic_search
from gentians.evaluation.evaluator import CandidateEvaluator
from gentians.evaluation.result import EvaluationResult
from tests.task_helpers import example, inductive_task, make_clause_space


@pytest.mark.parametrize("algorithm", ["steady_state_genetic", "incremental_clause_genetic"])
def test_unlimited_search_stops_after_all_subsets_are_evaluated(monkeypatch, algorithm):
    search = importlib.import_module(f"gentians.algorithms.{algorithm}")

    def bounded_count():
        yield from range(10)
        raise AssertionError("search kept running after the finite space was evaluated")

    monkeypatch.setattr(search, "count", bounded_count)
    args = Arguments(
        iterations_genetic=0, random_seed=1,
        population={"name": "random", "size": 2},
        incremental={"batch_size": 2, "epoch_generations": 1, "elite_count": 1},
    )
    task = inductive_task(
        [], [example(("target(c)", ""), True)], [], [], [], max_program_clauses=1,
    )
    result = getattr(search, f"{algorithm}_search")(
        args, task, make_clause_space(["target(a).", "target(b)."]),
    )
    assert not result.is_solution
    assert result.hypothesis in (("target(a).",), ("target(b).",))


def test_exhaustion_requires_all_subsets_and_a_full_active_space():
    task = inductive_task([], [], [], [], [], max_program_clauses=2)
    hypotheses = HypothesisGenerator(task, make_clause_space(["p.", "q.", "r."]), 2)
    assert not hypotheses.all_subsets_evaluated(3)  # Singles do not exhaust pairs.
    assert hypotheses.all_subsets_evaluated(6)
    hypotheses.set_available_clauses(hypotheses.encode(("p.",)))
    assert not hypotheses.all_subsets_evaluated(1)
    assert not hypotheses.all_subsets_evaluated(6)




@pytest.mark.parametrize("algorithm", ["steady_state", "incremental"])
def test_solve_selects_configured_search(monkeypatch, algorithm):
    calls = []
    result = SearchResult(("target(a).",), 1.0, True)
    monkeypatch.setattr(
        entrypoint,
        "steady_state_genetic_search",
        lambda *args: calls.append("steady") or result,
    )
    monkeypatch.setattr(
        entrypoint,
        "incremental_clause_genetic_search",
        lambda *args: calls.append("incremental") or result,
    )
    arguments = Arguments()
    arguments.algorithm = algorithm

    entrypoint.solve(inductive_task([], [], [], [], []), arguments)

    assert calls == ["incremental" if algorithm == "incremental" else "steady"]


@pytest.mark.parametrize(
    "config",
    [
        {"batch_size": 0, "epoch_generations": 1, "elite_count": 1},
        {"batch_size": 1, "epoch_generations": True, "elite_count": 1},
        {"batch_size": 1, "epoch_generations": 1, "elite_count": 4},
    ],
)
def test_incremental_search_rejects_invalid_config(config):
    arguments = Arguments(
        evaluation={"scoring": "cov_program", "constraint_inheritance": False},
        iterations_genetic=1,
        population={"name": "random", "size": 3},
        incremental=config,
    )

    with pytest.raises(ValueError, match="incremental"):
        incremental_clause_genetic_search(
            arguments,
            inductive_task([], [], [], [], []),
            make_clause_space(["target(a)."]),
        )




def _incremental_arguments(**overrides):
    return Arguments(
        evaluation={"scoring": "cov_program", "constraint_inheritance": False},
        iterations_genetic=8,
        random_seed=17,
        population={"name": "random", "size": 4},
        incremental={
            "batch_size": 4,
            "epoch_generations": 2,
            "elite_count": 2,
            **overrides,
        },
    )








@pytest.mark.parametrize("solution_stage", ["initialization", "refill"])
def test_epoch_search_stops_evaluating_at_first_perfect_candidate(
    monkeypatch, solution_stage
):
    task = inductive_task(
        [], [example(("target(a)", ""), True)], [], [], [], max_program_clauses=1
    )
    space = make_clause_space(["target(a).", "target(b).", "target(c)."])
    proposals = []

    def initialize(context):
        proposals.append(1)
        programs = (
            ["target(b)."]
            if solution_stage == "refill" and len(proposals) == 1
            else ["target(a).", "target(c)."]
        )
        return [context.hypotheses.encode((source,)) for source in programs]

    evaluated = []
    evaluate = CandidateEvaluator.__call__

    def record_evaluation(self, candidate):
        evaluated.append(tuple(str(statement) for statement in candidate))
        return evaluate(self, candidate)

    monkeypatch.setattr(incremental_search, "create_population", lambda config: initialize)
    monkeypatch.setattr(CandidateEvaluator, "__call__", record_evaluation)
    result = incremental_clause_genetic_search(_incremental_arguments(batch_size=3), task, space)
    assert result.is_solution
    assert result.hypothesis == ("target(a).",)
    assert evaluated == (
        [("target(a).",)]
        if solution_stage == "initialization"
        else [("target(b).",), ("target(a).",)]
    )

def test_retention_preserves_champion_and_exact_size():
    champion = Individual(1, 10, False, (1, 0))
    population = [Individual(2, 8, False), Individual(4, 7, False)]
    retained = retain_population(population, champion, 2)
    assert champion in retained
    assert len(retained) == 2
    assert len({item.genome for item in retained}) == 2


def test_batch_renewal_evaluates_new_bit_collision_and_reuses_retained_result(monkeypatch):
    @contextmanager
    def batches(*args):
        yield iter([make_clause_space(["m.", "z."]), make_clause_space(["a."])])

    contexts = []

    def populate(context):
        contexts.append(context)
        if len(contexts) == 1:
            return [context.hypotheses.encode((clause,)) for clause in ("m.", "z.")]
        retained = context.hypotheses.encode(("m.",))
        assert context.evaluate(retained).score == 0.4
        return [context.hypotheses.encode(("a.",))]

    evaluated = []

    def evaluate(program):
        text = tuple(map(str, program))
        evaluated.append(text)
        return EvaluationResult({("m.",): 0.4, ("z.",): 0.2, ("a.",): 0.8}[text],
                                False, (0, 0), False, True)

    monkeypatch.setattr(clause_pool, "incremental_clause_batches", batches)
    monkeypatch.setattr(incremental_search, "create_population", lambda config: populate)
    monkeypatch.setattr(incremental_search, "create_evaluator", lambda *args: evaluate)
    monkeypatch.setattr(incremental_search, "create_crossover", lambda config: lambda *args: None)
    args = _incremental_arguments(epoch_generations=1, elite_count=1)
    args.population["size"] = 2
    args.iterations_genetic = 2

    result = incremental_clause_genetic_search(args, inductive_task([], [], [], [], []))

    assert result.hypothesis == ("a.",)
    assert result.score == 0.8
    assert evaluated == [("m.",), ("z.",), ("a.",)]
    assert len(contexts) == 2
    assert contexts[0].hypotheses.encode(("m.",)) == contexts[1].hypotheses.encode(("a.",))






def test_active_space_preserves_seeds_and_closes_sampled_candidates():
    task = inductive_task(["seed(a)."], [], [], [], [])
    space = make_clause_space(
        ["p(X) :- seed(X).", "q(X) :- p(X).", "r(X) :- q(X).", "s(a)."]
    )
    hypotheses = HypothesisGenerator(task, space, max_clauses=3)
    seed = hypotheses.encode(("p(X) :- seed(X).", "q(X) :- p(X)."))
    pool = activate_clauses(hypotheses, [seed], 3, random.Random(4))
    assert pool & seed == seed
    assert pool == hypotheses.available_clauses
    assert pool.bit_count() >= 3
    for number in range(30):
        candidate = hypotheses.create(random.Random(number))
        if candidate is None:
            continue
        assert candidate & ~pool == 0
        assert candidate.bit_count() <= 3
        selected = [
            entry
            for index, entry in enumerate(hypotheses.space.entries)
            if candidate & (1 << index)
        ]
        heads = {head for entry in selected for head in entry.heads}
        deps = {dependency for entry in selected for dependency in entry.deps}
        assert deps <= heads | {("seed", 1)}


def test_restricted_sampler_preserves_ascending_rank_rng_sequence():
    hypotheses = HypothesisGenerator(
        inductive_task([], [], [], [], []),
        make_clause_space([f"p({index})." for index in range(12)]),
        max_clauses=4,
    )
    pool = sum(1 << index for index in (0, 2, 5, 6, 9, 11))
    hypotheses.set_available_clauses(pool)
    excluded = (1 << 2) | (1 << 9)
    for seed in range(30):
        actual_rng = random.Random(seed)
        reference_rng = random.Random(seed)
        remaining = pool & ~excluded
        expected = []
        while remaining:
            ids = [index for index in range(12) if remaining & (1 << index)]
            selected = ids[reference_rng.randrange(len(ids))]
            expected.append(selected)
            remaining &= ~(1 << selected)
        assert list(hypotheses._random_available(excluded, actual_rng)) == expected
        assert actual_rng.getstate() == reference_rng.getstate()


@pytest.mark.parametrize("iterations, epoch, expected", [(8, 1, False), (110, 1, True), (110, 150, False)])
def test_stagnation_restart_preserves_champion_and_stops_at_solution(monkeypatch, iterations, epoch, expected):
    from gentians.language import parse_text

    calls = []
    def population(context):
        calls.append(True)
        rules = ["p.", "r."] if len(calls) == 1 else ["q."]
        return [context.hypotheses.encode((rule,)) for rule in rules]

    monkeypatch.setattr(incremental_search, "create_population", lambda config: population)
    monkeypatch.setattr(incremental_search, "create_crossover", lambda config: lambda *args: None)
    args = _incremental_arguments(epoch_generations=epoch)
    args.iterations_genetic = iterations
    args.population["size"] = 2
    result = incremental_clause_genetic_search(
        args, parse_text("#maxpl(1). #pos({q},{})."),
        make_clause_space(["p.", "q.", "r."]),
    )
    assert result.is_solution is expected
    assert len(calls) == (2 if expected else 1)
    assert result.hypothesis == (("q.",) if expected else ("p.",))




def test_stagnation_does_not_restart_constraint_only_space(monkeypatch):
    from gentians.language import parse_text

    calls = []
    original = incremental_search.create_population
    def factory(config):
        generate = original(config)
        def populate(context):
            calls.append(True)
            return generate(context)
        return populate

    monkeypatch.setattr(incremental_search, "create_population", factory)
    monkeypatch.setattr(incremental_search, "create_crossover", lambda config: lambda *args: None)
    args = _incremental_arguments(epoch_generations=1)
    args.iterations_genetic = 110
    args.population["size"] = 2
    result = incremental_clause_genetic_search(
        args, parse_text("{a;b}. #maxpl(1). #pos({absent},{})."),
        make_clause_space([":- a.", ":- b."]),
    )
    assert not result.is_solution
    assert len(calls) == 1


@pytest.mark.parametrize("headed,solved", [(False, True), (True, False)])
def test_constraint_probes_extend_complete_program_and_stop(monkeypatch, headed, solved):
    task = inductive_task(
        ["{a;b}."], [example(("", "a,b"), True)],
        [example(("a", ""), False), example(("b", ""), False)], [], [],
        max_program_clauses=2,
    )
    space = make_clause_space([":- a.", ":- b.", *(["c."] if headed else [])])
    monkeypatch.setattr(incremental_search, "create_population", lambda config:
                        lambda context: [context.hypotheses.encode((":- a.",))])
    monkeypatch.setattr(incremental_search, "create_crossover", lambda config: lambda *args: None)
    args = _incremental_arguments(epoch_generations=50)
    args.population = {"name": "random", "size": 1}
    args.incremental["elite_count"] = 1
    result = incremental_clause_genetic_search(args, task, space)
    assert result.is_solution is solved
    if solved:
        assert set(result.hypothesis) == {":- a.", ":- b."}
