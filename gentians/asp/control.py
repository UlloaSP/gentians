import time

import clingo

from .callbacks import wrapper_exit_callback
from ..timing import add, current_phase


def build_control(
    lines: "list[str]",
    clingo_arguments: "list[str]" = [],
) -> "clingo.Control":
    ctl = clingo.Control(clingo_arguments, logger=wrapper_exit_callback)
    for clause in lines:
        ctl.add("base", [], clause)
    start = time.perf_counter()
    ctl.ground([("base", [])])
    add(f"{current_phase()}.grounding", time.perf_counter() - start)
    return ctl
