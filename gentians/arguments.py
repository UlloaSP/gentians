from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Arguments:
    """SDK config for GENTIANS.

    Create this class in Python and pass it to `gentians.main(arguments)`.
    No terminal parsing happens here.
    """

    # Path to a task file with background, examples, and language bias.
    filename: str | None = None

    # Maximum number of variables allowed in one generated rule.
    max_variables: int = 3

    # Maximum rule length: head atoms + body literals.
    max_depth: int = 3

    # Maximum number of atoms allowed in a disjunctive head.
    disjunctive_head_length: int = 1

    # Maximum number of candidate clauses generated from the hypothesis space.
    # 0 means all.
    max_candidate_clauses: int = 0

    # Maximum number of clauses in one candidate program.
    max_program_clauses: int = 6

    # Genetic algorithm iterations.
    iterations_genetic: int = 1000

    # Fitness operator config.
    fitness: dict[str, object] = field(
        default_factory=lambda: {
            # Fitness function implementation.
            "name": "coverage_fixed",
            # Maximum answer sets requested from Clingo per coverage check. 0 means all.
            "max_as": 0,
            # Clingo CLI arguments used by the fitness evaluator.
            "clingo_arguments": ["--enum-mode=brave"],
            # Fixed-program score penalty per selected rule.
            "size_penalty": 0.01,
            # Fixed-program score penalty per body literal.
            "literal_penalty": 0.002,
            # Fixed-program score penalty per cheap syntactic redundancy.
            "redundancy_penalty": 0.01,
        }
    )

    # Parent selection operator config.
    selection: dict[str, object] = field(
        default_factory=lambda: {
            # Parent selection implementation.
            "name": "tournament",
            # Number of candidates sampled for each tournament.
            "tournament_size": 25,
            # Probability of picking the fittest candidate in the tournament.
            "prob_selecting_fittest": 0.9,
        }
    )

    # Crossover operator config.
    crossover: dict[str, object] = field(
        default_factory=lambda: {
            # Crossover implementation.
            "name": "set_mix",
            # Probability of applying crossover to selected parents.
            "probability": 0.7,
        }
    )

    # Mutation operator config.
    mutation: dict[str, object] = field(
        default_factory=lambda: {
            # Mutation implementation.
            "name": "random_group",
            # Probability of mutating an offspring.
            "probability": 0.2,
        }
    )

    # Population initialization operator config.
    population: dict[str, object] = field(
        default_factory=lambda: {
            # Population initialization implementation.
            "name": "random",
            # Number of individuals kept in the population.
            "size": 100,
        }
    )

    # Population replacement operator config.
    replacement: dict[str, object] = field(
        default_factory=lambda: {
            # Replacement implementation.
            "name": "oldest_or_worst",
            # Probability of replacing the oldest individual instead of the worst.
            "prob_replacing_oldest": 0.5,
        }
    )

    # Hypothesis-space solver config.
    hypothesis_space: dict[str, object] = field(
        default_factory=lambda: {
            # Extra Clingo CLI arguments used to enumerate generated clauses.
            "clingo_arguments": [],
            # Whether sampled rules may recursively use the target predicate.
            "enable_recursion": False,
            # Predicate specs whose repeated variable args are invalid, e.g. ["edge/2"].
            "irreflexive": [],
            # Drop duplicated symmetric comparisons such as V0!=V1,V1!=V0.
            "prune_redundant_comparisons": True,
            # Drop algebraically implied add/sub literals.
            "prune_arithmetic_identities": True,
        }
    )


