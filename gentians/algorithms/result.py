from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SearchResult:
    hypothesis: tuple[str, ...]
    score: float
    is_solution: bool
