from __future__ import annotations

from .coverage_common import coverage_score, record_fitness_metric
from ...asp.coverage import Coverage
from ...asp.normal_coverage_solver import NormalCoverageSolver
from ...rule_generation.program import Program
from ...rule_generation.rule_space import RuleSpace
from ..types import FitnessResult


class CovSubprogramsMax:
    def __init__(self, program: Program, solver) -> None:
        self.program = program
        self.solver = solver

    @classmethod
    def from_config(
        cls,
        program: Program,
        config: dict[str, object],
        max_program_clauses: int,
        rule_space: RuleSpace,
    ) -> "CovSubprogramsMax":
        obsolete = {"scope", "aggregation", "grounding"}.intersection(config)
        if obsolete:
            raise ValueError(
                f"Obsolete fitness options for cov_subprograms_max: {sorted(obsolete)}"
            )
        max_as = int(config.get("max_as", 0))
        if max_as != 0:
            raise ValueError("subset coverage requires max_as=0")
        arguments = [
            str(max_as),
            "--project",
            *[str(value) for value in config.get("clingo_arguments", [])],
        ]
        solver = NormalCoverageSolver(
            program.background,
            arguments,
            program.positive_examples,
            program.negative_examples,
        )
        return cls(program, solver)

    def __call__(
        self, candidate: tuple[str, ...]
    ) -> FitnessResult:
        return self._evaluate(candidate)

    def _evaluate(
        self, candidate: tuple[str, ...]
    ) -> FitnessResult:
        coverages = self.solver.extract_subset_coverage(candidate)
        if not coverages:
            self._record(candidate, Coverage([], []), -2000.0, False, 0, len(candidate))
            return FitnessResult(-2000.0, False, None, (0, 0))

        ranked = [
            (coverage_score(self.program, coverage), selected, coverage)
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
        return FitnessResult(
            score,
            bool(perfect),
            selected_program,
            (selected[2].pos_mask, selected[2].neg_mask),
        )

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
                "evaluated_subprograms": evaluated,
                "candidate_rules": candidate_rules,
            },
        )
