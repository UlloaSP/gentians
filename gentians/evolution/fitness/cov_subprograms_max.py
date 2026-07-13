from __future__ import annotations

import math

from .coverage_common import cached_fitness, record_fitness_metric
from ...asp.coverage import Coverage
from ...asp import create_coverage_solver
from ...rule_generation.program import Program


class CovSubprogramsMax:
    def __init__(self, program: Program, solver, grounding: str) -> None:
        self.program = program
        self.solver = solver
        self.grounding = grounding
        self.cache = {}

    @classmethod
    def from_config(
        cls,
        program: Program,
        config: dict[str, object],
        max_program_clauses: int,
        rule_space: tuple[str, ...] | None,
    ) -> "CovSubprogramsMax":
        obsolete = {"scope", "aggregation"}.intersection(config)
        if obsolete:
            raise ValueError(
                f"Obsolete fitness options for cov_subprograms_max: {sorted(obsolete)}"
            )
        grounding = str(config.get("grounding", "normal"))
        max_as = int(config.get("max_as", 0))
        if grounding not in {"normal", "externals", "assumptions"}:
            raise ValueError(f"Unknown coverage grounding: {grounding}")
        if grounding != "normal" and max_as != 0:
            raise ValueError("Pre-grounded coverage requires max_as=0")
        arguments = [
            str(max_as),
            "--project",
            *[str(value) for value in config.get("clingo_arguments", [])],
        ]
        solver = create_coverage_solver(
            grounding,
            program.background,
            arguments,
            program.positive_examples,
            program.negative_examples,
            rule_space=rule_space,
            max_program_clauses=max_program_clauses,
        )
        return cls(program, solver, grounding)

    def __call__(
        self, candidate: tuple[str, ...]
    ) -> tuple[float, bool, tuple[str, ...] | None]:
        return cached_fitness(self.cache, candidate, lambda value: self._evaluate(value))

    def _evaluate(
        self, candidate: tuple[str, ...]
    ) -> tuple[float, bool, tuple[str, ...] | None]:
        coverages = self.solver.extract_subset_coverage(candidate)
        if not coverages:
            self._record(candidate, Coverage([], []), -2000.0, False, 0, len(candidate))
            return -2000.0, False, None

        ranked = [
            (self._score(coverage), selected, coverage)
            for selected, coverage in coverages.items()
        ]
        score = max(item[0] for item in ranked)
        perfect = [item for item in ranked if self._is_perfect(item[2])]
        selected = (
            min(perfect, key=lambda item: (len(item[1]), item[1]))
            if perfect
            else min(ranked, key=lambda item: (-item[0], len(item[1]), item[1]))
        )
        selected_program = (
            tuple(candidate[index] for index in selected[1]) if perfect else None
        )
        metric_program = tuple(candidate[index] for index in selected[1])
        self._record(
            metric_program,
            selected[2],
            score,
            bool(perfect),
            len(ranked),
            len(candidate),
        )
        return score, bool(perfect), selected_program

    def _score(self, coverage: Coverage) -> float:
        positive_rate = (
            coverage.pos_mask.bit_count() / len(self.program.positive_examples)
            if self.program.positive_examples
            else 0.0
        )
        negative_rate = (
            coverage.neg_mask.bit_count() / len(self.program.negative_examples)
            if self.program.negative_examples
            else 0.0
        )
        return math.exp((positive_rate - negative_rate) * 10)

    def _is_perfect(self, coverage: Coverage) -> bool:
        return (
            coverage.pos_mask.bit_count() == len(self.program.positive_examples)
            and coverage.neg_mask == 0
        )

    def _record(
        self,
        metric_program: tuple[str, ...],
        coverage: Coverage,
        score: float,
        best_found: bool,
        evaluated: int,
        candidate_rules: int,
    ) -> None:
        record_fitness_metric(
            "cov_subprograms_max",
            self.program,
            metric_program,
            coverage,
            score,
            best_found,
            {
                "grounding": self.grounding,
                "evaluated_subprograms": evaluated,
                "candidate_rules": candidate_rules,
            },
        )
