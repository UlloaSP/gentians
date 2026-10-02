# Shared clause Python optimizations

The fourth set of ten changes removes repeated Python work in clause analysis,
normalization and decoding. Production changes are limited to eight Python
modules under `gentians/clauses/`. No `.lp` module, task file, language frontend,
hypothesis operator or coverage rule was edited for this work. Earlier changes
and measurements are recorded in [clause-python-prepared.md](clause-python-prepared.md).

## Implemented changes

| Change | Owner under `gentians/clauses/` | Result |
| --- | --- | --- |
| Retain linear coefficients | `arithmetic_literal.py` | Derive coefficients at first use, cache both tuples and non-linear `None`, and avoid adding an AST walk to construction. Clones start with their own uncomputed cache; identity is unchanged. |
| Prepare comparison traversal | `clause_mode.py`, `canonicalization/expression_normalization.py` | Compile postorder term instructions once per mode; later decoding substitutes bindings without traversing native template nodes. |
| Fuse arithmetic metadata collection | `canonicalization/arithmetic.py` | Collect builtin separation and external, safe and numeric variable sets in one body traversal, preserving the no-builtin path and body order. |
| Decode without suffix copies | `decoder.py` | Iterate from the bisected index instead of slicing the remaining candidates, preserving truth-probe order, section resets and gaps. |
| Share pair properties | `analysis/inference.py`, `analysis/relation_properties.py` | Compare extension/arity groups once for equivalence, implication, inverse, mutex, complement domains and disjoint argument domains. Expand to every original signed predicate; negation permission remains per pair. |
| Share projected inclusion | `analysis/relation_properties.py` | Group both source and target aliases by extension and arity, prove complete-tuple inclusion once, and emit all original predicate facts. |
| Share column inclusion | `analysis/relation_properties.py` | Group identical column sets, cache matches for identical domains and expand sorted original argument indexes, retaining exact output order. Empty domains skip setup. |
| Compare minimal determinants | `analysis/relation_properties.py` | Group composite dependencies by predicate/output, process determinant sizes in order and compare only retained minimal sets. Keep all original tuple orders for equal determinant sets. |
| Share syntactic rule inspection | `analysis/inference.py`, `analysis/rule_properties.py` | Cache immutable syntax hints and propagation templates locally for at most eight exact programs. Clingo proofs and propagation through currently proven keys still run per context. |
| Bound partition capacity with top counts | `analysis/relation_properties.py` | Prepare tuple counts once and use `nlargest` for the remaining capacity. Equal-sized relations use the exact multiplication directly. Preserve partition sizes, minimality and product limit. |

Derived metadata does not participate in equality or hashing. Relation grouping
never identifies `p/n` with `-p/n`; each gets its own facts. Composite subsumption
still runs after intersection across contexts.

## Protocol

Measured on 2026-10-02 with CPython 3.14.6, Clingo 5.8.2, Windows 11 build
26200 and Intel64 Family 6 Model 186 Stepping 2. Two detached worktrees start
at `c9501c74a4e631b7c686f3d467eba20f9fe53615`. The control includes the preceding
prepared-clause changes and the language changes present when this round
started; it is a frozen worktree snapshot, not the plain commit. The candidate
copies this snapshot and replaces only the eight production modules above.
Source manifests confirm that these are the only differing Python modules.
They have identical language, ASP metaprograms and benchmark tasks.

The SHA-256 of the sorted `gentians/**/*.py` path/hash manifest is
`3c3ace07b6d0e2294e757683289559a6010245642b19a1a7ab3bba2e53fb7592`
for the control and
`8cdc942a0d79354dc9871b313dc620c5ff525a768fb130d676c3cb264c05c443`
for the candidate. Another agent's later language and profiling changes remain
in the main workspace and are included in a separate integrated test snapshot.

Both variants run the same harness with the same interpreter, sequentially:

```powershell
$env:PYTHONHASHSEED = '0'
& C:/software/gentians/.venv/Scripts/python.exe benchmarks/profile_clause_shared.py --repeats 7 --memory
```

Fixtures are prepared once, followed by one warmup and seven timed samples.
Production timing is disabled for these microbenchmarks. Results are medians;
semantic fingerprints are computed outside timing. One extra warmed run uses
`tracemalloc`. Its peak excludes native Clingo memory, fixtures and previously
retained caches; it is not RSS or retained metadata size. The cold coefficient
case constructs 1000 pairs of arithmetic literals. The cold comparison case
constructs 300 modes from an existing native template, excluding parsing.

Warm coefficient reads repeat 10000 times for linear and non-linear literals.
Comparison decoding repeats 1000 times on a depth-40 function template. Trait
scans repeat 2000 times over 18 body literals, with a warmed arithmetic-system
cache. Wide decoding repeats 200 times over 3000 candidates per slot; small
decoding repeats 1000 times. Pair analysis uses twelve independent, identical
4000-row binary extensions, or six distinct 80-row extensions. Projection
sharing uses twenty source and twelve target aliases of 300-row extensions.
Domain sharing uses thirty three-column predicates and forty two-position
domains. Dependency cases include nested determinants and a size-four antichain
over nine input positions for six predicates.

The syntax-only cases compare inspection of twelve programs without grounding
or solving: the repeated case has 100 normal rules plus a choice rule, and the
distinct case has twelve different programs with ten normal rules each. Their
fixtures have no key-propagation equalities, so both implementations return the
same syntax hints. The separate full syntax cases run the real closed-world
pipeline and Clingo proofs in every context. They are not isolated Python
timings. Partition cases use sixty, or six, equal-sized disjoint relations; the
small case repeats 100 times. Complete and incremental enumeration use a warmed
small task IR and seed 31; they do not measure cold frontend parsing.

## Isolated results

All 24 semantic fingerprints match. Times are milliseconds; ratio is control
median divided by candidate median. Peaks are Python allocation bytes.

| Workload | Control ms | Candidate ms | Ratio | Peak bytes |
| --- | ---: | ---: | ---: | ---: |
| Warm coefficient reads | 356.3660 | 3.1692 | 112.45x | 237 → 168 |
| Arithmetic literal construction | 32.8386 | 17.0318 | 1.93x | 741 → 773 |
| Prepared comparison decoding | 1543.2649 | 77.3825 | 19.94x | 18629 → 12400 |
| Comparison mode construction | 33.5556 | 156.5940 | 0.21x | 4120 → 7091 |
| Arithmetic metadata, cache warm | 63.1605 | 23.4266 | 2.70x | 1848 → 2000 |
| Metadata, no builtins | 5.2063 | 3.7429 | 1.39x | 880 → 760 |
| Wide decoder | 4.3931 | 2.4199 | 1.82x | 5456 → 1552 |
| Small decoder | 3.4908 | 2.3770 | 1.47x | 752 → 752 |
| Pair analysis, identical extensions | 27.7606 | 25.4907 | 1.09x | 2218880 → 2219136 |
| Pair analysis, distinct extensions | 2.3497 | 1.7931 | 1.31x | 221888 → 221688 |
| Projected inclusion, aliases | 30.4437 | 1.2658 | 24.05x | 178864 → 166832 |
| Projected inclusion, distinct extensions | 0.2768 | 0.2660 | 1.04x | 3936 → 4624 |
| Domain inclusion, repeated columns/domains | 18.1080 | 1.6984 | 10.66x | 304592 → 304624 |
| Domain inclusion, distinct columns/domains | 0.1844 | 0.1218 | 1.51x | 1336 → 2888 |
| Nested determinant reduction | 24.1391 | 4.9045 | 4.92x | 1468640 → 1824592 |
| Antichain determinant reduction | 9.4914 | 3.3828 | 2.81x | 211184 → 296744 |
| Syntax inspection, repeated program | 375.8787 | 34.6864 | 10.84x | 11339 → 9983 |
| Syntax inspection, distinct programs | 49.6471 | 68.7264 | 0.72x | 10586 → 25147 |
| Closed-world syntax and proofs, repeated | 1082.3552 | 1151.1808 | 0.94x | 40706 → 42498 |
| Closed-world syntax and proofs, distinct | 440.0750 | 255.9901 | 1.72x | 68329 → 82422 |
| Wide partitions | 1005.4271 | 437.6144 | 2.30x | 223736 → 226016 |
| Small partitions | 32.5467 | 19.6282 | 1.66x | 7952 → 8320 |
| Small complete enumeration | 83.4919 | 46.7092 | 1.79x | 34388 → 34367 |
| Small incremental enumeration | 85.3311 | 50.1043 | 1.70x | 38066 → 38045 |

The first implementation eagerly derived arithmetic coefficients and regressed
on construction. Lazy first-use caching removes that added traversal. The first
partition implementation used a heap even for equal counts; the exact uniform
bound avoids its overhead. Empty numeric-position generators and empty-domain
setup are also skipped. Domain expansion now sorts only matching original
indexes rather than rescanning every argument for membership in an included set.

Comparison preparation is 4.67 times slower in its cold fixture: compiling
instructions transfers work from repeated normalization to construction.
Prepared modes retain those instructions. Composite determinant grouping raises
the traced peak by about 24% on nested inputs and 41% on the antichain. Distinct
syntax inspection is 38% slower and uses more Python memory; the local cache
helps repeated programs, while unique programs pay for immutable hints and
cache management. The full repeated-program syntax case is 6.4% slower despite
the isolated inspection gain, because it retains the real Clingo work.

The machine showed substantial variation between measurement batches, including
unchanged cold construction and native Clingo paths. For example, control-only
small enumeration medians ranged from approximately 43 to 85 ms. Consequently
the ratios are observations for these fixtures, not precise causal estimates or
general speed guarantees. No speed improvement is claimed for cold arithmetic
construction, unique-program syntax analysis or full search. Tiny distinct-domain
and small-decoder results also varied between batches. Fewer traversals and
subset checks are independently covered by regression tests.

## End-to-end checks

Four `profile_clauses.py` snapshots match exactly, including canonical text,
head signatures, dependencies and body cost: `grandparent` has 326 clauses,
`constant_colour` 2, `coloring` 59 and `subset_sum_unbalanced_ops` 49.

Both variants ran seeds 32, 33 and 34 for three tasks and both algorithms:

```powershell
& C:/software/gentians/.venv/Scripts/python.exe benchmarks/profile_baseline.py --datasets grandparent constant_colour coloring --runs 3 --seed-base 31 --timeout-seconds 30 --set iterations_genetic=50 --out-dir <fresh-result-directory> --python C:/software/gentians/.venv/Scripts/python.exe
```

Repeat with `--set algorithm=incremental` for incremental search. The existing
dashboard producer reports disjoint grounding (G), solving (S), Python (P) and
closure (C) times, averaged over three runs in milliseconds. Total excludes
subprocess startup.

| Algorithm / task | Total control → candidate | G | S | P | C |
| --- | ---: | ---: | ---: | ---: | ---: |
| steady_state / grandparent | 161.091 → 161.145 | 64.346 → 64.708 | 20.426 → 20.309 | 69.138 → 69.549 | 7.181 → 6.579 |
| steady_state / constant_colour | 44.398 → 47.575 | 30.805 → 33.328 | 1.772 → 2.005 | 11.540 → 11.958 | 0.282 → 0.285 |
| steady_state / coloring | 181.218 → 181.903 | 86.796 → 86.913 | 22.469 → 22.463 | 68.326 → 68.909 | 3.627 → 3.618 |
| incremental / grandparent | 104.285 → 102.175 | 56.902 → 55.193 | 7.100 → 7.119 | 37.717 → 37.347 | 2.566 → 2.516 |
| incremental / constant_colour | 40.008 → 39.857 | 28.510 → 28.606 | 0.586 → 0.549 | 10.640 → 10.458 | 0.271 → 0.244 |
| incremental / coloring | 85.144 → 84.332 | 44.095 → 43.837 | 7.803 → 7.508 | 31.968 → 31.782 | 1.277 → 1.204 |

All eighteen paired genetic traces match after excluding only `elapsed_seconds`.
Candidate counts, perfect-result counts, ground/solve call counts, operator and
coverage summaries, epochs and restarts match. Per-phase Clingo call and model
totals also match. Perfect-result counts are 1/3, 3/3, 0/3 for steady-state
grandparent, constant_colour and coloring; incremental counts are 0/3, 3/3, 0/3.
These short runs verify preserved search behavior, not convergence. The full
search totals show no consistent overall speedup; steady-state constant_colour
is 7.2% slower in this batch. Unchanged grounding, solving and closure also vary.

Raw outputs and source manifests remain outside the repository and were not
edited by hand. This work adds a benchmark harness without changing timing,
the dashboard producer, schema, preview or charts. The paired producer's schema
version remains 13. Concurrent profiling changes belong to the other agent.

## Verification and affected chains

Twenty-three new regression cases cover lazy coefficients and non-linear
results; compiled comparisons with nested terms, tuples, intervals, arithmetic
and chained operators; independent metadata-set reconstruction; signed pair
property oracles; exact alias expansion and reduced row/subset visits; composite
dependency oracles with empty and reordered determinants; bounded syntax-cache
reuse with a real Clingo counterexample and context-dependent key propagation;
independent partition enumeration with product thresholds; and decoder probe
order without tuple slices. They pass in the final integrated snapshot.
Independent read-only review found no critical or important correctness issues,
including the lazy coefficient, uniform-capacity and ordered domain refinements.

The frozen integrated snapshot passes all 1975 tests in 157.91 seconds using
`C:/software/gentians/.venv/Scripts/python.exe -m pytest -q`. It starts at
`c29bc4d74b2604ef4b35ec5c8b711d1bd5d7452b` and copies the current workspace files,
including concurrent language and profiling work without editing their originals.
Freezing inputs prevents source-fingerprint races while the other agent continues
working. Ruff passes for `gentians/clauses/`, the adapted compilation test, the
new regressions and the new harness; `uv run ty check` passes as well. The eight
production files match both the benchmark candidate and integrated validation
snapshot byte for byte. The adapted/new test files and harness match validation.
Temporary worktrees are removed after verification.

The language chain applies to static evidence, prepared mode metadata,
canonicalization and decoding. Task syntax, ASP legality and rendered semantics
are unchanged, so the language contract needs no amendment. Both algorithms use
these components; their loops, states and factories are unchanged. Coverage still
evaluates complete hypotheses and keeps contexts isolated. Measurement uses the
existing phase contract. The [clause-generation guide](clause-generation.md)
documents the updated preparation and reuse boundaries.
