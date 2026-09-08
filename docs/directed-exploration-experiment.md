# Directed exploration experiments

> Historical experiment. Duplicate retries and complete-candidate reserves were removed on 2026-09-08, together with their active matrix entries. Results below describe the measured implementation before removal.

## Implementation and protocol

On 2026-09-07, two opt-in controls were implemented and measured independently
and together. Mutation may retry a processed duplicate up to three additional
times, from the same input and without additional candidate solves. Classification
and the complete-generator deletion permission are computed once per mutation
decision. Replacement may reserve one discovered complete candidate, admitting
it at lower fitness when the reserve is empty without evicting the best member.
Neither control changes task semantics, closure, scoring, or crossover.
Both defaults remain zero because these measurements do not justify enabling them.
See [variation policy](variation-policy.md) for edge cases and exact guarantees.

The four configurations live in `benchmarks/experiments.toml` under
`directed-exploration/{control,retries,reserve,combined}`. Control is the current
constraint-replacement policy with both controls disabled, not the historical
original. Each variant was compared with a newly executed historical original.
The original comparison includes earlier implementation differences; differences
between the four current variants isolate the two configuration controls.

Each dataset/version had ten planned runs, 300-second wall-clock timeout,
unlimited generations, population 10, mutation probability 0.9, lexicase,
set_mix crossover, and no pooling. Seeds are 1–10 for 5queens and 11–20 for
grandparent. Instrumentation is full, without cProfile. Runs execute serially,
original/new alternating within each paired batch. The four batches themselves
execute consecutively, so between-batch time variation remains a limitation.

The agreed screening rule stops a new dataset after timeout or once accumulated
net time exceeds all ten fresh originals. A historical bound may provisionally
pause new runs, but screening is confirmed against the fresh complete control.
Other datasets continue. Reserve and combined each omit only seed 10 of 5queens.
Their nine runs cost 68.831078 and 79.120983 seconds, already above the ten-run
original totals of 55.689605 and 55.001037 seconds. All 158 executed runs solved
their tasks. There were no timeouts; two planned runs were not executed.

Artifacts and reproduction:

- `.benchmarks/experiments/directed-exploration/run_all.py` runs the four paired batches.
- `run_paired.py <variant>` loads the existing TOML configuration and reuses
  profiling workers and aggregators. It refuses to overwrite results.
- `<variant>/paired/protocol.json` retains source/task hashes, exact configuration,
  run order, results and screening decisions; `original/` and `new/` retain
  raw metrics, logs and dashboards.
- `summarize.py` reads those artifacts without modifying them.

## Results on shared seeds

Times are mean net `total_execution` seconds. Each row compares the same seeds
on both sides; reserve/combined 5queens rows use nine pairs, not an imputed tenth.

| Variant | Dataset | Pairs | Original, s | Current, s | Delta | Evaluations original | Evaluations current |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| control | 5queens | 10 | 5.001671 | 7.050631 | 40.97% | 1029.6 | 1604.1 |
| control | grandparent | 10 | 1.346032 | 0.493360 | -63.35% | 1222.0 | 446.1 |
| retries | 5queens | 10 | 5.276646 | 7.070151 | 33.99% | 1029.6 | 1540.5 |
| retries | grandparent | 10 | 1.546715 | 1.239510 | -19.86% | 1222.0 | 1057.8 |
| reserve | 5queens | 9 | 5.679521 | 7.647898 | 34.66% | 1058.2 | 1502.8 |
| reserve | grandparent | 10 | 1.510040 | 0.585453 | -61.23% | 1222.0 | 446.1 |
| combined | 5queens | 9 | 5.579752 | 8.791220 | 57.56% | 1058.2 | 1823.3 |
| combined | grandparent | 10 | 1.483777 | 1.243995 | -16.16% | 1222.0 | 1057.8 |

Retries reduced mean generations in 5queens from 2238.0 to 1549.4 versus current
control, but evaluations only fell from 1604.1 to 1540.5. Mean time remained about
7.05–7.07 seconds, above the original. Fewer generations did not establish better
end-to-end efficiency. In grandparent, retries increased evaluations from 446.1
to 1057.8; the combined variant has those same counts. Reserve alone retains
control's grandparent counts of 1000.7 generations and 446.1 evaluations.

No tested variant outperformed its original 5queens control. All current
variants were faster than their original grandparent control in these batches,
but retries and combined were worse than the current policy without retries.
Reserve and combined were screened in 5queens; their partial means must not be
compared with ten-seed current-control means as an unbiased effect estimate.
These results reject enabling either feature by default on this evidence. They
do not establish that every possible quota or retry count would fail, nor that
completeness-directed search is generally ineffective.

## Time decomposition on shared seeds

Grounding, solving and closure sum their recorded phase-specific metrics. Python
is the remainder of net total after those three types. Values are mean seconds.

| Variant | Dataset | Version | Grounding | Solving | Closure | Python |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| control | 5queens | original | 1.895497 | 0.576167 | 0.091115 | 2.438892 |
| control | 5queens | new | 2.872109 | 0.756153 | 0.156758 | 3.265610 |
| control | grandparent | original | 0.471990 | 0.069501 | 0.224121 | 0.580420 |
| control | grandparent | new | 0.187073 | 0.033924 | 0.056891 | 0.215472 |
| retries | 5queens | original | 2.016431 | 0.638706 | 0.098097 | 2.523412 |
| retries | 5queens | new | 2.841365 | 0.840319 | 0.134471 | 3.253997 |
| retries | grandparent | original | 0.536906 | 0.095118 | 0.252527 | 0.662165 |
| retries | grandparent | new | 0.455210 | 0.081626 | 0.211897 | 0.490777 |
| reserve | 5queens | original | 2.101460 | 0.836416 | 0.102680 | 2.638965 |
| reserve | 5queens | new | 2.878272 | 1.026321 | 0.147368 | 3.595937 |
| reserve | grandparent | original | 0.532719 | 0.091229 | 0.243189 | 0.642903 |
| reserve | grandparent | new | 0.217796 | 0.051409 | 0.065164 | 0.251083 |
| combined | 5queens | original | 2.064687 | 0.831868 | 0.100782 | 2.582416 |
| combined | 5queens | new | 3.531667 | 1.138624 | 0.159889 | 3.961040 |
| combined | grandparent | original | 0.517901 | 0.088148 | 0.242563 | 0.635164 |
| combined | grandparent | new | 0.457105 | 0.080833 | 0.212461 | 0.493596 |

## Individual net times

A dash means not executed, not zero cost. Each row uses seed `run` for 5queens
and seed `run + 10` for grandparent.

| Variant | Run | Original 5queens | Current 5queens | Original grandparent | Current grandparent |
| --- | ---: | ---: | ---: | ---: | ---: |
| control | 1 | 3.223482 | 15.914205 | 0.726439 | 0.781527 |
| control | 2 | 3.172257 | 6.330076 | 0.742729 | 0.239058 |
| control | 3 | 3.495024 | 3.347249 | 2.039887 | 0.298373 |
| control | 4 | 4.139259 | 4.977879 | 1.248939 | 0.381836 |
| control | 5 | 5.281418 | 7.704087 | 0.793693 | 0.765261 |
| control | 6 | 7.935017 | 9.004526 | 0.474235 | 0.443497 |
| control | 7 | 3.856233 | 5.640156 | 5.907738 | 0.667644 |
| control | 8 | 8.833719 | 3.986186 | 0.107790 | 0.106492 |
| control | 9 | 5.909048 | 3.955755 | 0.553273 | 0.506536 |
| control | 10 | 4.171250 | 9.646186 | 0.865596 | 0.743377 |
| retries | 1 | 2.671487 | 6.604201 | 0.810539 | 2.331474 |
| retries | 2 | 3.112186 | 4.715185 | 0.799599 | 0.288339 |
| retries | 3 | 3.482505 | 10.824204 | 2.280982 | 2.745601 |
| retries | 4 | 4.108714 | 11.280912 | 1.417161 | 0.642415 |
| retries | 5 | 5.530857 | 7.948212 | 0.826851 | 0.846452 |
| retries | 6 | 7.927893 | 3.908548 | 0.702065 | 0.130323 |
| retries | 7 | 4.063130 | 10.290853 | 6.908599 | 2.341143 |
| retries | 8 | 10.172271 | 4.951255 | 0.125176 | 0.542912 |
| retries | 9 | 7.005611 | 3.596519 | 0.633045 | 2.342669 |
| retries | 10 | 4.691805 | 6.581624 | 0.963133 | 0.183772 |
| reserve | 1 | 3.326724 | 10.768878 | 0.786355 | 0.910327 |
| reserve | 2 | 3.483292 | 7.537233 | 0.951169 | 0.313511 |
| reserve | 3 | 3.956427 | 4.729385 | 2.330048 | 0.333162 |
| reserve | 4 | 4.437456 | 10.581319 | 1.312690 | 0.434890 |
| reserve | 5 | 5.836679 | 7.921910 | 0.806152 | 0.828786 |
| reserve | 6 | 8.861736 | 5.906740 | 0.580045 | 0.546624 |
| reserve | 7 | 4.293264 | 6.548941 | 6.597767 | 0.673195 |
| reserve | 8 | 9.809993 | 7.826969 | 0.141727 | 0.125419 |
| reserve | 9 | 7.110120 | 7.009704 | 0.617646 | 0.662365 |
| reserve | 10 | 4.573913 | — | 0.976800 | 1.026249 |
| combined | 1 | 3.138886 | 7.627989 | 0.784494 | 2.339431 |
| combined | 2 | 3.727714 | 5.738918 | 0.787509 | 0.285358 |
| combined | 3 | 3.780867 | 12.162840 | 2.241801 | 2.790812 |
| combined | 4 | 4.626065 | 8.000754 | 1.380951 | 0.617236 |
| combined | 5 | 5.843038 | 7.839387 | 0.822162 | 0.808202 |
| combined | 6 | 8.661819 | 8.536776 | 0.541066 | 0.138058 |
| combined | 7 | 4.409405 | 12.565262 | 6.387399 | 2.212392 |
| combined | 8 | 9.505707 | 4.036694 | 0.121178 | 0.524727 |
| combined | 9 | 6.524269 | 12.612363 | 0.618107 | 2.516019 |
| combined | 10 | 4.783268 | — | 1.153101 | 0.207715 |

## Environment and source identity

Python 3.14.6, Clingo 5.8.0, Windows 11 build 26200, Intel Core i7-13700H,
14 cores and 20 logical processors. Dirty worktree based on
`dfe7571c028c370d75c9afa42e664732748e0e08`.

Original source SHA-256:
`4ace35a8420f5be661cd9c1b9a88c501d705528535b2f75644ccb95f34df2f47`.
Current source SHA-256, identical across all four variants:
`0cbb515d9aa640b2d12f4035aecc000fe36c03686aaf2d696477ccabddde0dfe`.
Task hashes:
5queens `7fd1ae9d51df466c1399ab40fe9e54d6c1ba6712c80efc3381db52981f7f7bb2`;
grandparent `d4a328a9272fa6d2bc58724b2fbccd55f84ebd762a71307b4a3f9eb723274918`.
Each runner verified sources and tasks again after completing its batch.

Final verification: 592 tests passed; Ruff and type checks passed. Independent
review found no critical or important issues. No source changes were made during
the benchmark batches.
