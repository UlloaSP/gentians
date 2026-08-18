from ...asp.normal_coverage_solver import NormalCoverageSolver
from ...rule_generation.program import Program
from ..types import FitnessResult
from .coverage_common import coverage_score, record_fitness_metric


class CovProgram:
    def __init__(self, program: Program, solver) -> None:
        self.program = program
        self.solver = solver

    @classmethod
    def from_config(
        cls,
        program: Program,
        config: dict[str, object],
    ) -> CovProgram:
        max_as = int(config.get("max_as", 0))
        if max_as != 0:
            raise ValueError("cov_program requires max_as=0")
        extra = [
            str(value)
            for value in config.get("clingo_arguments", [])
            if not str(value).startswith("--enum-mode")
        ]
        arguments = [
            "0",
            "--enum-mode=brave",
            *extra,
        ]
        solver = NormalCoverageSolver(
            program.background,
            arguments,
            program.positive_examples,
            program.negative_examples,
        )
        return cls(program, solver)

    def __call__(self, candidate: tuple[str, ...]) -> FitnessResult:
        coverage = self.solver.extract_fixed_coverage(candidate)
        score = coverage_score(self.program, coverage)
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
                "candidate_rules": len(candidate),
            },
        )
        return FitnessResult(
            score,
            best_found,
            (coverage.pos_mask, coverage.neg_mask),
        )
