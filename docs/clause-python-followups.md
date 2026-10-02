# Clause Python follow-up optimizations

The second set of ten Python changes preserves the task language, pruning
facts and canonical clause output. No `gentians/language/` file, `.lp` module,
benchmark task, evaluation rule or hypothesis operator is changed by this work.
The first set of optimizations is recorded in
[clause-python-optimizations.md](clause-python-optimizations.md).

## Implemented changes

| Change | Owner | Effect |
| --- | --- | --- |
| Reuse proven keys during dependency enumeration | `analysis/relation_properties.py` | Skip determinant scans containing a key, while retaining all functional-dependency facts needed before context intersection. |
| Share tuple-mutex projections | `analysis/relation_properties.py` | Compute once per identical extension and arity, then emit the original predicate pairs, including distinct strong-negation signatures. |
| Extract consequence atoms natively | `analysis/ground_relations.py` | Replace the Python `is_true` loop over symbolic atoms with `Model.symbols(atoms=True)` for brave and cautious models. |
| Reuse identical effective consequence programs | `analysis/inference.py` | Bound the per-analysis cache to eight entries; include lower-bound rules in the key and preserve separate context classification and proofs. |
| Skip zero-factor row rebuilding | `canonicalization/linear_normalization.py` | Reuse unaffected rows during auxiliary-variable elimination. |
| Cache immutable variable sets | `canonicalization/expression.py`, `linear_constraint.py` | Compute each queried object's set once, including empty sets, without changing equality or hashing. |
| Prepare head metadata once | `clause_mode.py`, `canonicalization/clauses.py` | Reuse head predicates, dependencies and condition counts during decoding. |
| Preserve unchanged substitution nodes | `analysis/rule_properties.py` | Return the original AST for an empty mapping or unchanged subtree; rebuild only changed paths. |
| Traverse arithmetic modes iteratively | `canonicalization/expression_normalization.py`, `arithmetic_literal.py` | Preserve binding order and coefficient signs while removing recursive construction and coefficient collection. |
| Traverse pruning head guards iteratively | `pruning.py` | Handle deeply nested guards while retaining conservative rejection of unknown theory atoms. |

## Protocol

Measured on 2026-10-02, Windows 11 build 26200, Intel64 Family 6 Model 186
Stepping 2, CPython 3.14.6 and Clingo 5.8.2. The control is revision
`0e315c5796b34e5cf17cc5caaecd97b01d72676f`. Two detached worktrees used that
revision; the candidate received only the twelve production Python files above.
This freezes the language implementation while another agent changes the main
worktree. Both variants use the same virtual environment and `PYTHONHASHSEED=0`.
Run the harness from each worktree, using the same interpreter:

```powershell
$env:PYTHONHASHSEED = '0'
& C:/software/gentians/.venv/Scripts/python.exe benchmarks/profile_clause_followups.py --repeats 7 --memory
```

The harness is copied unchanged to the control. Each workload constructs its
fixtures once, warms up once, then reports the median of seven wall-clock
samples. Fingerprints are computed outside the timed region. A separate extra
run measures Python allocations with `tracemalloc`; this excludes native Clingo
memory and is neither RSS nor total retained cache memory. The normalization
workload clears the component cache on each invocation. Variable-set workloads
read the same warmed object 1000 times, and metadata workloads decode 1000
clauses against already compiled modes. Production timers are disabled in these
microbenchmarks. The consequence and context workloads include Clingo grounding
and solving and must not be interpreted as isolated Python timings.

## Isolated results

All seventeen before/after result fingerprints match. Times are milliseconds;
the ratio is control median divided by candidate median. Peaks are Python
allocation bytes, control to candidate.

| Workload | Control ms | Candidate ms | Ratio | Peak bytes |
| --- | ---: | ---: | ---: | ---: |
| Keyed dependencies, 500 rows, arity 7 | 26.1682 | 3.1960 | 8.19× | 40872 → 40064 |
| Unkeyed dependencies, arity 4 | 0.0687 | 0.0607 | 1.13× | 2344 → 2344 |
| Mutex, 12 identical extensions, arity 5 | 162.6470 | 13.2157 | 12.31× | 1633528 → 1624064 |
| Mutex, 6 distinct singleton extensions | 0.0797 | 0.0750 | 1.06× | 11424 → 11776 |
| Brave and cautious consequences | 155.9522 | 39.9313 | 3.91× | 581865 → 343254 |
| 20 repeated effective context programs | 34.0666 | 9.1814 | 3.71× | 42866 → 48577 |
| 12 distinct effective context programs | 8.1755 | 8.0947 | 1.01× | 40602 → 48303 |
| Sparse auxiliary elimination | 38.8186 | 0.9638 | 40.28× | 319480 → 160672 |
| Expression variable-set reads | 111.8602 | 0.0468 | 2390.18× | 16304 → 0 |
| Linear variable-set reads | 30.8433 | 0.0627 | 491.92× | 5496 → 0 |
| Head metadata during decoding | 7.4263 | 1.2088 | 6.14× | 3016 → 2976 |
| Substitution with no matching variable | 14.9580 | 3.8217 | 3.91× | 19387 → 10354 |
| Substitution of one head variable | 15.0815 | 4.0863 | 3.69× | 23499 → 11695 |
| Small arithmetic-mode expressions | 17.7975 | 18.9682 | 0.94× | 200365 → 1511 |
| Nested head guard, depth 180 | 2.4669 | 2.1269 | 1.16× | 296013 → 1363 |
| Small complete enumeration | 42.3649 | 34.7925 | 1.22× | 32626 → 33994 |
| Small incremental enumeration | 41.7763 | 34.5052 | 1.21× | 36349 → 37717 |

The large variable-read ratios concern repeated access to a warmed object. Each
object now retains a field and, when queried, its variable set; a zero allocation
peak does not mean zero object memory. Prepared head metadata moves work into
mode construction, which these decoding measurements exclude. The bounded
context cache increases Python allocation peaks in both context fixtures and
helps only when effective programs repeat. Distinct-extension mutex and small
unkeyed-dependency results provide no convincing speed claim at these durations.

Small arithmetic-mode expressions take 6.6% longer in this run. Their iterative
implementation passes depth-1400 tests and allocates less traced Python memory;
its benefit is removal of the recursion failure, rather than a speed claim for
small expressions. The old recursive local function can leave collectible
closure cycles, so its traced peak also depends on garbage-collection timing.
The small enumeration ratios do not establish a general search speedup.

## End-to-end checks

`profile_clauses.py` snapshots compare exactly, including canonical text, head
predicates, dependencies and body cost: `grandparent` has 326 clauses,
`constant_colour` 2, `coloring` 59 and `subset_sum_unbalanced_ops` 49.

The full-search control and candidate each ran three seeds (32, 33, 34) on
`grandparent`, `constant_colour` and `coloring` under both algorithms:

```powershell
& C:/software/gentians/.venv/Scripts/python.exe benchmarks/profile_baseline.py --datasets grandparent constant_colour coloring --runs 3 --seed-base 31 --timeout-seconds 30 --set iterations_genetic=50 --out-dir <fresh-result-directory> --python C:/software/gentians/.venv/Scripts/python.exe
```

Repeat with `--set algorithm=incremental` for incremental search. Existing full
instrumentation is enabled. Grounding (G), solving (S), Python (P) and dependency
closure (C) are the existing dashboard producer's disjoint phase totals,
averaged across three runs, in milliseconds. They are not subprocess wall times.

| Algorithm / task | Total control → candidate | G | S | P | C |
| --- | ---: | ---: | ---: | ---: | ---: |
| steady_state / grandparent | 114.755 → 109.556 | 49.841 → 45.749 | 11.191 → 10.765 | 48.764 → 48.194 | 4.959 → 4.848 |
| steady_state / constant_colour | 34.064 → 29.846 | 24.524 → 21.155 | 0.941 → 0.833 | 8.376 → 7.660 | 0.223 → 0.198 |
| steady_state / coloring | 131.591 → 120.820 | 61.036 → 58.595 | 19.328 → 14.227 | 48.755 → 45.798 | 2.471 → 2.200 |
| incremental / grandparent | 80.379 → 87.864 | 42.474 → 47.053 | 5.646 → 6.023 | 30.337 → 32.631 | 1.921 → 2.157 |
| incremental / constant_colour | 33.380 → 34.055 | 24.122 → 24.332 | 0.443 → 0.424 | 8.608 → 9.071 | 0.207 → 0.228 |
| incremental / coloring | 68.533 → 74.124 | 35.606 → 38.239 | 6.136 → 6.277 | 25.882 → 28.347 | 0.909 → 1.261 |

All eighteen paired genetic traces match after excluding only `elapsed_seconds`.
Candidate counts, perfect-result counts, grounding/solving call counts, operator
summaries and coverage summaries match. Perfect-result counts are 1/3, 3/3, 0/3
for steady-state grandparent, constant_colour and coloring, respectively;
incremental counts are 0/3, 3/3, 0/3. These deliberately short runs measure
equivalence, not convergence.

The incremental candidate is 2–9% slower in this batch. Grounding, solving and
unchanged closure also vary, so three short sequential runs cannot attribute
these differences to the Python changes. The result supports the isolated
workload improvements and output preservation, but does not establish an
end-to-end speed improvement for either search algorithm. Raw generated files
remain outside the repository and are not edited by hand. The dashboard schema
stays at version 13 and no producer, preview or chart contract changes.

## Semantic verification and affected chains

Thirty new regression cases use independent pairwise functional-dependency and
tuple-mutex oracles, stable-model union/intersection oracles, isolated open and
closed contexts, exact-input cache reuse/eviction, unsatisfiable contexts,
zero-factor elimination, signed head metadata, hash/equality/remapping checks,
unchanged AST identity, and depth-1400 arithmetic and pruning traversals.
The decoder test still forbids materializing symbols for stable models returned
by clause enumeration, while allowing native brave/cautious consequence reads.
The integrated workspace passes all 1848 tests (`uv run pytest -q`, 138.99 s),
including the concurrently updated language tests. Ruff passes for the changed
clause code, tests and benchmark; `uv run ty check` also passes. Independent
review found no critical or important correctness issues. The benchmark now
records the hash seed in its environment metadata so cross-process fingerprint
comparisons can verify the fixed-seed condition explicitly.

The language chain applies to static analysis, compiled mode metadata,
canonicalization and rendering, covered by generation and syntax tests. It adds
no task-language syntax or semantics, so the language contract is unchanged.
Both algorithm paths use the shared generator and are checked above; their loops,
state and evolutionary factories are unchanged. Coverage and dependency closure
still evaluate the complete hypothesis. The measurement chain reuses existing
timing fields and schema; documentation updates the clause-generation guide.
