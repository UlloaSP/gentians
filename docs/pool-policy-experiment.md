# Frozen pools and reproductive search policies

> Historical experiment. Adaptive renewal and reproductive parent selection were removed on 2026-09-08, together with their active matrix entries. Results below describe the measured implementation before removal.

Configuration location: this matrix now lives in `benchmarks/experiments.toml`
under `pool-policy/` IDs. Worker arguments and output folders are unchanged.
The ID change makes old manifests stale; historical measurements below are not
rewritten. Commands below select named entries, not every matrix in the file.

Historical experiment: references below to `#bias`, metarules, or atomic bundles
describe the measured implementation, not the current language. That support has
been removed; see [the current contract](language-bias.md#removed-meta-programming-directives).

## Question and implementation

The experiment separates evaluator reuse from the change in search caused by a
restricted clause pool. A faster grounding operation is useful only if total
time to a perfect hypothesis improves without a lower success rate.

The normal GA remains the default. The experimental GA freezes a subset of the
prepared `ClauseSpace` for each epoch. Background, isolated example contexts,
coverage rules and all guarded pool clauses are grounded together. Candidate
evaluation changes only the selected external activators. A new pool creates a
new control; it does not assume that an earlier grounding can anticipate future
clause dependencies. Compilation of the static coverage AST is reused between
epochs. Activator symbols are cached and only changed activators are assigned.

`HypothesisGenerator` remains the authority for candidate validity. Retained
programs, generated neighbors and random programs include complete bundles and
dependency closures. Pool size is a target that these complete programs may
exceed. The pool does not rank clauses by an assumed independent coverage.

## Search policies

Fitness retention preserves the best complete programs and the global champion.
Behavior retention starts with the champion and greedily prefers programs that
cover missing positive examples or avoid negative examples shared by those
already retained. Behavioral distance breaks ties before score. This is diversity
on the observed task, not ASP equivalence.

Reproductive retention cycles through behavior specialists, parents with high
observed improvement rates and parents with little evidence, after the champion.
Small retention counts may not include every category in that cycle. Each
reproduction gives each distinct parental genome one opportunity. A fresh child
strictly better than the better parent gives both parents one success. Invalid
offspring and duplicate genomes give zero successes. The value is
`(successes + 1) / (opportunities + 2)`. This is a contextual heuristic, not a
causal attribution to a parent or a clause. Evidence is halved at pool renewal
and discarded for parents outside the live population and champion.

`reproductive_lexicase` retains ordinary lexicase filtering and uses those values
as positive selection weights only among its survivors. It also works without
pooling. Normal lexicase preserves its original random-number sequence.

Neighbor filling aims to spend half the capacity remaining after retention on
legal append or same-head replacement moves. Whole programs can overshoot that
target. Global random valid programs fill the remaining capacity; unsuccessful
sampling is bounded. No policy names a benchmark predicate or assumes a target
program shape.

Fixed renewal uses an interval in generations. Adaptive renewal waits for that
many transitions without a better score or a previously unseen behavior, then
renews after either its fresh-evaluation budget or 80% duplicate transitions.
Initialization and refill evaluations count toward the epoch budget; duplicates
count final offspring already in the evaluation cache. A hard epoch-age cap of
ten intervals prevents indefinite residence in a pool. It does not cap the
number of generations in the search.

## Protocol

`benchmarks/experiments.toml` defines nine configurations: unrestricted
control, restricted search with fresh solver, matched persistent solver, behavior
retention, reproductive retention, neighbor filling, adaptive renewal,
unrestricted reproductive selection and a combined variant. Each isolated policy
states its comparator; the combined variant is not an ablation.

Every configuration uses the same ten seeds per dataset, a 100-second wall-clock
timeout, and `iterations_genetic=0`. The datasets are `5queens` and `grandparent`.
Pool variants use target size 64, interval 50, evaluation budget 50 and retention
count 3. Generality of semantics is also tested using small programs with
disjunction, choice/cardinality heads, recursion, default and strong negation,
aggregates, conditional literals, context constraints and inconsistent programs.
Two benchmark tasks alone cannot establish a general performance advantage.

Light instrumentation keeps canonical timings, GA progress and per-epoch pool
JSONL. It omits detailed clause, operator, quality and Clingo-statistic logging
and deliberately produces no dashboard. Omitted metrics are not zero.
Pool rows record effective size, preparation and solver-setup time, transitions,
fresh evaluations, duplicates, best score and reason for ending the epoch.

```powershell
uv run python benchmarks/run_experiments.py pool-policy/control pool-policy/reproductive_retention
uv run python benchmarks/run_experiments.py pool-policy/control pool-policy/reproductive_retention --summary
```

Report success and timeouts for every configuration. `total_execution` is the
canonical net time and its solved-run mean must be identified as such. PAR-1
wall-clock penalizes unsuccessful runs with 100 seconds; it is a timeout-aware
operational measure, not a replacement for `total_execution`. Generations and
fresh evaluations expose changes in convergence. Light results must not be
directly compared with the older heavily instrumented experiment as if only the
algorithm had changed.

The runner terminates timed-out processes forcibly. Their buffered timing, GA
and epoch records may therefore be absent. The summary does not invent partial
progress: generation, evaluation and net-time means use completed successful
runs only. Timeout counts and PAR-1 include censored runs. The summary rejects
artifacts whose manifest does not match the selected configuration.

## Matched evaluator replay

```powershell
uv run python benchmarks/profile_pool_evaluator.py --datasets 5queens grandparent --seeds 1 2 3 --candidates 100 --epoch-size 50 --repeats 3 --out-dir .benchmarks/experiments/pool-evaluator
```

Replay evaluates exactly the same valid candidate sequence with fresh controls
and with one frozen control per batch. It checks exact coverage equality and
includes pool construction and solver setup in the comparison. Candidate
generation is excluded and the sequence and hash are retained. The replay pool
is the union of the forthcoming batch, an optimistic assumption unavailable to
the real search. Replay cannot demonstrate faster convergence.

## Results

The evaluator replay completed with exact coverage equality for all six
100-candidate workloads. Each workload was timed three times in alternating
fresh/pooled order. Means below include setup and evaluation of 100 candidates;
the nine timings per row are repetitions of three seeds, not nine independent
searches.

| Dataset | Fresh evaluator | Frozen-pool evaluator | Change |
|---|---:|---:|---:|
| 5queens | 0.399411 s | 0.243849 s | -38.9% |
| grandparent | 0.062076 s | 0.027701 s | -55.4% |

There were 100 grounding calls in the fresh replay and two in the pooled replay.
These measurements establish a local saving for those workloads, not faster
learning. Raw workloads, hashes, timings and environment are in
`.benchmarks/experiments/pool-evaluator/replay.json`.

Environment: Python 3.14.6, Clingo 5.8.0, Windows 11, Intel Core i7-13700H.
The base revision is `ff57d65e60cce685da8c8a79d47cc162128d5c05`, with the
uncommitted implementation described here. Searches ran sequentially under the
same matrix and machine, without concurrent benchmark runs. The task seeds were
1 through 10 for 5queens and 11 through 20 for grandparent.

### Whole-search results

All nine configurations completed ten runs per dataset: 179 solutions in 180
runs. The only timeout was `combined` on grandparent, run 9 (seed 19).
Net time, generation, evaluation and grounding-call means below use solved runs;
PAR-1 includes all ten runs, assigning 100 seconds to the timeout. All times are
seconds. Grounding calls include clause-space generation.

#### 5queens

| Configuration | Solved | Net time | PAR-1 | Generations | Evaluations | Ground calls |
|---|---:|---:|---:|---:|---:|---:|
| control | 10/10 | 6.283 | 6.879 | 1412.1 | 1029.6 | 1030.6 |
| pool_fresh | 10/10 | 18.584 | 19.304 | 3632.3 | 3027.6 | 3028.6 |
| pool_persistent | 10/10 | 9.560 | 10.275 | 3632.3 | 3027.6 | 74.2 |
| behavior | 10/10 | 11.967 | 12.725 | 5122.9 | 4051.8 | 103.9 |
| reproductive_retention | 10/10 | 8.932 | 9.628 | 3164.4 | 2711.7 | 64.8 |
| neighbors | 10/10 | 10.163 | 10.855 | 3535.0 | 3021.6 | 72.2 |
| adaptive | 10/10 | 21.379 | 22.576 | 17754.3 | 9365.0 | 38.6 |
| reproductive_selection | 10/10 | 12.017 | 12.693 | 3428.9 | 2291.4 | 2292.4 |
| combined | 10/10 | 21.694 | 22.851 | 18349.3 | 9606.7 | 39.3 |

#### grandparent

| Configuration | Solved | Net time | PAR-1 | Generations | Evaluations | Ground calls |
|---|---:|---:|---:|---:|---:|---:|
| control | 10/10 | 1.522 | 2.113 | 3967.1 | 1222.0 | 1223.0 |
| pool_fresh | 10/10 | 5.386 | 6.098 | 6532.6 | 2121.2 | 2122.2 |
| pool_persistent | 10/10 | 5.402 | 6.085 | 6532.6 | 2121.2 | 132.2 |
| behavior | 10/10 | 1.155 | 1.639 | 1656.7 | 877.8 | 34.7 |
| reproductive_retention | 10/10 | 0.518 | 1.015 | 632.8 | 399.1 | 14.2 |
| neighbors | 10/10 | 8.737 | 9.617 | 12814.0 | 3298.4 | 257.8 |
| adaptive | 10/10 | 3.384 | 3.988 | 6827.6 | 2239.8 | 82.7 |
| reproductive_selection | 10/10 | 2.468 | 3.061 | 6591.0 | 2074.9 | 2075.9 |
| combined | 9/10 | 3.613 | 13.826 | 7893.7 | 2369.2 | 108.6 |

### Cost breakdown

Means in seconds over solved runs. These four components sum to net time;
Python is the residual after grounding, solving and closure. Pool construction
uses closure work as well as Python; it is not free simply because ground calls
fall.

#### 5queens

| Configuration | Grounding | Solving | Closure | Python |
|---|---:|---:|---:|---:|
| control | 2.471 | 0.631 | 0.164 | 3.018 |
| pool_fresh | 7.749 | 1.545 | 0.581 | 8.709 |
| pool_persistent | 0.697 | 1.053 | 0.532 | 7.279 |
| behavior | 0.911 | 1.299 | 0.701 | 9.057 |
| reproductive_retention | 0.625 | 0.982 | 0.463 | 6.863 |
| neighbors | 0.704 | 1.088 | 0.589 | 7.782 |
| adaptive | 0.377 | 2.540 | 2.146 | 16.316 |
| reproductive_selection | 5.409 | 1.062 | 0.376 | 5.169 |
| combined | 0.368 | 2.471 | 2.152 | 16.703 |

#### grandparent

| Configuration | Grounding | Solving | Closure | Python |
|---|---:|---:|---:|---:|
| control | 0.535 | 0.075 | 0.297 | 0.616 |
| pool_fresh | 1.051 | 0.140 | 2.992 | 1.203 |
| pool_persistent | 0.605 | 0.179 | 2.857 | 1.761 |
| behavior | 0.140 | 0.063 | 0.593 | 0.360 |
| reproductive_retention | 0.073 | 0.037 | 0.233 | 0.175 |
| neighbors | 1.184 | 0.304 | 3.775 | 3.475 |
| adaptive | 0.341 | 0.142 | 1.749 | 1.152 |
| reproductive_selection | 0.808 | 0.105 | 0.510 | 1.045 |
| combined | 0.459 | 0.162 | 1.505 | 1.488 |

### Interpretation

Fresh and persistent pool searches produced 101,669 GA progress rows each, with
identical values and order in every column except elapsed time. Reuse reduced
5queens net time by 48.55% for that matched search, but remained slower than the
unrestricted control. Grandparent's matched net times were effectively equal.

Reproductive retention improves on its direct behavior-retention comparator in
both tasks: 11.967 to 8.932 seconds in 5queens and 1.155 to 0.518 seconds in
grandparent. It wins 6/10 and 7/10 paired runs respectively. Compared with the
unrestricted control, it wins only 3/10 runs in 5queens but 8/10 in grandparent.
Grandparent's mean improves by 66.0% and median by 42.2%; a slow control run
amplifies the mean. This supports further investigation of retention, not an
unconditional switch to pooled search or reproductive selection.

Adaptive renewal illustrates the convergence tradeoff directly: 5queens uses
only 38.6 ground calls on average but requires 17,754.3 generations and 9,365
fresh evaluations, taking 21.379 seconds versus the control's 6.283 seconds.
The combined policy is worse and has the only timeout. Reproductive selection
without pooling also increases mean time in both tasks.

The implementation is semantically viable and the optimized evaluator can save
work. None of the tested variants beats the control in both datasets. Pooling
and all new policies remain opt-in; ordinary search and selection stay the
default. Ten paired seeds on two tasks are exploratory evidence, not a general
performance guarantee. Artifacts are under `.benchmarks/experiments/pool-policy/` and the
read-only summary command reproduces the tables from the measured CSV files.

## Verification

The final suite reports 477 passed tests and four pre-existing failures in
`tests/test_run_experiments.py`. Those failures concern the ordinary experiment
matrix: tests expect seven configurations while the current matrix has five,
and its baseline-selection assumptions differ. That unrelated matrix was not
changed. Ruff and the repository's `ty check` both pass.

New tests cover frozen-pool coverage equivalence, external reactivation after
inconsistency, exact fresh/persistent search behavior, restricted sampling's RNG
sequence, retention and renewal policies, reproductive credit and selection,
immediate stopping at the first solution, solver lifetime between epochs, light
instrumentation and rejection of stale benchmark summaries.

## Cost model and limitations

With `M` distinct evaluated hypotheses and `R` pool epochs, fresh evaluation pays
the sum of `M` candidate groundings. Pool evaluation replaces that with the sum
of `R` joint pool groundings, plus pool construction, activation changes and
solving each candidate against the larger frozen program. Reproductive history
does constant-size work per pair of parents; retention and lexicase add their
own population-dependent costs. None of these changes removes the worst-case
combinatorics of ASP solving or hypothesis search.

Crucially, `M` and `R` depend on the search policy. Fewer grounding calls do not
imply lower total cost if the restricted search requires many more evaluations
or cannot reach a solution within the timeout. This is why both matched replay
and whole-search experiments are necessary.
