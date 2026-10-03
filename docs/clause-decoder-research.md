# Clause decoder and enumeration research

Research date: 2026-10-02. Sources target Clingo 5.8.2, the version installed
in this workspace and required by `pyproject.toml`. The inspected worktree was
dirty at commit `88d1985557150fedf310d869e43baf76f483db25`; existing changes
were preserved. The measured experiment used the subsequent `7c818b4` source
snapshot plus the benchmark changes recorded in its source hashes. This note
records API facts and experimental measurements, followed by the requested
production integration. External parallel partitions remain unimplemented.

## Decision supported by the source

The first experiment should retrieve the true `selected/3` and `var_at/4`
symbols together, then decode them through metadata prepared once after
grounding. Direct raw-symbol lookup can avoid both per-literal truth calls and
per-symbol argument conversion. Use ordinary output signatures first:

```prolog
#show selected/3.
#show var_at/4.
```

Integer output encoding is an alternative experiment, not a prerequisite.
External parallel partitions remain unimplemented pending an exact-space
comparison and an end-to-end measurement.

## Current local contract

[`generator.py`](../gentians/clauses/generator.py) grounds task-derived facts
and the complete metaprogram, then prepares the decoder index. Complete
materialization calls `solve(on_model=...)`; incremental generation grounds
once, disables cleanup, and uses one resumable solve per body-size assumption.
Incremental sampling sets one solver thread and a seed. Complete generation's
default arguments contain `--parallel-mode=5,split` in
[`arguments.py`](../gentians/arguments.py).

[`decoder.py`](../gentians/clauses/decoder.py) prepares slot/binding metadata
from grounded symbols, then copies the true output once per model into a
reusable buffer. [`representation/output.lp`](../gentians/clauses/metaprogram/representation/output.lp)
shows the two reified signatures. The older truth-probe implementation is now
the benchmark-only [reference decoder](../benchmarks/clause_decoder_reference.py).
Bindings follow each `ClauseMode.binding_positions`, including flattened
nested terms, conditions, aggregate elements and head guards. Predicate arity
is not a substitute for this binding layout. Compound heads select their
complete form; constraints have no selected head, and bodyless rules have no
selected body.

The decoder also reuses immutable reified literals within one Control, and
final materialization reuses mode-dependent metadata within each finish pass.
Both LRU caches have 8192 entries. Their keys retain complete bindings or mode
sequences and their lifetimes preserve task isolation. Measurements and limits:
[materialization reuse](clause-materialization-reductions.md).

[`ClauseCanonicalizer`](../gentians/clauses/canonicalization/clauses.py)
reduces arithmetic systems and retains one preferred representative per key
across complete enumeration. [`ClauseSpace`](../gentians/clauses/clause_space.py)
then deduplicates text and performs the final deterministic ordering. A model
partition can therefore be disjoint before canonicalization while producing
overlapping canonical clauses. Metadata such as body size and dependencies
must also agree with the baseline; equal clause counts alone are insufficient.

## What the APIs actually do

The public Python `Model.symbols(shown=True)` selects displayed atoms and terms;
`atoms=True` selects all atoms regardless of output directives. Its
implementation queries the size, allocates a C array, fills it, and wraps it in
a symbol sequence. `Model.is_true` checks one program literal. `contains`
also checks one atom, and `is_consequence` remains a scalar query, so neither
provides the desired batch truth operation. Models are valid only during their
callback or until enumeration advances. Copy data before returning; never
queue a `Model` for later decoding.
[Python solving API](https://potassco.org/clingo/python-api/5.8/clingo/solving.html),
[5.8.2 Python implementation](https://github.com/potassco/clingo/blob/v5.8.2/libpyclingo/clingo/solving.py).

The C model API exposes a size query and a buffer-copy function, not an array
of true program literals. The destination must hold the selected symbols;
insufficient capacity reports an error. The ordinary two-call approach retrieves
the size on every model and consumes exactly that many entries from a reused buffer.
[C model API](https://potassco.org/clingo/c-api/5.8/group__Model.html).

In 5.8.2 both `clingo_model_symbols_size` and `clingo_model_symbols` call
`m->atoms(show)` independently. The copy implementation accepts capacity
greater than the result size and writes only the actual prefix. The unused
suffix of a reused buffer is not cleared. This path reads the current model;
it does not resume solving.
[5.8.2 C implementation, lines 808–826](https://github.com/potassco/clingo/blob/v5.8.2/libclingo/src/control.cc#L808).

`ClingoModel::atoms` rebuilds its native output vector on each call, and
`OutputBase::atoms` builds a fresh vector. Reusing Python's buffer removes the
caller's allocation, not those native builds. The model predicate checks are
performed against the current solver assignment.
[ClingoModel implementation](https://github.com/potassco/clingo/blob/v5.8.2/libclingo/clingo/clingocontrol.hh#L349),
[OutputBase implementation](https://github.com/potassco/clingo/blob/v5.8.2/libgringo/src/output/output.cc#L495).

`Translator::atoms` visits predicate domains to check their signatures, then
scans every grounded atom in each selected domain, testing truth. Thus two
batch API calls still scan the grounded `selected/3` and `var_at/4` domains
twice, even if only a few atoms are true. Integer `#show` terms instead scan
the term-output table. Fewer Python/C calls is therefore a hypothesis about
speed, not evidence of it.
[Translator implementation](https://github.com/potassco/clingo/blob/v5.8.2/libgringo/src/output/statements.cc#L439).

### Raw symbols and integer terms

The C type `clingo_symbol_t` is a 64-bit symbol representation, not a program
literal ID. Treat it as an opaque lookup key. Build the mapping from actual
grounded symbols rather than unpacking bits or converting AST text.
[C header](https://github.com/potassco/clingo/blob/v5.8.2/libclingo/clingo.h).

In this version the C equality function delegates to `Gringo::Symbol`
equality, which compares `rep_` directly. Function symbols are internalized.
Consequently, a prepared `atom.symbol._rep -> metadata` dictionary matches
the handles copied from the model in the same process. Some handles encode
process-local pointers: do not serialize them, use them as stable benchmark
fingerprints, or send them to another process. Access to `_rep`, `_ffi` and
`_lib` is a private Python binding dependency even when the C functions are
public.
[C equality implementation](https://github.com/potassco/clingo/blob/v5.8.2/libclingo/src/control.cc#L369),
[symbol construction and equality](https://github.com/potassco/clingo/blob/v5.8.2/libgringo/src/symbol.cc#L390).

Using `Symbol` objects as dictionary keys still calls Clingo for their hash
and equality; reading `.arguments`, `.name` and `.number` also crosses into
the native library. Raw lookup can move those conversions to preparation.
[Python symbol implementation](https://github.com/potassco/clingo/blob/v5.8.2/libpyclingo/clingo/symbol.py).

An alternative is to assign a unique integer to each possible selected mode
or variable assignment and show that integer conditionally. A prepared map
from actual `Number(id)._rep` to metadata would avoid per-model numeric
conversion. It requires a collision-free namespace and bounded integer
values, adds output compilation work, and changes the native scan path.
This is an unimplemented design option; no speedup is inferred from compact
output alone.

## Output, projection and parallelism

Ordinary output directives control displayed data. Projective enumeration
changes which solutions are considered equivalent. Explicit projection can
use `#project` atoms; `--project=show` uses output atoms, while `auto` selects
based on the existence of project directives. Test this interaction before
supporting user-supplied projection arguments with a changed output layout.
The two decoder signatures describe the complete reified clause, but a
lossy encoding could merge distinct clauses. Projection can also change
model counts and incremental model-budget prefixes even if the final space
is unchanged.
[Potassco language guide](https://potassco.org/guide/language/),
[5.8.2 projection options](https://github.com/potassco/clingo/blob/v5.8.2/clasp/clasp/cli/clasp_cli_options.inl#L570).

`split` already partitions search dynamically through guiding paths. It is
not five independent Python materializers. In Clingo's bundled clasp,
`ParallelSolve::commitModel` holds the model mutex while reporting a model;
the callback lies inside that serialized section. Several search threads can
solve concurrently, but cannot execute this model pipeline concurrently.
This supplies a reason to measure callback cost before adding solver threads.
It does not establish how much lock contention occurs in a particular task.
[Bundled clasp implementation](https://github.com/potassco/clingo/blob/v5.8.2/clasp/src/parallel_solve.cpp#L628).

`Control.solve` and blocking solve-handle operations release Python's GIL,
but are not thread-safe. Async callbacks may run on another thread. Each
independent worker needs its own `Control`; concurrent solves on one control
are not a supported partition mechanism.
[Control API](https://potassco.org/clingo/python-api/5.8/clingo/control.html).

## Candidate disjoint partitions — unimplemented

These are partitions of the existing legal model space, not smaller task
biases. Each must include every case exactly once:

| Partition key | Local justification | Limitation to measure |
| --- | --- | --- |
| Total clause body size | `clause_body_size/1` already groups incremental models; it counts attached conditions too. | The longest size can dominate; assumptions leave full grounding. |
| Selected complete head form | At most one `selected_head_form/1`; include a separate headless case. | Forms can differ greatly in workload; compound heads must remain indivisible. |
| First occupied body mode, grouped into ranges | Gapless, sorted slots give each nonempty body exactly one minimum mode; include bodyless clauses. | Small first modes may dominate; canonical arithmetic can overlap across groups. |
| Exact number of used variables | Dense variable IDs supply a finite, exhaustive count. | Changing `max_vars` alone is not an exact-count partition; extra guards are needed. |

A shallow prefix can subdivide heavy groups, provided there is a separate
branch for shorter clauses. Constraints or assumptions restrict one worker's
models; removing declarations, changing recalls or disabling pruning can
change the experiment. Constraints added after grounding do not make the
grounded representation smaller. Restricted grounding is a separate
transformation needing its own equivalence proof.

Multiple processes can run separate callbacks and Python construction, at
the cost of repeated preparation, grounding, solver memory and IPC. Start
with one solver thread per process and compare under the same total CPU
budget as the existing five-thread split run. Send ordinary reified values
or canonical data across process boundaries, not model, symbol handles,
control or AST pointers. Measure merge and storage as part of the total.

Preserve one global representative-selection contract. A union of worker
text outputs is not generally enough when workers chose different local
arithmetic representatives. Either merge reified candidates through the
existing canonicalizer or define and test an exact merge over canonical
keys and the existing preference rules. Keep deterministic final ordering.
Incremental generation additionally needs a policy for seeded order,
body-size preference, suspension, model budgets and early cancellation;
complete-space equivalence alone does not preserve those behaviors.

## Experiment and verification protocol

1. Freeze the current dirty source snapshot and task hashes. Compare the
   existing truth-probe decoder, two shown signatures with public symbols,
   and two shown signatures with a prepared raw lookup and reusable buffer.
   Load output directives before the initial grounding in an integrated
   candidate; any experiment that grounds them afterward must record that
   difference.
2. On small spaces compare decoded `ReifiedClause` values for every model.
   Cover empty sides, repeated modes, constants, nested terms, strong/default
   negation, compound heads, head guards, conditional and aggregate locals.
   Then compare exact ordered `ClauseSpace` text and metadata. Existing
   clause-generation and syntax-matrix tests are the semantic gate.
3. Alternate independent control/candidate runs, with identical interpreter,
   Clingo arguments, metrics settings and cache warmup. Report individual
   runs and medians. Avoid concurrent benchmark load.
4. Separate preparation, grounding, callback Python, solving residual,
   final canonical output/storage and process peak RSS. Record native atoms,
   rules, choices, conflicts and models as well as final clauses. A cProfile
   run supplies attribution, not the timing baseline.
5. If testing external partitions, verify both the union of raw model
   encodings and final canonical space, exhaustion and absence of overlap.
   Record per-worker duration, imbalance, aggregate memory and merge time;
   compare with `--parallel-mode=5,split` under a fixed resource budget.

The existing solving residual subtracts callback wall time from the complete
solve wall time. It is useful phase accounting, but not aggregate CPU time
or a direct measurement of callback-induced waits in the other solver
threads. Benchmark whole materialization before claiming a speedup.

## Measured results

### Implemented experimental decoders

[`profile_clause_decoder.py`](../benchmarks/profile_clause_decoder.py) compares
the frozen scalar truth-probe reference with four shown-symbol variants: public
`Model.symbols`, raw size/copy calls, a flat-state raw decoder, and a flat-state
decoder with one native copy call. All shown variants select only `selected/3`
and `var_at/4`, with output loaded before the initial grounding. The task's
facts, legality, symmetry and pruning rules remain identical.

The one-call variant preallocates a capacity equal to the maximum selected
slots plus their argument positions. Before each model it zeroes the buffer.
Every prepared output handle is verified to be nonzero, so the unused zero
suffix terminates iteration. This specifically accounts for the native API's
uncleared suffix; it does not assume that a reused array knows the new length.
Raw handles are converted to prepared slot/binding metadata, never unpacked or
persisted. Decoded values follow the existing index and binding-position order.

The initial version was a version-specific prototype. The requested integration
now uses the one-copy decoder in complete and incremental production generation,
with the same private binding dependency as the previous decoder. The initial
prototype loaded output in a second grounding, which increased
native atoms/rules; those exploratory runs are excluded from the whole-space
comparison below. The measured version loads output before grounding and checks
the same native atoms/rules as the control.

### Environment and accounting

Windows 11, Python 3.14.6, Clingo 5.8.2; Intel Core i7-13700H, 14 cores /
20 logical processors, approximately 32 GiB physical RAM. Complete runs use
`0 --parallel-mode=5,split`, the existing default. Instrumentation exports and
cProfile are disabled. Literal-instantiation caches start empty in each complete
run; task parsing occurs beforehand. The experiment retains the production
`ClauseCanonicalizer` and `ClauseSpace`.

Decode and canonicalization are elapsed callback-stage times, including native
calls made by those stages. Solving residual subtracts the entire callback wall
time; it is not pure native CPU time. Complete totals include preparation,
grounding, callbacks, solving and final `ClauseSpace` storage, and exclude task
loading, output fingerprinting and report serialization. Peak RSS is cumulative
for the process, not per-run allocation or a memory delta. Each JSON includes
the effective arguments, environment and relevant source/task SHA256 values.

Another Python process was consuming CPU during these runs. The results are
exploratory measurements under concurrent load, not an isolated speed guarantee.
An initial output in `.debug` disappeared during execution, preventing its
completed Alzheimer row from being saved; that lost run is excluded. Subsequent
reports use `.benchmarks/experiments/decoder-research-20261002/`.

### Complete-space measurements

Alzheimer acetyl was measured in the order control, candidate, candidate,
control (the last control ran in a separate invocation). These are the actual
completed runs, not a selection of the fastest result:

| Run | Total s | Decode s | Canonicalization s | Solving residual s | Final storage s |
| --- | ---: | ---: | ---: | ---: | ---: |
| Truth control 1 | 130.420 | 23.454 | 21.822 | 79.017 | 1.849 |
| Single-scan candidate 1 | 97.810 | 15.623 | 14.958 | 62.283 | 2.352 |
| Single-scan candidate 2 | 160.883 | 27.600 | 26.655 | 99.744 | 4.091 |
| Truth control 2 | 128.628 | 21.105 | 19.460 | 83.175 | 1.584 |

Median total: **129.524 s control, 129.347 s candidate**, approximately 0.14%
difference. This does not establish a stable materialization speedup. Native
parallel enumeration and concurrent machine load are confounders, and two runs
per method do not estimate that variance reliably. The candidate's faster first
run must not be reported alone as a 25% optimization.

Every complete run exhausted **289,326 models** and produced **289,326 clauses**.
All ordered text and metadata fingerprints were
`44f8cb5181ee57dc45c6aec1947d03aea0dd50321825321489fa6f79d7461836`.
All controls and candidates had **36,718 ground atoms** and **1,251,053 rules**.
Native choices/conflicts vary with five-thread split; each row retains them.
These checks support exact-space preservation for this task and configuration,
not a universal proof for every Clingo projection option or language task.

The control's median decode stage is 22.280 s, canonicalization 20.641 s and
solving residual 81.096 s. Decode is worth investigating; the larger residual
remains relevant. Replacing callbacks with a batch API is not, by itself,
evidence that complete enumeration scales better.

Local generated reports:

- [First control and small paired tasks](../.benchmarks/experiments/decoder-research-20261002/full-five-threads.json).
- [Two candidate runs](../.benchmarks/experiments/decoder-research-20261002/full-five-threads-candidate.json).
- [Final control](../.benchmarks/experiments/decoder-research-20261002/full-five-threads-final-control.json).

The candidate report was generated by the earlier benchmark CLI, whose generic
protocol string mentions alternating order. Its invocation selected only the
candidate; the four-run order stated above is the actual combined protocol.
Current output records the decoder selection explicitly.

### Same-model attribution

An exhaustive solve decoded every one of the **289,326 identical live models**
with all five methods, rotating method order at each callback and checking exact
`ReifiedClause` equality every time. This isolates decoder attribution within
one enumeration; the solver cadence differs from ordinary materialization
because each callback runs five decoders and no canonicalizer.

| Decoder | Decode s across all models | Microseconds/model | Speedup over truth probes |
| --- | ---: | ---: | ---: |
| Existing truth probes | 15.028 | 51.943 | 1.000× |
| Public shown symbols | 17.851 | 61.697 | 0.842× |
| Raw size/copy, nested state | 13.278 | 45.893 | 1.132× |
| Raw size/copy, flat state | 12.796 | 44.227 | 1.174× |
| One copy, cleared buffer, flat state | 9.600 | 33.180 | **1.566×** |

The one-copy decoder uses **36.1% less elapsed decode time** in this experiment.
Public symbol retrieval is slower than the existing decoder. Fewer API calls
and prepared metadata help here, but batching through the public API alone
does not. These seconds are not rescaled to the earlier 33.558 s Python total
or to the complete control's decode time.

[Complete same-model report](../.benchmarks/experiments/decoder-research-20261002/same-models-full.json).
All recorded production and task hashes match across the measured reports;
only the experimental benchmark CLI changed between invocations.

### Conclusion and verification

There is a measured decoder improvement on identical models, but **no stable
end-to-end improvement demonstrated by these whole-space runs**. Following the
request to implement it, the one-copy decoder is now the production path. This
does not turn the faster first candidate run into a whole-pipeline speed claim.
The benchmark retains the frozen previous decoder as its control. Projection,
buffer reuse and incremental behavior have dedicated regression coverage.

`tests/test_profile_clause_decoder.py` checks all five decoders on complete
small syntax spaces: facts, constraints, exact/combined compound heads,
variable head bounds, empty heads, nested terms, conditions, aggregates and
strong/default negation. It also checks complete final output and metadata,
poisons reused buffers to detect stale suffix reads, verifies bounded exhaustion,
and reuses a prepared decoder across seeded incremental body-size solves.

Initial investigation verification: **39 tests passed** across the new decoder benchmark tests and
the existing clause-report/cProfile tests; Ruff passed on touched Python paths;
`uv run ty check` passed. The affected chains are standalone measurement and
documentation, with generation parity tests for the prototype. Task language,
production generation, algorithms, strategies, coverage, `timing.py`, dashboard
producer/schema and preview did not change.

Reproduce attribution and paired materialization:

```powershell
uv run python benchmarks/profile_clause_decoder.py --datasets alzheimer_acetyl --limit 0 --out .benchmarks/experiments/decoder-research/same-models-full.json
uv run python benchmarks/profile_clause_decoder.py --datasets alzheimer_acetyl --materialize --repeats 2 --out .benchmarks/experiments/decoder-research/full-pairs.json
```

`--override 'clause_generation.clingo_arguments=["--parallel-mode=1"]'` changes
only the runtime solver configuration. `--decoder truth_probes` or
`--decoder shown_single_scan` selects individual exhaustive methods. The CLI
prints and saves each completed row, including its effective arguments and
source hashes; generated reports remain local and ignored by Git.

### Production integration

`_ModelDecoder` is built once after grounding and owns prepared metadata and
the reused buffer. `_clause_from_model` remains the counted callback entry point
for cProfile. Complete enumeration and incremental batches share this decoder;
incremental cleanup stays disabled and no live `Model` is retained.

The production module contains only the one-copy implementation. The previous
truth-probe code lives in `benchmarks/clause_decoder_reference.py` as a frozen
measurement control and parity oracle, also used by historical microbenchmarks.
The comparison tool uses the actual production function for its one-copy row.

`profile_clauses.py` now prints a three-column table by default and writes no
artifacts. Its seconds measure clause-space generation wall time, excluding task
loading. `--debug` enables detailed metrics and snapshot JSON; `--debug --cprofile`
adds the separate profile and its `.prof`/JSON. Compact mode disables and restores
ambient generation instrumentation, including on failure. Dashboard timing/schema
and charts retain their existing contract.

Integration verification: **1,026 tests passed** across clause generation,
incremental batches, pruning, the syntax matrix, decoder parity, profiling and
historical decoder benchmarks. Ruff and `uv run ty check` passed. The affected
chains are generation (metaprogram output, prepared decoder and both consumers),
standalone measurement and documentation. Task syntax, evolutionary strategies,
coverage and dashboard producer/schema/preview did not change.

A complete production run on Alzheimer acetyl, with the same five-thread split
and a cold literal cache, exhausted **289,326 models and final clauses**. Its
ordered content/metadata SHA256 exactly matches the previous control:
`44f8cb5181ee57dc45c6aec1947d03aea0dd50321825321489fa6f79d7461836`.
It retained 36,718 ground atoms and 1,251,053 ground rules. Total materialization
was 147.182 s: preparation 2.665 s (including grounding 2.324 s), decoding
17.245 s, canonicalization 21.901 s, solver wall time excluding callbacks
103.670 s, final storage 1.438 s and remaining callback bookkeeping 0.264 s.
This single integration run verifies full-space parity; it does not establish an
end-to-end speed improvement over the earlier controls.

[Production integration report](../.benchmarks/experiments/decoder-integration-20261002/full.json).
Reproduce:

```powershell
uv run python benchmarks/profile_clause_decoder.py --datasets alzheimer_acetyl --materialize --repeats 1 --decoder shown_single_scan --out .benchmarks/experiments/decoder-integration/full.json
```

### Parallel enumeration finding

One exploratory run with `--parallel-mode=1` was cancelled after approximately
three minutes without exhausting Alzheimer acetyl. It supplies no complete
space fingerprint or final duration and is not used as a completed comparison.
This evidence does not support changing the default to one thread. External
process partitions were researched but not implemented or benchmarked.

Body-size assumptions are the simplest existing partition key, but their worker
grounding still includes the complete bias and the largest size may dominate.
Any proposed process experiment must compare against the current five-thread
split under the same resource budget, reconcile canonical representatives
globally, and include grounding duplication, transfer, merging and memory.
