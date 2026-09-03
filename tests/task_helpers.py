from typing import Any

from gentians.language.asp import parse_program
from gentians.language.ir.inductive_task import InductiveTask


def inductive_task(background: list[str], *args: Any, **kwargs: Any) -> InductiveTask:
    return InductiveTask(parse_program("\n".join(background)), *args, **kwargs)
