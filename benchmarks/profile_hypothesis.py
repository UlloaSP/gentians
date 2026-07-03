from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from benchmarks.catalog import DEFAULT_DATASETS, case_names
from benchmarks.hypothesis_files import hypothesis_path, write_hypothesis_file
from benchmarks.profile_baseline import profile_arguments
from gentians import timing
from gentians.gentians import program_from_arguments
from gentians.rule_generation.hypothesis_space import build_hypothesis_space


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate benchmark hypothesis spaces.")
    parser.add_argument("--datasets", nargs="+", default=DEFAULT_DATASETS)
    parser.add_argument("--out-dir", type=Path, default=Path(".debug") / "hypothesis")
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="PATH=JSON",
        help="Override Arguments field, e.g. --set max_depth=4",
    )
    parser.add_argument(
        "--arguments-json",
        help="Full Arguments JSON object. Used for every listed dataset unless --set overrides it.",
    )
    parser.add_argument("--list-datasets", action="store_true")
    args = parser.parse_args()

    if args.list_datasets:
        print("\n".join(case_names()))
        return

    for dataset in args.datasets:
        try:
            arguments = profile_arguments(args, dataset)
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            raise SystemExit(f"Invalid arguments for dataset {dataset}: {exc}") from exc
        started = time.perf_counter()
        program = program_from_arguments(arguments)
        rule_space, metrics = build_profiled_hypothesis(program, arguments)
        path = hypothesis_path(args.out_dir, dataset)
        write_hypothesis_file(path, dataset, arguments, rule_space, metrics)
        elapsed = time.perf_counter() - started
        print(f"{dataset}: {len(rule_space)} clauses -> {path} ({elapsed:.2f}s)")


def build_profiled_hypothesis(program, arguments):
    with tempfile.TemporaryDirectory() as raw_tmp:
        tmp = Path(raw_tmp)
        timings_path = tmp / "timings.json"
        timing_events_path = tmp / "timing_events.jsonl"
        candidate_metrics_path = tmp / "candidate_metrics.jsonl"
        clingo_metrics_path = tmp / "clingo_metrics.jsonl"
        env = {
            "GENTIANS_TIMINGS_PATH": str(timings_path),
            "GENTIANS_TIMING_EVENTS_PATH": str(timing_events_path),
            "GENTIANS_CANDIDATE_METRICS_PATH": str(candidate_metrics_path),
            "GENTIANS_CLINGO_METRICS_PATH": str(clingo_metrics_path),
        }
        old_env = {key: os.environ.get(key) for key in env}
        try:
            os.environ.update(env)
            timing.reset()
            timing.set_enabled(True)
            rule_space = build_hypothesis_space(program, arguments)
            timing.export()
            metrics = {
                "timings": read_json_rows(timings_path),
                "timingEvents": read_jsonl_rows(timing_events_path),
                "candidateMetrics": read_jsonl_rows(candidate_metrics_path),
                "clingoMetrics": read_jsonl_rows(clingo_metrics_path),
            }
            return rule_space, metrics
        finally:
            for key, value in old_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            timing.reset()


def read_json_rows(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl_rows(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


if __name__ == "__main__":
    main()
