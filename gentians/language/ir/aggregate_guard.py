from dataclasses import dataclass

from .term_template import TermTemplate


@dataclass(frozen=True, slots=True)
class AggregateGuard:
    operator: str
    term: TermTemplate

    def concretizations(
        self, constants: dict[str, tuple[str, ...]]
    ) -> tuple["AggregateGuard", ...]:
        return tuple(
            AggregateGuard(self.operator, term)
            for term in self.term.concretizations(constants)
        )
