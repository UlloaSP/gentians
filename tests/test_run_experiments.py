import json

import pytest

from benchmarks.run_experiments import (
    DEFAULT_CONFIG,
    experiment_command,
    fingerprint,
    load_config,
    write_index,
    write_manifest,
)


def test_default_config_defines_comparable_experiment_matrix():
    output_root, experiments = load_config(DEFAULT_CONFIG)

    assert output_root.name == ".benchmarks"
    assert {experiment["id"] for experiment in experiments} == {
        f"{coverage}_{grounding}"
        for coverage in (
            "cov_subprograms_mean",
            "cov_subprograms_max",
            "cov_program",
        )
        for grounding in ("normal", "externals", "assumptions")
    }
    assert all(experiment["runs"] == 10 for experiment in experiments)
    assert all(experiment["timeout_seconds"] == 100 for experiment in experiments)
    assert all(experiment["cprofile"] is False for experiment in experiments)
    control = experiments[0]["overrides"]
    assert control["iterations_genetic"] > 0
    assert control["closure.name"] == "dependency"
    assert control["selection.name"] == "tournament"
    assert control["crossover.name"] == "set_mix"
    assert control["mutation.name"] == "random_group"

    assert set(control) == {
        "iterations_genetic",
        "closure.name",
        "fitness.name",
        "fitness.grounding",
        "fitness.max_as",
        "fitness.clingo_arguments",
        "population.name",
        "population.size",
        "selection.name",
        "selection.tournament_size",
        "selection.prob_selecting_fittest",
        "crossover.name",
        "crossover.probability",
        "mutation.name",
        "mutation.probability",
        "replacement.name",
        "replacement.prob_replacing_oldest",
    }


def test_pregrounded_experiments_enumerate_all_models():
    _, experiments = load_config(DEFAULT_CONFIG)
    pregrounded = [
        experiment["overrides"]
        for experiment in experiments
        if experiment["overrides"]["fitness.grounding"] != "normal"
    ]

    assert all(overrides["fitness.max_as"] == 0 for overrides in pregrounded)


def test_default_experiments_form_coverage_by_grounding_matrix():
    _, experiments = load_config(DEFAULT_CONFIG)
    matrix = {
        (
            experiment["overrides"]["fitness.name"],
            experiment["overrides"]["fitness.grounding"],
        )
        for experiment in experiments
    }
    assert matrix == {
        (coverage, grounding)
        for coverage in (
            "cov_subprograms_mean",
            "cov_subprograms_max",
            "cov_program",
        )
        for grounding in ("normal", "externals", "assumptions")
    }

    controlled_keys = set(experiments[0]["overrides"]) - {
        "fitness.name",
        "fitness.grounding",
    }
    for experiment in experiments[1:]:
        overrides = experiment["overrides"]
        assert set(overrides) - {"fitness.name", "fitness.grounding"} == controlled_keys
        assert all(
            overrides[key] == experiments[0]["overrides"][key]
            for key in controlled_keys
        )


def test_load_config_inherits_suite_and_builds_profile_command(tmp_path):
    config = tmp_path / "experiments.toml"
    config.write_text(
        '[suite]\noutput_root = ".benchmarks"\ndatasets = ["coin"]\nruns = 10\n'
        '[[experiment]]\nid = "subprogram_mean"\n'
        'overrides = { "closure.name" = "dependency", "fitness.name" = "cov_subprograms_mean" }\n',
        encoding="utf-8",
    )

    output_root, [experiment] = load_config(config)
    command = experiment_command(experiment, output_root / experiment["id"])

    assert output_root.name == ".benchmarks"
    assert experiment["runs"] == 10
    assert command[command.index("--datasets") + 1] == "coin"
    assert "closure.name=\"dependency\"" in command
    assert "fitness.name=\"cov_subprograms_mean\"" in command


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


def test_index_points_to_each_dashboard_for_lazy_comparison(tmp_path):
    experiment = {
        "id": "subprogram_mean",
        "label": "Subprogram mean",
        "description": "",
        "datasets": ["coin"],
        "runs": 2,
        "overrides": {"fitness.name": "cov_subprograms_mean"},
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
    assert indexed["dashboard_path"] == "subprogram_mean/dashboard_data.json"
    assert indexed["has_dashboard"] is True
    assert "dashboard" not in indexed
    assert indexed["fingerprint"] == fingerprint(experiment)


def test_index_marks_results_stale_when_config_changed(tmp_path):
    experiment = {
        "id": "subprogram_mean",
        "datasets": ["coin"],
        "runs": 2,
        "overrides": {"fitness.name": "cov_subprograms_mean"},
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
        "id": "subprogram_mean",
        "label": "Current label",
        "description": "current",
        "datasets": ["coin"],
        "runs": 2,
        "overrides": {"fitness.grounding": "normal"},
    }
    out_dir = tmp_path / experiment["id"]
    out_dir.mkdir()
    write_manifest(out_dir, experiment, "complete")
    experiment.update(
        runs=10,
        label="New label",
        overrides={"fitness.grounding": "externals"},
    )

    write_index(tmp_path, [experiment])

    [indexed] = json.loads((tmp_path / "experiments.json").read_text())["experiments"]
    assert indexed["status"] == "stale"
    assert indexed["runs"] == 10
    assert indexed["label"] == "New label"
    assert indexed["overrides"] == {"fitness.grounding": "externals"}
