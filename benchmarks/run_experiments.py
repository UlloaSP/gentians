import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tomllib
from statistics import mean
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE_BASELINE = Path(__file__).with_name("profile_baseline.py")
DEFAULT_CONFIG = Path(__file__).with_name("experiments.toml")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*(?:/[a-z0-9][a-z0-9_-]*)*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run comparable profile_baseline experiments from TOML."
    )
    parser.add_argument("experiments", nargs="*", help="Experiment IDs; all by default.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--force", "--rerun", dest="force", action="store_true",
        help="Replace existing output and rerun.",
    )
    parser.add_argument("--list", action="store_true", help="List experiments and exit.")
    parser.add_argument("--summary", action="store_true", help="Print measured run summaries as CSV without executing.")
    return parser.parse_args()


def load_config(path: Path) -> tuple[Path, list[dict[str, Any]]]:
    with path.open("rb") as file:
        config = tomllib.load(file)
    suite = config.get("suite", {})
    experiments = config.get("experiment", [])
    if not isinstance(suite, dict) or not isinstance(experiments, list):
        raise ValueError("TOML requires [suite] and [[experiment]] entries")
    output_root = Path(str(suite.get("output_root", ".benchmarks")))
    if not output_root.is_absolute():
        output_root = REPO_ROOT / output_root
    defaults = {
        "datasets": suite.get("datasets", []),
        "runs": suite.get("runs", 10),
        "timeout_seconds": suite.get("timeout_seconds", 100),
        "seed_base": suite.get("seed_base", 1),
        "cprofile": suite.get("cprofile", False),
        "instrumentation": suite.get("instrumentation", "full"),
        "python": suite.get("python", sys.executable),
    }
    common_overrides = suite.get("overrides", {})
    if not isinstance(common_overrides, dict):
        raise ValueError("suite.overrides must be a table")
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for raw in experiments:
        if not isinstance(raw, dict):
            raise ValueError("each [[experiment]] must be a table")
        experiment = {**defaults, **raw}
        experiment_id = experiment.get("id")
        if not isinstance(experiment_id, str) or not ID_RE.fullmatch(experiment_id):
            raise ValueError(f"invalid experiment id: {experiment_id!r}")
        if experiment_id in seen:
            raise ValueError(f"duplicate experiment id: {experiment_id}")
        # An experiment must not own a parent directory of another experiment:
        # --force removes the entire selected output directory.
        if any(
            experiment_id.startswith(other + "/") or other.startswith(experiment_id + "/")
            for other in seen
        ):
            raise ValueError(f"overlapping experiment output paths: {experiment_id}")
        seen.add(experiment_id)
        datasets = experiment.get("datasets")
        own_overrides = experiment.get("overrides", {})
        if not isinstance(own_overrides, dict):
            raise ValueError(f"{experiment_id}: overrides must be a table")
        overrides = {**common_overrides, **own_overrides}
        experiment["overrides"] = overrides
        if not isinstance(datasets, list) or not datasets or not all(
            isinstance(item, str) for item in datasets
        ):
            raise ValueError(f"{experiment_id}: datasets must be a non-empty string array")
        if int(experiment["runs"]) < 1:
            raise ValueError(f"{experiment_id}: runs must be positive")
        if experiment["instrumentation"] not in ("full", "light"):
            raise ValueError(f"{experiment_id}: instrumentation must be full or light")
        if not isinstance(experiment.get("stop_on_timeout", False), bool):
            raise ValueError(f"{experiment_id}: stop_on_timeout must be a boolean")
        normalized.append(experiment)
    return output_root.resolve(), normalized


def experiment_output_path(output_root: Path, experiment_id: str) -> Path:
    """Resolve a namespaced output without traversing links or leaving the root."""
    root = output_root.resolve()
    target = root / experiment_id
    resolved = target.resolve()
    if resolved == root or not resolved.is_relative_to(root) or resolved != target:
        raise ValueError(f"Unsafe output path: {target}")
    return resolved


def experiment_command(experiment: dict[str, Any], out_dir: Path) -> list[str]:
    command = [
        str(experiment["python"]),
        str(PROFILE_BASELINE),
        "--datasets",
        *experiment["datasets"],
        "--runs",
        str(experiment["runs"]),
        "--out-dir",
        str(out_dir),
        "--timeout-seconds",
        str(experiment["timeout_seconds"]),
        "--seed-base",
        str(experiment["seed_base"]),
        "--instrumentation",
        str(experiment.get("instrumentation", "full")),
    ]
    if experiment.get("cprofile"):
        command.append("--cprofile")
    if experiment.get("stop_on_timeout"):
        command.append("--stop-on-timeout")
    for path, value in sorted(experiment["overrides"].items()):
        command.extend(("--set", f"{path}={json.dumps(value, separators=(',', ':'))}"))
    return command


def fingerprint(experiment: dict[str, Any]) -> str:
    relevant = {key: value for key, value in experiment.items() if key != "python"}
    payload = json.dumps(relevant, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def summarize_experiment(experiment: dict[str, Any], out_dir: Path) -> list[dict[str, object]]:
    """Keep censored wall-clock costs separate from net times of solved runs."""
    if not (out_dir / "runs.csv").exists():
        return []
    manifest_path = out_dir / "experiment.json"
    if not manifest_path.exists():
        raise ValueError(f"{experiment['id']}: missing manifest; cannot summarize incomplete results")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("fingerprint") != fingerprint(experiment):
        raise ValueError(f"{experiment['id']}: stale config; cannot summarize results")
    if manifest.get("status") not in ("complete", "completed_with_failures", "screened_out"):
        raise ValueError(f"{experiment['id']}: incomplete experiment; cannot summarize results")

    def rows(name):
        path = out_dir / name
        if not path.exists():
            return []
        with path.open(encoding="utf-8", newline="") as file:
            return list(csv.DictReader(file))

    timing_rows = rows("timings_raw.csv")
    timings = {
        (row["dataset"], row["run"]): float(row["seconds"])
        for row in timing_rows if row["metric"] == "total_execution"
    }
    categories = {}
    for row in timing_rows:
        kind = row["metric"].rsplit(".", 1)[-1]
        if kind not in ("grounding", "solving", "closure"):
            continue
        key = row["dataset"], row["run"]
        categories.setdefault(key, {}).setdefault(kind, []).append(row)
    latest = {}
    for row in rows("ga_fitness.csv"):
        key = row["dataset"], row["run"]
        if key not in latest or int(row["generation"]) >= int(latest[key]["generation"]):
            latest[key] = row
    runs = rows("runs.csv")
    summaries = []
    for dataset in experiment["datasets"]:
        selected = [row for row in runs if row["dataset"] == dataset]
        if not selected:
            continue
        solved = [row for row in selected if row["status"] == "ok" and row.get("success", "").lower() == "true"]
        solved_keys = [(row["dataset"], row["run"]) for row in solved]
        total_times = [timings[key] for key in solved_keys if key in timings]
        generations = [int(latest[key]["generation"]) for key in solved_keys if key in latest]
        evaluations = [int(latest[key]["fitness_evaluations"]) for key in solved_keys if key in latest]
        measured = {}
        for kind in ("grounding", "solving", "closure"):
            samples = [
                sum(float(row["seconds"]) for row in categories[key][kind])
                for key in solved_keys if key in timings and kind in categories.get(key, {})
            ]
            measured[f"solved_{kind}_mean"] = mean(samples) if samples else None
            if kind != "closure":
                counts = [
                    sum(int(row["calls"]) for row in categories[key][kind])
                    for key in solved_keys
                    if key in timings and kind in categories.get(key, {})
                    and all(row.get("calls") not in (None, "") for row in categories[key][kind])
                ]
                label = "ground" if kind == "grounding" else "solve"
                measured[f"solved_{label}_calls_mean"] = mean(counts) if counts else None
        python_samples = [
            max(timings[key] - sum(
                float(row["seconds"])
                for kind in ("grounding", "solving", "closure")
                for row in categories[key][kind]
            ), 0.0)
            for key in solved_keys if key in timings
            and all(kind in categories.get(key, {}) for kind in ("grounding", "solving", "closure"))
        ]
        measured["solved_python_mean"] = mean(python_samples) if python_samples else None
        penalties = [
            float(row["elapsed_seconds"]) if row in solved else float(experiment["timeout_seconds"])
            for row in selected
        ]
        summaries.append({
            "experiment": experiment["id"], "dataset": dataset, "runs": len(selected),
            "successes": len(solved),
            "timeouts": sum(row["status"] == "timeout" for row in selected),
            "failed": sum(row["status"] == "failed" for row in selected),
            "par1_wall_seconds": mean(penalties),
            "solved_total_execution_mean": mean(total_times) if total_times else None,
            "solved_total_execution_count": len(total_times),
            "solved_generations_mean": mean(generations) if generations else None,
            "solved_evaluations_mean": mean(evaluations) if evaluations else None,
            **measured,
        })
    return summaries


def result_status(out_dir: Path, returncode: int = 0, *, stop_on_timeout: bool = False) -> str:
    if returncode:
        return "failed"
    runs_path = out_dir / "runs.csv"
    if not runs_path.exists():
        return "failed"
    with runs_path.open(encoding="utf-8", newline="") as file:
        statuses = [row.get("status") for row in csv.DictReader(file)]
    if stop_on_timeout and "timeout" in statuses:
        return "screened_out"
    return "complete" if statuses and all(status == "ok" for status in statuses) else "completed_with_failures"


def write_manifest(out_dir: Path, experiment: dict[str, Any], status: str) -> None:
    payload = {
        "schema_version": 1,
        "id": experiment["id"],
        "label": experiment.get("label", experiment["id"]),
        "description": experiment.get("description", ""),
        "status": status,
        "fingerprint": fingerprint(experiment),
        "datasets": experiment["datasets"],
        "runs": experiment["runs"],
        "instrumentation": experiment.get("instrumentation", "full"),
        "stop_on_timeout": experiment.get("stop_on_timeout", False),
        "overrides": experiment["overrides"],
        "updated_at": datetime.now(UTC).isoformat(),
    }
    (out_dir / "experiment.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )


def write_index(output_root: Path, experiments: list[dict[str, Any]]) -> None:
    rows = []
    for experiment in experiments:
        out_dir = experiment_output_path(output_root, experiment["id"])
        manifest_path = out_dir / "experiment.json"
        dashboard_path = out_dir / "dashboard_data.json"
        manifest = (
            json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest_path.exists()
            else {
                "id": experiment["id"],
                "label": experiment.get("label", experiment["id"]),
                "description": experiment.get("description", ""),
                "status": "not_run",
                "datasets": experiment["datasets"],
                "runs": experiment["runs"],
                "instrumentation": experiment.get("instrumentation", "full"),
                "overrides": experiment["overrides"],
            }
        )
        if manifest_path.exists() and manifest.get("fingerprint") != fingerprint(experiment):
            manifest["status"] = "stale"
        manifest.update(
            {
                "id": experiment["id"],
                "label": experiment.get("label", experiment["id"]),
                "description": experiment.get("description", ""),
                "datasets": experiment["datasets"],
                "runs": experiment["runs"],
                "instrumentation": experiment.get("instrumentation", "full"),
                "overrides": experiment["overrides"],
            }
        )
        manifest["output_dir"] = experiment["id"]
        manifest["dashboard_path"] = f"{experiment['id']}/dashboard_data.json"
        manifest["has_dashboard"] = dashboard_path.exists() and manifest["status"] != "stale"
        rows.append(manifest)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "experiments.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "generated_at": datetime.now(UTC).isoformat(),
                "experiments": rows,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    output_root, experiments = load_config(args.config)
    by_id = {experiment["id"]: experiment for experiment in experiments}
    if args.list:
        write_index(output_root, experiments)
        for experiment in experiments:
            print(f"{experiment['id']}\t{experiment.get('label', experiment['id'])}")
        return 0
    unknown = sorted(set(args.experiments) - by_id.keys())
    if unknown:
        raise SystemExit(f"Unknown experiments: {', '.join(unknown)}")
    selected = [by_id[key] for key in args.experiments] if args.experiments else experiments
    if args.summary:
        try:
            summaries = [row for experiment in selected for row in summarize_experiment(
                experiment, experiment_output_path(output_root, experiment["id"])
            )]
        except (ValueError, OSError) as error:
            raise SystemExit(str(error)) from error
        if summaries:
            writer = csv.DictWriter(sys.stdout, fieldnames=list(summaries[0]))
            writer.writeheader()
            writer.writerows(summaries)
        return 0
    output_root.mkdir(parents=True, exist_ok=True)
    for experiment in selected:
        out_dir = experiment_output_path(output_root, experiment["id"])
        manifest_path = out_dir / "experiment.json"
        if manifest_path.exists() and not args.force:
            previous = json.loads(manifest_path.read_text(encoding="utf-8"))
            if previous.get("fingerprint") != fingerprint(experiment):
                raise SystemExit(f"{experiment['id']}: config changed; use --force")
            if (
                previous.get("status") in ("complete", "screened_out")
                and (
                    experiment.get("instrumentation") == "light"
                    or (out_dir / "dashboard_data.json").exists()
                )
            ):
                print(f"{experiment['id']}: skip (already run)")
                continue
        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        command = experiment_command(experiment, out_dir)
        print(f"{experiment['id']}: run")
        completed = subprocess.run(command, cwd=REPO_ROOT, check=False)
        status = result_status(out_dir, completed.returncode,
                               stop_on_timeout=experiment.get("stop_on_timeout", False))
        write_manifest(out_dir, experiment, status)
        write_index(output_root, experiments)
        if completed.returncode:
            print(f"{experiment['id']}: runner failed ({completed.returncode})", file=sys.stderr)
            return completed.returncode
    write_index(output_root, experiments)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
