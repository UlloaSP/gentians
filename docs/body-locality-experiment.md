# Body-local replacement at 80 percent

> Historical experiment. Body-local replacement was removed on 2026-09-08, together with its configuration and active matrix entries. The measurements below describe the implementation before removal.

## Change and protocol

On 2026-09-07, body-local replacement was implemented and compared against both
the historical original and the current policy before this change. Locality
tries to add, remove or replace one top-level body element while retaining the
exact canonical AST head. It does not require relaxation or assume preserved
coverage. One independent draw chooses local search with probability 0.8; the
remaining attempts use global replacement. If no legal local proposal exists,
local search falls back to global. Existing head-jump permission, completeness
protection, dependency closure, size limits and append restrictions remain.
Retries and complete reserve are disabled. Default body locality remains zero.
See [variation policy](variation-policy.md#replacement-candidates).

Configurations are `locality-80/current` and `locality-80/local80` in
`benchmarks/experiments.toml`. The current source was copied before the change;
the new source was copied after testing. The historical original uses the
verified snapshot retained from earlier experiments. All three were executed
again, not represented by timings copied from history.

Each dataset/version had ten planned runs, a 300-second wall-clock timeout and
no generation cap. Seeds are 1–10 for 5queens and 11–20 for grandparent. Population
is 10, mutation probability 0.9, selection lexicase, crossover set_mix, scoring
cov_program, pooling disabled. Instrumentation is full without cProfile. Runs
execute serially, rotating original/current/local80 order by seed. Both controls
complete all ten runs. The new version retains the agreed timeout and cumulative
net-time screening rule. A historical total can provisionally pause runs, but
screening is confirmed against the ten fresh originals and pending runs resume
when that comparison still permits improvement.

All 53 executed runs found solutions. No timeout occurred. Local80's first three
5queens runs totaled 110.202760 net seconds, exceeding all ten originals at
59.288660 seconds. Its remaining seven runs were not executed. Thus no ten-run
mean or success rate is claimed for local80 on 5queens.

## Results on matched seeds

Mean net `total_execution` seconds, using the same seeds in each row.

| Dataset | Matched seeds | Original | Current | Local80 |
| --- | ---: | ---: | ---: | ---: |
| 5queens | 1–3 | 4.027862 | 11.341953 | 36.734253 |
| grandparent | 11–20 | 1.535551 | 0.569444 | 0.395326 |

The complete ten-run 5queens controls have means of 5.928866 seconds for original
and 8.611263 for current; those means must not be directly compared with the
three-run local80 mean as a paired estimate.

| Dataset | Metric, matched seeds | Original | Current | Local80 |
| --- | --- | ---: | ---: | ---: |
| 5queens | Mean final generation | 538.3 | 3072.7 | 18716.0 |
| 5queens | Mean fitness evaluations | 458.7 | 2054.0 | 8488.3 |
| grandparent | Mean final generation | 3967.1 | 1000.7 | 527.6 |
| grandparent | Mean fitness evaluations | 1222.0 | 446.1 | 265.3 |

Local80 improved grandparent's observed mean time by 30.6% versus current, with
fewer evaluations. On the three measured 5queens seeds it needed about 4.13 times
as many evaluations as current and was substantially slower. This is not merely
an index-initialization cost: the search trajectory changed and required many
more candidate solves. The evidence does not establish why these particular
syntactic neighborhoods are unfavorable or that every locality definition would
fail. Three screened runs are not a general success-rate estimate.

Locality remains an explicit experimental option, not a new default. This
configuration does not deliver a general improvement across the two tasks.

## Time decomposition on matched seeds

Mean seconds. Grounding, solving and closure sum their phase-specific metrics;
Python is the residual of net total after those categories.

| Dataset | Version | Grounding | Solving | Closure | Python |
| --- | --- | ---: | ---: | ---: | ---: |
| 5queens | Original | 1.040909 | 0.728818 | 0.040654 | 2.217481 |
| 5queens | Current | 4.695596 | 1.329431 | 0.266673 | 5.050253 |
| 5queens | Local80 | 17.288225 | 3.529424 | 1.982186 | 13.934419 |
| grandparent | Original | 0.536366 | 0.092378 | 0.247595 | 0.659212 |
| grandparent | Current | 0.210049 | 0.050855 | 0.062460 | 0.246080 |
| grandparent | Local80 | 0.142923 | 0.043405 | 0.042528 | 0.166470 |

## Index-only diagnostic

The separate `profile_neighborhood.py` diagnostic traced Python allocations
only during index construction. These timings include tracemalloc overhead and
are not end-to-end benchmark comparisons. Neighbor counts precede candidate,
pool and closure filtering, so they are not counts of legal offspring.

| Dataset | Clauses | With neighbors | Median neighbors | Maximum neighbors | Postings | Traced retained bytes | Traced build, s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5queens | 4797 | 4797 | 38 | 219 | 24118 | 5135709 | 0.384557 |
| grandparent | 326 | 322 | 10 | 21 | 1217 | 162360 | 0.023337 |

The index stores full-body and one-deletion postings, not all neighbor pairs.
It conservatively matches existing variable names and arithmetic spelling;
additional alpha-renamings and algebraic equivalences are not inferred.

## Individual net times

A dash means not executed, not zero cost. Run i uses seed i for 5queens and i+10
for grandparent.

| Dataset | Run | Original | Current | Local80 |
| --- | ---: | ---: | ---: | ---: |
| 5queens | 1 | 4.075074 | 22.628728 | 24.277016 |
| 5queens | 2 | 3.849862 | 7.407315 | 27.807003 |
| 5queens | 3 | 4.158649 | 3.989816 | 58.118740 |
| 5queens | 4 | 5.026206 | 5.981900 | — |
| 5queens | 5 | 6.145639 | 9.283739 | — |
| 5queens | 6 | 9.465806 | 10.346433 | — |
| 5queens | 7 | 4.761655 | 6.227882 | — |
| 5queens | 8 | 10.346107 | 4.828777 | — |
| 5queens | 9 | 6.898317 | 4.466248 | — |
| 5queens | 10 | 4.561345 | 10.951790 | — |
| grandparent | 1 | 0.782091 | 0.967135 | 0.873654 |
| grandparent | 2 | 0.780599 | 0.275728 | 0.199906 |
| grandparent | 3 | 2.303692 | 0.314221 | 0.322413 |
| grandparent | 4 | 1.404650 | 0.417184 | 0.893530 |
| grandparent | 5 | 0.922273 | 0.903852 | 0.473239 |
| grandparent | 6 | 0.594003 | 0.538327 | 0.235622 |
| grandparent | 7 | 6.648048 | 0.719757 | 0.229451 |
| grandparent | 8 | 0.148990 | 0.134491 | 0.138838 |
| grandparent | 9 | 0.737423 | 0.613849 | 0.249626 |
| grandparent | 10 | 1.033739 | 0.809892 | 0.336982 |

## Reproduction and source identity

All builds, snapshots and raw outputs live under the ignored directory
`.benchmarks/experiments/locality-80/`. Nothing in that directory is intended for Git.

- `run_triple.py` executes the protocol, refuses to overwrite outputs and checks
  source/task hashes at completion. It uses the existing profiling worker and
  aggregator, not separate timing definitions.
- `triple/protocol.json` records configs, paths, versions, order and screening.
- `triple/{original,current,local80}/` contains logs, CSVs and dashboards.
- `summarize.py` recomputes matched aggregates without editing raw results.
- `profile_neighborhood.py` and its JSON preserve the index-only diagnostic.

Python 3.14.6, Clingo 5.8.0, Windows 11 build 26200, Intel Core i7-13700H,
14 cores and 20 logical processors. Worktree based on
`467f0651900a2295f3efd813e63c31680dee502e`.

Source hashes:

- original: `4ace35a8420f5be661cd9c1b9a88c501d705528535b2f75644ccb95f34df2f47`.

- current: `0cbb515d9aa640b2d12f4035aecc000fe36c03686aaf2d696477ccabddde0dfe`.

- local80: `19ae9997b3cde89018e805ca2da5779ec1e0a8823865747e47ee7bcbd96f9590`.

Task hashes:

- 5queens: `7fd1ae9d51df466c1399ab40fe9e54d6c1ba6712c80efc3381db52981f7f7bb2`.

- grandparent: `d4a328a9272fa6d2bc58724b2fbccd55f84ebd762a71307b4a3f9eb723274918`.

The runner verified all sources and tasks remained unchanged during execution.
Verification before measurement: 605 tests passed; Ruff and type checks passed.
Independent review found no severe issues.
