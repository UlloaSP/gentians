"""Evaluation and admission caches tied to the current prepared ClauseSpace."""

import random
from collections.abc import Callable
from dataclasses import replace

from ..evaluation.result import EvaluationResult
from ..evolution.context import EvolutionContext
from ..evolution.individual import Individual
from ..hypotheses import Genome, GenomeTable, HypothesisGenerator
from ..hypotheses.types import release_int_blocks
from ..language.asp import AspProgram
from .budget import SearchBudget


class Candidates:
    """Evaluate each genome once and admit it once as an `Individual`.

    `birth_order` counts evaluations, so it is the logical age used by
    replacement. An optional budget stops evaluation at its deadline. The
    caches keep each result and birth order, not the genome: an admitted
    individual is rebuilt on demand from the genome being asked about.
    """

    def __init__(
        self, hypotheses: HypothesisGenerator, evaluator: Callable[[AspProgram], EvaluationResult],
        rng: random.Random, budget: SearchBudget | None = None,
    ) -> None:
        self.hypotheses = hypotheses
        self.evaluator = evaluator
        self.budget = budget
        self.evaluated: GenomeTable[int] = GenomeTable()
        self.results: GenomeTable[EvaluationResult] = GenomeTable()
        self.evaluations = 0
        self.context = EvolutionContext(hypotheses, rng, self.evaluate, self.results)

    def evaluate(self, genome: Genome) -> EvaluationResult:
        if self.budget is not None:
            self.budget.check()
        result = self.results.get(genome)
        if result is None:
            program = self.hypotheses.program(genome)
            # The birth order and the result outlive this call.
            release_int_blocks()
            self.evaluations += 1
            result = self.evaluator(program)
            self.results[genome] = result
            if self.budget is not None:
                self.budget.accept(self.hypotheses, genome, result)
        return result

    def admit(self, genome: Genome) -> Individual | None:
        """Return a new individual, or None when the genome was already admitted."""
        if genome in self.evaluated:
            return None
        if genome & ~self.hypotheses.available_clauses:
            raise AssertionError("candidate escaped the active clause batch")
        result = self.evaluate(genome)
        self.evaluated[genome] = self.evaluations
        return _individual(genome, result, self.evaluations)

    def individual(self, genome: Genome) -> Individual | None:
        """Return the admitted individual for a genome, admitting it if needed."""
        birth_order = self.evaluated.get(genome)
        if birth_order is None:
            return self.admit(genome)
        return _individual(genome, self.results[genome], birth_order)

    def restart(self, survivors: list[Individual]) -> None:
        """Forget every admission except the survivors'; keep the evaluations.

        A forgotten program may be admitted again, but its complete-program
        result is reused instead of solved again.
        """
        self.evaluated = GenomeTable((item.genome, item.birth_order) for item in survivors)

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
        evaluated = GenomeTable((item.genome, item.birth_order) for item in new_retained)
        results = GenomeTable(
            (item.genome, self.results[old_genome]) for old_genome, item in remapped.items()
        )
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


def _individual(genome: Genome, result: EvaluationResult, birth_order: int) -> Individual:
    return Individual(
        genome=genome, score=result.score, is_solution=result.is_solution,
        behavior=result.behavior, birth_order=birth_order,
        is_complete=result.is_complete, is_consistent=result.is_consistent,
    )
