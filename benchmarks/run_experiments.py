import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
import traceback
from collections import deque
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from statistics import mean
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from benchmarks.catalog import arguments_for, arguments_json, parse_override  # noqa: E402
from benchmarks.profile_baseline import (  # noqa: E402
    build_dashboard, read_ga_metrics, read_timings, run_file, write_summary,
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
    parser.add_argument(
        # process_cpu_count honours the CPU affinity a scheduler such as Slurm
        # assigns; cpu_count would report every CPU of the node.
        "--jobs", type=positive_int, default=max(1, (os.process_cpu_count() or 1) // 2),
        help="Experiment, method and dataset units run at once; 1 runs them in sequence. "
             "Defaults to half the CPUs available to this process. Concurrent units share CPU and memory, "
             "so wall-clock times and timeouts depend on this value.",
    )
    parser.add_argument(
        "--set", action="append", default=[], metavar="PATH=JSON",
        help="Override an Arguments field in every Gentians experiment after the TOML overrides, "
             "e.g. --set clause_generation.clingo_arguments=[]. Saved configs and fingerprints include it.",
    )
    parser.add_argument("--list", action="store_true", help="List experiments and exit.")
    parser.add_argument("--summary", action="store_true", help="Print measured run summaries as CSV without executing.")
    parser.add_argument(
        "--rebuild-dashboards", action="store_true",
        help="Rewrite dashboard_data.json from saved run artifacts with the current schema; do not run experiments.",
    )
    return parser.parse_args()


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


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


_print_lock = threading.Lock()


def emit(line: str) -> None:
    with _print_lock:
        print(line, flush=True)


def run_gentians(experiment: dict, output_dir: Path, runs_path: Path) -> int:
    label = f"{experiment['id']} {'+'.join(experiment['datasets'])}"
    with subprocess.Popen(
        experiment_command(experiment, output_dir, runs_path), cwd=REPO_ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
    ) as process:
        assert process.stdout is not None
        # Concurrent units share the console; each line names its unit.
        for line in process.stdout:
            if line.strip():
                emit(f"[{label}] {line.rstrip()}")
    return process.returncode


# New learners register their execution function here and methods above.
# Every backend saves hypotheses and uses the shared independent checker. A
# runner receives the experiment restricted to the datasets of one unit and
# writes that unit's run index to `runs_path`; artifacts go to the experiment
# directory. Rows already in `runs_path` may be treated as cached.
RUNNERS = {"gentians": run_gentians, "ilasp": ilasp.run_experiment}


def dataset_groups(experiment: dict[str, Any]) -> list[list[str]]:
    """Datasets that one unit runs together; units of an experiment run in parallel.

    Stopping on timeout screens out the whole configuration after its first
    timeout, so those datasets keep running in sequence within one unit.
    """
    datasets = list(experiment["datasets"])
    return [datasets] if experiment.get("stop_on_timeout") else [[dataset] for dataset in datasets]


def part_path(out_dir: Path, group: list[str]) -> Path:
    return out_dir / ".parts" / f"{'+'.join(group)}.csv"


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return list(reader.fieldnames or []), list(reader)


def write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, restval="")
        writer.writeheader()
        writer.writerows(rows)


def seed_parts(out_dir: Path, groups: list[list[str]]) -> None:
    """Split a kept run index into unit parts, so units can reuse cached rows."""
    if (out_dir / ".parts").exists():
        return
    fieldnames, rows = read_csv_rows(out_dir / "runs.csv")
    for group in groups:
        selected = [row for row in rows if row["dataset"] in group]
        if selected:
            write_csv_rows(part_path(out_dir, group), fieldnames, selected)


def merge_parts(out_dir: Path, groups: list[list[str]]) -> None:
    """Write the unit parts to runs.csv in configured dataset order, then drop them."""
    fieldnames: list[str] = []
    rows: list[dict[str, str]] = []
    for group in groups:
        names, part = read_csv_rows(part_path(out_dir, group))
        fieldnames.extend(name for name in names if name not in fieldnames)
        rows.extend(part)
    if fieldnames:
        write_csv_rows(out_dir / "runs.csv", fieldnames, rows)
    shutil.rmtree(out_dir / ".parts", ignore_errors=True)


def experiment_output_path(output_root: Path, experiment_id: str) -> Path:
    """Resolve a namespaced output without traversing links or leaving the root."""
    root = output_root.resolve()
    target = root / experiment_id
    resolved = target.resolve()
    if resolved == root or not resolved.is_relative_to(root) or resolved != target:
        raise ValueError(f"Unsafe output path: {target}")
    return resolved


def experiment_command(
    experiment: dict[str, Any], out_dir: Path, part_index: Path | None = None,
) -> list[str]:
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
    if part_index is not None:
        command.extend(("--part-index", str(part_index)))
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
             if path.suffix in {".py", ".lp", ".c", ".so", ".pyd"}]
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


def read_json(path: Path) -> dict:
    for attempt in range(20):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05)
    raise AssertionError("unreachable")


def summarize_experiment(experiment: dict[str, Any], out_dir: Path) -> list[dict[str, object]]:
    """Keep censored wall-clock costs separate from net times of solved runs."""
    if not (out_dir / "runs.csv").exists():
        return []
    manifest_path = out_dir / "experiment.json"
    if not manifest_path.exists():
        raise ValueError(f"{experiment['id']}: missing manifest; cannot summarize incomplete results")
    manifest = read_json(manifest_path)
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
                   inputs: dict[str, Any] | None = None, *, jobs: int | None = None) -> None:
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
    if jobs is not None:
        # Concurrency belongs to the measurement environment, not to the result identity.
        payload["jobs"] = jobs
    write_json_atomic(out_dir / "experiment.json", payload)


def write_json_atomic(path: Path, payload: dict) -> None:
    file = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                      prefix=path.name + ".", suffix=".tmp", delete=False)
    temporary = Path(file.name)
    try:
        with file:
            json.dump(payload, file, indent=2, sort_keys=True)
        for attempt in range(20):
            try:
                temporary.replace(path)
                return
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.05)
    finally:
        temporary.unlink(missing_ok=True)


def write_index(output_root: Path, experiments: list[dict[str, Any]]) -> None:
    """Serialize snapshots so a slower parallel job cannot publish an older index."""
    output_root.mkdir(parents=True, exist_ok=True)
    with (output_root / ".index.lock").open("a+b") as lock:
        if os.name == "nt":
            import msvcrt
            if lock.tell() == 0:
                lock.write(b"\0")
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            _write_index(output_root, experiments)
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _write_index(output_root: Path, experiments: list[dict[str, Any]]) -> None:
    """Index every experiment; saved results of an older config become historical."""
    rows = []
    for experiment in experiments:
        out_dir = experiment_output_path(output_root, experiment["id"])
        manifest_path = out_dir / "experiment.json"
        dashboard_path = out_dir / "dashboard_data.json"
        manifest = (
            read_json(manifest_path)
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
        # A finished result keeps its own metadata; partial or foreign results stay stale.
        historical = (
            manifest_path.exists()
            and manifest.get("id") == experiment["id"]
            and manifest.get("fingerprint") != current_fingerprint
            and (dashboard_path.exists() or (out_dir / "runs.csv").is_file())
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
    write_json_atomic(output_root / "experiments.json", {
        "schemaVersion": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "experiments": rows,
    })


def main() -> int:
    args = parse_args()
    output_root, definitions = load_config(args.config)
    cli_overrides = dict(parse_override(raw) for raw in getattr(args, "set", []))
    for definition in definitions:
        definition["overrides"] = {**definition["overrides"], **cli_overrides}
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
    plans = []
    for experiment in selected:
        out_dir = experiment_output_path(output_root, experiment["id"])
        manifest_path = out_dir / "experiment.json"
        if manifest_path.exists() and not args.force:
            previous = read_json(manifest_path)
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
        plans.append((experiment, out_dir))
    return run_plans(plans, output_root, experiments, force=args.force, jobs=getattr(args, "jobs", 1))


def run_plans(
    plans: list[tuple[dict[str, Any], Path]], output_root: Path, experiments: list[dict[str, Any]],
    *, force: bool, jobs: int,
) -> int:
    """Run every experiment, method and dataset unit, at most `jobs` at once.

    An experiment is reset when its first unit starts and finalized when its
    last unit ends. After a failure no new unit starts: started experiments are
    finalized with the runs they completed, the others keep their saved results.
    """
    units = deque(
        (experiment, out_dir, group) for experiment, out_dir in plans for group in dataset_groups(experiment)
    )
    remaining = {experiment["id"]: len(dataset_groups(experiment)) for experiment, _ in plans}
    inputs: dict[str, dict[str, Any]] = {}
    returncodes: dict[str, int] = {}
    running: dict[Future[int], tuple[dict[str, Any], Path]] = {}
    failure = 0
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        while units or running:
            while units and len(running) < jobs and not failure:
                experiment, out_dir, group = units.popleft()
                if experiment["id"] not in inputs:
                    inputs[experiment["id"]] = start_experiment(experiment, out_dir, force=force, jobs=jobs)
                unit = {**experiment, "datasets": group}
                running[pool.submit(run_unit, unit, out_dir, part_path(out_dir, group))] = experiment, out_dir
            if not running:
                break
            done, _ = wait(running, return_when=FIRST_COMPLETED)
            for future in done:
                experiment, out_dir = running.pop(future)
                returncode = future.result()
                if returncode:
                    emit(f"{experiment['id']}: runner failed ({returncode})")
                    returncodes.setdefault(experiment["id"], returncode)
                    failure = failure or returncode
                remaining[experiment["id"]] -= 1
                if not remaining[experiment["id"]]:
                    finish_experiment(experiment, out_dir, inputs[experiment["id"]],
                                      returncodes.get(experiment["id"], 0), jobs=jobs)
                    write_index(output_root, experiments)
    # Units that never started after a failure leave their experiment incomplete.
    for experiment, out_dir in plans:
        if experiment["id"] in inputs and remaining[experiment["id"]]:
            finish_experiment(experiment, out_dir, inputs[experiment["id"]],
                              returncodes.get(experiment["id"], failure), jobs=jobs)
    write_index(output_root, experiments)
    return failure


def start_experiment(experiment: dict[str, Any], out_dir: Path, *, force: bool, jobs: int) -> dict[str, Any]:
    if out_dir.exists() and (force or experiment["tool"] == "gentians"):
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    seed_parts(out_dir, dataset_groups(experiment))
    inputs = execution_inputs(experiment)
    emit(f"{experiment['id']}: run")
    write_manifest(out_dir, experiment, "running", inputs, jobs=jobs)
    return inputs


def run_unit(unit: dict[str, Any], out_dir: Path, runs_path: Path) -> int:
    try:
        return RUNNERS[unit["tool"]](unit, out_dir, runs_path)
    except Exception:
        emit(traceback.format_exc())
        return 1


def finish_experiment(
    experiment: dict[str, Any], out_dir: Path, inputs: dict[str, Any], returncode: int, *, jobs: int,
) -> None:
    merge_parts(out_dir, dataset_groups(experiment))
    if experiment["tool"] == "gentians" and (out_dir / "runs.csv").exists():
        try:
            write_summary(out_dir, experiment.get("instrumentation", "full"))
        except Exception:
            emit(traceback.format_exc())
            returncode = returncode or 1
    status = result_status(out_dir, returncode, stop_on_timeout=experiment.get("stop_on_timeout", False))
    if inputs != execution_inputs(experiment):
        status = "stale"
    write_manifest(out_dir, experiment, status, inputs, jobs=jobs)


if __name__ == "__main__":
    raise SystemExit(main())
