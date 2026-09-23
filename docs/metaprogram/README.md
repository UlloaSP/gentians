# Reading the clause metaprogram

One stable model of this metaprogram encodes **one candidate clause**. It does
not evaluate that clause's coverage. Python compiles the language bias and
static task evidence into facts; Clingo chooses mode occurrences and variable
bindings; Python decodes and canonicalizes the surviving clauses. Candidate
hypotheses are evaluated separately, as complete ASP programs.

The source is in `gentians/clauses/metaprogram/`. Its directories distinguish
what a rule establishes and what a rejection claims:

```text
metaprogram/
  representation/
    schema.lp            declared facts and cross-module predicate contract
    *.lp                 selected syntax and argument views
  inference/            consequences of selected relations and task evidence
  legality/             structural limits, scopes, types and safety
    flow/               declarations, seeds, closure, requirements
  symmetry/             ordering of interchangeable encodings
  pruning/
    contradictions/     impossible combinations under stated assumptions
    redundancy/         repeated or entailed combinations
    properties/         checks conditional on predicate properties
    policies/           additional restrictions of the existing enumerator
    task/               pruning relative to the inductive task
```

`CLAUSE_METAPROGRAM_MODULES` in `generator.py` explicitly lists all files.
They form one grounded program, not a sequence of filters. In particular,
moving a definition to `inference/` does not make it run before another file.
The separation identifies ownership and proof obligations.

`representation/schema.lp` is the single declaration point for optional facts
and relations shared across modules. Its comments define every argument and
state whether absence means an empty optional relation or unproved static
evidence. `#defined` does not create facts or rules; it tells Clingo that an
empty relation is still part of the vocabulary. The remaining modules contain
the rules that derive views from this schema and do not repeat declarations.

## The shared vocabulary

| Relation | Meaning |
| --- | --- |
| `mode_section(Mode,Section)`, `mode_recall(Mode,Recall)` | Declaration placement and effective recall limit. |
| `mode_kind(Mode,Kind)` | Explicit template kind: normal, conditional, comparison, arithmetic, body aggregate or head aggregate element. |
| `comparison_operator(Mode,Operator)` | Simple binary comparison operator: eq, neq, lt, gt, leq or geq. Complex comparison chains have no such fact. |
| `mode_atom(Mode,Predicate,Arity)` | Predicate signature of a normal atom, conditional conclusion or head aggregate element; absent for operators and body aggregates. |
| `mode_arithmetic_operand(Mode,Side,Position)`, `mode_arithmetic_result(Mode,Position)` | Static arithmetic roles mapped to storage positions. |
| `mode_aggregate_tuple_arg(Mode,TuplePosition,Position)` | Static aggregate tuple mapping. |
| `mode_aggregate_condition_arg(Mode,Condition,LocalPosition,Position)` | Static mapping of each condition occurrence. |
| `mode_aggregate_result_arg(Mode,Position)` | Aggregate result storage position. Internal positions derive from tuple and condition mappings. |
| `mode_aggregate_element_tuple_arg(Mode,Element,TuplePosition,Position)`, `mode_aggregate_element_condition_arg(Mode,Element,Condition,Argument,Position)` | Occurrence-preserving mappings for each body aggregate element; elements have separate local scopes. |
| `mode_aggregate_guard_arg(Mode,Position)`, `mode_aggregate_output_arg(Mode,Position)` | Nonproducing guard input and equality output positions. |
| `head_aggregate_element_arg(Mode,Position)`, `head_aggregate_condition_arg(Mode,Condition,Position)` | Local positions and positive condition bindings of a function aggregate head element. |
| `selected(Section,Slot,Mode)` | A mode occurrence in a head or body slot. |
| `var_at(Section,Slot,Position,Variable)` | A syntactic variable id at a flattened placeholder position. |
| `same_term_bindings(S0,L0,S1,L1)` | Equal recursive term shapes and equal variable bindings at corresponding positions. Does not itself compare predicates. |
| `selected_lt(X,Y)`, `selected_leq(X,Y)` | An explicitly selected comparison, oriented left to right. |
| `known_unequal_values(X,Y)` | A selected strict comparison or disequality entails different values. |
| `addition(Slot,X,Y,Z)` | A recognized addition template selected with these bindings; the compiler's specialized-mode eligibility still applies. |
| `positive_value(X)`, `inferred_lt(X,Y)` | Numeric consequences, including transitive order, under the supplied evidence. |
| `numeric_argument_var(X)` | A binding at a position identified as numeric from normal predicate modes; not an added domain-membership literal. |
| `aggregate_tuple_binding(Slot,Position,Variable)` | A tuple position of a selected aggregate. |
| `aggregate_condition_binding(Slot,Condition,Position,Variable)` | A condition occurrence and a position local to that occurrence. |
| `aggregate_result_var(Slot,Variable)` | The aggregate's result binding. |
| `aggregate_output_var(Slot,Variable)`, `aggregate_guard_var(Slot,Variable)` | General output and guard variables; the latter must already be ASP-safe. |
| `count_condition_orderable(Slot)`, `sum_condition_orderable(Slot,Weight)` | Eligibility for ordering a full-local condition; these predicates do not enumerate permutations. |

`Mode`, `Slot`, `Position` and `Variable` are encoding identifiers. In
`var_at(body,0,1,2)`, `2` means the variable rendered as `V2`; it does not mean
the integer value two. Consequently, `X != Y` in a rule over variable ids does
**not** prove that those variables have unequal values in the learned program.
The name `known_unequal_values` makes that stronger premise explicit.

The reified program assigns exactly one mode to each occupied slot and one variable
to each variable-placeholder position. Specialized arithmetic flags identify
complete three-placeholder templates; the arithmetic views therefore have all
three bindings even when a consumer needs only two. Each aggregate element and
condition occurrence has a mapping to storage positions within its mode. The
older tuple/condition/result projections apply to the single-element
equality-output subset used by symmetry and redundancy rules.
These are representation invariants on which the projections rely.

`mode_facts.py` computes static role mappings once per template;
`fact_compiler.py` only assembles them with task and property facts.
`representation/arithmetic.lp` and `representation/aggregates.lp` join these
mappings with `selected` and `var_at`; consumers do not calculate offsets.
Mappings use flattened variable bindings: a fixed term emits no role position,
while a structured term points to the position of its placeholder.
Aggregate internal positions are the union of element tuple and condition mappings, so
they are derived rather than declared again.
`mode_atom` always describes a real predicate signature, including the conclusion
arity of a conditional rather than the width of its complete template. Numeric
argument evidence applies only to normal atoms, never to operator identifiers
or conditional templates. Property checks also use
`aggregate_condition_arg(Slot,Predicate,Position,Variable)`, the existing
predicate-level projection. That projection merges occurrences of the same
predicate; it must not be mistaken for the occurrence-preserving relation.

## Variable flow and ASP safety

The four files in `legality/flow/` describe a positive fixed point:

1. `declarations.lp` identifies directed modes and counts required input positions.
2. `seeds.lp` supplies head inputs, aggregate results and undirected positive
   `any` bindings.
3. `closure.lp` makes a literal ready when its inputs are bound, propagates its
   positive outputs, and repeats through recursion until no new facts follow.
4. `requirements.lp` rejects inputs or head outputs that remain unsupported.

These are explanatory steps, not imperative execution passes. In the code,
`flow_produced(V)` implies `flow_bound(V)`. A positive `any` position can bind
a variable without satisfying an explicit output requirement. Head inputs
also satisfy an output position identified with that input. Default negation
and conditional conclusions do not produce global variables.

`asp_safe(V)` is a separate condition. A head input can seed directed flow but
does not by itself ground the variable in ASP. Positive body atoms, supported
arithmetic results and Clingo-proved relation outputs supply grounding safety.
Local conditional and aggregate variables have their own scope checks.

## What each rejection means

The table gives the interpretation and representative cases. Cases denote
fragments; an otherwise legal surrounding clause is assumed. An accepted
nearby fragment can still be rejected by another independent restriction.

| Source family | Premise and reason | Rejected / nearby retained case |
| --- | --- | --- |
| `legality/{clause_shape,recall,labels,invention}.lp` | Enforce declared limits, identities and invention rules. | Recall 1 with two occurrences / one occurrence. |
| `legality/{typing,scopes,asp_safety,aggregates}.lp` | Preserve nominal types and grounding in the appropriate scope. | Global head variable with no grounding support / supported by a positive body atom. |
| `legality/flow/` | Every required input has a derivation from flow seeds. | Unseeded input cycle / a chain beginning at a head input or zero-input producer. |
| `legality/linkedness.lp` | Enforce the enumerator's structural connectedness condition. This is a bias condition, not general ASP syntax. | Disconnected variable-bearing components / components sharing an eligible global binding. |
| `symmetry/{slots,variables,conditions}.lp` | Select an ordered encoding among permutations of slots, ids or same-variant conditions. | Descending interchangeable tuple / ascending tuple. |
| `symmetry/{arithmetic,comparisons}.lp` | Order eligible interchangeable operands. Arithmetic eligibility comes from the compiler. | Reversed addition operands / ordered operands; directed non-interchangeable templates retain their own encoding. |
| `symmetry/aggregates.lp` | Order count tuples; permute full-local conditions only, keeping sum weights fixed. | The swapped condition in `examples/aggregate.lp` / its ordered form. |
| `pruning/contradictions/comparisons.lp` | Selected strict order cannot be reflexive or opposed by its reverse. | `X<Y, Y<=X` / `X<Y`. |
| `pruning/contradictions/numeric.lp` | Arithmetic and numeric-domain evidence imply an incompatible order. | `X+Y=Z, Z<X` with positive `Y` / the addition without that comparison. |
| `pruning/redundancy/{literals,conditions}.lp` | Reject identical bindings of repeated literals or condition variants. | Repeated `p(X)` / one occurrence. |
| `pruning/redundancy/comparisons.lp` | A comparison is entailed by others, or a declared strict comparison can replace a non-strict comparison plus disequality. | `X<Y, X!=Y` / `X<Y`. |
| `pruning/redundancy/numeric.lp` | Positive addition already entails an operand/result comparison. | `X+Y=Z, X<Z` with positive `Y` / the addition alone. |
| `pruning/redundancy/arithmetic.lp` | Exclude repeated computations with different result ids and the existing removable common-factor form. These require variable-identification/replacement reasoning, not a claim that different ids have different values. | Two identical inputs assigned to different result ids / one computation whose result is reused. |
| `pruning/redundancy/aggregates.lp` | Compare duplicate inputs; remove a key-determined tuple discriminator only when a shorter declared template exists. | Extra discriminator determined by retained key positions / retain it when no shorter template is available. |
| `pruning/policies/` | Preserve restrictions on singletons, aggregate bindings/result usage and comparisons that force identification. They are not universal ASP validity rules. | `X<=Y, Y<=X` with distinct ids is excluded by policy, although it can hold when their values are equal. |
| `pruning/task/optional_constraints.lp` | Python proves that a perfect hypothesis needs a learned head in the applicable positive-only task. | Optional headless clause / retain headless choices when the proof does not apply. |

Property-specific checks live together under `pruning/properties/` because
their assumptions belong to static predicate analysis. Their filenames name
the premise, not an unconditional theorem about every task:

| Files | Property used and kind of check |
| --- | --- |
| `empty`, `universal`, `reflexive`, `irreflexive` | Known extension or diagonal membership; remove impossible or already satisfied literals. |
| `arg_equal`, `arg_distinct` | Relations between values at argument positions; enforce compatible variable bindings. |
| `functional`, `functional_set`, `key` | Determinants identify output values. Positive-pair rules restrict variable encodings; negative redundancy additionally requires `known_unequal_values`. |
| `symmetric`, `antisymmetric`, `asymmetric`, `inverse` | Reverse-tuple relationships; remove redundant orientations or incompatible pairs. |
| `acyclic`, `transitive`, `strict_order`, `total_order` | Path/order structure; reject cycles or entailed combinations under those properties. |
| `implies`, `project_implies`, `subsumption`, `equivalent` | Inclusion between relations, sometimes after projection; eliminate dominated combinations while retaining required joins. |
| `disjoint`, `complement`, `mutex`, `partition` | Exclusion or exhaustive alternatives; prune incompatible or redundant combinations. Strong-negation coherence also supplies mutex facts. |
| `cardinality_upper` | A predicate cardinality cap; reject excess positive tuples only when their values are provably pairwise distinct. |

An observed property is useful only under the assumptions that justify treating
the analyzed relation as closed. These checks must not be described as global
equivalence based on example coverage. Likewise, a replacement argument must
preserve representability under types, labels, recalls and declared templates.
The directory taxonomy does not itself prove these obligations.

Two preserved implementation assumptions need particular care in a paper's
soundness argument. Aggregate argument-property checks use the predicate-level
projection, so repeated occurrences of the same predicate can contribute
bindings to the same check. Nonnegative-addition pruning tests domain membership
for one operand and the result without always testing the other operand. Its
justification needs the broader numeric-domain assumption; those local guards
alone do not prove the sign of the omitted operand. This refactor preserves
these policies and does not establish their soundness for every admitted task.

## Executable examples

Run from the repository root:

```powershell
uv run python -m clingo docs/metaprogram/examples/flow.lp 0
uv run python -m clingo docs/metaprogram/examples/flow.lp 0 -c source=2
uv run python -m clingo docs/metaprogram/examples/arithmetic.lp 0
uv run python -m clingo docs/metaprogram/examples/arithmetic.lp 0 -c reverse=1
uv run python -m clingo docs/metaprogram/examples/aggregate.lp 0
uv run python -m clingo docs/metaprogram/examples/aggregate.lp 0 -c swap=1
```

Each first command has a model; its modified counterpart is unsatisfiable.
The fixtures include the production modules directly. They pin one reified
selection to explain a particular family, rather than run every independent
pruning check or simulate complete hypothesis evaluation.

The flow example corresponds to these mode declarations:

```prolog
#modeh(1,target(var(node,input),var(node,output))).
#modeb(1,edge(var(node,input),var(node,output))).
```

For the pinned clause `target(V0,V1) :- edge(V0,V1).`, head input `V0` seeds
flow, making `edge` ready; its output produces `V1`, satisfying the head output.
Changing the body input to `V2` leaves that input unbound. The shown facts expose
the derivation. `tests/test_metaprogram_examples.py` checks both outcomes and
the aggregate role and numeric inference facts.

## Evidence and limits

### Readability restructuring

The readability refactor was checked against the immediately preceding working
tree: 160 exhaustive generation calls across 148 existing tests retained exact
clause text, AST, head signatures, dependencies and body sizes. This establishes
regression evidence for those tasks, not a proof of every pruning rule or
preservation of incremental enumeration prefixes.

The full metaprogram was also compared on `grandparent`, `4queens` and
`subset_sum`, with three alternating before/after runs per dataset using
`build_profiled_clause_space` from `benchmarks/profile_clauses.py`, default
catalog arguments, exhaustive enumeration and no sampling seed. Python 3.14.6,
Clingo 5.8.0, Windows 11, Intel Core i7-13700H; both variants used the same process
and task. Both working trees were based on commit
`3127f34a8a3c7766d82accb2c8efbf68c0f5c347` with the preceding clause-package
refactor uncommitted. These are a grounding-cost check, not a performance
improvement claim or a published comparison between clean revisions.

The SHA-256 fingerprints of the ordered, newline-joined `str(AST)` metaprograms
are `0d50c1326a7f4ab1c9c1d12480db59a75f385165582c3a3e503e9b232b8b12ab`
(before) and `005ee81e2bb729637fcc83550ce7606718c0afb4eeb917cf4d3c3d341fc7a6f1`
(after). This identifies the measured encodings despite the uncommitted base.

| Dataset | Clauses / raw models, both variants | Ground atoms before → after | Ground rules before → after | Median grounding ms before → after |
| --- | --- | --- | --- | --- |
| `grandparent` | 326 / 341 | 1060 → 1060 | 5367 → 5337 | 22.40 → 21.49 |
| `4queens` | 313 / 388 | 1903 → 2128 | 10698 → 10830 | 25.67 → 25.11 |
| `subset_sum` | 5 / 5 | 1125 → 1165 | 3661 → 3676 | 22.96 → 19.79 |

Semantic views introduce auxiliary atoms. These small runs do not establish
scaling behavior. To measure another revision, run
`uv run python benchmarks/profile_clauses.py --datasets grandparent 4queens subset_sum`
with identical arguments on both revisions and compare grounding, solving,
atoms, rules and clause signatures separately. Record the revisions and
environment; do not infer a speedup from these millisecond differences.

### Removal of implied constraints

The subsequent cleanup removes five constraints while retaining their rejection
conditions through general rules:

- Two domain-positive addition constraints are instances of the rules using
  `positive_value` on the opposite operand: numeric-domain positivity and a
  numeric argument binding already derive that premise.
- Two strict reversals of positive-addition order create a cycle in
  `inferred_lt` and are rejected by its irreflexivity constraint.
- A pair of opposite selected strict comparisons creates the same cycle.

These implications concern the assembled metaprogram. In particular,
`pruning/contradictions/comparisons.lp` relies on the closure and cycle constraint
in `inference/numeric.lp` and `pruning/contradictions/numeric.lp`.
`tests/test_metaprogram_pruning.py` exercises the five excluded patterns and
nearby consistent alternatives against those production modules. The two
conditional-local-variable definitions are also one rule parameterized by
section; generated conditional sections remain `head` and `body`.

The same 160 exhaustive calls retain their exact clause signatures. A separate
five-run comparison used the same three datasets, environment and catalog
arguments as above, alternating which encoding ran first on successive runs.
The following values are medians; clauses, raw models and ground atoms are
unchanged from the preceding refactor.

| Dataset | Ground rules before → after | Grounding ms before → after | Solving ms before → after |
| --- | --- | --- | --- |
| `grandparent` | 5337 → 5337 | 23.95 → 23.04 | 24.34 → 23.50 |
| `4queens` | 10920 → 10734 | 29.13 → 29.87 | 32.07 → 30.31 |
| `subset_sum` | 3676 → 3676 | 22.53 → 33.80 | 6.67 → 6.46 |

The before fingerprint is the preceding refactor's after fingerprint. The new
ordered AST fingerprint is
`8c49582a631ff0689af7e5da65f1c8153435d3fe44d408f3bd2d2b8ce95837d7`.
The ground-rule reduction is observable for `4queens`; the timing changes are
mixed, including slower grounding for `subset_sum`. This supports a readability
cleanup with preserved tested behavior, not a general speedup claim.
