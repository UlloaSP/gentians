from __future__ import annotations

from dataclasses import dataclass

RuleId = int


@dataclass(frozen=True)
class Rule:
    id: RuleId
    text: str


class RuleSpace:
    def __init__(self, rules: list[Rule]) -> None:
        self.rules = rules
        self._by_id = {rule.id: rule for rule in rules}

    @classmethod
    def from_clauses(cls, clauses: list[str]) -> "RuleSpace":
        unique = sorted(dict.fromkeys(clauses))
        return cls([Rule(index, clause) for index, clause in enumerate(unique)])

    @property
    def ids(self) -> list[RuleId]:
        return [rule.id for rule in self.rules]

    @property
    def clauses(self) -> list[str]:
        return [rule.text for rule in self.rules]

    def render(self, program: list[RuleId]) -> list[str]:
        return [self._by_id[rule_id].text for rule_id in program]

    def __len__(self) -> int:
        return len(self.rules)

    def __bool__(self) -> bool:
        return bool(self.rules)
