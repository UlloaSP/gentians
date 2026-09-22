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
| Mode expansion and ASP fact emission | `mode_compiler.py`, `fact_compiler.py` |
| Declarative legality and redundancy checks during enumeration | `metaprogram/` |
| Positive-only constraint proof and post-model theta pruning | `pruning.py` |
| Clingo model decoding | `decoder.py` |
| Clause normalization and representative selection | `canonicalization/clauses.py`, `canonicalization/arithmetic.py` |
| Linear and expression normalization algorithms | `canonicalization/linear_normalization.py`, `canonicalization/expression_normalization.py` |
| Arithmetic systems, expressions and constraint values | The remaining class modules in `canonicalization/` |

The generator obtains static evidence from `analysis/` before passing it to
`fact_compiler.py`. The compiler translates the supplied properties and numeric
domain into facts; it does not infer them. `pruning.py` supplies the conservative
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
solves them together; these directories are responsibilities, not execution
stages.

| Directory | Responsibility |
| --- | --- |
| `representation/` | Select modes, assign variables and derive literal, operator, conditional, aggregate and tuple relations. |
| `safety/` | Enforce scopes, nominal types, linkedness, ASP safety and directed variable flow. |
| `pruning/` | Enforce clause limits, recalls, labels and invention policy; remove duplicate literals and symmetric encodings. |
| `operators/` | Prune arithmetic and comparison contradictions or redundancies. |
| `properties/` | Apply predicate properties supplied by static task analysis. |

`selected(Section,Slot,Mode)` identifies a selected mode occurrence.
`var_at(Section,Slot,Arg,Var)` assigns a variable to one flattened placeholder;
`Arg` is not necessarily a rendered predicate argument because templates can
contain nested terms. Fixed terms remain in the compiled mode shape.
`representation/literals.lp` derives positive and negative literal views from
these assignments. Conditional and aggregate roles are represented separately;
`safety/scopes.lp` determines which variables are local to their conditions.

Property facts are evidence from the task analysis, not coverage measurements
of individual clauses. Shared tuple comparisons live in `representation/tuples.lp`;
their consumers own the constraints that reject a particular combination.
Comments beside those constraints explain semantic assumptions rather than
repeat the shared predicate inventory.
