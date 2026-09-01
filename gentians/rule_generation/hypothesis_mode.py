from dataclasses import dataclass

from .arithmetic_template import ArithmeticTemplate


@dataclass(frozen=True, slots=True)
class HypothesisMode:
    id: int
    recall_group: int
    section: str
    kind: str
    name: str
    arity: int
    recall: int
    positive: bool = True
    operator: str = ""
    aggregate_function: str = ""
    tuple_arity: int = 0
    aggregate_atoms: tuple[tuple[str, int], ...] = ()
    arg_types: tuple[str, ...] = ()
    arg_directions: tuple[str, ...] = ()
    fixed_arguments: tuple[str | None, ...] = ()
    arithmetic: ArithmeticTemplate | None = None
    head_form: int | None = None
    head_position: int = 0
    head_kind: str = ""
    head_lower: int | None = None
    head_upper: int | None = None
    arg_labels: tuple[str, ...] = ()
