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

    # Logging level: 0 quiet, 1 sampled clauses, 2 variable placements.
    verbosity: int = 0

    # Maximum number of variables allowed in one generated rule.
    max_variables: int = 3

    # Maximum rule length: head atoms + body literals.
    max_depth: int = 3

    # Sampling probability of adding one more literal to current clause.
    prob_increase: float = 0.5

    # Maximum number of atoms allowed in a disjunctive head.
    disjunctive_head_length: int = 1

    # Number of clause stubs sampled at each sampling step.
    clauses_to_sample: int = 1000

    # Allow aggregate literals whose variables are not fully balanced.
    unbalanced_aggregates: bool = False

    # Maximum answer sets generated while checking candidates.
    max_as: int = 5000

    # Maximum number of clauses in one candidate program.
    clauses_per_individual: int = 6

    # Maximum number of outer sample/evolution cycles.
    iterations: int = 100

    # Number of individuals in genetic population.
    population_size: int = 50

    # Genetic algorithm iterations per outer cycle.
    iterations_genetic: int = 2000

    # Probability of mutating one individual during evolution.
    mutation_probability: float = 0.2

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

    # Run under cProfile and print cumulative stats.
    profile: bool = False
