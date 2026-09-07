# Original versus dependency-block mutation

## Protocol

On 2026-09-07, both versions were executed again in isolated source snapshots.
The control is the verified historical original, not the current implementation
with its mutation parameters set to zero. The treatment is the current code with
unified `random_group` mutation and dependency-block transitions.

The new configuration comes from `shared-variation/new` in
`benchmarks/experiments.toml`. Historical outputs were not overwritten. The local
paired runner and this run's outputs are under `.benchmarks/block-mutation/`:

- `run_paired.py` reuses the existing profiling worker and aggregation functions.
- `paired/protocol.json` records source hashes, task hashes, arguments reference,
  configuration, runtime environment, execution order and screening decisions.
- `paired/original/` and `paired/new/` contain raw runs, timings, metrics and
  dashboards. The copied new source is retained in `sources/new/`.

There were ten planned runs per dataset and version, a 300-second wall-clock
timeout, no generation limit, population 10, mutation probability 0.9, lexicase
selection and `set_mix` crossover. Pooling was disabled. Instrumentation was
full, without cProfile. Seeds were 1 through 10 for 5queens and 11 through 20 for
grandparent. Versions ran consecutively for each seed, alternating original/new
and new/original. Runs were not executed concurrently.

The original used its saved argument payloads. The new payloads were verified
equal outside `mutation`, whose head-jump permission and complete-generator
deletion-attempt probability were both 0.1. The snapshots also differ in earlier
implementation changes; this is an original-versus-current comparison, not an
ablation isolating only the most recent mutation changes.

The agreed screening rule stopped new runs of a dataset after a timeout. A
historical cumulative-net bound could provisionally pause runs, but would need
confirmation against all ten freshly measured originals before screening. That
cumulative-time condition was not used here. Original control batches and the
other dataset continued after the new 5queens timeout.

## Results

Means and medians below use net `total_execution`, not wall-clock. The timeout
has no completed net timing and is not inserted as a 300-second net observation.

| Dataset | Original successes / executed | New successes / executed | Original mean, s | New mean, s | New mean change |
| --- | ---: | ---: | ---: | ---: | ---: |
| 5queens | 10/10 | 0/1 | 4.883228 | unavailable | unavailable |
| grandparent | 10/10 | 10/10 | 1.282888 | 0.487609 | -61.99% |

The first new 5queens run, seed 1, timed out at 300 wall-clock seconds. The
remaining nine new runs were not executed. The original solved that same seed
in 2.808704 net seconds. No ten-run mean or ten-run success rate is claimed for
the new 5queens configuration. Buffered net and progress metrics were not
exported before the timed-out process was killed, so this experiment does not
locate the slow phase or establish the reason for the regression.

| Grandparent metric | Original | New |
| --- | ---: | ---: |
| Median net time, s | 0.702202 | 0.465271 |
| Mean final generation | 3967.1 | 1000.7 |
| Mean fitness evaluations | 1222.0 | 446.1 |
| Mean clause-generation time, s | 0.088265 | 0.086938 |

Grandparent uses fewer evaluations and generations in this batch, unlike the
earlier shared-variation comparison where search counts were identical. This
supports a change in search behavior rather than only a timing fluctuation.
It does not establish a general improvement across tasks or isolate which
component of the current implementation caused it. The 5queens timeout prevents
accepting this configuration as an across-the-board improvement.

## Individual runs

All numeric entries are net seconds. Within a row, 5queens uses seed `run` and
grandparent uses seed `run + 10`. A dash means not executed, never zero cost.

| Run | Original 5queens | New 5queens | Original grandparent | New grandparent |
| --- | ---: | --- | ---: | ---: |
| 1 | 2.808704 | timeout | 0.653353 | 0.869569 |
| 2 | 2.813412 | — | 0.700735 | 0.253532 |
| 3 | 3.123534 | — | 1.989220 | 0.284814 |
| 4 | 3.600560 | — | 1.133671 | 0.350490 |
| 5 | 4.640493 | — | 0.703670 | 0.718974 |
| 6 | 9.942461 | — | 0.513641 | 0.425857 |
| 7 | 4.734701 | — | 5.573751 | 0.607481 |
| 8 | 8.259334 | — | 0.109414 | 0.111190 |
| 9 | 5.406131 | — | 0.582787 | 0.504686 |
| 10 | 3.502951 | — | 0.868636 | 0.749500 |

## Environment and source identity

Python 3.14.6, Clingo 5.8.0, Windows 11 Pro build 26200, Intel Core i7-13700H,
14 cores and 20 logical processors. The current dirty worktree is based on
`ff57d65e60cce685da8c8a79d47cc162128d5c05`.

Source SHA-256 concatenates each UTF-8 relative path and raw file bytes, first
ordinal-sorted `gentians/**/*.py`, then ordinal-sorted `gentians/**/*.lp`:

- Original: `4ace35a8420f5be661cd9c1b9a88c501d705528535b2f75644ccb95f34df2f47`.
- New: `8ba09663a794b68f7004300a788098f6512747b0f292bbbcb03e759e596467ea`.
- 5queens task: `7fd1ae9d51df466c1399ab40fe9e54d6c1ba6712c80efc3381db52981f7f7bb2`.
- Grandparent task: `d4a328a9272fa6d2bc58724b2fbccd55f84ebd762a71307b4a3f9eb723274918`.

The runner verified both source snapshots, the current source and both task
files remained unchanged throughout execution. No algorithm changes were made
during or after these measurements in this benchmark turn.

## Repeat with constraint deletion only

Later on 2026-09-07, structural relaxation was removed. For incomplete
hypotheses with positive and negative examples, mutation can delete constraints
but cannot add or replace them. Replacement is restricted to headed clauses.
Complete hypotheses retain constraint addition, replacement and deletion.
Dependency blocks and the nonempty-candidate invariant still apply; consequently,
a single-constraint incomplete hypothesis cannot lose its final clause.
The mutation factory and both 0.1 probability defaults remain unchanged.

The same paired protocol was repeated, including fresh original runs, under
`.benchmarks/block-mutation-no-relax/`. Its `run_paired.py`, snapshots and
`paired/protocol.json` preserve the executable protocol and source identities.
The new source hash is
`ff9eca645e43cbb3815fcf396510682ec65a5bb41c355c6a30f7ddd38bbfe31b`.
Original source and task hashes are unchanged. The runner verified all source
and task hashes again after execution. Before this repeat, 582 tests passed;
Ruff and type checks also passed.

| Dataset | Original successes / executed | New successes / executed | Original mean net, s | New mean net, s |
| --- | ---: | ---: | ---: | ---: |
| 5queens | 10/10 | 0/1 | 4.924175 | unavailable |
| grandparent | 10/10 | 10/10 | 1.547917 | 0.504041 |

New 5queens seed 1 again timed out after 300 wall-clock seconds. Its other
nine runs were skipped, not recorded as failures or zero-cost observations.
There is no completed net time or final generation count for that timeout.
Removing the relaxation scan therefore did not suffice to restore convergence
within the budget. The remaining restriction can limit exploration in a
constraint-only task, but this timeout alone does not isolate its causal role.

Grandparent's mean net time decreased by 67.44% against this fresh original.
Mean generations remained 3967.1 versus 1000.7, and mean fitness evaluations
1222.0 versus 446.1. Those counts match the preceding batch; the different
percentage improvement should not be interpreted as a new search improvement.
This remains a full-original-versus-current comparison, not a mutation-only
ablation.

| Run | Original 5queens | New 5queens | Original grandparent | New grandparent |
| --- | ---: | --- | ---: | ---: |
| 1 | 2.361298 | timeout | 0.712722 | 0.752058 |
| 2 | 2.945924 | — | 0.696511 | 0.233499 |
| 3 | 3.231454 | — | 2.498814 | 0.363819 |
| 4 | 4.039114 | — | 1.218948 | 0.403518 |
| 5 | 5.182188 | — | 0.807191 | 0.838117 |
| 6 | 8.748950 | — | 0.528834 | 0.452335 |
| 7 | 4.223560 | — | 7.447855 | 0.618975 |
| 8 | 8.652813 | — | 0.124064 | 0.127205 |
| 9 | 5.970005 | — | 0.593709 | 0.514527 |
| 10 | 3.886444 | — | 0.850519 | 0.736360 |

## Repeat allowing constraint replacement in incomplete candidates

On 2026-09-07, the paired protocol was repeated after permitting incomplete
candidates to replace a constraint with another constraint, without structural
relaxation checks. Appending constraints remains prohibited in that state.
Root-role protection, dependency closure and the mutation factory remain.

Artifacts are retained under `.benchmarks/block-mutation-constraint-replace/`.
Its `run_paired.py` reuses the preceding local paired runner with new output
paths and the preceding original batch as its provisional screening reference.
Configuration still comes from `shared-variation/new` in `experiments.toml`.
The original was freshly executed for all ten seeds of both datasets. Runtime,
task hashes, original source, 300-second timeout, unlimited generations and
instrumentation match the protocol above. New source SHA-256 is
`7d4449b5284e52a6f21f63fc3a3580520ecb2a83593670dfd06bd36b070974ae`.
All source and task hashes were checked again at completion.

| Dataset | Original successes / executed | New successes / executed | Original mean net, s | New mean net, s |
| --- | ---: | ---: | ---: | ---: |
| 5queens | 10/10 | 6/6 | 6.705552 | 11.930151 |
| grandparent | 10/10 | 10/10 | 1.770335 | 0.580864 |

The 5queens means use different sample counts and are not a paired effect
estimate. On the six shared seeds the original mean is 5.760263 seconds.
The six new runs accumulated 71.580904 net seconds, already exceeding all ten
originals at 67.055517 seconds. The remaining four new runs were therefore
omitted under the agreed cumulative-time screening rule. No timeout occurred.
Even zero additional cost could not produce a better ten-run mean.

Allowing replacement restored a solution for seed 1, previously timed out,
but did not make the current algorithm competitive with the original in this
batch. Grandparent's mean decreased by approximately 67.2%. Its search counts
remain unchanged from the preceding batches: 3967.1 versus 1000.7 mean
generations, and 1222.0 versus 446.1 evaluations. Timing variation between
batches is not evidence of another search improvement. This comparison still
contrasts full historical and current implementations, not a single-change
ablation.

All entries below are net seconds. A dash means not executed.

| Run | Original 5queens | New 5queens | Original grandparent | New grandparent |
| --- | ---: | ---: | ---: | ---: |
| 1 | 3.474065 | 26.432528 | 0.867665 | 0.984161 |
| 2 | 3.553531 | 7.586472 | 0.902454 | 0.320391 |
| 3 | 5.077832 | 5.024266 | 2.696687 | 0.356215 |
| 4 | 5.257474 | 7.389466 | 1.380316 | 0.414695 |
| 5 | 7.800075 | 10.667207 | 0.885954 | 0.853473 |
| 6 | 9.398599 | 14.480966 | 0.569640 | 0.557420 |
| 7 | 5.123109 | — | 8.608969 | 0.684892 |
| 8 | 12.696257 | — | 0.127420 | 0.130677 |
| 9 | 8.635609 | — | 0.663357 | 0.623942 |
| 10 | 6.038967 | — | 1.000884 | 0.882772 |
