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
| Ground relations and numeric/nominal domains | `analysis/ground_relations.py`, `analysis/domains.py` |
| Property inference from ASP rules and ground relations | `analysis/inference.py`, `analysis/rule_properties.py`, `analysis/relation_properties.py` |
| Mode expansion | `mode_compiler.py` |
| ASP fact assembly | `fact_compiler.py` |
| Mode representation facts | `mode_facts.py` |
| Static predicate-property facts | `property_facts.py` |
| Declarative legality and redundancy checks during enumeration | `metaprogram/` |
| Positive-only constraint proof and post-model theta pruning | `pruning.py` |
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

After solving, `decoder.py` constructs a `ReifiedClause`. The generator then
applies theta pruning and calls canonicalization. Decoding itself does not
reject theta-redundant clauses, and it reads variable positions from
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
| `legality/` | Structural limits, recalls, labels, invention, scopes, types and safety. `flow/` separates binding roles, seeds, closure and requirements. |
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
