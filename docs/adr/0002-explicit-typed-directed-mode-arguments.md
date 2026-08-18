# ADR 0002: Explicit typed and directed mode arguments

Status: accepted.

## Context

Normal modes previously declared predicate name and arity separately, with an
optional direction tuple. Every generated argument was a variable. Types were
inferred from background facts and examples, so data changes could silently
change the legal hypothesis space. Adding constant placeholders would also
make a separate arity-aligned direction tuple ambiguous.

ILASP's `var(type)`, `const(type)`, and `#constant(type,value)` make term kind
and type part of language bias. Gentians additionally needs its existing
input/output discipline.

## Decision

Normal mode arguments use exactly one of:

```prolog
var(type,input)
var(type,output)
var(type,any)
const(type)
```

`var(type)` is invalid. There is no separate direction tuple and no legacy
syntax adapter. Predicate arity is derived from the atom template. Body
polarity remains an explicit Gentians argument.

Constants are finite and task-owned through `#constant(type,value)`. They are
not inferred from background terms and do not assert facts. Each constant
template is expanded into concrete generator modes in Python; those modes share
one recall group. This keeps the existing variable assignment machinery small
instead of introducing a general term-assignment layer throughout every ASP
pruning module.

Normal modes are never synthesized from observed predicates. Types, term kinds,
directions, polarities, and recalls all come from the task. Predicate invention
uses the same atom template so invented arguments need no fallback defaults.

Aggregate declarations remain unchanged. Their source predicates already occur
in background/example literals, so aggregate argument types continue to be
inferred from those defined occurrences. When an explicitly typed normal mode
belongs to the same observed type component, its task type name labels that
component. Comparison and arithmetic modes retain intrinsic built-in types.

## Direction semantics

- Head inputs seed bound variables.
- Body inputs must be bound.
- Outputs from positive body literals become bound and produced.
- `any` positions impose no readiness requirement; positive body occurrences
  become bound but are not considered produced.
- Head outputs require a produced variable.
- Negative modes cannot declare outputs and never produce variables.
- Constants are always ground and have no direction.

An all-`any` mode deliberately opts out of directed ordering. This lets migrated
tasks preserve their previous broad spaces while making that choice explicit.

## Consequences

- Changing task data no longer invents or retypes normal modes.
- Missing direction/type information fails during parsing.
- Constant-only clauses can use `#maxv(0)`; existing policy still requires a
  non-empty body for generated clauses.
- Multiple constants cause Cartesian expansion. Task authors control this cost
  through explicit finite declarations, recalls, and structural limits.
- Every bundled Gentians task must migrate its normal modes. Existing Clingo
  `#const` macros stay unchanged; bundled ILASP tasks already use their own
  native syntax and stay unchanged.
- Hypothesis cache schema changes because generated mode identities and legal
  rule spaces change.

## Rejected alternatives

### Keep the direction tuple

Rejected: constant positions make tuple alignment redundant and ambiguous.

### Allow `var(type)` with implicit `any`

Rejected: omission and deliberate lack of direction become indistinguishable.

### Infer constants from background knowledge

Rejected: data changes would silently expand the hypothesis language.

### Replace every `var_at` relation with generic term assignment

Rejected: constants can be expanded into concrete modes with much less code and
without rewriting all variable safety and property modules.
