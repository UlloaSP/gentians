from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean, stdev


REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE_BASELINE = REPO_ROOT / "benchmarks" / "profile_baseline.py"
DEFAULT_GRID = [1, 10, 100, 1000, 2000]


@dataclass(frozen=True)
class Cell:
    dataset: str
    fitness_operator: str
    outer_iterations: int
    genetic_iterations: int

    @property
    def key(self) -> str:
        return (
            f"{self.dataset}__{self.fitness_operator}"
            f"__outer-{self.outer_iterations}__genetic-{self.genetic_iterations}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run GENTIANS parameter sweeps and aggregate dashboard data."
    )
    parser.add_argument("--datasets", nargs="+", default=["coin"])
    parser.add_argument("--outer-iterations", nargs="+", type=int, default=DEFAULT_GRID)
    parser.add_argument("--genetic-iterations", nargs="+", type=int, default=DEFAULT_GRID)
    parser.add_argument(
        "--fitness-operators",
        nargs="+",
        default=["coverage_exp_mean", "coverage_exp_max"],
    )
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=int, default=100)
    parser.add_argument("--seed-base", type=int, default=1)
    parser.add_argument("--population", type=int)
    parser.add_argument("--samples", type=int)
    parser.add_argument("--python", default=_default_python())
    parser.add_argument("--out-dir", type=Path, default=Path(".benchmarks") / "sweeps" / "latest")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--plots-only", action="store_true")
    args = parser.parse_args()

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    cells = [
        Cell(dataset, mode, outer, genetic)
        for dataset in args.datasets
        for mode in args.fitness_operators
        for outer in args.outer_iterations
        for genetic in args.genetic_iterations
    ]
    manifest = {
        "datasets": args.datasets,
        "fitnessOperators": args.fitness_operators,
        "outerIterations": args.outer_iterations,
        "geneticIterations": args.genetic_iterations,
        "runs": args.runs,
        "timeoutSeconds": args.timeout_seconds,
        "cells": [asdict(cell) | {"key": cell.key} for cell in cells],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if not args.plots_only:
        for index, cell in enumerate(cells, start=1):
            run_cell(args, out_dir, cell, index, len(cells))

    write_sweep_outputs(out_dir, manifest)


def run_cell(args: argparse.Namespace, out_dir: Path, cell: Cell, index: int, total: int) -> None:
    cell_dir = out_dir / "cells" / cell.key
    cell_dir.mkdir(parents=True, exist_ok=True)
    if cell_complete(cell_dir, args.runs) and not args.force:
        print(f"[{index}/{total}] skip complete {cell.key}", flush=True)
        return

    seed_base = args.seed_base + stable_cell_offset(cell)
    cmd = [
        args.python,
        str(PROFILE_BASELINE),
        "--datasets",
        cell.dataset,
        "--runs",
        str(args.runs),
        "--out-dir",
        str(cell_dir),
        "--timeout-seconds",
        str(args.timeout_seconds),
        "--outer-iterations",
        str(cell.outer_iterations),
        "--genetic-iterations",
        str(cell.genetic_iterations),
        "--fitness-json",
        json.dumps({"name": cell.fitness_operator}),
        "--seed-base",
        str(seed_base),
    ]
    if args.population is not None:
        cmd += ["--population", str(args.population)]
    if args.samples is not None:
        cmd += ["--samples", str(args.samples)]

    print(f"[{index}/{total}] {cell.key}", flush=True)
    print("cmd:", subprocess.list2cmdline(cmd), flush=True)
    if args.dry_run:
        return
    subprocess.run(cmd, cwd=str(REPO_ROOT), check=True)


def write_sweep_outputs(out_dir: Path, manifest: dict[str, object]) -> None:
    cell_rows: list[dict[str, object]] = []
    curve_rows: list[dict[str, object]] = []
    for cell in discover_cells(out_dir, manifest):
        cell_dir = out_dir / "cells" / cell.key
        runs = read_csv_dicts(cell_dir / "runs.csv")
        ga_rows = read_csv_dicts(cell_dir / "ga_fitness.csv")
        if not runs and not ga_rows:
            cell_rows.append(base_cell_row(cell) | {"status": "missing"})
            continue
        cell_rows.append(summarize_cell(cell, runs, ga_rows))
        curve_rows.extend(summarize_curves(cell, ga_rows))

    write_csv(out_dir / "cells.csv", cell_rows)
    write_csv(out_dir / "fitness_curves.csv", curve_rows)
    datasets = sorted({str(row.get("dataset")) for row in cell_rows})
    fitness_operators = sorted({str(row.get("fitness_operator")) for row in cell_rows})
    payload = {
        "meta": manifest
        | {
            "availableDatasets": datasets,
            "availableFitnessOperators": fitness_operators,
        },
        "cells": cell_rows,
        "curves": curve_rows,
        "heatmaps": {
            mode: [row for row in cell_rows if row.get("fitness_operator") == mode]
            for mode in sorted({str(row.get("fitness_operator")) for row in cell_rows})
        },
    }
    (out_dir / "sweep_dashboard_data.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def discover_cells(out_dir: Path, manifest: dict[str, object]) -> list[Cell]:
    cells_by_key: dict[str, Cell] = {}
    for raw_cell in manifest.get("cells", []):  # type: ignore[union-attr]
        cell = Cell(
            str(raw_cell["dataset"]),
            str(raw_cell["fitness_operator"]),
            int(raw_cell["outer_iterations"]),
            int(raw_cell["genetic_iterations"]),
        )
        cells_by_key[cell.key] = cell

    cells_dir = out_dir / "cells"
    if cells_dir.exists():
        for cell_dir in cells_dir.iterdir():
            if not cell_dir.is_dir():
                continue
            cell = parse_cell_key(cell_dir.name)
            if cell is not None:
                cells_by_key[cell.key] = cell

    return sorted(
        cells_by_key.values(),
        key=lambda cell: (
            cell.dataset,
            cell.fitness_operator,
            cell.outer_iterations,
            cell.genetic_iterations,
        ),
    )


def parse_cell_key(key: str) -> Cell | None:
    parts = key.split("__")
    if len(parts) != 4:
        return None
    dataset, fitness_operator, outer, genetic = parts
    if not outer.startswith("outer-") or not genetic.startswith("genetic-"):
        return None
    try:
        return Cell(
            dataset,
            fitness_operator,
            int(outer.removeprefix("outer-")),
            int(genetic.removeprefix("genetic-")),
        )
    except ValueError:
        return None


def summarize_cell(
    cell: Cell, runs: list[dict[str, str]], ga_rows: list[dict[str, str]]
) -> dict[str, object]:
    by_run: dict[int, list[dict[str, str]]] = {}
    for row in ga_rows:
        by_run.setdefault(int_float(row.get("run")), []).append(row)
    finals = []
    for rows in by_run.values():
        rows.sort(key=lambda row: int_float(row.get("global_generation") or row.get("generation")))
        if rows:
            finals.append(max(float_value(row.get("best_so_far")) for row in rows))
    statuses = [row.get("status", "") for row in runs]
    elapsed = [float_value(row.get("elapsed_seconds")) for row in runs if row.get("elapsed_seconds")]
    success_values = [
        float_value(row.get("success"))
        for row in runs
        if row.get("success") not in (None, "")
    ]
    return base_cell_row(cell) | {
        "status": "ok" if runs or finals else "missing",
        "runs": len(runs) or len(finals),
        "completed_runs": sum(1 for status in statuses if status == "ok"),
        "timeouts": sum(1 for status in statuses if status == "timeout"),
        "success_rate": mean(success_values) if success_values else 0.0,
        "elapsed_seconds_mean": mean(elapsed) if elapsed else 0.0,
        "fitness_mean": mean(finals) if finals else 0.0,
        "fitness_std": stdev(finals) if len(finals) > 1 else 0.0,
        "fitness_min": min(finals, default=0.0),
        "fitness_max": max(finals, default=0.0),
    }


def summarize_curves(cell: Cell, ga_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    by_run: dict[int, list[tuple[int, float]]] = {}
    for row in ga_rows:
        run = int_float(row.get("run"))
        generation = int_float(row.get("global_generation") or row.get("generation"))
        by_run.setdefault(run, []).append((generation, float_value(row.get("best_so_far"))))
    for rows in by_run.values():
        rows.sort()
        best = float("-inf")
        for index, (generation, value) in enumerate(rows):
            best = max(best, value)
            rows[index] = (generation, best)
    generations = sorted({generation for rows in by_run.values() for generation, _ in rows})
    curve = []
    for generation in generations:
        values = []
        for rows in by_run.values():
            last = None
            for row_generation, value in rows:
                if row_generation > generation:
                    break
                last = value
            if last is not None:
                values.append(last)
        if not values:
            continue
        curve.append(
            base_cell_row(cell)
            | {
                "global_generation": generation,
                "fitness_mean": mean(values),
                "fitness_std": stdev(values) if len(values) > 1 else 0.0,
                "runs": len(values),
            }
        )
    return curve


def base_cell_row(cell: Cell) -> dict[str, object]:
    return {
        "dataset": cell.dataset,
        "fitness_operator": cell.fitness_operator,
        "outer_iterations": cell.outer_iterations,
        "genetic_iterations": cell.genetic_iterations,
        "cell_key": cell.key,
    }


def cell_complete(cell_dir: Path, expected_runs: int) -> bool:
    rows = read_csv_dicts(cell_dir / "runs.csv")
    return len(rows) >= expected_runs


def stable_cell_offset(cell: Cell) -> int:
    raw = f"{cell.dataset}|{cell.fitness_operator}|{cell.outer_iterations}|{cell.genetic_iterations}"
    return sum((index + 1) * ord(char) for index, char in enumerate(raw)) * 1000


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_float(value: object) -> int:
    return int(float_value(value))


def float_value(value: object) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        if isinstance(value, str) and value.lower() == "true":
            return 1.0
        return 0.0


def _default_python() -> str:
    local = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    return str(local.resolve()) if local.exists() else sys.executable


if __name__ == "__main__":
    main()
