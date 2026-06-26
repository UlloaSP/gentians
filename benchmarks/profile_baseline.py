import argparse
import copy
import csv
import json
import os
import queue
import random
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
    seed: int
    experiment_id: str
    status: str
    returncode: int | None
    elapsed_seconds: float
    command: list[str]
    arguments_json: str
    log_path: str
    cprofile_path: str
    total_seconds: float | None = None
    success: bool = False
    first_success_generation_observed: int | None = None
    fitness_operator: str = "coverage_exp_mean"
    outer_iterations: int = 0
    genetic_iterations: int = 0


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
    outer_iteration: int
    generation: int
    global_generation: int
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
    "fitness": {
        "name": "coverage_exp_mean",
        "max_as": 10000,
        "clingo_arguments": ["--project"],
        "empty_score": -2000,
    },
    "selection": {
        "name": "tournament",
        "tournament_size": 12,
        "prob_selecting_fittest": 0.9,
    },
    "crossover": {"name": "one_point", "probability": 1.0},
    "mutation": {"name": "random_stub", "probability": 0.05, "change_stub": True},
    "population": {"name": "random", "size": 36},
    "replacement": {
        "name": "oldest_or_worst",
        "prob_replacing_oldest": 0.5,
        "k_best_for_next_round": 5,
    },
    "variable_placement": {
        "clingo_arguments": ["0"],
        "single_variable_until_positions": 2,
    },
    "sampling": {
        "negation_probability": 0.5,
        "enable_recursion": False,
    },
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
    "crossover.operator",
    "crossover.fitness",
    "mutation.grounding",
    "mutation.solving",
    "mutation.operator",
    "mutation.fitness",
    "crossover.grounding",
    "crossover.solving",
    "fitness.initialization.grounding",
    "fitness.initialization.solving",
    "fitness.final.grounding",
    "fitness.final.solving",
    "mutation",
    "crossover",
    "genetic",
    "fitness.initialization",
    "fitness.final",
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
    parser.add_argument("--fitness-json")
    parser.add_argument("--selection-json")
    parser.add_argument("--crossover-json")
    parser.add_argument("--mutation-json")
    parser.add_argument("--population-json")
    parser.add_argument("--replacement-json")
    parser.add_argument("--variable-placement-json")
    parser.add_argument("--sampling-json")
    parser.add_argument("--population", type=int)
    parser.add_argument("--seed-base", type=int, default=1)
    parser.add_argument("--no-plots", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--plots-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--live-plot-seconds",
        type=float,
        default=2.0,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "runs").mkdir(exist_ok=True)

    if args.plots_only:
        (
            results,
            fitness,
            phases,
            timings,
            ga_metrics,
            timing_events,
            operator_metrics,
            candidate_metrics,
            quality_metrics,
            clingo_metrics,
            invariants,
        ) = read_existing_outputs(out_dir)
        _ = (fitness, phases, timing_events, invariants)
        write_dashboard_data(
            out_dir,
            results,
            timings,
            ga_metrics,
            timing_events,
            operator_metrics,
            candidate_metrics,
            quality_metrics,
            clingo_metrics,
        )
        return

    results: list[RunResult] = []
    fitness: list[FitnessPoint] = []
    phases: list[PhaseTime] = []
    timings: list[TimingMetric] = []
    ga_metrics: list[GAMetric] = []
    timing_events: list[dict[str, object]] = []
    operator_metrics: list[dict[str, object]] = []
    candidate_metrics: list[dict[str, object]] = []
    quality_metrics: list[dict[str, object]] = []
    clingo_metrics: list[dict[str, object]] = []
    invariants: list[dict[str, object]] = []

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
            timing_events_path = (
                out_dir / "runs" / f"{dataset}_run_{run}_timing_events.jsonl"
            )
            ga_metrics_path = out_dir / "runs" / f"{dataset}_run_{run}_ga_metrics.json"
            operator_metrics_path = (
                out_dir / "runs" / f"{dataset}_run_{run}_operator_metrics.jsonl"
            )
            candidate_metrics_path = (
                out_dir / "runs" / f"{dataset}_run_{run}_candidate_metrics.jsonl"
            )
            quality_metrics_path = (
                out_dir / "runs" / f"{dataset}_run_{run}_quality_metrics.jsonl"
            )
            clingo_metrics_path = (
                out_dir / "runs" / f"{dataset}_run_{run}_clingo_metrics.jsonl"
            )
            log_path = out_dir / "runs" / f"{dataset}_run_{run}.log"
            cmd, arguments_json = build_command(args.python, config, override_arguments(args))
            seed = args.seed_base + completed - 1
            experiment_id = f"{dataset}_seed_{seed}"
            with commands_path.open("a", encoding="utf-8") as f:
                f.write(f"GENTIANS_ARGUMENTS_JSON={arguments_json} ")
                f.write(f"GENTIANS_RANDOM_SEED={seed} ")
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
                timing_events_path,
                ga_metrics_path,
                operator_metrics_path,
                candidate_metrics_path,
                quality_metrics_path,
                clingo_metrics_path,
                out_dir,
                dataset,
                run,
                seed,
                ga_metrics,
                timings,
            )
            elapsed = time.perf_counter() - started
            status = "timeout" if timed_out else "ok" if returncode == 0 else "failed"
            parsed = parse_log(log_path, dataset, run)
            run_arguments = json.loads(arguments_json)
            fitness_config = run_arguments.get("fitness", {})
            if not isinstance(fitness_config, dict):
                fitness_config = {}
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
                cprofile_path=str(cprofile_path),
                total_seconds=parsed["total_seconds"],
                success=parsed["success"],
                first_success_generation_observed=parsed[
                    "first_success_generation_observed"
                ],
                fitness_operator=str(fitness_config.get("name", "coverage_exp_mean")),
                outer_iterations=int(run_arguments.get("iterations", 0)),
                genetic_iterations=int(run_arguments.get("iterations_genetic", 0)),
            )
            results.append(run_result)
            fitness.extend(parsed["fitness"])
            ga_metrics.extend(read_ga_metrics(ga_metrics_path, dataset, run))
            run_timings = read_timings(timings_path, dataset, run)
            timings.extend(run_timings)
            timing_events.extend(
                read_jsonl_rows(timing_events_path, dataset, run, seed, experiment_id)
            )
            operator_metrics.extend(
                read_jsonl_rows(operator_metrics_path, dataset, run, seed, experiment_id)
            )
            candidate_metrics.extend(
                read_jsonl_rows(candidate_metrics_path, dataset, run, seed, experiment_id)
            )
            quality_metrics.extend(
                read_jsonl_rows(quality_metrics_path, dataset, run, seed, experiment_id)
            )
            clingo_metrics.extend(
                read_jsonl_rows(clingo_metrics_path, dataset, run, seed, experiment_id)
            )
            invariants.extend(compute_accounting_invariants(dataset, run, run_timings))
            write_outputs(
                out_dir,
                results,
                fitness,
                phases,
                timings,
                ga_metrics,
                timing_events,
                operator_metrics,
                candidate_metrics,
                quality_metrics,
                clingo_metrics,
                invariants,
            )
            print(
                f"[{completed}/{total}] {dataset} run {run} {status} {elapsed:.2f}s",
                flush=True,
            )


def _default_python() -> str:
    local = Path(".venv") / "Scripts" / "python.exe"
    return str(local.resolve()) if local.exists() else sys.executable


def override_arguments(args: argparse.Namespace) -> dict[str, object]:
    arguments = copy.deepcopy(DEFAULT_ARGUMENTS)
    replacements = {
        "clauses_to_sample": args.samples,
        "iterations_genetic": args.genetic_iterations,
        "iterations": args.outer_iterations,
    }
    for name, value in replacements.items():
        if value is not None:
            arguments[name] = value
    if args.population is not None:
        population_config = arguments.get("population", {})
        if not isinstance(population_config, dict):
            population_config = {}
        arguments["population"] = population_config | {"size": args.population}
    for name in [
        "fitness",
        "selection",
        "crossover",
        "mutation",
        "population",
        "replacement",
        "variable_placement",
        "sampling",
    ]:
        raw = getattr(args, f"{name}_json")
        if raw is not None:
            base = arguments.get(name, {})
            if not isinstance(base, dict):
                base = {}
            arguments[name] = base | parse_json_config(raw, name)
    return arguments


def parse_json_config(raw: str, name: str) -> dict[str, object]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid --{name}-json: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"--{name}-json must be a JSON object")
    return value


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
    seed = os.environ.get("GENTIANS_RANDOM_SEED")
    if seed is not None:
        random.seed(int(seed))
    gentians_main(Arguments(**json.loads(payload)))


def run_streamed(
    cmd: list[str],
    arguments_json: str,
    log_path: Path,
    timeout_seconds: int,
    timings_path: Path,
    timing_events_path: Path,
    ga_metrics_path: Path,
    operator_metrics_path: Path,
    candidate_metrics_path: Path,
    quality_metrics_path: Path,
    clingo_metrics_path: Path,
    out_dir: Path,
    dataset: str,
    run: int,
    seed: int,
    completed_ga_metrics: list[GAMetric],
    completed_timings: list[TimingMetric],
) -> tuple[int | None, bool]:
    _ = (out_dir, dataset, run, completed_ga_metrics, completed_timings)
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["GENTIANS_PROFILE_WORKER"] = "1"
    env["GENTIANS_ARGUMENTS_JSON"] = arguments_json
    env["GENTIANS_RANDOM_SEED"] = str(seed)
    env["GENTIANS_TIMINGS_PATH"] = str(timings_path.resolve())
    env["GENTIANS_TIMING_EVENTS_PATH"] = str(timing_events_path.resolve())
    env["GENTIANS_GA_METRICS_PATH"] = str(ga_metrics_path.resolve())
    env["GENTIANS_OPERATOR_METRICS_PATH"] = str(operator_metrics_path.resolve())
    env["GENTIANS_CANDIDATE_METRICS_PATH"] = str(candidate_metrics_path.resolve())
    env["GENTIANS_QUALITY_METRICS_PATH"] = str(quality_metrics_path.resolve())
    env["GENTIANS_CLINGO_METRICS_PATH"] = str(clingo_metrics_path.resolve())
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
            if time.monotonic() > deadline:
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
            int(row.get("outer_iteration", 0)),
            int(row["generation"]),
            int(row.get("global_generation", row["generation"])),
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


def read_jsonl_rows(
    path: Path, dataset: str, run: int, seed: int, experiment_id: str
) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
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


def compute_accounting_invariants(
    dataset: str, run: int, timings: list[TimingMetric]
) -> list[dict[str, object]]:
    values = {t.metric: t.seconds for t in timings}
    total = values.get("total_execution", 0.0)
    top_level = [
        "sampling",
        "sampling.instantiation",
        "variable_placement",
        "genetic",
    ]
    attributed = sum(values.get(metric, 0.0) for metric in top_level)
    clingo_grounding = sum(
        value for metric, value in values.items() if metric.endswith(".grounding")
    )
    clingo_solving = sum(
        value for metric, value in values.items() if metric.endswith(".solving")
    )
    rows = [
        {
            "dataset": dataset,
            "run": run,
            "invariant": "total_vs_top_level",
            "left_seconds": total,
            "right_seconds": attributed,
            "delta_seconds": total - attributed,
            "delta_percent": (total - attributed) / total * 100 if total else 0.0,
            "status": "ok" if not total or abs(total - attributed) / total < 0.15 else "check",
        },
        {
            "dataset": dataset,
            "run": run,
            "invariant": "clingo_grounding_vs_solving",
            "left_seconds": clingo_grounding,
            "right_seconds": clingo_solving,
            "delta_seconds": clingo_solving - clingo_grounding,
            "delta_percent": (clingo_solving - clingo_grounding)
            / (clingo_grounding + clingo_solving)
            * 100
            if clingo_grounding + clingo_solving
            else 0.0,
            "status": "info",
        },
    ]
    for phase in [
        "variable_placement",
        "fitness.initialization",
        "crossover",
        "mutation",
        "fitness.final",
    ]:
        phase_total = values.get(phase, 0.0)
        clingo_total = sum_nested_metric(values, phase, "grounding") + sum_nested_metric(
            values, phase, "solving"
        )
        rows.append(
            {
                "dataset": dataset,
                "run": run,
                "invariant": f"{phase}_contains_clingo",
                "left_seconds": phase_total,
                "right_seconds": clingo_total,
                "delta_seconds": phase_total - clingo_total,
                "delta_percent": (phase_total - clingo_total) / phase_total * 100
                if phase_total
                else 0.0,
                "status": "ok" if clingo_total <= phase_total + 0.001 else "check",
            }
        )
    return rows


def read_existing_outputs(
    out_dir: Path,
) -> tuple[
    list[RunResult],
    list[FitnessPoint],
    list[PhaseTime],
    list[TimingMetric],
    list[GAMetric],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
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
            int(to_float(row.get("outer_iteration"))),
            int(row["generation"]),
            int(to_float(row.get("global_generation") or row.get("generation"))),
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
    results = [
        RunResult(
            row.get("dataset", ""),
            int(to_float(row.get("run"))),
            int(to_float(row.get("seed"))),
            row.get("experiment_id", ""),
            row.get("status", ""),
            int(to_float(row.get("returncode"))) if row.get("returncode") not in (None, "") else None,
            to_float(row.get("elapsed_seconds")),
            [],
            row.get("arguments_json", ""),
            row.get("log_path", ""),
            row.get("cprofile_path", ""),
            to_float(row.get("total_seconds")) if row.get("total_seconds") not in (None, "") else None,
            bool(to_float(row.get("success"))),
            int(to_float(row.get("first_success_generation_observed")))
            if row.get("first_success_generation_observed") not in (None, "")
            else None,
            row.get("fitness_operator", "coverage_exp_mean"),
            int(to_float(row.get("outer_iterations"))),
            int(to_float(row.get("genetic_iterations"))),
        )
        for row in read_csv_dicts(out_dir / "runs.csv")
    ]
    return (
        results,
        fitness,
        [],
        timings,
        ga_metrics,
        read_csv_object_rows(out_dir / "timing_events.csv"),
        read_csv_object_rows(out_dir / "operator_metrics.csv"),
        read_csv_object_rows(out_dir / "candidate_metrics.csv"),
        read_csv_object_rows(out_dir / "quality_metrics.csv"),
        read_csv_object_rows(out_dir / "clingo_metrics.csv"),
        read_csv_object_rows(out_dir / "accounting_invariants.csv"),
    )


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def read_csv_object_rows(path: Path) -> list[dict[str, object]]:
    return [dict(row) for row in read_csv_dicts(path)]


def write_outputs(
    out_dir: Path,
    results: list[RunResult],
    fitness: list[FitnessPoint],
    phases: list[PhaseTime],
    timings: list[TimingMetric],
    ga_metrics: list[GAMetric],
    timing_events: list[dict[str, object]],
    operator_metrics: list[dict[str, object]],
    candidate_metrics: list[dict[str, object]],
    quality_metrics: list[dict[str, object]],
    clingo_metrics: list[dict[str, object]],
    invariants: list[dict[str, object]],
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
    write_csv(out_dir / "timing_events.csv", normalize_rows(timing_events))
    write_csv(out_dir / "operator_metrics.csv", normalize_rows(operator_metrics))
    write_csv(out_dir / "operator_summary.csv", operator_summary(operator_metrics))
    write_csv(out_dir / "candidate_metrics.csv", normalize_rows(candidate_metrics))
    write_csv(out_dir / "candidate_summary.csv", candidate_summary(candidate_metrics))
    write_csv(out_dir / "quality_metrics.csv", normalize_rows(quality_metrics))
    write_csv(out_dir / "quality_summary.csv", quality_summary(quality_metrics))
    write_csv(out_dir / "clingo_metrics.csv", normalize_rows(clingo_metrics))
    write_csv(out_dir / "clingo_summary.csv", clingo_summary(clingo_metrics))
    write_csv(out_dir / "accounting_invariants.csv", normalize_rows(invariants))
    write_dashboard_data(
        out_dir,
        results,
        timings,
        ga_metrics,
        timing_events,
        operator_metrics,
        candidate_metrics,
        quality_metrics,
        clingo_metrics,
    )


def write_dashboard_data(
    out_dir: Path,
    results: list[RunResult],
    timings: list[TimingMetric],
    ga_metrics: list[GAMetric],
    timing_events: list[dict[str, object]],
    operator_metrics: list[dict[str, object]],
    candidate_metrics: list[dict[str, object]],
    quality_metrics: list[dict[str, object]],
    clingo_metrics: list[dict[str, object]],
) -> None:
    datasets = sorted({result.dataset for result in results})
    candidate_rows = candidate_summary(candidate_metrics)
    quality_rows = quality_summary(quality_metrics)
    clingo_rows = clingo_summary(clingo_metrics)
    operator_rows = operator_summary(operator_metrics)
    benchmarks = []
    for dataset in datasets:
        dataset_results = [result for result in results if result.dataset == dataset]
        dataset_timings = [timing for timing in timings if timing.dataset == dataset]
        dataset_ga = [metric for metric in ga_metrics if metric.dataset == dataset]
        dataset_quality = [row for row in quality_metrics if row.get("dataset") == dataset]
        dataset_clingo_summary = [row for row in clingo_rows if row.get("dataset") == dataset]
        first_timing_run = min(
            [int(to_float(row.get("run"))) for row in timing_events if row.get("dataset") == dataset],
            default=0,
        )
        dataset_timing_events = [
            row
            for row in timing_events
            if row.get("dataset") == dataset and int(to_float(row.get("run"))) == first_timing_run
        ]
        candidate = first_row(candidate_rows, dataset)
        quality = first_row(quality_rows, dataset)
        phases = dashboard_phases(dataset_timings)
        total = mean(
            timing.seconds
            for timing in dataset_timings
            if timing.metric == "total_execution"
        )
        solve_calls = sum(
            to_float(row.get("calls"))
            for row in clingo_rows
            if row.get("dataset") == dataset and row.get("operation") == "solving"
        )
        ground_calls = sum(
            to_float(row.get("calls"))
            for row in clingo_rows
            if row.get("dataset") == dataset and row.get("operation") == "grounding"
        )
        atoms = sum(
            to_float(row.get("stats_atoms"))
            for row in clingo_metrics
            if row.get("dataset") == dataset
        )
        ground_rules = sum(
            to_float(row.get("stats_rules"))
            for row in clingo_metrics
            if row.get("dataset") == dataset
        )
        choices = sum(
            to_float(row.get("stats_choices"))
            for row in clingo_metrics
            if row.get("dataset") == dataset
        )
        conflicts = sum(
            to_float(row.get("stats_conflicts"))
            for row in clingo_metrics
            if row.get("dataset") == dataset
        )
        models = sum(
            to_float(row.get("models"))
            for row in clingo_metrics
            if row.get("dataset") == dataset
        )
        benchmarks.append(
            {
                "name": dataset,
                "family": "real",
                "source": "benchmarks",
                "complexity": max(
                    1.0,
                    to_float(candidate.get("mean_generated_placements")) / 10
                    + to_float(candidate.get("mean_valid_placements")) / 20,
                ),
                "candidates": int(
                    sum(
                        to_float(row.get("placed_candidate_rules"))
                        for row in candidate_metrics
                        if row.get("dataset") == dataset
                        and row.get("metric") == "place_candidate_rules"
                    )
                ),
                "stubs": int(
                    sum(
                        to_float(row.get("placed_stub_groups"))
                        for row in candidate_metrics
                        if row.get("dataset") == dataset
                        and row.get("metric") == "place_candidate_rules"
                    )
                ),
                "variables": int(
                    mean(
                        to_float(row.get("variables_slots"))
                        for row in candidate_metrics
                        if row.get("dataset") == dataset
                        and row.get("metric") == "place_variables_clause"
                    )
                ),
                "predicates": 0,
                "avgArity": 0,
                "bodyLiterals": mean(
                    to_float(row.get("body_literals"))
                    for row in candidate_metrics
                    if row.get("dataset") == dataset
                    and row.get("metric") == "place_variables_clause"
                ),
                "varsPerRule": mean(
                    to_float(row.get("variables_slots"))
                    for row in candidate_metrics
                    if row.get("dataset") == dataset
                    and row.get("metric") == "place_variables_clause"
                ),
                "negation": to_float(candidate.get("negation_stub_rate")),
                "aggregates": to_float(candidate.get("aggregate_stub_rate")),
                "arithmetic": to_float(candidate.get("arithmetic_stub_rate")),
                "recursion": 0,
                "contextAtoms": 0,
                "total": total,
                "runCount": len(dataset_results),
                "successRate": mean_bool(
                    [asdict(result) for result in dataset_results], "success"
                ),
                "timeouts": sum(1 for result in dataset_results if result.status == "timeout"),
                "firstSolution": min(
                    [
                        result.first_success_generation_observed
                        for result in dataset_results
                        if result.first_success_generation_observed is not None
                    ],
                    default=0,
                ),
                "finalQuality": to_float(quality.get("best_found_rate")),
                "exactSolved": to_float(quality.get("best_found_rate")),
                "internalFitness": to_float(quality.get("best_score")),
                "fitnessOperator": dataset_results[0].fitness_operator
                if dataset_results
                else "mean",
                "outerIterations": dataset_results[0].outer_iterations
                if dataset_results
                else 0,
                "geneticIterations": dataset_results[0].genetic_iterations
                if dataset_results
                else 0,
                "solveCalls": solve_calls,
                "groundCalls": ground_calls,
                "atoms": atoms,
                "groundRules": ground_rules,
                "choices": choices,
                "conflicts": conflicts,
                "propagations": 0,
                "models": models,
                "memoryMB": 0,
                "dominant": dominant_phase(phases),
                "phases": phases,
                "fitnessRuns": dashboard_fitness_runs(dataset_ga),
                "stubRows": dashboard_stub_rows(dataset, candidate_metrics),
                "operatorSummary": [
                    row for row in operator_rows if row.get("dataset") == dataset
                ],
                "qualityRows": dashboard_quality_rows(dataset_quality),
                "timingEvents": dashboard_timing_events(dataset_timing_events),
                "clingoSummary": dataset_clingo_summary,
            }
        )
    (out_dir / "dashboard_data.json").write_text(
        json.dumps({"benchmarks": benchmarks}, indent=2), encoding="utf-8"
    )


def dashboard_phases(timings: list[TimingMetric]) -> dict[str, dict[str, float]]:
    values = {timing.metric: timing.seconds for timing in timings}

    def phase(name: str, source: str) -> dict[str, float]:
        total = values.get(source, 0.0)
        grounding = sum_nested_metric(values, source, "grounding")
        solving = sum_nested_metric(values, source, "solving")
        return {
            "self": max(total - grounding - solving, 0.0),
            "grounding": grounding,
            "solving": solving,
            "other": 0.0,
        }

    phases = {
        "sampling": phase("sampling", "sampling"),
        "variablePlacement": phase("variablePlacement", "variable_placement"),
        "initialization": phase("initialization", "fitness.initialization"),
        "selection": phase("selection", "selection"),
        "crossover": phase("crossover", "crossover"),
        "mutation": phase("mutation", "mutation"),
        "fitnessFinal": phase("fitnessFinal", "fitness.final"),
        "other": {"self": 0.0, "grounding": 0.0, "solving": 0.0, "other": 0.0},
    }
    total = values.get("total_execution", 0.0)
    measured = sum(
        sum(type_values.values()) for type_values in phases.values()
    )
    phases["other"]["other"] = max(total - measured, 0.0)
    return phases


def dominant_phase(phases: dict[str, dict[str, float]]) -> str:
    grounding = sum(row.get("grounding", 0.0) for row in phases.values())
    solving = sum(row.get("solving", 0.0) for row in phases.values())
    self_time = sum(row.get("self", 0.0) for row in phases.values())
    if grounding >= solving and grounding >= self_time:
        return "grounding"
    if solving >= self_time:
        return "solving"
    return "overhead"


def dashboard_fitness_runs(metrics: list[GAMetric]) -> list[dict[str, object]]:
    runs = []
    for run in sorted({metric.run for metric in metrics}):
        points = sorted(
            [metric for metric in metrics if metric.run == run],
            key=lambda metric: metric.global_generation,
        )
        global_best = []
        best_value = float("-inf")
        for point in points:
            best_value = max(best_value, point.best_so_far)
            global_best.append([point.global_generation, best_value])
        runs.append(
            {
                "maxArr": [[point.generation, point.max_fitness] for point in points],
                "avgArr": [[point.generation, point.avg_fitness] for point in points],
                "bestArr": [[point.generation, point.best_so_far] for point in points],
                "globalMaxArr": [
                    [point.global_generation, point.max_fitness] for point in points
                ],
                "globalAvgArr": [
                    [point.global_generation, point.avg_fitness] for point in points
                ],
                "globalBestArr": global_best,
                "diversity": [[point.generation, 0.0] for point in points],
                "invalid": [[point.generation, 0.0] for point in points],
            }
        )
    return runs


def dashboard_stub_rows(
    dataset: str, candidate_metrics: list[dict[str, object]]
) -> list[dict[str, object]]:
    rows = []
    for row in candidate_metrics:
        if row.get("dataset") != dataset or row.get("metric") != "place_variables_clause":
            continue
        rows.append(
            {
                "stub": str(row.get("stub_index")),
                "literals": int(to_float(row.get("body_literals"))),
                "variables": int(to_float(row.get("variables_slots"))),
                "aggregates": int(to_float(row.get("has_aggregate"))),
                "candidates": int(to_float(row.get("generated_placements"))),
                "valid": int(to_float(row.get("valid_placements"))),
                "unique": int(to_float(row.get("valid_placements"))),
                "maxScore": 0.0,
                "evalSeconds": to_float(row.get("seconds")),
            }
        )
    return rows


def dashboard_quality_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "run": int(to_float(row.get("run"))),
            "phase": str(row.get("phase_context") or row.get("phase") or ""),
            "wallTime": to_float(row.get("wall_time")),
            "score": to_float(row.get("score")),
            "coveredPositive": to_float(row.get("covered_positive")),
            "coveredNegative": to_float(row.get("covered_negative")),
            "programSize": to_float(row.get("program_size")),
            "bestFound": bool(to_float(row.get("best_found"))),
        }
        for row in rows
    ]


def dashboard_timing_events(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    if not rows:
        return []
    origin = min(to_float(row.get("started_perf")) for row in rows)
    rows = sorted(rows, key=lambda row: to_float(row.get("started_perf")))
    return [
        {
            "phase": str(row.get("phase") or ""),
            "seconds": to_float(row.get("seconds")),
            "start": to_float(row.get("started_perf")) - origin,
            "depth": int(to_float(row.get("depth"))),
        }
        for row in rows[:400]
        if to_float(row.get("seconds")) > 0
    ]


def first_row(rows: list[dict[str, object]], dataset: str) -> dict[str, object]:
    return next((row for row in rows if row.get("dataset") == dataset), {})


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
    keys = sorted(
        {
            (str(row.get("dataset", "")), str(row.get("operator", "")), str(row.get("strategy", "")))
            for row in rows
            if row.get("operator")
        }
    )
    for dataset, operator, strategy in keys:
        selected = [
            row
            for row in rows
            if row.get("dataset") == dataset
            and row.get("operator") == operator
            and row.get("strategy") == strategy
        ]
        children = sum(to_float(row.get("children")) for row in selected)
        children_improved = sum(
            to_float(row.get("children_improved")) for row in selected
        )
        children_duplicates = sum(
            to_float(row.get("children_duplicate_parent")) for row in selected
        )
        summary.append(
            {
                "dataset": dataset,
                "operator": operator,
                "strategy": strategy,
                "events": len(selected),
                "improvement_rate": children_improved / children
                if children
                else mean_bool(selected, "improved"),
                "acceptance_rate": mean_bool(selected, "accepted"),
                "duplicate_rate": children_duplicates / children
                if children
                else mean_bool(selected, "duplicate"),
                "changed_rate": mean_bool(selected, "changed"),
                "mean_score_delta": mean(
                    to_float(row.get("new_score")) - to_float(row.get("original_score"))
                    for row in selected
                    if row.get("new_score") not in (None, "")
                    and row.get("original_score") not in (None, "")
                ),
            }
        )
    return summary


def candidate_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    summary: list[dict[str, object]] = []
    datasets = sorted({str(row.get("dataset", "")) for row in rows})
    for dataset in datasets:
        selected = [row for row in rows if row.get("dataset") == dataset]
        placements = [
            row for row in selected if row.get("metric") == "place_variables_clause"
        ]
        summary.append(
            {
                "dataset": dataset,
                "placement_rows": len(placements),
                "mean_seconds_per_stub": mean(
                    to_float(row.get("seconds")) for row in placements
                ),
                "mean_valid_placements": mean(
                    to_float(row.get("valid_placements")) for row in placements
                ),
                "mean_generated_placements": mean(
                    to_float(row.get("generated_placements")) for row in placements
                ),
                "aggregate_stub_rate": mean_bool(placements, "has_aggregate"),
                "arithmetic_stub_rate": mean_bool(placements, "has_arithmetic"),
                "comparison_stub_rate": mean_bool(placements, "has_comparison"),
                "negation_stub_rate": mean_bool(placements, "has_negation"),
            }
        )
    return summary


def quality_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    summary: list[dict[str, object]] = []
    for dataset in sorted({str(row.get("dataset", "")) for row in rows}):
        selected = [row for row in rows if row.get("dataset") == dataset]
        summary.append(
            {
                "dataset": dataset,
                "evaluations": len(selected),
                "mean_score": mean(to_float(row.get("score")) for row in selected),
                "best_score": max(
                    [to_float(row.get("score")) for row in selected], default=0.0
                ),
                "best_found_rate": mean_bool(selected, "best_found"),
                "mean_program_size": mean(
                    to_float(row.get("program_size")) for row in selected
                ),
                "mean_covered_positive": mean(
                    to_float(row.get("covered_positive")) for row in selected
                ),
                "mean_covered_negative": mean(
                    to_float(row.get("covered_negative")) for row in selected
                ),
            }
        )
    return summary


def clingo_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    summary: list[dict[str, object]] = []
    keys = sorted(
        {
            (str(row.get("dataset", "")), str(row.get("operation", "")), str(row.get("phase_context", "")))
            for row in rows
            if row.get("operation")
        }
    )
    for dataset, operation, phase_context in keys:
        selected = [
            row
            for row in rows
            if row.get("dataset") == dataset
            and row.get("operation") == operation
            and row.get("phase_context") == phase_context
        ]
        summary.append(
            {
                "dataset": dataset,
                "operation": operation,
                "phase_context": phase_context,
                "calls": len(selected),
                "total_seconds": sum(to_float(row.get("seconds")) for row in selected),
                "mean_seconds": mean(to_float(row.get("seconds")) for row in selected),
                "total_models": sum(to_float(row.get("models")) for row in selected),
            }
        )
    return summary


def ga_fitness_means(points: list[GAMetric]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for dataset in sorted({p.dataset for p in points}):
        dataset_points = [p for p in points if p.dataset == dataset]
        for generation in sorted({p.global_generation for p in dataset_points}):
            generation_points = [
                p for p in dataset_points if p.global_generation == generation
            ]
            rows.append(
                {
                    "dataset": dataset,
                    "generation": generation,
                    "global_generation": generation,
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


def to_float(value: object) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        if value.lower() == "true":
            return 1.0
        if value.lower() == "false":
            return 0.0
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def mean_bool(rows: list[dict[str, object]], key: str) -> float:
    values = [
        to_float(row.get(key))
        for row in rows
        if key in row and row.get(key) not in (None, "")
    ]
    return mean(values)


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
