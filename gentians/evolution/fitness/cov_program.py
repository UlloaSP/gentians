from __future__ import annotations

import math

from .coverage_common import cached_fitness, record_fitness_metric
from ...asp.coverage import Coverage
from ...asp import create_coverage_solver
from ...rule_generation.program import Program


class CovProgram:
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
    ) -> "CovProgram":
        obsolete = {"scope", "aggregation"}.intersection(config)
        if obsolete:
            raise ValueError(
                f"Obsolete fitness options for cov_program: {sorted(obsolete)}"
            )
        grounding = str(config.get("grounding", "normal"))
        max_as = int(config.get("max_as", 0))
        if grounding not in {"normal", "externals", "assumptions"}:
            raise ValueError(f"Unknown coverage grounding: {grounding}")
        if grounding != "normal" and max_as != 0:
            raise ValueError("Pre-grounded coverage requires max_as=0")
        arguments = [
            str(max_as),
            *[
                str(value)
                for value in config.get("clingo_arguments", ["--enum-mode=brave"])
            ],
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
    ) -> tuple[float, bool, tuple[str, ...]]:
        return cached_fitness(
            self.cache, candidate, lambda value: self._evaluate(value)
        )

    def _evaluate(
        self, candidate: tuple[str, ...]
    ) -> tuple[float, bool, tuple[str, ...]]:
        coverage = self.solver.extract_fixed_coverage(candidate)
        score = self._score(coverage)
        best_found = (
            coverage.pos_mask.bit_count() == len(self.program.positive_examples)
            and coverage.neg_mask == 0
        )
        record_fitness_metric(
            "cov_program",
            self.program,
            candidate,
            coverage,
            score,
            best_found,
            {
                "grounding": self.grounding,
                "evaluated_subprograms": 1,
                "candidate_rules": len(candidate),
            },
        )
        return score, best_found, candidate

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
