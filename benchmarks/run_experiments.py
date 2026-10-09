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
sys.path.insert(0, str(REPO_ROOT))

from benchmarks.catalog import arguments_for, arguments_json  # noqa: E402
from benchmarks.profile_baseline import (  # noqa: E402
    build_dashboard, read_ga_metrics, read_timings, run_file,
)
from benchmarks import ilasp  # noqa: E402

PROFILE_BASELINE = Path(__file__).with_name("profile_baseline.py")
DEFAULT_CONFIG = Path(__file__).with_name("experiments.toml")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*(?:/[a-z0-9][a-z0-9_-]*)*$")
METHODS = {
    "gentians-steady_state": ("gentians", "steady_state"),
    "gentians-incremental": ("gentians", "incremental"),
    **{f"ilasp-{version}": ("ilasp", version) for version in ("2", "2i", "3", "4")},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run selected ILP tools and algorithms from one experiment TOML."
    )
    parser.add_argument("experiments", nargs="*", help="Experiment IDs; all by default.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--methods", nargs="+", choices=tuple(METHODS),
                        help="Methods to run; defaults to the experiment's methods.")
    parser.add_argument(
        "--force", "--rerun", dest="force", action="store_true",
        help="Replace existing output and rerun.",
    )
    parser.add_argument("--list", action="store_true", help="List experiments and exit.")
    parser.add_argument("--historical-index", action="store_true",
                        help="Index saved results with their original metadata; do not run experiments.")
    parser.add_argument("--summary", action="store_true", help="Print measured run summaries as CSV without executing.")
    parser.add_argument(
        "--rebuild-dashboards", action="store_true",
        help="Rewrite dashboard_data.json from saved run artifacts with the current schema; do not run experiments.",
    )
    return parser.parse_args()


def load_config(path: Path) -> tuple[Path, list[dict[str, Any]]]:
    with path.open("rb") as file:
        config = tomllib.load(file)
    suite = config.get("suite", {})
    experiments = config.get("experiment", [])
    if not isinstance(suite, dict) or not isinstance(experiments, list):
        raise ValueError("TOML requires [suite] and [[experiment]] entries")
    output_root = Path(str(suite.get("output_root", ".benchmarks/experiments")))
    if not output_root.is_absolute():
        output_root = REPO_ROOT / output_root
    defaults = {
        "datasets": suite.get("datasets", []),
        "runs": suite.get("runs", 10),
        "timeout_seconds": suite.get("timeout_seconds", 100),
        "seed_base": suite.get("seed_base", 42),
        "cprofile": suite.get("cprofile", False),
        "instrumentation": suite.get("instrumentation", "full"),
        "python": suite.get("python"),
        "validation_timeout_seconds": suite.get("validation_timeout_seconds", 60),
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
        default_method = "gentians-" + overrides.get("algorithm", "steady_state")
        methods = raw.get("methods", suite.get("methods", [default_method]))
        if not isinstance(methods, list) or not methods or any(
            not isinstance(method, str) or method not in METHODS for method in methods
        ):
            raise ValueError(f"{experiment_id}: methods must select registered tools/algorithms")
        experiment["methods"] = list(dict.fromkeys(methods))
        experiment["method_matrix"] = "methods" in raw or "methods" in suite
        experiment["tools"] = config.get("tools", {})
        if not isinstance(experiment["tools"], dict) or any(
            not isinstance(options, dict) for options in experiment["tools"].values()
        ):
            raise ValueError("tools must contain one configuration table per tool")
        if int(experiment["validation_timeout_seconds"]) < 1:
            raise ValueError(f"{experiment_id}: validation timeout must be positive")
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


def expand_experiments(experiments: list[dict], methods: list[str] | None = None) -> list[dict]:
    expanded = []
    for experiment in experiments:
        selected = list(dict.fromkeys(methods or experiment["methods"]))
        for method in selected:
            tool, variant = METHODS[method]
            effective = {key: value for key, value in experiment.items()
                         if key not in ("methods", "tools", "method_matrix")}
            method_id = (f"{experiment['id']}/{method}" if experiment["method_matrix"] else
                         experiment["id"] if method == experiment["methods"][0] else
                         f"{experiment['id']}-{method}")
            effective.update(id=method_id,
                             experiment_id=experiment["id"], method=method, tool=tool, variant=variant)
            if tool == "gentians":
                effective["overrides"] = {**experiment["overrides"], "algorithm": variant}
            else:
                effective.update(runs=1, overrides={}, instrumentation="external",
                                 tool_options=experiment["tools"].get(tool, {}))
            expanded.append(effective)
    return expanded


def run_gentians(experiment: dict, output_dir: Path) -> int:
    return subprocess.run(experiment_command(experiment, output_dir), cwd=REPO_ROOT, check=False).returncode


# New learners register their execution function here and methods above.
# Every backend saves hypotheses and uses the shared independent checker.
RUNNERS = {"gentians": run_gentians, "ilasp": ilasp.run_experiment}


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
        str(experiment["python"] or sys.executable),
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
        "--validation-timeout-seconds", str(experiment.get("validation_timeout_seconds", 60)),
    ]
    if experiment.get("cprofile"):
        command.append("--cprofile")
    if experiment.get("stop_on_timeout"):
        command.append("--stop-on-timeout")
    for path, value in sorted(experiment["overrides"].items()):
        command.extend(("--set", f"{path}={json.dumps(value, separators=(',', ':'))}"))
    return command


def execution_inputs(experiment: dict[str, Any], *, runtime: dict | None = None) -> dict[str, Any]:
    """Identify code, task contents, effective SDK arguments and worker runtime."""
    paths = [path for path in (REPO_ROOT / "gentians").rglob("*")
             if path.suffix in {".py", ".lp"}]
    paths.extend((REPO_ROOT / "benchmarks").rglob("*.py"))
    paths.extend(REPO_ROOT / name for name in ("pyproject.toml", "uv.lock"))
    if experiment.get("tool") == "ilasp":
        paths.extend(ilasp.task_path(experiment, dataset) for dataset in experiment["datasets"])
        executable = ilasp.repo_path(experiment["tool_options"].get("executable", "tools/ilasp/ILASP"))
        if executable.is_file():
            paths.append(executable)
    overrides = [f"{key}={json.dumps(value)}" for key, value in sorted(experiment.get("overrides", {}).items())]
    arguments = {}
    for dataset in experiment["datasets"]:
        configured = arguments_for(dataset, overrides)
        arguments[dataset] = json.loads(arguments_json(configured))
        task_path = Path(configured.filename)
        task_path = task_path if task_path.is_absolute() else REPO_ROOT / task_path
        if task_path.is_dir():
            paths.extend(task_path / name for name in ("bk.lp", "exs.lp", "bias.lp"))
        else:
            paths.append(task_path)
    if runtime is None:
        runtime = json.loads(subprocess.check_output(
        [str(experiment.get("python") or sys.executable), "-c",
         "import sys,clingo,platform,json; print(json.dumps(dict("
         "python=sys.version,clingo=clingo.__version__,platform=platform.platform(),"
         "machine=platform.machine(),processor=platform.processor())))"],
        cwd=REPO_ROOT, text=True,
        ))
    return {
        "arguments": arguments,
        "runtime": runtime,
        "files": {str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in sorted(set(paths))},
    }


def fingerprint(experiment: dict[str, Any], inputs: dict[str, Any] | None = None) -> str:
    relevant = {"experiment": experiment,
                "execution": execution_inputs(experiment) if inputs is None else inputs}
    payload = json.dumps(relevant, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def saved_fingerprint(experiment: dict, manifest: dict) -> str:
    """Read-only indexing checks current code/config against the saved worker's runtime."""
    runtime = manifest.get("execution", {}).get("runtime")
    inputs = execution_inputs(experiment, runtime=runtime) if runtime is not None else execution_inputs(experiment)
    return fingerprint(experiment, inputs)


def summarize_experiment(experiment: dict[str, Any], out_dir: Path) -> list[dict[str, object]]:
    """Keep censored wall-clock costs separate from net times of solved runs."""
    if not (out_dir / "runs.csv").exists():
        return []
    manifest_path = out_dir / "experiment.json"
    if not manifest_path.exists():
        raise ValueError(f"{experiment['id']}: missing manifest; cannot summarize incomplete results")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("fingerprint") != saved_fingerprint(experiment, manifest):
        raise ValueError(f"{experiment['id']}: stale config; cannot summarize results")
    if manifest.get("status") not in ("complete", "completed_with_failures", "screened_out"):
        raise ValueError(f"{experiment['id']}: incomplete experiment; cannot summarize results")

    def rows(name):
        path = out_dir / name
        if not path.exists():
            return []
        with path.open(encoding="utf-8", newline="") as file:
            return list(csv.DictReader(file))

    runs = rows("runs.csv")
    timings = {}
    categories = {}
    latest = {}
    for row in runs:
        key = row["dataset"], row["run"]
        run = int(row["run"])
        if experiment.get("tool") not in (None, "gentians"):
            if row.get("total_seconds"):
                timings[key] = float(row["total_seconds"])
            continue
        for timing in read_timings(run_file(out_dir, row["dataset"], run, "_timings.json"),
                                   row["dataset"], run):
            if timing.metric == "total_execution":
                timings[key] = timing.seconds
            kind = timing.metric.rsplit(".", 1)[-1]
            if kind in ("grounding", "solving", "closure"):
                categories.setdefault(key, {}).setdefault(kind, []).append(
                    {"seconds": timing.seconds, "calls": timing.calls}
                )
        progress = read_ga_metrics(run_file(out_dir, row["dataset"], run, "_ga_metrics.json"),
                                   row["dataset"], run)
        if progress:
            final = max(progress, key=lambda point: point.generation)
            latest[key] = {"generation": final.generation,
                           "fitness_evaluations": final.fitness_evaluations}
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
            float(row.get("elapsed_seconds", row.get("wall_seconds", 0))) if row in solved else float(experiment["timeout_seconds"])
            for row in selected
        ]
        summaries.append({
            "experiment": experiment["id"], "dataset": dataset, "runs": len(selected),
            "successes": len(solved),
            "timeouts": sum(row["status"] == "timeout" for row in selected),
            "failed": sum(row["status"] == "failed" for row in selected),
            "par1_wall_seconds": mean(penalties) if float(experiment["timeout_seconds"]) > 0 else None,
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


def write_manifest(out_dir: Path, experiment: dict[str, Any], status: str,
                   inputs: dict[str, Any] | None = None) -> None:
    inputs = execution_inputs(experiment) if inputs is None else inputs
    payload = {
        "schema_version": 1,
        "id": experiment["id"],
        "label": experiment.get("label", experiment["id"]),
        "description": experiment.get("description", ""),
        "status": status,
        "fingerprint": fingerprint(experiment, inputs),
        "execution": inputs,
        "datasets": experiment["datasets"],
        "runs": experiment["runs"],
        "instrumentation": experiment.get("instrumentation", "full"),
        "stop_on_timeout": experiment.get("stop_on_timeout", False),
        "overrides": experiment["overrides"],
        "method": experiment.get("method"),
        "tool": experiment.get("tool", "gentians"),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    (out_dir / "experiment.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )


def write_index(output_root: Path, experiments: list[dict[str, Any]], *,
                historical_ids: set[str] | None = None) -> None:
    """Index every experiment; historical results stay historical until rerun."""
    if historical_ids is None:
        historical_ids = indexed_historical_ids(output_root)
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
        current_fingerprint = saved_fingerprint(experiment, manifest) if manifest_path.exists() else None
        historical = (
            experiment["id"] in historical_ids
            and manifest_path.exists()
            and manifest.get("fingerprint") != current_fingerprint
            and dashboard_path.exists()
            and manifest.get("status") in (
                "complete", "completed_with_failures", "screened_out", "stale"
            )
        )
        if historical:
            manifest["original_status"] = manifest["status"]
            manifest["status"] = "historical"
        elif manifest_path.exists() and manifest.get("fingerprint") != current_fingerprint:
            manifest["status"] = "stale"
        if not historical:
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


def indexed_historical_ids(output_root: Path) -> set[str]:
    index_path = output_root / "experiments.json"
    if not index_path.exists():
        return set()
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    return {
        item["id"]
        for item in payload.get("experiments", [])
        if item.get("status") == "historical" and isinstance(item.get("id"), str)
    }


def main() -> int:
    args = parse_args()
    output_root, definitions = load_config(args.config)
    experiments = expand_experiments(definitions)
    configured_ids = {item["id"] for item in experiments}
    # Keep previously run optional methods discoverable after changing --methods.
    experiments.extend(
        item for definition in definitions for method in METHODS
        for item in expand_experiments([definition], [method])
        if item["id"] not in configured_ids
        and (experiment_output_path(output_root, item["id"]) / "experiment.json").exists()
    )
    by_id = {experiment["id"]: experiment for experiment in experiments}
    definitions_by_id = {experiment["id"]: experiment for experiment in definitions}
    if args.list:
        write_index(output_root, experiments)
        for experiment in definitions:
            print(f"{experiment['id']}\t{', '.join(experiment['methods'])}")
        return 0
    unknown = sorted(set(args.experiments) - (by_id.keys() | definitions_by_id.keys()))
    if unknown:
        raise SystemExit(f"Unknown experiments: {', '.join(unknown)}")
    selected = []
    for key in args.experiments or list(definitions_by_id):
        if key in definitions_by_id:
            selected.extend(expand_experiments([definitions_by_id[key]], getattr(args, "methods", None)))
        else:
            selected.append(by_id[key])
    selected_by_id = {experiment["id"]: experiment for experiment in selected}
    owners = {}
    for experiment in [*experiments, *selected]:
        owner = owners.setdefault(experiment["id"], experiment["experiment_id"])
        if owner != experiment["experiment_id"]:
            raise SystemExit(f"Method output belongs to another experiment: {experiment['id']}")
    selected = list(selected_by_id.values())
    experiments = list({**by_id, **selected_by_id}.values())
    ids = [experiment["id"] for experiment in experiments]
    if any(left != right and right.startswith(left + "/") for left in ids for right in ids):
        raise SystemExit("Method outputs overlap; give the experiments distinct IDs")
    if args.historical_index:
        historical_ids = indexed_historical_ids(output_root)
        historical_ids.update(item["id"] for item in selected)
        write_index(output_root, experiments, historical_ids=historical_ids)
        return 0
    if args.rebuild_dashboards:
        for experiment in selected:
            if experiment["tool"] != "gentians":
                continue
            out_dir = experiment_output_path(output_root, experiment["id"])
            if (out_dir / "runs.csv").exists():
                print(f"{experiment['id']}: rebuild dashboard")
                build_dashboard(out_dir)
        write_index(output_root, experiments)
        return 0
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
    # Validate every selected backend/task before starting any benchmark.
    for experiment in selected:
        if experiment["tool"] == "ilasp":
            lengths = experiment["tool_options"].get("max_body_length", {})
            missing = [dataset for dataset in experiment["datasets"] if dataset not in lengths]
            if missing:
                raise SystemExit(f"{experiment['id']}: missing ILASP max_body_length for {', '.join(missing)}")
            for dataset in experiment["datasets"]:
                if not ilasp.task_path(experiment, dataset).is_file():
                    raise SystemExit(f"ILASP task not found: {ilasp.task_path(experiment, dataset)}")
    for experiment in selected:
        out_dir = experiment_output_path(output_root, experiment["id"])
        manifest_path = out_dir / "experiment.json"
        if manifest_path.exists() and not args.force:
            previous = json.loads(manifest_path.read_text(encoding="utf-8"))
            if previous.get("fingerprint") != fingerprint(experiment):
                raise SystemExit(f"{experiment['id']}: config changed; use --force")
            if (
                previous.get("status") in ("complete", "screened_out")
                or (experiment["tool"] != "gentians" and previous.get("status") == "completed_with_failures")
            ) and (
                    experiment.get("instrumentation") == "light"
                    or experiment["tool"] != "gentians"
                    or (out_dir / "dashboard_data.json").exists()
            ):
                print(f"{experiment['id']}: skip (already run)")
                continue
        if out_dir.exists() and (args.force or experiment["tool"] == "gentians"):
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        inputs = execution_inputs(experiment)
        print(f"{experiment['id']}: run")
        write_manifest(out_dir, experiment, "running", inputs)
        returncode = RUNNERS[experiment["tool"]](experiment, out_dir)
        status = result_status(out_dir, returncode,
                               stop_on_timeout=experiment.get("stop_on_timeout", False))
        if inputs != execution_inputs(experiment):
            status = "stale"
        write_manifest(out_dir, experiment, status, inputs)
        write_index(output_root, experiments)
        if returncode:
            print(f"{experiment['id']}: runner failed ({returncode})", file=sys.stderr)
            return returncode
    write_index(output_root, experiments)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
