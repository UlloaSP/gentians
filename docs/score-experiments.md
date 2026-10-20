# Positive and negative score weights

The active local suite compares **1:1 and 10:1 positive:negative weights** with
steady state, populations **10 and 100**, five matched seeds **43–47**, and a
**300-second wall timeout per run**. The sole configuration is
[`benchmarks/experiments.toml`](../benchmarks/experiments.toml).

```powershell
uv run python benchmarks/run_experiments.py --list
uv run python benchmarks/run_experiments.py
uv run python benchmarks/run_experiments.py --summary
```

The default command runs the four configurations sequentially. To run only one:

```powershell
uv run python benchmarks/run_experiments.py score-weights/population-10-ratio-10-1
```

## Tasks and known solution

The synthetic `score_coloring_balanced`, `score_coloring_positive_heavy`, and
`score_coloring_negative_heavy` tasks have respectively **24/24**, **48/12**,
and **12/48** positive/negative examples. Each example is one complete coloring
of a six-node cycle and explicitly excludes every other color. Every negative
has adjacent nodes of the same color. Colors occur symmetrically in each class.
The smaller samples are nested within the larger samples. The three tasks share
identical background and bias; only their example samples differ.

Each task's `reference.lp` supplies a perfect hypothesis:

```prolog
red(X); green(X); blue(X) :- node(X).
:- edge(X,Y), red(X), red(Y).
:- edge(X,Y), green(X), green(Y).
:- edge(X,Y), blue(X), blue(Y).
```

The background contains only nodes and edges. One disjunctive rule generates the
alternative stable models; three integrity constraints reject conflicts. No
generator or reference constraint is supplied as background. Removing any one
of these four reference clauses breaks perfect coverage. This is an ablation of
the reference, not a uniqueness proof over every legal alternative hypothesis.
Tests independently solve each example program and check that all reference
clauses survive actual clause generation.

Reproduce the synthetic task files deterministically:

```powershell
uv run python benchmarks/generate_score_tasks.py
```

`coloring` and `set_partition_sum` are additional unchanged controls: disjunction
and constraints in the former, an aggregate rule and a constraint in the latter.
`latin_square` was excluded after one preliminary pilot's independent checker
returned `status=error, valid=null` despite a learner-reported solution. No
examples were checked in that failed validation; this is not evidence that the
hypothesis was semantically wrong. The verified `set_partition_sum` control
avoids counting an unknown result as evidence about score quality.

## Score and controls

For both nonempty classes, define `TPR = TP / P` and `TNR = TN / N`. We use:

```text
weighted_accuracy = (w_pos * TPR + w_neg * TNR) / (w_pos + w_neg)
score = exp(10 * (2 * weighted_accuracy - 1))
```

The baseline is exactly the existing `exp(10 * (TPR - FPR))` mathematically.
The normalization keeps the score in `[exp(-10), exp(10)]` for either ratio.
The perfect score is unchanged. Weights change preference, never coverage,
task legality, or the requirement for a verified perfect solution. One-class
tasks keep their original score. No partial hypothesis is promoted to success.

This task has actual ASP candidates whose ranking changes: on the balanced
variant, one four-clause hypothesis covers **3 positives and avoids 24 negatives**;
another covers **6 positives and avoids 17 negatives**. The first wins at 1:1;
the second wins at 10:1. `tests/test_score_benchmarks.py` fixes both programs and
checks the whole-program coverage and ranking.

Selection is tournament with a 50% sample in every configuration, so the
configured scalar score influences parent choice. Default lexicase selects by
individual example behavior and does not directly use the scalar weights.
All other operators retain SDK defaults. Clause generation uses a single
process (`clause_generation.clingo_arguments=[]`) for local repeatability.

Compare verified perfect-solution rate, time/evaluations to success, positive
coverage, and negatives avoided. Raw score values from different weight ratios
do not represent the same quality objective, despite their common numeric range.
Five seeds can reveal large effects; they do not establish a reliable success
probability. These tiny tasks do not establish performance on Alzheimer or on
arbitrary ASP programs.

## Artifacts and budget

The runner saves full raw metrics, the best hypothesis (including on timeout),
independent per-example validation, and the existing schema-14 Vite dashboard.
No schema or chart changes are needed. A timeout is an incomplete search, not
necessarily an absent hypothesis. The learner has up to five additional seconds
to close metrics; independent validation has its own 60-second budget.

The complete suite contains 100 runs (4 configurations × 5 tasks × 5 seeds).
Its worst-case learner budget is 8 hours 20 minutes, plus validation and I/O.
The 300-second limit applies to each run, not to the full suite. Local calibration
results and their limitations are recorded below.

The previous TOML and local index were backed up under
`.benchmarks/experiments/.imports/score-suite-20261016T133539Z/` before replacement.
Old result directories remain untouched. Remote Slurm jobs and their checkout
are independent of this local suite.

## Local measurements — 2026-10-16

All **100/100 saved hypotheses** passed independent per-example validation;
every winner contains both headed rules and integrity constraints. There were
**no learner timeouts or nonzero exit codes**. The longest learner process took
**4.231 seconds wall time**, well within the 300-second budget. The full driver
completed in **267.814 seconds**, before the two validation rechecks described
below. Summed learner net time was **98.773 seconds**; summed worker wall time
was **178.212 seconds**. Validation, process startup, instrumentation, and
aggregation explain why these are different measurements.

Each cell below is **mean fitness evaluations / mean net seconds**, across
five matched seeds. Net seconds are the recorded `total_execution` metric.

| Task | Pop. 10, 1:1 | Pop. 10, 10:1 | Pop. 100, 1:1 | Pop. 100, 10:1 |
| --- | ---: | ---: | ---: | ---: |
| `score_coloring_balanced` | 128.8 / 1.074 | 83.2 / 0.713 | 204.6 / 1.590 | 157.0 / 1.280 |
| `score_coloring_positive_heavy` | 85.4 / 0.955 | 90.0 / 0.941 | 174.6 / 1.840 | 157.0 / 1.658 |
| `score_coloring_negative_heavy` | 140.6 / 1.398 | 83.2 / 0.867 | 194.4 / 1.881 | 157.0 / 1.691 |
| `coloring` | 213.8 / 0.288 | 201.0 / 0.289 | 295.0 / 0.396 | 331.2 / 0.401 |
| `set_partition_sum` | 75.8 / 0.386 | 146.4 / 0.599 | 220.4 / 1.001 | 162.0 / 0.507 |

At population 10, weighting positives 10:1 reduced mean evaluations on the
balanced and negative-heavy synthetic tasks, while the positive-heavy sample
was slightly worse. At population 100, it reduced evaluations on all three
synthetic samples. The unchanged controls show mixed results: for example,
`set_partition_sum` worsens at population 10 and improves at population 100.
No ratio dominates every task and population. All runs reach perfect coverage,
so this suite distinguishes search effort and intermediate coverage tradeoffs,
not final accuracy. Five seeds and these small tasks do not support statistical
significance or generalization to harder benchmarks.

Environment: Windows 11 build 26300, Intel Core i7-13700H (14 cores, 20 logical
processors), Python 3.14.6, Clingo 5.8.2. Configurations ran sequentially on the
same desktop; other activity was not isolated. The source was a dirty worktree
based on `ec23ae5ff7107ecdafeb683f9df93826e375bef6`. Each manifest records
the actual source, task, and runtime fingerprints. Small timing differences
are weaker evidence than the deterministic evaluation counts.

### Calibration and validation audit

An earlier, more difficult prototype used three default-negated normal rules
and three constraints. All four 30-second one-seed pilots timed out. Their
inputs and results were archived under `calibration-30s/`; they are not the
tasks or runs reported above. The final disjunctive generator focuses the
comparison on rejecting assignments with learned constraints.

The first full attempt stopped on a Windows `WinError 5` while atomically
replacing a hypothesis checkpoint. A real reader handle that did not share
delete access reproduced the failure. The checkpoint now retries temporary
reader locks for at most 20 attempts with 50 ms pauses, and still raises on
persistent failure. Both cases have regression tests; a real 150 ms lock
recovered in 204.5 ms. The interrupted attempt was preserved under
`failed-full-suite-before-checkpoint-retry/`.

In the subsequent full run, two independent checker processes returned
`status=error, valid=null` with an empty error string: seed 47 of
`score_coloring_negative_heavy`, population 100, at both weight ratios.
The saved hypotheses passed direct independent checks, and 30 additional fresh
checker processes also passed. The original checker failure's cause remains
unknown; it must not be counted as a semantic failure or claimed fixed.
Both canonical validations were rerun successfully using `validate_run`,
and the native `write_outputs` producer regenerated their CSV indexes and
dashboards. Original reports, partial example programs, CSVs, and dashboards
were preserved under `validation-rechecks/`. No learner was rerun or result
score edited during this revalidation.

All audit paths are relative to
`.benchmarks/experiments/.imports/score-suite-20261016T133539Z/`.
The active results are under `.benchmarks/experiments/score-weights/`.
The four schema-14 dashboard payloads and index were served successfully by
the local Vite preview. All 32 previously recorded result-file hashes remained
unchanged.
