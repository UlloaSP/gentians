"""Population lifecycle for incremental clause search."""

from ..evolution.individual import Individual
from ..evolution.metrics import record_replacement
from ..evolution.operator_types import PopulationInitializerFn, ReplacementFn
from ..hypotheses import Genome
from ..timing import net_time, phase
from .incremental_candidates import IncrementalCandidates
from .incremental_clause_pool import IncrementalClausePool
from .result import SearchResult


class IncrementalPopulation:
    def __init__(
        self, candidates: IncrementalCandidates, initializer: PopulationInitializerFn,
        replacement: ReplacementFn, size: int, replacement_name: str,
    ) -> None:
        self.candidates = candidates
        self.initializer = initializer
        self.replacement = replacement
        self.size = size
        self.replacement_name = replacement_name
        self.members: list[Individual] = []
        self.best: Individual
        self.build_seconds = 0.0

    @property
    def winner(self) -> Individual | None:
        return next((item for item in self.members if item.is_solution), None)

    def initialize(self, pool: IncrementalClausePool) -> None:
        proposals = self.initializer(self.candidates.context)
        self._activate(pool, proposals)
        for proposal in proposals:
            individual = self.candidates.admit(proposal)
            if individual is not None:
                self.members.append(individual)
                if individual.is_solution:
                    break
        self.members = self._refill(self.members)
        self._probe_constraints(self.candidates.hypotheses.available_clauses)
        if not self.members:
            raise RuntimeError("Could not initialize population")
        self.members.sort(key=lambda item: item.score, reverse=True)
        self.best = self.members[0]

    def restart(self) -> None:
        self.build_seconds = 0.0
        self.candidates.restart(self.best)
        self.members = self._refill([self.best])
        self._remember_winner()

    def renew(self, pool: IncrementalClausePool, elite_count: int) -> None:
        retained = retain_population(self.members, self.best, min(elite_count, len(self.members)))
        retained_mask = 0
        for item in retained:
            retained_mask |= item.genome
        hypotheses = self.candidates.hypotheses
        entries = [hypotheses.space.entries[i] for i in hypotheses._ids(retained_mask)]
        proposed = pool.draw(entries)
        additions = 0
        if proposed is not None:
            retained, self.best, additions = self.candidates.renew(proposed, retained, self.best)
        del hypotheses, entries, proposed
        self._activate(pool, [item.genome for item in retained])
        self.members = self._refill(retained)
        self._probe_constraints(additions)
        if not self.members:
            raise RuntimeError("Could not refill population after batch renewal")
        self._remember_winner()

    def update_best(self) -> None:
        self.members.sort(key=lambda item: item.score, reverse=True)
        if self.members[0].score > self.best.score:
            self.best = self.members[0]

    def admit_child(self, child: Individual) -> None:
        rng = self.candidates.context.rng
        if child.is_solution:
            if child.score > self.best.score:
                self.best = child
            updated = self.replacement(list(self.members), child, rng)
            self.members = (
                updated if any(item is child for item in updated)
                else [*self.members[:-1], child]
            )
        else:
            with phase("replacement"):
                before = self.members
                self.members = self.replacement(self.members, child, rng)
            record_replacement(self.replacement_name, before, self.members, child)

    def result(self) -> SearchResult:
        chosen = self.winner or self.best
        return SearchResult(
            self.candidates.hypotheses.render(chosen.genome), chosen.score, chosen.is_solution,
        )

    def _remember_winner(self) -> None:
        winner = self.winner
        if winner is not None and winner.score > self.best.score:
            self.best = winner

    def _activate(self, pool: IncrementalClausePool, seeds: list[Genome]) -> None:
        started = net_time()
        pool.activate(self.candidates.hypotheses, seeds)
        self.build_seconds = net_time() - started

    def _refill(self, seed: list[Individual]) -> list[Individual]:
        population = list(dict.fromkeys(seed))
        if any(item.is_solution for item in population):
            return population
        attempts = 0
        while len(population) < self.size and attempts < 64:
            proposals = self.initializer(self.candidates.context)
            added = False
            for proposal in proposals:
                individual = self.candidates.evaluated.get(proposal)
                if individual is None:
                    individual = self.candidates.admit(proposal)
                if individual is not None and individual not in population:
                    population.append(individual)
                    added = True
                    if individual.is_solution:
                        return population
                    if len(population) == self.size:
                        break
            attempts = 0 if added else attempts + 1
        return population

    def _probe_constraints(self, additions: Genome) -> None:
        hypotheses = self.candidates.hypotheses
        if hypotheses.clauses_by_head or not hypotheses.has_positive_examples:
            return
        additions &= hypotheses.available_clauses
        complete = max((item for item in self.members if item.is_complete),
                       key=lambda item: item.score, default=None)
        rng = self.candidates.context.rng
        for _ in range(16):
            if self.winner is not None:
                break
            base = complete.genome if complete is not None else 0
            candidate = (
                hypotheses.replace(base, rng, mutable=base | additions)
                if base.bit_count() >= hypotheses.max_clauses
                else hypotheses.append(base, rng, mutable=additions)
            )
            if candidate is None:
                break
            child = self.candidates.admit(candidate)
            if child is None:
                continue
            if child.is_complete and (complete is None or child.score > complete.score):
                complete = child
            before = self.members
            self.members = self.replacement(self.members, child, rng)
            record_replacement(self.replacement_name, before, self.members, child)
            if child.is_solution:
                if child not in self.members:
                    self.members[-1] = child
                break


def retain_population(
    population: list[Individual], champion: Individual, count: int,
) -> list[Individual]:
    retained = sorted(population, key=lambda item: item.score, reverse=True)[:count]
    if champion not in retained:
        retained[-1] = champion
    return retained
