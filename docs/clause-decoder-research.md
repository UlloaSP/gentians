# Clause decoder and enumeration research

Research date: 2026-10-02. Sources target Clingo 5.8.2, the version installed
in this workspace and required by `pyproject.toml`. The inspected worktree was
dirty at commit `88d1985557150fedf310d869e43baf76f483db25`; existing changes
were preserved. This note records API facts and candidate experiments. It does
not itself claim a measured speedup or implement parallel partitions.

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

[`decoder.py`](../gentians/clauses/decoder.py) currently prepares program
literals for the two signatures and probes truth through Clingo's CFFI
interface. Its early exits rely on gapless slots and nondecreasing mode IDs
within a section, enforced by
[`symmetry/slots.lp`](../gentians/clauses/metaprogram/symmetry/slots.lp).
Bindings follow each `ClauseMode.binding_positions`, including flattened
nested terms, conditions, aggregate elements and head guards. Predicate arity
is not a substitute for this binding layout. Compound heads select their
complete form; constraints have no selected head, and bodyless rules have no
selected body.

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
insufficient capacity reports an error. Retrieve the size on every model and
consume exactly that many entries from a reused buffer.
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

Reserved for the controlled runs accompanying this investigation. This
research pass performed source inspection only; no performance numbers or
partition results were generated here.
