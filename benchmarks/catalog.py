from __future__ import annotations

import copy
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from gentians import Arguments

ROOT = Path(__file__).resolve().parents[1]
DATASETS = ROOT / "benchmarks" / "gentians"


def task(filename: str) -> Arguments:
    return Arguments(filename=str(DATASETS / filename))


CASES: dict[str, Arguments] = {
    "4queens": task("4queens.txt"),
    "5queens": task("5queens.txt"),
    "8queens": task("8queens.txt"),
    "adj2red": task("adjacent_to_red.txt"),
    "animals_bird": task("animals_bird.txt"),
    "clique": task("clique.txt"),
    "coin": task("coin.txt"),
    "constant_colour": task("constant_colour.txt"),
    "euclid": task("euclid.txt"),
    "coloring": task("coloring.txt"),
    "even_odd": task("even_odd.txt"),
    "grandparent": task("grandparent.txt"),
    "knapsack": task("knapsack.txt"),
    "latin_square": task("latin_square.txt"),
    "magic_square_no_diag": task("magic_square_no_diag.txt"),
    "penguin": task("penguin.txt"),
    "sudoku": task("sudoku.txt"),
    "subset_sum": task("subset_sum.txt"),
    "hamming_0": task("hamming_0.txt"),
    "hamming_1": task("hamming_1.txt"),
    "hamming_0_unbalanced": task("hamming_0_unbalanced.txt"),
    "hamming_1_unbalanced": task("hamming_1_unbalanced.txt"),
    "subset_sum_unbalanced": task("subset_sum_unbalanced.txt"),
    "subset_sum_unbalanced_ops": task("subset_sum_unbalanced_ops.txt"),
    "subset_sum_double": task("subset_sum_double.txt"),
    "subset_sum_double_unbalanced": task("subset_sum_double_unbalanced.txt"),
    "subset_sum_double_unbalanced_count": task(
        "subset_sum_double_unbalanced_count.txt"
    ),
    "subset_sum_double_and_sum": task("subset_sum_double_and_sum.txt"),
    "subset_sum_double_and_prod": task("subset_sum_double_and_prod.txt"),
    "subset_sum_double_and_prod_unbalanced": task(
        "subset_sum_double_and_prod_unbalanced.txt"
    ),
    "subset_sum_triple": task("subset_sum_triple.txt"),
    "set_partition_sum": task("set_partition_sum.txt"),
    "set_partition_sum_and_cardinality": task(
        "set_partition_sum_and_cardinality.txt"
    ),
    "set_partition_sum_cardinality_and_square": task(
        "set_partition_sum_cardinality_and_square.txt"
    ),
}


DEFAULT_DATASETS = [
    "coin",
    "adj2red",
    "clique",
    "4queens",
    "8queens",
    "5queens",
    "even_odd",
    "grandparent",
    "sudoku",
    "coloring",
    "knapsack",
    "latin_square",
    "magic_square_no_diag",
    "penguin",
    "subset_sum",
    "hamming_0",
    "hamming_1",
    "hamming_0_unbalanced",
    "hamming_1_unbalanced",
    "subset_sum_unbalanced",
    "subset_sum_unbalanced_ops",
    "subset_sum_double",
    "subset_sum_double_unbalanced",
    "subset_sum_double_unbalanced_count",
    "subset_sum_double_and_sum",
    "subset_sum_double_and_prod",
    "subset_sum_double_and_prod_unbalanced",
    "subset_sum_triple",
    "set_partition_sum",
    "set_partition_sum_and_cardinality",
    "set_partition_sum_cardinality_and_square",
]


def case_names() -> list[str]:
    return sorted(CASES)


def arguments_for(name: str, overrides: list[str] | None = None) -> Arguments:
    if name not in CASES:
        raise KeyError(name)
    arguments = copy.deepcopy(CASES[name])
    apply_overrides(arguments, overrides or [])
    return arguments


def arguments_json(arguments: Arguments) -> str:
    return json.dumps(asdict(arguments), sort_keys=True)


def arguments_from_json(raw: str, overrides: list[str] | None = None) -> Arguments:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("arguments JSON must be an object")
    arguments = Arguments(**value)
    apply_overrides(arguments, overrides or [])
    return arguments


def apply_overrides(arguments: Arguments, overrides: list[str]) -> None:
    for raw in overrides:
        path, value = parse_override(raw)
        set_path(arguments, path, value)


def parse_override(raw: str) -> tuple[str, Any]:
    if "=" not in raw:
        raise ValueError(f"override must be path=value: {raw}")
    path, value = raw.split("=", 1)
    if not path:
        raise ValueError(f"override path cannot be empty: {raw}")
    return path, parse_value(value)


def parse_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def set_path(arguments: Arguments, path: str, value: Any) -> None:
    parts = path.split(".")
    if len(parts) == 1:
        if not hasattr(arguments, path):
            raise ValueError(f"unknown Arguments field: {path}")
        setattr(arguments, path, value)
        return
    current: Any = getattr(arguments, parts[0], None)
    if not isinstance(current, dict):
        raise ValueError(f"override root is not a dict: {parts[0]}")
    for part in parts[1:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[parts[-1]] = value
