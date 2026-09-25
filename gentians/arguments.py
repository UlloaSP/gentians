from dataclasses import dataclass, field


@dataclass
class Arguments:
    """SDK config for GENTIANS.

    Create this class in Python and pass it to `gentians.main(arguments)`.
    No terminal parsing happens here.
    """

    # Path to a task file or a directory containing bk.lp, exs.lp, and bias.lp.
    filename: str | None = None

    # Seed used by evolutionary operators.
    random_seed: int | None = None

    # Number of genetic generations. 0 means unlimited.
    iterations_genetic: int = 0

    # Candidate evaluation config.
    evaluation: dict[str, object] = field(
        default_factory=lambda: {
            # Whole-program coverage score.
            "scoring": "cov_program",
            # Clingo CLI arguments used to obtain candidate coverage.
            "clingo_arguments": [],
            # Reuse exact coverage bounds under pure integrity-constraint edits.
            "constraint_inheritance": True,
        }
    )

    # Parent selection operator config.
    selection: dict[str, object] = field(
        default_factory=lambda: {
            # tournament or lexicase.
            "name": "lexicase",
            # Population percentage sampled per tournament, expressed in (0, 1].
            "tournament_percentage": 0.1,
            # Probability of picking the fittest candidate; tournament only.
            "prob_selecting_fittest": 1.0,
        }
    )

    # Crossover operator config.
    crossover: dict[str, object] = field(
        default_factory=lambda: {
            # Set crossover over clauses.
            "name": "set_mix",
            # Probability of applying crossover to selected parents.
            "probability": 1.0,
        }
    )

    # Mutation operator config.
    mutation: dict[str, object] = field(
        default_factory=lambda: {
            # Unified dependency-block mutation; factory remains the entry point.
            "name": "random_group",
            # Probability of mutating an offspring.
            "probability": 0.9,
            # Per replacement attempt: allow a different signed head signature.
            "random_jump_probability": 0.1,
            # Per complete-candidate mutation: try deleting a headed block.
            "complete_generator_removal_probability": 0.1,
        }
    )

    # Population initialization operator config.
    population: dict[str, object] = field(
        default_factory=lambda: {
            # Random initialization of valid programs.
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
        }
    )

    # Population restart config.
    restart: dict[str, object] = field(
        default_factory=lambda: {
            # Restart from the champion when the best score stops improving.
            "name": "stagnation",
            # Generations without a better champion before restarting.
            "generations": 100,
        }
    )

    # Full-space steady-state search or bounded incremental clause search.
    algorithm: str = "steady_state"
    incremental: dict[str, object] = field(
        default_factory=lambda: {
            "batch_size": 128,
            "archive_size": 8192,
            "epoch_generations": 50,
            "elite_count": 10,
            "time_limit_seconds": None,
        }
    )

    # Clause-generation solver details.
    clause_generation: dict[str, object] = field(
        default_factory=lambda: {
            # Extra Clingo CLI arguments used to enumerate generated clauses.
            "clingo_arguments": ["--parallel-mode=5,split"],
        }
    )
