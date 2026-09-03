import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from benchmarks.catalog import DEFAULT_DATASETS, case_names  # noqa: E402
from benchmarks.profile_baseline import profile_arguments  # noqa: E402
from gentians import timing  # noqa: E402
from gentians.clauses import generate_clause_space  # noqa: E402
from gentians.gentians import task_from_arguments  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate benchmark clause spaces."
    )
    parser.add_argument("--datasets", nargs="+", default=DEFAULT_DATASETS)
    parser.add_argument("--out-dir", type=Path, default=Path(".debug") / "clauses")
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="PATH=JSON",
        help=(
            "Override Arguments field, e.g. --set clause_generation.clingo_arguments=[]"
        ),
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
        task = task_from_arguments(arguments)
        clause_space, metrics = build_profiled_clause_space(task, arguments)
        path = args.out_dir / f"{safe_filename(dataset)}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "entries": [
                        {
                            "text": entry.text,
                            "heads": [list(value) for value in sorted(entry.heads)],
                            "deps": [list(value) for value in sorted(entry.deps)],
                            "body_literals": entry.body_literals,
                        }
                        for entry in clause_space.entries
                    ],
                    "metrics": metrics,
                },
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        elapsed = time.perf_counter() - started
        print(f"{dataset}: {len(clause_space)} clauses -> ({elapsed:.2f}s)")


def build_profiled_clause_space(program, arguments):
    with tempfile.TemporaryDirectory() as raw_tmp:
        tmp = Path(raw_tmp)
        timings_path = tmp / "timings.json"
        clingo_metrics_path = tmp / "clingo_metrics.jsonl"
        env = {
            "GENTIANS_TIMINGS_PATH": str(timings_path),
            "GENTIANS_CLINGO_METRICS_PATH": str(clingo_metrics_path),
        }
        old_env = {key: os.environ.get(key) for key in env}
        try:
            os.environ.update(env)
            timing.reset()
            timing.set_enabled(True)
            clause_space = generate_clause_space(program, arguments)
            timing.export()
            metrics = {
                "timings": read_json_rows(timings_path),
                "clingoMetrics": read_jsonl_rows(clingo_metrics_path),
            }
            return clause_space, metrics
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


def safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value)


if __name__ == "__main__":
    main()
