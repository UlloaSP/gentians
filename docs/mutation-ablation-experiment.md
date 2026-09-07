# Mutation regression ablation

## Objective and protocol

Recover the historical operator's 5queens runtime without losing the current
operator's grandparent improvement. A faster grounding phase or fewer generations
alone does not meet this objective. Compare successful end-to-end net
`total_execution` and unique candidate evaluations until solution.

The first batch compares the historical source snapshot with four configurations
of the current source. All configurations live in `benchmarks/experiments.toml`.

| Configuration | Completeness guidance | Head-jump probability |
| --- | --- | ---: |
| mutation-ablation/control | Enabled | 0.1 |
| mutation-ablation/unguided | Disabled | 0.1 |
| mutation-ablation/global-head | Enabled | 1.0 |
| mutation-ablation/unguided-global | Disabled | 1.0 |

Body locality, duplicate retries, complete reserve and clause pooling are off.
Each dataset has ten planned runs, a 300-second wall-clock timeout, no generation
limit, population size ten, lexicase selection, set-mix crossover and mutation
probability 0.9. Seeds are 1 through 10 for 5queens and 11 through 20 for
grandparent. Instrumentation is full and cProfile is disabled.

The local runner `.benchmarks/mutation-ablation/run.py` freezes Python and ASP
sources, records task and source hashes, refuses to overwrite output, and checks
hashes after measurement. All snapshots and generated results are ignored by Git.
Within each dataset it measures the ten historical controls first, then rotates
the current configurations serially by seed. This ordering permits the user's
cumulative-time screening rule, but is not a fully interleaved historical control.
A treatment stops after its first failure or when its observed cumulative net
time exceeds the sum of all ten fresh historical controls. The current control
always completes. Unexecuted runs are not zero-time successes or failures.

## Interpretation boundaries

Disabling completeness guidance changes both mutation restrictions and intermediate
evaluation cost. A difference alone cannot distinguish those two causes. The
head-jump ablation retains the random draw, isolating filtering from random-stream
changes. Every pure constraint has an empty head signature, so this ablation
should leave the 5queens search trajectory unchanged.

The earlier measured regression is recorded in
[the locality experiment](body-locality-experiment.md). Its timings are historical
references, not observations from this new batch. Results below will identify
their own source snapshot and executed seed prefix.

## First batch results

All 90 executed runs found a solution. The table compares each treatment with
the same executed seeds of the fresh historical control. Times are mean net
seconds. The current control always completed ten runs; treatment screening
happened only between runs.

| Dataset | Configuration | Runs | Net seconds | Historical control, matched | Evaluations |
| --- | --- | ---: | ---: | ---: | ---: |
| 5queens | Historical original | 10 | 7.428 | 7.428 | 1029.6 |
| 5queens | Current control | 10 | 10.021 | 7.428 | 1604.1 |
| 5queens | Unguided | 9 | 10.210 | 7.596 | 1888.3 |
| 5queens | Global head | 6 | 12.474 | 6.267 | 1857.7 |
| 5queens | Unguided global | 8 | 10.203 | 7.349 | 1496.5 |
| Grandparent | Historical original | 10 | 1.436 | 1.436 | 1222.0 |
| Grandparent | Current control | 10 | 0.523 | 1.436 | 446.1 |
| Grandparent | Unguided | 7 | 2.775 | 1.817 | 2180.9 |
| Grandparent | Global head | 10 | 1.391 | 1.436 | 1219.2 |
| Grandparent | Unguided global | 10 | 1.519 | 1.436 | 1318.3 |

The three 5queens treatments stopped on cumulative net time. Unguided grandparent
stopped after seven runs. Unguided-global grandparent crossed the threshold on
its tenth run, so no runs were omitted there. No timeout occurred.

Removing head filtering preserved the exact 5queens generation and evaluation
counts at every matched seed. Time differences between those identical searches
are execution variability, not a filtering effect. Removing completeness guidance
did not recover historical performance and lost the grandparent improvement.
Neither option is selected as a new default.

The historical source hash is
`4ace35a8420f5be661cd9c1b9a88c501d705528535b2f75644ccb95f34df2f47`.
All four ablations used
`62b4b87b9edd9fb2056887db447fddd2c95da2c9b05a43d79ac4a8cddd249d9b`.
These hashes cover ordered relative paths and bytes of `gentians/**/*.py` and
`gentians/**/*.lp`. The protocol retains task hashes and resolved arguments.
Environment was Python 3.14.6, Clingo 5.8.0, Windows 11 build 26200 on an Intel
Core i7-13700H. Source and task hashes matched after execution.

Review found that the first current snapshot omitted `benchmarks/__init__.py`.
Its worker therefore imported the live `benchmarks.catalog`, which was unchanged
throughout this batch. Core `gentians` imports were frozen. Later batches copy the
package marker and fingerprint supporting benchmark files as well.

## Second batch hypothesis

The replacement head-permission draw is inapplicable when the active pool contains
only constraints. The second batch removes that draw while retaining completeness
guidance, operation restrictions and dependency closure. Pools containing headed
clauses keep the existing head draw. This is a property of the active clause pool,
not a dataset-name special case. It changes random trajectories in constraint-only
spaces; a faster result would not prove that one saved RNG call is computationally
expensive, nor establish a universal search advantage.

`mutation-ablation/nohead-draw` records the candidate configuration. The local
second batch also reruns the frozen first-batch current control and historical
original. All three use the same seeds and measurement settings.

## Second batch results

All 57 executed runs found a solution. The head-draw change was rejected and
reverted. Grandparent retained identical evaluation and generation counts, as
expected because its active pool contains headed clauses. The change did not
recover 5queens performance and was screened after seven runs.

| Dataset | Configuration | Runs | Net seconds | Historical control, matched | Evaluations |
| --- | --- | ---: | ---: | ---: | ---: |
| 5queens | Historical original | 10 | 5.312 | 5.312 | 1029.6 |
| 5queens | Current control | 10 | 7.573 | 5.312 | 1604.1 |
| 5queens | No head draw | 7 | 7.675 | 4.697 | 1601.3 |
| Grandparent | Historical original | 10 | 1.439 | 1.439 | 1222.0 |
| Grandparent | Current control | 10 | 0.545 | 1.439 | 446.1 |
| Grandparent | No head draw | 10 | 0.550 | 1.439 | 446.1 |

The candidate source hash was
`afc71e9d1bfe1bc059877ae3521f1faffbc0a576ddebdc0e06ba414eebceb41c`.
Controls used the same source hashes as the first batch, freshly executed.
The historical `nohead-draw` configuration needs this frozen snapshot to reproduce
its implementation; current code no longer skips that draw.

## Third batch hypothesis

Constraint-only removal and replacement permissions do not depend on completeness.
The third candidate reads cached results immediately but delays an uncached
classification until an append attempt requires it. Headed pools retain the
existing eager policy. Incomplete candidates still cannot append constraints,
and known perfect candidates remain protected. An unknown perfect crossover child
may now be mutated before discovery, so this is not a claim of identical search
trajectories. The head draw is restored, isolating classification timing from the
rejected second-batch change.

The regression test for a replacement-only constraint pool failed on the eager
implementation because it requested intermediate fitness. After the fix it passes.
Additional tests exercise complete and incomplete append decisions with the actual
evaluator, and protection of a cached perfect constraint program. The third matrix
entry is `mutation-ablation/lazy-classification`.

## Third batch results

All 57 executed runs found a solution. Delayed classification was screened after
seven 5queens runs. It saved some intermediate evaluations but did not recover
the historical search cost. Grandparent kept the current trajectory.

| Dataset | Configuration | Runs | Net seconds | Historical control, matched | Evaluations |
| --- | --- | ---: | ---: | ---: | ---: |
| 5queens | Historical original | 10 | 5.628 | 5.628 | 1029.6 |
| 5queens | Current control | 10 | 8.657 | 5.628 | 1604.1 |
| 5queens | Lazy classification | 7 | 8.217 | 4.995 | 1628.4 |
| Grandparent | Historical original | 10 | 1.506 | 1.506 | 1222.0 |
| Grandparent | Current control | 10 | 0.543 | 1.506 | 446.1 |
| Grandparent | Lazy classification | 10 | 0.558 | 1.506 | 446.1 |

Candidate hash:
`2034ac7fb7188fc14a0fb6d878256452fb59beb63ccca2a8419d8f760e6f1a3a`.
The table does not compare the seven-run treatment with the ten-run current
mean as if they were paired samples.

## Structural policy hypothesis

The fourth batch enables `mutation.constraint_only_random` for both datasets.
It applies unrestricted random mutation only when the active pool contains no
headed clauses. Otherwise it preserves the directed policy. The decision reads
clause-pool structure, not the dataset name. The option defaults to false because
it relaxes the earlier preference against appending constraints to incomplete
programs. All candidate legality and evaluation semantics remain unchanged.

The causal distinction matters: appending a constraint cannot recover a missing
positive witness, but it can eliminate negative witnesses and improve the score
of a still-incomplete candidate. A real-evaluator test demonstrates this case.
Treating all such additions as useless was an unsupported search assumption.
The fourth configuration is `mutation-ablation/structural-policy`.

## Fourth batch results

All 58 executed runs found a solution. The option reproduced historical 5queens
generation and evaluation counts at every executed seed, while preserving the
current grandparent counts. It did not recover historical net time in this
original-first batch and was screened after eight 5queens runs.

| Dataset | Configuration | Runs | Net seconds | Historical control, matched | Evaluations |
| --- | --- | ---: | ---: | ---: | ---: |
| 5queens | Historical original | 10 | 5.576 | 5.576 | 1029.6 |
| 5queens | Current control | 10 | 10.795 | 5.576 | 1604.1 |
| 5queens | Structural policy | 8 | 7.217 | 5.553 | 1023.9 |
| Grandparent | Historical original | 10 | 2.022 | 2.022 | 1222.0 |
| Grandparent | Current control | 10 | 0.635 | 2.022 | 446.1 |
| Grandparent | Structural policy | 10 | 0.622 | 2.022 | 446.1 |

Candidate hash:
`2f50d7a1ce6e11fe8f64d2bdfafb40ede640250f01d8d09c0482b33b8d7a1b8c`.
Matched eight-seed mutation grounding averaged 1.917 seconds for the original
and 2.545 for the structural option; mutation solving averaged 0.323 and 0.422.
The solver, coverage compiler and evaluator files were byte-identical across
those sources. This motivated an interleaved confirmation rather than treating
every timing difference as a mutation-code effect. It does not prove the timing
gap is entirely environmental.

## Final implementation and confirmation protocol

The unsuccessful delayed-classification code and its dedicated tests were removed.
Default mutation again uses eager classification. The final implementation keeps
the opt-in structural policy and the explicit completeness ablation switch. The
structural option is still false by default because it changes an earlier search
restriction. Body locality, duplicate retries and complete reserve remain off.
The deleted head-draw and delayed-classification experiments require their recorded
source snapshots to reproduce; their TOML entries preserve execution settings.

The `confirmation` batch rotates original, frozen current control and final
structural candidate by seed, serially. It uses the same ten seeds per dataset,
300-second timeout, full instrumentation and unlimited generations. Candidate
execution can pause when its cumulative time exceeds the fourth batch's historical
ten-run total. Both fresh controls continue. Pending runs resume only if the final
fresh-original budget still permits them. Because the fresh budget is unknown
until its ten runs finish, this is provisional screening, not an immediate cutoff
against the eventual fresh total. No missing observation is imputed as zero.

The package markers, supporting benchmark files, source and task hashes are
checked. The protocol also records the runner hash. The worktree is based on
`467f0651900a2295f3efd813e63c31680dee502e`; dirty source fingerprints, not that commit
alone, identify measured implementations. CPU metadata confirms 14 cores and
20 logical processors. No benchmarks execute concurrently.

## Confirmation results and decision

All sixty confirmation runs found a solution. No run was omitted or timed out.
The final candidate source hash is
`009e2d736c85a56039ae7118f44cbb1c6587862f453e47d46e8728272c6ac8e0`.
Control hashes remain those recorded above. Source, task and support fingerprints
matched after execution.

| Dataset | Configuration | Runs | Mean net seconds | Median net seconds | Evaluations | Generations |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 5queens | Historical original | 10 | 6.090 | 5.380 | 1029.6 | 1412.1 |
| 5queens | Current control | 10 | 9.686 | 7.554 | 1604.1 | 2238.0 |
| 5queens | Structural policy | 10 | 5.569 | 4.984 | 1029.6 | 1412.1 |
| Grandparent | Historical original | 10 | 1.495 | 0.742 | 1222.0 | 3967.1 |
| Grandparent | Current control | 10 | 0.484 | 0.494 | 446.1 | 1000.7 |
| Grandparent | Structural policy | 10 | 0.485 | 0.479 | 446.1 | 1000.7 |

Mean phase costs in seconds, with closure separated from residual Python work:

| Dataset | Configuration | Grounding | Solving | Closure | Python | Ground calls | Solve calls |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 5queens | Historical original | 2.299 | 0.728 | 0.106 | 2.958 | 1030.6 | 1030.6 |
| 5queens | Current control | 3.889 | 1.071 | 0.205 | 4.521 | 1605.1 | 1605.1 |
| 5queens | Structural policy | 2.085 | 0.688 | 0.111 | 2.686 | 1030.6 | 1030.6 |
| Grandparent | Historical original | 0.525 | 0.076 | 0.250 | 0.644 | 1223.0 | 1223.0 |
| Grandparent | Current control | 0.183 | 0.034 | 0.056 | 0.211 | 447.1 | 447.1 |
| Grandparent | Structural policy | 0.183 | 0.034 | 0.056 | 0.212 | 447.1 | 447.1 |

Ground and solve counts include clause generation, hence one more call than
candidate evaluations. No wall-clock value substitutes for net time in these
tables. Python is total net time minus grounding, solving and closure.

The final audit compared every recorded GA field except elapsed time. All 14,131
5queens rows matched the historical original, and all 10,017 grandparent rows
matched the frozen current control. Thus the structural option recovers the
original observed search trajectory in the first task and preserves the current
one in the second. This is stronger evidence than final counters alone, but it
does not establish behavior on other tasks or seeds.

The runtime objective is met in this confirmation: 5queens recovers original-level
time while grandparent keeps the current improvement. The measured 8.6% advantage
over original 5queens is not claimed as a general algorithmic speedup; search
counts are identical and earlier batches demonstrate substantial timing variability.
Relative to the current control, the structural option used 42.5% less net time
in 5queens. Grandparent remained essentially unchanged versus current and about
67.6% below the historical original.

Keep `constraint_only_random` as an opt-in execution preference, with the same
value for both datasets. To run the selected configuration:

```powershell
uv run python benchmarks/run_experiments.py mutation-ablation/structural-policy
```

For SDK use, set `args.mutation["constraint_only_random"] = True`. Default false
preserves the user's earlier strict directed preference. This is not a hidden
benchmark-specific default. The option preserves task syntax, semantic coverage,
closure and structural limits. Mutation's factory still has one implementation.

The five batches contain 322 successful executions in total. Rejected variants
and truncated prefixes remain in the tables above. Local raw observations,
dashboards, frozen sources, the serial runner, `summarize.py` and
`verify_results.py` remain under `.benchmarks/mutation-ablation/`, ignored by Git.
`verify_results.py` checks completion, successes and the observed trajectory
matches without rewriting any measurements.

Final verification: 622 tests passed, Ruff and type checking passed, and the diff
has no whitespace errors. Independent read-only review found no blocking issue.
All source snapshots, generated measurements and builds from these batches are
ignored by Git.
