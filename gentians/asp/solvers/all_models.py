import time

from ..control import build_control
from ...timing import add, current_phase, record_metric


def solve_all_models(
    lines: "list[str]",
    clingo_arguments: "list[str]",
) -> "list[set[str]]":
    ctl = build_control(lines, clingo_arguments)
    models: "list[set[str]]" = []
    start = time.perf_counter()
    with ctl.solve(yield_=True) as handle:  # type: ignore
        for model in handle:  # type: ignore
            models.append({str(symbol) for symbol in model.symbols(shown=True)})
    seconds = time.perf_counter() - start
    phase = current_phase()
    add(f"{phase}.solving", seconds)
    record_metric(
        "clingo",
        {
            "operation": "solving",
            "phase_context": phase,
            "seconds": seconds,
            "models": len(models),
            "program_size": len(lines),
            "coverage_subsets": 0,
            "clingo_arguments": " ".join(clingo_arguments),
        },
    )
    return models
