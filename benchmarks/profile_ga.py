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
    metrics_from_payload,
    read_hypothesis_payload,
    rule_space_from_payload,
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
        if not path.exists():
            raise FileNotFoundError(f"Hypothesis space not found: {path}")
        return {"GENTIANS_HYPOTHESIS_SPACE_PATH": str(path.resolve())}

    return env


def run_profile_worker() -> None:
    payload = os.environ["GENTIANS_ARGUMENTS_JSON"]
    arguments = Arguments(**json.loads(payload))
    seed = os.environ.get("GENTIANS_RANDOM_SEED")
    if seed is not None:
        random.seed(int(seed))
    path = Path(os.environ["GENTIANS_HYPOTHESIS_SPACE_PATH"])
    worker_started = time.time()
    started = time.perf_counter()
    payload = read_hypothesis_payload(path, arguments)
    rule_space = rule_space_from_payload(payload, path)
    load_seconds = time.perf_counter() - started
    timing.add("hypothesis_load", load_seconds)
    replay_hypothesis_metrics(metrics_from_payload(payload))
    solve(
        program_from_arguments(arguments),
        arguments,
        rule_space,
        start_total_time=worker_started,
    )


def replay_hypothesis_metrics(metrics: dict[str, object]) -> None:
    timings = [row for row in metrics.get("timings", []) if isinstance(row, dict)]
    clingo_rows = [
        row for row in metrics.get("clingoMetrics", []) if isinstance(row, dict)
    ]
    timing.merge_timings(timings)
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
        timing.merge_timings(
            [{"metric": "total_execution", "seconds": hypothesis_seconds, "calls": 1}]
        )
    timing.append_jsonl(os.environ.get("GENTIANS_CLINGO_METRICS_PATH"), clingo_rows)
    timing.append_jsonl(
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


if __name__ == "__main__":
    if os.environ.get("GENTIANS_PROFILE_WORKER") == "1":
        run_profile_worker()
    else:
        main()
