"""Evaluation and admission caches tied to the current prepared ClauseSpace."""

import random
from collections.abc import Callable
from dataclasses import replace

from ..evaluation.result import EvaluationResult
from ..evolution.context import EvolutionContext
from ..evolution.individual import Individual
from ..hypotheses import Genome, HypothesisGenerator
from ..language.asp import AspProgram
from .budget import SearchBudget


class Candidates:
    """Evaluate each genome once and admit it once as an `Individual`.

    `birth_order` counts evaluations, so it is the logical age used by
    replacement. An optional budget stops evaluation at its deadline.
    """

    def __init__(
        self, hypotheses: HypothesisGenerator, evaluator: Callable[[AspProgram], EvaluationResult],
        rng: random.Random, budget: SearchBudget | None = None,
    ) -> None:
        self.hypotheses = hypotheses
        self.evaluator = evaluator
        self.budget = budget
        self.evaluated: dict[Genome, Individual] = {}
        self.results: dict[Genome, EvaluationResult] = {}
        self.evaluations = 0
        self.context = EvolutionContext(hypotheses, rng, self.evaluate, self.results)

    def evaluate(self, genome: Genome) -> EvaluationResult:
        if self.budget is not None:
            self.budget.check()
        if genome not in self.results:
            self.evaluations += 1
            result = self.evaluator(self.hypotheses.program(genome))
            self.results[genome] = result
            if self.budget is not None:
                self.budget.accept(self.hypotheses, genome, result)
        return self.results[genome]

    def admit(self, genome: Genome) -> Individual | None:
        """Return a new individual, or None when the genome was already admitted."""
        if genome in self.evaluated:
            return None
        if genome & ~self.hypotheses.available_clauses:
            raise AssertionError("candidate escaped the active clause batch")
        result = self.evaluate(genome)
        individual = Individual(
            genome=genome, score=result.score, is_solution=result.is_solution,
            behavior=result.behavior, birth_order=self.evaluations,
            is_complete=result.is_complete, is_consistent=result.is_consistent,
        )
        self.evaluated[genome] = individual
        return individual

    def individual(self, genome: Genome) -> Individual | None:
        """Return the admitted individual for a genome, admitting it if needed."""
        return self.evaluated.get(genome) or self.admit(genome)

    def restart(self, survivors: list[Individual]) -> None:
        """Forget every evaluation except those of the restart survivors."""
        self.evaluated = {item.genome: item for item in survivors}
        self.results = {item.genome: self.results[item.genome] for item in survivors}
        self.context = EvolutionContext(
            self.hypotheses, self.context.rng, self.evaluate, self.results,
        )

    def renew(
        self, hypotheses: HypothesisGenerator, retained: list[Individual], champion: Individual,
    ) -> tuple[list[Individual], Individual, Genome]:
        """Adopt a new space only after all retained programs have been recoded.

        The champion must be retained and all retained clauses must exist in
        the new prepared space. No evaluation or random draw occurs. Scores,
        behavior and age survive; caches for discarded programs do not.
        """
        remapped = {
            item.genome: replace(
                item, genome=hypotheses.encode(self.hypotheses.render(item.genome)),
            )
            for item in retained
        }
        new_champion = remapped[champion.genome]
        new_retained = list(remapped.values())
        evaluated = {item.genome: item for item in new_retained}
        results = {
            item.genome: self.results[old_genome]
            for old_genome, item in remapped.items()
        }
        # Only constraint-only spaces use the extra probes after renewal.
        additions = (
            sum(1 << index for index, clause in enumerate(hypotheses.clauses)
                if clause not in self.hypotheses.clause_ids)
            if not hypotheses.clauses_by_head else 0
        )
        context = EvolutionContext(hypotheses, self.context.rng, self.evaluate, results)
        self.hypotheses, self.context = hypotheses, context
        self.evaluated, self.results = evaluated, results
        return new_retained, new_champion, additions
