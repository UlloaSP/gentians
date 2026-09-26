# Running and configuring Gentians

This guide covers task input, the Python entry point, both search algorithms and
their options. The task language is summarized in
[task-language.md](task-language.md) and specified in
[language-bias.md](language-bias.md).

## Task input

Provide a task file, or a directory with `bk.lp`, `exs.lp`, and `bias.lp`.
Benchmark tasks live in separate directories under `benchmarks/gentians/`, each
with a `README.md` describing the problem, its source, and its search bounds.

`bias.lp` owns the task's structural language bias:

```prolog
#maxv(4).
#maxbl(3).
#maxhl(1).
#maxpl(6).
```

Clingo validates background ASP. Task files do not accept `#script` blocks.

## Running a task

Run code inside the managed environment with `uv run python your_script.py`.
`Arguments` is the SDK configuration; no terminal parsing happens.

```python
from gentians import Arguments, main

main(Arguments(
    filename="benchmarks/gentians/hamming_0", # Task directory to parse.
))
```

A fuller configuration:

```python
arguments = Arguments(
    filename="benchmarks/gentians/coin",
    iterations_genetic=0,
    evaluation={
        "scoring": "cov_program",
        "clingo_arguments": [],
    },
    algorithm="incremental",
    incremental={
        "batch_size": 128,
        "epoch_generations": 50,
        "elite_count": 10,
    },
)
main(arguments)
```

## How search is organized

Gentians searches candidate hypotheses built from a generated `ClauseSpace`.
`gentians.language` owns task I/O, lexical framing, parsing, ASP syntax helpers,
and the typed `InductiveTask` IR. Background, examples, contexts, bias, and
candidate clauses stay as Clingo AST nodes and enter controls through
`ProgramBuilder`. The background is parsed once; only non-empty example fields
invoke Clingo. The static coverage program is retained as AST instead of being
reparsed for every candidate. Candidate `Clause` values retain their AST
beside canonical output text. `gentians.clauses` compiles task IR into candidate
clauses.

The mandatory `HypothesisGenerator` in `gentians.hypotheses` is plumbing used by
evolutionary strategies to preserve size, membership, and dependency
invariants: every initialization, mutation, and crossover returns an already
dependency-closed valid program. `Genome` is the bitset genotype, the rendered
ASP hypothesis is its phenotype, and `Individual` couples one genome to its
evaluation and logical birth order.

Complete search algorithms live in `gentians.algorithms` and return a
`SearchResult`; the runtime they share lives in `gentians.search`. Evolutionary operators live in `gentians.evolution`; candidate
evaluation lives in `gentians.evaluation` so exact or greedy algorithms can
reuse it.

## Evaluation

`evaluation.scoring` is `cov_program`, which scores whole-program coverage.
Whole-program evaluation uses brave consequences. Evolutionary individuals
record whether they cover every positive example and avoid every negative
example. Replacement has no behavior-specific tie-break. The benchmark dashboard
reports complete, incomplete, consistent, inconsistent, and perfect candidate
rates.

Coverage inheritance is enabled by default. Unresolved coverage queries create
and ground a fresh Clingo control; fully inherited results need no new control.
Both algorithms use the normal evaluator.

## Algorithms

`algorithm="steady_state"` is the default and materializes the full clause
space. `steady_state_genetic_search` replaces population members after each
offspring.

`algorithm="incremental"` selects `incremental_clause_genetic_search`, which
uses the same operators while renewing a bounded working clause space.
Generation grounds once and visits increasing body budgets, including attached
conditions, with a resumable seeded solve for each size. Each batch consumes at
most `incremental.batch_size` models before pruning and canonicalization.
Generation pauses while the GA searches.

Each epoch retains the highest-scoring hypotheses and the champion. A bounded
archive keeps the first `incremental.archive_size` distinct clauses before
hypothesis dependency pruning. This lets providers and consumers from different
batches meet. The working `ClauseSpace` combines the archive, the next batch and
elite programs. When the archive contains every visited clause, all prepared
clauses remain active. Once the finite space is exhausted, search continues on
that complete space without rebuilding indices or clearing caches each epoch.

After exhaustion, a space containing learned clauses with heads can restart a
stalled population after `restart.generations` generations without a better
champion score. The champion and its evaluation survive, the other evaluation caches are cleared,
and the existing population strategy fills the remaining slots with closed
hypotheses. Every improvement resets the stagnation counter. Constraint-only
spaces do not restart. Normal, choice and disjunctive heads use the same rule;
whole-program ASP evaluation is unchanged.

For constraint-only spaces with positive examples, incremental tries up to 16
extra proposals during initialization and each batch renewal. It extends the
best complete candidate using new clauses, or replaces a clause at the
program-size limit. Every proposal is a valid hypothesis evaluated as a whole
ASP program. This is a fixed part of incremental search. Historical measurements
on 5queens, 4queens and nested large spaces are in the
[constraint-probe report](incremental-crossover-experiment.md).

If the archive overflows, the active mask selects retained programs and random
closed candidates. Exhaustion starts a new seeded enumeration pass so discarded
clauses can return. Each pass grounds once and enumerates increasing body
budgets. This bounded search is neither uniform sampling nor complete hypothesis
search. A supplied `ClauseSpace` bypasses generation. The archive limits clause
count, not bytes: the working space also contains the fresh batch and elite
programs, and Clingo, caches and instrumentation consume additional memory.

Restarted batch sampling and frozen-pool evaluation have been removed. `#maxpl`
still limits complete hypotheses; unbounded task limits can allow large retained
programs.

Each algorithm file in `gentians/algorithms/` only wires its steps together;
`gentians/algorithms/metrics/` records generation progress for both and epochs
for incremental. The steps live in `gentians/search/`:

- `candidates.py`: evaluation/admission caches, logical age and recoding
  retained programs when the prepared space changes.
- `population.py`: members, champion, initialization, refill, restarts and
  child admission.
- `offspring.py`: one mating event and evaluation phase attribution.
- `clause_pool.py`: incremental batch enumeration, bounded archive and active clauses.
- `renewal.py`: incremental epoch renewal and constraint probes.
- `budget.py`: net-time deadline and best result evaluated within budget.
- `result.py`: `SearchResult`.

## Variation

Mutation has one implementation, `random_group`, selected through the existing
mutation factory. It adds, replaces or removes a root clause and its dependency
block. Replacement normally preserves the set of signed head predicate
signatures, not the exact head expression or body:

```python
mutation={
    "name": "random_group",
    "probability": 0.9,
    "random_jump_probability": 0.1,
    "complete_generator_removal_probability": 0.1,
}
```

`random_jump_probability` permits a different head on 10% of replacement
attempts. It does not override complete-candidate protection.
`complete_generator_removal_probability` reserves a separate 10% chance to try
deleting a headed dependency block. Its offspring still requires evaluation;
deletion is not proof of redundancy. Both defaults are configurable.

Complete programs keep their headed clauses unchanged, except for that
removal attempt. If a complete candidate has no legal constraint edit or allowed
deletion, mutation leaves it unchanged. This restriction can block candidates
whose solution requires a headed replacement. Incomplete programs can edit
headed clauses or remove and replace constraints. With negatives present,
incomplete candidates replace roots within their role, headed or constraint, and
do not append pure constraints. Constraint replacement does not require
structural relaxation. Without negative examples, construction removes optional
pure constraints whenever a nonempty legal program remains.

When the active clause space contains only constraints, mutation uses
unrestricted random edits, while preserving the directed policy in spaces with
headed clauses. It permits constraint additions to incomplete candidates, which
can improve negative coverage without recovering positives. See
[the mutation ablation report](mutation-ablation-experiment.md) for controls,
timings and limitations.

Mutation classifies its actual input through the cached evaluator when
positives exist, including crossover offspring and homogeneous spaces. Known
solutions remain unchanged. Classification evaluations count toward search cost.
Consistency alone does not freeze headed clauses; tasks without positives do not
freeze them either. The separate `completeness` and `structural_neighbor`
mutation names have been removed.

The default `set_mix` crossover retains its preference for complete recipient
heads, including its 10% unrestricted escape and fallback. Lexicase selects
distinct parents within each mating event; it does not certify coverage or
preserve complete recipient heads. An already evaluated crossover result may
still serve as the base for mutation, and in that case mutation bypasses its
probability gate. Selection and variation still run once per generation.
`set_mix` remains the default; a matched steady-state experiment is prepared in
`benchmarks/experiments.toml`.

See [variation policy](variation-policy.md) for guarantees and exceptions, and
[the mutation guide](mutation-guide.md) for diagrams.

## Clause pruning

Clause generation prunes headless models before decoding when a static
missing-predicate proof establishes that a positive example needs a learned
head. This applies to exhaustive enumeration and incremental batches. It
preserves constraint-only languages and uncertain cases. Absence of negatives
alone is not sufficient to prune every constraint because hypotheses must remain
nonempty. The exact conditions are documented in
[language bias](language-bias.md#positive-only-constraint-pruning).

## Main options

Structural limits belong to the task, not to `Arguments`:

- `#maxv`: maximum distinct variables in one clause. Default 3.
- `#maxbl`: maximum body literals in one clause. Default 3.
- `#maxhl`: maximum head atoms in one clause. Default 1.
- `#maxpl`: maximum clauses in one candidate program. Default 6.
- Any structural limit accepts `*` when remaining mode recalls still make the
  clause space finite.

`Arguments` fields:

- `filename`: task file or task directory to parse.
- `iterations_genetic`: number of genetic generations. `0` means unlimited and is
  the default.
- `population.name`: `random`, which samples valid programs through
  `HypothesisGenerator`.
- `evaluation.scoring`: `cov_program`.
- `evaluation.constraint_inheritance`: exact coverage reuse for pure
  integrity-constraint changes, using the normal solver. Default `true`.
  Unresolved examples still use a fresh Clingo control. See
  [the experiment and guarantees](semantic-inheritance-experiment.md).
- `restart.name`: `stagnation`, which restarts both algorithms from the
  champion when the best score stops improving. Constraint-only spaces never
  restart.
- `restart.generations`: generations without a better champion before a
  restart. Default `100`.
- `algorithm`: `steady_state` (default) or `incremental`.
- `incremental.batch_size`: raw models per new clause batch. Default `128`.
- `incremental.archive_size`: retained distinct clauses before dependency
  pruning. Default `8192`.
- `incremental.epoch_generations`: generations between batches. Default `50`.
- `incremental.elite_count`: complete hypotheses retained at renewal. Default `10`.
- `incremental.time_limit_seconds`: optional positive net-time budget, including
  clause generation. Default `None`. `iterations_genetic=0` disables the
  generation limit. In-flight operations finish before returning, but late
  evaluations cannot improve the timed result. The benchmark runner's
  `timeout_seconds=0` disables its separate process timeout.

`gentians/arguments.py` lists every field with its default.

## Recommended configuration

The recommended shared benchmark configuration uses structural mutation and
exact constraint-coverage inheritance. The default algorithm remains
`steady_state`. The same settings run 5queens, grandparent, coloring and
knapsack, with ten runs each, a 30-second timeout per run and no generation
limit. A timeout skips remaining runs of that dataset. This is the
best-supported combination across these measured tasks, not a claim of
optimality for every ASP task. Historical matrices remain in the same TOML.

```powershell
uv run python benchmarks/run_experiments.py sdk-defaults/steady_state
```

## Historical configurations

Historical pool experiments and their measurements remain documented in
[pool-policy-experiment.md](pool-policy-experiment.md) and
[million-clauses-experiment.md](million-clauses-experiment.md). Their retired
configurations are no longer executable on the current API. Current
standard-task runs are recorded in [the incremental report](incremental-experiment.md).
Benchmark timings belong to their recorded source versions.
