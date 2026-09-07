# Constraint diagnosis and mutation repair

## Question and implementation

Does distinguishing missing headed behavior from positive witnesses blocked by
learned integrity constraints improve the current mutation policy?

The evaluator optionally obtains exact positive coverage after removing learned
integrity constraints. Background and contexts are unchanged. A bounded cache
shares that diagnosis across candidates with the same headed program. A second
option prefers edits of the diagnosed role in 80 percent of eligible mutation
inputs. Unknown inputs are not classified solely for this preference. Mutation
logs also record differences between cached whole-program coverage masks.
See [the contract and limitations](variation-policy.md#experimental-constraint-diagnosis).

This experiment does not implement witnesses, rule-level credit, adaptive
operator selection or semantic crossover. Those changes would introduce
additional cost and independent search-policy variables. The measured policy
does not justify enabling diagnosis-guided repair by default.

## Protocol

Only `5queens` and `grandparent` were used, without modifying their tasks.
The control is the latest constraint-inheritance configuration, not historical
original. All variants use population 10, lexicase selection, set-mix crossover
at probability 1, random-group mutation at probability 0.9, oldest-or-worst
replacement, no pool, no duplicate retries and no body locality. Structural
constraint-only mutation is enabled. The existing 0.1 head-jump and complete
generator-removal probabilities are unchanged.

Ten runs were scheduled per dataset and variant. Seeds are 1 through 10 for
5queens and 11 through 20 for grandparent. Runs execute serially with rotating
variant order for each seed, a 30-second wall timeout, full instrumentation,
no cProfile and no generation limit. After a timeout or failure, remaining runs
of that variant on that dataset are skipped. Other variants continue.

Reported time is net `total_execution`, including clause generation, diagnosis,
grounding, solving and search. Instrumentation is excluded. A timeout without
completed timing output has no net time; it is not assigned a fabricated
30-second net observation or included in a successful-run average.

The matrices live in `benchmarks/experiments.toml` as `semantic-repair/control`,
`semantic-repair/diagnosis` and `semantic-repair/repair80`. The ignored serial
runner `.benchmarks/experiments/semantic-inheritance/run.py` freezes implementations and
records source hashes, task hashes, resolved arguments and each completed run
in `protocol.json`. Logs, timing records, operator effects and coverage records
remain under each variant's `runs/` directory. Results were not edited manually.

Environment: Windows 11 build 26200, Intel Core i7-13700H, Python 3.14.6,
Clingo 5.8.0. The worktree was based on commit
`cc30482b44d7a2c8d2fd7c8be90fdce6b09dbb3c`. The historical control snapshot hash is
`08b5a12d376149e7c7cdbf4cbeedc668e18d109f67d0f195c16438e2b39e2d7c`.

## First batch

Artifacts: `.benchmarks/experiments/semantic-inheritance/repair/`.
The new implementation snapshot hash was
`8ed955f325151ac25b43e83d2ef7d7576e7a4f2ca188330f1a98c1e9fa45a613`.

| Dataset | Variant | Successes / attempted | Mean net seconds | Mean candidate evaluations |
| --- | --- | ---: | ---: | ---: |
| 5queens | Control | 10 / 10 | 6.907233 | 1029.60 |
| 5queens | Diagnosis only | 10 / 10 | 6.573336 | 1029.60 |
| 5queens | Repair 80% | 4 / 5 | 10.206423 | 1487.25 |
| grandparent | Control | 10 / 10 | 0.527706 | 446.10 |
| grandparent | Diagnosis only | 10 / 10 | 0.559762 | 446.10 |
| grandparent | Repair 80% | 10 / 10 | 1.849282 | 1293.10 |

The 5queens repair means describe only the four successful runs. Seed 5 timed
out and seeds 6 through 10 were skipped. The corresponding four control runs
averaged 4.765087 seconds. Diagnosis-only preserved every recorded non-time GA
field at every generation on both datasets. Its small timing changes therefore
do not demonstrate fewer evaluations or faster convergence.

The repair implementation contained an unnecessary random draw on grandparent,
where the prepared space has no constraints. The draw changed subsequent random
choices without providing role information. This was removed before confirmation.
Review also corrected guided proposals bypassing duplicate retries, connected
semantic-effect logging in the epoch loop, and kept cached diagnosis from
reactivating disabled legacy completeness guidance during ordinary fallback.
The measured configurations had zero duplicate retries and legacy guidance
enabled, so those two fixes do not explain the first 5queens regression.

## Corrected confirmation

Artifacts: `.benchmarks/experiments/semantic-inheritance/repair-confirmation/`.
The final implementation snapshot hash is
`3b75e02cf5b434e08de0d6fcf7cd6c841207068d22e6837fe75f2740d950deba`.
The same frozen control was rerun alongside repair. All forty runs succeeded.

| Dataset | Variant | Mean net seconds | Mean candidate evaluations | Mean generations |
| --- | --- | ---: | ---: | ---: |
| 5queens | Control | 4.767414 | 1029.60 | 1412.10 |
| 5queens | Repair 80% | 8.028273 | 2000.40 | 3182.80 |
| grandparent | Control | 0.524320 | 446.10 | 1000.70 |
| grandparent | Repair 80% | 0.546950 | 446.10 | 1000.70 |

Repair increased 5queens mean net time by 68.40 percent and required nearly
twice as many candidate evaluations. Grandparent preserved every non-time GA
field at every generation after the inert random draw was removed. Its 4.32
percent time increase is small in absolute terms and does not show a search
benefit. No unseen-seed validation or confidence claim is made.

| Dataset | Variant | Grounding seconds | Solving seconds | Closure seconds | Remaining Python seconds |
| --- | --- | ---: | ---: | ---: | ---: |
| 5queens | Control | 1.564183 | 0.690499 | 0.105842 | 2.406891 |
| 5queens | Repair 80% | 3.128982 | 0.968412 | 0.227604 | 3.703275 |
| grandparent | Control | 0.192668 | 0.048588 | 0.057849 | 0.225216 |
| grandparent | Repair 80% | 0.193083 | 0.044973 | 0.058284 | 0.250611 |

These are mean net components across ten runs. Remaining Python is total minus
grounding, solving and closure, not an independently measured wall time.
Mean ground and solve call counts, including clause generation, increased from
1014.2 to 1983.7 in 5queens and stayed at 447.1 in grandparent.
The first batch and confirmation have different absolute 5queens times even
for the unchanged control. Compare variants within a batch, not across batches.
The seed that previously timed out finished in confirmation; that does not
erase the earlier timeout or establish a change in its search trajectory.

Across both batches, 95 runs were attempted, 94 succeeded and one timed out.
The remaining five first-batch repair runs were deliberately skipped.

## What the evidence can and cannot tell us

In 5queens the headed program is fixed. Its diagnosis is shared across all
constraint candidates and needs one additional positive-only query per run.
It does not identify the offending constraint. Repair changes the proposal
distribution and suppresses constraint append on diagnosed incomplete inputs.
Although such append cannot recover positives, it can improve negatives.
Therefore excluding it is not justified as an evaluation-saving proof.

Diagnosis-only logged 12,694 changed mutation transitions in 5queens. Both
endpoint evaluations were available for 9,497 of them. Across those known pairs,
the logs count 1,125 positive recoveries, 14,467 positive losses, 5,130 negative
removals and 25,637 negative introductions. These are repeated example-transition
counts, not distinct examples or causal contributions of individual clauses.
The missing pairs are not sampled uniformly, so the totals must not be treated
as unbiased operator success rates.

The useful distinction is between an exact diagnosis and a useful repair choice.
This implementation provides the former. These experiments do not show that
this particular repair preference provides the latter. Both new options remain
disabled by default; no general speedup is claimed.

Tests cover the diagnostic distinction, context isolation, exclusions, strong
negation, role-restricted changes, no classification of unknown constraint-only
inputs, duplicate retries, probability validation, inactive-policy RNG identity,
disabled legacy guidance and whole-program effect logging. The final full suite
passed 646 tests. Ruff and type checking passed.

## Reproduction

Each command runs the named current-source matrix on both datasets:

```powershell
uv run python benchmarks/run_experiments.py semantic-repair/control
uv run python benchmarks/run_experiments.py semantic-repair/diagnosis
uv run python benchmarks/run_experiments.py semantic-repair/repair80
```

The retained serial batch runner additionally interleaves versions and uses
frozen historical control code. Its protocol, rather than separate command
wall times, is the source of the tables here.
