import argparse
import csv
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE_BASELINE_PATH = Path(__file__).resolve()
sys.path.insert(0, str(REPO_ROOT))

from gentians import Arguments, main as gentians_main


@dataclass(frozen=True)
class DatasetConfig:
    task: str
    arguments: dict[str, object]


@dataclass
class RunResult:
    dataset: str
    run: int
    status: str
    returncode: int | None
    elapsed_seconds: float
    command: list[str]
    log_path: str
    cprofile_path: str
    total_seconds: float | None = None
    success: bool = False
    first_success_generation_observed: int | None = None


@dataclass
class FitnessPoint:
    dataset: str
    run: int
    generation: int
    best_current: float
    best_so_far: float


@dataclass
class PhaseTime:
    dataset: str
    run: int
    phase: str
    inclusive_ms: float
    exclusive_ms: float
    calls: int


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


def cfg(task: str, **arguments: object) -> DatasetConfig:
    return DatasetConfig(task=task, arguments=dict(arguments))


DATASETS = {
    "coin": cfg("coin"),
    "knapsack": cfg("knapsack"),
    "4queens": cfg(
        "4queens",
        max_depth=5,
        prob_increase=0.8,
        arithmetic_operators=["add", "sub"],
        comparison_operators=["lt"],
    ),
    "adj2red": cfg("adjacent_to_red", max_depth=4),
    "clique": cfg("clique", max_depth=6, comparison_operators=["neq"]),
    "coloring": cfg("coloring", disjunctive_head_length=3, max_depth=4),
    "evenodd": cfg("even_odd"),
    "grandparent": cfg("grandparent"),
    "sudoku": cfg("sudoku", max_depth=3),
    "subsum2prod": cfg(
        "subset_sum_double_and_prod",
        max_depth=4,
        aggregates=["sum(el/2)", "sum(el/2)"],
        arithmetic_operators=["add", "mul", "sub"],
        max_variables=5,
    ),
}


DEFAULT_DATASETS = ["coin", "knapsack", "adj2red"]


DEFAULT_ARGUMENTS: dict[str, object] = {
    "clauses_to_sample": 2000,
    "prob_increase": 0.5,
    "disjunctive_head_length": 1,
    "max_depth": 3,
    "max_variables": 3,
    "clauses_per_individual": 6,
    "iterations_genetic": 1000,
    "iterations": 5,
    "population_size": 36,
    "mutation_probability": 0.05,
}


ITERATION_RE = re.compile(
    r"Iteration\s+(\d+)\s+-.*best:\s+Program:.*-\s+score:\s+([-+0-9.eE]+)"
)
TOTAL_RE = re.compile(r"Total time:\s+([-+0-9.eE]+)")


PHASE_FUNCTIONS = {
    "sampling.stub_generation": {"sample_clauses_stub"},
    "variable_placement.total": {"place_variables_list_of_clauses"},
    "variable_placement.clause_generation": {"_place_variables_clause"},
    "genetic.total": {"genetic_solver"},
    "genetic.selection": {"tournament", "pick_two_fittest", "get_fittest"},
    "genetic.crossover_inclusive": {"crossover"},
    "genetic.mutation_inclusive": {"mutate"},
    "genetic.evaluation.total": {"evaluate_score"},
    "coverage.extract": {"extract_coverage_and_set_clauses"},
}


STANDARD_TIMING_METRICS = [
    "sampling",
    "variable_placement",
    "variable_placement.grounding",
    "variable_placement.solving",
    "selection",
    "mutation.grounding",
    "mutation.solving",
    "crossover.grounding",
    "crossover.solving",
    "fitness.initialization.grounding",
    "fitness.initialization.solving",
    "fitness.final.grounding",
    "fitness.final.solving",
    "mutation",
    "crossover",
    "fitness.initialization",
    "fitness.final",
]


TIMING_PLOT_ORDER = [
    "sampling",
    "variable_placement",
    "variable_placement.grounding",
    "variable_placement.solving",
    "selection",
    "mutation.grounding",
    "mutation.solving",
    "crossover.grounding",
    "crossover.solving",
    "fitness.initialization.grounding",
    "fitness.initialization.solving",
    "mutation",
    "crossover",
    "fitness.initialization",
    "clingo.grounding.total_all",
    "clingo.solving.total_all",
    "total_execution",
]


TOP_LEVEL_TIMING_PHASES = [
    "sampling",
    "variable_placement",
    "fitness.initialization",
    "selection",
    "crossover",
    "mutation",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="External profiler for baseline GENTIANS. Does not modify gentians code."
    )
    parser.add_argument("--datasets", nargs="+", default=DEFAULT_DATASETS)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument(
        "--out-dir", type=Path, default=Path(".benchmarks") / "baseline_profile"
    )
    parser.add_argument("--timeout-seconds", type=int, default=100)
    parser.add_argument("--python", default=_default_python())
    parser.add_argument("--samples", type=int)
    parser.add_argument("--genetic-iterations", type=int)
    parser.add_argument("--outer-iterations", type=int)
    parser.add_argument("--population", type=int)
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument("--plots-only", action="store_true")
    parser.add_argument(
        "--live-plot-seconds",
        type=float,
        default=2.0,
        help="Seconds between live GA fitness plot refreshes while a run is active.",
    )
    args = parser.parse_args()

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "runs").mkdir(exist_ok=True)

    if args.plots_only:
        results, fitness, phases, timings, ga_metrics = read_existing_outputs(out_dir)
        write_plots(out_dir, fitness, phases, timings, ga_metrics, results)
        return

    results: list[RunResult] = []
    fitness: list[FitnessPoint] = []
    phases: list[PhaseTime] = []
    timings: list[TimingMetric] = []
    ga_metrics: list[GAMetric] = []

    dataset_names = list(args.datasets)
    total = len(dataset_names) * args.runs
    completed = 0
    commands_path = out_dir / "commands.txt"
    commands_path.write_text("", encoding="utf-8")

    for dataset in dataset_names:
        if dataset not in DATASETS:
            raise SystemExit(f"Unknown dataset: {dataset}")
        config = DATASETS[dataset]
        for run in range(1, args.runs + 1):
            completed += 1
            cprofile_path = out_dir / "runs" / f"{dataset}_run_{run}.prof"
            timings_path = out_dir / "runs" / f"{dataset}_run_{run}_timings.json"
            ga_metrics_path = out_dir / "runs" / f"{dataset}_run_{run}_ga_metrics.json"
            log_path = out_dir / "runs" / f"{dataset}_run_{run}.log"
            cmd, arguments_json = build_command(args.python, config, override_arguments(args))
            with commands_path.open("a", encoding="utf-8") as f:
                f.write(f"GENTIANS_ARGUMENTS_JSON={arguments_json} ")
                f.write(subprocess.list2cmdline(cmd) + "\n")

            print(
                f"[{completed}/{total}] {dataset} run {run}/{args.runs} timeout={args.timeout_seconds}s",
                flush=True,
            )
            print("cmd:", subprocess.list2cmdline(cmd), flush=True)
            started = time.perf_counter()
            returncode, timed_out = run_streamed(
                cmd,
                arguments_json,
                log_path,
                args.timeout_seconds,
                timings_path,
                ga_metrics_path,
                out_dir,
                dataset,
                run,
                ga_metrics,
                live_plots=not args.no_plots,
                live_plot_seconds=args.live_plot_seconds,
            )
            elapsed = time.perf_counter() - started
            status = "timeout" if timed_out else "ok" if returncode == 0 else "failed"
            parsed = parse_log(log_path, dataset, run)
            run_result = RunResult(
                dataset=dataset,
                run=run,
                status=status,
                returncode=returncode,
                elapsed_seconds=elapsed,
                command=cmd,
                log_path=str(log_path),
                cprofile_path=str(cprofile_path),
                total_seconds=parsed["total_seconds"],
                success=parsed["success"],
                first_success_generation_observed=parsed[
                    "first_success_generation_observed"
                ],
            )
            results.append(run_result)
            fitness.extend(parsed["fitness"])
            ga_metrics.extend(read_ga_metrics(ga_metrics_path, dataset, run))
            timings.extend(read_timings(timings_path, dataset, run))
            write_outputs(
                out_dir,
                results,
                fitness,
                phases,
                timings,
                ga_metrics,
                include_plots=not args.no_plots,
            )
            print(
                f"[{completed}/{total}] {dataset} run {run} {status} {elapsed:.2f}s",
                flush=True,
            )


def _default_python() -> str:
    local = Path(".venv") / "Scripts" / "python.exe"
    return str(local.resolve()) if local.exists() else sys.executable


def override_arguments(args: argparse.Namespace) -> dict[str, object]:
    arguments = dict(DEFAULT_ARGUMENTS)
    replacements = {
        "clauses_to_sample": args.samples,
        "iterations_genetic": args.genetic_iterations,
        "iterations": args.outer_iterations,
        "population_size": args.population,
    }
    for name, value in replacements.items():
        if value is not None:
            arguments[name] = value
    return arguments


def build_command(
    python: str, config: DatasetConfig, base_arguments: dict[str, object]
) -> tuple[list[str], str]:
    arguments = {
        **base_arguments,
        **config.arguments,
        "filename": str(
            (REPO_ROOT / "benchmarks" / "gentians" / f"{config.task}.txt").resolve()
        ),
    }
    arguments_json = json.dumps(arguments, sort_keys=True)
    return [python, str(PROFILE_BASELINE_PATH)], arguments_json


def run_profile_worker() -> None:
    payload = os.environ["GENTIANS_ARGUMENTS_JSON"]
    gentians_main(Arguments(**json.loads(payload)))


def run_streamed(
    cmd: list[str],
    arguments_json: str,
    log_path: Path,
    timeout_seconds: int,
    timings_path: Path,
    ga_metrics_path: Path,
    out_dir: Path,
    dataset: str,
    run: int,
    completed_ga_metrics: list[GAMetric],
    live_plots: bool,
    live_plot_seconds: float,
) -> tuple[int | None, bool]:
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENTIANS_PROFILE_WORKER"] = "1"
    env["GENTIANS_ARGUMENTS_JSON"] = arguments_json
    env["GENTIANS_TIMINGS_PATH"] = str(timings_path.resolve())
    env["GENTIANS_GA_METRICS_PATH"] = str(ga_metrics_path.resolve())
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
        deadline = time.monotonic() + timeout_seconds
        next_live_plot = time.monotonic() + max(live_plot_seconds, 0.1)
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
            now = time.monotonic()
            if live_plots and now >= next_live_plot:
                refresh_live_ga_plot(
                    out_dir,
                    dataset,
                    completed_ga_metrics,
                    ga_metrics_path,
                    run,
                )
                next_live_plot = now + max(live_plot_seconds, 0.1)
            if process.poll() is not None and done:
                if live_plots:
                    refresh_live_ga_plot(
                        out_dir,
                        dataset,
                        completed_ga_metrics,
                        ga_metrics_path,
                        run,
                    )
                return process.wait(), False
            if time.monotonic() > deadline:
                kill_tree(process)
                thread.join(timeout=2)
                if live_plots:
                    refresh_live_ga_plot(
                        out_dir,
                        dataset,
                        completed_ga_metrics,
                        ga_metrics_path,
                        run,
                    )
                return process.wait(), True


def refresh_live_ga_plot(
    out_dir: Path,
    dataset: str,
    completed_ga_metrics: list[GAMetric],
    current_ga_metrics_path: Path,
    current_run: int,
) -> None:
    current = read_ga_metrics(current_ga_metrics_path, dataset, current_run)
    if not current:
        return
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    dataset_dir = out_dir / "images" / "by_example" / dataset
    dataset_dir.mkdir(parents=True, exist_ok=True)
    points = [
        point for point in completed_ga_metrics if point.dataset == dataset
    ] + current
    write_dataset_ga_fitness_plot(plt, dataset_dir, dataset, points)


def kill_tree(process: subprocess.Popen[str]) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        process.kill()


def parse_log(path: Path, dataset: str, run: int) -> dict[str, object]:
    points: list[FitnessPoint] = []
    best_so_far = float("-inf")
    last_generation: int | None = None
    total_seconds: float | None = None
    success = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = ITERATION_RE.search(line)
        if match:
            generation = int(match.group(1))
            score = float(match.group(2))
            best_so_far = max(best_so_far, score)
            last_generation = generation
            points.append(FitnessPoint(dataset, run, generation, score, best_so_far))
        if "--- Found best program ---" in line:
            success = True
        total_match = TOTAL_RE.search(line)
        if total_match:
            total_seconds = float(total_match.group(1))
    return {
        "fitness": points,
        "total_seconds": total_seconds,
        "success": success,
        "first_success_generation_observed": (
            last_generation if last_generation is not None else 0
        )
        if success
        else None,
    }


def read_phase_times(path: Path, dataset: str, run: int) -> list[PhaseTime]:
    stats = pstats.Stats(str(path))
    by_phase = {phase: [0.0, 0.0, 0] for phase in PHASE_FUNCTIONS}
    for (_filename, _line, func_name), (
        cc,
        _nc,
        tt,
        ct,
        _callers,
    ) in stats.stats.items():
        for phase, names in PHASE_FUNCTIONS.items():
            if func_name in names:
                row = by_phase[phase]
                row[0] += ct * 1000
                row[1] += tt * 1000
                row[2] += cc
    return [
        PhaseTime(dataset, run, phase, values[0], values[1], int(values[2]))
        for phase, values in by_phase.items()
    ]


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
        )
        for row in rows
    ]


def read_json_rows(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (PermissionError, json.JSONDecodeError):
        return []


def read_existing_outputs(
    out_dir: Path,
) -> tuple[
    list[RunResult],
    list[FitnessPoint],
    list[PhaseTime],
    list[TimingMetric],
    list[GAMetric],
]:
    timings = [
        TimingMetric(
            row["dataset"],
            int(row["run"]),
            row["metric"],
            float(row["seconds"]),
            int(row["calls"]),
        )
        for row in read_csv_dicts(out_dir / "timings_raw.csv")
    ]
    ga_metrics = [
        GAMetric(
            row["dataset"],
            int(row["run"]),
            int(row["generation"]),
            float(row["max_fitness"]),
            float(row["avg_fitness"]),
            float(row["best_so_far"]),
        )
        for row in read_csv_dicts(out_dir / "ga_fitness.csv")
    ]
    fitness = [
        FitnessPoint(
            row["dataset"],
            int(row["run"]),
            int(row["generation"]),
            float(row["best_current"]),
            float(row["best_so_far"]),
        )
        for row in read_csv_dicts(out_dir / "fitness_observed.csv")
    ]
    datasets = sorted(
        {row["dataset"] for row in read_csv_dicts(out_dir / "runs.csv")}
        | {t.dataset for t in timings}
        | {g.dataset for g in ga_metrics}
    )
    results = [
        RunResult(dataset, 0, "plots-only", 0, 0.0, [], "", "", None, False, None)
        for dataset in datasets
    ]
    return results, fitness, [], timings, ga_metrics


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_outputs(
    out_dir: Path,
    results: list[RunResult],
    fitness: list[FitnessPoint],
    phases: list[PhaseTime],
    timings: list[TimingMetric],
    ga_metrics: list[GAMetric],
    include_plots: bool,
) -> None:
    (out_dir / "raw_results.json").write_text(
        json.dumps([asdict(r) for r in results], indent=2), encoding="utf-8"
    )
    write_csv(out_dir / "runs.csv", [asdict(r) for r in results])
    write_csv(out_dir / "fitness_observed.csv", [asdict(p) for p in fitness])
    write_csv(out_dir / "timings_raw.csv", [asdict(t) for t in timings])
    write_csv(out_dir / "timings_mean.csv", timing_means(timings))
    write_csv(out_dir / "ga_fitness.csv", [asdict(p) for p in ga_metrics])
    write_csv(out_dir / "ga_fitness_mean.csv", ga_fitness_means(ga_metrics))
    if include_plots:
        write_plots(out_dir, fitness, phases, timings, ga_metrics, results)


def ga_fitness_means(points: list[GAMetric]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for dataset in sorted({p.dataset for p in points}):
        dataset_points = [p for p in points if p.dataset == dataset]
        for generation in sorted({p.generation for p in dataset_points}):
            generation_points = [
                p for p in dataset_points if p.generation == generation
            ]
            rows.append(
                {
                    "dataset": dataset,
                    "generation": generation,
                    "max_mean": mean(p.max_fitness for p in generation_points),
                    "max_std": stddev(p.max_fitness for p in generation_points),
                    "avg_mean": mean(p.avg_fitness for p in generation_points),
                    "avg_std": stddev(p.avg_fitness for p in generation_points),
                    "best_so_far_mean": mean(p.best_so_far for p in generation_points),
                    "best_so_far_std": stddev(p.best_so_far for p in generation_points),
                    "runs": len(generation_points),
                }
            )
    return rows


def timing_means(timings: list[TimingMetric]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for dataset in sorted({t.dataset for t in timings}):
        dataset_timings = [t for t in timings if t.dataset == dataset]
        runs = sorted({t.run for t in dataset_timings})
        extra_metrics = sorted(
            {
                t.metric
                for t in dataset_timings
                if t.metric
                not in {
                    "total_execution",
                    "clingo.grounding.total_all",
                    "clingo.solving.total_all",
                }
            }
        )
        metrics = list(dict.fromkeys(STANDARD_TIMING_METRICS + extra_metrics))
        for metric in metrics:
            values = [
                sum(
                    t.seconds
                    for t in dataset_timings
                    if t.run == run and t.metric == metric
                )
                for run in runs
            ]
            calls = [
                sum(
                    t.calls
                    for t in dataset_timings
                    if t.run == run and t.metric == metric
                )
                for run in runs
            ]
            rows.append(
                {
                    "dataset": dataset,
                    "metric": metric,
                    "mean_seconds": mean(values),
                    "mean_calls": mean(calls),
                    "runs": len(values),
                }
            )
        for suffix in ("grounding", "solving"):
            per_run = []
            for run in runs:
                per_run.append(
                    sum(
                        t.seconds
                        for t in dataset_timings
                        if t.run == run and t.metric.endswith(f".{suffix}")
                    )
                )
            rows.append(
                {
                    "dataset": dataset,
                    "metric": f"clingo.{suffix}.total_all",
                    "mean_seconds": mean(per_run),
                    "mean_calls": "",
                    "runs": len(per_run),
                }
            )
        values = [
            sum(
                t.seconds
                for t in dataset_timings
                if t.run == run and t.metric == "total_execution"
            )
            for run in runs
        ]
        calls = [
            sum(
                t.calls
                for t in dataset_timings
                if t.run == run and t.metric == "total_execution"
            )
            for run in runs
        ]
        rows.append(
            {
                "dataset": dataset,
                "metric": "total_execution",
                "mean_seconds": mean(values),
                "mean_calls": mean(calls),
                "runs": len(values),
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_plots(
    out_dir: Path,
    fitness: list[FitnessPoint],
    phases: list[PhaseTime],
    timings: list[TimingMetric],
    ga_metrics: list[GAMetric],
    results: list[RunResult],
) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:
        (out_dir / "PLOTS_SKIPPED.txt").write_text(
            f"matplotlib unavailable: {exc}\n", encoding="utf-8"
        )
        return
    skipped = out_dir / "PLOTS_SKIPPED.txt"
    if skipped.exists():
        skipped.unlink()
    images = out_dir / "images"
    by_example = images / "by_example"
    global_dir = images / "global"
    by_example.mkdir(parents=True, exist_ok=True)
    global_dir.mkdir(parents=True, exist_ok=True)
    for dataset in sorted({r.dataset for r in results}):
        dataset_dir = by_example / dataset
        dataset_dir.mkdir(exist_ok=True)
        write_dataset_ga_fitness_plot(
            plt, dataset_dir, dataset, [p for p in ga_metrics if p.dataset == dataset]
        )
        write_dataset_timing_plot(
            plt, dataset_dir, dataset, [t for t in timings if t.dataset == dataset]
        )
        write_dataset_timing_breakdown_plot(
            plt, dataset_dir, dataset, [t for t in timings if t.dataset == dataset]
        )
        write_dataset_timing_aggregates_plot(
            plt, dataset_dir, dataset, [t for t in timings if t.dataset == dataset]
        )


def write_dataset_fitness_plot(
    plt, out_dir: Path, dataset: str, points: list[FitnessPoint]
) -> None:
    if not points:
        return
    by_run: dict[int, list[FitnessPoint]] = {}
    for point in points:
        by_run.setdefault(point.run, []).append(point)
    fig, ax = plt.subplots(figsize=(9, 5), layout="constrained")
    for run, run_points in sorted(by_run.items()):
        ordered = sorted(run_points, key=lambda p: p.generation)
        ax.plot(
            [p.generation for p in ordered],
            [p.best_so_far for p in ordered],
            label=f"run {run}",
            alpha=0.75,
        )
    ax.set_title(f"{dataset}: best_so_far observado en stdout")
    ax.set_xlabel("generacion reportada por baseline")
    ax.set_ylabel("fitness")
    ax.legend(ncol=2, fontsize="small")
    fig.savefig(out_dir / f"{dataset}_best_so_far_observado.png", dpi=160)
    plt.close(fig)


def write_dataset_ga_fitness_plot(
    plt, out_dir: Path, dataset: str, points: list[GAMetric]
) -> None:
    if not points:
        return
    rows = ga_fitness_means(points)
    generations = [int(row["generation"]) for row in rows if row["dataset"] == dataset]
    max_mean = [float(row["max_mean"]) for row in rows if row["dataset"] == dataset]
    max_std = [float(row["max_std"]) for row in rows if row["dataset"] == dataset]
    avg_mean = [float(row["avg_mean"]) for row in rows if row["dataset"] == dataset]
    avg_std = [float(row["avg_std"]) for row in rows if row["dataset"] == dataset]
    best_mean = [
        float(row["best_so_far_mean"]) for row in rows if row["dataset"] == dataset
    ]
    best_std = [
        float(row["best_so_far_std"]) for row in rows if row["dataset"] == dataset
    ]

    fig, ax = plt.subplots(figsize=(10, 5), layout="constrained")
    by_run: dict[int, list[GAMetric]] = {}
    for point in points:
        by_run.setdefault(point.run, []).append(point)
    for run_points in by_run.values():
        ordered = sorted(run_points, key=lambda p: p.generation)
        ax.plot(
            [p.generation for p in ordered],
            [p.max_fitness for p in ordered],
            color="#4e79a7",
            alpha=0.14,
            linewidth=0.8,
        )
        ax.plot(
            [p.generation for p in ordered],
            [p.avg_fitness for p in ordered],
            color="#f28e2b",
            alpha=0.14,
            linewidth=0.8,
        )
    ax.plot(
        generations,
        max_mean,
        color="#4e79a7",
        linewidth=2,
        label="max fitness mean +/- std",
    )
    ax.fill_between(
        generations,
        [m - s for m, s in zip(max_mean, max_std)],
        [m + s for m, s in zip(max_mean, max_std)],
        color="#4e79a7",
        alpha=0.18,
    )
    ax.plot(
        generations,
        avg_mean,
        color="#f28e2b",
        linewidth=2,
        label="avg fitness mean +/- std",
    )
    ax.fill_between(
        generations,
        [m - s for m, s in zip(avg_mean, avg_std)],
        [m + s for m, s in zip(avg_mean, avg_std)],
        color="#f28e2b",
        alpha=0.18,
    )
    ax.plot(
        generations,
        best_mean,
        color="#59a14f",
        linestyle="--",
        linewidth=2,
        label="best-so-far mean +/- std",
    )
    ax.fill_between(
        generations,
        [m - s for m, s in zip(best_mean, best_std)],
        [m + s for m, s in zip(best_mean, best_std)],
        color="#59a14f",
        alpha=0.12,
    )
    ax.set_title(f"{dataset}: evolucion fitness GA")
    ax.set_xlabel("iteracion")
    ax.set_ylabel("fitness")
    ax.legend()
    fig.savefig(out_dir / f"{dataset}_ga_fitness.png", dpi=160)
    plt.close(fig)


def write_dataset_phase_plot(
    plt, out_dir: Path, dataset: str, phases: list[PhaseTime]
) -> None:
    if not phases:
        return
    labels = sorted({p.phase for p in phases})
    inclusive = [
        mean(p.inclusive_ms for p in phases if p.phase == label) for label in labels
    ]
    exclusive = [
        mean(p.exclusive_ms for p in phases if p.phase == label) for label in labels
    ]
    fig, ax = plt.subplots(figsize=(9, 5), layout="constrained")
    y = list(range(len(labels)))
    ax.barh([v - 0.18 for v in y], inclusive, height=0.35, label="inclusive/cum ms")
    ax.barh([v + 0.18 for v in y], exclusive, height=0.35, label="exclusive/tottime ms")
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("ms por run (media)")
    ax.set_title(f"{dataset}: tiempos cProfile por funcion")
    ax.legend()
    fig.savefig(out_dir / f"{dataset}_tiempos_cprofile_ms.png", dpi=160)
    plt.close(fig)


def write_global_phase_plot(plt, out_dir: Path, phases: list[PhaseTime]) -> None:
    if not phases:
        return
    labels = sorted({p.phase for p in phases})
    inclusive = [
        mean(p.inclusive_ms for p in phases if p.phase == label) for label in labels
    ]
    fig, ax = plt.subplots(figsize=(9, 5), layout="constrained")
    ax.barh(labels, inclusive)
    ax.invert_yaxis()
    ax.set_xlabel("ms por run (media inclusive)")
    ax.set_title("Global: tiempos cProfile por funcion")
    fig.savefig(out_dir / "tiempos_cprofile_ms.png", dpi=160)
    plt.close(fig)


def write_dataset_timing_plot(
    plt, out_dir: Path, dataset: str, timings: list[TimingMetric]
) -> None:
    if not timings:
        return
    means = {
        row["metric"]: row["mean_seconds"]
        for row in timing_means(timings)
        if row["dataset"] == dataset
    }
    labels = TIMING_PLOT_ORDER
    values = [float(means[metric]) for metric in labels]
    colors = [timing_color(metric) for metric in labels]
    display_labels = [timing_label(metric) for metric in labels]
    fig, ax = plt.subplots(
        figsize=(11, max(5, len(labels) * 0.35)), layout="constrained"
    )
    ax.barh(display_labels, values, color=colors)
    ax.invert_yaxis()
    ax.set_xlabel("segundos por run (media)")
    ax.set_title(f"{dataset}: debug raw inclusive timers (no sumar barras)")
    handles = [
        plt.Line2D([0], [0], color="#4e79a7", lw=6, label="python/self"),
        plt.Line2D([0], [0], color="#8e63b0", lw=6, label="grounding"),
        plt.Line2D([0], [0], color="#9c5f53", lw=6, label="solving"),
        plt.Line2D([0], [0], color="#8f8f8f", lw=6, label="inclusive/aggregate"),
        plt.Line2D([0], [0], color="#4c4c4c", lw=6, label="total ejecucion"),
    ]
    ax.legend(handles=handles, loc="lower right")
    fig.savefig(out_dir / f"{dataset}_timings_mean.png", dpi=160)
    plt.close(fig)


def write_dataset_timing_breakdown_plot(
    plt, out_dir: Path, dataset: str, timings: list[TimingMetric]
) -> None:
    if not timings:
        return
    means = {
        row["metric"]: float(row["mean_seconds"])
        for row in timing_means(timings)
        if row["dataset"] == dataset
    }
    rows = []
    for phase_name in TOP_LEVEL_TIMING_PHASES:
        total = means.get(phase_name, 0.0)
        grounding = means.get(f"{phase_name}.grounding", 0.0)
        solving = means.get(f"{phase_name}.solving", 0.0)
        self_time = max(total - grounding - solving, 0.0)
        rows.append((phase_name, self_time, grounding, solving))
    covered = sum(
        self_time + grounding + solving for _, self_time, grounding, solving in rows
    )
    total_execution = means.get("total_execution", 0.0)
    unattributed = max(total_execution - covered, 0.0)
    if unattributed:
        rows.append(("other/unattributed", unattributed, 0.0, 0.0))

    labels = [timing_label(row[0]) for row in rows]
    y = list(range(len(labels)))
    self_values = [row[1] for row in rows]
    grounding_values = [row[2] for row in rows]
    solving_values = [row[3] for row in rows]

    fig, ax = plt.subplots(
        figsize=(11, max(5, len(labels) * 0.45)), layout="constrained"
    )
    totals = [
        self_time + grounding + solving for _, self_time, grounding, solving in rows
    ]
    self_bars = ax.barh(y, self_values, color="#4e79a7", label="python/self")
    left = self_values
    grounding_bars = ax.barh(
        y, grounding_values, left=left, color="#9467bd", label="grounding"
    )
    left = [a + b for a, b in zip(left, grounding_values)]
    solving_bars = ax.barh(
        y, solving_values, left=left, color="#8c564b", label="solving"
    )
    add_percent_labels(ax, self_bars, self_values, [0.0] * len(y), totals)
    add_percent_labels(ax, grounding_bars, grounding_values, self_values, totals)
    add_percent_labels(
        ax,
        solving_bars,
        solving_values,
        [a + b for a, b in zip(self_values, grounding_values)],
        totals,
    )
    add_total_share_labels(ax, totals, total_execution)
    if total_execution:
        ax.axvline(
            total_execution, color="#2f2f2f", linewidth=1.5, label="total_execution"
        )
        ax.set_xlim(0, total_execution * 1.22)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("segundos por run (media)")
    ax.set_title(
        f"{dataset}: desglose sin doble conteo (% interno; etiqueta final = % total)"
    )
    ax.legend(loc="lower right")
    fig.savefig(out_dir / f"{dataset}_timings_breakdown.png", dpi=160)
    plt.close(fig)


def add_percent_labels(
    ax, bars, widths: list[float], lefts: list[float], totals: list[float]
) -> None:
    for bar, width, left, total in zip(bars, widths, lefts, totals):
        if width <= 0 or total <= 0:
            continue
        percent = width / total * 100
        # if percent < 15:
        #    continue
        ax.text(
            left + width / 2,
            bar.get_y() + bar.get_height() / 2,
            f"{percent:.0f}%",
            ha="center",
            va="center",
            color="white",
            fontsize=8,
        )


def add_total_share_labels(ax, totals: list[float], total_execution: float) -> None:
    if total_execution <= 0:
        return
    pad = total_execution * 0.01
    for index, total in enumerate(totals):
        if total <= 0:
            continue
        percent = total / total_execution * 100
        # if percent < 2:
        #   continue
        ax.text(
            total + pad,
            index,
            f"{total:.2f}s · {percent:.0f}% total",
            va="center",
            fontsize=8,
            color="#333333",
        )


def write_dataset_timing_aggregates_plot(
    plt, out_dir: Path, dataset: str, timings: list[TimingMetric]
) -> None:
    if not timings:
        return
    means = {
        row["metric"]: float(row["mean_seconds"])
        for row in timing_means(timings)
        if row["dataset"] == dataset
    }
    grounding = means.get("clingo.grounding.total_all", 0.0)
    solving = means.get("clingo.solving.total_all", 0.0)
    total_execution = means.get("total_execution", 0.0)
    values = {
        "grounding": grounding,
        "solving": solving,
        "python/self + other": max(total_execution - grounding - solving, 0.0),
    }
    labels = list(values)
    colors = [
        "#9467bd",
        "#8c564b",
        "#4e79a7",
    ]
    fig, ax = plt.subplots(figsize=(10, 3.2), layout="constrained")
    left = 0.0
    for label, color in zip(labels, colors):
        value = values[label]
        ax.barh(["total_execution"], [value], left=[left], color=color, label=label)
        if total_execution and value / total_execution >= 0.08:
            ax.text(
                left + value / 2,
                0,
                f"{value / total_execution * 100:.0f}%",
                ha="center",
                va="center",
                color="white",
                fontsize=9,
            )
        left += value
    ax.set_xlabel("segundos por run (media)")
    ax.set_title(f"{dataset}: particion de total_execution")
    if total_execution:
        ax.set_xlim(0, total_execution * 1.05)
    ax.legend(loc="lower right")
    fig.savefig(out_dir / f"{dataset}_timing_aggregates.png", dpi=160)
    plt.close(fig)


def timing_color(metric: str) -> str:
    if metric == "total_execution":
        return "#4c4c4c"
    if metric.endswith(".grounding") or ".grounding." in metric:
        return "#9467bd"
    if metric.endswith(".solving") or ".solving." in metric:
        return "#8c564b"
    if metric in {"mutation", "crossover", "fitness.initialization", "fitness.final"}:
        return "#8f8f8f"
    return "#4e79a7"


def timing_label(metric: str) -> str:
    return metric.replace("fitness.initialization", "poblacion inicializacion")


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def stddev(values: Iterable[float]) -> float:
    values = list(values)
    if len(values) < 2:
        return 0.0
    avg = mean(values)
    return (sum((value - avg) ** 2 for value in values) / (len(values) - 1)) ** 0.5


if __name__ == "__main__":
    if os.environ.get("GENTIANS_PROFILE_WORKER") == "1":
        run_profile_worker()
    else:
        main()
