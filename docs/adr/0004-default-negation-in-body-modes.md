# ADR 0004: Default negation in body modes

Status: accepted.

## Context

Body modes encoded polarity as a third argument, `positive` or `negative`.
That repeated information already represented by ASP's `not` syntax and made
positive declarations noisier than necessary.

## Decision

Positive body modes omit a polarity marker:

```prolog
#modeb(1,p(var(term,input))).
```

Default-negated body modes place `not` before the atom template:

```prolog
#modeb(1,not p(var(term,input))).
```

The two forms are independent declarations. A task that permits both
polarities declares both, preserving separate recalls and existing generation
semantics. `not` is invalid in head modes. Negated body modes cannot contain
`output` arguments because they do not bind variables.

Internally Gentians retains mode polarity: rule generation and rendering still
need to distinguish positive literals from default-negated literals. Existing
ASP `positive_mode/1` and `negative_mode/1` relations remain unchanged.

## Consequences

- Task syntax matches learned ASP literals directly.
- The old three-argument `#modeb` form is rejected; there is no compatibility
  adapter.
- Bundled Gentians tasks migrate one-to-one without changing their hypothesis
  spaces.
- ILASP benchmark sources retain ILASP syntax and are not Gentians task files.

## Rejected alternative

Automatically enabling the positive form when a negated mode is declared was
rejected because it would silently enlarge the hypothesis space and make recall
ownership ambiguous.
