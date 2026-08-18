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

    # Seed used by evolutionary operators.
    random_seed: int | None = None

    # Number of genetic generations. 0 means unlimited.
    iterations_genetic: int = 0

    # Fitness operator config.
    fitness: dict[str, object] = field(
        default_factory=lambda: {
            # cov_subprograms_mean, cov_subprograms_max, cov_program, or trigram_cov.
            "name": "cov_subprograms_mean",
            # Maximum answer sets requested from Clingo per coverage check. 0 means all.
            "max_as": 0,
            # Clingo CLI arguments used by the fitness evaluator.
            "clingo_arguments": [],
        }
    )

    # Parent selection operator config.
    selection: dict[str, object] = field(
        default_factory=lambda: {
            # tournament or behavior_tournament.
            "name": "tournament",
            # Population percentage sampled per tournament, expressed in (0, 1].
            "tournament_percentage": 0.1,
            # Probability of picking the fittest candidate; tournament only.
            "prob_selecting_fittest": 1.0,
        }
    )

    # Crossover operator config.
    crossover: dict[str, object] = field(
        default_factory=lambda: {
            # Crossover implementation.
            "name": "set_mix",
            # Probability of applying crossover to selected parents.
            "probability": 0.6,
        }
    )

    # Mutation operator config.
    mutation: dict[str, object] = field(
        default_factory=lambda: {
            # random_group or structural_neighbor.
            "name": "random_group",
            # Probability of mutating an offspring.
            "probability": 0.9,
            # Probability of ignoring structural neighbors and jumping randomly.
            "random_jump_probability": 0.0,
        }
    )

    # Population initialization operator config.
    population: dict[str, object] = field(
        default_factory=lambda: {
            # Population initialization implementation.
            "name": "random",
            # Number of individuals kept in the population.
            "size": 10,
        }
    )

    # Population replacement operator config.
    replacement: dict[str, object] = field(
        default_factory=lambda: {
            # Replacement implementation.
            "name": "oldest_or_worst",
            # Probability of replacing the oldest individual instead of the worst.
            "prob_replacing_oldest": 0.1,
            # Prefer behavior diversity when scores tie.
            "behavior_tiebreak": False,
        }
    )

    # Hypothesis-space candidate-source details.
    hypothesis_space: dict[str, object] = field(
        default_factory=lambda: {
            # Extra Clingo CLI arguments used to enumerate generated clauses.
            "clingo_arguments": ["--parallel-mode=5,split"],
        }
    )
