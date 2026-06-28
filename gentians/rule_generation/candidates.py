from dataclasses import dataclass

from ..arguments import Arguments
from ..timing import profile_phase, record_metric
from .program import Program
from .reader import read_program
from .hypothesis_space import HypothesisSpaceGenerator


@dataclass
class CandidateRuleSpace:
    clauses: list[str]


def read_task(filename: str) -> Program:
    return read_program(filename)


@profile_phase("hypothesis_space")
def build_candidate_rule_space(
    program: Program,
    arguments: Arguments,
) -> CandidateRuleSpace:
    clauses = HypothesisSpaceGenerator(program, arguments).generate()

    record_metric(
        "candidate",
        {
            "metric": "build_reified_hypothesis_space",
            "generated_clauses": len(clauses),
            "candidate_rules": len(clauses),
        },
    )

    return CandidateRuleSpace(clauses=clauses)


def build_candidate_rule_space_from_file(
    filename: str,
    arguments: Arguments,
) -> "tuple[Program,CandidateRuleSpace]":
    program = read_task(filename)
    return (
        program,
        build_candidate_rule_space(
            program,
            arguments,
        ),
    )
