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

Clingo applies theta reduction with the other redundancy checks before returning
a model. `mode_facts.theta_facts` chooses its encoding: enumerated offsets keep
the program normal, and saturation takes over only when they would be too many
(see `docs/metaprogram/README.md`). After solving, `decoder.py` constructs a `ReifiedClause` and the
generator calls canonicalization. Decoding reads variable positions from
`ClauseMode` rather than importing the mode compiler.

Arithmetic representation modules own keys, variable sets, remapping and
rendering. Normalization algorithms own connected components, substitutions,
linear reduction and contradiction detection. Choosing one representative per
canonical key remains part of canonicalization; no separate duplicate policy
reimplements that choice. `ClauseSpace` orders and deduplicates the final clauses.

These stages concern individual clauses. Dependency closure and coverage of a
complete candidate hypothesis remain in `hypotheses/` and `evaluation/`.

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
