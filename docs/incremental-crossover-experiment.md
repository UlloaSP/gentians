# Constraint probes and the incremental crossover

> Historical measurements. The active matrix and API were simplified on 2026-09-10.
> Old experiment IDs and ablation switches below are no longer executable options.
> See [the current SDK comparison](sdk-defaults-comparison.md) for current behavior.
> Local artifact links describe the original measurement locations and may be absent.

## Retained implementation

Incremental can make a bounded number of constraint proposals during initialization
and after each new clause batch. The retained default is `constraint_probes=16`.
It applies when the prepared ClauseSpace has no heads and the task has positives.
The proposal starts from the best complete candidate in the population, or asks
HypothesisGenerator for a single-clause candidate when none is complete. It appends
from the new clauses, or replaces a clause at the program-size limit. Every
proposal passes through HypothesisGenerator and the normal whole-program evaluator.
A better complete candidate becomes the base for subsequent proposals in that batch.
Ordinary replacement and the evolutionary search remain in use.

This is a search preference, not per-clause fitness, additive coverage or semantic
pruning. Failed proposals do not establish that a clause is globally useless.
No empty candidate is evaluated. Initialization and replacement own the measured
cost of their probes; no artificial timing phase was introduced. A perfect
candidate stops probing immediately. `constraint_probes=0` disables the policy.

## Small-task protocol and results

All runs use a 30-second external process timeout and unlimited generations,
full instrumentation, no cProfile, population 10, batch 128, archive 8192, epochs
50, elite count 10 and headed-space restart 100. Other selection, crossover,
mutation and replacement settings match the preceding incremental experiments.
There is no constraint inheritance. Only constraint_probes changes between the
incremental variants. The steady-state reference uses the same shared strategies.

Discovery ran control then probes on 5queens seeds 1-10 and grandparent seeds
11-20. Validation used unseen 5queens seeds 61-70, in order probes, incremental
control, steady-state. Transfer to another arithmetic constraint task used
4queens seeds 101-110, control before probes. There are 90 small-task runs in
this study. The fixed ordering is not fully interleaved, and machine timing varied
substantially; a timing difference alone cannot establish an algorithmic speedup.

All returned perfect programs have score 22026.465795. These means cover clean
successful processes only; the successful subsets differ where timeouts occurred.
A timeout is not assigned a fabricated net time.

| Group | Task | Variant | Success / runs | Net seconds | Peak RSS MiB | Evaluations | Generations |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| Discovery | 5queens | Incremental control | 6/10 | 13.507 | 85.515 | 1543.3 | 1950.7 |
| Discovery | 5queens | Probes 16 | 10/10 | 13.906 | 88.824 | 2270.7 | 2205.3 |
| Discovery | grandparent | Incremental control | 10/10 | 0.962 | 45.760 | 701.6 | 1024.4 |
| Discovery | grandparent | Probes 16 | 10/10 | 1.691 | 45.712 | 701.6 | 1024.4 |
| Validation | 5queens | Incremental control | 4/10 | 16.909 | 92.157 | 1720.5 | 2282.3 |
| Validation | 5queens | Probes 16 | 10/10 | 11.627 | 84.882 | 1971.2 | 1896.1 |
| Validation | 5queens | Steady-state | 9/10 | 13.056 | 105.407 | 1604.6 | 2427.9 |
| Transfer | 4queens | Incremental control | 10/10 | 0.400 | 42.053 | 89.9 | 155.4 |
| Transfer | 4queens | Probes 16 | 10/10 | 0.305 | 42.215 | 63.3 | 106.4 |

For a matched timing comparison, the four validation seeds completed by both
incremental variants averaged 16.909 versus 9.347 net seconds, 92.157 versus
77.329 MiB peak RSS, and 1720.5 versus 1571.25 evaluations. These four seeds alone
are not the success-rate sample.

On the nine validation seeds completed by both steady-state and probes, means
were 13.056 versus 12.520 net seconds, 105.407 versus 87.984 MiB peak RSS, and
1604.6 versus 2129.4 evaluations. Thus fewer evaluator calls are not the explanation
for the observed steady-state time comparison. Candidate complexity, phase costs
and machine variability also matter. The strongest evidence is the preserved
or increased observed success, plus the separate 4queens reduction in evaluations.

Grandparent reproduced every recorded non-time GA metric at every generation for
all ten matched seeds. Its increased measured time occurred despite an unchanged
search trajectory; it must not be presented as extra search work caused by probes.

## Scaling protocol

`uv run python -m benchmarks.synthetic_million --sweep` generates five tasks under
`.benchmarks/experiments/incremental-crossover/tasks/`. They keep exactly the same
background, examples, 32 feature modes and six-clause reference solution. Only
`#maxbl` changes from 2 through 6. Every reference clause has body length two.
The legal spaces contain sum(comb(32, k), k=1..maxbl) clauses: 528, 5488, 41448,
242824 and 1149016. The tests check unchanged fixed task text and the reference
solution at every limit. These are nested languages, but changing the language
can also change enumeration order and the search landscape.

Each algorithm receives seeds 101-103 at each size, unlimited generations and
the same 30-second process timeout. No 500-generation cutoff is used. Both use
constraint_probes=16 in their Arguments; steady-state does not consume that setting.
Execution ascends by body limit and alternates the first algorithm between sizes.
A further three-run incremental control with probes disabled uses the largest
space to check whether the new policy loses quality there.

Resource snapshots retain the last completed GA record every approximately
200 ms, along with the sampled phase. A timeout snapshot is censored. Its peak
RSS and CPU are lower bounds at the last sample, and its score is observed search
progress, not a returned SearchResult. Missing progress is not replaced by zero.
Only clean completed runs provide canonical net total_execution. Sampling never
flushes the full instrumentation buffers. Three seeds locate large effects in
this family; they do not establish precise success rates or a universal threshold.

## Scaling results

All 30 size-comparison runs reached the external timeout without returning a
perfect hypothesis. These are means of the last observed score and sampled peak
RSS, not time-to-solution measurements. A missing score means no generation-zero
record was published; it is not a score of zero.

| Legal clauses | Steady score | Incremental score | Steady RSS MiB | Incremental RSS MiB |
| ---: | ---: | ---: | ---: | ---: |
| 528 | 5517.76 | 3306.50 | 44.97 | 44.15 |
| 5488 | 6121.30 | 2167.00 | 67.86 | 46.03 |
| 41448 | 631.81 | 3968.88 | 268.21 | 55.12 |
| 242824 | Not observed | 7758.07 | 122.74 | 54.67 |
| 1149016 | Not observed | 11306.31 | 174.53 | 55.72 |

At 5488 clauses, steady-state still gives the better observed quality. At 41448,
incremental gives better quality and uses less sampled resident memory. This
brackets the observed crossover between those sizes for this task family and
30-second budget. It does not identify a universal threshold. In particular,
5queens has different clause structure and evaluation costs.

At the two largest sizes, every steady-state worker was still in
clause_generation at its final resource sample. The lower observed RSS at 242824
than at 41448 does not mean materializing more clauses is cheaper: these workers
were killed before completing the same pipeline stage. Incremental reached
search at every size. CPU consumption can exceed 30 CPU seconds because Clingo
uses several worker threads; it is not canonical net execution time.

The largest-space control without probes averaged score 6192.92, 58.72 MiB,
853.3 evaluations and 956.7 generations. Probes averaged score 11306.31,
55.72 MiB, 791.7 evaluations and 676.3 generations. Probes improved score on
seeds 101 and 103, but lost on seed 102, 6141.39 versus 7319.12. All six runs
timed out. This supports retaining the policy, not a claim that it always wins.

## Decision

Keep constraint_probes=16 as the incremental default. The policy improved
observed success on both 5queens seed groups, transferred to 4queens with fewer
evaluations, left grandparent's search trajectory unchanged, and improved mean
observed quality in the million-clause control. It has no benchmark-name branch.
The algorithm remains in incremental_clause_genetic.py and uses existing
hypothesis construction, evaluation and replacement. No additional cache or
parallel evaluation path was introduced.

The global algorithm default remains steady_state. The measured crossover is a
family-specific interval, not enough evidence for an automatic selector based
only on clause count. For this synthetic family and budget, steady-state is
preferable for quality through 5488 clauses, while incremental is preferable
from 41448 among the measured points. An exact transition inside that interval
was not measured. Three seeds and fixed ordering limit confidence.

Historical incremental experiment configurations explicitly disable probes so
that rerunning an old control does not silently enable the new policy. The
measured probe arms already explicitly requested 16. Promoting the fallback and
SDK default after measurement does not change those arms' behavior.

## Reproduction and environment

Experiment parameters are in benchmarks/experiments.toml. Small runs have IDs
under incremental-stagnation/probe*, transfer runs under
incremental-crossover/4queens-*, and scaling runs under
incremental-crossover/body*. Python is 3.14.6, Clingo is 5.8.0, and the machine is
Windows 11 on Intel Core i7-13700H. Base revision is e25270e with a modified worktree.

`.benchmarks/experiments/constraint-probes/` retains before.py, candidate.py,
protocol.json, summarize.py and summary.json. The crossover directory has its
own protocol, generated tasks, aggregator and summary. Protocols record hashes
and the instrumentation stages: validation added search-progress snapshots, and
scaling also records the sampled phase. All algorithms within a comparison use
the same instrumentation stage. Raw run data remain unedited.

Final verification passed 595 tests with `uv run pytest -q`, Ruff on touched
Python files and `uv run ty check`. A separate static review found no blocking
issues. `final-source.json` records hashes after default promotion; the original
measurement protocols retain their original source hashes.

To regenerate the large tasks and repeat one matched size without replacing
existing artifacts:

```powershell
uv run python -m benchmarks.synthetic_million --sweep
uv run python benchmarks/run_experiments.py incremental-crossover/body4-steady_state incremental-crossover/body4-incremental
```

Use the other body2 through body6 IDs for the complete sweep. The runner may
reuse matching results; `--force` intentionally replaces an existing experiment.
