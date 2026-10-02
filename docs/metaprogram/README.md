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
    flow/               declarations, seeds, closure, requirements, removal
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

Every rule, choice and constraint in those modules has a comment directly
above it, following the conventions stated at the top of `schema.lp`. A
`DEFINITION` says whether the view is reusable (and which modules consume it)
or a local helper, and lists each head argument. A `CHOICE` shows the
alternatives it opens. A `CONSTRAINT` gives `pruned` and `kept` example
clauses; `kept` means that constraint does not reject the clause, not that the
whole metaprogram accepts it.

## The shared vocabulary

| Relation | Meaning |
| --- | --- |
| `mode_section(Mode,Section)`, `mode_recall(Mode,Recall)` | Declaration placement and effective recall limit. |
| `mode_kind(Mode,Kind)` | Explicit template kind: normal, conditional, comparison, arithmetic, Boolean literal, body aggregate, or head aggregate element. |
| `interchangeable_operands(Mode)`, `interchangeable_condition_args(Mode,Condition,First,Second)`, `interchangeable_tuple_args(Mode,First,Second)` | The two operands of an arithmetic or simple comparison template, the two arguments of a binary atom of plain variables, two arguments of one aggregate condition, or two tuple positions of an aggregate have equal type, direction and label. Every rule that picks one orientation requires it. |
| `comparison_operator(Mode,Operator)` | Simple binary comparison operator: eq, neq, lt, gt, leq or geq. Complex comparison chains have no such fact. |
| `mode_atom(Mode,Predicate,Arity)` | Predicate signature of a normal atom, atomic conditional conclusion or atomic head aggregate element; absent for operators, body aggregates and non-atomic conclusions. |
| `pooled_body_mode(Mode)`, `mode_pool_alternative(Mode,Alternative)`, `mode_pool_alternative_arg(Mode,Alternative,Position)` | Alternatives of one pooled body atom and the flattened placeholders present in each alternative. A variable is supplied by the atom only when it occurs in every alternative. |
| `local_pool_condition_arg(Mode,Scope,Element,Condition,Position)`, `local_pool_alternative(Mode,Scope,Element,Condition,Alternative)`, `local_pool_alternative_arg(Mode,Scope,Element,Condition,Alternative,Position)` | Alternatives of a positive local condition. A conditional or aggregate variable is supplied only when every alternative contains it. |
| `mode_arithmetic_operand(Mode,Side,Position)`, `mode_arithmetic_result(Mode,Position)` | Static arithmetic roles mapped to storage positions. |
| `mode_aggregate_tuple_arg(Mode,TuplePosition,Position)` | Static aggregate tuple mapping. |
| `mode_aggregate_condition_arg(Mode,Condition,LocalPosition,Position)` | Static mapping of each condition occurrence. |
| `mode_aggregate_result_arg(Mode,Position)` | Aggregate result storage position. Internal positions derive from tuple and condition mappings. |
| `mode_aggregate_element_tuple_arg(Mode,Element,TuplePosition,Position)`, `mode_aggregate_element_condition_arg(Mode,Element,Condition,Argument,Position)` | Occurrence-preserving mappings for body function and set aggregate elements; elements have separate local scopes. |
| `aggregate_element_atom(Mode,Element,Predicate,Arity)`, `mode_aggregate_element_positive_arg(Mode,Element,Condition,Position)` | A body set element's conclusion predicate and bindings supplied by positive atomic conditions. |
| `mode_aggregate_guard_arg(Mode,Position)`, `mode_aggregate_output_arg(Mode,Position)` | Nonproducing guard input and equality output positions. |
| `head_aggregate_element_arg(Mode,Position)`, `head_aggregate_condition_arg(Mode,Condition,Position)`, `head_aggregate_positive_condition_arg(Mode,Condition,Position)` | Local positions, all condition bindings, and the positive atomic subset of a function aggregate head element. |
| `local_comparison_variant/6`, `local_comparison_input/6`, `local_comparison_output/6` | Grounding-safe variable bindings proved by Clingo for a comparison inside a conditional or aggregate element; required inputs must be safe in that same scope. |
| `head_guard_arg(Mode,Position)` | Clause-global guard or cardinality bound position on the first member of a complete head. |
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

`representation/tuples.lp` projects the unique selected mode to
`selected_shape(Section,Slot,Shape)` before comparing argument bindings.
Several modes may have one shape; the comparison needs that shape and the
bindings, so it need not repeat the Cartesian product of mode ids.
Every `var_at` already belongs to a placeholder of that selected mode.
The equal-shape requirement, complete binding comparison and exclusion of
slot self-comparisons remain unchanged.

`property_facts.py` assigns one `tuple_mutex_arg` mapping id to each complete
argument permutation. Predicate pairs with the same permutation share its
description, while every original signed pair retains its own
`tuple_mutex_pred(Left,Right,Mapping)` fact. In
`pruning/properties/disjoint.lp`, `tuple_mutex_pair(Slot0,Slot1,Mapping)`
checks membership of the selected predicates before comparing bindings.
Sharing a mapping for `p/q` and `r/s` therefore never relates `p/s`.
The helper is a deterministic projection, not another choice or pruning rule;
it retains the original equal-arity and different-slot conditions. The
mismatch check still requires the target argument position to exist.
These changes affect the encoding used by both exhaustive and incremental
generation, without changing the task language or its pruning conditions.

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
`aggregate_condition_arg(Slot,Condition,Predicate,Position,Variable)`, which
tags each binding of a condition occurrence with its predicate. `Position` is
the source argument of that predicate, so it lines up with property facts, and
two occurrences of one predicate keep separate `Condition` ids.

## Variable flow and ASP safety

The four files in `legality/flow/` describe a positive fixed point:

1. `declarations.lp` identifies directed modes and counts required input positions.
2. `seeds.lp` supplies head inputs, aggregate results and the `any` bindings
   of undirected positive normal atoms.
3. `closure.lp` makes a literal ready when its inputs are bound, propagates the
   outputs and `any` bindings of positive normal atoms, and repeats through
   recursion until no new facts follow.
4. `requirements.lp` rejects inputs or head outputs that remain unsupported.

`removal.lp` is not part of that fixed point. It defines `flow_needed(Slot)`:
removing the positive body atom at `Slot` may leave a variable without the
producer or binder it needs. Every pruning that rejects a clause for holding a
redundant positive atom (`implies`, `universal`, `reflexive`,
`project_implies`, `transitive`, `inverse`, `subsumption`) requires the atom
not to be needed, because the argument "the shorter clause is enumerated
anyway" fails when directed flow makes that shorter clause illegal. With
`node(output)` and `red(input)`, where `red` implies `node`,
`h(X) :- node(X), red(X)` stays: `h(X) :- red(X)` has no binder for the input.
The test is sufficient, not exact. It accepts a removal only when another atom
without inputs supplies each variable at least as strongly, so in doubt the
redundant clause is kept.

These are explanatory steps, not imperative execution passes. In the code,
`flow_produced(V)` implies `flow_bound(V)`. A positive `any` position of a
normal atom can bind a variable without satisfying an explicit output
requirement. A head input is bound, not produced: it satisfies only an output
position of the same head, never a body output requirement. Default negation,
comparisons, aggregates and conditional conclusions do not bind global
variables through `any`.

`asp_safe(V)` is a separate condition. A head input can seed directed flow but
does not by itself ground the variable in ASP. Positive body atoms, supported
arithmetic results and Clingo-proved relation outputs supply grounding safety;
a relation output is safe only when its other arguments are already safe. A
placeholder inside non-invertible arithmetic, such as `q(X+Y)` or `q(|X|)`,
does not ground its variable, matching Clingo.
Local conditional and aggregate variables have their own scope checks.

## What each rejection means

The table gives the interpretation and representative cases. Cases denote
fragments; an otherwise legal surrounding clause is assumed. An accepted
nearby fragment can still be rejected by another independent restriction.

| Source family | Premise and reason | Rejected / nearby retained case |
| --- | --- | --- |
| `legality/{clause_shape,recall,labels}.lp` | Enforce declared limits and identities. | Recall 1 with two occurrences / one occurrence. |
| `legality/linkedness.lp` | Keep literals with global variables in one connected component; local scopes do not bridge components. This is a search policy beyond Clingo safety. | `q(X) :- d(X),r(Y)` / `q(X) :- d(X),r(X)`. |
| `legality/invention.lp` | Keep invented definitions ordered by declaration and exclude invented dependencies in constraints. This is a search policy beyond Clingo syntax. | `early(X) :- late(X)` when `late` is declared later / `late(X) :- early(X)`. |
| `legality/{typing,scopes,asp_safety,aggregates}.lp` | Preserve nominal types and grounding in the appropriate scope. | Global head variable with no grounding support / supported by a positive body atom. |
| `legality/flow/` | Every required input has a derivation from flow seeds. | Unseeded input cycle / a chain beginning at a head input or zero-input producer. |
| `symmetry/{slots,variables,conditions}.lp` | Select an ordered encoding among permutations of slots, ids or same-variant conditions. | Descending interchangeable tuple / ascending tuple. |
| `symmetry/{arithmetic,comparisons}.lp` | Order eligible interchangeable operands. Arithmetic eligibility comes from the compiler. | Reversed addition operands / ordered operands; directed non-interchangeable templates retain their own encoding. |
| `symmetry/aggregates.lp` | Order count tuples; permute full-local conditions only, keeping sum weights fixed. | The swapped condition in `examples/aggregate.lp` / its ordered form. |
| `pruning/contradictions/comparisons.lp` | Selected strict order cannot be reflexive or opposed by its reverse. | `X<Y, Y<=X` / `X<Y`. |
| `pruning/contradictions/numeric.lp` | Arithmetic and numeric-domain evidence imply an incompatible order. | `X+Y=Z, Z<X` with positive `Y` / the addition without that comparison. |
| `pruning/redundancy/{literals,conditions}.lp` | Reject identical bindings of repeated literals or condition variants. | Repeated `p(X)` / one occurrence. |
| `pruning/redundancy/theta.lp` | Reject a clause when a substitution maps all its literals to a subclause without one repeated normal body atom. Other literals map to themselves and fix their variables. | `:- r(A,B),r(A,C),s(A,D),B!=D` / `:- r(A,B),r(A,C),B!=C`. |
| `pruning/redundancy/comparisons.lp` | A comparison is entailed by others, or a declared strict comparison can replace a non-strict comparison plus disequality. | `X<Y, X!=Y` / `X<Y`. |
| `pruning/redundancy/numeric.lp` | Positive addition already entails an operand/result comparison. | `X+Y=Z, X<Z` with positive `Y` / the addition alone. |
| `pruning/redundancy/arithmetic.lp` | Exclude repeated computations with different result ids and the existing removable common-factor form. These require variable-identification/replacement reasoning, not a claim that different ids have different values. | Two identical inputs assigned to different result ids / one computation whose result is reused. |
| `pruning/redundancy/aggregates.lp` | Compare duplicate inputs; remove a key-determined tuple discriminator only when a shorter declared template exists. | Extra discriminator determined by retained key positions / retain it when no shorter template is available. |
| `pruning/policies/` | Preserve restrictions on singletons, aggregate bindings/result usage and comparisons that force identification. They are not universal ASP validity rules. | `X<=Y, Y<=X` with distinct ids is excluded by policy, although it can hold when their values are equal. |
| `pruning/task/optional_constraints.lp` | Python proves that a perfect hypothesis needs a learned head in the applicable positive-only task. | Optional headless clause / retain headless choices when the proof does not apply. |

Theta reduction checks homomorphisms that move repeated normal body atoms onto
atoms of the same mode; every other literal, including the whole head, maps to
itself and fixes its variables. Dropping a head literal is never considered: a
shorter head can leave the language, as under `#minhl`. Because equal modes are
contiguous, a moved atom can only land on `Start + Offset` inside its mode
group. Python enumerates every offset combination as facts, so "some
combination is a consistent substitution" is stratified negation: the program
stays normal. Only when those combinations exceed `THETA_OFFSET_LIMIT` does
Python select the disjunctive saturation encoding instead; both are exact and
prune the same clauses. `mode_recall` keeps the check out of the grounding
when no body mode can repeat. It does not infer global equivalence from
example coverage.

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

One preserved implementation assumption needs particular care in a paper's
soundness argument. Nonnegative-addition pruning tests domain membership
for one operand and the result without always testing the other operand. Its
justification needs the broader numeric-domain assumption; those local guards
alone do not prove the sign of the omitted operand. This refactor preserves
this policy and does not establish its soundness for every admitted task.

Two checks depend on argument positions and slot order in ways that are easy to
get wrong. `subsumption` drops a positive atom only when a substitution maps it
onto a stricter atom of the same predicate and term shape while moving only
variables that occur nowhere else: a variable the rest of the clause uses must
sit at the same argument in both atoms, so `:- p(X,X,Y), p(Y,X,Z)` stays.
Between atoms of one repeatable mode theta reduction already finds these
substitutions; `subsumption` adds the pairs selected through different modes.
`transitive` rejects the shortcut `p(X,Z)` of a positive path `p(X,Y), p(Y,Z)`
in whatever slot it sits, because tuple order places it between the two path
atoms; it only requires the shortcut to be a third atom.

More checks replace a literal by an equivalent spelling and therefore depend
on that spelling being in the language. `symmetric` keeps one argument order
only for templates whose two arguments have equal type, direction and label
(`interchangeable_operands` for atoms, `interchangeable_condition_args` for
aggregate conditions): with `friend(input,output)` the swapped atom can be
illegal by flow, so both orders stay. `symmetry/aggregates.lp` orders the tuple
and the condition arguments of a count or sum under the same requirement
(`interchangeable_tuple_args`, `interchangeable_condition_args`), and
`symmetry/conditions.lp` orders only conditions whose variant includes equal
types, directions and labels. `arg_equal` asks for one variable id at two
equal-valued positions only when the template lets them share a variable;
positions with different types or different labels keep two ids.

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

For the pinned clause `target(V0,V1) :- edge(V0,V1).`, head input `V0` is
bound, making `edge` ready; its output produces `V1`, satisfying the head output.
Changing the body input to `V2` leaves that input unbound. The shown facts expose
the derivation. `tests/test_metaprogram_examples.py` checks both outcomes and
the aggregate role and numeric inference facts.

## Evidence and limits

### Factored shapes and tuple-mutex mappings

The 2026-10-02 pass preserves the task files, mode choices, legality and pruning
conditions. It changes only deterministic representation views and the ids of
identical complete tuple-mutex argument mappings. On `alzheimer_acetyl`, the
846 predicate-pair mappings require just 6 distinct permutations.

| Encoding | Internal solver variables | Internal constraints | Ground rules |
| --- | ---: | ---: | ---: |
| Original pair joins | 462,589 | 3,627,187 | 1,251,053 |
| Project selected shapes | 240,694 | 2,313,027 | 1,029,314 |
| Also share mappings and project tuple-mutex pairs | 28,930 | 900,747 | 826,154 |

Internal constraints are the sum of Clingo's generic, binary and ternary
counts, not its weighted `problem.generator.complexity` estimate. These
variables are solver representation variables, not the task's `#maxv`.

The control freezes the preceding ASP files and property compiler. Each variant
uses fresh Controls, the same task and static properties, `5,split`, `stats=2`,
the production decoder and canonicalizer, and a cold literal-instantiation
cache. Enumeration is exhaustive, with the order reversed on the second
paired run. The measured generation interval includes loading, grounding,
decoder preparation, solving, callbacks and final storage; common task parsing,
static analysis and fact preparation are outside it. The local prototype's
fact-id AST rewrite is measured separately. Production shares mappings while
compiling facts directly and adds no parse.

Python 3.14.6, Clingo 5.8.2, Windows 11, Intel Core i7-13700H; two ABBA samples
per paired variant gave these medians:

| Encoding | Generation wall seconds | Process CPU seconds |
| --- | ---: | ---: |
| Project selected shapes | 157.13 | 556.76 |
| Also share mappings and project tuple-mutex pairs | 124.75 | 269.01 |

A subsequent direct production verification took 47.40 s with the same output
and representation counts. This is one sample under different machine load,
not evidence of another speedup relative to the paired result.

All completed variants emit 289,326 models and clauses with the same ordered
SHA-256 fingerprint, including text, signed heads, dependencies and body size:
`44f8cb5181ee57dc45c6aec1947d03aea0dd50321825321489fa6f79d7461836`.
Generation, pruning, syntax-matrix and incremental tests cover nearby accepted
and rejected cases, including mappings shared by unrelated predicate pairs.
An additional incremental case compares the complete clause metadata after
exhausting batches. The production run passed all 853 tests in these four
groups, plus Ruff on the touched Python files and `ty check`.
This is measured equivalence on this task and construct
coverage, not a proof for every possible inductive task.

Exhaustive control/production comparisons also retain the same ordered text and
metadata on `grandparent` (326 clauses), `8queens` (4,797) and
`subset_sum_double_unbalanced_count` (21,005). Shape projection does not shrink
every solver: internal variables on `8queens` rise from 9,801 to 10,001.
These additional timings have one sample each and do not establish speed
estimates.

The raw reports, frozen controls, source/task hashes and reproduction scripts
are local artifacts under
`.benchmarks/experiments/encoding-reductions-20261002/`; the original-shape
comparison is under `encoding-proposal-20261002/`. Another user-started
`profile_clauses` execution overlapped the later comparison. Wall times are
therefore preliminary. Solve wall minus callback wall is a residual, not an
exclusive native CPU attribution during parallel solving.

Further module-omission probes identify transitive and acyclic joins as sources
of many remaining ground rules. Those probes remove semantics and only locate
cost. Factoring their shared two-step paths is a possible next experiment,
**not implemented**; it must preserve the existing slot-order, shortcut and
directed-flow guards. Removing those constraints or replacing them with a
stronger closure would change the task being solved.

### Ground size of pairwise helpers

Several helpers compared two placeholders with `var_at(.., V0), var_at(.., V1),
V0 != V1`, which grounds every pair of variable ids. Each placeholder holds
exactly one variable, so they now state `var_at(.., V), not var_at(other, V)`
and are derived only for the literal pairs their consumer inspects:
`different_variable_binding` (equal term shapes), `tuple_mutex_vars_differ`,
`project_vars_differ`, `fd_inputs_differ`, `aggregate_input_differs` and
`arithmetic_input_differs`. Typing is stated per variable instead of per pair
of placeholders, mode order compares neighbouring slots, and three aggregate
safety constraints covered by the general element constraint were removed with
the views only they used. `generator.py` also drops comment nodes from the
parsed metaprogram; they were added to every `Control` and counted by
`program_chars`, which now measures code only.

The clause spaces of 34 benchmark tasks (every task in `benchmarks/gentians`
except `euclid` and the four Alzheimer ones, which exceeded the 150 s allowed
per task; the 34 include the 1,149,016 clauses of `synthetic_million`) are
text-identical before and after. Sizes and times are
medians of 9 runs, in two alternating rounds per variant of one process each,
default `Arguments`, exhaustive enumeration; Python 3.14, Clingo 5.8.0,
Windows 11, Intel Core i7-13700H. The second round is shown; the first agreed
within 5 ms of grounding. Total is the whole `generate_clause_space` call.

| Dataset | Ground rules before → after | Grounding ms before → after | Total ms before → after |
| --- | --- | --- | --- |
| `grandparent` | 6028 → 3480 | 27.6 → 25.3 | 73.0 → 67.4 |
| `4queens` | 14903 → 11058 | 35.5 → 34.9 | 118.0 → 120.4 |
| `8queens` | 37627 → 23586 | 51.6 → 42.6 | 1028.5 → 985.8 |
| `coloring` | 10008 → 6174 | 30.5 → 27.9 | 64.9 → 61.2 |
| `subset_sum` | 3887 → 2732 | 25.1 → 25.5 | 39.4 → 38.4 |
| `latin_square` | 20384 → 9935 | 41.8 → 30.7 | 151.3 → 122.3 |
| `magic_square_no_diag` | 36357 → 20767 | 55.0 → 39.3 | 460.7 → 413.0 |
| `subset_sum_double_unbalanced_count` | 12944 → 7580 | 33.9 → 28.3 | 2821.2 → 2753.2 |

Ground rules fall by 26% to 51%. Grounding time follows on the larger programs
and is within noise on the smallest. Total time barely moves where Python
canonicalization dominates: grounding is a small share of clause generation,
so this is a smaller ground program, not a faster pipeline.

### Second pass: decoding, rendering and five more rewrites

A later pass measured each stage of `generate_clause_space` without a
profiler. Decoding models was 26-28% of the call on the arithmetic tasks,
parsing the rendered clauses 9-22%, and grounding 1-7%. It changed three
things in Python and five in the metaprogram, all of which leave the 34
clause spaces above text-identical:

- At that stage, `decoder.py` read model literals through clingo's C function
  with one reused result cell instead of `Model.is_true`. The current decoder
  supersedes it with one shown-symbol copy per model; see
  [decoder research and integration](../clause-decoder-research.md).
- Canonicalization renders each distinct head once per mode space.
- `CoverageSolver` maps shown symbols to example bits through a table keyed by
  the raw symbol id; 0.47 ms became 0.03 ms per evaluation on the 99 shown
  symbols of `magic_square_no_diag`.
- `subsumption` compares only atoms of different modes (theta reduction is
  exact within one mode), first-occurrence order compares consecutive ids,
  `repeated_var` counts placeholders, the doubling check drops slots, and the
  helpers of `cardinality_upper` and `inverse` exist only with their facts.

The same protocol as above, four alternating rounds of 7 runs per variant; the
machine was loaded during the first two, so the last two are shown.

| Dataset | Ground rules before → after | Total ms before → after (round 3, round 4) |
| --- | --- | --- |
| `grandparent` | 3489 → 3220 | 80 → 75, 71 → 72 |
| `8queens` | 23592 → 17565 | 1017 → 868, 985 → 829 |
| `latin_square` | 9947 → 6773 | 113 → 103, 112 → 100 |
| `magic_square_no_diag` | 20779 → 14675 | 384 → 345, 388 → 324 |
| `subset_sum_double_unbalanced_count` | 7590 → 5467 | 2681 → 2208, 2669 → 2131 |
| `set_partition_sum_cardinality_and_square` | 16954 → 12979 | 657 → 521, 627 → 495 |

The after column includes the rules of `legality/flow/removal.lp` and the
guards added with it. Clause generation is 9% to 21% faster on the larger
tasks and unchanged within noise on `grandparent`. Decoding relies on clingo's
private cffi module and the coverage table on `Symbol._rep`; both are pinned by
the locked clingo version and covered by the generation and evaluation tests.

Prototypes that were measured and dropped in that historical pass: decoding from shown symbols in one
call (3-7%, less than the direct call), deducing the last candidate variable
without a probe (no gain), a prefix predicate instead of the two counts in
`same_mode_tuple_gt` (no gain), adding the static evaluation program as text
(five times slower than as AST) and single-threaded enumeration (mixed).

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
