import json
from argparse import Namespace
from pathlib import Path
from subprocess import CompletedProcess

import pytest
from benchmarks import run_experiments as runner

from benchmarks.run_experiments import (
    DEFAULT_CONFIG,
    experiment_command,
    experiment_output_path,
    fingerprint,
    load_config,
    summarize_experiment,
    write_index,
    write_manifest,
)


def test_instrumentation_is_inherited_forwarded_and_fingerprinted(tmp_path):
    path = tmp_path / "light.toml"
    path.write_text(
        '[suite]\ndatasets=["grandparent"]\ninstrumentation="light"\n'
        '[[experiment]]\nid="control"\n', encoding="utf-8",
    )
    _, experiments = load_config(path)
    experiment = experiments[0]
    assert experiment["instrumentation"] == "light"
    command = experiment_command(experiment, tmp_path)
    assert command[command.index("--instrumentation") + 1] == "light"
    assert fingerprint(experiment) != fingerprint({**experiment, "instrumentation": "full"})
    path.write_text(path.read_text().replace('"light"', '"invalid"'))
    with pytest.raises(ValueError, match="instrumentation"):
        load_config(path)


def test_timeout_stop_is_forwarded_and_fingerprinted(tmp_path):
    path = tmp_path / "stop.toml"
    path.write_text('[suite]\ndatasets=["grandparent"]\n'
                    '[[experiment]]\nid="control"\nstop_on_timeout=true\n', encoding="utf-8")
    _, experiments = load_config(path)
    experiment = experiments[0]
    assert "--stop-on-timeout" in experiment_command(experiment, tmp_path)
    assert fingerprint(experiment) != fingerprint({**experiment, "stop_on_timeout": False})
    path.write_text(path.read_text().replace("stop_on_timeout=true", 'stop_on_timeout="yes"'))
    with pytest.raises(ValueError, match="stop_on_timeout"):
        load_config(path)


def test_pool_policy_matrix_is_unlimited_and_has_single_policy_ablations():
    _, entries = load_config(DEFAULT_CONFIG)
    experiments = [{**entry, "id": entry["id"].removeprefix("pool-policy/")}
                   for entry in entries if entry["id"].startswith("pool-policy/")]
    variants = {entry["id"]: entry["overrides"] for entry in experiments}
    assert len(variants) == 9
    for entry in experiments:
        assert entry["runs"] == 10
        assert entry["timeout_seconds"] == 100
        assert entry["instrumentation"] == "light"
        assert entry["overrides"]["iterations_genetic"] == 0
    comparisons = [
        ("pool_fresh", "pool_persistent", "clause_pool.solver"),
        ("pool_persistent", "behavior", "clause_pool.retention"),
        ("behavior", "reproductive_retention", "clause_pool.retention"),
        ("behavior", "neighbors", "clause_pool.filling"),
        ("behavior", "adaptive", "clause_pool.renewal"),
        ("control", "reproductive_selection", "selection.name"),
    ]
    for first, second, changed_key in comparisons:
        assert {key for key in variants[first] if variants[first][key] != variants[second][key]} == {changed_key}


def test_summary_penalizes_timeouts_and_keeps_net_time_of_solved_runs(tmp_path):
    experiment = {"id": "control", "datasets": ["d"], "timeout_seconds": 100}
    (tmp_path / "experiment.json").write_text(json.dumps({
        "fingerprint": fingerprint(experiment), "status": "completed_with_failures",
    }), encoding="utf-8")
    (tmp_path / "runs.csv").write_text(
        "dataset,run,status,success,elapsed_seconds\n"
        "d,1,ok,True,3\nd,2,timeout,False,101\n", encoding="utf-8",
    )
    (tmp_path / "timings_raw.csv").write_text(
        "dataset,run,metric,seconds\nd,1,total_execution,2\n", encoding="utf-8",
    )
    (tmp_path / "ga_fitness.csv").write_text(
        "dataset,run,generation,fitness_evaluations\nd,1,0,10\nd,1,20,30\n",
        encoding="utf-8",
    )
    summary, = summarize_experiment(
        experiment, tmp_path,
    )
    assert summary["par1_wall_seconds"] == 51.5
    assert summary["solved_total_execution_mean"] == 2
    assert summary["solved_generations_mean"] == 20
    assert summary["solved_evaluations_mean"] == 30
    assert summary["successes"] == summary["timeouts"] == 1
    assert summary["solved_grounding_mean"] is None
    assert summary["solved_python_mean"] is None
    assert summary["solved_ground_calls_mean"] is None
    (tmp_path / "timings_raw.csv").write_text(
        "dataset,run,metric,seconds,calls\n"
        "d,1,total_execution,2,1\n"
        "d,1,clause_generation.grounding,0.1,1\n"
        "d,1,initialization.grounding,0.2,3\n"
        "d,1,initialization.grounding.self,0.2,3\n"
        "d,1,initialization.solving,0.4,4\n"
        "d,1,initialization.closure,0.5,10\n"
        "d,2,initialization.grounding,90,10000\n", encoding="utf-8",
    )
    summary, = summarize_experiment(experiment, tmp_path)
    assert summary["solved_grounding_mean"] == pytest.approx(0.3)
    assert summary["solved_solving_mean"] == pytest.approx(0.4)
    assert summary["solved_closure_mean"] == pytest.approx(0.5)
    assert summary["solved_python_mean"] == pytest.approx(0.8)
    assert summary["solved_ground_calls_mean"] == 4
    assert summary["solved_solve_calls_mean"] == 4


def test_summary_rejects_stale_or_incomplete_runs(tmp_path):
    experiment = {"id": "control", "datasets": ["d"], "timeout_seconds": 100}
    assert summarize_experiment(experiment, tmp_path) == []
    (tmp_path / "runs.csv").write_text("dataset,run,status\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing manifest"):
        summarize_experiment(experiment, tmp_path)
    manifest = tmp_path / "experiment.json"
    manifest.write_text(json.dumps({"fingerprint": "old", "status": "complete"}), encoding="utf-8")
    with pytest.raises(ValueError, match="stale config"):
        summarize_experiment(experiment, tmp_path)
    manifest.write_text(json.dumps({
        "fingerprint": fingerprint(experiment), "status": "failed",
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="incomplete experiment"):
        summarize_experiment(experiment, tmp_path)


def test_default_config_defines_comparable_experiment_matrix():
    output_root, experiments = load_config(DEFAULT_CONFIG)

    assert output_root.name == ".benchmarks"
    assert {experiment["id"] for experiment in experiments if "/" not in experiment["id"]} == {
        "cov_program_random_group_pop10_mut09",
        "cov_program_behavior_tournament_pop10",
        "cov_program_behavior_tournament_pop100",
        "cov_balanced",
        "cov_balanced_structural",
    }
    assert all(experiment["runs"] == 10 for experiment in experiments)
    assert all(experiment["timeout_seconds"] == (
        300 if experiment["id"].startswith(("sampled-roles/", "shared-variation/", "directed-exploration/")) else 100
    ) for experiment in experiments)
    assert all(experiment["cprofile"] is False for experiment in experiments)
    assert all(
        "evaluation.grounding" not in experiment["overrides"]
        for experiment in experiments
    )


def test_default_experiments_have_no_pregrounding_strategy_matrix():
    _, experiments = load_config(DEFAULT_CONFIG)
    assert all("evaluation.grounding" not in item["overrides"] for item in experiments)
    assert len(experiments) == 30
    assert {prefix: sum(e["id"].startswith(prefix + "/") for e in experiments)
            for prefix in ("epoch-pool", "pool-policy", "sampled-roles", "shared-variation")} == {
        "epoch-pool": 7, "pool-policy": 9, "sampled-roles": 3, "shared-variation": 2,
    }


def test_consolidation_preserves_existing_selection_settings():
    _, experiments = load_config(DEFAULT_CONFIG)
    indexed = {e["id"]: e["overrides"]["selection.name"] for e in experiments}
    assert indexed["cov_program_random_group_pop10_mut09"] == "lexicase"
    assert indexed["cov_balanced"] == "tournament"
    assert indexed["pool-policy/reproductive_selection"] == "reproductive_lexicase"


def test_default_experiments_cover_configured_mutation_population_matrix():
    _, experiments = load_config(DEFAULT_CONFIG)
    matrix = {
        (
            experiment["overrides"]["mutation.name"],
            experiment["overrides"]["population.size"],
            experiment["overrides"]["mutation.probability"],
        )
        for experiment in experiments
        if "population.size" in experiment["overrides"]
    }

    assert matrix == {
        ("random_group", 10, 0.9),
        ("random_group", 100, 0.9),
    }


def test_default_experiments_cover_all_fitness_operators():
    _, experiments = load_config(DEFAULT_CONFIG)
    names = {
        experiment["overrides"].get("evaluation.scoring", "cov_program")
        for experiment in experiments
    }
    assert names == {"cov_program", "cov_balanced"}


def test_existing_balanced_configuration_keeps_its_distinct_selection():
    _, experiments = load_config(DEFAULT_CONFIG)
    indexed = {experiment["id"]: experiment for experiment in experiments}
    baseline = dict(indexed["cov_program_random_group_pop10_mut09"]["overrides"])
    balanced = dict(indexed["cov_balanced"]["overrides"])

    assert baseline.pop("evaluation.scoring") == "cov_program"
    assert balanced.pop("evaluation.scoring") == "cov_balanced"
    assert baseline.pop("selection.name") == "lexicase"
    assert balanced.pop("selection.name") == "tournament"
    assert balanced == baseline
    assert indexed["cov_program_random_group_pop10_mut09"]["runs"] == 10
    assert indexed["cov_balanced"]["runs"] == 10


def test_load_config_inherits_suite_and_builds_profile_command(tmp_path):
    config = tmp_path / "experiments.toml"
    config.write_text(
        '[suite]\noutput_root = ".benchmarks"\ndatasets = ["coin"]\nruns = 10\n'
        '[[experiment]]\nid = "whole_program"\n'
        'overrides = { "evaluation.scoring" = "cov_program" }\n',
        encoding="utf-8",
    )

    output_root, [experiment] = load_config(config)
    command = experiment_command(experiment, output_root / experiment["id"])

    assert output_root.name == ".benchmarks"
    assert experiment["runs"] == 10
    assert command[command.index("--datasets") + 1] == "coin"
    assert 'evaluation.scoring="cov_program"' in command


def test_load_config_rejects_path_like_and_duplicate_ids(tmp_path):
    config = tmp_path / "experiments.toml"
    config.write_text(
        '[suite]\ndatasets = ["coin"]\n'
        '[[experiment]]\nid = "../bad"\n'
        '[[experiment]]\nid = "../bad"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid experiment id"):
        load_config(config)


@pytest.mark.parametrize("identifier", ["../bad", "/absolute", "a/../b", "a//b", "a/", "C:/bad", "a\\b", "."])
def test_namespaced_ids_reject_unsafe_paths(tmp_path, identifier):
    config = tmp_path / "config.toml"
    config.write_text('[suite]\ndatasets=["coin"]\n[[experiment]]\nid='
                      + json.dumps(identifier), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid experiment id"):
        load_config(config)


@pytest.mark.parametrize("ids", [("a", "a/b"), ("a/b", "a"), ("a/b", "a/b")])
def test_experiments_cannot_share_or_contain_output_directories(tmp_path, ids):
    config = tmp_path / "config.toml"
    config.write_text('[suite]\ndatasets=["coin"]\n' + "\n".join(
        f'[[experiment]]\nid="{identifier}"' for identifier in ids
    ), encoding="utf-8")
    with pytest.raises(ValueError, match="overlapping|duplicate"):
        load_config(config)


def test_namespaced_index_keeps_nested_dashboard_path_and_marks_old_id_stale(tmp_path):
    out_dir = tmp_path / "pool-policy" / "control"
    out_dir.mkdir(parents=True)
    previous = {"id": "control", "datasets": ["coin"], "runs": 10, "overrides": {}}
    write_manifest(out_dir, previous, "complete")
    (out_dir / "dashboard_data.json").write_text("{}", encoding="utf-8")
    current = {**previous, "id": "pool-policy/control"}
    write_index(tmp_path, [current])
    row, = json.loads((tmp_path / "experiments.json").read_text())["experiments"]
    assert row["dashboard_path"] == "pool-policy/control/dashboard_data.json"
    assert row["status"] == "stale"
    assert json.loads((out_dir / "experiment.json").read_text())["id"] == "control"


def test_output_path_rejects_links_even_to_another_directory_inside_root(tmp_path):
    destination = tmp_path / "other"
    destination.mkdir()
    link = tmp_path / "alias"
    try:
        link.symlink_to(destination, target_is_directory=True)
    except OSError:
        pytest.skip("creating symlinks requires OS privileges")
    with pytest.raises(ValueError, match="Unsafe output path"):
        experiment_output_path(tmp_path, "alias/control")


def test_force_replaces_only_selected_namespaced_output(tmp_path, monkeypatch):
    root = tmp_path / "results"
    chosen = root / "group" / "control"
    sibling = root / "group" / "other"
    chosen.mkdir(parents=True)
    sibling.mkdir()
    (chosen / "old").write_text("remove")
    (sibling / "keep").write_text("retain")
    config = tmp_path / "config.toml"
    config.write_text('[suite]\noutput_root=' + json.dumps(root.as_posix())
                      + '\ndatasets=["coin"]\n[[experiment]]\nid="group/control"\n',
                      encoding="utf-8")
    monkeypatch.setattr(runner, "parse_args", lambda: Namespace(
        config=config, experiments=["group/control"], force=True, list=False, summary=False))
    commands = []
    def run(command, **kwargs):
        commands.append(command)
        return CompletedProcess(command, 0)
    monkeypatch.setattr(runner.subprocess, "run", run)
    assert runner.main() == 0
    assert not (chosen / "old").exists()
    assert (sibling / "keep").read_text() == "retain"
    assert Path(commands[0][commands[0].index("--out-dir") + 1]) == chosen


def test_index_points_to_each_dashboard_for_comparison(tmp_path):
    experiment = {
        "id": "whole_program",
        "label": "Whole program",
        "description": "",
        "datasets": ["coin"],
        "runs": 2,
        "overrides": {"evaluation.scoring": "cov_program"},
    }
    out_dir = tmp_path / experiment["id"]
    out_dir.mkdir()
    (out_dir / "dashboard_data.json").write_text(
        json.dumps({"benchmarks": [{"name": "coin"}]}), encoding="utf-8"
    )
    write_manifest(out_dir, experiment, "complete")

    write_index(tmp_path, [experiment])

    [indexed] = json.loads((tmp_path / "experiments.json").read_text())["experiments"]
    assert indexed["status"] == "complete"
    assert indexed["dashboard_path"] == "whole_program/dashboard_data.json"
    assert indexed["has_dashboard"] is True
    assert "dashboard" not in indexed
    assert indexed["fingerprint"] == fingerprint(experiment)


def test_index_marks_results_stale_when_config_changed(tmp_path):
    experiment = {
        "id": "whole_program",
        "datasets": ["coin"],
        "runs": 2,
        "overrides": {"evaluation.scoring": "cov_program"},
    }
    out_dir = tmp_path / experiment["id"]
    out_dir.mkdir()
    write_manifest(out_dir, experiment, "complete")
    (out_dir / "dashboard_data.json").write_text("{}", encoding="utf-8")
    experiment["runs"] = 3

    write_index(tmp_path, [experiment])

    [indexed] = json.loads((tmp_path / "experiments.json").read_text())["experiments"]
    assert indexed["status"] == "stale"
    assert indexed["runs"] == 3
    assert indexed["has_dashboard"] is False


def test_stale_index_describes_current_config_not_old_manifest(tmp_path):
    experiment = {
        "id": "whole_program",
        "label": "Current label",
        "description": "current",
        "datasets": ["coin"],
        "runs": 2,
        "overrides": {"evaluation.scoring": "cov_program"},
    }
    out_dir = tmp_path / experiment["id"]
    out_dir.mkdir()
    write_manifest(out_dir, experiment, "complete")
    experiment.update(
        runs=10,
        label="New label",
        overrides={"evaluation.scoring": "cov_program"},
    )

    write_index(tmp_path, [experiment])

    [indexed] = json.loads((tmp_path / "experiments.json").read_text())["experiments"]
    assert indexed["status"] == "stale"
    assert indexed["runs"] == 10
    assert indexed["label"] == "New label"
    assert indexed["overrides"] == {"evaluation.scoring": "cov_program"}
