# Prepared clause Python optimizations

The third set of ten Python changes prepares reusable mode and relation data.
It preserves canonical clauses, pruning facts, context boundaries and complete
hypothesis evaluation. This work edits six production files under
`gentians/clauses/`; it changes no `.lp` module, language frontend, benchmark
task, hypothesis operator or evaluation rule. Earlier measurements are in
[clause-python-optimizations.md](clause-python-optimizations.md) and
[clause-python-followups.md](clause-python-followups.md).

## Implemented changes

| Change | Owner under `gentians/clauses/` | Effect |
| --- | --- | --- |
| Prepare arithmetic traversal | `clause_mode.py`, `canonicalization/expression_normalization.py` | Compile postorder instructions once; normalization substitutes input bindings without walking the template AST again. |
| Share intrinsic extension analysis | `analysis/inference.py` | Analyze argument relations, dependencies, products and binary properties once per identical extension and arity within a context, retaining every original signed predicate. |
| Check argument pairs in one pass | `analysis/relation_properties.py` | The first row selects equality or distinctness; remaining rows check only that property, preserving empty and singleton policies. |
| Reuse binary graph and domain | `analysis/inference.py`, `analysis/relation_properties.py` | Share a successor index between transitivity and cycle checks; reuse positional domains for reflexivity. |
| Prove totality by cardinality | `analysis/relation_properties.py` | After reflexivity, transitivity and antisymmetry are established, replace pair enumeration with the exact `n*(n+1)/2` tuple count, preserving the minimum domain size. |
| Stop failed projection inclusion early | `analysis/relation_properties.py` | A single compatible target checks membership row by row; multiple targets still share a materialized projection. |
| Share the key index after intersection | `analysis/inference.py`, `analysis/relation_properties.py` | Build one index for both functional-dependency filters, then release it before composite subsumption. |
| Reuse condition ordering | `mode_facts.py` | Cache sorted conditions and original position mappings for one compilation call, preserving duplicates and emitted deletion indexes. |
| Cache the complete mode hash | `clause_mode.py` | Lazily retain the structural identity hash, avoiding collisions between distinct tasks whose local mode ids repeat. |
| Bisect decoder mode candidates | `decoder.py` | Skip the sorted prefix below the section's current minimum mode id without a Python loop over that prefix. |

The old mode hash already used only `id` and was constant time. The ninth change
does not remove repeated AST hashing from that baseline: it pays for a complete
identity hash once to improve cache distribution across tasks, then reuses it.
Derived metadata and the cached hash do not participate in equality.

## Protocol

Measured on 2026-10-02 with CPython 3.14.6, Clingo 5.8.2, Windows 11 build
26200 and Intel64 Family 6 Model 186 Stepping 2. The control is revision
`c9501c74a4e631b7c686f3d467eba20f9fe53615`. Two detached worktrees used this
revision. The candidate received only the six production Python files above;
the harness was identical in both. This isolates these changes from another
agent's concurrent edits to `gentians/language/` in the main workspace. The
interpreter and environment were shared, with `PYTHONHASHSEED=0`.

```powershell
$env:PYTHONHASHSEED = '0'
& C:/software/gentians/.venv/Scripts/python.exe benchmarks/profile_clause_prepared.py --repeats 7 --memory
```

Each fixture is prepared once, followed by one warmup and seven timed samples.
Production timing is disabled in these microbenchmarks. The reported time is
the median; result fingerprints are computed outside timing. A separate extra
run uses `tracemalloc` after warmup. Its peak excludes native Clingo memory,
fixture construction and previously retained caches, including arithmetic
instructions and the mode hash. It is neither RSS nor total retained memory.
The arithmetic workload substitutes the same prepared mode 1000 times. The
conditional workload compiles all facts for 52 modes with twelve-condition and
eleven-condition alternatives. Decoder workloads repeat 200 wide or 1000 small
decodes. Complete and incremental workloads generate from a warmed small task
IR; they are not cold frontend or large search benchmarks.

The total-order fixture supplies its three prerequisite proofs as already
true. Its ratio measures the final totality check alone. The cache fixture
queries 100 warmed modes from different tasks, all with local id zero, ten
times. It deliberately exercises the old id-only hash collision pattern.

## Isolated results

All seventeen result fingerprints match. Times are milliseconds, ratio is
control median divided by candidate median, and peaks are Python allocation
bytes from control to candidate.

| Workload | Control ms | Candidate ms | Ratio | Peak bytes |
| --- | ---: | ---: | ---: | ---: |
| Prepared arithmetic instructions | 31.2079 | 2.9901 | 10.44× | 1675 → 864 |
| Intrinsics, 12 identical extensions | 5.4286 | 2.0127 | 2.70× | 143576 → 47800 |
| Intrinsics, 6 distinct extensions | 1.6132 | 1.3871 | 1.16× | 72192 → 73904 |
| Argument pairs, all equal | 1.1651 | 1.0135 | 1.15× | 1576 → 1576 |
| Argument pairs, mixed rows | 10.6278 | 6.6897 | 1.59× | 1664 → 1664 |
| Binary checks, 4000-edge path | 6.8122 | 5.0075 | 1.36× | 1011544 → 1364128 |
| Final totality check, prerequisites proven | 58.4634 | 0.0071 | 8234.29× | 10560 → 0 |
| Projection inclusion fails early | 3.1820 | 0.8845 | 3.60× | 170312 → 170312 |
| Projection inclusion succeeds | 2.8096 | 2.8873 | 0.97× | 170312 → 170312 |
| Key and dependency reduction | 5.1809 | 5.2592 | 0.99× | 307384 → 307384 |
| Conditional mode fact compilation | 1286.1747 | 32.8808 | 39.12× | 371067 → 347624 |
| Warm mode-hash reads | 2.0418 | 1.9354 | 1.05× | 0 → 36 |
| Literal cache across tasks with repeated ids | 53.8378 | 0.1709 | 315.03× | 0 → 0 |
| Decoder, 3000 choices per slot | 249.3650 | 4.4396 | 56.17× | 1552 → 5456 |
| Decoder, two choices per slot | 4.8609 | 3.3085 | 1.47× | 752 → 752 |
| Small complete enumeration | 100.4726 | 64.1655 | 1.57× | 34084 → 34087 |
| Small incremental enumeration | 109.4474 | 60.5597 | 1.81× | 37754 → 37712 |

The initial argument-pair implementation maintained both flags throughout the
scan and regressed on all-equal rows. The measured final implementation selects
one branch using the first tuple. This avoids that regression while retaining
the mixed-row improvement.

Successful projections are 2.8% slower in this fixture, which has repeated
projected rows: streaming checks every source row, whereas a materialized set
deduplicates them before inclusion. The benefit applies to failures that stop
early. The key-index change removes duplicate index construction, but this
whole-reduction measurement shows no convincing speed gain. Binary graph reuse
increases the traced peak by about 35% because the graph remains live during
other checks. The decoder's tuple slice also raises its wide-fixture peak.
Prepared modes retain extra metadata whose construction and retained size are
excluded from the warmed arithmetic and hash fixtures.

The final totality and multi-task cache ratios apply to their stated narrow
fixtures. The small enumeration results do not establish a general speedup for
search or for cold mode compilation.

## End-to-end checks

`profile_clauses.py` snapshots match exactly, including canonical text, head
signatures, dependencies and body cost: `grandparent` has 326 clauses,
`constant_colour` 2, `coloring` 59 and `subset_sum_unbalanced_ops` 49.

Both variants ran three seeds (32, 33, 34) for three tasks and both algorithms:

```powershell
& C:/software/gentians/.venv/Scripts/python.exe benchmarks/profile_baseline.py --datasets grandparent constant_colour coloring --runs 3 --seed-base 31 --timeout-seconds 30 --set iterations_genetic=50 --out-dir <fresh-result-directory> --python C:/software/gentians/.venv/Scripts/python.exe
```

Repeat with `--set algorithm=incremental` for incremental search. Existing full
instrumentation is enabled. The following are the existing dashboard producer's
disjoint grounding (G), solving (S), Python (P) and closure (C) totals, averaged
over three runs in milliseconds. Total excludes subprocess startup.

| Algorithm / task | Total control → candidate | G | S | P | C |
| --- | ---: | ---: | ---: | ---: | ---: |
| steady_state / grandparent | 147.904 → 174.139 | 63.300 → 71.995 | 18.031 → 20.731 | 60.713 → 73.930 | 5.859 → 7.482 |
| steady_state / constant_colour | 51.284 → 50.234 | 35.297 → 35.182 | 2.144 → 2.234 | 13.532 → 12.511 | 0.310 → 0.307 |
| steady_state / coloring | 197.351 → 196.034 | 94.872 → 94.798 | 24.093 → 23.323 | 74.533 → 73.972 | 3.853 → 3.942 |
| incremental / grandparent | 129.090 → 108.903 | 69.541 → 56.944 | 9.131 → 7.784 | 47.523 → 41.447 | 2.895 → 2.727 |
| incremental / constant_colour | 48.266 → 38.006 | 34.754 → 26.677 | 0.669 → 0.519 | 12.529 → 10.469 | 0.314 → 0.340 |
| incremental / coloring | 97.210 → 83.181 | 50.242 → 41.045 | 8.435 → 6.966 | 36.919 → 34.013 | 1.614 → 1.158 |

All eighteen paired genetic traces match after excluding only `elapsed_seconds`.
Candidate counts, perfect-result counts, grounding/solving call counts,
operator and coverage summaries, epochs and restarts match. Perfect-result
counts are 1/3, 3/3, 0/3 for steady-state grandparent, constant_colour and
coloring; incremental counts are 0/3, 3/3, 0/3. Clingo's internal choice and
conflict counts vary in the steady-state runs. These short runs check preserved
search behavior rather than convergence.

Steady-state grandparent is 17.7% slower in this batch, while incremental totals
are 14–21% lower. Grounding, solving and unchanged closure also vary, so three
sequential runs do not establish a general speed improvement or attribute these
differences to the changed Python paths. Raw generated results remain outside
the repository and are not edited by hand. No dashboard producer, timer,
preview, chart or schema changes; schema version remains 13.

## Semantic verification and affected chains

Twenty-six new regression cases cover mixed and empty argument relations;
shared extension analysis with distinct signed predicates; independent random
binary-relation and projection oracles; non-mutated shared graphs; exact total
order cardinality; early projection failure; one key index after intersection;
arithmetic AST binding order without repeated traversal; duplicate conditional
forms; full mode-hash identity and cache independence; and decoder boundaries,
section resets and slot gaps. Existing exhaustive relation and depth-1400
arithmetic tests also cover the changed helper APIs. Independent review found
no critical or important correctness issues, including the final argument-pair
refinement.

The fixed integrated validation snapshot passes all 1904 tests in 199.15 seconds
with the same virtual-environment interpreter (`python -m pytest -q`). It includes
the concurrent language changes present when copied, without modifying their
original files. An earlier run in the actively edited main workspace had one
experiment-index fingerprint failure; that case and all 29 tests in its file
passed on repetition. The fixed snapshot avoids source changes between manifest
and index fingerprint checks. Ruff passes for `gentians/clauses/`, the changed
tests and the new benchmark; `uv run ty check` also passes. All six production
files and the regression/benchmark files match the validated snapshot byte for
byte. Temporary worktrees are removed after verification.

The language chain applies to static analysis, compiled metadata, fact
generation, decoding and canonicalization. Task syntax, ASP legality and
rendered clause semantics remain unchanged, so the language contract needs no
change. Both algorithms use these shared components; their state, loops and
evolutionary factories remain unchanged. Coverage still evaluates complete
hypotheses and keeps example contexts isolated. Measurement uses the existing
phase contract. The clause-generation guide documents the new reuse boundaries.
