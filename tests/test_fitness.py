from gentians.evolution.fitness.coverage_exp_max import coverage_exp_max
from gentians.rule_generation.program import Example, Program


def test_coverage_exp_max_checks_all_models_before_best_found():
    program = Program(
        ["base."],
        [Example(("target", ""), True)],
        [Example(("target", ""), False)],
        [],
        [],
    )

    score, best_found, indexes = coverage_exp_max(program, 0, [], -2000)(
        [0],
        [0],
        ["target :- base."],
    )

    assert score == 1.0
    assert best_found is False
    assert indexes == []
