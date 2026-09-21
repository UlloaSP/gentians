from pathlib import Path

import clingo
import pytest

from benchmarks.catalog import CASES, arguments_for
from benchmarks.export_ilasp_aggregates import (
    background_statement,
    has_body_aggregates,
    render_task,
)
from benchmarks.run_experiments import load_config
from benchmarks.run_ilasp_experiments import load_experiments
from gentians.clauses import generate_clause_space
from gentians.evaluation import create_evaluator
from gentians.gentians import task_from_arguments
from gentians.hypotheses import HypothesisGenerator
from gentians.language.parser import parse_text

ROOT = Path(__file__).resolve().parents[1]
AGGREGATES = [
    name for name in sorted(CASES)
    if has_body_aggregates(task_from_arguments(arguments_for(name)))
]


@pytest.mark.parametrize("dataset", AGGREGATES)
def test_checked_in_export_is_complete_and_current(dataset: str) -> None:
    arguments = arguments_for(dataset)
    task = task_from_arguments(arguments)
    space = generate_clause_space(task, arguments)
    exported = ROOT / "benchmarks/ilasp" / f"{dataset}.las"
    assert exported.read_text(encoding="utf-8") == render_task(task, space, Path(arguments.filename))
    assert b"\r" not in exported.read_bytes()
    assert len(space) > 0
    assert all(clause.body_literals + bool(clause.heads) > 0 for clause in space.entries)


@pytest.mark.parametrize(("dataset", "solution"), [
    ("subset_sum_triple",
     "ok(V3) :- #sum{V0,V1,V2:el(V0,V1,V2)}=V3,"
     "#sum{V0,V1,V2:el(V1,V0,V2)}=V3,#sum{V0,V1,V2:el(V1,V2,V0)}=V3."),
    ("subset_sum_double_and_prod",
     "ok(V4) :- #sum{V0,V1:el(V0,V1)}=V2,#sum{V0,V1:el(V1,V0)}=V3,V2*V3=V4."),
    ("subset_sum_double_and_prod_unbalanced",
     "ok(V4) :- #sum{V0:el(V0,V1)}=V2,#sum{V0:el(V1,V0)}=V3,V2*V3=V4."),
    ("hamming_1_unbalanced",
     ":- hd(V0),#sum{V1,V2:d(V2,V1)}=V3,V0-V3!=0."),
])
def test_previously_unsatisfiable_benchmarks_have_exported_perfect_hypotheses(dataset, solution):
    arguments = arguments_for(dataset)
    task = task_from_arguments(arguments)
    space = generate_clause_space(task, arguments)
    hypotheses = HypothesisGenerator(task, space, task.max_program_clauses or len(space))
    genome = hypotheses.encode((solution,))
    assert create_evaluator(task, arguments.evaluation)(hypotheses.program(genome)).is_solution
    clause = next(clause for clause in space.entries if clause.text == solution)
    cost = clause.body_literals + bool(clause.heads)
    assert f"{cost} ~ {solution}\n" in (ROOT / "benchmarks/ilasp" / f"{dataset}.las").read_text()


def test_singleton_choice_translation_preserves_stable_models() -> None:
    source = "{p(1)}."
    translated = background_statement(source)
    assert translated == "0 {p(1)} 1."

    def models(program):
        control = clingo.Control(["0"])
        control.add("base", [], program)
        control.ground([("base", [])])
        with control.solve(yield_=True) as handle:
            return {tuple(sorted(map(str, model.symbols(atoms=True)))) for model in handle}

    assert models(source) == models(translated) == {(), ("p(1)",)}


def test_export_preserves_included_excluded_and_context(tmp_path: Path) -> None:
    source = tmp_path / "context.txt"
    source.write_text("""
#maxv(2).
#maxbl(1).
#modeh(1,total(var(numeric,output))).
#modeb(1,#sum{var(numeric,any,x):value(var(numeric,any,x))}=var(numeric,output,s)).
#pos({total(3)}, {total(4)}, {value(1). value(2).}).
#neg({total(9)}, {total(3)}, {value(3).}).
""", newline="\n")
    task = parse_text(source.read_text())
    space = generate_clause_space(task, arguments_for("subset_sum"))
    exported = render_task(task, space, source)
    assert "#pos({total(3)}, {total(4)}, {value(1).\nvalue(2).})." in exported
    assert "#neg({total(9)}, {total(3)}, {value(3).})." in exported
    assert "2 ~ total(" in exported
    source.write_bytes(source.read_bytes().replace(b"\n", b"\r\n"))
    assert render_task(task, space, source) == exported


def test_comparison_matrix_matches_all_six_algorithms() -> None:
    ilasp = next(experiment for experiment in load_experiments(ROOT / "benchmarks/ilasp_experiments.toml")
                 if experiment.id == "all-120s-30runs")
    _, experiments = load_config(ROOT / "benchmarks/experiments.toml")
    gentians = [experiment for experiment in experiments
                if experiment["id"].startswith("ilasp-all-120s-30runs/")]
    assert len(AGGREGATES) == 20
    assert len(ilasp.datasets) == len(set(ilasp.datasets)) == 29
    assert set(AGGREGATES) <= set(ilasp.datasets)
    assert ilasp.versions == ("2", "2i", "3", "4")
    assert ilasp.runs == 30 and ilasp.timeout_seconds == 120
    assert {experiment["overrides"]["algorithm"] for experiment in gentians} == {"steady_state", "incremental"}
    for experiment in gentians:
        assert experiment["datasets"] == list(ilasp.datasets)
        assert experiment["runs"] == 30 and experiment["timeout_seconds"] == 120
        assert experiment["seed_base"] == 1
        assert not experiment.get("stop_on_timeout", False)
    for dataset in ilasp.datasets:
        content = (ilasp.task_dir / f"{dataset}.las").read_text(encoding="utf-8")
        assert (" ~ " in content) == (dataset in AGGREGATES)
