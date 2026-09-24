# Synthetic million-clause search comparison

Historical experiment. The pool API, restarted sampling and persistent pool solver
were retired on 2026-09-09. Configuration names below describe the measured version,
not the current API. Use `algorithm="incremental"` with `Arguments.incremental`.

## Task and scope

`benchmarks/synthetic_million.py` deterministically generates
`benchmarks/gentians/synthetic_million/`, using data seed 20260908. The task
chooses exactly one active world. Each of 32 unary predicates describes one
Boolean feature of that world. Positive worlds satisfy six forbidden-pair
constraints; negative worlds violate at least one. Positive singleton worlds
prevent solutions that simply forbid an individual feature. The all-true
negative world provides a common possible instance of every conjunction.

The language contains headless clauses with one variable, one to six positive
feature literals, and recall one per feature. Its size is
`sum(comb(32, k) for k in range(1, 7)) = 1,149,016`. Every feature subset has one
canonical variable spelling. Singleton worlds make predicate extensions
incomparable, so implication and equivalence pruning do not collapse the space.
The tests enumerate the reduced six- and eight-feature languages and check
their exact counts. This combinatorial count must be distinguished from a
completed full materialization of the million-clause `ClauseSpace`.

A reference solution is the six constraints `:- f0(X), f1(X).` through
`:- f10(X), f11(X).`. The normal evaluator verifies perfect coverage; the empty
program fails. This establishes solvability, not uniqueness or a six-clause
minimum. Learned alternatives are scored against the supplied examples.

This is a scale experiment with simple conjunctions and many possible coverage
collisions on a finite dataset. It does not reproduce the arithmetic or
recursion of other tasks. Success does not establish generalization to unseen
worlds or a universal benefit from sampling.

## Fixed protocol

Both algorithms use seeds 1, 2 and 3, unlimited genetic generations, population
10, lexicase, set-mix crossover, mutation probability 0.9, and the current
recommended constraint-only mutation policy. Each run has a 180-second process
timeout. Runs execute serially, steady-state first and sampled-pool second.
There is no tuning against the measured results. Full instrumentation is used
without cProfile. Time means net `total_execution`, including clause generation.

`million-clauses/steady` uses the overrides of `recommended/general`. It
materializes the complete clause space before initializing its population.

`million-clauses/sampled-pool` samples at most 128 clause models per epoch,
renews every 50 generations, retains ten hypotheses by fitness, fills randomly,
and uses persistent pool evaluation. Retained clauses may increase the active
space above 128. This implementation rebuilds and grounds a frozen pool each
epoch; it does not append clauses to an existing grounding. Exact constraint
inheritance is disabled because the persistent solver does not support it.
Thus the comparison measures these two usable algorithm configurations, not an
isolated ablation of the pool restriction or solver reuse.

Three seeds provide exploratory evidence. Fixed execution order and the small
sample limit conclusions. Timed-out runs without a closed timing record have
no reported net time, coverage or evaluation count. A generation timeout and
a timeout during search are different outcomes and must be identified from
available logs rather than inferred from wall time.

## Reproduction and artifacts

```powershell
uv run python -m benchmarks.synthetic_million
uv run pytest tests/test_synthetic_million.py -q
uv run python benchmarks/run_experiments.py million-clauses/steady million-clauses/sampled-pool
uv run python benchmarks/run_experiments.py million-clauses/steady million-clauses/sampled-pool --summary
```

The shared matrix is `benchmarks/experiments.toml`. Existing results are preserved
unless an explicit rerun uses `--force`. Raw results, logs and dashboards live
under `.benchmarks/experiments/million-clauses/{steady,sampled-pool}/`.
The parent `protocol.json` records source and task hashes, resolved arguments,
Python, Clingo, hardware identity, revision and execution order. Changes in the
dirty worktree are represented by content hashes, not the Git revision alone.


## Incremental enumeration comparison

The follow-up implements `incremental_clause_genetic_search` in one algorithm
file, including its retention and filling policies. `source="incremental"`
prepares the task analysis and clause metaprogram once, keeps one Clingo solve
handle open, and resumes it for each bounded batch. It closes the handle on
success, generation limit, exhaustion, or an exception. The default evaluator
is fresh and independent of clause enumeration. The old `sampled` source and
persistent evaluator remain explicit controls.

This is sequential demand-driven enumeration. A producer could prepare a future
batch concurrently, but this implementation does not run one. The timing module
uses a process-global phase stack, and concurrent generation would require
separate accounting of overlapping work. No parallel speedup is claimed.
The initial metaprogram grounding is still unbounded by the batch size. Clingo's
search state may also grow; the bound applies to retained clause batches, not
all process memory. Canonical duplicates are removed within the active space,
without accumulating a set of every clause ever visited. Dependencies that fall
in different discarded batches can be missed, and exhausting the enumerator
continues genetic search on the last working space rather than proving failure.

The new comparison uses the original synthetic task unchanged, seeds 1ÃƒÆ’Ã†â€™Ãƒâ€ ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ3,
population 10, 128 models per batch, 50 generations per epoch, ten retained
hypotheses, and the same operators as the first experiment. Both fixed-budget
variants disable coverage inheritance and use the normal fresh evaluator.
Their only configuration difference is `clause_pool.source`:

- `million-clauses/sampled-fresh-budget` runs 500 generations with restarted
  randomized batches.
- `million-clauses/incremental-fresh-budget` runs 500 generations with one
  continuous randomized enumeration.
- `million-clauses/incremental-fresh` uses the latter configuration with unlimited
  generations and a 180-second timeout, measuring whether it reaches a solution.

Each variant has three serial runs and full instrumentation without cProfile.
Fixed generations measure work completed under a common search budget, not time
until an equally good hypothesis. Changing enumeration changes candidate order
and coverage, so runtime must be read alongside score and success. The unlimited
runs retain the timeout of the earlier experiment; their fresh evaluation means
they are not an isolated comparison with the historical persistent-pool runs.

```powershell
uv run python benchmarks/run_experiments.py million-clauses/sampled-fresh-budget million-clauses/incremental-fresh-budget million-clauses/incremental-fresh
```

The generated `incremental-protocol.json` under the parent output directory
records the execution order, full matrix entries, source hashes, task hash,
Python, Clingo, operating system, CPU identity and Git revision. No previous
experiment outputs are overwritten. The original `protocol.json` and its
historical outputs retain their original meaning.


### Fixed-budget results

Measured on 2026-09-08 with Python 3.14.6, Clingo 5.8.0 and Windows 11
10.0.26200, on an Intel Core i7-13700H with 14 cores and 20 logical processors.
The Git revision was `de0cc8e332542191999775278bed27a8e07e0d14`, with the dirty
worktree identified by the protocol's source hashes. Each incremental or sampled
clause enumerator used one solver thread; candidate evaluation used its normal
configuration. No benchmark variants ran concurrently. Small source/document
inspection operations ran alongside the benchmark.

All six fixed-budget runs completed 500 generations. None found a perfect
hypothesis. Times below are net `total_execution`, not process elapsed time.
Positive coverage has denominator 57; covered negatives have denominator 25
and should reach zero.

| Source | Seed | Total seconds | Clause generation seconds | Fitness evaluations | Best score | Positives covered | Negatives covered |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Restarted sampled | 1 | 70.416 | 62.410 | 415 | 101.958 | 56 | 13 |
| Restarted sampled | 2 | 72.787 | 64.219 | 398 | 121.510 | 57 | 13 |
| Restarted sampled | 3 | 73.540 | 66.521 | 430 | 1116.042 | 40 | 0 |
| Continuous incremental | 1 | 16.392 | 6.478 | 418 | 6.200 | 56 | 20 |
| Continuous incremental | 2 | 15.621 | 6.788 | 406 | 54.598 | 57 | 15 |
| Continuous incremental | 3 | 16.400 | 6.350 | 456 | 11.023 | 57 | 19 |

Mean total time fell from 72.248 to 16.138 seconds, a 77.7% reduction and a
4.48-fold ratio for this fixed budget. Mean clause generation fell from 64.383
to 6.539 seconds. Each run consumed 1,280 clause models in ten batches. The
incremental source made one grounding and one solve call for clause enumeration;
the restarted source made ten of each. Solver resumes are not counted as new
solve calls. This count excludes candidate evaluation calls.

| Mean time category, whole run | Restarted sampled seconds | Continuous incremental seconds |
| --- | ---: | ---: |
| Grounding | 1.771 | 1.300 |
| Solving | 0.559 | 0.521 |
| Closure | 0.039 | 0.039 |
| Python | 69.879 | 14.278 |

Python is the residual of `total_execution` after grounding, solving and closure.
The measured saving is predominantly Python work, consistent with reusing task
analysis and mode compilation in addition to retaining the Clingo control.
The initial grounding reduction alone does not explain the result.

Best score was lower with incremental enumeration in every paired seed, and it
covered more negative examples. Continuing a randomized enumeration visits a
different, potentially correlated sequence of clauses compared with restarting.
The experiment establishes cheaper progress through 500 generations, not better
solution quality or a reduction in time to a perfect hypothesis. Three seeds and
fixed variant order limit the strength and generality of the evidence.


### Unlimited-generation outcome

`million-clauses/incremental-fresh` timed out in all three seeds at the
180-second process limit, with zero perfect hypotheses reported. The terminated
workers did not export their buffered timing or progress records, so these runs
have no closed net `total_execution`, terminal coverage or evaluation count.
The timeout is an operational limit and is not substituted for net execution
time. This matches the earlier experiment's zero reported solutions, while the
change from persistent to fresh evaluation prevents attributing differences to
enumeration alone.

The incremental mechanism remains available for tasks where full enumeration is
too expensive, with `clause_pool.enabled=false` retaining the existing default
search. Parallel prefetch and example-guided clause generation are not
implemented by this change. The follow-up below tests whether ordering batches can improve search quality
without restarting the expensive task analysis.

Verification covers bounded, seeded batches, continuation of model numbers,
small-space exhaustion, early cancellation on normal and exceptional exit,
consumer-time exclusion, nonmonotonic head/body forms, and release of preceding
hypothesis spaces. A reviewer identified the inherited 64-batch retry cutoff;
continuous enumeration now skips unusable batches until actual exhaustion.
The correction was made during the first restarted-source control run and does
not change that control's 64-attempt path. All incremental runs used the corrected
code; both hashes and this distinction are recorded in the protocol.


## Body-size ordering experiment

The quality follow-up keeps the synthetic task unchanged. A diagnostic of ten
128-model batches from the old continuous enumerator, using generator RNG seed
`3 ^ 0x5EED_600D`, found that every one of the 1,280 clauses had six body literals.
This diagnostic advances only the generator RNG and does not reproduce the GA's
pool-filling RNG draws. The raw histogram is in
`million-clauses/enumeration-order-diagnostic.json`. It shows a structural bias
in the visited prefix, not a coverage score for individual clauses.

The candidate uses `clause_pool.order="body_size"` with the incremental source.
An optional ASP atom represents the sum of selected body slots and attached
conditions. The generator grounds once, then solves under one exact-size
assumption at a time, from smallest to largest. Within each size it keeps the
same seeded enumeration handle across batches. A size is exhausted before the
next one starts, and the final batch of a size can contain fewer than 128 models.
This does not change `#maxbl`, remove long clauses, or score clauses separately.
Whole hypotheses still receive normal ASP evaluation. Shorter clauses are a
search preference; tasks needing longer bodies may benefit less or be delayed.

The initial matrix consists of `incremental-quality/control` and
`incremental-quality/body-size`, both with seeds 1ÃƒÆ’Ã†â€™Ãƒâ€ ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ3, 500 generations, population
10, batch budget 128, epochs of 50 generations, fitness retention of ten complete
hypotheses, and fresh evaluation without coverage inheritance. Both have full
instrumentation, no cProfile, and a 180-second process timeout. The only changed
configuration is the clause-generation source/order. The control restarts its
sampler; the candidate reuses analysis and grounding and orders enumeration by
body size. Both run on the current code, preserving the previous experiment's
outputs. Their protocol and source hashes are recorded under
`.benchmarks/experiments/incremental-quality/protocol.json`.

```powershell
uv run python benchmarks/run_experiments.py incremental-quality/control incremental-quality/body-size
```

### Pilot results

| Source | Seed | Net total seconds | Best score | Positive covered / 57 | Negative covered / 25 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Restarted sampled | 1 | 165.893 | 101.958 | 56 | 13 |
| Restarted sampled | 2 | Timeout | Unavailable | Unavailable | Unavailable |
| Restarted sampled | 3 | 126.501 | 1116.042 | 40 | 0 |
| Incremental by body size | 1 | 16.324 | 6450.609 | 50 | 0 |
| Incremental by body size | 2 | 15.521 | 1889.107 | 43 | 0 |
| Incremental by body size | 3 | 26.746 | 7687.635 | 51 | 0 |

All completed runs reached the 500-generation budget without a perfect hypothesis.
The two completed paired controls lost on score and net time. The new candidate
also exceeded all three historical restarted-sampler scores. That historical
comparison is secondary: host contention changed substantially, and the current
seed-2 control has no exported terminal score. Its old score cannot fill that gap.
The improvement in score trades some positive coverage for eliminating covered
negative examples, as reflected in the unchanged `cov_program` objective.

### Independent validation protocol

After inspecting seeds 1-3, the ordering policy was frozen for seeds 11-15.
`incremental-quality/validation-control` and
`incremental-quality/validation-body-size` retain the same 500-generation budget
and all search parameters. Both receive a 300-second process timeout because
one pilot control exceeded 180 seconds under host contention. The five control
runs execute first, followed by the five candidate runs, without concurrent
benchmark variants. This fixed order leaves possible host-load drift as a timing
confounder. No new seed was used to tune the ordering policy.

Environment, revision, source hashes and configurations are retained in
`.benchmarks/experiments/incremental-quality/validation-protocol.json`.
Python is 3.14.6, Clingo is 5.8.0, and the host is Windows 11 build 26200 on an
Intel Core i7-13700H with 14 cores and 20 logical processors. The worktree is
dirty; source hashes supplement revision `de0cc8e332542191999775278bed27a8e07e0d14`.

```powershell
uv run python benchmarks/run_experiments.py incremental-quality/validation-control incremental-quality/validation-body-size
```

### Independent validation results

| Seed | Pool score | Incremental score | Pool net seconds | Incremental net seconds | Pool positive / negative | Incremental positive / negative |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 11 | 81.451 | 5412.635 | 136.223 | 14.959 | 57 / 14 | 49 / 0 |
| 12 | 24.533 | 6450.609 | 126.806 | 15.093 | 57 / 17 | 50 / 0 |
| 13 | 25.768 | 5412.635 | 145.795 | 14.883 | 55 / 16 | 49 / 0 |
| 14 | 54.598 | 3197.663 | 102.602 | 14.408 | 57 / 15 | 46 / 0 |
| 15 | 107.092 | 2251.379 | 138.234 | 14.109 | 54 / 12 | 44 / 0 |

All ten runs completed 500 generations without a timeout or a perfect hypothesis.
Incremental ordering achieved higher score and lower net time in all five paired
seeds. Mean score rose from 58.688 to 4544.984. Median score rose from 54.598 to
5412.635. Mean `total_execution` fell from 129.932 to 14.691 seconds, an 88.69%
reduction and an 8.84-fold ratio. Median time fell from 136.223 to 14.883 seconds.

Mean positive coverage fell from 56.0 to 47.6 out of 57; mean negative coverage
fell from 14.8 to zero out of 25. Thus the quality improvement follows the existing
score's tradeoff, not a gain in both coverage dimensions. Mean program size fell
from 6.0 to 5.2 clauses. These are training-task scores, not held-out accuracy.

Mean clause-generation time fell from 111.223 to 7.775 seconds. Each restarted
run consumed 1280 raw models with ten groundings and ten solves. Each incremental
run consumed 1168 raw models with one grounding and four solves, including the
unsatisfiable size-zero partition. The 128-model per-batch budget is equal, but
final batches of exhausted sizes are shorter. These counts describe the tested
source policy; they do not establish an equal-model-count comparison.

| Mean whole-run time category | Restarted pool seconds | Incremental seconds |
| --- | ---: | ---: |
| Grounding | 3.020 | 1.541 |
| Solving | 1.146 | 0.492 |
| Closure | 0.062 | 0.044 |
| Python residual | 125.704 | 12.614 |

The large Python saving includes avoiding repeated task analysis and mode
compilation, and decoding/canonicalizing shorter clauses. The experiment does not
isolate these contributions. The fixed variant order and variable host load limit
the precision of the speed ratio. Five unseen seeds support this task-specific
result; they do not establish universal dominance, generalization, or faster time
to a perfect hypothesis. No perfect hypothesis was found by either method.

After validation, `body_size` became the default ordering when incremental search
is enabled. The ordinary steady-state default remains unchanged through
`clause_pool.enabled=false`. Restarted sampling remains available as
`clause_pool.source="sampled"`, and the original continuous order remains available
as `clause_pool.order="solver"`. Historical continuous experiment entries explicitly
retain `solver` ordering. The final default changes occurred after measured runs;
the measured validation entries already selected both source and order explicitly.
No evaluation, task, fitness or evolutionary-operator policy was changed.

Final verification passed all 617 tests in 35.47 seconds, Ruff on the touched
Python files, and `uv run ty check`. Generation tests compare exhaustive and
ordered spaces, include conditional-body budgets and nonmonotonic forms, and
check that grounding occurs once while solves are counted per size. Existing
lifecycle tests retain the original unpartitioned order explicitly. The matrix
validation test fixes equal budgets and allows only source/order differences.

## Equal thirty-second budgets

The follow-up requested equal time instead of equal generation count.
`incremental-quality/time30-control` and `incremental-quality/time30-body-size`
use the same seeds 11-15 and search settings as the independent validation, with
`iterations_genetic=0` and `clause_pool.time_limit_seconds=30` in both arms.
The budget starts when the search function is entered, before clause generation,
and uses `net_time`, excluding instrumentation overhead. Task-file parsing occurs
before the measured search, as in the earlier runs.

The search checks its deadline at generation and batch boundaries and before and
after candidate evaluation. It retains the best whole-program evaluation completed
strictly before the deadline. A Clingo or canonicalization operation already in
progress can overrun the deadline; its late evaluation cannot improve the returned
score. Cleanup and that overrun remain in exported `total_execution`. Thus 30
seconds is the eligibility budget, not a claim that process wall time is exactly
30 seconds. A separate 90-second process timeout protects against a stuck worker
and is not additional search budget. If no candidate was evaluated in time, the
search fails explicitly instead of inventing a result.

The five restarted controls execute before the five incremental runs. Both keep
full instrumentation and fresh evaluation. Source hashes, environment and config
are recorded in `.benchmarks/experiments/incremental-quality/time30-protocol.json`.
The final printed `SearchResult` is authoritative at the cutoff. Raw evaluation
metrics may contain an operation completed after the deadline, and the last GA
row may precede an interrupted generation. Neither replaces the returned score.

```powershell
uv run python benchmarks/run_experiments.py incremental-quality/time30-control incremental-quality/time30-body-size
```

### Thirty-second results

| Seed | Pool score | Incremental score | Pool positive / negative | Incremental positive / negative | Pool net total seconds | Incremental net total seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 11 | 24.533 | 10918.847 | 57 / 17 | 53 / 0 | 30.010 | 30.057 |
| 12 | 11.023 | 10918.847 | 57 / 19 | 53 / 0 | 37.196 | 30.007 |
| 13 | 13.799 | 9161.883 | 56 / 18 | 52 / 0 | 33.120 | 30.014 |
| 14 | 54.598 | 6141.394 | 57 / 15 | 52 / 1 | 30.012 | 30.015 |
| 15 | 16.445 | 6450.609 | 57 / 18 | 50 / 0 | 30.004 | 30.006 |

Incremental achieved a higher returned score in all five paired seeds. Mean score
was 8718.316 versus 24.079 for restarted sampling. Mean positive coverage was
52.0 versus 56.8 out of 57, and mean negative coverage was 0.2 versus 17.4 out of
25. Neither method found a perfect hypothesis. The last completed GA generation
averaged 1999 for incremental and 149 for restarted sampling. These generation
counts are observed work, not limits; an interrupted generation is not counted.

Mean exported net total time was 30.020 seconds for incremental and 32.069 for
restarted sampling. The latter included a maximum overrun to 37.196 seconds while
a clause batch completed. Its generated candidates did not enter the timed
result. The comparison establishes higher score within the same eligibility
budget, not an exact 30-second wall-clock termination guarantee. Fixed variant
order and host load still affect how much search fits into that budget.

Both timed variants return the best evaluated complete program within budget,
including evaluated operator proposals that did not survive population replacement.
The retained text is independent of later pool indices. Raw quality metrics describe
all executed evaluations, including a possible final late evaluation; their
`best_found` counts must not be interpreted as timed-run success. Run success and
the scores above come from the returned `SearchResult`.

Verification passed 119 targeted tests for bounded generation, pool search,
experiment configuration and mutation, plus Ruff and type checking. A simulated
clock test covers both sources, includes 20 seconds of generation, and rejects a
higher-scoring evaluation completed at 32 seconds while retaining the one completed
at 26 seconds. It also checks generator closure on deadline exit.
