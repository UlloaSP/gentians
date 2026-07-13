from dataclasses import dataclass


@dataclass(init=False, slots=True)
class ModeDeclaration:
    """Predicate recall and polarity declaration."""

    recall: int
    name: str
    arity: int
    positive: bool
    head: bool

    def __init__(
        self,
        values: tuple[str, str, str] | tuple[str, str, str, str],
        head: bool,
    ) -> None:
        self.recall = -1 if values[0] == "*" else int(values[0])
        self.name = values[1]
        self.arity = int(values[2])
        self.positive = len(values) != 4 or values[3] != "negative"
        self.head = head
