import time

from ..control import build_control
from ...timing import add, current_phase


def solve_all_models(
    lines: "list[str]",
    clingo_arguments: "list[str]" = [],
) -> "list[set[str]]":
    ctl = build_control(lines, clingo_arguments)
    models: "list[set[str]]" = []
    start = time.perf_counter()
    with ctl.solve(yield_=True) as handle:  # type: ignore
        for model in handle:  # type: ignore
            models.append(set(str(model).split()))
    add(f"{current_phase()}.solving", time.perf_counter() - start)
    return models
