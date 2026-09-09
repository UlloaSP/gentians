# Incremental on the standard tasks

The pool variants were retired on 2026-09-09. The public search selector is
`Arguments.algorithm`, with `steady_state` and `incremental`. Incremental settings
are `batch_size`, `epoch_generations`, `elite_count` and `time_limit_seconds` under
`Arguments.incremental`. The generator retains one grounding, enumerates increasing
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
