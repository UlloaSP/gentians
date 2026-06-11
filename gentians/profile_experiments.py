import argparse
import json
import shlex
import statistics
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .profiling import (
    ExperimentProfiler,
    TimingEvent,
    profiler_from_dict,
    write_csv,
    write_fitness_csv,
    write_html_report,
    write_json,
)


@dataclass(frozen=True)
class DatasetConfig:
    example: str
    flags: List[str]


def _cfg(example: str, *flags: str) -> DatasetConfig:
    return DatasetConfig(example=example, flags=list(flags))


DATASETS: Dict[str, DatasetConfig] = {
    "4queens": _cfg("4queens", "-d", "5", "--arithm", "add", "sub", "--comparison", "lt", "--variables", "3"),
    "adj2red": _cfg("adjacent_to_red", "-d", "4"),
    "clique": _cfg("clique", "-d", "7", "--comparison", "neq", "--variables", "2"),
    "coin": _cfg("coin"),
    "coloring": _cfg("coloring", "-dh", "3", "-d", "4"),
    "evenodd": _cfg("even_odd"),
    "grandparent": _cfg("grandparent"),
    "sudoku": _cfg("sudoku", "-d", "3"),
    "hamming0": _cfg("hamming_0", "-d", "3", "--aggregates", "sum(d/2)", "--comparison", "neq", "--variables", "4"),
    "hamming0e": _cfg("hamming_0", "-d", "3", "--aggregates", "sum(d/2)", "count(d/2)", "--comparison", "neq", "--variables", "4", "-ua"),
    "hamming1": _cfg("hamming_1", "-d", "3", "--aggregates", "sum(d/2)", "--comparison", "neq", "--variables", "4"),
    "hamming1e": _cfg("hamming_1", "-d", "3", "--aggregates", "sum(d/2)", "count(d/2)", "--comparison", "neq", "--variables", "4", "-ua"),
    "subsum1": _cfg("subset_sum", "-d", "3", "--aggregates", "sum(el/1)"),
    "subsum1e": _cfg("subset_sum", "-d", "3", "--aggregates", "sum(el/1)", "count(el/1)", "--comparison", "neq", "-ua"),
    "subsum1eop": _cfg("subset_sum", "-d", "3", "--aggregates", "sum(el/1)", "count(el/1)", "--comparison", "neq", "geq", "leq", "-ua"),
    "subsum2": _cfg("subset_sum_double", "-d", "4", "--aggregates", "sum(el/2)", "sum(el/2)", "--arithm", "add", "--variables", "3"),
    "subsum2eua": _cfg("subset_sum_double", "-d", "4", "--aggregates", "sum(el/2)", "sum(el/2)", "--arithm", "add", "--variables", "3", "-ua"),
    "subsum2euac": _cfg("subset_sum_double", "-d", "4", "--aggregates", "sum(el/2)", "sum(el/2)", "count(el/2)", "count(el/2)", "--arithm", "add", "--variables", "3", "-ua"),
    "subsum2prod": _cfg("subset_sum_double_and_prod", "-d", "4", "--aggregates", "sum(el/2)", "sum(el/2)", "--arithm", "add", "mul", "sub", "--variables", "5"),
    "subsum2produa": _cfg("subset_sum_double_and_prod", "-d", "4", "--aggregates", "sum(el/2)", "sum(el/2)", "--arithm", "add", "mul", "sub", "--variables", "5", "-ua"),
    "subsum2produac": _cfg("subset_sum_double_and_prod", "-d", "4", "--aggregates", "sum(el/2)", "sum(el/2)", "count(el/2)", "count(el/2)", "--arithm", "add", "mul", "sub", "--variables", "5", "-ua"),
    "subsum3": _cfg("subset_sum_triple", "-d", "4", "--aggregates", "sum(el/3)", "sum(el/3)", "sum(el/3)", "--variables", "4"),
    "subsum3ua": _cfg("subset_sum_triple", "-d", "4", "--aggregates", "sum(el/3)", "sum(el/3)", "sum(el/3)", "--variables", "4", "-ua"),
    "ps6": _cfg("set_partition_sum_new", "-d", "4", "--comparison", "neq", "neq", "--variables", "4", "--aggregates", "sum(p/2)", "-ua"),
    "ps12": _cfg("set_partition_sum", "-d", "4", "--comparison", "neq", "neq", "--variables", "4", "--aggregates", "sum(p/2)", "-ua"),
}


def _override_flags(
    samples: Optional[int],
    genetic_iterations: Optional[int],
    outer_iterations: Optional[int],
    population: Optional[int],
) -> List[str]:
    flags: List[str] = []
    if samples is not None:
        flags += ["--samples", str(samples)]
    if genetic_iterations is not None:
        flags += ["--iterations-genetic", str(genetic_iterations)]
    if outer_iterations is not None:
        flags += ["--iterations", str(outer_iterations)]
    if population is not None:
        flags += ["--pop-size", str(population)]
    return flags


def build_command(
    gentians_cmd: str,
    dataset: str,
    config: DatasetConfig,
    run_id: int,
    seed: int,
    profile_path: Path,
    overrides: List[str],
) -> List[str]:
    return [
        *shlex.split(gentians_cmd),
        "-e",
        config.example,
        *config.flags,
        *overrides,
        "--seed",
        str(seed),
        "--profile-output",
        str(profile_path),
        "--profile-dataset",
        dataset,
        "--profile-run",
        str(run_id),
    ]


def _load_profile(path: Path) -> ExperimentProfiler:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data:
        raise ValueError(f"Empty profile file: {path}")
    return profiler_from_dict(data[0])


def _write_failed_profile(
    path: Path,
    dataset: str,
    run_id: int,
    elapsed: float,
    status: str,
    returncode: Optional[int] = None,
) -> ExperimentProfiler:
    profiler = ExperimentProfiler(dataset=dataset, run=run_id)
    profiler.events.append(
        TimingEvent(
            name=f"run.{status}",
            seconds=elapsed,
            dataset=dataset,
            run=run_id,
            iteration=0,
            metadata={"returncode": returncode} if returncode is not None else {},
        )
    )
    write_json(path, [profiler])
    return profiler


def _write_outputs(out_dir: Path, profilers: List[ExperimentProfiler]) -> None:
    all_events = [event for profiler in profilers for event in profiler.events]
    all_fitness = [point for profiler in profilers for point in profiler.fitness]
    write_json(out_dir / "profile_raw.json", profilers)
    write_csv(out_dir / "profile_events.csv", all_events)
    write_fitness_csv(out_dir / "fitness_evolution.csv", all_fitness)
    write_html_report(out_dir / "report.html", profilers)


def run_profile(
    dataset_names: Iterable[str],
    runs: int,
    out_dir: Path,
    seed: int,
    gentians_cmd: str = "gentians",
    samples: Optional[int] = None,
    genetic_iterations: Optional[int] = None,
    outer_iterations: Optional[int] = None,
    population: Optional[int] = None,
    timeout_seconds: int = 100,
) -> List[ExperimentProfiler]:
    out_dir.mkdir(parents=True, exist_ok=True)
    profiles_dir = out_dir / "runs"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    profilers: List[ExperimentProfiler] = []
    overrides = _override_flags(samples, genetic_iterations, outer_iterations, population)
    commands_path = out_dir / "commands.txt"

    dataset_list = list(dataset_names)
    total_runs = len(dataset_list) * runs
    completed = 0

    with commands_path.open("w", encoding="utf-8") as commands_file:
        for dataset_index, dataset in enumerate(dataset_list, start=1):
            if dataset not in DATASETS:
                raise ValueError(f"Unknown dataset: {dataset}")
            config = DATASETS[dataset]

            for run_id in range(1, runs + 1):
                completed += 1
                run_seed = seed + run_id
                profile_path = profiles_dir / f"{dataset}_run_{run_id}.json"
                log_path = profiles_dir / f"{dataset}_run_{run_id}.log"
                cmd = build_command(gentians_cmd, dataset, config, run_id, run_seed, profile_path, overrides)
                printable_cmd = subprocess.list2cmdline(cmd)
                commands_file.write(printable_cmd + "\n")
                print(
                    f"[{completed}/{total_runs}] dataset {dataset_index}/{len(dataset_list)} "
                    f"{dataset} run {run_id}/{runs} start timeout={timeout_seconds}s",
                    flush=True,
                )
                print(f"cmd: {printable_cmd}", flush=True)
                start = time.perf_counter()
                with log_path.open("w", encoding="utf-8") as log_file:
                    try:
                        result = subprocess.run(
                            cmd,
                            stdout=log_file,
                            stderr=subprocess.STDOUT,
                            timeout=timeout_seconds,
                            check=False,
                        )
                        elapsed = time.perf_counter() - start
                        if result.returncode == 0:
                            profiler = _load_profile(profile_path)
                            print(f"[{completed}/{total_runs}] {dataset} run {run_id} ok {elapsed:.2f}s", flush=True)
                        else:
                            profiler = _write_failed_profile(
                                profile_path,
                                dataset,
                                run_id,
                                elapsed,
                                "failed",
                                result.returncode,
                            )
                            print(
                                f"[{completed}/{total_runs}] {dataset} run {run_id} failed "
                                f"code={result.returncode} {elapsed:.2f}s log={log_path}",
                                flush=True,
                            )
                    except subprocess.TimeoutExpired:
                        elapsed = time.perf_counter() - start
                        profiler = _write_failed_profile(profile_path, dataset, run_id, elapsed, "timeout")
                        print(f"[{completed}/{total_runs}] {dataset} run {run_id} timeout {elapsed:.2f}s log={log_path}", flush=True)
                profilers.append(profiler)
                _write_outputs(out_dir, profilers)

    return profilers


def _print_summary(profilers: List[ExperimentProfiler]) -> None:
    by_dataset: Dict[str, List[float]] = {}
    for profiler in profilers:
        total = sum(event.seconds for event in profiler.events if event.name == "solver.total")
        by_dataset.setdefault(profiler.dataset, []).append(total)
    for dataset, totals in sorted(by_dataset.items()):
        stdev = statistics.stdev(totals) if len(totals) > 1 else 0.0
        print(f"{dataset}: mean={statistics.mean(totals):.6f}s stdev={stdev:.6f}s runs={len(totals)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run each GENTIANS dataset N times through the gentians CLI.")
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--datasets", nargs="+", default=list(DATASETS.keys()))
    parser.add_argument("--out-dir", type=Path, default=Path(".benchmarks") / "profiling")
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--gentians-cmd", default="gentians", help="Command used to run one experiment.")
    parser.add_argument("--samples", type=int, default=None, help="Override sampled clauses per run.")
    parser.add_argument("--genetic-iterations", type=int, default=None, help="Override GA iterations.")
    parser.add_argument("--outer-iterations", type=int, default=None, help="Override sampling/GA outer iterations.")
    parser.add_argument("--population", type=int, default=None, help="Override population size.")
    parser.add_argument("--timeout-seconds", type=int, default=100, help="Per-run timeout.")
    parsed = parser.parse_args()

    profilers = run_profile(
        parsed.datasets,
        parsed.runs,
        parsed.out_dir,
        parsed.seed,
        gentians_cmd=parsed.gentians_cmd,
        samples=parsed.samples,
        genetic_iterations=parsed.genetic_iterations,
        outer_iterations=parsed.outer_iterations,
        population=parsed.population,
        timeout_seconds=parsed.timeout_seconds,
    )
    _print_summary(profilers)
    print(f"Commands: {parsed.out_dir / 'commands.txt'}")
    print(f"Report: {parsed.out_dir / 'report.html'}")


if __name__ == "__main__":
    main()
