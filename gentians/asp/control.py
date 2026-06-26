import time

import clingo

from .callbacks import wrapper_exit_callback
from ..timing import add, current_phase, record_metric


def build_control(
    lines: "list[str]",
    clingo_arguments: "list[str]",
) -> "clingo.Control":
    ctl = clingo.Control(clingo_arguments, logger=wrapper_exit_callback)
    for clause in lines:
        ctl.add("base", [], clause)
    start = time.perf_counter()
    ctl.ground([("base", [])])
    seconds = time.perf_counter() - start
    phase = current_phase()
    add(f"{phase}.grounding", seconds)
    record_metric(
        "clingo",
        {
            "operation": "grounding",
            "phase_context": phase,
            "seconds": seconds,
            "input_clauses": len(lines),
            "program_chars": sum(len(line) for line in lines),
            "clingo_arguments": " ".join(clingo_arguments),
        },
    )
    return ctl
