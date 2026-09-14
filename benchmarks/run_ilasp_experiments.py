import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import tomllib
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "benchmarks" / "ilasp_experiments.toml"
PHASE_PATTERNS = {
    "preprocessing_seconds": re.compile(
        r"^%% Pre-processing\s+:\s+([0-9.]+)s$", re.MULTILINE
    ),
    "hypothesis_space_seconds": re.compile(
        r"^%% Hypothesis Space Generation\s+:\s+([0-9.]+)s$", re.MULTILINE
    ),
    "conflict_analysis_seconds": re.compile(
        r"^%% Conflict analysis\s+:\s+([0-9.]+)s$", re.MULTILINE
    ),
    "counterexample_search_seconds": re.compile(
        r"^%% Counterexample search\s+:\s+([0-9.]+)s$", re.MULTILINE
    ),
    "hypothesis_search_seconds": re.compile(
        r"^%% Hypothesis Search\s+:\s+([0-9.]+)s$", re.MULTILINE
    ),
    "total_seconds": re.compile(r"^%% Total\s+:\s+([0-9.]+)s$", re.MULTILINE),
}
RUN_FIELDS = (
    "dataset",
    "version",
    "run",
    "status",
    "returncode",
    "wall_seconds",
    *PHASE_PATTERNS,
    "stdout_path",
    "stderr_path",
)
SUMMARY_FIELDS = (
    "dataset",
    "version",
    "runs",
    "solved",
    "timeouts",
    "failed",
    "mean_par1_seconds",
    "median_par1_seconds",
    "mean_solved_seconds",
    "mean_wall_seconds",
)


@dataclass(frozen=True)
class Experiment:
    id: str
    description: str
    datasets: tuple[str, ...]
    versions: tuple[str, ...]
    runs: int
    timeout_seconds: int
    output_root: Path
    task_dir: Path
    distro: str
    executable: str
    python_runtime: str
    max_body_length: dict[str, int]

    @property
    def output_dir(self) -> Path:
        return self.output_root.joinpath(*PurePosixPath(self.id).parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run reproducible ILASP matrices.")
    parser.add_argument("experiments", nargs="*")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    experiments = load_experiments(args.config)
    by_id = {experiment.id: experiment for experiment in experiments}
    if args.list:
        for experiment in experiments:
            print(f"{experiment.id}\t{experiment.description}")
        return 0
    unknown = sorted(set(args.experiments) - by_id.keys())
    if unknown:
        raise SystemExit(f"Unknown experiments: {', '.join(unknown)}")
    selected = (
        [by_id[experiment_id] for experiment_id in args.experiments]
        if args.experiments
        else experiments
    )
    if args.summary:
        print_summaries(selected)
        return 0
    for experiment in selected:
        run_experiment(experiment, force=args.force)
    return 0


def load_experiments(config_path: Path) -> list[Experiment]:
    payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    suite = payload.get("suite", {})
    definitions = payload.get("experiment", [])
    if not definitions:
        raise ValueError("ILASP config must define at least one [[experiment]]")
    experiments = []
    for definition in definitions:
        merged = {**suite, **definition}
        experiment_id = str(merged["id"])
        validate_experiment_id(experiment_id)
        datasets = tuple(str(item) for item in merged.get("datasets", ()))
        versions = tuple(str(item) for item in merged.get("versions", ()))
        lengths = {
            str(name): int(value)
            for name, value in merged.get("max_body_length", {}).items()
        }
        missing_lengths = sorted(set(datasets) - lengths.keys())
        if not datasets or not versions:
            raise ValueError(f"{experiment_id}: datasets and versions are required")
        if missing_lengths:
            raise ValueError(
                f"{experiment_id}: missing max body length for {', '.join(missing_lengths)}"
            )
        experiments.append(
            Experiment(
                id=experiment_id,
                description=str(merged.get("description", "")),
                datasets=datasets,
                versions=versions,
                runs=positive_int(merged.get("runs"), "runs", experiment_id),
                timeout_seconds=positive_int(
                    merged.get("timeout_seconds"), "timeout_seconds", experiment_id
                ),
                output_root=repo_path(merged["output_root"]),
                task_dir=repo_path(merged["task_dir"]),
                distro=str(merged["distro"]),
                executable=str(merged["executable"]),
                python_runtime=str(merged["python_runtime"]),
                max_body_length=lengths,
            )
        )
    return experiments


def run_experiment(experiment: Experiment, force: bool = False) -> None:
    output_dir = experiment.output_dir
    ensure_output_path(experiment.output_root, output_dir)
    expected_fingerprint = fingerprint(experiment)
    manifest_path = output_dir / "experiment.json"
    if force and output_dir.exists():
        shutil.rmtree(output_dir)
    elif manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if previous.get("fingerprint") != expected_fingerprint:
            raise SystemExit(f"{experiment.id}: config or tasks changed; use --force")
        if previous.get("status") == "complete":
            print(f"{experiment.id}: skip (already complete)")
            return

    runs_dir = output_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    runs_path = output_dir / "runs.csv"
    completed = completed_runs(runs_path)
    write_manifest(experiment, expected_fingerprint, "running")
    planned = len(experiment.datasets) * len(experiment.versions) * experiment.runs
    position = 0
    for dataset in experiment.datasets:
        task = experiment.task_dir / f"{dataset}.las"
        if not task.exists():
            raise SystemExit(f"{experiment.id}: task not found: {task}")
        task_wsl = windows_to_wsl(task)
        for version in experiment.versions:
            for run in range(1, experiment.runs + 1):
                position += 1
                key = (dataset, version, run)
                if key in completed:
                    print(f"[{position}/{planned}] {dataset} ILASP {version} run {run}: cached")
                    continue
                print(
                    f"[{position}/{planned}] {dataset} ILASP {version} run {run}",
                    flush=True,
                )
                row, stdout, stderr = execute_run(
                    experiment, dataset, version, run, task_wsl
                )
                stem = f"{dataset}_v{version}_run_{run}"
                stdout_path = runs_dir / f"{stem}.out"
                stderr_path = runs_dir / f"{stem}.err"
                stdout_path.write_text(stdout, encoding="utf-8")
                stderr_path.write_text(stderr, encoding="utf-8")
                row["stdout_path"] = str(stdout_path.relative_to(output_dir))
                row["stderr_path"] = str(stderr_path.relative_to(output_dir))
                append_csv(runs_path, RUN_FIELDS, row)
                print(
                    f"  {row['status']} wall={row['wall_seconds']}s "
                    f"ILASP={row['total_seconds'] or '-'}s",
                    flush=True,
                )
    rows = read_csv(runs_path)
    write_summary(output_dir / "summary.csv", rows, experiment.timeout_seconds)
    write_manifest(experiment, expected_fingerprint, "complete")


def execute_run(
    experiment: Experiment, dataset: str, version: str, run: int, task_wsl: str
) -> tuple[dict[str, object], str, str]:
    command = build_command(experiment, dataset, version, task_wsl)
    started = time.perf_counter()
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=experiment.timeout_seconds + 10,
            check=False,
        )
        returncode: int | None = result.returncode
        stdout = result.stdout
        stderr = result.stderr
        status = classify_status(returncode)
    except subprocess.TimeoutExpired as error:
        returncode = None
        stdout = decode_timeout_output(error.stdout)
        stderr = decode_timeout_output(error.stderr)
        status = "timeout"
    row: dict[str, object] = {
        "dataset": dataset,
        "version": version,
        "run": run,
        "status": status,
        "returncode": "" if returncode is None else returncode,
        "wall_seconds": f"{time.perf_counter() - started:.6f}",
    }
    for field, pattern in PHASE_PATTERNS.items():
        match = pattern.search(stdout)
        row[field] = match.group(1) if match else ""
    return row, stdout, stderr


def build_command(
    experiment: Experiment, dataset: str, version: str, task_wsl: str
) -> list[str]:
    runtime = experiment.python_runtime
    return [
        "wsl",
        "-d",
        experiment.distro,
        "--",
        "env",
        f"LD_LIBRARY_PATH={runtime}/lib/x86_64-linux-gnu",
        f"PYTHONHOME={runtime}",
        "timeout",
        "--signal=INT",
        "--kill-after=5s",
        f"{experiment.timeout_seconds}s",
        experiment.executable,
        f"--version={version}",
        f"-ml={experiment.max_body_length[dataset]}",
        task_wsl,
    ]


def summarize(rows: list[dict[str, str]], timeout_seconds: int) -> list[dict[str, object]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        groups.setdefault((row["dataset"], row["version"]), []).append(row)
    summary = []
    for (dataset, version), group in groups.items():
        solved_times = [
            float(row["total_seconds"])
            for row in group
            if row["status"] == "ok" and row["total_seconds"]
        ]
        par1 = [
            float(row["total_seconds"])
            if row["status"] == "ok" and row["total_seconds"]
            else float(timeout_seconds)
            for row in group
        ]
        summary.append(
            {
                "dataset": dataset,
                "version": version,
                "runs": len(group),
                "solved": sum(row["status"] == "ok" for row in group),
                "timeouts": sum(row["status"] == "timeout" for row in group),
                "failed": sum(row["status"] == "failed" for row in group),
                "mean_par1_seconds": f"{mean(par1):.6f}",
                "median_par1_seconds": f"{median(par1):.6f}",
                "mean_solved_seconds": (
                    f"{mean(solved_times):.6f}" if solved_times else ""
                ),
                "mean_wall_seconds": f"{mean(float(row['wall_seconds']) for row in group):.6f}",
            }
        )
    return summary


def write_summary(path: Path, rows: list[dict[str, str]], timeout_seconds: int) -> None:
    write_csv(path, SUMMARY_FIELDS, summarize(rows, timeout_seconds))


def print_summaries(experiments: list[Experiment]) -> None:
    rows = []
    for experiment in experiments:
        runs_path = experiment.output_dir / "runs.csv"
        if not runs_path.exists():
            continue
        for row in summarize(read_csv(runs_path), experiment.timeout_seconds):
            rows.append({"experiment": experiment.id, **row})
    if not rows:
        return
    writer = csv.DictWriter(
        os.sys.stdout, fieldnames=("experiment", *SUMMARY_FIELDS)
    )
    writer.writeheader()
    writer.writerows(rows)


def fingerprint(experiment: Experiment) -> str:
    payload = asdict(experiment)
    payload["output_root"] = str(experiment.output_root)
    payload["task_dir"] = str(experiment.task_dir)
    payload["tasks"] = {
        dataset: hashlib.sha256(
            (experiment.task_dir / f"{dataset}.las").read_bytes()
        ).hexdigest()
        for dataset in experiment.datasets
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def write_manifest(experiment: Experiment, digest: str, status: str) -> None:
    experiment.output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        **asdict(experiment),
        "output_root": str(experiment.output_root),
        "task_dir": str(experiment.task_dir),
        "fingerprint": digest,
        "status": status,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    (experiment.output_dir / "experiment.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )


def completed_runs(path: Path) -> set[tuple[str, str, int]]:
    return {
        (row["dataset"], row["version"], int(row["run"]))
        for row in read_csv(path)
    }


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def append_csv(path: Path, fields: tuple[str, ...], row: dict[str, object]) -> None:
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def write_csv(
    path: Path, fields: tuple[str, ...], rows: list[dict[str, object]]
) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def classify_status(returncode: int) -> str:
    if returncode == 0:
        return "ok"
    if returncode in (9, 124, 137):
        return "timeout"
    return "failed"


def decode_timeout_output(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


def windows_to_wsl(path: Path) -> str:
    drive, tail = os.path.splitdrive(str(path.resolve()))
    if not drive:
        raise ValueError(f"Expected a Windows path, got {path}")
    return f"/mnt/{drive[0].lower()}/{tail.lstrip('\\/').replace('\\', '/')}"


def repo_path(value: Any) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else REPO_ROOT / path


def validate_experiment_id(experiment_id: str) -> None:
    path = PurePosixPath(experiment_id)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError(f"invalid experiment id: {experiment_id}")


def positive_int(value: Any, field: str, experiment_id: str) -> int:
    result = int(value)
    if result < 1:
        raise ValueError(f"{experiment_id}: {field} must be positive")
    return result


def ensure_output_path(root: Path, target: Path) -> None:
    root = root.resolve()
    target = target.resolve()
    if target == root or root not in target.parents:
        raise ValueError(f"experiment output escapes its root: {target}")


if __name__ == "__main__":
    raise SystemExit(main())
