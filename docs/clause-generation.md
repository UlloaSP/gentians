# Clause generation

`generate_clause_space()` and `incremental_clause_batches()` share the pipeline
in `gentians/clauses/generator.py`. Both produce canonical `ClauseSpace` values.
Incremental enumeration changes the visited order and batch boundaries; the
language and pruning rules are shared.

| Responsibility | Location under `gentians/clauses/` |
| --- | --- |
| Candidate clause, ordered space and reified literals | `clause.py`, `clause_space.py`, `reified_clause.py`, `reified_literal.py` |
| Compiled mode representation, including variable positions | `clause_mode.py` |
| Task declarations, predicate types and observed AST evidence | `analysis/task.py`, `analysis/ast_inspection.py` |
| Closed-world relations computed by Clingo per evaluation context | `analysis/ground_relations.py` |
| Property inference from ASP rules and ground relations | `analysis/inference.py`, `analysis/rule_properties.py`, `analysis/relation_properties.py` |
| Mode expansion | `mode_compiler.py` |
| ASP fact assembly | `fact_compiler.py` |
| Mode representation facts | `mode_facts.py` |
| Static predicate-property facts | `property_facts.py` |
| Declarative legality and redundancy checks during enumeration | `metaprogram/` |
| Positive-only constraint proof | `pruning.py` |
| Clingo model decoding | `decoder.py` |
| Clause normalization and representative selection | `canonicalization/clauses.py`, `canonicalization/arithmetic.py` |
| Linear and expression normalization algorithms | `canonicalization/linear_normalization.py`, `canonicalization/expression_normalization.py` |
| Arithmetic systems, expressions and constraint values | The remaining class modules in `canonicalization/` |

The generator obtains static evidence from `analysis/` before passing it to
`fact_compiler.py`. This module assembles the fact program but does not infer
new evidence. `property_facts.py` translates the supplied static properties;
`mode_facts.py` declares each mode's section, kind, recall, predicate signature
and argument roles from its flattened variable bindings. Fixed terms consume no
binding position. Aggregate internal positions derive from the tuple and
condition mappings instead of being emitted a second time.
`metaprogram/representation/` combines those static facts with the selected
bindings. `pruning.py` supplies the conservative
proof that enables optional-constraint pruning in ASP. The metaprogram still
owns checks over selected modes and variable assignments.

The mode compiler prepares condition declarations once per task and shares the
conditioned alternatives across ordinary, choice and disjunctive heads and body
modes. Head and condition combinations are built in the same lexicographic
order as before, stopping branches when a declaration recall or concrete-literal
capacity is exhausted. `ClauseMode` owns its derived arithmetic traits without
an unbounded process-wide traits cache. Other normalization caches remain bounded.
It also prepares head predicates, head dependencies and condition counts once;
decoded clauses reuse these immutable values. Positive and strongly negated
predicates retain their distinct signatures, and default-negated heads remain
dependencies.
Arithmetic and comparison modes retain postorder instruction tuples, so
normalization substitutes bindings without walking the native templates again.
`ArithmeticLiteral` derives its linear coefficients on first use and retains
them, including a non-linear result. Derived metadata does not affect identity. Arithmetic
clause normalization collects external, safe and numeric variables in the same
body traversal that separates builtins from ordinary literals.
Each mode lazily caches a hash of its complete identity; modes from different
tasks with the same local id need not collide in bounded normalization caches.
Mode-fact compilation memoizes native term shapes for that call, including
pooled alternatives and conditional variants, without changing fact order.
It also reuses relative pool-binding alternatives and complete local-comparison
variants, including rejected output combinations. Clingo remains the authority
for comparison safety; those caches retain no controls and end with the
compilation call. Pool binding counts and invertibility are computed bottom-up;
arithmetic subtrees are not expanded as pools. A single index of aggregate
function, conditions and tuple width supplies shorter-mode checks.
Conditional shorter-mode checks share sorted conditions and original-to-sorted
position mappings within the compilation call. Deleting a condition uses that
mapping, preserving repeated conditions and the original fact indexes.
Complete and combinable head templates are consumed as iterators. Combinable
heads deduplicate element tuples before constructing their native bounds, in
the same width, combination and bound order as before.

Predicate argument types and capabilities are diagnostic data. They are computed
on demand, or during generator preparation when Clingo metrics are enabled.
They do not alter the task's modes or legal clause space.
Synthetic type names follow sorted predicate positions, independent of Python's
hash seed. Numeric-term classification also uses an explicit traversal stack.

## Closed-world properties

Property facts let the metaprogram drop clauses that are redundant or
impossible given the background. They are sound only for relations no learned
clause can change, so `analysis/ground_relations.py` works per evaluation
context, the background plus one example context, and Clingo is the authority:

- A predicate is open when a head mode can define it, or when a background rule
  defining it depends on an open predicate. Only closed predicates get facts.
- Clingo computes brave and cautious consequences of the closed statements. A
  closed predicate is fixed when both agree; extension properties such as
  symmetry, implication, mutual exclusion or keys are checked on fixed
  extensions only. A context whose closed part has no stable model covers no
  example and adds no constraint.
- A property is emitted only if it holds in every context separately. Merging
  contexts would invent relations that no example is evaluated against.
- Open predicates keep a lower bound: atoms a normal background rule over closed
  predicates derives in every model. A closed relation inside it implies the
  open one, which prunes `p(X) :- q(X)` when the background already makes every
  `q` a `p`, for plain heads only.
- Unfixed closed predicates, such as choice atoms, keep a brave upper bound.
  Their values can cover a domain or bound a numeric sign, but no extension
  property is read from them.
- Properties suggested by rule syntax, such as keys of a choice rule, are kept
  only when Clingo proves that no stable model violates them.
- Reflexivity, total orders, universal relations, complements and partitions
  hold on a finite domain. `domain_cover` facts name the arguments whose values
  stay inside it; the metaprogram prunes only variables bound there.
- `positive_arg` and `nonnegative_arg` give the sign of every value a closed
  argument takes, for numeric inference over positive body literals.

Property facts address source argument indexes, so they are emitted only for
predicates whose templates use plain variables and constants.

One property-analysis call shares immutable rule dependencies across contexts;
each context propagates open predicates through its own index and worklist.
Ground relations, bounds and proofs remain isolated. Argument-value sets and tuple
projections are reused inside that context only. Transitivity checks use a
successor index shared with cycle detection; reflexivity reuses the positional
domain. After reflexivity, transitivity and antisymmetry are proven, a total
order over a domain of at least two values needs exactly `n*(n+1)/2` tuples.
These indexes do not merge example contexts or change which
properties are emitted.
Within that analysis call, a cache of at most eight exact effective ASP programs
reuses brave and cautious bounds, including unsatisfiable results. Its input
includes the closed statements and lower-bound rules. It retains no Clingo
controls or worlds; open-predicate classification and property proofs still run
per context. Consequence extraction uses Clingo's native atom-symbol collection,
independently of `#show` declarations.
Another local cache, also limited to eight exact programs, shares syntactic
inspection of choice bounds, normal-rule definitions and key propagation
templates. Key propagation uses each context's own proven keys, and Clingo
checks the suggested properties separately in every context.
Each context shares positional value sets between product checks, projection
filtering, domain coverage and numeric signs. Complement and partition domains
are unions of those positions. Empty relations retain their vacuous sign and
implication properties. Projection enumeration rejects mappings whose position
domains cannot fit the target, then checks inclusion of the complete projected
tuples. It streams compatible injective mappings without keeping their history.
Uniform compatible domains use `itertools.permutations` directly because they
cannot reject any prefix.
When a mapping has just one compatible target, inclusion streams the source
rows and stops at the first missing tuple. Multiple targets still share one
materialized projection. Source and target predicates with identical extensions
and arity share that inclusion proof, then receive their individual facts.
Domain coverage likewise shares subset checks for identical argument-value
sets and domain positions while preserving original predicate and argument order.
Partition enumeration keeps the existing sizes three through six and minimality
rule; it abandons non-disjoint prefixes and prefixes whose growing domain
product cannot be completed by the remaining tuple capacity. This bound uses
only the largest remaining counts instead of sorting every candidate count.
Equal-sized relations use the remaining count directly.
Dependency checks group tuples once per determinant and share that scan across
output positions and key detection. A determinant containing a proven key needs
no further tuple scan, but still emits its dependent-position facts before
context intersection. Tuple-mutex checks share projections between predicates
with identical extensions and arity, then emit facts for every original signed
predicate pair. Intrinsic argument, dependency, product and binary-relation
properties also run once per identical extension and arity inside each context,
then retain every original signed predicate. Pair properties, including
implication, inverse, mutual exclusion and disjoint argument domains, share
the same extension groups. Complement permissions still apply to each original
predicate pair. Syntactic proofs remain attached
to their own predicates and programs. Equality and distinctness select the only
possible property from the first row and check the remaining rows once.
Context properties are intersected as each world is processed, and subsumption
runs only after the intersection. Both functional-dependency filters share one
key index at that stage. Composite dependency subsumption compares minimal
determinants separately for each predicate and output position, retaining all
original tuple orders for equal determinants. Identical
violation bodies share one Clingo proof while retaining every associated fact.
Proof rules use a fresh auxiliary predicate absent from the task and proof
bodies, including macros and strongly negated names, so they cannot redefine
the background's predicates or introduce cycles into it.
Cycle checks and static AST inspection use iterative traversals.
Rule-variable substitutions return unchanged AST nodes by identity and rebuild
only paths containing a renamed variable. Optional-constraint head inspection
also uses an explicit stack and still rejects unknown theory heads.

Clingo applies theta reduction with the other redundancy checks before returning
a model. `mode_facts.theta_facts` chooses its encoding: enumerated offsets keep
the program normal, and saturation takes over only when they would be too many
(see `docs/metaprogram/README.md`). As models arrive, `decoder.py` constructs a
`ReifiedClause` and the generator passes it to `ClauseCanonicalizer`. Complete
enumeration retains the preferred representative per canonical key rather than
all decoded clauses. Incremental enumeration uses a fresh canonicalizer per
batch; its model budget still counts models before deduplication and it retains
no cross-batch history. Decoding reads variable positions from
`ClauseMode` rather than importing the mode compiler. `representation/output.lp`
displays only `selected/3` and `var_at/4`. A decoder prepared after grounding
maps their raw symbols to slots and binding positions. One native copy per model
fills a reusable buffer, whose cleared zero suffix marks the end. Decode visits
the prepared deterministic slot order, preserving complete heads and flattened
bindings without per-literal truth probes or public `Symbol` wrappers. The same
decoder is reused across incremental size solves with cleanup disabled.
Arithmetic system reuse is task-local and capped at 8192 contexts, with oldest
entries evicted first. Connected-component partitions share up to 8192 global
entries keyed only by ordered variable masks, preserving the original literal
order. Exact structural expressions share up to 8192 native terms independently
of their algebraic keys; output and safety wrappers stay with each constraint.
These caches retain no control or task. Representatives are yielded directly to `ClauseSpace`,
which alone performs final text sorting and deduplication. Compiled argument
binding offsets are reused by head instantiation and mode-fact compilation.
Head-condition products prune over-budget prefixes in the original product order.
Literal instantiation has a bounded cache keyed by mode and variable bindings;
its key omits the reified slot. Each immutable arithmetic system constructs its
native literal tuple lazily once and retains it for its own lifetime. Native AST
membership uses a set while preserving main-literal and guard insertion order.
Guard ordering is derived once per immutable expression constraint and rebuilt
on remapping. Shared native nodes are templates: transformations use `AST.update`.
An arithmetic system also retains its structural key lazily for its own lifetime;
remapping constructs a new system with independent key and literal caches.

Arithmetic representation modules own keys, variable masks and sets, remapping and
rendering through Clingo's AST. Reified modes and normalized systems construct
native nodes; canonicalization assembles and retains `ast.Rule` directly.
Normalization algorithms own connected components, substitutions,
linear reduction and contradiction detection. Choosing one representative per
canonical key remains part of canonicalization; no separate duplicate policy
reimplements that choice. `ClauseSpace` orders and deduplicates the final clauses.
The linear path retains masks through component collection, auxiliary elimination
and orientation, materializing sets only for expressions or structural fallback.
Static proportional-row pairs permit guarded contradiction pruning in ASP;
Clingo compares bindings, while Python retains authority over coefficient analysis.
Expression assignments index their missing inputs and visit only ready entries.
The queue preserves the former left-to-right scan order, including repeated
outputs and divisor guards; unresolved cycles retain the structural fallback.
Linear orientation indexes missing variables too. It always consumes fully safe
constraints before assignments, choosing the earliest original constraint in
either category. Only unit-coefficient equality outputs can make a new variable
safe; unresolved systems retain their existing fallback.
Auxiliary-variable elimination reuses rows whose elimination factor is zero.
Each immutable expression and linear constraint caches its variable set lazily
for its own lifetime, including an empty set. These caches do not participate
in equality or hashing; remapping creates independently cached values.

Expression traversal, structural equality, key construction, substitutions and
native AST construction use explicit stacks and reuse shared expression nodes
by identity within each operation. Linear assignments use exact
integer coefficients and multiplication for magnitudes above two instead of
repeating a variable once per coefficient unit. Oversized derived coefficients
use arithmetic composed of native integer leaves. The output still follows
Clingo's arithmetic and formatting. The internal `scale` expression preserves
the canonical key of repeated addition; ordinary multiplication keeps its
structural key, so compact formatting does not change representative selection.
Compiled arithmetic-mode instantiation and linear-coefficient collection also
use explicit stacks, preserving left-to-right binding order without Python's
recursion-depth limit.

Solving timers exclude decoding and canonicalization inside callbacks or between
yielded models. Those Python costs stay in `clause_generation`; grounding and
solving remain separately reported with the existing metric fields.
Both complete and incremental enumeration read per-model clocks only when
timings or Clingo metrics are enabled. Clingo metrics alone still measure the
same durations; incremental consumer time never belongs to solving. The dashboard
schema and chart contract are unchanged.

These stages concern individual clauses. Dependency closure and coverage of a
complete candidate hypothesis remain in `hypotheses/` and `evaluation/`.
Measurements and regression checks for prepared mode and relation analysis are
recorded in [clause-python-prepared.md](clause-python-prepared.md).

## ASP metaprogram

`CLAUSE_METAPROGRAM_MODULES` lists every module explicitly. Clingo grounds and
solves them together; directories identify responsibilities, not execution
stages.

| Directory | Responsibility |
| --- | --- |
| `representation/` | Central input schema plus selected modes, bindings and semantic views of literals, operators and aggregates. |
| `inference/` | Numeric consequences of selected relations and supplied domain evidence. |
| `legality/` | Structural limits, recalls, labels, invention, scopes, types and safety. `flow/` separates binding roles, seeds, closure and requirements, and says when a redundant atom is still needed as a binder. |
| `symmetry/` | Ordered representatives of interchangeable encodings. |
| `pruning/contradictions/` | Incompatible relations under stated assumptions. |
| `pruning/redundancy/` | Repeated or entailed combinations. |
| `pruning/properties/` | Checks conditional on statically analyzed predicate properties. |
| `pruning/policies/` | Additional restrictions of the existing enumerator. |
| `pruning/task/` | Task-relative optional-constraint pruning. |

The [metaprogram guide](metaprogram/README.md) defines the shared predicate
contracts, distinguishes variable ids from values, explains each family of
checks and provides executable examples that include the production modules.
It also records the assumptions and limits of the pruning arguments.
