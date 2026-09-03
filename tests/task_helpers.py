from typing import Any

from gentians.language.asp import parse_program
from gentians.language.ir.example import Example
from gentians.language.ir.inductive_task import InductiveTask


def inductive_task(background: list[str], *args: Any, **kwargs: Any) -> InductiveTask:
    return InductiveTask(parse_program("\n".join(background)), *args, **kwargs)


def example(
    values: tuple[str, str] | tuple[str, str, str], positive: bool
) -> Example:
    return Example.parse(values, positive)
