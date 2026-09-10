# Current SDK comparison

This run compares steady-state and incremental on 5queens and grandparent with
unmodified SDK defaults apart from the algorithm selector. Coverage inheritance
is enabled. Both use ten runs per task, unlimited generations, a 30-second
external process timeout, full instrumentation and no cProfile. Seeds are 1-10
for 5queens and 11-20 for grandparent, matched between algorithms. Workers run
serially. Canonical time is net `total_execution`; a timeout has no completed net
time and is excluded from successful-run means.

The active matrix is `benchmarks/experiments.toml`. Historical catalogue entries
and catalogue-content tests were removed. Completeness guidance and constraint-only
mutation are fixed structural policies. Incremental retains its bounded archive,
100-generation headed-space restart and 16 constraint proposals, without ablation
switches. No new performance heuristic was introduced during this cleanup.

The runner records effective arguments, source and task hashes and Python/Clingo
runtime identity. Changes invalidate reuse; changes during execution mark the
run stale. Both algorithms completed their scheduled runs. The steady-state manifest is complete; incremental has two timed-out runs.

## Results

Net times in seconds. Means exclude timeouts.

| Run | 5queens steady | 5queens incremental | Grandparent steady | Grandparent incremental |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 3.136 | 10.674 | 1.074 | 0.950 |
| 2 | 4.188 | Timeout | 0.295 | 0.114 |
| 3 | 3.645 | 5.294 | 0.347 | 1.941 |
| 4 | 4.415 | 18.365 | 0.382 | 0.153 |
| 5 | 6.151 | 3.482 | 0.757 | 0.288 |
| 6 | 9.320 | Timeout | 0.478 | 0.214 |
| 7 | 4.034 | 18.044 | 0.850 | 1.568 |
| 8 | 9.935 | 7.560 | 0.130 | 1.168 |
| 9 | 6.141 | 9.294 | 0.564 | 0.304 |
| 10 | 5.437 | 5.855 | 0.924 | 0.138 |
| Mean completed | 5.640 | 9.821 | 0.580 | 0.684 |
| Solutions | 10/10 | 8/10 | 10/10 | 10/10 |

On the eight 5queens seeds completed by both, mean net times were 5.361729 seconds for steady-state and 9.821015 for incremental. Incremental took 83.2% longer on that subset and timed out on seeds 2 and 6. Steady-state was faster on average in both tasks in this batch. Ten seeds and fixed execution order do not establish a universal ordering.

## Environment and verification

Measured on 2026-09-10, Windows 11, Intel Core i7-13700H, Python 3.14.6 and Clingo 5.8.0. Base revision e25270e with modified worktree. Steady-state ran first, then incremental; no tests or other benchmarks ran concurrently. Each manifest stores complete source hashes and effective arguments, including coverage inheritance=true.

The solver checks passed after updating one expectation that described the removed direct-constructor policy. Ruff and type checking passed. No catalogue tests were added or run. Static review found and resolved relative-task-path and override-order fingerprint issues before measurement.

The two attempts to delete the old local artifact directory were rejected by automatic execution policy. Those old files therefore remain on disk; the active index only includes the new pair. New raw results are under `.benchmarks/experiments/sdk-defaults/`.
