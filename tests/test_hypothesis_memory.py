import random
import tracemalloc

from gentians.hypotheses import HypothesisGenerator
from tests.task_helpers import inductive_task, make_clause_space


def constructor_memory(count):
    """Measure retained Python allocations, excluding input clauses and ASTs."""
    task = inductive_task([], [], [], [], [])
    space = make_clause_space([f"q({i})." for i in range(count)])
    tracemalloc.start()
    try:
        generator = HypothesisGenerator(task, space, 6)
        retained, _ = tracemalloc.get_traced_memory()
        assert generator.clause_count == count
        return retained
    finally:
        tracemalloc.stop()


def test_constructor_memory_scales_linearly():
    small = constructor_memory(8192)
    large = constructor_memory(16384)
    print(f"constructor retained bytes: 8192={small}, 16384={large}")
    # Allow allocator variation, but reject the quadratic singleton-mask table.
    assert large < 2.6 * small


def test_clauses_remain_independent_and_dependency_closure_is_preserved():
    generator = HypothesisGenerator(
        inductive_task(["seed."], [], [], [], []),
        make_clause_space(["p :- seed.", "q :- seed.", "target :- p."]),
        3,
    )
    target = generator.encode(("target :- p.",))
    provider = generator.encode(("p :- seed.",))
    rng = random.Random(1)
    assert generator._build(target, 0, rng) == target | provider
    assert generator._build(target, provider, rng) is None
    generator.set_available_clauses(provider)
    assert generator.create(rng) == provider
