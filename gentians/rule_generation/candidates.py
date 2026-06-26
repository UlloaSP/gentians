from dataclasses import dataclass

from ..arguments import Arguments
from ..timing import record_metric
from .placed_clause import PlacedClause
from .program import Program
from .reader import read_program
from .hypothesis_space import HypothesisSpaceGenerator


@dataclass
class CandidateRuleSpace:
    generated_clauses: "list[str]"
    placed_clause_groups: "list[list[str]]"
    placed_clauses: "list[PlacedClause]"


def read_task(filename: str) -> Program:
    return read_program(filename)


def build_candidate_rule_space(
    program: Program,
    arguments: Arguments,
) -> CandidateRuleSpace:
    placed_list, placed_list_improved = HypothesisSpaceGenerator(
        program, arguments
    ).generate()
    generated_clauses = [group[0] for group in placed_list]

    record_metric(
        "candidate",
        {
            "metric": "build_reified_hypothesis_space",
            "generated_clauses": len(generated_clauses),
            "placed_clause_groups": len(placed_list),
            "placed_candidate_rules": sum(len(group) for group in placed_list),
        },
    )

    return CandidateRuleSpace(
        generated_clauses=generated_clauses,
        placed_clause_groups=placed_list,
        placed_clauses=placed_list_improved,
    )


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
