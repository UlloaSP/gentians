# Variation policy and dependency-block mutation

Steady-state and epoch-pool search use the same mutation and crossover factories.
`RandomGroupMutation` owns mutation decisions. `evolution/variation.py` provides
cached classification and the existing crossover policy. `HypothesisGenerator`
owns dependency closure, size limits and valid
construction. Mutation has one registered implementation; its factory remains.
The policy does not change the task language. Clause generation additionally
applies the documented positive-only pruning before producing `ClauseSpace`.

## Constraint normalization

The early counterpart lives in `clauses/task_analysis.py` and
`clauses/metaprogram/core/constraints.lp`. With no negatives and headed alternatives,
it checks whether an included positive predicate cannot be
defined by the background and its isolated context. This sufficient proof permits
removing headless models during enumeration. Uncertain cases retain constraints.
See [the full contract](language-bias.md#positive-only-constraint-pruning).

Without negative examples, a closed candidate drops optional pure constraints
when the remaining program is nonempty. Removing integrity constraints preserves
existing stable models and therefore preserves brave positive witnesses, including
positive examples with excluded atoms. Background and context constraints are
untouched. A constraint-only
candidate remains legal because the current genotype contract forbids empty
hypotheses. Constraints can therefore remain when their removal would violate
that contract. No claim about generalization outside observed examples follows.

## Dependency blocks

Mutation selects one root clause. The effective change may contain several
clauses, determined by the current candidate rather than a fixed grouping.

| Operation | Dependency treatment |
| --- | --- |
| Append | Add the root and transitively close missing providers. Reuse existing providers; do not insert every alternative. |
| Remove | Delete the root, then repeatedly delete consumers lacking a provider. Never insert replacement providers. |
| Replace | Consider the replacement head while removing unsupported consumers of the old clause, then close the new block. Removed clauses cannot be reintroduced as repair. |

Providers in the background or remaining candidate preserve their consumers.
Signed predicates are distinct. Removing a consumer does not automatically
remove its providers, which can have other uses. Cycles are handled through the
same syntactic closure invariant; mutual recursion does not establish semantic
support or the existence of a stable model.

The resulting candidate must remain nonempty, inside the active pool and within
`#maxpl`. Append is available below the size limit; removal requires more than
one clause and must not empty the candidate after cascading. Replacement needs
an absent alternative. The mutable mask protects the entire changed block,
including providers and removed consumers. An invalid alternative is skipped.

## Unified mutation

Configure the sole strategy through `create_mutation`:

```python
mutation = {
    "name": "random_group",
    "probability": 0.9,
    "random_jump_probability": 0.1,
    "complete_generator_removal_probability": 0.1,
}
```

All probabilities reject booleans, nonnumeric values and values outside `[0, 1]`.
`structural_neighbor` was removed without an alias. Migrate that configuration to
`random_group` and retain the desired jump probability. Historical experiment IDs
and output directories remain; their old results are not measurements of this
implementation.

After the overall mutation probability gate, known perfect candidates are
returned unchanged. Other candidates use this policy:

| Candidate state | Permitted mutation |
| --- | --- |
| Complete, with positives | Edit constraints only, except for the separate headed-block deletion attempt. |
| Incomplete, with positives and negatives | Add or edit headed clauses; remove headed blocks or constraints. Constraint replacement is not attempted. |
| No positives | Do not freeze headed clauses on vacuous completeness. Ordinary block edits remain available. |
| No negatives | Do not introduce pure constraints. Existing constraints may be removed or replaced by headed clauses, including normalization when a constraint-only candidate acquires a headed block. |

On a complete candidate containing headed clauses, one draw selects a
headed-root deletion attempt with probability
`complete_generator_removal_probability`. Cascading may also remove dependent
constraints. If no such deletion is legal, try ordinary constraint edits.
There is no redraw and no fallback to headed replacement or addition. The
offspring receives normal evaluation; this operation does not certify redundancy
or preserve completeness in advance.

For ordinary edits, shuffle the structurally available operation types and return
the first valid changed candidate. Failed attempts can therefore change the
distribution of successful operations; the operator does not promise equal
frequencies of accepted append, remove and replace operations.

Each replacement attempt has one independent `random_jump_probability` draw.
Otherwise source and replacement must have the same set of signed predicate
signatures in their heads. This does not preserve argument order, head form,
body size or body similarity. All pure constraints have the empty head signature.
A jump permits but does not require another signature, and never overrides the
state policy or block protection.

Incomplete candidates do not add pure constraints, including through a headed
replacement. This deliberately prioritizes recovering positives over edits that
only reduce negative coverage. Removing a headed rule is also allowed: under
nonmonotonic semantics it can recover positive witnesses.

## Constraint edits and semantic limits

With the headed program fixed, adding integrity constraints can only remove
stable models. Removing constraints preserves existing models. Therefore adding
constraints cannot recover positive brave witnesses, and removing constraints
cannot remove negative witnesses. These statements include positive examples
with excluded atoms. They do not extend to blocks that change headed clauses.

Constraint-relaxation search has been removed. Incomplete candidates with
negatives only replace headed roots with headed alternatives; dependency-block
deletion may still remove their unsupported constraint consumers. Constraints
can be removed directly, but are not searched for weaker replacements. Complete
candidates retain ordinary constraint replacement without body comparisons.
An incomplete single-constraint candidate has no legal mutation when the space
contains no headed clauses: deletion would violate the nonempty invariant.
This is a remaining search restriction, not evidence of semantic optimality.

Completeness and consistency are properties of the evaluated candidate, not
of its clauses. Consistency can be measured before completeness, but a program
without models can satisfy it vacuously. Identical positive and negative masks
after deletion establish only unchanged behavior on the observed examples,
not ASP equivalence or generalization.

Protecting complete headed programs is a search restriction, not a theorem of
repairability. For a positive requiring `p`, a negative requiring `q`, and
`#maxpl=1`, the candidate `p | q.` is complete but inconsistent. If no useful
constraints exist, it needs replacement by `p.`; this mutation policy leaves
it unchanged. The surrounding search may obtain another candidate through
crossover or population diversity, but convergence is not guaranteed. Headed
rules can also define pruning helpers rather than only generate models.

## Crossover

Crossover retains its earlier policy. In a mixed space with positive examples,
90% of complete-recipient decisions first try constraint-only mixing. The other
10% permit unrestricted mixing. Restricted mixing fixes recipient heads and
cannot insert headed providers. If it yields no change, crossover falls back
to ordinary mixing. This mutation update does not change those probabilities
or impose mutation's stricter protection on crossover.

## Evaluation and cost

Search supplies its existing evaluation cache. Mutation classifies its actual
input, not its parents, whenever positives exist. This includes homogeneous
spaces because completeness now changes the permitted operations there too.
An uncached crossover output can therefore require one extra whole-program
evaluation before mutation. Changed offspring receive normal evaluation. All
cost stays in the requesting phase. Without an evaluator or cached result, the
standalone operator cannot infer completeness and uses unclassified block edits.

Crossover retains its mixed-space classification fast path. Cached solutions
remain protected in either operator. No per-clause semantic evaluations, witness
tracing or fixed clause fitness are introduced.

Candidate alternatives remain lazily sampled. No constraint-body cache,
relaxation comparison or quadratic neighbor table is maintained. Headed-only
replacement returns immediately for constraint-only spaces. No full-space
forbidden mask per removal is stored.

Tests cover transitive deletion, alternative and background providers, signed
dependencies, cycles, joint replacement, pool/size/protection invariants,
positive-only recovery, headed-root replacement, probability boundaries,
actual-child classification and complete-candidate freezing.
No speedup is claimed. End-to-end comparisons need matched seeds, wall-clock
timeouts, no generation cap, success rates and net `total_execution` alongside
grounding, solving, Python and closure time.

## Early constraint-pruning measurement

This historical measurement predates dependency-block mutation and does not
measure its search behavior or classification cost.

An enumeration-only ablation used ten paired runs with alternating execution
order. Both sides used the same task and metaprogram; only the static pruning
decision was forced off or on. This isolates enumeration, not the cost of the
static proof or genetic-search convergence.

The synthetic task has `#maxv(0)`, `#maxbl(4)`, head mode `p`, one positive
requiring `p`, and eight optional background atoms `q0` through `q7`, each with
a body mode of recall one. There are no negative examples. Generation used
`Arguments(clause_generation={"clingo_arguments": []})` and the existing
`build_profiled_clause_space` runner.

| Mean per run | Pruning disabled | Pruning enabled |
| --- | ---: | ---: |
| Enumerated models / final clauses | 17 / 17 | 9 / 9 |
| Headless clauses | 8 | 0 |
| Net clause generation | 44.04 ms | 40.39 ms |
| Grounding | 30.31 ms | 28.65 ms |
| Solving | 1.93 ms | 1.60 ms |

The reproducible structural result is eight fewer enumerated models. The small
timing difference on this synthetic task does not establish a speedup on
5queens, grandparent, or end-to-end search. Existing pruning already limits this
task to seventeen clauses before the new optimization.

Environment: Windows 11 build 26200, Intel Core i7-13700H, Python 3.14.6,
Clingo 5.8.0, dirty worktree based on
`ff57d65e60cce685da8c8a79d47cc162128d5c05`. The local runner and all twenty
observations are retained under `.benchmarks/shared-variation/` as
`measure_constraint_pruning.py` and `constraint_pruning_measurement.json`.
The runner refuses to overwrite existing observations.
