from dataclasses import dataclass

from ..arguments import Arguments
from .placed_clause import PlacedClause
from .program import Program
from .reader import read_program
from .sampler import ProgramSampler
from .sampled_clause import Clause
from .variable_placement import VariablePlacer


@dataclass
class CandidateRuleSpace:
    sampled_stubs: "list[Clause]"
    sampled_clauses: "list[str]"
    placed_clause_groups: "list[list[str]]"
    placed_clauses: "list[PlacedClause]"


def read_task(filename: str) -> Program:
    return read_program(filename)


def create_program_sampler(program: Program, arguments: Arguments) -> ProgramSampler:
    return ProgramSampler(
        program.language_bias_head,
        program.language_bias_body,
        arguments,
    )


def sample_rule_stubs(
    sampler: ProgramSampler,
    arguments: Arguments,
    best_stub_for_next_round: "list[Clause]",
) -> "list[Clause]":
    cls = sampler.sample_clauses_stub(arguments.clauses_to_sample)

    # add the best from the previous rounds
    cls.extend(best_stub_for_next_round)

    return cls


def instantiate_sampled_clauses(sampled_stubs: "list[Clause]") -> "list[str]":
    # Step 1: remove duplicates
    instantiated_clauses = [c.instantiated for c in sampled_stubs]
    return [item for sublist in instantiated_clauses for item in sublist]


def place_candidate_rules(
    placer: VariablePlacer,
    sampled_clauses: "list[str]",
) -> "tuple[list[list[str]], list[PlacedClause]]":
    # Step 2: place the variables
    # This is THE bottleneck: generation of all the
    # possible locations, which are #n_vars^#n_pos in the
    # worst case
    placed_list: "list[list[str]]" = placer.place_variables_list_of_clauses(
        sampled_clauses
    )

    placed_list_improved: "list[PlacedClause]" = list(map(PlacedClause, placed_list))

    return placed_list, placed_list_improved


def build_candidate_rule_space(
    program: Program,
    arguments: Arguments,
    sampler: ProgramSampler,
    placer: VariablePlacer,
    best_stub_for_next_round: "list[Clause]",
) -> CandidateRuleSpace:
    cls = sample_rule_stubs(sampler, arguments, best_stub_for_next_round)
    sampled_clauses = instantiate_sampled_clauses(cls)
    placed_list, placed_list_improved = place_candidate_rules(placer, sampled_clauses)

    return CandidateRuleSpace(
        sampled_stubs=cls,
        sampled_clauses=sampled_clauses,
        placed_clause_groups=placed_list,
        placed_clauses=placed_list_improved,
    )


def build_candidate_rule_space_from_file(
    filename: str,
    arguments: Arguments,
    best_stub_for_next_round: "list[Clause]",
) -> "tuple[Program,CandidateRuleSpace]":
    program = read_task(filename)
    sampler = create_program_sampler(program, arguments)
    placer = VariablePlacer(arguments)
    return (
        program,
        build_candidate_rule_space(
            program,
            arguments,
            sampler,
            placer,
            best_stub_for_next_round,
        ),
    )
