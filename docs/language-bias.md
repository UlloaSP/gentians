# Language bias

Status: implemented.

An inductive task owns every limit that changes which hypotheses are legal.
Runtime configuration owns only how GENTIANS searches that space.

## Structural limits

```prolog
#maxv(4).
#maxbl(3).
#maxhl(1).
#maxpl(6).
```

| Directive | Meaning |
| --- | --- |
| `#maxv(N).` | At most `N` distinct variables in one clause. |
| `#maxbl(N).` | At most `N` literals in one clause body. |
| `#maxhl(N).` | At most `N` atoms in one clause head. `0` permits only headless clauses. |
| `#maxpl(N).` | At most `N` clauses in one candidate hypothesis. |

`#maxv` and `#maxhl` follow ILASP terminology. `#maxpl` uses `p` for
program because `h` already means hypothesis/head in the surrounding language.

## Grammar

```ebnf
limit-directive = limit-name, "(", limit, ")", "." ;
limit-name      = "#maxv" | "#maxbl" | "#maxhl" | "#maxpl" ;
limit           = non-negative-integer | "*" ;
```

Additional validity rules:

- Each directive occurs at most once in a task.
- `#maxbl` and `#maxpl` require an integer greater than zero or `*`.
- `#maxv(0).` allows only clauses without variables.
- `#maxhl(0).` allows only constraints.
- Duplicate directives are task errors.
- Missing directives use `#maxv(3)`, `#maxbl(3)`, `#maxhl(1)`, and `#maxpl(6)`.
  Bundled tasks state all four values explicitly for reproducibility.

## Meaning of `*`

`*` means **no explicit limit from that directive**, not mathematical infinity.
GENTIANS must still derive a finite search space before grounding.

- `#maxv(*).`: every variable needed by a finite clause is allowed. Unused
  variables are irrelevant and are never generated.
- `#maxbl(*).`: body length is bounded only by finite body-mode recalls.
- `#maxhl(*).`: head length is bounded only by finite head-mode recalls.
- `#maxpl(*).`: a candidate may contain every clause in the finite generated
  rule space.

All four directives may contain `*` when mode recalls still imply finite head
and body capacities. A section containing both an unbounded length and a mode
with recall `*` is invalid because it describes an infinite rule space:

```prolog
% Invalid combination: no finite body bound.
#maxbl(*).
#modeb(*,edge,2,positive).
```

Use a finite global length or a finite recall to make that task enumerable.

## Example

```prolog
#maxv(3).
#maxbl(2).
#maxhl(1).
#maxpl(*).

#modeh(1,target,1).
#modeb(2,edge,2,positive).
#modeb(1,red,1,positive).
```

This permits clauses with at most three distinct variables, two body literals,
and one head atom. Candidate hypotheses may use any number of clauses from the
finite rule space.

## Runtime boundary

These limits do not belong in `Arguments`. Options such as random seed,
population size, evolutionary operators, Clingo arguments, and enumeration
strategy remain runtime configuration because they change execution rather than
the legal hypothesis language.

GENTIANS always enumerates the complete finite rule space. There is no
`max_candidate_clauses` runtime option: its only supported value was `0` (all),
so exposing it would create configuration without a real choice.
