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
#modeb(*,edge(var(node,any),var(node,any)),positive).
```

Use a finite global length or a finite recall to make that task enumerable.

## Example

```prolog
#maxv(3).
#maxbl(2).
#maxhl(1).
#maxpl(*).

#modeh(1,target(var(node,any))).
#modeb(2,edge(var(node,any),var(node,any)),positive).
#modeb(1,red(var(node,any)),positive).
```

This permits clauses with at most three distinct variables, two body literals,
and one head atom. Candidate hypotheses may use any number of clauses from the
finite rule space.

## Normal modes

Normal head and body modes contain an atom template rather than a separate
predicate name and arity:

```prolog
#modeh(1,target(var(node,input))).
#modeb(1,edge(var(node,input),var(node,output)),positive).
#modeb(1,blocked(var(node,input)),negative).
```

Every argument is explicit. Variables always contain a nominal type and one
direction; `var(type)` without a direction is invalid.

```ebnf
head-mode       = "#modeh(", recall, ",", atom-template, ")." ;
body-mode       = "#modeb(", recall, ",", atom-template, ",", polarity, ")." ;
atom-template   = predicate, ["(", mode-argument, {",", mode-argument}, ")"] ;
mode-argument   = variable-argument | constant-argument ;
variable-argument = "var(", type, ",", direction, ")" ;
constant-argument = "const(", type, ")" ;
direction       = "input" | "output" | "any" ;
polarity        = "positive" | "negative" ;
recall          = positive-integer | "*" ;
type            = lowercase-identifier ;
```

Directions mean:

- `input`: must already be bound.
- `output`: is produced by a selected positive body literal.
- `any`: deliberately has no input/output requirement; a positive body literal
  still binds it for later inputs.

An output requirement in a rule head must be produced by a positive normal
body output, aggregate result, or arithmetic result. It is also satisfied when
that variable is unified with an input position of the same head. A negative
body mode cannot declare output variables. ASP safety remains active
independently of mode direction.

Built-ins have intrinsic directions rather than task syntax:

- aggregate condition variables are local or supplied by surrounding terms;
  the aggregate result is `output`;
- arithmetic consumes its first two arguments as `input` and produces its
  third argument as `output`;
- comparisons consume both arguments as `input` and produce nothing.

Readiness is a clause-wide fixed point, not textual body order. A zero-input
positive mode can seed a constraint, its outputs can make another literal
ready, and so on. Bundled benchmarks therefore use explicit `input`/`output`
directions throughout. `any` remains available only when a task intentionally
opts out of mode-directed pruning.

Types are nominal task declarations. They constrain which positions may share
a generated variable; they do not add domain literals to learned rules. The
reserved type name `any` is invalid because every normal-mode type must be
explicit. Aggregate source literals continue deriving their types from their
defined occurrences in the task; declared normal-mode types name connected
aggregate positions when both describe the same observed domain. Connections
come from shared variables in task rules, not merely from equal ground values:
the integer `1` may be both a node identifier and a numeric value without
merging those nominal types.

Gentians does not synthesize missing normal modes from background knowledge or
examples. No head modes means constraint learning; no body modes means no body
predicate templates. The task is the complete authority for normal language
bias.

## Constant placeholders

Constants allowed in learned literals are enumerated explicitly:

```prolog
#constant(colour,red).
#constant(colour,green).

#modeb(1,colour(var(node,input),const(colour)),positive).
```

`const(colour)` expands independently to each declared colour. A template with
multiple constant positions expands to their Cartesian product. All concrete
expansions share the original declaration's recall. Constants do not count
towards `#maxv`, are always ground, and have no direction. Using `const(type)`
without any `#constant(type,value)` is a task error.

`#constant` is mode-bias syntax and does not assert a background fact. It is
unrelated to Clingo's `#const name=value` macro, which remains background ASP.
Bundled tasks use it only when the learned rule itself contains a fixed term;
`constant_colour` is the reference benchmark. Singleton background predicates
such as `hd(D)` and `max_weight(M)` keep variable placeholders because their
values must be shared with aggregate or comparison results.

## Predicate invention

Invented predicates use the same complete template:

```prolog
#invent(2,helper(var(node,input),var(node,output))).
```

The template generates a head mode with recall 1 and a positive body mode with
the declared recall. This keeps invented arguments typed and directed without
fallback inference.

## Runtime boundary

These limits do not belong in `Arguments`. Options such as random seed,
population size, evolutionary operators, Clingo arguments, and enumeration
strategy remain runtime configuration because they change execution rather than
the legal hypothesis language.

GENTIANS always enumerates the complete finite rule space. There is no
`max_candidate_clauses` runtime option: its only supported value was `0` (all),
so exposing it would create configuration without a real choice.
