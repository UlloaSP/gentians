# ADR 0003: Directed benchmark dataflow

Status: accepted.

## Context

Initial migration to typed mode arguments used `any` in bundled tasks. That
preserved their previous broad hypothesis spaces but did not encode intended
dataflow. Replacing `any` only in normal modes was insufficient: aggregate and
arithmetic results are legitimate producers, while comparisons are consumers.

Ground values also cannot define nominal type identity. Several benchmarks use
the same integers as node IDs, partition IDs, indices, counts, and values.

## Decision

Bundled benchmark normal modes declare `input` or `output` at every variable
position. Constraints start from a zero-input positive mode such as `q(O,O)`,
`value(O,O)`, or `hd(O)`. Classification heads use inputs. Functional relations
use input-to-output flow.

Built-in flow is intrinsic:

- aggregate result: output;
- arithmetic operands: inputs, arithmetic result: output;
- comparison operands: inputs.

A head output unified with a head input is already supplied. Readiness is a
fixed point across the clause, independent of rendered literal order.

Type inference for aggregate source positions follows shared variables in task
rules. Equal ground terms do not merge type components. Explicit benchmark
types use domain names such as `node`, `index`, and `partition`; `numeric` is
reserved for values participating numerically.

`#constant` is not a variable-domain declaration. Existing benchmarks retain
variables when a background value must be joined with another literal. The
dedicated `constant_colour` benchmark covers fixed-term expansion without
changing established task semantics.

## Consequences

- Illegal dataflow is pruned before Python decodes clauses.
- Intended aggregate and arithmetic target rules remain expressible.
- Bundled tasks contain no accidental `any` directions.
- Reusing `1` in unrelated domains no longer collapses their nominal types.
- Hypothesis cache schema advances because legal rule spaces change.
- `constant_colour` is catalogued but excluded from default experiment sets;
  it is a feature regression task, not a replacement performance baseline.

## Rejected alternatives

### Treat built-ins as undirected

Rejected: a computed result could not satisfy a head output, while comparisons
could introduce otherwise unbound values.

### Add `#constant` for every task-domain value

Rejected: constants describe fixed terms in learned syntax, not domains for
variables. Cartesian expansion would enlarge spaces and destroy generalization.

### Merge types when the same ground value occurs

Rejected: spelling equality does not imply domain equality.
