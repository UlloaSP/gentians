# Bounded clause batches and completeness-guided operators

Configuration location: this matrix now lives in `benchmarks/experiments.toml`
under `sampled-roles/` IDs. Worker arguments and output folders are unchanged.
The ID change makes old manifests stale; historical measurements below are not
rewritten. Commands below select named entries, not every matrix in the file.

Historical experiment: references below to `#bias`, metarules, or atomic bundles
describe the measured implementation, not the current language. That support has
been removed; see [the current contract](language-bias.md#removed-meta-programming-directives).

The completeness-operator descriptions and measurements below are historical.
Those separate strategies have been replaced by the shared
[variation policy](variation-policy.md). They are no longer selectable, and their
results do not measure the current policy. Existing generated artifacts remain
untouched. The runnable matrix now contains only the three pool-source controls.

## Implementation

`generate_clause_space()` remains exhaustive. Epoch-pool search now accepts
`clause_pool.source="sampled"` and calls `sample_clause_space()` on every renewal.
The sampler limits Clingo's enumeration to `clause_pool.size` models before
decoding and canonicalization. It uses one solver thread, a seeded random sign
policy and random branching. It does not enumerate the complete space and then
truncate it. These are biased prefixes, not uniform samples; canonicalization
and theta reduction can produce fewer clauses than the model budget.

Metarules are already instantiated in the task IR. The sampler chooses at most
the batch size in bundles and includes each selected bundle whole. Their clauses
are additional to the model budget. Static analysis and grounding of the clause
metaprogram still occur for every batch. Sampling does not bound those costs.

At renewal, the search retains the configured number of complete hypotheses
(complete programs here, not necessarily complete positive coverage), including
the champion. It combines their clauses with a new batch, constructs new local
indices, remaps retained genotypes and reproductive credit, and drops old
evaluation and construction caches. Background, contexts and the new pool are
grounded together. A supplied `ClauseSpace` bypasses sampling. Historical
experiment matrices explicitly select `source="exhaustive"` to preserve their
original protocol.

With a batch of at most B canonical mode clauses, M clauses in selected bundles,
k retained hypotheses and maximum retained size L, the new working clause set
contains at most B + M + kL entries before dependency pruning. This replaces
retention of the entire C-clause space with retention of the current batch and
elite programs. It is not a byte-level bound: AST sizes, bitsets, caches and ASP
grounding matter. With `#maxpl(*)`, L can grow across epochs; an omitted directive
uses the existing default of six clauses. During renewal the
old and new working sets briefly coexist. The old constructor is then collectible.

The preventive ground-rule/literal budget and its fresh-solver fallback have
been removed. Oversized ASP groundings must be controlled externally; bounded
source clause count alone is not a universal memory guarantee.

Time must be compared until solution, not at a fixed generation count. The
original pays full clause enumeration once and grounding plus solving for each
new candidate. A sampled pool pays clause sampling and joint grounding once per
epoch, then solving for each new candidate. If the restricted search needs more
epochs or evaluations, those additional costs can exceed the savings. There is
no general improvement in worst-case search complexity, and a biased sampler
does not provide a finite-time guarantee of visiting a useful clause combination.

## Completeness policy

The optional `completeness` crossover and mutation classify whole programs using
the existing evaluator. If an input covers every positive example, its headed
clauses are frozen and only pure integrity constraints can change. Mixed bundles
are frozen as a unit. Dependency repair cannot insert a new headed clause into
a frozen program. Otherwise the ordinary general operators apply. A discovered
perfect input is returned unchanged.

Crossover chooses a complete parent when one exists. Mutation checks the actual
crossover output, not the parent's cached state. The shared evaluation cache
avoids evaluating unchanged programs twice; classifications of previously unseen
offspring count as real evaluations and their cost belongs to the requesting
operator phase. Admission and evaluation caches are separate so a classification
does not accidentally discard a novel offspring as an already admitted duplicate.

Consistency is observable before completeness: it means covering no negative
example. It does not trigger freezing. Adding or replacing constraints can lose
positive coverage; children are evaluated normally. Neither completeness nor
consistency is inherited as a semantic invariant. The policy can stall when a
complete generator needs restructuring, particularly in languages without useful
constraints. It remains opt-in and assigns no fixed fitness to individual rules.

## Experimental protocol

Run `uv run python benchmarks/run_experiments.py sampled-roles/original sampled-roles/exhaustive_pool sampled-roles/sampled_pool` on the original, unchanged `5queens`
and `grandparent` task files. The five configurations are unrestricted original,
exhaustive pool, sampled pool, original with completeness operators, and sampled
pool with completeness operators. Each uses ten runs, a 300-second process
timeout and `iterations_genetic=0`. Seeds match between configurations. The
runner assigns seeds 1–10 to `5queens` and 11–20 to `grandparent`.

All share population 10, lexicase selection, crossover probability 1, mutation
probability 0.9, `cov_program`, and oldest-or-worst replacement with probability
0.1. Pool variants share size 64, renewal every 50 generations, three retained
hypotheses, fitness retention, random filling and persistent evaluation. The
role policy changes crossover and mutation together; these experiments do not
separate the contribution of its two operators.

The original `5queens` task learns constraints with its generator in background;
it does not exercise freezing a learned generator. `grandparent` learns headed
rules and has no candidate integrity constraints. These two controls therefore
cannot establish a benefit for mixed generator/constraint learning. In particular,
freezing a complete but inconsistent headed program can leave no useful move in
the latter task. The role policy also evaluates intermediate crossover outputs
and preserves perfect ones, so any benefit cannot be attributed solely to the
syntactic freeze.

Runs execute sequentially with full instrumentation and without cProfile.
Exhaustive enumeration keeps the existing `--parallel-mode=5,split` default;
sampling overrides it to one thread to make seeded model prefixes reproducible.
This thread policy is part of the sampler, not a separately measured ablation.
`total_execution` is the canonical net time. Grounding, solving, Python and
closure are reported alongside generations, evaluation counts and success.
Timeouts without a closed net total are not assigned a fictitious 300-second
`total_execution`. The external monitor samples the experiment process tree's
private bytes every two seconds and stops that tree above 6 GiB. This threshold
does not modify Clingo or candidate fitness.

Artifacts live in `.benchmarks/experiments/sampled-roles/`, including dashboards, raw CSV,
per-run logs, manifests and `memory.csv`. The comparison measures learning a
program consistent with the observed examples, not proving generalization to
all N-queens boards.

Environment: Python 3.14.6, Clingo 5.8.0, Windows 11 build 26200, Intel Core
i7-13700H (14 cores, 20 logical processors), 34,117,484,544 bytes of physical RAM.
The run uses the dirty worktree based on commit
`ff57d65e60cce685da8c8a79d47cc162128d5c05`. Concatenating each sorted Python source
path and contents, followed by each sorted ASP module path and contents under
`gentians/`, gives SHA-256
`4ace35a8420f5be661cd9c1b9a88c501d705528535b2f75644ccb95f34df2f47`
for the implementation used by these runs. Source files remain unchanged during
the timed matrix; the runner's stopping policy was changed during a pause.

## Early stopping requested during execution

After the sampled pool's first grandparent timeout, the user requested abandoning
a configuration after its first timeout instead of waiting for all ten runs.
At that point three additional grandparent runs had finished. The fifth was
interrupted manually, not timed out. The sampled-pool results therefore contain
ten completed 5queens runs and four completed grandparent runs (three successes
and one timeout). Its unfinished fifth grandparent run is excluded from aggregate
results, and the remaining five were not started.

The interrupted runner had already written the completed runs' raw instrumentation.
Those 14 results were reconstructed through the existing aggregation functions,
not by editing generated CSV or JSON. Net timings retain their full recorded
precision. Recovered wall times come from the runner's two-decimal log; they are
operational metadata, not the reported net-time comparison.

The remaining configurations use `stop_on_timeout=true`, forwarded as
`--stop-on-timeout`. It stops the whole configuration after the first timeout,
writes results for the runs actually completed, and lets the experiment runner
continue to the next configuration. It does not turn unexecuted runs into
failures, alter the 300-second timeout, or impose a generation cap. This is a
screening rule, not a statistical proof that a configuration has a worse expected
time. Comparisons must retain observed sample counts and timeout counts.

The user subsequently approved stopping the final `sampled_roles` configuration
once its accumulated net time could no longer beat the original's ten-run mean,
even if every remaining run took zero time. Four 5queens runs finished before
the stop was applied; the fifth was interrupted and grandparent was not started.
The four runs accumulated 253.775 seconds, giving a lower bound of 25.377 seconds
on a hypothetical ten-run mean, already above the original's 6.675 seconds.
This second criterion was applied manually with user approval; the runner only
automates first-timeout stopping. Both discarded configurations have manifest
status `screened_out` and are not implicitly rerun or overwritten without
`--force`. Their completed raw runs were retained and reaggregated.

## Results

Times below are mean net `total_execution` for successful runs only. Counts show
successes over completed runs, not over the planned ten. There were 78 completed
runs, including one timeout, and two manually interrupted runs. Twenty runs were
never started. No generation cap or preventive grounding limit was used.

| Configuration | Dataset | Successes/completed | Timeouts | Net mean (s) | Mean generations | Mean evaluations |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Original | 5queens | 10/10 | 0 | 6.675 | 1,412.1 | 1,029.6 |
| Original | grandparent | 10/10 | 0 | 1.801 | 3,967.1 | 1,222.0 |
| Exhaustive pool | 5queens | 10/10 | 0 | 8.028 | 3,632.3 | 3,027.6 |
| Exhaustive pool | grandparent | 10/10 | 0 | 5.452 | 6,532.6 | 2,121.2 |
| Sampled pool | 5queens | 10/10 | 0 | 44.593 | 7,095.0 | 6,447.1 |
| Sampled pool | grandparent | 3/4 | 1 | 92.076 | 31,864.0 | 20,220.3 |
| Original + completeness | 5queens | 10/10 | 0 | 11.664 | 1,978.4 | 1,559.6 |
| Original + completeness | grandparent | 10/10 | 0 | 1.292 | 3,527.3 | 1,113.0 |
| Sampled pool + completeness | 5queens | 4/4 | 0 | 63.444 | 9,895.8 | 10,233.5 |
| Sampled pool + completeness | grandparent | Not run | — | — | — | — |

The grandparent timeout is excluded from its net mean because no closed
`total_execution` exists for it. The three successful grandparent samples are
not a ten-seed estimate and must not be read as a 100% success rate. Early stopping
also makes the final sampled-completeness mean a partial result.

| Configuration | Dataset | Grounding (s) | Solving (s) | Python (s) | Closure (s) | Clause generation (s) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Original | 5queens | 2.619 | 0.703 | 3.232 | 0.123 | 1.683 |
| Original | grandparent | 0.626 | 0.094 | 0.776 | 0.304 | 0.096 |
| Exhaustive pool | 5queens | 0.638 | 0.988 | 6.028 | 0.374 | 1.607 |
| Exhaustive pool | grandparent | 0.601 | 0.202 | 1.809 | 2.841 | 0.088 |
| Sampled pool | 5queens | 10.495 | 9.166 | 24.350 | 0.583 | 28.615 |
| Sampled pool | grandparent | 35.108 | 9.826 | 35.260 | 11.883 | 64.789 |
| Original + completeness | 5queens | 3.939 | 0.919 | 4.442 | 2.364 | 1.636 |
| Original + completeness | grandparent | 0.456 | 0.068 | 0.557 | 0.211 | 0.091 |
| Sampled pool + completeness | 5queens | 14.793 | 12.965 | 34.809 | 0.877 | 40.291 |

Grounding, solving, Python and closure partition net execution time. Clause
generation is an inclusive phase overlapping those categories; do not add it
again. All means in this table use the same successful runs as the first table.

The exhaustive `ClauseSpace` contains 4,797 clauses for 5queens and 326 for
grandparent. Recorded sampled working sets contained 26–74 and 2–71 clauses,
respectively; sampled-completeness 5queens contained 38–74. The metaprogram solve
records confirm a maximum of 64 enumerated models per batch. These counts include
retained elite clauses after preparation, not only newly sampled clauses.

The external monitor observed a peak of 1,298,726,912 private bytes (1.210 GiB)
for the experiment process tree and never triggered its 6-GiB stop. This includes
runner-side buffered metrics and is not an isolated solver-memory measurement.
It does not include later standalone artifact recovery. Sampling every two
seconds can miss shorter peaks.

## Interpretation

Bounded sampling removes retention of the complete clause space, but this
implementation loses on time in these two small controls. It repeatedly grounds
and enumerates the clause metaprogram and requires more search evaluations.
Even eliminating that generation phase would not establish parity with the
original from these measurements. The exhaustive pool similarly saves grounding
without saving total time.

Completeness-guided operators improved the observed grandparent mean but worsened
5queens. Their extra classifications and constraint-index traversal have a cost;
these results do not isolate each contribution. No tested variant improves both
original tasks. The unrestricted original remains the default. Pooling and
completeness operators remain explicit experimental options, not a recommended
replacement or a demonstrated solution to larger N-queens learning tasks.

Possible follow-ups, not implemented or measured here, are reusing the grounded
clause enumerator between batches and sampling strategies that improve clause
combination discovery. Neither should be presented as a solved convergence or
memory problem without a controlled end-to-end comparison.

## Verification

The full test suite reports 524 passing tests and five unrelated failures: four
expect an older ordinary experiment matrix, and one rejects the pre-existing
`any` directions in an experimental task that has since been removed. The original
5queens and grandparent task files were not modified. The added tests cover
bounded and seeded sampling, whole metarule bundles, collection of old epoch
constructors, elite-size bounds, frozen headed clauses, mixed bundles,
dependency repair, actual-child classification, loss of completeness after a
constraint change, reproductive-credit remapping and first-timeout stopping.
Ruff and Ty pass. Independent review found no blocking correctness issue and
required the explicit retained-size and grounding-memory caveats above.
