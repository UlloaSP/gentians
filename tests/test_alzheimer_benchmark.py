import pytest

from benchmarks.catalog import arguments_for
from gentians.language import parse_file


@pytest.mark.parametrize(
    ("name", "background", "positive", "negative", "body_modes"),
    [
        ("acetyl", 632, 530, 530, 30),
        ("amine", 628, 274, 274, 31),
        ("mem", 628, 256, 256, 31),
        ("toxic", 628, 354, 354, 31),
    ],
)
def test_alzheimer_tasks_keep_source_facts_examples_and_bias(
    name, background, positive, negative, body_modes
):
    task = parse_file(arguments_for(f"alzheimer_{name}").filename)

    assert len(task.background) == background
    assert len(task.positive_examples) == positive
    assert len(task.negative_examples) == negative
    assert len(task.language_bias_head) == 1
    assert len(task.language_bias_body) == body_modes
    assert task.max_body_literals == 5
    assert task.max_program_clauses == 3
