# Incremental on the standard tasks

> Historical measurements. The active matrix and API were simplified on 2026-09-10.
> Old experiment IDs and ablation switches below are no longer executable options.
> See [the current SDK comparison](sdk-defaults-comparison.md) for current behavior.
> Local artifact links describe the original measurement locations and may be absent.

The pool variants were retired on 2026-09-09. The public search selector is
`Arguments.algorithm`, with `steady_state` and `incremental`. Incremental settings
are `batch_size`, `archive_size`, `epoch_generations`, `restart_generations`,
`elite_count` and `time_limit_seconds` under
`Arguments.incremental`. The generator retains one grounding per enumeration pass, enumerates increasing
body budgets and renews a bounded active clause space. Highest-scoring complete
hypotheses and the champion survive renewal. Candidate evaluation uses the normal
coverage solver. Restarted sampling, persistent pool evaluation and the experimental
retention/filling policies have been removed, without compatibility aliases.

## Protocol and interrupted runs

The requested protocol uses population 10, batch size 128, epochs of 50 generations,
ten retained hypotheses, lexicase selection, set_mix crossover, random_group mutation
and fresh evaluation without constraint inheritance. Both the generation limit and
process timeout are zero, meaning unlimited; the internal time budget is None.
No task file or fitness formula was changed. Full instrumentation is enabled.

The first combined experiment completed 5queens seeds 1 and 2, then was interrupted
while seed 3 was searching. A subsequent grandparent seed 1 was interrupted to
prioritize the user's explicit request to rerun all of 5queens. Neither interrupted
run has a terminal score, and neither is counted as a solved or timed-out run.

The new 5queens run uses seeds 1-5. Seeds 4-5 were also run in a separate tail job
while seed 3 continued, so their times include concurrent benchmark activity.
They must not be treated as isolated timing measurements. The source hashes and
configurations are recorded in
`.benchmarks/experiments/incremental/restart-protocol.json`.
Python is 3.14.6 and Clingo is 5.8.0 on Windows 11, Intel Core i7-13700H.
The worktree is dirty; source hashes supplement the Git revision.

## Confirmed results from the requested 5queens rerun

| Seed | Status | Net total seconds | Score | Completed generations |
| --- | --- | ---: | ---: | ---: |
| 1 | Perfect hypothesis | 5.345 | 22026.466 | 1350 |
| 2 | Perfect hypothesis | 7.559 | 22026.466 | 2009 |
| 3 | Interrupted for the paired comparison below | Not closed | Unavailable | Unavailable |
| 4 | Perfect hypothesis | 4.050 | 22026.466 | 1338 |
| 5 | Perfect hypothesis | 3.278 | 22026.466 | 1085 |

No overall mean or success-rate estimate is reported for this incomplete batch.
Seed 3 was stopped when the user requested the paired timeout comparison below. An unlimited evolutionary search
is not guaranteed to find a solution: bounded batch renewal can discard clauses
needed together, and exhaustion retains only the last active space.
Grandparent has no completed result from this protocol yet.

```powershell
uv run python benchmarks/run_experiments.py incremental/5queens-unlimited
uv run python benchmarks/run_experiments.py incremental/grandparent-unlimited
```

The old pool experiments remain historical reports. Their inactive configurations
were removed from the runnable matrix. The benchmark runner now treats
`timeout_seconds=0` as unlimited and reports PAR1 as undefined without a timeout,
rather than assigning failed runs a zero penalty.

## Paired comparison against steady-state, thirty-second process timeout

The user subsequently requested a new controlled comparison, replacing the
unlimited-run protocol. Both algorithms run ten paired runs per dataset, no generation limit and a
30-second process timeout. The runner increments seeds across datasets: 5queens
uses seeds 1-10 and grandparent uses seeds 11-20 in both algorithms.
There is no internal net-time cutoff in this comparison. The external timeout
includes process startup and instrumentation overhead; exported `total_execution`
remains the net-time metric for completed runs.

`search-comparison/steady_state-30s` and `search-comparison/incremental-30s`
differ only in `algorithm`. Both use the same population, selection, crossover,
mutation and replacement settings, fresh coverage evaluation with inheritance
disabled, and full instrumentation without cProfile. Incremental uses batch size
128, epochs of 50 generations and ten retained hypotheses. The previous unlimited
run was stopped before this comparison. Benchmark variants run sequentially,
steady-state first, so host-load drift remains a timing limitation.

Environment, configurations, revision and source hashes are recorded in
`.benchmarks/experiments/search-comparison/protocol.json`. Timed-out workers do not
export buffered terminal metrics, so no terminal score or net total is imputed
for them. Solved-run time means must be read alongside success and timeout counts.

```powershell
uv run python benchmarks/run_experiments.py search-comparison/steady_state-30s search-comparison/incremental-30s
```

### Completed paired results

| Dataset | Algorithm | Perfect / runs | Timeouts | Mean net seconds, solved only | Median net seconds, solved only | Mean completed generations, solved only |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 5queens | steady_state | 10/10 | 0 | 5.312 | 4.041 | 1412.1 |
| 5queens | incremental | 7/10 | 3 | 6.093 | 5.935 | 1636.6 |
| grandparent | steady_state | 10/10 | 0 | 0.439 | 0.424 | 1000.7 |
| grandparent | incremental | 2/10 | 8 | 0.158 | 0.158 | 96.0 |

All 40 requested executions were attempted. There were no process failures.
Every solved run returned score 22026.465794806718, covering all positives and no
negatives. Incremental timed out on 5queens seeds 3, 7 and 9. In grandparent it
solved only seeds 14 and 17, run numbers 4 and 7; the other eight reached the
process timeout.

Steady-state solved all ten seeds on both datasets. Incremental's lower mean
solved-run time in grandparent describes only its two successes and is not evidence
of better overall performance. The comparison favors steady-state on reliability
under the requested cutoff. It does not establish general dominance on other tasks,
and the earlier million-clause result does not transfer to these two tasks.

Timed-out runs have no closed net `total_execution` or exported terminal score.
They are counted as timeouts, not assigned score zero or a fabricated 30-second
net time. The runs were sequential with a fixed algorithm order; host-load drift
limits precision of the timing comparison. Both used the same evaluation and
operator configuration and differed only in the search algorithm.

| Algorithm | Dataset | Seed | Status | Net total seconds | Terminal score |
| --- | --- | ---: | --- | ---: | ---: |
| steady_state | 5queens | 1 | perfect | 2.556 | 22026.466 |
| steady_state | 5queens | 2 | perfect | 3.041 | 22026.466 |
| steady_state | 5queens | 3 | perfect | 3.072 | 22026.466 |
| steady_state | 5queens | 4 | perfect | 3.766 | 22026.466 |
| steady_state | 5queens | 5 | perfect | 4.539 | 22026.466 |
| steady_state | 5queens | 6 | perfect | 10.465 | 22026.466 |
| steady_state | 5queens | 7 | perfect | 4.316 | 22026.466 |
| steady_state | 5queens | 8 | perfect | 12.596 | 22026.466 |
| steady_state | 5queens | 9 | perfect | 5.285 | 22026.466 |
| steady_state | 5queens | 10 | perfect | 3.488 | 22026.466 |
| steady_state | grandparent | 11 | perfect | 0.668 | 22026.466 |
| steady_state | grandparent | 12 | perfect | 0.228 | 22026.466 |
| steady_state | grandparent | 13 | perfect | 0.279 | 22026.466 |
| steady_state | grandparent | 14 | perfect | 0.321 | 22026.466 |
| steady_state | grandparent | 15 | perfect | 0.760 | 22026.466 |
| steady_state | grandparent | 16 | perfect | 0.408 | 22026.466 |
| steady_state | grandparent | 17 | perfect | 0.556 | 22026.466 |
| steady_state | grandparent | 18 | perfect | 0.107 | 22026.466 |
| steady_state | grandparent | 19 | perfect | 0.439 | 22026.466 |
| steady_state | grandparent | 20 | perfect | 0.620 | 22026.466 |
| incremental | 5queens | 1 | perfect | 3.833 | 22026.466 |
| incremental | 5queens | 2 | perfect | 6.083 | 22026.466 |
| incremental | 5queens | 3 | timeout | Unavailable | Unavailable |
| incremental | 5queens | 4 | perfect | 3.781 | 22026.466 |
| incremental | 5queens | 5 | perfect | 3.940 | 22026.466 |
| incremental | 5queens | 6 | perfect | 5.935 | 22026.466 |
| incremental | 5queens | 7 | timeout | Unavailable | Unavailable |
| incremental | 5queens | 8 | perfect | 6.349 | 22026.466 |
| incremental | 5queens | 9 | timeout | Unavailable | Unavailable |
| incremental | 5queens | 10 | perfect | 12.728 | 22026.466 |
| incremental | grandparent | 11 | timeout | Unavailable | Unavailable |
| incremental | grandparent | 12 | timeout | Unavailable | Unavailable |
| incremental | grandparent | 13 | timeout | Unavailable | Unavailable |
| incremental | grandparent | 14 | perfect | 0.124 | 22026.466 |
| incremental | grandparent | 15 | timeout | Unavailable | Unavailable |
| incremental | grandparent | 16 | timeout | Unavailable | Unavailable |
| incremental | grandparent | 17 | perfect | 0.192 | 22026.466 |
| incremental | grandparent | 18 | timeout | Unavailable | Unavailable |
| incremental | grandparent | 19 | timeout | Unavailable | Unavailable |
| incremental | grandparent | 20 | timeout | Unavailable | Unavailable |


## Bounded retention, 9 September 2026

The objective is to match observed steady-state success on the small tasks while
avoiding full clause-space materialization on the synthetic large task. The
following experiment uses the current bounded-retention implementation; earlier
sections describe the discarded last-batch-only behavior.

### Diagnosis and change

Replaying grandparent seed 11 for 600 generations left only 19 working clauses,
with 307 previously seen clauses discarded. The simple father and mother
providers survived in that replay, so provider loss alone did not explain the
failure. Lost combinations also mattered. A separate regression demonstrates the
provider-order bug: a consumer arriving before its provider was discarded before
the two could form a valid program.

Incremental now retains the first 8192 distinct clauses before hypothesis
preparation. Every prepared clause remains active until this archive overflows.
This retains small spaces and lets dependencies arriving in later batches close
earlier clauses. Finite exhaustion then stops epoch reconstruction and preserves
population and evaluation caches. If the archive overflows, the working space
combines the archive, fresh batch and complete retained hypotheses; bounded active
selection resumes. Exhaustion can start another seeded enumeration pass.
Initial exhaustion without any constructible hypothesis raises an error rather
than restarting indefinitely. The archive is a clause-count budget, not a byte
limit on the worker, Clingo or retained hypotheses.

### Protocol

The runnable matrices are `incremental-retention/steady_state-30s`,
`incremental-retention/incremental-30s`, `incremental-retention/million-steady_state`
and `incremental-retention/million-incremental` in `benchmarks/experiments.toml`.
Small tasks use ten runs each, 30 seconds external timeout and unlimited
generations. Seeds are 1-10 for 5queens and 11-20 for grandparent in both arms.
The million-clause task uses five runs, seeds 11-15, 500 generations and the same
30-second process timeout in both arms. The internal time limit is disabled.
Population is 10, batch size 128, epoch length 50, elite count 10 and archive size
8192. Selection, mutation, crossover, replacement, task files and scoring are
identical between arms. Constraint inheritance is disabled for both.

All runs execute serially, steady-state before incremental, first the small tasks
and then the synthetic task. Full instrumentation is enabled, without cProfile.
Environment: Python 3.14.6, Clingo 5.8.0, Windows 11 and Intel Core i7-13700H.
The base revision is `e25270e`; the worktree is modified. The generated
`.benchmarks/experiments/incremental-retention/protocol.json` records source hashes,
seed assignment, environment and execution order.

Each worker writes `*_resources.json` every 200 ms and once after normal return.
Peak RSS is the operating system's high-water resident memory of the Python
worker. CPU seconds sum its threads and include instrumentation. Launchers and
unrelated processes are excluded. A timeout leaves `final=false`; the last
snapshot is a lower bound and can miss work since that sample. Net time remains
`total_execution`; it is not replaced by CPU time or wall-clock. Resource sidecars
do not change the dashboard schema. Results below include the cost of full
instrumentation and its buffers.

### Small-task results

Means over all ten runs. Every returned program is perfect, score 22026.465795.
RSS is the mean of per-run OS peaks, in MiB.

| Task | Algorithm | Perfect | Net seconds | Peak RSS MiB | CPU seconds | Generations | Fitness evaluations |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 5queens | steady_state | 10/10 | 5.013 | 104.421 | 6.614 | 1412.1 | 1029.6 |
| 5queens | incremental | 10/10 | 8.226 | 96.256 | 10.316 | 2899.4 | 2158.0 |
| grandparent | steady_state | 10/10 | 0.456 | 45.452 | 0.900 | 1000.7 | 446.1 |
| grandparent | incremental | 10/10 | 1.043 | 55.915 | 1.858 | 3341.8 | 1051.4 |

Observed success matches the control and improves on the old incremental 7/10
and 2/10 respectively. Time does not improve on these small tasks; grandparent
also consumes more memory. Ten runs do not establish equal underlying success
probabilities or guarantee success on other tasks or seeds. These are the same
seeds used for diagnosis, not held-out validation.


### Million-clause results

The unchanged synthetic task permits 1,149,016 clauses. Means over five runs:

| Algorithm | Runs returning a hypothesis | Perfect | Net seconds | Peak RSS MiB | CPU seconds | Generations | Fitness evaluations | Returned score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| steady_state | 0/5 | 0/5 | Unavailable, all process timeouts | 290.002 or more | 34.584 or more | Unavailable | Unavailable | Unavailable |
| incremental | 5/5 | 0/5 | 10.700 | 50.718 | 12.063 | 500 | 438.0 | 3693.309 |

Incremental used 82.5% less peak resident memory than the control had already
reached at its last samples. Recorded CPU consumption was 65.1% lower. It returned
candidates in every run, while the control returned none within the 30-second
process budget. The control has no terminal `total_execution`, so this does not
establish an exact net-time speedup. Neither algorithm produced a perfect program
under this protocol; lower memory and useful partial results do not establish
superior final solution quality. The incremental working space reached 1168
clauses in every run, far below full materialization and below the archive cap.
Thus this benchmark validates lazy growth, not steady-state memory after filling
all 8192 archive slots. Bounded-overflow and restart behavior have regression tests.

| Seed | Incremental net seconds | Returned score |
| --- | ---: | ---: |
| 11 | 10.320 | 3197.663 |
| 12 | 10.392 | 1889.107 |
| 13 | 10.883 | 2554.506 |
| 14 | 10.805 | 5412.635 |
| 15 | 11.099 | 5412.635 |

### Time components and space

These means are net seconds from the existing timing categories. Clause generation
is inclusive and overlaps the grounding, solving, closure and Python columns;
it must not be added to them. Python is the residual net time. Maximum clauses
is the mean of per-run recorded working-space maxima, not RAM usage.

| Task | Algorithm | Clause generation | Grounding | Solving | Closure | Python | Ground calls | Solve calls | Maximum clauses |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5queens | steady_state | 1.459 | 1.873 | 0.690 | 0.103 | 2.346 | 1030.600 | 1030.600 | 4797.000 |
| grandparent | steady_state | 0.081 | 0.171 | 0.038 | 0.050 | 0.196 | 447.100 | 447.100 | 326.000 |
| 5queens | incremental | 1.710 | 3.414 | 1.311 | 0.176 | 3.326 | 2159.000 | 2164.000 | 4007.600 |
| grandparent | incremental | 0.070 | 0.363 | 0.059 | 0.165 | 0.456 | 1052.400 | 1055.200 | 261.000 |
| synthetic_million | incremental | 5.877 | 1.091 | 0.344 | 0.023 | 9.241 | 439.000 | 442.000 | 1168.000 |

The raw `runs.csv`, timing/GA files, resource sidecars and generated
`resource_summary.json` remain under `.benchmarks/experiments/incremental-retention/`.
The summary uses arithmetic means; missing timeout metrics remain missing rather
than becoming zero. Successful-run RSS snapshots are final; timeout snapshots are
censored. The source protocol also records the post-measurement initialization
error guard, which is not reached by any benchmark task. No benchmark code changed
during the runs.

Verification covered the split-provider regression, bounded retention, finite
stream revisits, initial exhaustion, time budgets and resource snapshots. The full
suite passed 580 tests and exposed one worker fixture missing the newly required
timing path. After fixing that fixture, all 103 tests in the affected search and
benchmark files passed; Ruff and ty passed as well.

The measured objective is met on this matrix: small-task success matches the
control, and the large task returns partial hypotheses with less memory and CPU
within the allotted process budget. This is not a claim that incremental always
wins. Fixed execution order, ten small-task seeds, five large-task seeds and full
instrumentation limit the conclusions. No holdout validation or strict process
memory ceiling is claimed.


## Rejected exact-program cache, 9 September 2026

A follow-up investigated whether repeated evaluations across epoch boundaries
explained the remaining cost. A diagnostic replay found 250 repeated complete
programs among 1915 evaluator calls on 5queens seed 1, and 51 among 2342 calls on
grandparent seed 11. The candidate change used a 4096-entry LRU keyed by the exact
canonical text tuple of the complete program. Cache hits reused EvaluationResult,
not per-clause coverage. A separate request counter preserved individual birth
order while the evaluation metric counted actual evaluator calls.

A regression initially reproduced three evaluations of the same program after
clause IDs changed, and passed with the cache. Static review found no correctness
bug. The 25 cached runs reproduced the preceding control's entire recorded
max/average/best-score trajectory and terminal hypothesis at the same generation.
The cache did not change search quality or reduce the number of generations.

The first timing comparison showed changed clause-generation times as well as
changed evaluation times, so a fresh control was run. Both arms used the preceding
retention protocol: ten paired seeds for each small task, five seeds for the large
task, 30-second process timeout, 500 generations only on the large task, full
instrumentation, no constraint inheritance and no cProfile. The cached arm ran
first, then the fresh uncached control, all serially. There were 50 runs in total.
The current core is restored byte-for-byte to the uncached pre-experiment snapshot.
The tested cache is not an implemented runtime option.

Means against the fresh control:

| Task | Variant | Net seconds | CPU seconds | Peak RSS MiB | Evaluations | Generations |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 5queens | Uncached control | 9.117 | 11.406 | 96.276 | 2158.000 | 2899.400 |
| grandparent | Uncached control | 1.061 | 1.869 | 56.445 | 1051.400 | 3341.800 |
| 5queens | Rejected cache | 9.640 | 12.192 | 96.552 | 1877.100 | 2899.400 |
| grandparent | Rejected cache | 1.018 | 1.798 | 56.223 | 1022.000 | 3341.800 |
| synthetic_million | Uncached control | 11.215 | 12.644 | 51.812 | 438.000 | 500.000 |
| synthetic_million | Rejected cache | 16.633 | 18.778 | 52.127 | 411.800 | 500.000 |

Both variants solved all ten runs of each small task, with score 22026.465795.
Both returned five non-perfect programs on the large task, with mean score
3693.308968. Evaluator calls fell by 13.0% on 5queens, 2.8% on grandparent and 6.0%
on the large task. This did not produce a consistent time improvement, so the
additional cache was removed. The machine's observed timing variation and fixed
execution order prevent attributing the entire slowdown to the cache itself;
they also prevent claiming a demonstrated speed benefit.

Environment remains Python 3.14.6, Clingo 5.8.0, Windows 11, Intel Core i7-13700H,
base revision e25270e with a modified worktree. Raw artifacts, original/cached
source snapshots, hashes and generated summary are retained under
`.benchmarks/experiments/incremental-cache/`. The protocol identifies the cached
source and the fresh control source separately. Study parameters are recorded
beside the active retention configurations in `benchmarks/experiments.toml`; the
rejected source variant is retired from the active runner catalogue. Restoring its
source snapshot is necessary to reproduce that historical treatment.

The remaining hypotheses concern search policy rather than this memo: advance
batch generation when proposals stop being novel, or test a partial population
restart after prolonged stagnation while preserving the champion and dependency
closure. At that stage these were unimplemented hypotheses, not measured improvements. One
observed grandparent seed spent 8022 generations in its final epoch, illustrating
why this is a more substantial source of work than 51 repeated evaluations.

## Stagnation restart, 9 September 2026

The implemented change restarts a stalled population after clause enumeration
has finished, provided the prepared space contains clauses with heads. The default
`incremental.restart_generations` is 100; zero disables this policy. A strictly
better champion resets the counter. The champion and its evaluation survive the
restart. Other evaluation-cache entries are discarded, and the existing population
strategy refills valid programs through HypothesisGenerator. Clause indices and
the clause source are not rebuilt. Normal, choice, disjunctive and strongly negated
heads use the same policy. This changes search, not stable-model evaluation.

A universal restart was tested first. It regressed on the constraint-only 5queens
task, so the final implementation leaves constraint-only search unchanged. This
scope is a measured heuristic, not a theorem that headed tasks benefit. Advancing
batches according to novelty was not implemented or measured in this iteration.

### Protocol

The paired study contains 90 runs. Each variant used a 30-second external process
timeout, full instrumentation, no cProfile and no constraint inheritance. Small
tasks had unlimited generations; synthetic_million had 500. Shared settings were
population 10, batch 128, archive 8192, epoch 50, elite count 10, lexicase selection,
set_mix crossover with probability 1, random_group mutation with probability 0.9,
completeness guidance and constraint-only random mutation enabled, jump and
complete-generator-removal probabilities 0.1, and oldest_or_worst replacement
with probability 0.1. Control and treatment differed only in restart_generations,
zero versus 100.

Execution was serial in this order: small-control, small-restart,
holdout-control, holdout-restart, million-control, million-restart. All experiment
IDs have the `incremental-stagnation/` prefix and live in
`benchmarks/experiments.toml`. Small-task discovery seeds were 1-10 for 5queens and
11-20 for grandparent. Additional validation used 21-30 and 31-40 respectively.
Grandparent seeds 31-40 were unseen during threshold selection. 5queens seed 21
had been screened with threshold 500, so that entire group is not a holdout.
Threshold 100 was selected after preliminary screening of 100 and 500.
The large task used seeds 11-15.

After the study, the restart was restricted to spaces with heads and enabled by
default. Twenty further runs checked this exact final source: final-5queens used
seeds 1-10, and final-grandparent used seeds 31-40. These are confirmation repeats,
not twenty independent new seeds. There were 110 matrix runs in total, excluding
preliminary screening.

Environment was Python 3.14.6, Clingo 5.8.0, Windows 11 and Intel Core i7-13700H.
The base revision was e25270e with a modified worktree. Raw artifacts, source
snapshots before.py and unrestricted.py, source hashes, protocol.json and generated
summary.json are retained under `.benchmarks/experiments/incremental-stagnation/`.
The paired study used the unrestricted snapshot; current configurations use the
final scope. Restore the recorded snapshot to reproduce the historical treatment
on constraint-only tasks. The final confirmation source is separately fingerprinted.

### Grandparent results

All forty paired runs found perfect programs with score 22026.465795. Each table
row is a mean over ten runs. Time is net total_execution; CPU and peak RSS are
worker-process OS measurements. CPU includes instrumentation and solver threads.

| Seeds | Variant | Net seconds | CPU seconds | Peak RSS MiB | Generations | Evaluations |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 11-20 | Control | 1.133 | 2.108 | 55.093 | 3341.8 | 1051.4 |
| 11-20 | Restart 100 | 0.611 | 1.167 | 44.601 | 1024.4 | 701.6 |
| 31-40, unseen | Control | 2.056 | 3.450 | 74.976 | 7400.1 | 1788.8 |
| 31-40, unseen | Restart 100 | 1.533 | 2.666 | 52.637 | 2405.7 | 1633.7 |

Across twenty paired seeds, means changed from 1.594 to 1.072 net seconds,
2.779 to 1.916 CPU seconds, 65.034 to 48.619 MiB peak RSS, 5370.95 to 1715.05
generations and 1420.10 to 1167.65 evaluations. These are observed reductions of
32.8%, 31.0%, 25.2%, 68.1% and 17.8%, with success preserved at 20/20.
The independent seed group supports retaining the policy, although fixed execution
order and variable machine timing limit the precision of timing effects.

### Rejected constraint-only restart and large-space check

On 5queens discovery seeds, the control solved 10/10 with mean net time 7.929
seconds. The unrestricted restart printed ten perfect hypotheses but one process
failed during final resource capture. All ten terminal net measurements averaged
10.423 seconds; the nine clean runs averaged 9.877 seconds. These are different
samples and must not be conflated. The failed run remains failed in the artifacts.
On additional seeds 21-30, both arms solved 9/10 and timed out on seed 30. Among
the nine solutions, control and unrestricted restart averaged 9.494 and 10.231
net seconds, and 1799.3 and 2092.7 evaluations. The restart was not retained for
constraint-only spaces.

The failure was a transient Windows PermissionError when replacing the resource
snapshot, after printing a perfect program. The resource writer now retries that
operation up to twenty times with a 50 ms delay. The fix was introduced during
the paired study and recorded in the protocol. It does not change search; all
final confirmation workers used it. Timeout resource snapshots remain censored,
and missing final snapshots are never replaced with zero measurements.

Both large-task arms returned five non-perfect programs, with identical terminal
programs and every recorded non-time GA metric. Each run completed 500 generations;
mean evaluations were 438, mean score was 3693.308968, and maximum working space
was 1168 clauses, against a full space of 1,149,016 clauses. No stagnation restart
occurred. Control and treatment nevertheless averaged 15.132 and 20.393 net
seconds, 17.166 and 23.288 CPU seconds, and 51.692 and 51.980 MiB peak RSS.
The experiment therefore does not demonstrate a large-task time improvement.
Identical search trajectories and substantial timing variation in unchanged
5queens runs caution against attributing the whole difference to this policy.
The bounded clause-space behavior and large-task quality are preserved.

### Final-source confirmation and checks

| Task | Seeds | Perfect / runs | Net seconds | CPU seconds | Peak RSS MiB | Generations | Evaluations |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 5queens | 1-10 | 10/10 | 11.864 | 14.883 | 96.024 | 2899.4 | 2158.0 |
| grandparent | 31-40 | 10/10 | 1.426 | 2.530 | 51.982 | 2405.7 | 1633.7 |

All final processes completed cleanly within 30 seconds, exported final resource
snapshots and achieved score 22026.465795. Every recorded non-time GA metric and
terminal hypothesis in final-5queens matches small-control. Final-grandparent
matches holdout-restart by the same checks. In particular, preserving 5queens
search does not establish a timing improvement: its measured mean increased from
7.929 to 11.864 seconds across these separate execution batches.

The final source passed 589 tests, Ruff and ty. Regression checks cover champion
retention, early solution detection during refill, disabled restarts, source
exhaustion, constraint-only exclusion, invalid configuration and transient resource
replacement failure. Static review found no blocking issue.

The useful result is reduced grandparent search work and memory with preserved
observed success. This iteration did not rerun steady-state, improve large-task
scores or establish universal success within 30 seconds. Historical steady-state
comparisons above remain separate experiments.

## Common-policy validation, 9 September 2026

The user clarified the acceptance criterion: an improvement must benefit both
5queens and grandparent. The preceding headed-space restart is only a partial
result and does not satisfy that stronger requirement. This follow-up tested
three shared runtime policies through existing configuration, without changing
the task language, evaluator or search implementation.

There were 120 new runs, all serial, fully instrumented, with a 30-second process
timeout and unlimited generations. The control was the preceding implementation
with batch_size 128, epoch_generations 50, elite_count 10, archive_size 8192 and
restart_generations 100. Other evolutionary settings match the stagnation study.
The control therefore includes its headed-space restart. This study does not
compare against steady-state or the earlier restart-disabled implementation.

The first eighty runs used 5queens seeds 1-10 and grandparent seeds 11-20, in this
order: cadence-control, cadence-batch512, cadence-epoch10 and cadence-elite5.
Each candidate changed only the named value relative to that control. The
512-model batch was then checked on unseen seeds, 41-50 for 5queens and 51-60
for grandparent. The validation reversed execution order: cadence-validation512
ran before cadence-validation-control. All six experiment IDs have the
incremental-stagnation/ prefix and retain their parameters in experiments.toml.

The following means include only processes that completed cleanly. In particular,
a lower mean over nine successes cannot establish an improvement against ten
successes. Success below requires both a perfect hypothesis and clean completion
within the timeout. All clean successes had score 22026.465795.

| Group | Variant | Task | Success / runs | Net seconds | CPU seconds | Peak RSS MiB | Evaluations | Generations |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Discovery | control | 5queens | 10/10 | 11.374 | 14.102 | 95.526 | 2158.0 | 2899.4 |
| Discovery | control | grandparent | 10/10 | 0.663 | 1.231 | 44.748 | 701.6 | 1024.4 |
| Discovery | batch512 | 5queens | 10/10 | 9.746 | 12.159 | 106.007 | 2226.7 | 3559.3 |
| Discovery | batch512 | grandparent | 10/10 | 0.624 | 1.189 | 44.328 | 722.1 | 971.2 |
| Discovery | epoch10 | 5queens | 9/10 | 9.167 | 11.220 | 98.631 | 1576.8 | 2372.4 |
| Discovery | epoch10 | grandparent | 10/10 | 1.804 | 3.250 | 51.795 | 1483.7 | 2256.4 |
| Discovery | elite5 | 5queens | 8/10 | 17.711 | 22.305 | 99.268 | 2415.8 | 2846.9 |
| Discovery | elite5 | grandparent | 10/10 | 2.329 | 4.653 | 54.375 | 1741.5 | 2582.7 |
| Validation | validation-control | 5queens | 10/10 | 11.217 | 14.147 | 98.568 | 2308.1 | 3130.7 |
| Validation | validation-control | grandparent | 10/10 | 2.113 | 3.708 | 58.043 | 2174.3 | 3219.4 |
| Validation | validation512 | 5queens | 9/10 | 9.517 | 11.814 | 96.414 | 1560.1 | 2422.7 |
| Validation | validation512 | grandparent | 9/10 | 1.502 | 2.717 | 50.809 | 1445.7 | 2093.0 |

Short epochs lost 5queens seed 5 and increased grandparent evaluations from
701.6 to 1483.7. Retaining five elites lost 5queens seeds 4 and 7 and increased
grandparent evaluations to 1741.5. Both variants were rejected.

The larger batch completed all discovery runs with lower measured net means,
although evaluations increased on both tasks. Validation exposed two failures:
5queens seed 45 printed a perfect program but hit the process timeout during
finalization, while grandparent seed 56 timed out without a terminal perfect
program. The control completed both seeds and all other validation runs. The
5queens event remains a timeout despite its printed score. The larger batch was
therefore rejected as a replacement default.

The environment remains Python 3.14.6, Clingo 5.8.0, Windows 11 and Intel Core
i7-13700H, base revision e25270e with a modified worktree. Protocol, source hashes,
a before.py snapshot, the aggregation script summarize.py and its generated
summary.json are stored in .benchmarks/experiments/incremental-cadence/. Raw runs
remain in the six corresponding incremental-stagnation/cadence-* directories.
The summary retains per-run status, seed, score, evaluations, generations, net
time, CPU, peak RSS and the final-resource flag. Timeout resources are censored.

No tested setting was promoted to a default. The runtime source is unchanged
from the beginning of this follow-up. The experiment catalogue and its count
checks were updated; 79 relevant benchmark tests passed. These experiments have
not produced the requested common improvement. The earlier grandparent gain
must not be presented as completion of that requirement.

## Constraint probes and the size crossover

The subsequent [constraint-probe experiment](incremental-crossover-experiment.md)
retains 16 whole-program proposals per batch for constraint-only incremental
search with positives. It reports 5queens validation, 4queens transfer, unchanged
grandparent search trajectories and a fixed-example scaling sweep. The measured
30-second crossover lies between 5488 and 41448 clauses in that synthetic family;
it is not a universal clause-count threshold.
