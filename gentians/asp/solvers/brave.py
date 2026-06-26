from .all_models import solve_all_models


def solve_brave_clingo(
    lines: "list[str]",
    clingo_arguments: "list[str]",
) -> "set[str]":
    models = solve_all_models(lines, [*clingo_arguments, "--enum-mode=brave"])
    return set().union(*models) if models else set()


def solve_brave_python(
    lines: "list[str]",
    clingo_arguments: "list[str]",
) -> "set[str]":
    models = solve_all_models(lines, clingo_arguments)
    return set().union(*models) if models else set()
