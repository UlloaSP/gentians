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
from benchmarks.process_resources import peak_rss_bytes  # noqa: E402
from gentians import timing  # noqa: E402
from gentians.clauses import generate_clause_space  # noqa: E402
from gentians.gentians import task_from_arguments  # noqa: E402

ALZHEIMER_DATASETS = tuple(
    name for name in case_names() if name.startswith("alzheimer_")
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate benchmark clause spaces and report generation costs and throughput."
    )
    parser.add_argument(
        "--datasets", nargs="+", default=DEFAULT_DATASETS,
        help="Dataset names, or 'alzheimer' for all four Alzheimer's tasks.",
    )
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

    datasets = []
    for name in args.datasets:
        datasets.extend(ALZHEIMER_DATASETS if name == "alzheimer" else (name,))

    for dataset in datasets:
        try:
            arguments = profile_arguments(args, dataset)
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            raise SystemExit(f"Invalid arguments for dataset {dataset}: {exc}") from exc
        started = time.perf_counter()
        task = task_from_arguments(arguments)
        loading_seconds = time.perf_counter() - started
        generation_started = time.perf_counter()
        clause_space, metrics = build_profiled_clause_space(task, arguments)
        generation_wall_seconds = time.perf_counter() - generation_started
        serialization_started = time.perf_counter()
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
        serialization_seconds = time.perf_counter() - serialization_started
        elapsed = time.perf_counter() - started
        print_profile_report(
            dataset, len(clause_space), metrics,
            loading_seconds=loading_seconds,
            generation_wall_seconds=generation_wall_seconds,
            serialization_seconds=serialization_seconds,
            total_seconds=elapsed,
            peak_memory_bytes=peak_rss_bytes(),
            path=path,
        )


def print_profile_report(
    dataset, clauses, metrics, *, loading_seconds, generation_wall_seconds,
    serialization_seconds, total_seconds, peak_memory_bytes, path,
) -> None:
    timings = {row["metric"]: row["seconds"] for row in metrics["timings"]}
    generation = timings.get("clause_generation")
    grounding = timings.get("clause_generation.grounding")
    solving = timings.get("clause_generation.solving")
    python = (
        max(generation - grounding - solving, 0.0)
        if generation is not None and grounding is not None and solving is not None
        else None
    )
    clingo_rows = [
        row for row in metrics["clingoMetrics"]
        if row.get("phase_context") == "clause_generation"
    ]
    grounds = [row for row in clingo_rows if row["operation_category"] == "grounding"]
    solves = [row for row in clingo_rows if row["operation_category"] == "solving"]
    models = int(sum(row["models"] for row in solves)) if solves else None

    def duration(seconds):
        return f"{seconds:.3f}s" if seconds is not None else "N/A"

    def rate(count, seconds):
        return f"{count / seconds:,.2f}/s" if count is not None and seconds else "N/A"

    print(f"\n{dataset}: {clauses:,} final clauses (canonical, deduplicated)")
    print("  Time:")
    print(f"    Task loading: {loading_seconds:.3f}s")
    print(f"    Clause generation (net): {duration(generation)}")
    for label, seconds in (("Grounding", grounding), ("Solving", solving), ("Python", python)):
        share = f" ({100 * seconds / generation:.1f}%)" if generation and seconds is not None else ""
        print(f"      {label}: {duration(seconds)}{share}")
    print("      Python includes preparation, decoding, canonicalization and deduplication.")
    print("      Solving excludes Python model callbacks.")
    print(f"    Generation wall-clock (including profiling/export): {generation_wall_seconds:.3f}s")
    print(f"    JSON serialization + write: {serialization_seconds:.3f}s")
    print(f"    Total wall-clock (load + generation + JSON): {total_seconds:.3f}s")
    print("  Throughput:")
    print(f"    Final clauses / generation wall-clock: {rate(clauses, generation_wall_seconds)}")
    print(f"    Final clauses / net generation: {rate(clauses, generation)}")
    per_clause = (
        f"{1e6 * generation / clauses:,.2f} us/clause"
        if clauses and generation is not None else "N/A"
    )
    print(f"    Amortized net generation time: {per_clause}")
    print(f"    Final clauses / total wall-clock: {rate(clauses, total_seconds)}")
    print(f"    Enumerated models / net generation: {rate(models, generation)}")
    print("  Enumeration:")
    model_count = f"{models:,}" if models is not None else "N/A"
    print(f"    Clingo models (after ASP pruning): {model_count}")
    removed = f"{models - clauses:,}" if models is not None else "N/A"
    retention = f"{100 * clauses / models:.2f}%" if models else "N/A"
    print(f"    Removed/merged after enumeration: {removed}")
    print(f"    Post-enumeration retention (final clauses / models): {retention}")
    print("    Pre-pruning candidates, raw throughput and global survival: N/A")
    print("      Clingo prunes internally; models do not count rejected combinations.")
    print("  Clingo:")
    print(f"    Ground calls: {len(grounds)}; solve calls: {len(solves)}")
    if grounds:
        print(f"    Ground atoms: {int(max(row['stats_atoms'] for row in grounds)):,}")
        print(f"    Ground rules: {int(max(row['stats_rules'] for row in grounds)):,}")
    if solves:
        print(f"    Choices: {int(sum(row['stats_choices'] for row in solves)):,}")
        print(f"    Conflicts: {int(sum(row['stats_conflicts'] for row in solves)):,}")
    print(f"  Peak RSS (process so far, including JSON): {peak_memory_bytes / 2**20:,.2f} MiB")
    print(f"  Output: {path} ({path.stat().st_size / 2**20:,.2f} MiB)")


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
        old_enabled = timing.is_enabled()
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
            timing.set_enabled(old_enabled)


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
