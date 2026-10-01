# Witness-based coverage and constraint selection

> Offline measurement, 2026-10-01. Nothing here is implemented in `gentians/`.
> The scripts replay real searches or run beside them.

## Question

Can stable models already found (witnesses) decide coverage without solving, or
replace the search? Three exact schemes were measured against the current
evaluator, plus one applicability count.

A witness is a stable model of `static + P` that extends an example, where
`static` is the background plus the coverage program. Non-monotonicity is
global, but for one fixed interpretation `W` it splits into two checks:

- `W` stays a stable model after adding a rule that `W` satisfies;
- `W` stays a stable model after removing a rule that does not fire in `W`
  (no ground body is true in `W`). A satisfied constraint never fires.

Both checks ground one rule against the facts of `W`. Neither is a per-clause
fitness: each holds only relative to one interpretation.

| Scheme | What it uses | What it can prove |
| --- | --- | --- |
| I, control | Existing constraint inheritance (`evaluation.constraint_inheritance`) | Ones and zeros, only between programs with the same headed rules |
| A, delta witnesses | Up to four witnesses per example, revalidated with the two checks | Ones only |
| B, exhaustive extensions | Every stable model of `static + headed rules` that extends some example, enumerated the second time a headed program appears, cap 512 | Ones and zeros for any constraint set on that headed program |
| C, constraint selection | Constraint-only spaces. Stored models, the constraints each violates, one Clingo call that picks the smallest constraint set, and counterexamples from the real program | The whole hypothesis |
| D, exception operator | Learn `q`, then add `not q` to a body (FOLD style) | Counted only |

A covered example has a certificate (a witness). An excluded example has none
in general, which is why A cannot prove zeros and B must enumerate.

## Protocol

- Source: commit `face4d6f3d2ac33c1ead6606e30f8c1047c67d7d`. The worktree was clean for every
  catalog run. Catalog task files were not edited by this experiment.
- Environment: Windows 11 build 26200, Intel Core i7-13700H, Python 3.14.6, Clingo 5.8.2.
- Control: `steady_state` with SDK defaults, including constraint inheritance.
- Replay (I, A, B): the 31 default datasets, seeds 43, 44 and 45, at most 500
  evaluations and 60 seconds per search. Every distinct candidate the real
  search evaluates is logged with its coverage, then re-evaluated in order.
  Evaluation time is one fresh control with brave enumeration, as the solver
  does. Every verdict of A and B is compared with the logged coverage.
- Selection (C): the ten constraint-only datasets. Control is the real search,
  seeds 43 to 52, 60-second wall limit. C is deterministic and was run ten
  times. Both timings include clause generation. Every hypothesis from C is
  verified with the real `CandidateEvaluator`.
- Scale probe: a local copy of `5queens` with `#maxv(6)`, `#maxbl(6)` and
  recall 3 for `q/2`, giving 283,072 constraints instead of 4,797. Five seeds,
  300-second limit for the search, 1,500 seconds for C.
- Runs were serial. Instrumentation was off.

## Results

### Soundness

15,392 evaluations were replayed. A and B produced no wrong coverage bit, and
no rule shape was left untranslated. Head aggregates, body aggregates and
arithmetic are covered by the datasets; disjunctive heads and contexts are not,
because no catalog task uses them.

### A and B on real trajectories

Totals over the three seeds. "Skipped" is the fraction of evaluations fully
decided without solving. "Left" is the evaluation time that remains; "cost" is
what the scheme spends to obtain and check its evidence.

| Dataset | Evaluations | Evaluation time, s | Skipped I | Skipped A | Skipped B | A: left + cost, s | B: left + cost, s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| set_partition_sum_cardinality_and_square | 1,081 | 181.24 | 0.10 | 0.66 | 0.62 | 140.12 + 39.37 | 87.27 + 255.67 |
| magic_square_no_diag | 423 | 10.12 | 0.04 | 0.61 | 0.58 | 6.42 + 33.39 | 3.61 + 25.07 |
| set_partition_sum_and_cardinality | 1,500 | 6.78 | 0.06 | 0.33 | 0.57 | 5.40 + 56.60 | 2.83 + 168.99 |
| 5queens | 1,500 | 3.07 | 0.02 | 0.12 | 1.00 | 2.68 + 3.70 | 0.01 + 3.00 |
| subset_sum_double_unbalanced_count | 1,292 | 2.56 | 0.00 | 0.00 | 0.02 | 2.56 + 8.98 | 2.50 + 833.10 |
| latin_square | 835 | 1.61 | 0.05 | 0.26 | 0.40 | 1.19 + 4.08 | 0.90 + 3.46 |
| 8queens | 581 | 0.79 | 0.06 | 0.31 | 0.99 | 0.54 + 0.81 | 0.00 + 1.62 |
| coloring | 545 | 0.40 | 0.09 | 0.36 | 0.88 | 0.25 + 1.10 | 0.05 + 5.22 |
| grandparent | 1,500 | 0.71 | 0.00 | 0.00 | 0.00 | 0.71 + 1.52 | 0.71 + 0.00 |
| All 31 datasets | 15,392 | 218.38 | 0.04 | 0.18 | 0.40 | 169.78 + 169.75 | 105.67 + 1,493.27 |

Skipped A and B include what I already decides. With I, A and B together 45%
of all evaluations are decided without solving, against 4% for I alone.

A also knew before solving that 5,144 of the 6,812 inconsistent candidates
covered a negative, and that 3,169 of the 4,515 complete candidates covered
every positive.

Neither scheme pays in time. An evaluation costs between 0.5 and 2 ms on most
tasks, less than obtaining and checking the evidence. In no dataset is "left +
cost" clearly below the control. The closest case is
`set_partition_sum_cardinality_and_square`, where an evaluation costs 168 ms:
A leaves 140.12 s and costs 39.37 s, against 170.79 s left by I. Of that cost,
32.21 s is solving again to collect witnesses and 3.72 s is checking.

B fails on headed spaces for a second reason: enumerating every extension costs
far more than one brave query, and a new headed program needs a new enumeration.
`sudoku` exceeded the cap in all three enumerations.

### C against the search, constraint-only datasets

| Dataset | Constraints | Search mean, s | Search median, s | Search max, s | Search evaluations | C mean, s | C max, s | C iterations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5queens | 4,797 | 6.821 | 4.236 | 20.905 | 2,335 | 2.581 | 2.724 | 1 |
| 8queens | 4,797 | 1.663 | 1.624 | 2.162 | 136 | 1.742 | 1.784 | 1 |
| 4queens | 313 | 0.175 | 0.165 | 0.306 | 66 | 0.164 | 0.168 | 1 |
| hamming_0 | 4 | 0.182 | 0.179 | 0.215 | 5 | 0.135 | 0.141 | 1 |
| hamming_0_unbalanced | 27 | 0.221 | 0.211 | 0.299 | 12 | 0.145 | 0.148 | 1 |
| hamming_1 | 4 | 0.183 | 0.180 | 0.205 | 4 | 0.134 | 0.137 | 1 |
| hamming_1_unbalanced | 27 | 0.226 | 0.211 | 0.318 | 12 | 0.141 | 0.146 | 1 |
| clique | 6 | 0.080 | 0.079 | 0.094 | 18 | 0.083 | 0.086 | 1 |
| knapsack | 8 | 0.074 | 0.071 | 0.100 | 19 | 0.045 | 0.047 | 1 |
| sudoku | 4 | 0.145 | 0.143 | 0.163 | 7 | 0.409 | 0.437 | 8 |

Both solved every run, and every hypothesis from C verified as a solution. C
needs one selection in nine datasets because every positive there has at most
64 extensions, so sparing one stored model is exact. `sudoku` has partial
positives and needed eight iterations and one nogood.

C is faster only on `5queens`, 2.6 times in the mean and 7.7 times in the worst
case, and it removes the variance. It is slower on `sudoku` and equal within
noise elsewhere. In `5queens` C spends 0.73 s generating clauses, 1.17 s
classifying all 4,797 constraints against 45 models and 0.43 s selecting.

### C does not scale with the clause space

| 5queens variant | Constraints | Search, 5 seeds | Search evaluations | C |
| --- | ---: | --- | ---: | --- |
| catalog | 4,797 | mean 6.821 s (10 seeds) | 2,335 | 2.581 s |
| wide probe | 283,072 | mean 121.11 s, range 86.39 to 152.08, 5 of 5 solved | 1,724 | no result in 1,500 s |

A second run of C on the probe, with a 1,700-second limit, spent 124.6 s generating
clauses, 134.7 s classifying the constraints against 45 models, and was still
in its first selection call when the limit arrived, more than 1,400 s later.
The process held 6.6 GB.

Unrelated uncommitted edits to `gentians/clauses/canonicalization/` began in the
worktree while the probe was running. The first run of C started on the clean
source. The five searches and the phase breakdown imported the edited source, so
their numbers are indicative and need a rerun on a frozen tree.

The search needed no more evaluations in a space 59 times larger. C classifies
and grounds every constraint of the space, so its cost grows with the space
while the search samples it.

### D, exception operator

Only `coin` has clauses that negate by default a predicate another clause
defines (6 of its 8 clauses). `penguin` negates a background predicate. The
other 29 spaces contain no default negation over a learnable predicate, so the
operator has nothing to act on in this catalog and was not measured further.

## Reading

- The decomposition is correct and gives exact evidence, including a priori
  verdicts for most inconsistent and complete candidates.
- It does not reduce cost at the current price of an evaluation. A is worth
  revisiting only for tasks whose evaluations cost tens of milliseconds, and
  only with witnesses taken from the evaluation's own solve.
- C replaces the search on small constraint-only spaces and loses on large
  ones. No scheme here approaches an unbounded reduction, in line with the
  Sigma-2-P hardness of the general problem.

## Limits

- A and B were measured by replay. Their effect on an end-to-end run, with
  partial queries for the undecided examples, was not measured.
- The checker and the violation matrix are prototypes. A large part of their
  cost is Python reading Clingo symbols; a tighter implementation would lower
  the costs above but not the count of skipped evaluations.
- Witness collection re-solves once per uncovered example because brave
  enumeration does not expose its intermediate stable models through the API.
- Three seeds per dataset, 500 evaluations per search; the scale probe is one
  task with five seeds. Timings are single runs on one machine.
- C handles only spaces without headed clauses, picks the smallest constraint
  set, and uses a whole failed constraint set as a nogood rather than a core.
- No catalog task uses example contexts or disjunctive heads.

## Reproduction

Scripts and raw results live under the ignored directory
`.benchmarks/experiments/witness/`. From that directory:

```powershell
uv run python witness.py <datasets> 43,44,45 500
uv run python baseline.py <datasets> 43,44,45,46,47,48,49,50,51,52
uv run python cegis.py <datasets> 10
uv run python exceptions.py
```

`<datasets>` is a comma-separated list of catalog names or task directories.
