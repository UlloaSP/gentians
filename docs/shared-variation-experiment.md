# Shared variation versus the historical original

Configuration location: this matrix now lives in `benchmarks/experiments.toml`
under `shared-variation/` IDs. Worker arguments and output folders are unchanged.
The ID change makes old manifests stale; historical measurements below are not
rewritten. Commands below select named entries, not every matrix in the file.

## Protocol

On 2026-09-07, only the new implementation was executed. The control was reused
from `.benchmarks/experiments/sampled-roles/original`; its artifacts were not overwritten.
New artifacts are in `.benchmarks/experiments/shared-variation/new`.

The reproducible configuration is `benchmarks/experiments.toml`.
Both datasets used ten sequential runs, a 300-second wall-clock timeout and no
generation limit. Seeds were 1–10 for 5queens and 11–20 for grandparent. All twenty
recorded argument sets and seeds match the historical control exactly. Pooling
was disabled. Both use exhaustive clause generation and fresh candidate solvers.
No source code was changed during the runs. Neither timeout screening nor the
previously agreed cumulative-time screening condition was triggered.

Run with:

```powershell
uv run python benchmarks/run_experiments.py shared-variation/new
```

## Results

Times are net `total_execution`, not wall-clock or grounding alone. Every dataset
and version solved 10/10 runs. There were no timeouts or failures.

| Dataset | Original mean, s | New mean, s | Mean change | Original median, s | New median, s |
| --- | ---: | ---: | ---: | ---: | ---: |
| 5queens | 6.675410 | 5.426887 | -18.70% | 5.781599 | 4.605669 |
| grandparent | 1.800651 | 1.582350 | -12.12% | 0.844685 | 0.906130 |

Every paired run finished at exactly the same generation and evaluation count
as the control. Mean generations were 1412.1 for 5queens and 3967.1 for
grandparent; mean evaluations were 1029.6 and 1222.0 respectively in both versions.
These homogeneous benchmarks use the policy's unrestricted fast path. The result
does not demonstrate improved convergence or validate the mixed-space heuristic.

The new run has lower mean times, but this is a historical comparison, not an
interleaved experiment controlling machine load and thermal state. The timing
differences alone cannot be attributed to the new policy. Grandparent's median
increased despite its lower mean.

## Same-seed repeat

A second new-code batch on 2026-09-07 repeated all twenty seeds, without changing
the implementation or overwriting either earlier batch. Its source digest matches
the one below. Run `shared-variation/new_repeat` to select this batch; artifacts
are in `.benchmarks/experiments/shared-variation/new_repeat`.

| Dataset | Original mean, s | First new mean, s | Repeat mean, s | Repeat median, s |
| --- | ---: | ---: | ---: | ---: |
| 5queens | 6.675410 | 5.426887 | 5.456950 | 4.534381 |
| grandparent | 1.800651 | 1.582350 | 1.510388 | 0.845507 |

Again both datasets solved 10/10 runs without timeouts. Recorded argument sets,
seeds, final generations and evaluation counts match the first new-code batch
for all twenty pairs. Relative to that batch, mean time changed by about +0.6%
for 5queens and -4.5% for grandparent. The lower new-code means persist rather
than disappearing on repetition.

Ten distinct seeds measure search variability; repeating those same seeds also
checks timing repeatability. Neither controls a systematic difference between
the historical machine conditions and both recent batches. Thus the timing gap
is repeatable here, but its cause remains unproven. It is not evidence of reduced
search effort, and the repeat does not justify dismissing the gap as a single
random timing fluctuation.

## Interleaved original/new rerun

The user then requested running both versions again. The pre-policy source was
reconstructed in an isolated copy. Its ordinal-path/raw-byte SHA-256 is exactly
`4ace35a8420f5be661cd9c1b9a88c501d705528535b2f75644ccb95f34df2f47`, matching the
historical control. The new copy has ordinal-path SHA-256
`bb4eab30369a0a26647218111b6ab2e242c0ccb70f7a6080e7a09f6db2efe270`.
This differs from the new-code digest below only because the earlier PowerShell
calculation used culture-sensitive path sorting rather than ordinal sorting.
Both snapshots remained unchanged throughout the experiment.

For each seed, the versions ran consecutively. Odd pairs ran original/new and
even pairs new/original. There were ten pairs per dataset, with the same seed
assignments, 300-second timeout, full instrumentation and no generation cap.
The existing profiling worker and aggregation functions were reused. The local
runner, snapshots and artifacts are retained under
`.benchmarks/experiments/shared-variation/`, in `run_paired.py`, `paired-sources/` and `paired/`.
`paired/protocol.json` records all forty runs in execution order.

| Dataset | Original rerun mean, s | New rerun mean, s | New versus original |
| --- | ---: | ---: | ---: |
| 5queens | 5.595531 | 5.606974 | +0.20% |
| grandparent | 1.799399 | 1.812183 | +0.71% |

All forty runs succeeded. Every paired argument set, seed, final generation and
evaluation count matches. Original/new medians were 5.061597/4.614052 seconds for
5queens and 0.913533/0.859859 seconds for grandparent.

The earlier 12–19% mean advantage does not persist in the paired rerun. New and
original mean times are now within 1%. The original 5queens implementation also
became faster relative to its historical batch without any code change. This
supports between-batch execution conditions as a confounder, not an algorithmic
speedup. The experiment does not identify a specific hardware or background-load
cause, prove exact performance equivalence, or validate the mixed-space policy.

## Environment

Python 3.14.6, Clingo 5.8.0, Windows 11 build 26200, Intel Core i7-13700H with
14 cores and 20 logical processors. This matches the environment recorded for
the historical control. The dirty worktree is based on commit
`ff57d65e60cce685da8c8a79d47cc162128d5c05`.

Concatenating UTF-8 relative paths with forward slashes and raw file contents,
first sorted `gentians/**/*.py`, then sorted `gentians/**/*.lp`, gives SHA-256
`cb8cf277e0b263c9c68c867f968573b5d4e6e5a759640249316919c5f0c9a7b8`.
The task SHA-256 values are:

- 5queens: `7fd1ae9d51df466c1399ab40fe9e54d6c1ba6712c80efc3381db52981f7f7bb2`.
- grandparent: `d4a328a9272fa6d2bc58724b2fbccd55f84ebd762a71307b4a3f9eb723274918`.
