import gc
import random
import weakref

import pytest

from gentians.algorithms import epoch_pool_genetic as search
from gentians.arguments import Arguments
from gentians.clauses import generate_clause_space, sample_clause_space
from gentians.language import parse_text
from gentians.language import parse_file
from benchmarks.catalog import CASES
from tests.task_helpers import example, inductive_task, make_clause_space


def test_sample_is_bounded_legal_and_seeded():
    filename = CASES["grandparent"].filename
    assert filename is not None
    task = parse_file(filename)
    args = Arguments()
    full = generate_clause_space(task, args)
    first = sample_clause_space(task, args, 8, random.Random(12))
    second = sample_clause_space(task, args, 8, random.Random(12))
    assert 0 < len(first) <= 8
    assert first.clauses == second.clauses
    assert set(first.clauses) <= set(full.clauses)


@pytest.mark.parametrize("size", [0, -1, True, 1.5])
def test_invalid_batch_size(size):
    with pytest.raises(ValueError, match="positive integer"):
        sample_clause_space(parse_text(""), Arguments(), size, random.Random(1))


def test_sampled_epochs_drop_old_spaces_and_never_enumerate_all(monkeypatch):
    references = []
    batches = []
    original = search.HypothesisGenerator

    def generator(*args):
        result = original(*args)
        assert len(result.space) <= 4  # Two new clauses plus one two-clause elite.
        references.append(weakref.ref(result))
        return result

    def sample(_task, _args, size, _rng):
        assert size == 2
        gc.collect()
        assert sum(reference() is not None for reference in references) <= 1
        index = len(batches)
        batch = make_clause_space([f"target(a{index}).", f"target(b{index})."])
        batches.append(batch.clauses)
        return batch

    def exhaustive(*_args):
        pytest.fail("sampled search must not enumerate the full ClauseSpace")

    monkeypatch.setattr(search, "HypothesisGenerator", generator)
    monkeypatch.setattr(search, "sample_clause_space", sample)
    monkeypatch.setattr(search, "generate_clause_space", exhaustive)
    task = inductive_task([], [example(("target(z)", ""), True)], [], [], [],
                          max_program_clauses=2)
    args = Arguments(iterations_genetic=4, random_seed=4,
                     evaluation={"scoring": "cov_program", "constraint_inheritance": False},
                     population={"name": "random", "size": 3},
                     clause_pool={"enabled": True, "size": 2,
                                  "epoch_generations": 1, "elite_count": 1})
    result = search.epoch_pool_genetic_search(args, task)
    assert len(batches) == 4
    assert set(result.hypothesis) <= {text for batch in batches for text in batch}
    gc.collect()
    assert all(reference() is None for reference in references)
