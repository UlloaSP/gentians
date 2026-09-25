import argparse
import csv
import gzip
import json
import math
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE_BASELINE_PATH = Path(__file__).resolve()
# Keep in sync with DASHBOARD_SCHEMA_VERSION in .benchmarks/src/metrics.js.
DASHBOARD_SCHEMA_VERSION = 12
# Progress points kept per run and positions in each precomputed mean series.
RUN_PROGRESS_POINTS = 300
MEAN_PROGRESS_POINTS = 300
PROGRESS_AXES = ("generation", "seconds", "evaluations")
sys.path.insert(0, str(REPO_ROOT))

from benchmarks.catalog import (  # noqa: E402
    DEFAULT_DATASETS,
    arguments_for,
    arguments_from_json,
    arguments_json,
    case_names,
)
from gentians import Arguments  # noqa: E402
from gentians import main as gentians_main  # noqa: E402
from gentians.evaluation.compiler import compile_coverage_program  # noqa: E402
from gentians.language import parse_file  # noqa: E402
from gentians.language.asp import render_program  # noqa: E402


@dataclass
class RunResult:
    dataset: str
    run: int
    seed: int
    experiment_id: str
    status: str
    returncode: int | None
    elapsed_seconds: float
    command: list[str]
    arguments_json: str
    log_path: str
    success: bool = False
    cprofile_path: str = ""


@dataclass
class TimingMetric:
    dataset: str
    run: int
    metric: str
    seconds: float
    calls: int


@dataclass
class GAMetric:
    dataset: str
    run: int
    generation: int
    max_fitness: float
    avg_fitness: float
    best_so_far: float
    population_size: float = 0.0
    unique_signatures: float = 0.0
    diversity: float = 0.0
    invalid_count: float = 0.0
    invalid_rate: float = 0.0
    mean_program_size: float = 0.0
    elapsed_seconds: float = 0.0
    fitness_evaluations: int = 0
    restarted: bool = False


# Reasons recorded by incremental search when an epoch ends, in display order.
EPOCH_REASONS = ("generations", "stagnation", "space_exhausted", "solution", "generation_limit")


def parse_profile_args(
    description: str,
    default_out_dir: Path,
    add_args: Callable[[argparse.ArgumentParser], None] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=description
    )
    parser.add_argument("--datasets", nargs="+", default=DEFAULT_DATASETS)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--out-dir", type=Path, default=default_out_dir)
    parser.add_argument("--timeout-seconds", type=int, default=100, help="Process timeout; 0 disables it.")
    parser.add_argument(
        "--stop-on-timeout", action="store_true",
        help="Stop this configuration after its first timed-out run; retain completed results.",
    )
    parser.add_argument("--python", default=_default_python())
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="PATH=JSON",
        help="Override Arguments field, e.g. --set iterations_genetic=1000 --set evaluation.scoring=cov_program",
    )
    parser.add_argument(
        "--arguments-json",
        help="Full Arguments JSON object. Used for every listed dataset unless --set overrides it.",
    )
    parser.add_argument("--list-datasets", action="store_true")
    parser.add_argument("--seed-base", type=int, default=1)
    parser.add_argument("--instrumentation", choices=("full", "light"), default="full")
    parser.add_argument(
        "--cprofile",
        action="store_true",
        help="Write one Python .prof file per run.",
    )
    if add_args is not None:
        add_args(parser)
    return parser.parse_args()


def main() -> None:
    args = parse_profile_args(
        "External profiler for baseline GENTIANS. Does not modify gentians code.",
        Path(".benchmarks/experiments") / "baseline_profile",
    )
    run_benchmark_suite(args, PROFILE_BASELINE_PATH)


def run_benchmark_suite(
    args: argparse.Namespace,
    profile_path: Path,
    run_env: Callable[[str, Arguments], dict[str, str]] | None = None,
) -> None:
    if args.list_datasets:
        print("\n".join(case_names()))
        return

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "runs").mkdir(exist_ok=True)

    results: list[RunResult] = []

    dataset_names = list(args.datasets)
    total = len(dataset_names) * args.runs
    completed = 0

    for dataset in dataset_names:
        try:
            dataset_arguments = profile_arguments(args, dataset)
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            raise SystemExit(f"Invalid arguments for dataset {dataset}: {exc}") from exc
        for run in range(1, args.runs + 1):
            completed += 1
            timings_path = run_file(out_dir, dataset, run, "_timings.json")
            ga_metrics_path = run_file(out_dir, dataset, run, "_ga_metrics.json")
            operator_metrics_path = run_file(out_dir, dataset, run, "_operator_metrics.jsonl")
            candidate_metrics_path = run_file(out_dir, dataset, run, "_candidate_metrics.jsonl")
            quality_metrics_path = run_file(out_dir, dataset, run, "_quality_metrics.jsonl")
            clingo_metrics_path = run_file(out_dir, dataset, run, "_clingo_metrics.jsonl")
            log_path = run_file(out_dir, dataset, run, ".log")
            cprofile_path = run_file(out_dir, dataset, run, ".prof")
            incremental_metrics_path = run_file(out_dir, dataset, run, "_incremental_metrics.jsonl")
            reset_run_outputs(
                [
                    timings_path,
                    timings_path.with_name(timings_path.name.replace("_timings.json", "_resources.json")),
                    ga_metrics_path,
                    operator_metrics_path,
                    candidate_metrics_path,
                    quality_metrics_path,
                    clingo_metrics_path,
                    log_path,
                    cprofile_path,
                    incremental_metrics_path,
                ]
            )
            cmd, arguments_json = build_command(
                args.python, dataset_arguments, profile_path
            )
            if args.cprofile:
                cmd = [
                    args.python,
                    "-m",
                    "cProfile",
                    "-o",
                    str(cprofile_path.resolve()),
                    *cmd[1:],
                ]
            seed = args.seed_base + completed - 1
            experiment_id = f"{dataset}_seed_{seed}"

            print(
                f"[{completed}/{total}] {dataset} run {run}/{args.runs} timeout={args.timeout_seconds}s",
                flush=True,
            )
            started = time.perf_counter()
            returncode, timed_out = run_streamed(
                cmd,
                arguments_json,
                log_path,
                args.timeout_seconds,
                timings_path,
                ga_metrics_path,
                operator_metrics_path,
                candidate_metrics_path,
                quality_metrics_path,
                clingo_metrics_path,
                dataset,
                run,
                seed,
                run_env(dataset, dataset_arguments) if run_env is not None else None,
                instrumentation_level=getattr(args, "instrumentation", "full"),
            )
            elapsed = time.perf_counter() - started
            status = "timeout" if timed_out else "ok" if returncode == 0 else "failed"
            parsed = parse_log(log_path)
            if returncode == 0:
                write_debug_clingo_program(
                    REPO_ROOT / ".debug" / "clingo",
                    dataset,
                    dataset_arguments,
                    parsed["best_program"],
                )
            run_result = RunResult(
                dataset=dataset,
                run=run,
                seed=seed,
                experiment_id=experiment_id,
                status=status,
                returncode=returncode,
                elapsed_seconds=elapsed,
                command=cmd,
                arguments_json=arguments_json,
                log_path=str(log_path),
                success=parsed["success"],
                cprofile_path=str(cprofile_path) if args.cprofile else "",
            )
            results.append(run_result)
            compress_run_jsonl(out_dir, dataset, run)
            print(
                f"[{completed}/{total}] {dataset} run {run} {status} {elapsed:.2f}s\n",
                flush=True,
            )
            if timed_out and getattr(args, "stop_on_timeout", False):
                print("Stopping configuration after first timeout.", flush=True)
                break
        if results and results[-1].status == "timeout" and getattr(args, "stop_on_timeout", False):
            break
    write_outputs(out_dir, results, getattr(args, "instrumentation", "full"))


# Line-oriented metrics each run writes; stored gzip-compressed once the run ends.
RUN_JSONL_SUFFIXES = (
    "_operator_metrics.jsonl",
    "_candidate_metrics.jsonl",
    "_quality_metrics.jsonl",
    "_clingo_metrics.jsonl",
    "_incremental_metrics.jsonl",
)


def run_file(out_dir: Path, dataset: str, run: int, suffix: str) -> Path:
    """Return the path of one per-run artifact inside an experiment directory."""
    return out_dir / "runs" / f"{dataset}_run_{run}{suffix}"


def compress_run_jsonl(out_dir: Path, dataset: str, run: int) -> None:
    """Replace each finished JSONL metric file of one run with its gzip copy."""
    for suffix in RUN_JSONL_SUFFIXES:
        compress_jsonl(run_file(out_dir, dataset, run, suffix))


def compress_jsonl(path: Path) -> None:
    if not path.exists():
        return
    target = path.with_name(path.name + ".gz")
    with path.open("rb") as source, gzip.open(target, "wb") as sink:
        shutil.copyfileobj(source, sink)
    path.unlink()


@dataclass
class RunArtifacts:
    timings: list[TimingMetric]
    ga: list[GAMetric]
    operator: list[dict[str, object]]
    candidate: list[dict[str, object]]
    quality: list[dict[str, object]]
    clingo: list[dict[str, object]]
    epochs: list[dict[str, object]]


def read_run_artifacts(out_dir: Path, result: RunResult) -> RunArtifacts:
    """Read the raw metrics one run wrote; missing files yield no rows."""
    dataset, run = result.dataset, result.run

    def rows(suffix: str) -> list[dict[str, object]]:
        return read_jsonl_rows(
            run_file(out_dir, dataset, run, suffix), dataset, run, result.seed,
            result.experiment_id,
        )

    return RunArtifacts(
        timings=read_timings(run_file(out_dir, dataset, run, "_timings.json"), dataset, run),
        ga=read_ga_metrics(run_file(out_dir, dataset, run, "_ga_metrics.json"), dataset, run),
        operator=rows("_operator_metrics.jsonl"),
        candidate=rows("_candidate_metrics.jsonl"),
        quality=rows("_quality_metrics.jsonl"),
        clingo=rows("_clingo_metrics.jsonl"),
        epochs=rows("_incremental_metrics.jsonl"),
    )


def build_dashboard(out_dir: Path) -> None:
    """Write dashboard_data.json from runs.csv and the raw artifacts in runs/.

    Uses the current aggregation and schema, so it also rebuilds saved results.
    Metrics a run never recorded stay absent, so their charts show an empty
    state instead of invented values.
    """
    with (out_dir / "runs.csv").open(encoding="utf-8", newline="") as file:
        results = [
            RunResult(
                dataset=row["dataset"],
                run=int(row["run"]),
                seed=int(row["seed"]),
                experiment_id=row["experiment_id"],
                status=row["status"],
                returncode=int(row["returncode"]) if row["returncode"] else None,
                elapsed_seconds=float(row["elapsed_seconds"]),
                command=[],
                arguments_json=row["arguments_json"],
                log_path=row["log_path"],
                success=row["success"].lower() == "true",
                cprofile_path=row.get("cprofile_path", ""),
            )
            for row in csv.DictReader(file)
        ]
    results_by_dataset: dict[str, list[RunResult]] = {}
    for result in results:
        results_by_dataset.setdefault(result.dataset, []).append(result)
    benchmarks = []
    # One dataset at a time bounds memory by its runs, not the whole experiment.
    for dataset, dataset_results in sorted(results_by_dataset.items()):
        metrics = RunArtifacts([], [], [], [], [], [], [])
        for result in dataset_results:
            run = read_run_artifacts(out_dir, result)
            metrics.timings.extend(run.timings)
            metrics.ga.extend(run.ga)
            metrics.operator.extend(run.operator)
            metrics.candidate.extend(run.candidate)
            metrics.quality.extend(run.quality)
            metrics.clingo.extend(run.clingo)
            metrics.epochs.extend(run.epochs)
        benchmarks.append(dashboard_benchmark(dataset, dataset_results, metrics))
        del metrics
    write_dashboard_payload(out_dir, benchmarks)


def _default_python() -> str:
    local = Path(".venv") / "Scripts" / "python.exe"
    return str(local.resolve()) if local.exists() else sys.executable


def reset_run_outputs(paths: list[Path]) -> None:
    for path in paths:
        for candidate in (path, path.with_name(path.name + ".gz")):
            try:
                candidate.unlink()
            except FileNotFoundError:
                pass


def profile_arguments(args: argparse.Namespace, dataset: str) -> Arguments:
    if args.arguments_json:
        return arguments_from_json(args.arguments_json, args.set)
    return arguments_for(dataset, args.set)


def build_command(
    python: str, arguments: Arguments, profile_path: Path = PROFILE_BASELINE_PATH
) -> tuple[list[str], str]:
    arguments_payload = arguments_json(arguments)
    return [python, str(profile_path)], arguments_payload


def run_profile_worker() -> None:
    payload = os.environ["GENTIANS_ARGUMENTS_JSON"]
    arguments = Arguments(**json.loads(payload))
    seed = os.environ.get("GENTIANS_RANDOM_SEED")
    if seed is not None:
        arguments.random_seed = int(seed)
    from benchmarks.process_resources import record_process_resources

    path = Path(os.environ["GENTIANS_TIMINGS_PATH"]).with_name(
        Path(os.environ["GENTIANS_TIMINGS_PATH"]).name.replace("_timings.json", "_resources.json")
    )
    with record_process_resources(path):
        gentians_main(arguments)


def run_streamed(
    cmd: list[str],
    arguments_json: str,
    log_path: Path,
    timeout_seconds: int,
    timings_path: Path,
    ga_metrics_path: Path,
    operator_metrics_path: Path,
    candidate_metrics_path: Path,
    quality_metrics_path: Path,
    clingo_metrics_path: Path,
    dataset: str,
    run: int,
    seed: int,
    extra_env: dict[str, str] | None = None,
    instrumentation_level: str = "full",
) -> tuple[int | None, bool]:
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENTIANS_PROFILE_WORKER"] = "1"
    env["GENTIANS_ARGUMENTS_JSON"] = arguments_json
    env["GENTIANS_RANDOM_SEED"] = str(seed)
    env["GENTIANS_BENCHMARK_NAME"] = dataset
    env["GENTIANS_RUN_NUMBER"] = str(run)
    env["GENTIANS_TIMINGS_PATH"] = str(timings_path.resolve())
    env["GENTIANS_GA_METRICS_PATH"] = str(ga_metrics_path.resolve())
    env["GENTIANS_INCREMENTAL_METRICS_PATH"] = str(
        ga_metrics_path.with_name(
            ga_metrics_path.name.replace("_ga_metrics.json", "_incremental_metrics.jsonl")
        ).resolve()
    )
    env["GENTIANS_OPERATOR_METRICS_PATH"] = str(operator_metrics_path.resolve())
    env["GENTIANS_CANDIDATE_METRICS_PATH"] = str(candidate_metrics_path.resolve())
    env["GENTIANS_QUALITY_METRICS_PATH"] = str(quality_metrics_path.resolve())
    env["GENTIANS_CLINGO_METRICS_PATH"] = str(clingo_metrics_path.resolve())
    if extra_env:
        env.update(extra_env)
    if instrumentation_level == "light":
        for category in ("OPERATOR", "CANDIDATE", "QUALITY", "CLINGO"):
            env.pop(f"GENTIANS_{category}_METRICS_PATH", None)
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
            cwd=str(REPO_ROOT),
        )
        assert process.stdout is not None
        lines: queue.Queue[str | None] = queue.Queue()

        def reader() -> None:
            try:
                for line in process.stdout:
                    lines.put(line)
            finally:
                lines.put(None)

        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        deadline = time.monotonic() + timeout_seconds if timeout_seconds > 0 else None
        done = False
        while True:
            try:
                line = lines.get(timeout=0.2)
                if line is None:
                    done = True
                else:
                    print(line, end="", flush=True)
                    log.write(line)
                    log.flush()
            except queue.Empty:
                pass
            if process.poll() is not None and done:
                return process.wait(), False
            if deadline is not None and time.monotonic() > deadline:
                kill_tree(process)
                thread.join(timeout=2)
                return process.wait(), True


def kill_tree(process: subprocess.Popen[str]) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        process.kill()


def parse_log(path: Path) -> dict[str, object]:
    success = False
    best_program: list[str] | None = None
    capturing_program = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "Found best program" in line:
            success = True
            best_program = []
            capturing_program = True
            continue
        if "Best candidate program" in line:
            best_program = []
            capturing_program = True
            continue
        if capturing_program:
            if line == "--------------------------" or line.startswith("Total time:"):
                capturing_program = False
            elif best_program is not None:
                best_program.append(line)
    return {
        "success": success,
        "best_program": best_program,
    }


def write_debug_clingo_program(
    directory: Path,
    dataset: str,
    arguments: Arguments,
    best_program: object,
) -> None:
    if arguments.filename is None or not isinstance(best_program, list):
        return
    task = parse_file(arguments.filename)
    lp_path = directory / f"{safe_filename(dataset)}.lp"
    args_path = directory / f"{safe_filename(dataset)}.args.txt"
    directory.mkdir(parents=True, exist_ok=True)
    static_program = compile_coverage_program(
        task.positive_examples, task.negative_examples
    )
    lp_path.write_text(
        "\n".join(
            (
                *render_program(task.background),
                *render_program(static_program),
                *(str(rule) for rule in best_program),
            )
        ),
        encoding="utf-8",
    )
    args_path.write_text(
        f"python -m clingo {' '.join(evaluation_clingo_arguments(arguments))} {lp_path}\n",
        encoding="utf-8",
    )


def evaluation_clingo_arguments(arguments: Arguments) -> list[str]:
    evaluation = arguments.evaluation
    if not isinstance(evaluation, dict):
        evaluation = {}
    clingo_args = evaluation.get("clingo_arguments", [])
    if isinstance(clingo_args, str):
        clingo_args = [clingo_args]
    return ["0", *[str(arg) for arg in clingo_args]]


def safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value)


def read_timings(path: Path, dataset: str, run: int) -> list[TimingMetric]:
    rows = read_json_rows(path)
    return [
        TimingMetric(
            dataset, run, row["metric"], float(row["seconds"]), int(row["calls"])
        )
        for row in rows
    ]


def read_ga_metrics(path: Path, dataset: str, run: int) -> list[GAMetric]:
    rows = read_json_rows(path)
    return [
        GAMetric(
            dataset,
            run,
            int(row["generation"]),
            float(row["max_fitness"]),
            float(row["avg_fitness"]),
            float(row["best_so_far"]),
            to_float(row.get("population_size")),
            to_float(row.get("unique_signatures")),
            to_float(row.get("diversity")),
            to_float(row.get("invalid_count")),
            to_float(row.get("invalid_rate")),
            to_float(row.get("mean_program_size")),
            to_float(row.get("elapsed_seconds")),
            int(to_float(row.get("fitness_evaluations"))),
            bool(row.get("restarted", False)),
        )
        for row in rows
    ]


def read_json_rows(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except PermissionError, json.JSONDecodeError:
        return []


def read_jsonl_rows(
    path: Path, dataset: str, run: int, seed: int, experiment_id: str
) -> list[dict[str, object]]:
    """Read a run's JSONL metrics, plain while running or gzip once finished."""
    compressed = path.with_name(path.name + ".gz")
    if path.exists():
        text = path.read_text(encoding="utf-8", errors="replace")
    elif compressed.exists():
        with gzip.open(compressed, "rt", encoding="utf-8", errors="replace") as file:
            text = file.read()
    else:
        return []
    rows: list[dict[str, object]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        row = {
            "dataset": dataset,
            "run": run,
            "seed": seed,
            "experiment_id": experiment_id,
            **row,
        }
        rows.append(row)
    return rows


def write_outputs(out_dir: Path, results: list[RunResult], instrumentation_level: str) -> None:
    """Index the runs and summarize them; per-run artifacts in runs/ stay the only raw copy."""
    write_csv(out_dir / "runs.csv", [asdict(r) for r in results])
    if instrumentation_level == "light":
        (out_dir / "dashboard_data.json").unlink(missing_ok=True)
        (out_dir / "measurement.json").write_text(
            json.dumps({
                "instrumentation": "light",
                "available": ["runs", "timings", "ga", "incremental_epoch_jsonl"],
                "unmeasured": ["operator", "candidate", "quality", "clingo"],
                "dashboard": False,
            }, indent=2), encoding="utf-8",
        )
        return
    build_dashboard(out_dir)


def write_dashboard_data(
    out_dir: Path,
    results: list[RunResult],
    timings: list[TimingMetric],
    ga_metrics: list[GAMetric],
    operator_metrics: list[dict[str, object]],
    candidate_metrics: list[dict[str, object]],
    quality_metrics: list[dict[str, object]],
    clingo_metrics: list[dict[str, object]],
    *,
    epoch_metrics: Sequence[dict[str, object]] = (),
) -> None:
    results_by_dataset: dict[str, list[RunResult]] = {}
    for result in results:
        results_by_dataset.setdefault(result.dataset, []).append(result)
    timings_by_dataset: dict[str, list[TimingMetric]] = {}
    for timing in timings:
        timings_by_dataset.setdefault(timing.dataset, []).append(timing)
    ga_by_dataset: dict[str, list[GAMetric]] = {}
    for metric in ga_metrics:
        ga_by_dataset.setdefault(metric.dataset, []).append(metric)
    operator_by_dataset = _rows_by_dataset(operator_metrics)
    candidate_by_dataset = _rows_by_dataset(candidate_metrics)
    quality_by_dataset = _rows_by_dataset(quality_metrics)
    clingo_by_dataset = _rows_by_dataset(clingo_metrics)
    epochs_by_dataset = _rows_by_dataset(list(epoch_metrics))
    write_dashboard_payload(out_dir, [
        dashboard_benchmark(
            dataset,
            results_by_dataset[dataset],
            RunArtifacts(
                timings=timings_by_dataset.get(dataset, []),
                ga=ga_by_dataset.get(dataset, []),
                operator=operator_by_dataset.get(dataset, []),
                candidate=candidate_by_dataset.get(dataset, []),
                quality=quality_by_dataset.get(dataset, []),
                clingo=clingo_by_dataset.get(dataset, []),
                epochs=epochs_by_dataset.get(dataset, []),
            ),
        )
        for dataset in sorted(results_by_dataset)
    ])


def write_dashboard_payload(out_dir: Path, benchmarks: list[dict[str, object]]) -> None:
    payload = {"schemaVersion": DASHBOARD_SCHEMA_VERSION, "benchmarks": benchmarks}
    (out_dir / "dashboard_data.json").write_text(
        json.dumps(json_safe(payload), separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )


def dashboard_benchmark(
    dataset: str, results: list[RunResult], metrics: RunArtifacts,
) -> dict[str, object]:
    """Aggregate every metric of one dataset; each run weighs the same."""
    phases = dashboard_phases(metrics.timings)
    totals = [timing for timing in metrics.timings if timing.metric == "total_execution"]
    clingo_by_run = _rows_by_run_number(metrics.clingo)
    solve_runs = _category_rows_by_run(clingo_by_run, "solving")
    ground_runs = _category_rows_by_run(clingo_by_run, "grounding")
    # Incremental search records one prepared space per batch; the largest
    # is the clause space the run reached. Steady-state records one.
    largest_space_by_run: dict[int, float] = {}
    for row in metrics.candidate:
        if is_clause_generation_metric(row):
            run = int(to_float(row.get("run")))
            largest_space_by_run[run] = max(
                largest_space_by_run.get(run, 0.0), candidate_clause_count(row)
            )
    progress = _progress_by_run(metrics.ga)
    return {
        "name": dataset,
        "algorithm": run_algorithm(results),
        "candidates": int(mean(largest_space_by_run.values())),
        "restarts": mean(sum(point.restarted for point in points) for points in progress),
        "epochs": dashboard_epochs(metrics.epochs),
        "total": mean(timing.seconds for timing in totals),
        "instrumentedRuns": len({timing.run for timing in totals}),
        "runCount": len(results),
        "bestFoundRuns": sum(1 for result in results if result.success),
        "solveCalls": mean(len(rows) for rows in solve_runs.values()),
        "groundCalls": mean(len(rows) for rows in ground_runs.values()),
        "atoms": mean_run_call_mean(metrics.clingo, sorted(clingo_by_run), "stats_atoms"),
        "groundRules": mean_run_call_mean(metrics.clingo, sorted(clingo_by_run), "stats_rules"),
        "choices": _mean_run_sum(solve_runs, "stats_choices"),
        "conflicts": _mean_run_sum(solve_runs, "stats_conflicts"),
        "models": _mean_run_sum(solve_runs, "models"),
        "dominant": dominant_phase(phases),
        "phases": phases,
        "fitnessRuns": dashboard_fitness_runs(metrics.ga),
        "fitnessMean": dashboard_fitness_mean(metrics.ga),
        "operatorSummary": operator_summary(metrics.operator),
        "quality": dashboard_quality(metrics.quality),
        "clingoSummary": clingo_summary(metrics.clingo),
    }


def _category_rows_by_run(
    rows_by_run: dict[int, list[dict[str, object]]], category: str,
) -> dict[int, list[dict[str, object]]]:
    """Keep the runs that made at least one call of this Clingo category."""
    selected = {
        run: [row for row in rows if row.get("operation_category") == category]
        for run, rows in rows_by_run.items()
    }
    return {run: rows for run, rows in selected.items() if rows}


def _mean_run_sum(rows_by_run: dict[int, list[dict[str, object]]], key: str) -> float:
    return mean(sum(to_float(row.get(key)) for row in rows) for rows in rows_by_run.values())


def dashboard_phases(timings: list[TimingMetric]) -> dict[str, dict[str, float]]:
    runs = sorted({timing.run for timing in timings})
    totals: dict[tuple[int, str], float] = {}
    for timing in timings:
        key = (timing.run, timing.metric)
        totals[key] = totals.get(key, 0.0) + timing.seconds
    values = {
        metric: mean(totals.get((run, metric), 0.0) for run in runs)
        for metric in sorted({timing.metric for timing in timings})
    }

    def phase(source: str) -> dict[str, float]:
        grounding = sum_nested_metric(values, source, "grounding")
        solving = sum_nested_metric(values, source, "solving")
        closure = sum_nested_metric(values, source, "closure")
        self_metric = f"{source}.self"
        inclusive_python = (
            values[self_metric]
            if self_metric in values
            else values.get(source, 0.0)
        )
        return {
            "python": max(inclusive_python - grounding - solving - closure, 0.0),
            "grounding": grounding,
            "solving": solving,
            "closure": closure,
        }

    phases = {
        "clauseGeneration": phase("clause_generation"),
        "initialization": phase("initialization"),
        "selection": phase("selection"),
        "crossover": phase("crossover"),
        "mutation": phase("mutation"),
        "replacement": phase("replacement"),
        "gaPython": phase("search"),
    }
    total = values.get("total_execution", 0.0)
    measured = sum(sum(type_values.values()) for type_values in phases.values())
    phases["gaPython"]["python"] += max(total - measured, 0.0)
    return phases


def dominant_phase(phases: dict[str, dict[str, float]]) -> str:
    totals = {
        kind: sum(row.get(kind, 0.0) for row in phases.values())
        for kind in ("python", "grounding", "solving", "closure")
    }
    return max(totals, key=totals.get)


def _progress_by_run(metrics: list[GAMetric]) -> list[list[GAMetric]]:
    by_run: dict[int, list[GAMetric]] = {}
    for metric in metrics:
        by_run.setdefault(metric.run, []).append(metric)
    return [
        sorted(points, key=lambda metric: metric.generation)
        for _, points in sorted(by_run.items())
    ]


def _progress_position(metric: GAMetric, axis: str) -> float:
    if axis == "seconds":
        return metric.elapsed_seconds
    if axis == "evaluations":
        return float(metric.fitness_evaluations)
    return float(metric.generation)


def thin_progress(points: list[GAMetric], limit: int = RUN_PROGRESS_POINTS) -> list[GAMetric]:
    """Keep at most `limit` points of one run, plus every event the chart marks.

    The first and last points, each best-so-far improvement and each restart
    always survive; evenly spaced points fill the remaining budget.
    """
    if len(points) <= limit:
        return points
    kept = {0, len(points) - 1}
    kept.update(
        index for index in range(1, len(points))
        if points[index].best_so_far != points[index - 1].best_so_far
        or points[index].restarted
    )
    spare = limit - len(kept)
    if spare > 0:
        step = len(points) / spare
        kept.update(int(slot * step) for slot in range(spare))
    return [points[index] for index in sorted(kept)]


def dashboard_fitness_mean(metrics: list[GAMetric]) -> dict[str, dict[str, list[list[float]]]]:
    """Aggregate progress across runs on a grid for every x axis.

    Each run carries its last value forward from its first recorded point. For
    max, avg and best so far a row is [x, mean, min, max]; best is [x, highest max].
    """
    runs = _progress_by_run(metrics)
    fields = {
        "max": lambda metric: metric.max_fitness,
        "avg": lambda metric: metric.avg_fitness,
        "bestSoFar": lambda metric: metric.best_so_far,
    }
    result: dict[str, dict[str, list[list[float]]]] = {}
    for axis in PROGRESS_AXES:
        series: dict[str, list[list[float]]] = {"best": [], **{name: [] for name in fields}}
        tracks = []
        for points in runs:
            # Sort by position only: ties keep generation order.
            track = sorted(
                (
                    (_progress_position(point, axis), point)
                    for point in points
                    if math.isfinite(_progress_position(point, axis))
                ),
                key=lambda item: item[0],
            )
            if track:
                tracks.append(track)
        positions = sorted({position for track in tracks for position, _ in track})
        if len(positions) > MEAN_PROGRESS_POINTS:
            low, high = positions[0], positions[-1]
            step = (high - low) / (MEAN_PROGRESS_POINTS - 1)
            positions = [low + step * slot for slot in range(MEAN_PROGRESS_POINTS)]
        cursors = [0] * len(tracks)
        for position in positions:
            current: list[GAMetric] = []
            for index, track in enumerate(tracks):
                while cursors[index] < len(track) and track[cursors[index]][0] <= position:
                    cursors[index] += 1
                if cursors[index]:
                    current.append(track[cursors[index] - 1][1])
            for name, value in fields.items():
                values = [value(point) for point in current if math.isfinite(value(point))]
                if values:
                    series[name].append(
                        [position, sum(values) / len(values), min(values), max(values)]
                    )
            highest = [point.max_fitness for point in current if math.isfinite(point.max_fitness)]
            if highest:
                series["best"].append([position, max(highest)])
        result[axis] = series
    return result


def dashboard_fitness_runs(metrics: list[GAMetric]) -> list[dict[str, object]]:
    runs = []
    for points in _progress_by_run(metrics):
        points = thin_progress(points)
        runs.append(
            {
                "points": [
                    [
                        point.generation,
                        point.elapsed_seconds,
                        point.fitness_evaluations,
                        point.max_fitness,
                        point.avg_fitness,
                        point.best_so_far,
                        point.diversity,
                        point.invalid_rate,
                        point.restarted,
                    ]
                    for point in points
                ],
            }
        )
    return runs


def run_algorithm(results: list[RunResult]) -> str:
    """Return the search algorithm shared by the runs of one dataset."""
    algorithms = {
        str(json.loads(result.arguments_json).get("algorithm", "steady_state"))
        for result in results
    }
    if len(algorithms) > 1:
        raise ValueError(f"runs mix search algorithms: {sorted(algorithms)}")
    return algorithms.pop() if algorithms else ""


def dashboard_epochs(rows: list[dict[str, object]]) -> dict[str, object] | None:
    """Summarize incremental epochs with equal weight per run."""
    if not rows:
        return None
    by_run = _rows_by_run_number(rows)
    return {
        "runs": len(by_run),
        "meanEpochs": mean(len(run_rows) for run_rows in by_run.values()),
        "reasons": [
            {
                "reason": reason,
                "meanCount": mean(
                    sum(row.get("reason") == reason for row in run_rows)
                    for run_rows in by_run.values()
                ),
            }
            for reason in EPOCH_REASONS
        ],
        "meanActiveClauses": mean(to_float(row.get("active_clauses")) for row in rows),
        "meanGenerations": mean(to_float(row.get("generations")) for row in rows),
        "meanEvaluations": mean(to_float(row.get("evaluations")) for row in rows),
    }


def dashboard_quality(rows: list[dict[str, object]]) -> dict[str, object]:
    run_ids = {int(to_float(row.get("run"))) for row in rows}
    run_count = len(run_ids)
    coverage: dict[tuple[float, float], dict[str, object]] = {}
    criteria_by_run: dict[int, dict[str, int]] = {}
    evaluated_sizes: dict[float, int] = {}
    winner_sizes: dict[int, float] = {}
    extent = {"positive": 0.0, "negative": 0.0}

    for row in rows:
        run = int(to_float(row.get("run")))
        positive = to_float(row.get("covered_positive"))
        negative = to_float(row.get("covered_negative"))
        total_positive = to_float(row.get("total_positive"))
        total_negative = to_float(row.get("total_negative"))
        score = to_float(row.get("score"))
        best = bool(to_float(row.get("best_found")))
        size = to_float(row.get("program_size"))

        extent["positive"] = max(extent["positive"], total_positive, positive)
        extent["negative"] = max(extent["negative"], total_negative, negative)

        point = coverage.setdefault(
            (positive, negative),
            {"count": 0, "score_total": 0.0, "best": False},
        )
        point["count"] = int(point["count"]) + 1
        point["score_total"] = float(point["score_total"]) + score
        point["best"] = bool(point["best"]) or best

        counts = criteria_by_run.setdefault(
            run,
            {
                "total": 0,
                "complete": 0,
                "incomplete": 0,
                "consistent": 0,
                "inconsistent": 0,
                "both": 0,
            },
        )
        complete = bool(row["complete"])
        consistent = bool(row["consistent"])
        counts["total"] += 1
        counts["complete"] += int(complete)
        counts["incomplete"] += int(not complete)
        counts["consistent"] += int(consistent)
        counts["inconsistent"] += int(not consistent)
        counts["both"] += int(complete and consistent)

        evaluated_sizes[size] = evaluated_sizes.get(size, 0) + 1
        if best:
            winner_sizes[run] = size

    best_sizes: dict[float, int] = {}
    for size in winner_sizes.values():
        best_sizes[size] = best_sizes.get(size, 0) + 1

    coverage_points = []
    for (positive, negative), values in sorted(coverage.items()):
        count = int(values["count"])
        coverage_points.append(
            {
                "positive": positive,
                "negative": negative,
                "count": count,
                "meanCount": count / run_count if run_count else 0.0,
                "runs": run_count,
                "meanScore": float(values["score_total"]) / count,
                "best": bool(values["best"]),
            }
        )

    criteria = []
    if run_count:
        for key in (
            "complete",
            "incomplete",
            "consistent",
            "inconsistent",
            "both",
        ):
            counts = [values[key] for values in criteria_by_run.values()]
            criteria.append(
                {
                    "key": key,
                    "rate": mean(
                        100 * values[key] / values["total"]
                        for values in criteria_by_run.values()
                    ),
                    "meanCount": mean(counts),
                    "count": sum(counts),
                    "runs": run_count,
                }
            )

    return {
        "coveragePoints": coverage_points,
        "criteria": criteria,
        "extent": extent,
        "programSizes": [
            {
                "size": size,
                "evaluated": count,
                "best": best_sizes.get(size, 0),
            }
            for size, count in sorted(evaluated_sizes.items())
        ],
    }


def _rows_by_dataset(rows: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("dataset", "")), []).append(row)
    return grouped


def _rows_by_run_number(rows: list[dict[str, object]]) -> dict[int, list[dict[str, object]]]:
    grouped: dict[int, list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault(int(to_float(row.get("run"))), []).append(row)
    return grouped


def normalize_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for row in rows:
        normalized.append(
            {
                key: json.dumps(value, sort_keys=True)
                if isinstance(value, (dict, list))
                else value
                for key, value in row.items()
            }
        )
    return normalized


def operator_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    summary: list[dict[str, object]] = []
    groups: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    for row in rows:
        if row.get("operator"):
            key = (
                str(row.get("dataset", "")),
                str(row.get("operator", "")),
                str(row.get("strategy", "")),
            )
            groups.setdefault(key, []).append(row)
    for (dataset, operator, strategy), selected in sorted(groups.items()):
        run_summaries = [
            operator_run_summary(operator, run_rows)
            for run_rows in _rows_by_run_number(selected).values()
        ]
        summary.append(
            {
                "dataset": dataset,
                "operator": operator,
                "strategy": strategy,
                "events": mean(row["events"] for row in run_summaries),
                "slots": mean(row["slots"] for row in run_summaries),
                "applied_rate": mean(row["applied_rate"] for row in run_summaries),
                "skipped_rate": mean(row["skipped_rate"] for row in run_summaries),
                "valid_rate": mean_optional(row["valid_rate"] for row in run_summaries),
                "duplicate_rate": mean_optional(
                    row["duplicate_rate"] for row in run_summaries
                ),
                "invalid_rate": mean_optional(
                    row["invalid_rate"] for row in run_summaries
                ),
                "improvement_rate": mean_optional(
                    row["improvement_rate"] for row in run_summaries
                ),
                "worse_or_equal_rate": mean_optional(
                    row["worse_or_equal_rate"] for row in run_summaries
                ),
                "best_rate": mean(row["best_rate"] for row in run_summaries),
                "changed_rate": (
                    mean_optional(row["changed_rate"] for row in run_summaries)
                    if operator == "mutation"
                    else None
                ),
                "mean_score_delta": mean_optional(
                    row["mean_score_delta"] for row in run_summaries
                ),
                "crossover_strategy": next(
                    (
                        str(row.get("crossover_strategy"))
                        for row in selected
                        if row.get("crossover_strategy")
                    ),
                    "",
                ),
                "crossover_gain_events": (
                    mean(row["crossover_gain_events"] for row in run_summaries)
                    if operator == "mutation"
                    else None
                ),
                "lost_crossover_gain_rate": (
                    mean_optional(row["lost_crossover_gain_rate"] for row in run_summaries)
                    if operator == "mutation"
                    else None
                ),
                "retained_crossover_gain_rate": (
                    mean_optional(row["retained_crossover_gain_rate"] for row in run_summaries)
                    if operator == "mutation"
                    else None
                ),
            }
        )
    return summary


def operator_run_summary(
    operator: str, selected: list[dict[str, object]]
) -> dict[str, float | None]:
    events = len(selected)
    slots = sum(operator_slots(row) for row in selected)
    applied_events = sum(1 for row in selected if operator_applied(row))
    skipped_slots = sum(
        operator_slots(row)
        for row in selected
        if operator_skipped(row)
    )
    valid_new_count = operator_valid_new_count(selected, operator)
    duplicate_count = operator_duplicate_count(selected, operator)
    invalid_count = operator_invalid_count(selected, operator)
    accepted_count = sum(to_float(row.get("accepted")) for row in selected)
    not_competitive_count = sum(
        to_float(row.get("not_competitive"))
        for row in selected
    )
    best_count = operator_best_count(selected, operator)
    replacement_operator = operator == "replacement"
    crossover_gain_events = sum(to_float(row.get("crossover_improved")) for row in selected)
    lost_crossover_gain_events = sum(
        to_float(row.get("lost_crossover_gain")) for row in selected
    )
    # Improvement and score delta share one denominator: new results with both scores.
    scored = [
        row
        for row in selected
        if row.get("valid_new") is True
        and row.get("new_score") not in (None, "")
        and row.get("original_score") not in (None, "")
    ]
    improved_count = operator_improved_count(
        selected if replacement_operator else scored, operator
    )
    score_deltas = [
        to_float(row.get("new_score")) - to_float(row.get("original_score"))
        for row in scored
    ]
    replacement_deltas = [
        to_float(row.get("candidate_score")) - to_float(row.get("victim_score"))
        for row in selected
        if row.get("accepted") is True and row.get("victim_score") not in (None, "")
    ]
    improvement_denominator = (
        accepted_count + not_competitive_count
        if replacement_operator
        else float(len(score_deltas)) if score_deltas else None
    )
    worse_or_equal_count = (
        max(improvement_denominator - improved_count, 0.0)
        if improvement_denominator is not None
        else None
    )
    if operator in {"crossover", "mutation"}:
        mean_score_delta = mean(score_deltas) if score_deltas else None
    elif replacement_operator:
        mean_score_delta = mean(replacement_deltas)
    else:
        mean_score_delta = None
    return {
        "events": float(events),
        "slots": slots,
        "applied_rate": applied_events / events if events else 0.0,
        "skipped_rate": skipped_slots / slots if slots else 0.0,
        "valid_rate": (
            (accepted_count if replacement_operator else valid_new_count) / slots
            if operator in {"crossover", "mutation", "replacement"} and slots
            else None
        ),
        "duplicate_rate": duplicate_count / slots if slots else None,
        "invalid_rate": invalid_count / slots if slots else None,
        "improvement_rate": (
            improved_count / improvement_denominator
            if improvement_denominator
            else 0.0 if improvement_denominator == 0.0 else None
        ),
        "worse_or_equal_rate": (
            worse_or_equal_count / improvement_denominator
            if improvement_denominator
            else 0.0 if improvement_denominator == 0.0 else None
        ),
        "best_rate": best_count / slots if slots else 0.0,
        "changed_rate": mean_bool(selected, "changed")
        if operator == "mutation"
        else None,
        "mean_score_delta": mean_score_delta,
        "crossover_gain_events": crossover_gain_events,
        "lost_crossover_gain_rate": (
            lost_crossover_gain_events / crossover_gain_events
            if crossover_gain_events
            else None
        ),
        "retained_crossover_gain_rate": (
            1.0 - lost_crossover_gain_events / crossover_gain_events
            if crossover_gain_events
            else None
        ),
    }


def operator_slots(row: dict[str, object]) -> float:
    return to_float(row.get("slots"))


def operator_applied(row: dict[str, object]) -> bool:
    return bool(to_float(row.get("applied")))


def operator_skipped(row: dict[str, object]) -> bool:
    return bool(to_float(row.get("skipped")))


def operator_valid_new_count(
    rows: list[dict[str, object]], operator: str
) -> float:
    return sum(to_float(row.get("valid_new")) for row in rows)


def operator_duplicate_count(
    rows: list[dict[str, object]], operator: str
) -> float:
    return sum(to_float(row.get("duplicate")) for row in rows)


def operator_invalid_count(
    rows: list[dict[str, object]], operator: str
) -> float:
    return sum(to_float(row.get("invalid")) for row in rows)


def operator_improved_count(
    rows: list[dict[str, object]], operator: str
) -> float:
    if operator == "replacement":
        return sum(to_float(row.get("improved_victim")) for row in rows)
    return sum(to_float(row.get("improved")) for row in rows)


def operator_best_count(rows: list[dict[str, object]], operator: str) -> float:
    return sum(to_float(row.get("is_best")) for row in rows)


def is_clause_generation_metric(row: dict[str, object]) -> bool:
    return row.get("metric") == "clause_generation"


def candidate_clause_count(row: dict[str, object]) -> float:
    return to_float(row.get("clauses"))


def clingo_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    summary: list[dict[str, object]] = []
    groups: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    runs_by_dataset: dict[str, set[int]] = {}
    for row in rows:
        dataset = str(row.get("dataset", ""))
        if row.get("run") not in (None, ""):
            runs_by_dataset.setdefault(dataset, set()).add(int(to_float(row.get("run"))))
        if row.get("operation_category"):
            groups.setdefault(
                (
                    dataset,
                    str(row.get("operation_category", "")),
                    str(row.get("phase_context", "")),
                ),
                [],
            ).append(row)
    for dataset, operation_category, phase_context in sorted(groups):
        run_ids = sorted(runs_by_dataset.get(dataset) or {0})
        selected = groups[(dataset, operation_category, phase_context)]
        selected_by_run: dict[int, list[dict[str, object]]] = {}
        for row in selected:
            selected_by_run.setdefault(int(to_float(row.get("run"))), []).append(row)
        calls = mean(len(selected_by_run.get(run, [])) for run in run_ids)
        total_seconds = mean(
            sum(to_float(row.get("seconds")) for row in selected_by_run.get(run, []))
            for run in run_ids
        )
        total_models = mean(
            sum(to_float(row.get("models")) for row in selected_by_run.get(run, []))
            for run in run_ids
        )
        summary.append(
            {
                "dataset": dataset,
                "operation_category": operation_category,
                "phase_context": phase_context,
                "calls": calls,
                "total_seconds": total_seconds,
                "total_models": total_models,
            }
        )
    return summary


def mean_run_call_mean(
    rows: list[dict[str, object]], run_ids: list[int], key: str
) -> float:
    rows_by_run: dict[int, list[dict[str, object]]] = {}
    for row in rows:
        if row.get(key) not in (None, ""):
            rows_by_run.setdefault(int(to_float(row.get("run"))), []).append(row)
    return mean(
        mean(to_float(row.get(key)) for row in run_rows)
        for run in run_ids
        if (run_rows := rows_by_run.get(run))
    )


def sum_nested_metric(values: dict[str, float], phase: str, suffix: str) -> float:
    return sum(
        value
        for metric, value in values.items()
        if metric == f"{phase}.{suffix}"
        or (metric.startswith(f"{phase}.") and metric.endswith(f".{suffix}"))
    )


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def mean_optional(values: Iterable[float | None]) -> float | None:
    values = [value for value in values if value is not None]
    return mean(values) if values else None


def to_float(value: object) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else 0.0
    if isinstance(value, str):
        if value.lower() == "true":
            return 1.0
        if value.lower() == "false":
            return 0.0
        try:
            number = float(value)
            return number if math.isfinite(number) else 0.0
        except ValueError:
            return 0.0
    return 0.0


def json_safe(value: object) -> object:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    return value


def mean_bool(rows: list[dict[str, object]], key: str) -> float:
    values = [
        to_float(row.get(key))
        for row in rows
        if key in row and row.get(key) not in (None, "")
    ]
    return mean(values)


if __name__ == "__main__":
    if os.environ.get("GENTIANS_PROFILE_WORKER") == "1":
        run_profile_worker()
    else:
        main()
