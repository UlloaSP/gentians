"""Population members, champion and every change applied to them."""

from ..evolution.individual import Individual
from ..evolution.metrics import record_replacement
from ..evolution.operator_types import PopulationInitializerFn, ReplacementFn
from ..hypotheses import Genome
from ..timing import phase
from .candidates import Candidates
from .result import SearchResult


class Population:
    """Members of one search and the best individual found so far.

    `best` may have left `members`. Ranking operations keep members sorted by
    descending score. New members are admitted through `candidates`, so each
    genome is evaluated once.
    """

    def __init__(
        self, candidates: Candidates, initializer: PopulationInitializerFn,
        replacement: ReplacementFn, replacement_name: str, size: int,
    ) -> None:
        self.candidates = candidates
        self.initializer = initializer
        self.replacement = replacement
        self.replacement_name = replacement_name
        self.size = size
        self.members: list[Individual] = []
        self.best: Individual

    @property
    def winner(self) -> Individual | None:
        return next((item for item in self.members if item.is_solution), None)

    def seed(self, proposals: list[Genome]) -> None:
        """Admit initial proposals in order, stopping at the first solution."""
        for proposal in proposals:
            individual = self.candidates.admit(proposal)
            if individual is not None:
                self.members.append(individual)
                if individual.is_solution:
                    break

    def refill(self) -> None:
        self.members = self.fill(self.members)

    def rank(self) -> None:
        """Sort a freshly initialized population and take its champion."""
        if not self.members:
            raise RuntimeError("Could not initialize population")
        self.members.sort(key=lambda item: item.score, reverse=True)
        self.best = self.members[0]

    def restart(self, survivors: list[Individual], *, keep_members: bool = False) -> None:
        """Resample every member except the survivors.

        With `keep_members`, current members fill the slots that sampling
        cannot, so the population keeps its size.
        """
        previous = self.members
        self.members = self.fill(survivors)
        if keep_members and self.winner is None:
            for individual in previous:
                if len(self.members) == self.size:
                    break
                if all(item.genome != individual.genome for item in self.members):
                    self.members.append(individual)
        self.members.sort(key=lambda item: item.score, reverse=True)
        self.remember_winner()

    def update_best(self) -> None:
        self.members.sort(key=lambda item: item.score, reverse=True)
        if self.members[0].score > self.best.score:
            self.best = self.members[0]

    def admit_child(self, child: Individual) -> None:
        rng = self.candidates.context.rng
        if not child.is_solution:
            with phase("replacement"):
                before = self.members
                self.members = self.replacement(self.members, child, rng)
            record_replacement(self.replacement_name, before, self.members, child)
            return
        # A solution always joins the population, even if replacement rejects it.
        if child.score > self.best.score:
            self.best = child
        updated = self.replacement(list(self.members), child, rng)
        self.members = (
            updated if any(item is child for item in updated)
            else [*self.members[:-1], child]
        )

    def result(self) -> SearchResult:
        chosen = self.winner or self.best
        return SearchResult(
            self.candidates.hypotheses.render(chosen.genome), chosen.score, chosen.is_solution,
        )

    def remember_winner(self) -> None:
        winner = self.winner
        if winner is not None and winner.score > self.best.score:
            self.best = winner

    def fill(self, seed: list[Individual]) -> list[Individual]:
        """Extend `seed` with novel sampled individuals up to the population size.

        Stops early at a solution or after 64 consecutive samples add nothing.
        """
        population = list(dict.fromkeys(seed))
        if any(item.is_solution for item in population):
            return population
        attempts = 0
        while len(population) < self.size and attempts < 64:
            added = False
            for proposal in self.initializer(self.candidates.context):
                individual = self.candidates.individual(proposal)
                if individual is None or any(
                    item.genome == individual.genome for item in population
                ):
                    continue
                population.append(individual)
                added = True
                if individual.is_solution:
                    return population
                if len(population) == self.size:
                    break
            attempts = 0 if added else attempts + 1
        return population
