# Structural diversity in the initial population

> Historical experiment. Structural population initialization was removed on 2026-09-08, together with its configuration and active matrix entries. The measurements below describe the implementation before removal.

## Implementation and limits

`population.name="structural_diverse"` is an alternative to `random` registered
in the existing population factory. It uses `RandomPopulation` to sample up to
four times the requested population size in distinct valid genomes. The existing
constructor closes dependencies and enforces the task's size and active-pool
limits. The existing sampler stops after 64 consecutive failed or duplicate
attempts, so small spaces do not cause unbounded retries.

Selection then repeatedly prefers the least represented actual program size.
Ties prefer the candidate with the largest minimum Jaccard distance to programs
already selected. Distance is the number of differing clause bits divided by
the number of clause bits in their union. Remaining ties preserve sampled order.
The first sampled program wins the initial tie. No bits are edited by the
strategy. Dependency closure can change the sampled size, so ranking uses final
genomes rather than requested seed sizes.

No fitness function is called during this selection. Only returned genomes are
evaluated by the existing search loop, which can stop early on a solution.
Discarded structural proposals cost Python and closure time, not Clingo fitness
queries. Those costs remain in initialization and net `total_execution`.
Sampling retains at most four times the population size in candidate genomes;
it does not enumerate the full hypothesis space. The straightforward greedy
ranking has cubic worst-case scaling in population size, excluding bitset width
and construction costs. The measured population size is ten.

The policy encourages diversity but cannot guarantee every size exists in the
sample or that distinct structures produce distinct behavior. It does not
require completeness or consistency, use additive clause fitness, or select
semantic specialists. Semantic oversampling would require evaluating discarded
candidates and is deliberately a separate, unimplemented experiment.

The comparison tests oversampling and structural ranking together. Generating
more proposals also advances the shared random stream before evolution starts.
Paired seeds provide reproducibility but do not isolate the ranking from that
change. A separate oversampling-without-ranking ablation would be needed to
attribute any measured effect specifically to the diversity criterion.

`random` remains the default and the recommended general configuration is
unchanged while this experiment is evaluated.

## Protocol

Two matrices in `benchmarks/experiments.toml`, `population-diversity/control`
and `population-diversity/structural`, use the recommended general configuration.
Their only override difference is `population.name`. Both use population ten,
lexicase selection, set-mix crossover, random-group mutation at 0.9, structural
constraint-only handling and exact constraint-coverage inheritance. Diagnosis,
repair preference, forced body locality and epoch pooling are disabled.

Datasets are 5queens, grandparent, coloring and knapsack. Ten runs are scheduled
per dataset and variant, with seeds 1 through 10, 11 through 20, 21 through 30
and 31 through 40 respectively. Every run has a 30-second wall timeout and no
generation cap. Execution is serial, alternating variant order within each seed.
Both variants use the same frozen implementation and task files. Full
instrumentation is enabled, without cProfile. After a failed run or timeout,
remaining runs for that variant and dataset are skipped.

The ignored runner `.benchmarks/experiments/semantic-inheritance/run.py population-diversity`
records resolved arguments, source and task hashes, environment, run order,
status, net time and final GA evaluation count in `protocol.json`. Raw metrics,
logs and dashboards are retained under
`.benchmarks/experiments/semantic-inheritance/population-diversity/`. The regular matrix
runner writes under ignored `.benchmarks/experiments/population-diversity/`.

Time means net `total_execution`, including clause generation and initialization.
Evaluation counts mean complete-candidate cache misses from generation zero
through termination, including initialization and any mutation classification.
Clingo call counts are a different metric because exact coverage inheritance
may avoid or narrow calls. Timed-out runs without completed metrics are not
assigned invented net time or evaluation counts.

Environment: Windows 11 build 26200, Intel Core i7-13700H, Python 3.14.6,
Clingo 5.8.0. The dirty worktree was based on commit
`cc30482b44d7a2c8d2fd7c8be90fdce6b09dbb3c`. Both variants use source hash
`3d14c8a0ebe90b5304f9ae8c6b1bba05ebb3fee0ab4790f8016372a20e264be2`.
The runner checks that the frozen source remains unchanged after execution.

Tests cover size balance and distance tie-breaking, actual dependency closure,
reproducible output, no initializer fitness calls, active-pool membership, small
spaces and invalid sizes. The experiment test requires identical settings except
for the initializer name. Independent static review found no blockers; it noted
the cubic selection cost already documented above.
The final full suite passed 656 tests. Ruff, type checking and whitespace checks
passed. Benchmark builds and artifacts are ignored by Git.

## Results

All 80 attempted runs succeeded, ten per dataset and initializer. There were
no timeouts or skipped runs. The source hash check passed.

| Dataset | Random mean seconds | Structural mean seconds | Time delta | Random mean evaluations | Structural mean evaluations | Evaluation delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 5queens | 5.131574 | 6.817245 | +32.85% | 1029.6 | 1503.0 | +45.98% |
| grandparent | 0.540842 | 1.298632 | +140.11% | 446.1 | 1079.7 | +142.03% |
| coloring | 0.387380 | 0.312554 | -19.32% | 207.4 | 163.4 | -21.22% |
| knapsack | 0.085128 | 0.084533 | -0.70% | 13.6 | 10.7 | -21.32% |

| Dataset | Random median seconds | Structural median seconds | Random median evaluations | Structural median evaluations |
| --- | ---: | ---: | ---: | ---: |
| 5queens | 4.096356 | 5.654609 | 766.5 | 1193.0 |
| grandparent | 0.528372 | 1.085902 | 417.0 | 967.5 |
| coloring | 0.310391 | 0.305797 | 166.0 | 153.0 |
| knapsack | 0.080431 | 0.080541 | 10.5 | 7.5 |

The coloring mean improvement is larger than its median improvement. Knapsack
saved only 0.000595 seconds per run on average and its median time did not
improve. Fewer evaluations therefore do not establish a useful runtime gain
there. These are ten fixed seeds per dataset, not a confidence guarantee or an
unseen-seed validation.

### Initialization and costs

| Dataset | Random initialization seconds | Structural initialization seconds | Random initial evaluations | Structural initial evaluations |
| --- | ---: | ---: | ---: | ---: |
| 5queens | 0.044532 | 0.048693 | 10.0 | 10.0 |
| grandparent | 0.011926 | 0.022509 | 10.0 | 10.0 |
| coloring | 0.014315 | 0.014655 | 10.0 | 10.0 |
| knapsack | 0.008558 | 0.011012 | 6.7 | 7.2 |

Knapsack sometimes solved during initialization; the loop correctly stopped
before evaluating the full population. There were no evaluations of the
discarded structural proposals. Initialization overhead does not explain the
large 5queens and grandparent regressions: their subsequent search used more
candidate evaluations.

| Dataset | Initializer | Grounding seconds | Solving seconds | Closure seconds | Remaining Python seconds |
| --- | --- | ---: | ---: | ---: | ---: |
| 5queens | Random | 1.670795 | 0.767264 | 0.112222 | 2.581292 |
| 5queens | Structural | 2.490025 | 0.887946 | 0.177766 | 3.261508 |
| grandparent | Random | 0.199429 | 0.047751 | 0.059981 | 0.233681 |
| grandparent | Structural | 0.459652 | 0.080098 | 0.190842 | 0.568040 |
| coloring | Random | 0.158806 | 0.048123 | 0.015050 | 0.165401 |
| coloring | Structural | 0.129551 | 0.039578 | 0.009894 | 0.133530 |
| knapsack | Random | 0.048515 | 0.011189 | 0.000390 | 0.025034 |
| knapsack | Structural | 0.047378 | 0.011822 | 0.000473 | 0.024860 |

Components are means across ten runs. Remaining Python is net total minus
grounding, solving and closure. Clause-generation cost is included in these
components and the net total, not added a second time.

The GA field `unique_signatures` counts distinct genomes, not distinct coverage
behaviors. Both initializers already produced distinct genomes. Its value must
not be used to claim equal or improved semantic diversity. No such measurement
is inferred from these results.

### Decision

Keep `structural_diverse` available as an experimental population strategy.
Keep `random` in `recommended/general`. Structural distance and balanced sizes
did not reduce evaluations consistently across tasks. The next independent
question would be whether bounded semantic selection improves this tradeoff
after accounting for every extra initialization evaluation; this experiment
does not answer it.

## Commands

```powershell
uv run python benchmarks/run_experiments.py population-diversity/control
uv run python benchmarks/run_experiments.py population-diversity/structural
```

These commands run current source. The retained paired runner freezes source
and interleaves variants; its protocol is the source of the comparison below.
