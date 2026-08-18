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
        "cov_subprograms_mean",
        "cov_subprograms_max",
        "cov_program",
        "cov_program_random_group_pop10_mut005",
        "cov_program_random_group_pop10_mut09",
        "cov_program_random_group_pop100_mut005",
        "cov_program_random_group_pop100_mut09",
        "cov_program_structural_neighbor_pop10_mut005",
        "cov_program_structural_neighbor_pop10_mut09",
        "cov_program_structural_neighbor_pop100_mut005",
        "cov_program_structural_neighbor_pop100_mut09",
    }
    assert all(experiment["runs"] == 10 for experiment in experiments)
    assert all(experiment["timeout_seconds"] == 100 for experiment in experiments)
    assert all(experiment["cprofile"] is False for experiment in experiments)
    assert all("fitness.grounding" not in experiment["overrides"] for experiment in experiments)


def test_default_experiments_have_no_pregrounding_strategy_matrix():
    _, experiments = load_config(DEFAULT_CONFIG)
    assert all("fitness.grounding" not in item["overrides"] for item in experiments)
    assert len(experiments) == 11


def test_default_experiments_cover_mutation_population_probability_matrix():
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
        (mutation, population, probability)
        for mutation in ("random_group", "structural_neighbor")
        for population in (10, 100)
        for probability in (0.05, 0.9)
    }


def test_default_experiments_cover_all_fitness_operators():
    _, experiments = load_config(DEFAULT_CONFIG)
    names = {
        experiment["overrides"].get("fitness.name", "cov_subprograms_mean")
        for experiment in experiments
    }
    assert names == {"cov_subprograms_mean", "cov_subprograms_max", "cov_program"}


def test_trigram_cov_matches_random_group_baseline_conditions():
    _, experiments = load_config(DEFAULT_CONFIG)
    indexed = {experiment["id"]: experiment for experiment in experiments}
    baseline = dict(indexed["cov_program_random_group_pop10_mut09"]["overrides"])
    trigram = dict(indexed["trigram_cov"]["overrides"])

    assert baseline.pop("fitness.name") == "cov_program"
    assert trigram.pop("fitness.name") == "trigram_cov"
    assert trigram == baseline
    assert indexed["cov_program_random_group_pop10_mut09"]["runs"] == 30
    assert indexed["trigram_cov"]["runs"] == 30


def test_load_config_inherits_suite_and_builds_profile_command(tmp_path):
    config = tmp_path / "experiments.toml"
    config.write_text(
        '[suite]\noutput_root = ".benchmarks"\ndatasets = ["coin"]\nruns = 10\n'
        '[[experiment]]\nid = "subprogram_mean"\n'
        'overrides = { "fitness.name" = "cov_subprograms_mean" }\n',
        encoding="utf-8",
    )

    output_root, [experiment] = load_config(config)
    command = experiment_command(experiment, output_root / experiment["id"])

    assert output_root.name == ".benchmarks"
    assert experiment["runs"] == 10
    assert command[command.index("--datasets") + 1] == "coin"
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


def test_index_points_to_each_dashboard_for_comparison(tmp_path):
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
        "overrides": {"fitness.name": "cov_subprograms_mean"},
    }
    out_dir = tmp_path / experiment["id"]
    out_dir.mkdir()
    write_manifest(out_dir, experiment, "complete")
    experiment.update(
        runs=10,
        label="New label",
        overrides={"fitness.name": "cov_program"},
    )

    write_index(tmp_path, [experiment])

    [indexed] = json.loads((tmp_path / "experiments.json").read_text())["experiments"]
    assert indexed["status"] == "stale"
    assert indexed["runs"] == 10
    assert indexed["label"] == "New label"
    assert indexed["overrides"] == {"fitness.name": "cov_program"}
