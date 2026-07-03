from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE_GA_PATH = Path(__file__).resolve()
sys.path.insert(0, str(REPO_ROOT))

from benchmarks.hypothesis_files import (
    hypothesis_path,
    read_hypothesis_file,
    read_hypothesis_metrics,
)
from benchmarks.profile_baseline import (
    parse_profile_args,
    run_benchmark_suite,
)
from gentians import Arguments
from gentians import timing
from gentians.gentians import program_from_arguments, solve


def main() -> None:
    args = parse_profile_args(
        "Profile GA using pre-generated benchmark hypothesis spaces.",
        Path(".benchmarks") / "ga_profile",
        add_hypothesis_dir_arg,
    )
    run_benchmark_suite(args, PROFILE_GA_PATH, hypothesis_env(args.hypothesis_dir))


def add_hypothesis_dir_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--hypothesis-dir", type=Path, default=Path(".debug") / "hypothesis"
    )


def hypothesis_env(directory: Path):
    def env(dataset: str, arguments: Arguments) -> dict[str, str]:
        path = hypothesis_path(directory, dataset)
        read_hypothesis_file(path, arguments)
        return {"GENTIANS_HYPOTHESIS_SPACE_PATH": str(path.resolve())}

    return env


def run_profile_worker() -> None:
    payload = os.environ["GENTIANS_ARGUMENTS_JSON"]
    arguments = Arguments(**json.loads(payload))
    seed = os.environ.get("GENTIANS_RANDOM_SEED")
    if seed is not None:
        random.seed(int(seed))
    path = Path(os.environ["GENTIANS_HYPOTHESIS_SPACE_PATH"])
    rule_space = read_hypothesis_file(path, arguments)
    replay_hypothesis_metrics(read_hypothesis_metrics(path, arguments))
    solve(program_from_arguments(arguments), arguments, rule_space)


def replay_hypothesis_metrics(metrics: dict[str, object]) -> None:
    timings = [row for row in metrics.get("timings", []) if isinstance(row, dict)]
    clingo_rows = [
        row for row in metrics.get("clingoMetrics", []) if isinstance(row, dict)
    ]
    for row in timings:
        metric = row.get("metric")
        if not isinstance(metric, str):
            continue
        seconds = float(row.get("seconds", 0.0))
        calls = int(row.get("calls", 0))
        timing._totals[metric] = timing._totals.get(metric, 0.0) + seconds
        timing._counts[metric] = timing._counts.get(metric, 0) + calls
    hypothesis_seconds = float(
        next(
            (
                row.get("seconds", 0.0)
                for row in timings
                if row.get("metric") == "hypothesis_space"
            ),
            0.0,
        )
    )
    if hypothesis_seconds:
        timing._totals["total_execution"] = (
            timing._totals.get("total_execution", 0.0) + hypothesis_seconds
        )
        timing._counts["total_execution"] = timing._counts.get("total_execution", 0) + 1
    timing._timings_dirty = True
    append_jsonl(os.environ.get("GENTIANS_CLINGO_METRICS_PATH"), clingo_rows)
    append_jsonl(
        os.environ.get("GENTIANS_TIMING_EVENTS_PATH"),
        synthetic_hypothesis_events(timings, hypothesis_seconds),
    )


def synthetic_hypothesis_events(
    timings: list[dict[str, object]], hypothesis_seconds: float
) -> list[dict[str, object]]:
    if not hypothesis_seconds:
        return []
    started = time.perf_counter() - hypothesis_seconds
    ended = started + hypothesis_seconds
    self_seconds = float(
        next(
            (
                row.get("seconds", 0.0)
                for row in timings
                if row.get("metric") == "hypothesis_space.self"
            ),
            0.0,
        )
    )
    return [
        {
            "event_id": -1,
            "parent_id": None,
            "phase": "hypothesis_space",
            "depth": 1,
            "started_perf": started,
            "ended_perf": ended,
            "started_wall": time.time() - hypothesis_seconds,
            "ended_wall": time.time(),
            "seconds": hypothesis_seconds,
            "self_seconds": self_seconds,
        }
    ]


def append_jsonl(path: str | None, rows: list[dict[str, object]]) -> None:
    if not path or not rows:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


if __name__ == "__main__":
    if os.environ.get("GENTIANS_PROFILE_WORKER") == "1":
        run_profile_worker()
    else:
        main()
