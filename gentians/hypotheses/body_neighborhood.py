from collections import defaultdict

from ..clauses import ClauseSpace


class BodyNeighborhood:
    """One body-element edit in the existing canonical AST spelling.

    Full bodies and bodies with one element removed share posting lists. No
    pairwise graph is stored. Variable renamings are not inferred: missed
    syntactic neighbors remain reachable through global replacement.
    """

    def __init__(self, space: ClauseSpace) -> None:
        self.signatures = tuple(
            (str(entry.statement.head), tuple(sorted(map(str, entry.statement.body))))
            for entry in space.entries
        )
        self.full: dict[tuple[str, tuple[str, ...]], list[int]] = defaultdict(list)
        self.holes: dict[tuple[str, tuple[str, ...]], list[int]] = defaultdict(list)
        for clause_id, (head, body) in enumerate(self.signatures):
            self.full[head, body].append(clause_id)
            for reduced in self._deletions(body):
                self.holes[head, reduced].append(clause_id)

    @staticmethod
    def _deletions(body: tuple[str, ...]):
        # Repeated elements produce the same key; retain their multiplicity in
        # the key itself, but do not duplicate a posting for identical holes.
        for i, literal in enumerate(body):
            if i == 0 or literal != body[i - 1]:
                yield body[:i] + body[i + 1:]

    def neighbors(self, clause_id: int) -> tuple[int, ...]:
        head, body = self.signatures[clause_id]
        found = set(self.holes.get((head, body), ()))  # Add one body element.
        for reduced in self._deletions(body):
            found.update(self.full.get((head, reduced), ()))  # Remove one.
            found.update(self.holes.get((head, reduced), ()))  # Replace one.
        found.difference_update(self.full.get((head, body), ()))
        return tuple(sorted(found))
