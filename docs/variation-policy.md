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
| Incomplete, with positives and negatives | Add or edit headed clauses; remove headed blocks or constraints; replace a constraint with another constraint. |
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

Incomplete candidates with negatives replace roots within their role: headed
with headed, or constraint with constraint. The head-signature jump does not
override this restriction. They do not append pure constraints or replace a
headed root with one. Removing a headed rule is also allowed: under
nonmonotonic semantics it can recover positive witnesses.

## Constraint edits and semantic limits

`mutation.constraint_only_random` is a boolean, true by default in `Arguments`. When
enabled and the active pool contains no headed clauses, mutation uses unrestricted
append, remove and replace preferences without intermediate classification or a
head-permission draw. Cached perfect candidates remain protected. An incomplete
candidate may then acquire another constraint. This cannot recover missing brave
positive witnesses, but can eliminate negative witnesses and improve fitness.
The directed prohibition is a search preference, not a proof that every such
offspring is useless. The option retains the no-negative-example policy and all
dependency, pool, nonempty and size invariants.

Pools containing headed clauses keep their existing policy and RNG draws. The
active pool is inspected on each call, including after renewal; no dataset name
is inspected. This option takes precedence over completeness guidance only in
constraint-only pools. It changes search reachability and sampling, not the task
language or the evaluator's stable-model semantics. No speedup on arbitrary tasks
or unseen seeds is guaranteed. Measurements and rejected alternatives are in
[the mutation ablation report](mutation-ablation-experiment.md).

With the headed program fixed, adding integrity constraints can only remove
stable models. Removing constraints preserves existing models. Therefore adding
constraints cannot recover positive brave witnesses, and removing constraints
cannot remove negative witnesses. These statements include positive examples
with excluded atoms. They do not extend to blocks that change headed clauses.

Constraint-relaxation search has been removed. Both incomplete and complete
candidates can replace a constraint without comparing body similarity or
semantic strength. All constraints share the empty head signature, so this
replacement does not need a head-signature jump. Evaluation of the resulting
whole program determines whether it recovers positives or improves fitness.
An incomplete single-constraint candidate can replace its constraint when a
legal alternative exists, even though deletion would violate the nonempty
invariant. Dependency-block deletion may still remove unsupported consumers.

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

### Exact constraint-coverage inheritance

`evaluation.constraint_inheritance` is enabled by default in `Arguments` for the normal
coverage solver. It does not change mutation, crossover, scoring, RNG draws or
population admission. The evaluator compares actual whole programs after
dependency closure, not operator labels or intended root edits.

Evidence is reusable only when all non-constraint statements match exactly.
With that fixed program, a superset of integrity constraints preserves previously
uncovered examples. A subset preserves previously covered examples. These facts
apply to both positive and negative examples, including exclusions and isolated
contexts. Arbitrary constraint replacement supplies no such guarantee unless
another stored whole program has a comparable constraint set.

Each example is known covered, known uncovered, or unresolved. Only unresolved
examples are compiled and solved; compact result indices are mapped back to the
original task. If all examples are known, no control is created. Otherwise the
normal solver creates a fresh control for the unresolved query. This does not
use a persistent ground program, per-rule fitness, or stable-model witnesses.

The solver retains at most 64 whole-program coverage records and 32 compiled
query subsets. A process-local LRU retains at most 4096 exact AST rendering keys.
Another bounded LRU retains at most 4096 compiled example fragments keyed by the
example, its local index, polarity helper and context guard. The search supplies
the prepared `ClauseSpace`; the evaluator disables inheritance when it contains
no constraints because distinct genomes cannot supply comparable constraint edits.
No Clingo controls or models are retained. The bounds limit entry counts, not
bytes independently of clause length or task size. Missing or evicted evidence
causes ordinary evaluation, never an approximation.

Inheritance requires exhaustive brave enumeration. An interrupted or limited
solve raises an error rather than turning incomplete coverage into absence
evidence. The epoch-pool factory rejects this option. A timeout remains a runner
failure, not a fitness observation.

The search's fitness-evaluation counter still counts candidates whose exact
result was requested. Clingo ground/solve calls count actual solver work. Query
records describe the unresolved examples actually compiled; final quality
records describe merged coverage over the full task.

See [the controlled experiment](semantic-inheritance-experiment.md) for measured
costs and limitations. The optimization does not establish that complete headed
programs are repairable using constraints, or that equal observed coverage means
global ASP equivalence.

### Replacement candidates

Replacement samples the active clause space subject to head-signature, root-type
and mutable-mask restrictions. `MutationProposal.local` records head-signature
restriction. Body-local replacement and its neighborhood index were removed.

### Experimental exploration controls

`mutation.completeness_guidance` is a boolean, enabled by default. Setting it
to false disables mutation's intermediate classification and state-dependent
restrictions for controlled ablation. It does not change crossover, scoring,
dependency closure, size limits, or the policy against adding constraints when
there are no negative examples. An unclassified perfect crossover output can
then be mutated before ordinary evaluation, just as in the historical operator.
This option is not a semantic optimization. The `mutation-ablation/` matrix
crosses it with head-jump probabilities 0.1 and 1.0, with ordinary replacement. Head-jump probability 1.0 still consumes the
existing random draw, so the ablation changes filtering without removing that
draw from the random stream.

Search supplies its existing evaluation cache. With completeness guidance enabled,
mutation classifies its actual input, not its parents, including constraint-only
pools when `constraint_only_random=false`. The default `constraint_only_random` policy skips
intermediate classification in those pools while protecting cached perfect
candidates. An unclassified perfect crossover output can then be mutated before
discovery. Changed offspring receive normal whole-program evaluation. All cost
stays in the requesting phase. Without an evaluator or cached result, the
standalone operator cannot infer completeness and uses unclassified block edits.
Delayed classification only on append was measured and rejected; it is not part
of the current default implementation.

Crossover retains its mixed-space classification fast path. Cached solutions
remain protected in either operator. No per-clause semantic evaluations, witness
tracing or fixed clause fitness are introduced.

Candidate alternatives remain lazily sampled. No constraint-body cache,
relaxation comparison or quadratic neighbor table is maintained. Replacement
skips roots with no absent alternative of the permitted kind. No full-space
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
observations are retained under `.benchmarks/experiments/shared-variation/` as
`measure_constraint_pruning.py` and `constraint_pruning_measurement.json`.
The runner refuses to overwrite existing observations.

## Retired experimental policies

Duplicate retries, complete-candidate reserves, constraint diagnosis and diagnosed
repair were removed on 2026-09-08 after their measured regressions. Historical
protocols and results remain in [directed exploration](directed-exploration-experiment.md)
and [semantic repair](semantic-repair-experiment.md). Their configuration keys
and experiment entries are no longer available.

Mutation instrumentation still records positive examples recovered or lost and
negative examples removed or introduced when both whole-program results are
cached. `semantic_effect_known=false` means the pair was unavailable; it does
not mean a measured zero effect. Logging adds no candidate evaluations.
