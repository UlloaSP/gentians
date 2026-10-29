import copy
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from gentians import Arguments

ROOT = Path(__file__).resolve().parents[1]
DATASETS = ROOT / "benchmarks" / "gentians"


def task(directory: str) -> Arguments:
    return Arguments(filename=str(DATASETS / directory))


# Ordered by generated clauses, fewest first.
CASES: dict[str, Arguments] = {
    "constant_colour": task("constant_colour"),
    "penguin": task("penguin"),
    "hamming_0": task("hamming_0"),
    "hamming_1": task("hamming_1"),
    "pedro": task("pedro"),
    "clique": task("clique"),
    "coin": task("coin"),
    "knapsack": task("knapsack"),
    "subset_sum": task("subset_sum"),
    "adj2red": task("adjacent_to_red"),
    "pedro_constraints": task("pedro_constraints"),
    "hamming_0_unbalanced": task("hamming_0_unbalanced"),
    "hamming_1_unbalanced": task("hamming_1_unbalanced"),
    "animals_bird": task("animals_bird"),
    "subset_sum_unbalanced": task("subset_sum_unbalanced"),
    "even_odd": task("even_odd"),
    "subset_sum_unbalanced_ops": task("subset_sum_unbalanced_ops"),
    "coloring": task("coloring"),
    "set_partition_sum": task("set_partition_sum"),
    "latin_square": task("latin_square"),
    "4queens": task("4queens"),
    "grandparent": task("grandparent"),
    "subset_sum_double_and_sum": task("subset_sum_double_and_sum"),
    "subset_sum_triple": task("subset_sum_triple"),
    "pedro_cabeza": task("pedro_cabeza"),
    "magic_square_no_diag": task("magic_square_no_diag"),
    "sudoku": task("sudoku"),
    "subset_sum_double_unbalanced": task("subset_sum_double_unbalanced"),
    "subset_sum_double": task("subset_sum_double"),
    "set_partition_sum_and_cardinality": task("set_partition_sum_and_cardinality"),
    "set_partition_sum_cardinality_and_square": task(
        "set_partition_sum_cardinality_and_square"
    ),
    "5queens": task("5queens"),
    "8queens": task("8queens"),
    "subset_sum_double_and_prod_unbalanced": task(
        "subset_sum_double_and_prod_unbalanced"
    ),
    "subset_sum_double_and_prod": task("subset_sum_double_and_prod"),
    "subset_sum_double_unbalanced_count": task("subset_sum_double_unbalanced_count"),
    "pedro_disyuntiva": task("pedro_disyuntiva"),
    "alzheimer_acetyl": task("alzheimer_acetyl"),
    "alzheimer_amine": task("alzheimer_amine"),
    "alzheimer_mem": task("alzheimer_mem"),
    "alzheimer_toxic": task("alzheimer_toxic"),
    "synthetic_million": task("synthetic_million"),
    "euclid": task("euclid"),
}


# Profiling runs every case by default except these opt-in heavy ones.
HEAVY_DATASETS = {"synthetic_million", "euclid"}
DEFAULT_DATASETS = [name for name in CASES if name not in HEAVY_DATASETS]


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
