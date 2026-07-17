from __future__ import annotations

from .coverage_common import coverage_score, record_fitness_metric
from ...asp.coverage import Coverage
from ...asp.normal_coverage_solver import NormalCoverageSolver
from ...rule_generation.program import Program
from ...rule_generation.rule_space import RuleSpace


class CovSubprogramsMean:
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
    ) -> "CovSubprogramsMean":
        obsolete = {"scope", "aggregation", "grounding"}.intersection(config)
        if obsolete:
            raise ValueError(
                f"Obsolete fitness options for cov_subprograms_mean: {sorted(obsolete)}"
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
    ) -> tuple[float, bool, tuple[str, ...] | None]:
        return self._evaluate(candidate)

    def _evaluate(
        self, candidate: tuple[str, ...]
    ) -> tuple[float, bool, tuple[str, ...] | None]:
        coverages = self.solver.extract_subset_coverage(candidate)
        if not coverages:
            self._record(candidate, -2000.0, False, 0, 0.0, 0.0)
            return -2000.0, False, None

        ranked = [
            (coverage_score(self.program, coverage), selected, coverage)
            for selected, coverage in coverages.items()
        ]
        score = sum(item[0] for item in ranked) / len(ranked)
        perfect = [item for item in ranked if self._is_perfect(item[2])]
        selected_program = None
        if perfect:
            selected = min(perfect, key=lambda item: (len(item[1]), item[1]))[1]
            selected_program = tuple(candidate[index] for index in selected)
        self._record(
            candidate,
            score,
            bool(perfect),
            len(ranked),
            sum(item[2].pos_mask.bit_count() for item in ranked) / len(ranked),
            sum(item[2].neg_mask.bit_count() for item in ranked) / len(ranked),
        )
        return score, bool(perfect), selected_program

    def _is_perfect(self, coverage: Coverage) -> bool:
        return (
            coverage.pos_mask.bit_count() == len(self.program.positive_examples)
            and coverage.neg_mask == 0
        )

    def _record(
        self,
        candidate: tuple[str, ...],
        score: float,
        best_found: bool,
        evaluated: int,
        covered_positive: float,
        covered_negative: float,
    ) -> None:
        record_fitness_metric(
            "cov_subprograms_mean",
            self.program,
            candidate,
            Coverage([], []),
            score,
            best_found,
            {
                "evaluated_subprograms": evaluated,
                "candidate_rules": len(candidate),
                "coverage_models_positive_mask": "",
                "coverage_models_negative_mask": "",
                "covered_positive": covered_positive,
                "covered_negative": covered_negative,
            },
        )
