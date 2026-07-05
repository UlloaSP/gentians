from __future__ import annotations

import copy
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from gentians import Arguments


ROOT = Path(__file__).resolve().parents[1]
DATASETS = ROOT / "benchmarks" / "gentians"


def task(filename: str, **kwargs: object) -> Arguments:
    return Arguments(filename=str(DATASETS / filename), **kwargs)


CASES: dict[str, Arguments] = {
    "4queens": task(
        "4queens.txt",
        max_depth=5,
        max_variables=3,
    ),
    "5queens": task(
        "5queens.txt",
        max_depth=5,
        max_variables=5,
    ),
    "8queens": task(
        "8queens.txt",
        max_depth=5,
        max_variables=5,
    ),
    "adj2red": task(
        "adjacent_to_red.txt",
        max_depth=4,
    ),
    "clique": task(
        "clique.txt",
        max_depth=7,
        max_variables=2,
    ),
    "coin": task("coin.txt"),
    "euclid": task("euclid.txt", max_depth=8, max_variables=5),
    "coloring": task(
        "coloring.txt",
        disjunctive_head_length=3,
        max_depth=4,
        max_program_clauses=4,
    ),
    "even_odd": task(
        "even_odd.txt",
    ),
    "grandparent": task(
        "grandparent.txt",
        max_program_clauses=3,
    ),
    "sudoku": task(
        "sudoku.txt",
        max_depth=3,
    ),
    "hamming_0": task(
        "hamming_0.txt",
        max_depth=3,
        max_variables=4,
    ),
    "hamming_1": task(
        "hamming_1.txt",
        max_depth=3,
        max_variables=4,
    ),
    "hamming_0_unbalanced": task(
        "hamming_0_unbalanced.txt",
        max_depth=3,
        max_variables=4,
    ),
    "hamming_1_unbalanced": task(
        "hamming_1_unbalanced.txt",
        max_depth=3,
        max_variables=4,
    ),
    "subset_sum_unbalanced": task(
        "subset_sum_unbalanced.txt",
        max_depth=3,
    ),
    "subset_sum_unbalanced_ops": task(
        "subset_sum_unbalanced_ops.txt",
        max_depth=3,
    ),
    "subset_sum_double": task(
        "subset_sum_double.txt",
        max_depth=4,
        max_variables=3,
    ),
    "subset_sum_double_unbalanced": task(
        "subset_sum_double_unbalanced.txt",
        max_depth=4,
        max_variables=3,
    ),
    "subset_sum_double_unbalanced_count": task(
        "subset_sum_double_unbalanced_count.txt",
        max_depth=4,
        max_variables=3,
    ),
    "subset_sum_double_and_sum": task(
        "subset_sum_double_and_sum.txt",
        max_depth=4,
        max_variables=6,
    ),
    "subset_sum_double_and_prod": task(
        "subset_sum_double_and_prod.txt",
        max_depth=4,
        max_variables=5,
    ),
    "subset_sum_double_and_prod_unbalanced": task(
        "subset_sum_double_and_prod_unbalanced.txt",
        max_depth=4,
        max_variables=5,
    ),
    "subset_sum_triple": task(
        "subset_sum_triple.txt",
        max_depth=4,
        max_variables=4,
    ),
    "set_partition_sum": task(
        "set_partition_sum_new.txt",
        max_depth=4,
        max_variables=4,
    ),
    "set_partition_sum_and_cardinality": task(
        "set_partition_sum_and_cardinality_new.txt",
        max_depth=4,
        max_variables=4,
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
