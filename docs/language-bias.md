# Language bias

Status: implemented.

An inductive task owns every limit that changes which hypotheses are legal.
Runtime configuration owns only how GENTIANS searches that space.

## Structural limits

```prolog
#maxv(4).
#maxbl(3).
#minhl(1).
#maxhl(1).
#maxpl(6).
```

| Directive | Meaning |
| --- | --- |
| `#maxv(N).` | At most `N` distinct variables in one clause. |
| `#maxbl(N).` | At most `N` literals in one clause body. |
| `#minhl(N).` | At least `N` atoms in a head built by `#modeha`. |
| `#maxhl(N).` | At most `N` atoms in one clause head. `0` permits only headless clauses. |
| `#maxpl(N).` | At most `N` clauses in one candidate hypothesis. |

`#maxv` and `#maxhl` follow ILASP terminology. `#maxpl` uses `p` for
program because `h` already means hypothesis/head in the surrounding language.

## Grammar

```ebnf
limit-directive = limit-name, "(", limit, ")", "." ;
limit-name      = "#maxv" | "#maxbl" | "#maxhl" | "#maxpl" ;
limit           = non-negative-integer | "*" ;
aggregate-head-minimum = "#minhl(", positive-integer, ")." ;
```

Additional validity rules:

- Each directive occurs at most once in a task.
- `#maxpl` requires an integer greater than zero or `*`.
- `#maxv(0).` allows only clauses without variables.
- `#maxbl(0).` allows only bodyless rules; ASP safety still applies.
- `#maxhl(0).` allows only constraints.
- `#minhl` requires a positive integer and cannot exceed a finite `#maxhl`
  when `#modeha` is present. Its default is `1`.
- Duplicate directives are task errors.
- Missing directives use `#maxv(3)`, `#maxbl(3)`, `#maxhl(1)`, and `#maxpl(6)`.
  Bundled tasks state all four values explicitly for reproducibility.

## Meaning of `*`

`*` means **no explicit limit from that directive**, not mathematical infinity.
GENTIANS must still derive a finite search space before grounding.

- `#maxv(*).`: every variable needed by a finite clause is allowed. Unused
  variables are irrelevant and are never generated.
- `#maxbl(*).`: body length is bounded only by finite body-mode recalls.
- `#maxhl(*).`: head length is derived from the widest complete `#modeh` and
  the sum of finite `#modeha` recalls.
- `#maxpl(*).`: a candidate may contain every clause in the finite generated
  rule space.

All four directives may contain `*` when mode recalls still imply finite head
and body capacities. A section containing both an unbounded length and a mode
with recall `*` is invalid because it describes an infinite rule space:

```prolog
% Invalid combination: no finite body bound.
#maxbl(*).
#modeb(*,edge(var(node,any),var(node,any))).
```

Use a finite global length or a finite recall to make that task enumerable.

## Example

```prolog
#maxv(3).
#maxbl(2).
#maxhl(1).
#maxpl(*).

#modeh(1,target(var(node,any))).
#modeb(2,edge(var(node,any),var(node,any))).
#modeb(1,red(var(node,any))).
```

This permits clauses with at most three distinct variables, two body literals,
and one head atom. Candidate hypotheses may use any number of clauses from the
finite rule space.

## Normal modes

Body modes contain one literal template. A head mode contains one complete
head template:

```prolog
#modeh(1,target(var(node,input))).
#modeh(1,red(var(node,input,x));green(var(node,input,x));blue(var(node,input,x))).
#modeh(1,{heads(var(coin,input,x));tails(var(coin,input,x))}).
#modeh(1,1 {heads(var(coin,input,x));tails(var(coin,input,x))} 1).
#modeh(1,-rejected(var(node,input))).
#modeb(1,edge(var(node,input),var(node,output))).
#modeb(1,not blocked(var(node,input))).
#modeb(1,not -approved(var(node,input))).
#modeb(1,wrapped(box(var(node,input),const(colour)))).
```

Every `#modeh` is an alternative complete head. Gentians selects either no
head (a constraint) or exactly one declaration; it does not construct subsets
or combine separate declarations. Head recall must be `1`. `#maxhl` bounds the
number of atoms in a declaration, and `#maxhl(*)` derives that width from the
largest declared head.

The optional third component of a head variable is a declaration-local
identity label. Reusing a label forces the corresponding positions to use one
variable. Different labels force different variables. Unlabelled positions
remain free. Labels must use compatible type declarations; their directions
may differ.
Conditional syntax is introduced with `#modec`, not embedded directly in a
`#modeh` declaration. Generated conditions may attach to every element of a
normal, disjunctive, choice, or cardinality head.

Every argument is explicit. Variables always contain a nominal type and one
direction; `var(type)` without a direction is invalid.

Functions and tuples may nest without a depth limit. Their leaves remain
explicit `var(...)` or `const(...)` placeholders. Variable limits, typing,
directions, labels, safety, and rendering use those leaves in left-to-right
depth-first order. Predicate arity still counts outer arguments, so
`p(f(X,Y))` has arity 1 and two variable placeholders.

```ebnf
head-mode       = "#modeh(1,", head-template, ")." ;
body-mode       = "#modeb(", recall, ",", ["not", whitespace], atom-template, ")." ;
condition-mode  = "#modec(", recall, ",", ["not", whitespace], atom-template, ")." ;
aggregate-head-mode = "#modeha(", [recall, ","], atom-template, ")." ;
head-template   = atom-template
                | atom-template, {";", atom-template}
                | [integer], "{", atom-template, {";", atom-template}, "}", [integer] ;
atom-template   = ["-"], predicate, ["(", mode-term, {",", mode-term}, ")"] ;
mode-term       = variable-argument | constant-argument | function-term | tuple-term ;
function-term   = function, "(", mode-term, {",", mode-term}, ")" ;
tuple-term      = "(", ")"
                | "(", mode-term, ",", [mode-term, {",", mode-term}], ")" ;
variable-argument = "var(", type, ",", direction, [",", label], ")" ;
constant-argument = "const(", type, ")" ;
direction       = "input" | "output" | "any" ;
recall          = positive-integer | "*" ;
type            = lowercase-identifier ;
label           = lowercase-identifier ;
```

A body mode without `not` permits the positive literal. A body mode with
`not` permits only its default-negated form. Declare both modes independently
to permit both polarities; their recalls remain independent. Head modes cannot
contain `not`.

## Learnable facts and empty bodies

An empty body is legal when the selected complete head is ASP-safe:

```prolog
#modeh(1,ready).

#constant(node,a).
#modeh(1,seed(const(node))).
```

These declarations include `ready.` and `seed(a).` in the rule space. The same
applies to ground disjunctions, choices, and cardinality heads. A variable in a
bodyless head is still rejected unless its head-conditional scope grounds it;
Gentians does not turn nominal types into hidden domain literals. The empty
head and empty body combination is never emitted, so `:-.` cannot be learned.

## Explicit meta-ASP bias and metarules

`#bias` adds ASP directly to the same meta-program that enumerates clauses. It
may span lines, and multiple declarations are cumulative:

```ebnf
bias-directive = "#bias(\"", asp-program, "\")." ;
```

```prolog
#bias("
bias_uses_edge :- selected_atom(body,_,\"edge\",2,positive).
:- selected_slot(head,_), not bias_uses_edge.
").
```

The stable relations intended for task bias are:

| Relation | Meaning |
| --- | --- |
| `selected(Section,Slot,Mode)` | Selected head or body mode at a slot. |
| `selected_atom(Section,Slot,Name,Arity,Polarity)` | Selected normal or conditional atom; `Name` is a string. |
| `selected_slot(Section,Slot)` | Occupied slot. |
| `selected_head_form(Form)` | Selected complete `#modeh` form. |
| `mode(Section,Mode,Pred,Arity,Recall)` | Reified mode metadata. |
| `predicate_symbol(Pred,Name,Arity)` | Predicate id to quoted ASP name. |
| `head_form_member(Form,Slot,Mode)` | Atom positions of a complete head. |
| `mode_variable_arg(Mode,Arg)` | Bindable flattened argument position. |
| `var_at(Section,Slot,Arg,Var)` | Variable assigned to that position. |
| `head_arg_label(Form,Mode,Arg,Label)` | Label metadata declared in `#modeh`. |
| `positive_mode(Mode)` / `negative_mode(Mode)` | Body literal polarity. |

Metarules are ordinary derived ASP rules inside `#bias`; they can name a
structural pattern once and let constraints require or forbid it. No separate
template engine or `#modem` cost language is involved:

```prolog
#bias("
bias_same_label_var(F,L,V) :-
    selected_head_form(F),
    head_arg_label(F,M,A,L),
    selected(head,S,M),
    var_at(head,S,A,V).

:- bias_same_label_var(F,L,X), bias_same_label_var(F,L,Y), X != Y.
:- bias_same_label_var(F,L,V), bias_same_label_var(F,R,V), L < R.
").
```

The presence of any `#bias` switches variable identity to explicit control.
Head labels remain available through `head_arg_label/4`, but Gentians stops
enforcing equal labels as equal variables and different labels as different
variables. The two constraints above restore both halves explicitly: equal
labels share a variable, and distinct labels cannot share one. Without `#bias`,
the default label semantics described in the normal-mode section remain active.
Typing, linkedness, direction checks, and ASP safety do not turn off: they are
validity conditions rather than identity policy.

`#bias` extends and restricts the finite space declared by modes. It does not
invent undeclared object-level predicates or bypass the mode grammar. Auxiliary
predicates defined inside a bias must use the `bias_` prefix. Generator
relations are read-only. Only ordinary ASP rules and hard constraints are
accepted: weak constraints, optimization directives, and a comment-only bias
are task errors because they would change or silently empty model enumeration.

## Aggregate head modes

`#modeha` is the ILASP aggregate-head declaration: each declaration contributes
compatible atoms that Gentians may combine into one choice/cardinality head.
It is distinct from body `#modeagg` declarations.

```prolog
#constant(colour,red).
#constant(colour,blue).
#minhl(1).
#maxhl(2).
#modeha(2,selected(var(node,input),const(colour))).
```

The recall may be omitted, meaning `*`. Recall counts uses of the declaration,
not its concrete constant variants. For the example, heads may contain one or
two compatible `selected/2` atoms. Width two includes forms such as:

```prolog
0 {selected(V0,red);selected(V0,blue)} 1
1 {selected(V0,red);selected(V0,blue)} 1
1 {selected(V0,red);selected(V0,blue)} 2
```

Gentians emits every meaningful integer interval and removes the two forms
that decompose into simpler heads: unrestricted `0..N` and all-required
`N..N` for `N > 1`. A singleton remains `0 {a} 1`. Separate declarations may
be combined, subject to each recall. `#minhl` affects only generated
`#modeha` heads; explicit complete `#modeh` declarations remain unchanged.

Aggregate-head atoms support strong negation, typed directions, constants,
functions, and tuples. They cannot use default negation or head identity
labels. The normal safety and direction rules apply. `#modec` may attach
conditions independently to every generated element, and those conditions
still consume the clause-wide body budget. Elements of one aggregate head are
one structural component for linkedness, so compatible atoms may use distinct
variables grounded by distinct body literals.

With `#maxhl(*)`, all `#modeha` recalls must be finite. Gentians then derives
the maximum width from their summed recalls. This preserves a finite search
space before grounding.

## Conditional literals

`#modec` declares atoms that may occur after the colon of a conditional
literal:

```prolog
#maxbl(3).
#modeh(1,target(var(node,input))).
#modeb(1,base(var(node,any))).
#modec(1,node(var(node,any))).
#modec(1,not blocked(var(node,input))).
```

This bias includes clauses such as:

```prolog
target(V0):node(V0),not blocked(V0) :- base(V0).
```

Gentians keeps the unconditioned form too. It may attach zero or more
conditions to each selected normal head or body literal. One `#modec` recall
is shared across all attachments in a clause, including head conditions.
`#maxbl` counts ordinary body literals plus every attached condition, wherever
the conclusion occurs. Therefore the example needs a budget of three: one
ordinary body literal and two conditions. With `#maxbl(*)`, every `#modec`
recall must be finite.

Conditions support default negation, strong negation, constants, nested
functions, and tuples using the same grammar as `#modeb`. Declare positive
and default-negated forms separately. Variable labels remain exclusive to
`#modeh` and cannot appear in `#modec`.

ASP scoping determines conditional-variable safety. A variable used only in a
body conditional is local. Its positive conclusion or one of its positive
conditions must ground it; a default-negated conclusion cannot do so. A
variable used only in the condition part of a head element is also local, but
the head conclusion does not ground it. Every other conditional variable is
global and must be made safe outside that conditional. Global `input`
positions must be bound; global `output` positions must be produced elsewhere.
A conditional literal itself never produces a global variable.

The optional `-` is ASP strong (classical) negation and is independent from
default negation: `p(X)`, `-p(X)`, `not p(X)`, and `not -p(X)` are four distinct
forms. `p/n` and `-p/n` have separate logical identities for dependency closure
and recursion, but share the base predicate's argument types. Gentians removes
bodies that require both `p(T)` and `-p(T)`, and removes a redundant
`not -p(T)` beside `p(T)` (and conversely). Two default-negated complements are
valid and remain available.

Directions mean:

- `input`: must already be bound.
- `output`: is produced by a selected positive body literal.
- `any`: deliberately has no input/output requirement; a positive body literal
  still binds it for later inputs.

An output requirement in a rule head must be produced by a positive normal
body output, aggregate result, or arithmetic result. It is also satisfied when
that variable is unified with an input position of the same head. A body mode
containing `not` cannot declare output variables. ASP safety remains active
independently of mode direction.

Built-ins have intrinsic directions rather than task syntax:

- aggregate condition variables are local or supplied by surrounding terms;
  the aggregate result is `output`;
- arithmetic templates consume every argument except the last as `input` and
  produce the last argument as `output`; connected relations are represented
  as one arithmetic system after decoding;
- comparisons consume both arguments as `input` and produce nothing.

Arithmetic systems use residual equations and canonical integer coefficient
rows when every variable is already safe. A row that must produce a variable
keeps an oriented assignment because Clingo rejects an unsafe residual form.
Division and modulo bundle `divisor != 0` with the source operation. The guard
does not consume another recall or another `#maxbl` position.
Inverse comparison declarations (`lt`/`gt` and `leq`/`geq`) share one canonical
mode and a combined recall budget. Emitted rules contain only the final system,
not the source built-in literals.

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

#modeb(1,colour(var(node,input),const(colour))).
```

`const(colour)` expands independently to each declared colour, including inside
a function or tuple. Multiple constant positions expand to their Cartesian
product. All concrete expansions share the original declaration's recall.
Constants do not count
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
fallback inference. The invented predicate itself cannot be strongly negated;
strongly negated uses can instead be declared explicitly with `#modeh` or
`#modeb`.

## Runtime boundary

These limits do not belong in `Arguments`. Options such as random seed,
population size, evolutionary operators, Clingo arguments, and enumeration
strategy remain runtime configuration because they change execution rather than
the legal hypothesis language.

GENTIANS always enumerates the complete finite rule space. There is no
`max_candidate_clauses` runtime option: its only supported value was `0` (all),
so exposing it would create configuration without a real choice.
