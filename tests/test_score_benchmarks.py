from pathlib import Path

import clingo
import pytest

from benchmarks.catalog import arguments_for
from benchmarks.check_hypothesis import example_program
from benchmarks.generate_score_tasks import COUNTS, GENERATORS, ROOT, task_sources
from benchmarks.run_experiments import DEFAULT_CONFIG, expand_experiments, load_config
from gentians.clauses import generate_clause_space
from gentians.evaluation import create_evaluator
from gentians.language import parse_file
from gentians.language.asp import parse_program, render_program


@pytest.mark.parametrize("name,sources", task_sources().items())
def test_score_tasks_are_reproducible_and_the_reference_is_independently_valid(name, sources):
    directory = ROOT / name
    for filename, content in sources.items():
        assert (directory / filename).read_text(encoding="utf-8") == content
    task = parse_file(str(directory))
    expected = COUNTS[name.removeprefix("score_coloring_")]
    assert (len(task.positive_examples), len(task.negative_examples)) == expected
    assert len({example.deduplication_key for example in
                (*task.positive_examples, *task.negative_examples)}) == sum(expected)
    background = "\n".join(render_program(task.background))
    for example in (*task.positive_examples, *task.negative_examples):
        control = clingo.Control(["--models=1"], logger=lambda *_: None)
        control.add("base", [], example_program(background, sources["reference.lp"], example))
        control.ground([("base", [])])
        assert control.solve().satisfiable is example.positive


@pytest.mark.parametrize("variant", COUNTS)
def test_every_reference_rule_and_constraint_is_needed(variant):
    directory = ROOT / f"score_coloring_{variant}"
    task = parse_file(str(directory))
    reference = parse_program((directory / "reference.lp").read_text())
    evaluate = create_evaluator(task, {"scoring": "cov_program"})
    assert evaluate(reference).is_solution
    assert not evaluate(reference[:1]).is_consistent
    assert not evaluate(reference[1:]).is_complete
    for index in range(len(reference)):
        assert not evaluate(reference[:index] + reference[index + 1:]).is_solution


def test_reference_survives_real_clause_generation():
    args = arguments_for("score_coloring_balanced", ["clause_generation.clingo_arguments=[]"])
    task = parse_file(args.filename)
    space = generate_clause_space(task, args)

    def signature(rule):
        return str(rule.head), frozenset(map(str, rule.body))

    generated = {signature(entry.statement) for entry in space.entries}
    source = (Path(args.filename) / "reference.lp").read_text().replace("X", "V0").replace("Y", "V1")
    assert {signature(rule) for rule in parse_program(source)} <= generated


def test_real_asp_hypotheses_reverse_rank_when_positives_get_ten_times_the_weight():
    task = parse_file(str(ROOT / "score_coloring_balanced"))
    conservative = parse_program("\n".join((*GENERATORS,
        ":- edge(X,Y), red(X), blue(Y).",
        ":- edge(X,Y), green(X), red(Y).",
        ":- edge(X,Y), blue(X), green(Y).",
    )))
    permissive = parse_program("\n".join((*GENERATORS,
        ":- edge(X,Y), red(X), red(Y).",
        ":- edge(X,Y), red(X), blue(Y).",
        ":- edge(X,Y), blue(X), red(Y).",
    )))
    balanced = create_evaluator(task, {"scoring": "cov_program"})
    weighted = create_evaluator(task, {"scoring": "cov_program", "positive_weight": 10})
    first, second = balanced(conservative), balanced(permissive)
    assert (first.behavior[0].bit_count(), first.behavior[1].bit_count()) == (3, 0)
    assert (second.behavior[0].bit_count(), second.behavior[1].bit_count()) == (6, 7)
    assert first.score > second.score
    assert weighted(conservative).score < weighted(permissive).score


def test_local_score_experiments_change_only_population_and_positive_weight():
    _, definitions = load_config(DEFAULT_CONFIG)
    experiments = expand_experiments(definitions)
    assert len(experiments) == 4
    observed = set()
    controls = []
    for experiment in experiments:
        assert experiment["method"] == "gentians-steady_state"
        assert experiment["runs"] == 5 and experiment["timeout_seconds"] == 300
        assert experiment["instrumentation"] == "full"
        overrides = dict(experiment["overrides"])
        observed.add((overrides.pop("population.size"), overrides.pop("evaluation.positive_weight")))
        assert overrides["evaluation.negative_weight"] == 1
        assert overrides["selection.name"] == "tournament"
        controls.append((experiment["datasets"], overrides))
    assert observed == {(10, 1), (10, 10), (100, 1), (100, 10)}
    assert all(control == controls[0] for control in controls)
