# ADR 0001: Task-owned structural limits

- Status: accepted
- Date: 2026-08-18

## Context

`max_variables`, `max_depth`, `disjunctive_head_length`, and
`max_program_clauses` lived in Python `Arguments` and benchmark catalog entries.
A task file therefore did not fully describe its hypothesis language. Running
the same file with different Python configuration silently changed the rules
and programs GENTIANS could learn.

Three limits feed rule-space generation. `max_program_clauses` feeds the
evolutionary program generator and fitness setup. Despite different consumers,
all four constrain legal hypotheses rather than search strategy.

## Decision

Task files own four directives:

```prolog
#maxv(VARIABLES).
#maxbl(BODY_LITERALS).
#maxhl(HEAD_ATOMS).
#maxpl(PROGRAM_CLAUSES).
```

Each value is a non-negative integer, subject to the validation rules in
`docs/language-bias.md`, or `*`. Omitted directives use documented defaults;
bundled tasks remain explicit.

Parsed values belong directly to the task `Program`. No compatibility adapter,
second configuration object, or precedence rule is introduced.

The four old `Arguments` fields are removed. Benchmark-specific values move
from `benchmarks/catalog.py` into `benchmarks/gentians/*.txt`. Every bundled
task states all four directives explicitly.

`max_candidate_clauses` is also removed from `Arguments`. GENTIANS always
uses its only supported behavior, `0` (enumerate all candidate clauses),
directly when configuring Clingo. This value is execution plumbing, not task
bias, and exposing a constant as public configuration has no benefit.

## Why these names

- `#maxv` matches ILASP and is already established ILP vocabulary.
- `#maxbl` says body length directly.
- `#maxhl` says head length directly and matches existing ILASP vocabulary.
- `#maxpl` says program length. Reusing `h` would make hypothesis/head ambiguous.
- Short names fit existing `#modeh`, `#modeb`, and `#modeagg` syntax.

`#max_penalty` is not reused: ILASP penalty measures optimisation cost, not an
exact clause-count ceiling.

## Why `*` is not infinity

GENTIANS enumerates a finite rule space with Clingo. A literal interpretation of
unbounded variables and unbounded clause lengths can produce infinitely many
rules, so enumeration cannot start.

`*` therefore removes only that directive's explicit cap. Other structural
facts must still provide a finite natural maximum. `#maxpl(*)` naturally means
the whole finite rule space. Head/body `*` values require finite recalls for
their respective mode declarations. An underbounded task is rejected early.

This keeps `*` useful without introducing arbitrary implementation limits whose
values would become hidden bias.

## Semantic change from `max_depth`

Previous `max_depth` was not body depth. It limited total clause size:

```text
head atoms + body literals <= max_depth
```

The new directives impose independent limits:

```text
body literals <= maxbl
head atoms <= maxhl
```

This is not an exact rename. For example, old `max_depth=4` and
`disjunctive_head_length=3` allowed at most one body literal when all three head
slots were occupied. New `#maxbl(4)` plus `#maxhl(3)` allows seven total literals.

Migration must choose benchmark values deliberately and regenerate hypothesis
spaces. Keeping an additional total-length limit would preserve old semantics
but create a fifth overlapping bound; that complexity is rejected unless real
tasks demonstrate the need.

## Consequences

- Task files become self-contained and reproducible.
- `Arguments` contains execution policy only.
- `max_candidate_clauses` disappears; rule-space enumeration always requests
  every candidate.
- Catalog entries become smaller and stop being a second source of task bias.
- `--set max_depth=...` and equivalent JSON fields become invalid breaking API.
- Hypothesis cache schema/key must change; task content hash covers new limits.
- Parser errors become the single validation boundary for malformed limits.
- Existing benchmark spaces may change because body and head limits are now
  independent.
- Tests, README examples, ASP fact comments, profiling scripts, and bundled task
  files require migration when implementation begins.

## Rejected alternatives

### Keep limits in `Arguments`

Rejected: task meaning remains split across file, Python call, and catalog.

### Allow task directives plus Python overrides

Rejected: creates precedence rules and two sources of truth. Benchmark variants
should use distinct task files.

### Treat `*` as a large implementation constant

Rejected: hidden constant becomes undocumented language bias and changes results
when tuned.

### Add a `ModeBiasLimits` wrapper

Rejected for now: four fields fit directly on `Program`; wrapper adds navigation
without enforcing a useful boundary.
