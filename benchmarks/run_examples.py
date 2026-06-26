from __future__ import annotations

from pathlib import Path

from gentians import Arguments, main


ROOT = Path(__file__).resolve().parents[1]
DATASETS = ROOT / "benchmarks" / "gentians"


def task(filename: str, **kwargs: object) -> Arguments:
    """Build SDK arguments for one benchmark task."""

    return Arguments(filename=str(DATASETS / filename), **kwargs)


EXAMPLES: dict[str, Arguments] = {
    "4queens": task(
        "4queens.txt",
        max_depth=5,
        arithmetic_operators=["add", "sub"],
        comparison_operators=["lt"],
        max_variables=3,
    ),
    "adjacent_to_red": task("adjacent_to_red.txt", max_depth=4),
    "clique": task(
        "clique.txt",
        max_depth=7,
        comparison_operators=["neq"],
        max_variables=2,
    ),
    "coin": task("coin.txt"),
    "coloring": task(
        "coloring.txt",
        disjunctive_head_length=3,
        max_depth=4,
    ),
    "even_odd": task("even_odd.txt"),
    "grandparent": task("grandparent.txt"),
    "sudoku": task("sudoku.txt", max_depth=3),
    "hamming_0": task(
        "hamming_0.txt",
        max_depth=3,
        aggregates=["sum(d/2)"],
        comparison_operators=["neq"],
        max_variables=4,
    ),
    "hamming_1": task(
        "hamming_1.txt",
        max_depth=3,
        aggregates=["sum(d/2)"],
        comparison_operators=["neq"],
        max_variables=4,
    ),
    "hamming_0_unbalanced": task(
        "hamming_0.txt",
        max_depth=3,
        aggregates=["sum(d/2)", "count(d/2)"],
        comparison_operators=["neq"],
        max_variables=4,
        unbalanced_aggregates=True,
    ),
    "hamming_1_unbalanced": task(
        "hamming_1.txt",
        max_depth=3,
        aggregates=["sum(d/2)", "count(d/2)"],
        comparison_operators=["neq"],
        max_variables=4,
        unbalanced_aggregates=True,
    ),
    "subset_sum_unbalanced": task(
        "subset_sum.txt",
        max_depth=3,
        aggregates=["sum(el/1)", "count(el/1)"],
        comparison_operators=["neq"],
        unbalanced_aggregates=True,
    ),
    "subset_sum_unbalanced_ops": task(
        "subset_sum.txt",
        max_depth=3,
        aggregates=["sum(el/1)", "count(el/1)"],
        comparison_operators=["neq", "geq", "leq"],
        unbalanced_aggregates=True,
    ),
    "subset_sum_double": task(
        "subset_sum_double.txt",
        max_depth=4,
        aggregates=["sum(el/2)", "sum(el/2)"],
        arithmetic_operators=["add"],
        max_variables=3,
    ),
    "subset_sum_double_unbalanced": task(
        "subset_sum_double.txt",
        max_depth=4,
        aggregates=["sum(el/2)", "sum(el/2)"],
        arithmetic_operators=["add"],
        max_variables=3,
        unbalanced_aggregates=True,
    ),
    "subset_sum_double_unbalanced_count": task(
        "subset_sum_double.txt",
        max_depth=4,
        aggregates=["sum(el/2)", "sum(el/2)", "count(el/2)", "count(el/2)"],
        arithmetic_operators=["add"],
        max_variables=3,
        unbalanced_aggregates=True,
    ),
    "subset_sum_double_and_prod": task(
        "subset_sum_double_and_prod.txt",
        max_depth=4,
        aggregates=["sum(el/2)", "sum(el/2)"],
        arithmetic_operators=["add", "mul", "sub"],
        max_variables=5,
    ),
    "subset_sum_double_and_prod_unbalanced": task(
        "subset_sum_double_and_prod.txt",
        max_depth=4,
        aggregates=["sum(el/2)", "sum(el/2)"],
        arithmetic_operators=["add", "mul", "sub"],
        max_variables=5,
        unbalanced_aggregates=True,
    ),
    "subset_sum_triple": task(
        "subset_sum_triple.txt",
        max_depth=4,
        aggregates=["sum(el/3)", "sum(el/3)", "sum(el/3)"],
        max_variables=4,
    ),
    "set_partition_sum_new": task(
        "set_partition_sum_new.txt",
        max_depth=4,
        comparison_operators=["neq", "neq"],
        max_variables=4,
        aggregates=["sum(p/2)"],
        unbalanced_aggregates=True,
    ),
    "set_partition_sum": task(
        "set_partition_sum.txt",
        max_depth=4,
        comparison_operators=["neq", "neq"],
        max_variables=4,
        aggregates=["sum(p/2)"],
        unbalanced_aggregates=True,
    ),
}


# Edit this list to choose tasks. Use list(EXAMPLES) to run every benchmark.
SELECTED = ["coin"]


def run(selected: list[str] = SELECTED) -> None:
    for name in selected:
        print(f"Running {name}")
        main(EXAMPLES[name])


if __name__ == "__main__":
    run()
