from .all_models import solve_all_models


def solve_cautious_clingo(
    lines: "list[str]",
    clingo_arguments: "list[str]" = [],
) -> "set[str]":
    models = solve_all_models(lines, [*clingo_arguments, "--enum-mode=cautious"])
    return set.intersection(*models) if models else set()


def solve_cautious_python(
    lines: "list[str]",
    clingo_arguments: "list[str]" = [],
) -> "set[str]":
    models = solve_all_models(lines, clingo_arguments)
    return set.intersection(*models) if models else set()
