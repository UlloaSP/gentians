from dataclasses import dataclass

import clingo
from clingo import ast

from ..language.asp import AspProgram


@dataclass(slots=True)
class PreparedClauses:
    """A control grounded with guarded clauses, solved once per candidate."""

    ctl: clingo.Control
    index: dict[ast.AST, int]
    # One negative guard literal per clause; a candidate flips its own.
    excluded: list[int]
    clauses: AspProgram
    # Seconds and phase of the grounding, until its metrics are recorded.
    grounding: tuple[float, str] | None
