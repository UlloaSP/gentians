from dataclasses import dataclass, field


@dataclass
class Arguments:
    """SDK config for GENTIANS.

    Create this class in Python and pass it to `gentians.main(arguments)`.
    No terminal parsing happens here.
    """

    # Path to a task file with background, examples, and language bias.
    filename: str | None = None

    # Seed used by evolutionary operators.
    random_seed: int | None = None

    # Number of genetic generations. 0 means unlimited.
    iterations_genetic: int = 0

    # Candidate evaluation config.
    evaluation: dict[str, object] = field(
        default_factory=lambda: {
            # cov_program or cov_balanced.
            "scoring": "cov_program",
            # Clingo CLI arguments used to obtain candidate coverage.
            "clingo_arguments": [],
            # Reuse exact coverage bounds under pure integrity-constraint edits.
            # Opt-in until end-to-end measurements justify the extra bookkeeping.
            "constraint_inheritance": False,
            # Diagnose incomplete candidates without learned constraints.
            "constraint_diagnosis": False,
        }
    )

    # Parent selection operator config.
    selection: dict[str, object] = field(
        default_factory=lambda: {
            # tournament, behavior_tournament, lexicase, or reproductive_lexicase.
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
            # Crossover implementation.
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
            # Extra proposals after a processed genome; experimental, off by default.
            "duplicate_retries": 0,
            # Try one body-literal edit before global replacement; opt-in.
            "body_local_probability": 0.0,
            # Disable only for controlled policy ablations, not language legality.
            "completeness_guidance": True,
            # Opt-in: original random edits for pools containing only constraints.
            # Allows constraint additions even when positives remain uncovered.
            "constraint_only_random": False,
            # Prefer diagnosed repair on already classified mutation inputs.
            "repair_probability": 0.0,
        }
    )

    # Population initialization operator config.
    population: dict[str, object] = field(
        default_factory=lambda: {
            # random or structural_diverse, which samples without extra fitness calls.
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
            # Reserve discovered complete candidates; experimental, off by default.
            "complete_quota": 0,
        }
    )

    # Optional frozen clause pool used by the epoch-pool genetic search.
    clause_pool: dict[str, object] = field(
        default_factory=lambda: {
            "enabled": False,
            # sampled generates a bounded new batch each epoch; exhaustive is the control.
            "source": "sampled",
            # Target clause count. Elite hypotheses may require a larger pool.
            "size": 128,
            # Rebuild after this many generations.
            "epoch_generations": 50,
            # Complete hypotheses retained when rebuilding.
            "elite_count": 10,
            # persistent reuses grounding; fresh isolates the pool's search effect.
            "solver": "persistent",
            # fitness, behavior, or reproductive retention of complete hypotheses.
            "retention": "fitness",
            # random or neighbors, with half the extra capacity reserved for exploration.
            "filling": "random",
            # generations or adaptive (stagnation, novel evaluations, duplicates).
            "renewal": "generations",
            "epoch_evaluations": 50,
        }
    )

    # Clause-generation solver details.
    clause_generation: dict[str, object] = field(
        default_factory=lambda: {
            # Extra Clingo CLI arguments used to enumerate generated clauses.
            "clingo_arguments": ["--parallel-mode=5,split"],
        }
    )
