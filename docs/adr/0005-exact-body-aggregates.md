# ADR 0005: Exact body aggregates use `#modeb`

Status: accepted.

## Context

Body aggregates used a separate declaration:

```prolog
#modeagg(1,sum(p/2),unbalanced).
```

That declaration did not describe one ASP literal. It synthesized tuple widths
and variable assignments from predicate signatures, inferred their types from
task data, and shared recall across the resulting variants. Arithmetic and
comparisons have since moved to exact `#modeb` templates parsed by Clingo.

Keeping aggregate shape implicit made task data part of the effective language
bias and hid which projections were legal. Merely renaming the old payload to
`#modeb` would preserve that separate generative interface.

## Decision

An aggregate in a clause body is declared as one exact `#modeb` template using
Clingo aggregate syntax. The template states its tuple, positive atomic
conditions, equality result, nominal types, directions, labels, and recall.
`#modeagg`, `balanced`, and `unbalanced` are removed and rejected explicitly.

The initial aggregate mode language contains one nonempty element and one
equality result. Tuple and condition variables use `input` or `any`; the result
uses `output`. Labels express identity within the declaration. Gentians retains
its dedicated `AggregateLiteral` and aggregate metaprogram modules because
scope, safety, dependencies, canonicalization, and result production remain
different from normal predicate literals.

Each exact declaration owns its recall. Separate tuple projections do not share
a hidden recall group. Tasks that need several projections declare them
separately and thereby choose their recalls explicitly.

## Consequences

- `InductiveTask.language_bias_body` owns normal atoms, comparisons, arithmetic
  relations, conditional literals, and body aggregates through one interface.
- Aggregate legality no longer depends on discovering a predicate signature or
  inferring its argument types from examples.
- Task authors see and control the exact aggregate tuple and projection.
- Migrating an old unbalanced declaration requires choosing the tuple shapes
  the task actually intends; its old generated family has no automatic adapter.
- The clause space and benchmark fingerprints change.

## Rejected alternatives

### Put the old aggregate payload inside `#modeb`

Rejected: `#modeb(1,sum(p/2),unbalanced)` would change only the directive name
while retaining a second, implicit body-mode language.

### Preserve automatic balanced/unbalanced expansion

Rejected: it keeps aggregate projections and shared recall implicit, unlike the
exact relation templates used by the rest of `#modeb`.

### Remove aggregate-specific IR and metaprogram rules

Rejected: a uniform declaration interface does not make aggregate-local scope,
result production, ASP safety, or tuple canonicalization equivalent to normal
body atoms.
