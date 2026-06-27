from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from gentians import main
from benchmarks.catalog import DEFAULT_DATASETS, arguments_for, case_names


def main_cli() -> None:
    parser = argparse.ArgumentParser(description="Run GENTIANS benchmark examples.")
    parser.add_argument("datasets", nargs="*", default=DEFAULT_DATASETS)
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="PATH=JSON",
        help="Override Arguments field, e.g. --set iterations_genetic=1000 --set fitness.name=coverage_exp_max",
    )
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list:
        print("\n".join(case_names()))
        return

    run(args.datasets, args.set)


def run(selected: list[str], overrides: list[str] | None = None) -> None:
    for name in selected:
        print(f"Running {name}")
        main(arguments_for(name, overrides))


if __name__ == "__main__":
    main_cli()
