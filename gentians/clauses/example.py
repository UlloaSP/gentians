from dataclasses import dataclass


@dataclass(init=False, slots=True)
class Example:
    """Included, excluded, and contextual atoms from one example."""

    included: str
    excluded: str
    context: str
    positive: bool

    def __init__(self, values: tuple[str, str] | tuple[str, str, str], positive: bool) -> None:
        self.included = values[0]
        self.excluded = values[1]
        self.context = values[2] if len(values) == 3 else ""
        self.positive = positive
