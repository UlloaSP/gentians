class RuleSpace:
    def __init__(self, clauses: list[str]) -> None:
        self.clauses = clauses

    @classmethod
    def from_clauses(cls, clauses: list[str]) -> "RuleSpace":
        return cls(sorted(dict.fromkeys(clauses)))

    def __len__(self) -> int:
        return len(self.clauses)

    def __bool__(self) -> bool:
        return bool(self.clauses)
