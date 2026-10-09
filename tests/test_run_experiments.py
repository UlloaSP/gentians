import json
from argparse import Namespace
from pathlib import Path
from subprocess import CompletedProcess


import pytest
from benchmarks import run_experiments as runner

from benchmarks.run_experiments import (
    expand_experiments,
    experiment_command,
    experiment_output_path,
    fingerprint,
    load_config,
    summarize_experiment,
    write_index,
    write_manifest,
)


def paired_config(tmp_path, methods=None):
    path = tmp_path / "paired.toml"
    path.write_text('[suite]\noutput_root=' + json.dumps((tmp_path / "results").as_posix())
                    + '\ndatasets=["coin"]\nruns=3\ntimeout_seconds=20\n[[experiment]]\nid="paired"\n'
                    + 'methods=' + json.dumps(methods or ["gentians-steady_state", "gentians-incremental", "ilasp-2", "ilasp-2i"])
                    + '\n[tools.ilasp]\ntask_dir="benchmarks/ilasp"\n[tools.ilasp.max_body_length]\ncoin=3\n')
    return path


def test_expands_one_experiment_with_shared_tasks_and_budget(tmp_path):
    _, definitions = load_config(paired_config(tmp_path))
    expanded = expand_experiments(definitions)
    assert [item["id"] for item in expanded] == [f"paired/{method}" for method in definitions[0]["methods"]]
    assert [item["runs"] for item in expanded] == [3, 3, 1, 1]
    assert all(item["datasets"] == ["coin"] and item["timeout_seconds"] == 20 for item in expanded)
    assert expanded[1]["overrides"]["algorithm"] == "incremental"


@pytest.mark.parametrize("methods", [None, ["gentians-incremental", "ilasp-2i"], ["ilasp-4"], ["ilasp-2", "ilasp-2"]])
def test_unified_cli_dispatches_selected_methods_only(tmp_path, monkeypatch, methods):
    path = paired_config(tmp_path)
    monkeypatch.setattr(runner.sys, "argv", ["run_experiments.py", "paired", "--config", str(path),
                                            *(["--methods", *methods] if methods else [])])
    calls = []

    def execute(experiment, output):
        calls.append(experiment)
        assert output.name == experiment["method"]
        (output / "runs.csv").write_text("dataset,run,status,success\ncoin,1,ok,True\n")
        return 0

    monkeypatch.setitem(runner.RUNNERS, "gentians", execute)
    monkeypatch.setitem(runner.RUNNERS, "ilasp", execute)
    monkeypatch.setattr(runner, "execution_inputs", lambda experiment: {})
    assert runner.main() == 0
    expected = methods or ["gentians-steady_state", "gentians-incremental", "ilasp-2", "ilasp-2i"]
    assert [item["method"] for item in calls] == list(dict.fromkeys(expected))
    index = json.loads((tmp_path / "results/experiments.json").read_text())["experiments"]
    assert {item["id"] for item in index} >= {item["id"] for item in calls}


def test_method_selection_keeps_other_methods_fingerprint_and_output_path(tmp_path):
    _, definitions = load_config(paired_config(tmp_path))
    all_methods = expand_experiments(definitions)
    selected = expand_experiments(definitions, ["ilasp-2"])[0]
    assert selected == all_methods[2]
    assert fingerprint(selected) == fingerprint(all_methods[2])


def test_legacy_method_paths_do_not_depend_on_other_selected_methods(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[suite]\ndatasets=["coin"]\n[[experiment]]\nid="legacy"\n')
    _, definitions = load_config(path)
    default = expand_experiments(definitions)[0]
    assert expand_experiments(definitions, ["gentians-steady_state", "ilasp-2"])[0] == default


def test_optional_methods_stay_indexed_when_selection_changes(tmp_path, monkeypatch):
    path = paired_config(tmp_path)
    root, definitions = load_config(path)
    optional = expand_experiments(definitions, ["ilasp-4"])[0]
    output = root / optional["id"]
    output.mkdir(parents=True)
    monkeypatch.setattr(runner, "execution_inputs", lambda experiment: {})
    write_manifest(output, optional, "complete", {})
    monkeypatch.setattr(runner.sys, "argv", ["run_experiments.py", "--list", "--config", str(path)])
    assert runner.main() == 0
    indexed = json.loads((root / "experiments.json").read_text())["experiments"]
    assert any(item["id"] == optional["id"] and item["status"] == "complete" for item in indexed)


def test_index_keeps_saved_worker_runtime_but_detects_changed_code(tmp_path, monkeypatch):
    path = paired_config(tmp_path)
    root, definitions = load_config(path)
    experiment = expand_experiments(definitions)[0]
    output = root / experiment["id"]
    output.mkdir(parents=True)
    (output / "dashboard_data.json").write_text("{}")
    current_files = {"source.py": "original"}

    def inputs(experiment, *, runtime=None):
        return {"files": dict(current_files), "runtime": runtime or {"python": "host"}}

    monkeypatch.setattr(runner, "execution_inputs", inputs)
    write_manifest(output, experiment, "complete", {"files": dict(current_files), "runtime": {"python": "container"}})
    write_index(root, expand_experiments(definitions))
    saved = json.loads((root / "experiments.json").read_text())["experiments"][0]
    assert saved["status"] == "complete" and saved["has_dashboard"] is True
    assert saved["execution"]["runtime"]["python"] == "container"
    current_files["source.py"] = "changed"
    write_index(root, expand_experiments(definitions))
    saved = json.loads((root / "experiments.json").read_text())["experiments"][0]
    assert saved["status"] == "stale" and saved["has_dashboard"] is False


def test_method_output_collision_cannot_replace_another_experiment(tmp_path, monkeypatch):
    path = tmp_path / "config.toml"
    root = tmp_path / "results"
    path.write_text('[suite]\ndatasets=["coin"]\noutput_root=' + json.dumps(root.as_posix())
                    + '\n[[experiment]]\nid="comparison"\n[[experiment]]\nid="comparison-ilasp-2"\n')
    other = root / "comparison-ilasp-2"
    other.mkdir(parents=True)
    saved = other / "keep.txt"
    saved.write_text("original")
    monkeypatch.setattr(runner.sys, "argv", ["run_experiments.py", "comparison", "--config", str(path),
                                            "--methods", "ilasp-2", "--force"])
    with pytest.raises(SystemExit, match="belongs to another experiment"):
        runner.main()
    assert saved.read_text() == "original"


def test_new_backend_registers_without_changing_the_dispatch_loop(tmp_path, monkeypatch):
    monkeypatch.setitem(runner.METHODS, "fastlas", ("fastlas", ""))
    calls = []
    monkeypatch.setitem(runner.RUNNERS, "fastlas", lambda experiment, output: calls.append(experiment) or 0)
    path = paired_config(tmp_path, ["fastlas"])
    monkeypatch.setattr(runner, "parse_args", lambda: Namespace(
        config=path, experiments=["paired"], methods=None, force=False, list=False,
        summary=False, historical_index=False, rebuild_dashboards=False))
    monkeypatch.setattr(runner, "execution_inputs", lambda experiment: {})
    assert runner.main() == 0
    assert len(calls) == 1 and calls[0]["runs"] == 1 and calls[0]["tool"] == "fastlas"


def test_external_validation_failure_is_not_counted_as_success(tmp_path, monkeypatch):
    path = paired_config(tmp_path, ["ilasp-2"])
    _, definitions = load_config(path)
    effective = expand_experiments(definitions)[0]
    out = tmp_path / "results/paired/ilasp-2"
    out.mkdir(parents=True)
    monkeypatch.setattr(runner, "execution_inputs", lambda experiment: {})
    write_manifest(out, effective, "complete", {})
    (out / "runs.csv").write_text("dataset,run,status,success,total_seconds,wall_seconds\n"
                                  "coin,1,ok,False,0.5,0.7\n")
    row = summarize_experiment(effective, out)[0]
    assert row["successes"] == 0 and row["solved_total_execution_mean"] is None
    assert row["par1_wall_seconds"] == 20


def test_instrumentation_is_inherited_forwarded_and_fingerprinted(tmp_path):
    path = tmp_path / "light.toml"
    path.write_text(
        '[suite]\ndatasets=["grandparent"]\ninstrumentation="light"\n'
        '[[experiment]]\nid="control"\n', encoding="utf-8",
    )
    output_root, experiments = load_config(path)
    assert output_root == runner.REPO_ROOT / ".benchmarks" / "experiments"
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




@pytest.mark.parametrize("timeout", [0, 100])
def test_summary_penalizes_timeouts_and_keeps_net_time_of_solved_runs(tmp_path, timeout):
    experiment = {"id": "control", "datasets": ["coin"], "timeout_seconds": timeout}
    (tmp_path / "experiment.json").write_text(json.dumps({
        "fingerprint": fingerprint(experiment), "status": "completed_with_failures",
    }), encoding="utf-8")
    (tmp_path / "runs.csv").write_text(
        "dataset,run,status,success,elapsed_seconds\n"
        "coin,1,ok,True,3\ncoin,2,timeout,False,101\n", encoding="utf-8",
    )
    runs = tmp_path / "runs"
    runs.mkdir()

    def timings(run, rows):
        (runs / f"coin_run_{run}_timings.json").write_text(json.dumps([
            {"metric": metric, "seconds": seconds, "calls": calls}
            for metric, seconds, calls in rows
        ]), encoding="utf-8")

    timings(1, [("total_execution", 2, 1)])
    (runs / "coin_run_1_ga_metrics.json").write_text(json.dumps([
        {"generation": generation, "max_fitness": 0, "avg_fitness": 0, "best_so_far": 0,
         "fitness_evaluations": evaluations}
        for generation, evaluations in ((0, 10), (20, 30))
    ]), encoding="utf-8")
    summary, = summarize_experiment(
        experiment, tmp_path,
    )
    assert summary["par1_wall_seconds"] == (51.5 if timeout else None)
    assert summary["solved_total_execution_mean"] == 2
    assert summary["solved_generations_mean"] == 20
    assert summary["solved_evaluations_mean"] == 30
    assert summary["successes"] == summary["timeouts"] == 1
    assert summary["solved_grounding_mean"] is None
    assert summary["solved_python_mean"] is None
    assert summary["solved_ground_calls_mean"] is None
    timings(1, [
        ("total_execution", 2, 1),
        ("clause_generation.grounding", 0.1, 1),
        ("initialization.grounding", 0.2, 3),
        ("initialization.grounding.self", 0.2, 3),
        ("initialization.solving", 0.4, 4),
        ("initialization.closure", 0.5, 10),
    ])
    timings(2, [("initialization.grounding", 90, 10000)])
    summary, = summarize_experiment(experiment, tmp_path)
    assert summary["solved_grounding_mean"] == pytest.approx(0.3)
    assert summary["solved_solving_mean"] == pytest.approx(0.4)
    assert summary["solved_closure_mean"] == pytest.approx(0.5)
    assert summary["solved_python_mean"] == pytest.approx(0.8)
    assert summary["solved_ground_calls_mean"] == 4
    assert summary["solved_solve_calls_mean"] == 4


def test_summary_rejects_stale_or_incomplete_runs(tmp_path):
    experiment = {"id": "control", "datasets": ["coin"], "timeout_seconds": 100}
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
        config=config, experiments=["group/control"], force=True, list=False,
        summary=False, historical_index=False, rebuild_dashboards=False))
    commands = []
    def run(command, **kwargs):
        commands.append(command)
        return CompletedProcess(command, 0)
    monkeypatch.setattr(runner.subprocess, "run", run)
    monkeypatch.setattr(runner, "execution_inputs", lambda experiment: {})
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


@pytest.mark.parametrize("original_status", ["completed_with_failures", "stale"])
def test_historical_index_preserves_saved_runs_and_provenance(tmp_path, original_status):
    experiment = {"id": "saved", "datasets": ["coin"], "runs": 300, "overrides": {}}
    out_dir = tmp_path / "saved"
    out_dir.mkdir()
    write_manifest(out_dir, experiment, original_status)
    manifest_path = out_dir / "experiment.json"
    original = manifest_path.read_bytes()
    (out_dir / "dashboard_data.json").write_text('{"schemaVersion":10}')
    experiment["runs"] = 30

    write_index(tmp_path, [experiment], historical_ids={"saved"})

    [indexed] = json.loads((tmp_path / "experiments.json").read_text())["experiments"]
    assert indexed["runs"] == 300
    assert indexed["status"] == "historical"
    assert indexed["original_status"] == original_status
    assert indexed["has_dashboard"] is True
    assert indexed["fingerprint"] == json.loads(original)["fingerprint"]
    assert manifest_path.read_bytes() == original


def test_historical_index_keeps_experiments_already_marked_historical(
    tmp_path, monkeypatch,
):
    experiment_ids = (
        "sdk-defaults/steady_state",
        "sdk-defaults/incremental",
        "ilasp/steady_state",
        "ilasp/incremental",
    )
    config = tmp_path / "experiments.toml"
    config.write_text(
        '[suite]\noutput_root = "' + tmp_path.as_posix() + '"\n'
        'datasets = ["coin"]\n'
        + "\n".join(
            f'[[experiment]]\nid = "{experiment_id}"'
            for experiment_id in experiment_ids
        ),
        encoding="utf-8",
    )
    for experiment_id in experiment_ids:
        out_dir = tmp_path / experiment_id
        out_dir.mkdir(parents=True)
        (out_dir / "experiment.json").write_text(json.dumps({
            "id": experiment_id,
            "datasets": ["coin"],
            "runs": 10,
            "overrides": {},
            "fingerprint": "old",
            "status": "complete",
        }), encoding="utf-8")
        (out_dir / "dashboard_data.json").write_text(
            '{"schemaVersion": 10}', encoding="utf-8",
        )
    (tmp_path / "experiments.json").write_text(json.dumps({
        "experiments": [
            {"id": experiment_id, "status": "historical"}
            for experiment_id in experiment_ids[:2]
        ],
    }), encoding="utf-8")
    monkeypatch.setattr(runner, "parse_args", lambda: Namespace(
        config=config,
        experiments=list(experiment_ids[2:]),
        force=False,
        list=False,
        summary=False,
        historical_index=True, rebuild_dashboards=False,
    ))

    assert runner.main() == 0

    indexed = json.loads((tmp_path / "experiments.json").read_text())["experiments"]
    assert {row["id"] for row in indexed if row["status"] == "historical"} == set(
        experiment_ids
    )


def test_rerun_or_list_keeps_other_historical_results(tmp_path):
    saved = {"id": "saved", "datasets": ["coin"], "runs": 10, "overrides": {}}
    out_dir = tmp_path / "saved"
    out_dir.mkdir()
    write_manifest(out_dir, saved, "complete")
    (out_dir / "dashboard_data.json").write_text('{"schemaVersion":10}')
    saved["runs"] = 30  # The configuration changed after the saved run.
    write_index(tmp_path, [saved], historical_ids={"saved"})

    write_index(tmp_path, [saved])

    [indexed] = json.loads((tmp_path / "experiments.json").read_text())["experiments"]
    assert indexed["status"] == "historical"
    assert indexed["has_dashboard"] is True


def test_rerun_with_current_config_is_no_longer_historical(tmp_path):
    experiment = {"id": "saved", "datasets": ["coin"], "runs": 10, "overrides": {}}
    out_dir = tmp_path / "saved"
    out_dir.mkdir()
    write_manifest(out_dir, experiment, "complete")
    (out_dir / "dashboard_data.json").write_text('{"schemaVersion":14}')
    (tmp_path / "experiments.json").write_text(
        json.dumps({"experiments": [{"id": "saved", "status": "historical"}]})
    )

    write_index(tmp_path, [experiment])

    [indexed] = json.loads((tmp_path / "experiments.json").read_text())["experiments"]
    assert indexed["status"] == "complete"
