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

    # Number of candidate clauses generated at each hypothesis-space step.
    clauses_to_sample: int = 1000

    # Allow aggregate literals whose variables are not fully balanced.
    unbalanced_aggregates: bool = False

    # Maximum number of clauses in one candidate program.
    clauses_per_individual: int = 6

    # Genetic algorithm iterations.
    iterations_genetic: int = 5000

    # Fitness operator config.
    fitness: dict[str, object] = field(
        default_factory=lambda: {
            # Fitness function implementation.
            "name": "coverage_exp_mean",
            # Maximum answer sets requested from Clingo per coverage check.
            "max_as": 10000,
            # Clingo CLI arguments used by the fitness evaluator.
            "clingo_arguments": ["--project"],
            # Score assigned when no coverage signal can be computed.
            "empty_score": -2000,
        }
    )

    # Parent selection operator config.
    selection: dict[str, object] = field(
        default_factory=lambda: {
            # Parent selection implementation.
            "name": "tournament",
            # Number of candidates sampled for each tournament.
            "tournament_size": 12,
            # Probability of picking the fittest candidate in the tournament.
            "prob_selecting_fittest": 0.9,
        }
    )

    # Crossover operator config.
    crossover: dict[str, object] = field(
        default_factory=lambda: {
            # Crossover implementation.
            "name": "one_point",
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
            "size": 50,
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
        }
    )

    # Enable choice-rule generation.
    cr: bool = False

    # Aggregate specs, e.g. ["sum(d/2)", "count(d/2)"].
    aggregates: list[str] = field(default_factory=list)

    # Comparison operators: lt, leq, gt, geq, eq, neq. Repeat to increase recall.
    comparison_operators: list[str] = field(default_factory=list)

    # Arithmetic operators: add, sub, mul, div, abs. Repeat to increase recall.
    arithmetic_operators: list[str] = field(default_factory=list)

    # Number of invented predicates. 0 disables predicate invention.
    predicate_invention: int = 0

    # Automatic language-bias recall. 0 disables it; negative recall allows negation.
    automatic_language_bias: int = 0
