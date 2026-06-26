import json

from benchmarks.sweep import Cell, write_sweep_outputs


def write_cell(out_dir, cell):
    cell_dir = out_dir / "cells" / cell.key
    cell_dir.mkdir(parents=True)
    (cell_dir / "runs.csv").write_text(
        "run,status,elapsed_seconds,success\n1,ok,0.5,1\n",
        encoding="utf-8",
    )
    (cell_dir / "ga_fitness.csv").write_text(
        "run,global_generation,best_so_far\n1,1,10\n1,2,12\n",
        encoding="utf-8",
    )


def test_write_sweep_outputs_discovers_existing_cell_dirs(tmp_path):
    coin = Cell("coin", "coverage_exp_mean", 1)
    sudoku = Cell("sudoku", "coverage_exp_mean", 1)
    write_cell(tmp_path, coin)
    write_cell(tmp_path, sudoku)
    manifest = {
        "datasets": ["coin"],
        "fitnessOperators": ["coverage_exp_mean"],
        "geneticIterations": [1],
        "runs": 1,
        "timeoutSeconds": 100,
        "cells": [
            {
                "dataset": coin.dataset,
                "fitness_operator": coin.fitness_operator,
                "genetic_iterations": coin.genetic_iterations,
                "key": coin.key,
            }
        ],
    }

    write_sweep_outputs(tmp_path, manifest)

    payload = json.loads((tmp_path / "sweep_dashboard_data.json").read_text())
    assert sorted({row["dataset"] for row in payload["cells"]}) == ["coin", "sudoku"]
    assert payload["meta"]["availableDatasets"] == ["coin", "sudoku"]
