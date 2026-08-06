from dataclasses import dataclass


@dataclass(init=False, slots=True)
class ModeDeclaration:
    """Predicate recall and polarity declaration."""

    recall: int
    name: str
    arity: int
    positive: bool
    head: bool
    directions: tuple[str, ...]

    def __init__(
        self,
        values: tuple[str, ...],
        head: bool,
    ) -> None:
        self.recall = -1 if values[0] == "*" else int(values[0])
        self.name = values[1]
        self.arity = int(values[2])
        self.positive = head or values[3] != "negative"
        self.head = head
        direction_index = 3 if head else 4
        self.directions = (
            _directions(values[direction_index], self.arity)
            if len(values) > direction_index
            else ()
        )
        if not self.positive and "output" in self.directions:
            raise ValueError("negative body modes cannot produce output variables")


def _directions(raw: str, arity: int) -> tuple[str, ...]:
    value = raw.strip()
    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1]
    aliases = {"+": "input", "-": "output", "?": "any"}
    directions = tuple(
        aliases.get(item.strip(), item.strip()) for item in value.split(",")
    )
    if len(directions) != arity or any(
        direction not in {"input", "output", "any"} for direction in directions
    ):
        raise ValueError(f"invalid mode directions for arity {arity}: {raw}")
    return directions
