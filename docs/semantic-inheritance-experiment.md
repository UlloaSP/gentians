# Exact constraint-coverage inheritance

## Question and implementation

Can previously established coverage reduce evaluation cost without changing the
search trajectory? This experiment studies exact bounds under integrity-constraint
addition and removal. It does not change mutation or crossover sampling.

The normal solver keeps bounded whole-program evidence. It inherits absence from
a program with fewer constraints and coverage from a program with more constraints,
provided all other statements match exactly. It solves only unresolved examples
and restores their original indices before scoring. Every unresolved query gets
a fresh control. The detailed contract is in `variation-policy.md`.

The first implementation compared AST sets. The second caches exact Clingo
renderings for native string-set comparisons and rejects non-brave or incomplete
enumeration before storing evidence. Neither implementation retains models.

## Protocol

The control is the current structural policy from the previous mutation ablation,
not the historical original: `mutation.constraint_only_random=true`, normal
coverage solver, lexicase, set-mix crossover, population 10, mutation 0.9,
no body locality, no duplicate retries and no complete reserve. The treatment
changes only `evaluation.constraint_inheritance` to true. Parameters remain in
`benchmarks/experiments.toml` under `semantic-inheritance/control` and
`semantic-inheritance/partial`.

Each batch uses ten paired seeds per dataset, 1 through 10 for 5queens and 11
through 20 for grandparent. Each pair alternates execution order. Workers run
serially against a frozen source tree. The timeout is 30 wall-clock seconds per
run and generations are unlimited. Reported times are net `total_execution`,
including clause generation. Full instrumentation is enabled; cProfile is off.
No timeout is interpreted as a zero-time result.

Environment: Windows 11, Intel Core i7-13700H, 14 cores and 20 logical processors,
Python 3.14.6, Clingo 5.8.0. Exact platform strings, source and task hashes,
arguments, schedules and raw metrics are retained in each local protocol.

Local artifacts and the paired runner are ignored under
`.benchmarks/experiments/semantic-inheritance/`. Reproduce the alternating schedule with
`uv run python .benchmarks/experiments/semantic-inheritance/run.py <new-batch-name>`.
The runner refuses to overwrite an existing batch. The regular experiment runner
also runs either TOML entry, but does not interleave them.

## First batch

| Dataset | Control mean, seconds | AST-set inheritance mean, seconds | Change | Solutions per version |
| --- | ---: | ---: | ---: | ---: |
| 5queens | 6.538490 | 5.993964 | -8.33% | 10/10 |
| grandparent | 0.511068 | 0.583836 | +14.24% | 10/10 |

In 5queens the mean number of candidate-example queries fell from 46,332 to
29,300.5. Actual candidate controls fell from 1,029.6 to 1,013.2. In grandparent
there was no inherited coverage: 6,691.5 candidate-example queries and 446.1
controls per run in both versions. Comparing evidence added work without saving
solver work there. No timeout occurred.

The full non-time GA trajectory is checked separately from runtime. An apparent
speed improvement is not evidence that the GA needs fewer generations.

## Second batch

| Dataset | Control mean, seconds | Cached-key inheritance mean, seconds | Change | Solutions per version |
| --- | ---: | ---: | ---: | ---: |
| 5queens | 7.561717 | 7.424981 | -1.81% | 10/10 |
| grandparent | 0.617618 | 0.640976 | +3.78% | 10/10 |

The number of controls and candidate-example queries was unchanged from the
first batch. All non-time GA fields matched for all 14,131 recorded rows in
5queens and all 10,017 rows in grandparent, in both batches. No timeout occurred.
The small net-time gain in this batch does not support enabling the feature
unconditionally.

The third implementation additionally disables bookkeeping when the prepared
space has no constraints and caches individual compiled example fragments. It
does not inspect dataset names. Its control uses the frozen first-batch source,
with inheritance disabled, so the comparison includes compiler changes too.

## Third batch: final implementation

| Dataset | Control mean, seconds | Final mean, seconds | Change | Solutions per version |
| --- | ---: | ---: | ---: | ---: |
| 5queens | 7.192765 | 6.440562 | -10.46% | 10/10 |
| grandparent | 0.525014 | 0.522700 | -0.44% | 10/10 |

The final implementation won 8 of 10 paired seeds in 5queens and 4 of 10 in
grandparent. Median times were 5.904825 versus 5.443372 seconds in 5queens and
0.499598 versus 0.520590 seconds in grandparent. The grandparent difference is
noise-sized and is not an algorithmic speedup: inheritance is disabled there
because the prepared space contains no constraints.

| Dataset/version | Grounding, seconds | Solving, seconds | Python, seconds | Closure, seconds |
| --- | ---: | ---: | ---: | ---: |
| 5queens control | 2.728099 | 0.923311 | 3.403120 | 0.138234 |
| 5queens final | 2.162541 | 0.845783 | 3.293659 | 0.138579 |
| grandparent control | 0.197009 | 0.045331 | 0.224352 | 0.058322 |
| grandparent final | 0.194282 | 0.045596 | 0.224094 | 0.058728 |

These are end-to-end mean costs, including clause generation. Python is net total
minus grounding, solving and closure. In 5queens the grounding reduction is
20.73%; the candidate-example query reduction is 36.76%. The latter is a count
of example occurrences across candidate evaluations, not a count of solve calls.
Candidate controls fell by 1.59%. The mean candidate evaluation count remained
1,029.6, and mean generations remained 1,412.1. In grandparent those counts
remained 446.1 and 1,000.7.

All 14,131 non-time GA rows in 5queens and 10,017 in grandparent matched exactly.
The runner completed all 120 runs across three batches without timeouts. Thirty
seconds sufficed; no generation cap or timeout extension was used.

An exploratory paired bootstrap of the final ten seeds, 10,000 resamples with
analysis seed 7, gave a mean treatment-minus-control interval of -1.110 to
-0.372 seconds for 5queens and -0.0191 to +0.0122 for grandparent. These intervals
do not correct for iterative development on the same seeds. Confirmation on
unseen seeds and more tasks remains necessary before a broad default-on claim.

The feature therefore remains opt-in. It implements exact coverage reuse and
partial evaluation, not witness collection, causal rule credit, or semantic
crossover. Those more expensive changes were deliberately deferred while testing
the cheaper proof-based mechanism.

## Source identity and verification

All batches used dirty-worktree snapshots based on commit
`467f0651900a2295f3efd813e63c31680dee502e`. The SHA-256 hashes below include sorted
relative paths and bytes of every `gentians/**/*.py` and `gentians/**/*.lp` file.

| Implementation | Source hash |
| --- | --- |
| First, AST sets; also frozen final control with option off | `4d3baff1c68e6c83876889309d472ae23a38ca1bb9e062c5abf6c5c4b2da2aad` |
| Second, cached rule keys and exhaustive checks | `2ca0c4c088bd0bcfec900f37aa2f2bca7b39247d452fb141ea0a50c1bb9cdda7` |
| Third, final implementation | `08b5a12d376149e7c7cdbf4cbeedc668e18d109f67d0f195c16438e2b39e2d7c` |

The paired runner verifies that frozen sources remain unchanged. Its local
`verify.py` checks completion, task hashes, identical non-time trajectories and
reports costs. No benchmark result files were edited manually.

## Scope

This is an evaluator optimization, not witness-guided variation. The tests cover
both constraint-subset directions, replacements, headed-program changes, default
and strong negation, inclusions, exclusions, empty example sides and isolated
contexts. Runtime evidence applies to these datasets and seeds, not every ASP
task. Retained-cache bounds do not substitute for measuring peak process memory.
## Transfer check: coloring and knapsack

The additional transfer batch compares three frozen versions without changing
either task: the historical original, the current structural mutation without
inheritance, and the final inheritance implementation. It uses ten runs per
version and dataset, seeds 1 through 10 for coloring and 11 through 20 for
knapsack, a 30-second wall timeout, unlimited generations, and full instrumentation
without cProfile. The three versions rotate serially within each seed. All sixty
runs found a solution without timeout.

| Dataset | Version | Mean net seconds | Median net seconds | Candidate evaluations | Candidate controls | Candidate-example queries |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| coloring | Original | 0.458941 | 0.394685 | 217.2 | 217.2 | 2172.0 |
| coloring | Current | 0.460857 | 0.394518 | 224.6 | 224.6 | 2246.0 |
| coloring | Latest, inheritance | 0.433253 | 0.387928 | 224.6 | 213.6 | 1768.6 |
| knapsack | Original | 0.097922 | 0.087516 | 10.5 | 10.5 | 42.0 |
| knapsack | Current | 0.090056 | 0.082324 | 10.5 | 10.5 | 42.0 |
| knapsack | Latest, inheritance | 0.090770 | 0.084590 | 10.5 | 9.0 | 32.9 |

The latest version was 5.99% faster than current in coloring and 5.60% faster
than original. The current and original means were effectively tied. Current
and latest had exactly the same 2,581 non-time GA rows, averaging 257.1
generations. Original followed a different trajectory, averaging 333.6
generations but fewer candidate evaluations. Generation count alone therefore
does not predict evaluation cost or runtime.

In knapsack, latest was 0.79% slower than current, an absolute difference of
0.000713 seconds. It reduced query occurrences by 21.67%, but the benchmark
already required only 10.5 candidate evaluations and 4.1 generations on average.
All three versions had identical non-time trajectories, 51 rows. The observed
time difference between original and current is not evidence of improved search
convergence; these short runs are sensitive to runtime noise. This batch does
not establish a useful end-to-end inheritance speedup on knapsack.

Artifacts are under `.benchmarks/experiments/semantic-inheritance/transfer/`, including the
three dashboards, raw metrics, argument payloads, schedule and task hashes.
The original source hash is
`4ace35a8420f5be661cd9c1b9a88c501d705528535b2f75644ccb95f34df2f47`.
Current uses the first-batch hash and latest uses the third-batch hash listed
above. Environment remains Python 3.14.6, Clingo 5.8.0, Windows 11 build 26200
on Intel Core i7-13700H. Source hashes were verified after execution.

The latest configuration is retained in `benchmarks/experiments.toml`. From the
repository root, run both transfer datasets using:

```powershell
uv run python benchmarks/run_experiments.py semantic-inheritance/coloring-knapsack
```

This command runs the latest implementation only, ten runs per dataset. It does
not relaunch the historical three-way comparison. To reproduce that local frozen
comparison, the ignored paired runner uses its `transfer` batch, which refuses
to overwrite existing artifacts. Existing TOML experiment results require an
explicit `--force` to replace them; the initial command above does not overwrite.
