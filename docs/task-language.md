# Task language guide

A task file declares background ASP, examples and the language bias. This guide
introduces each part with examples. [language-bias.md](language-bias.md) is the
contract for syntax and meaning, and wins wherever the two differ.

## Head modes

Each head declaration describes one complete allowed head:

```prolog
#modeh(1, head_template).
```

The template may be a normal atom, a disjunction, a choice, a bounded
cardinality head, or a function aggregate head:

```prolog
#modeh(1,a(var(node,input))).
#modeh(1,a(var(node,input,x));b(var(node,input,x))).
#modeh(1,{a(var(node,input,x));b(var(node,input,x))}).
#modeh(1,1 {a(var(node,input,x));b(var(node,input,x))} 1).
#modeh(1,-rejected(var(node,input))).
#modeh(1,not rejected(var(node,input))).
#modeh(1,p(var(node,input,x));not p(var(node,input,x))).
#modeh(1,p(1;2)).
#modeh(1,p(1,2;3,4)).
#modeh(1,1{not blocked;selected}1).
#modeh(1,#count{1:not blocked}=1).
#modeh(1,#count{var(node,any):selected(var(node,any)):
                  node(var(node,any))}=1).
#modeh(1,var(numeric,input,n) {selected(var(node,any)):
                  node(var(node,any))} var(numeric,input,n)).
```

Separate declarations are alternatives and are never combined implicitly.
Head recall is therefore always `1`. The optional third `var` argument is a
head-local identity label: equal labels denote the same generated variable;
different labels denote different variables. An omitted label leaves that
identity unconstrained. Variable labels always retain their declared identity
semantics. `#maxhl` limits the number of elements in one declared head, not a
later combination of declarations. Exact ASP conditions may be written on
individual elements; `#modec` additionally generates optional conditions.

Safe empty bodies are learnable. Ground normal heads, disjunctions, choices,
cardinality heads, and function aggregates therefore produce facts; a variable
head without a safe source remains rejected, and the empty constraint `:-.` is
never generated. Choice bounds and function aggregate guards may be variables
when a positive body literal makes them safe.

Pools in `#modeh` remain one complete clause (`p(1;2).` grounds to both facts).
An atom pool in `#modeb` stays one body literal, including nested forms such as
`q :- p(f(1;2)).`; pools in `#modec` and combinable head modes expand to separate
permitted alternatives. Complete-head atom pools may vary several arguments
while keeping one predicate and arity. Arithmetic expressions and intervals are
valid atom arguments. Body modes also accept `#true`, `#false`, and Boolean
conditional literals such as `#false:p(X)`. Exact heads also accept Boolean and
comparison elements, empty choice/function aggregate forms, and every Clingo
cardinality guard operator. Body pools inside guards or conditional conclusions
stay grouped in one mode. Parentheses around nested pools are preserved when
they affect grounding.

### Combinable heads

ILASP-style aggregate head modes build choice/cardinality heads by combining
compatible atoms:

```prolog
#minhl(1).
#maxhl(2).
#modeha(p(var(node,input))).
#modeha(2,q(var(node,input),const(colour))).
```

The recall is optional and defaults to `*`. `#minhl` and `#maxhl` bound the
number of elements. Gentians generates the non-redundant integer cardinality
bounds, shares recall across constant expansions, and applies `#modec` to each
element. `#maxhl(*)` requires finite recalls for every `#modeha` and `#modehd`
declaration.

`#modehd` has the same combinable-element interface, but constructs plain ASP
disjunctions instead of choices:

```prolog
#minhl(2).
#maxhl(3).
#modehd(2,p(var(node,input))).
#modehd(1,q(var(node,input))).
```

The head form is always explicit: `#modeh` is a complete head, `#modeha`
combines choice elements, and `#modehd` combines disjunctive elements. Recall
never changes one form into another.

Heads may use default negation in exact normal, choice, and function aggregate
forms, in `#modeha` choice heads, and in `#modehd` disjunctions. A normal
`not p` head depends on `p`; it does not define `p`.

## Body and condition modes

For positive body literals, omit default negation:

```prolog
#modeb(recall, atom_template).
```

For negative body literals, write `not` before the atom template:

```prolog
#modeb(recall, not atom_template).
```

Declare both forms independently when both polarities are allowed.

Condition modes accept atoms and exact comparisons:

```prolog
#modec(recall, atom_template).
#modec(recall, not atom_template).
#modec(recall, arithmetic_expression < arithmetic_expression).
```

Gentians may attach them after any selected normal head or body literal, for
example `p(V0):q(V0),not r(V0)`. Their recall is clause-wide and `#maxbl`
counts attached conditions as well as ordinary body literals. A conditional
local must be grounded by a positive atom or a Clingo-safe comparison in its own
condition scope; neither a body nor a head conclusion grounds it. Global
variables must be safe outside the conditional.

## Negation, types and directions

ASP strong negation is written with `-` and can be combined with default
negation, so `p(X)`, `-p(X)`, `not p(X)`, and `not -p(X)` are distinct mode
forms. Strongly negated heads are also supported. `p/n` and `-p/n` are distinct
for dependencies and recursion while sharing argument types.

Every non-nullary argument is explicitly either a directed typed variable or a
typed constant placeholder:

```prolog
#constant(colour,red).
#constant(colour,green).

#modeh(1,target(var(node,input))).
#modeb(1,edge(var(node,input),var(node,output))).
#modeb(1,colour(var(node,input),const(colour))).
#modeb(1,not blocked(var(node,input))).
#modeb(1,wrapped(box(var(node,input),const(colour)))).
```

Variables in atom templates require exactly one direction: `input`, `output`,
or `any`. `input` must already be bound, `output` is produced by a positive body
literal, and `any` opts out of data-flow restrictions. Constants have no
direction and must be enumerated by `#constant(TYPE, VALUE)`. Modes containing
`not` cannot contain output variables. Types and directions are task
declarations; Gentians does not infer normal modes from background knowledge or
examples.

Mode terms may contain nested functions and tuples. Every leaf stays explicit:
`var(...)` for a generated variable or `const(...)` for a declared ground value.
Predicate arity counts outer arguments; variable limits and directions apply to
nested placeholders.

## Aggregates

Body aggregates are exact `#modeb` templates using Clingo syntax:

```prolog
#modeb(1,#sum{var(numeric,any,value):el(var(numeric,any,value))}=
         var(numeric,output,result)).
#modeb(1,#count{var(numeric,any,value):
                  p(var(partition,any,group),var(numeric,any,value))}=
         var(numeric,output,result)).
#modeb(1,1 {p(var(node,any)):node(var(node,any))} 2).
#modeb(1,1 {not p(var(node,any)):node(var(node,any))} 2).
#modeb(1,1 {var(numeric,any)>1:node(var(numeric,any))} 1).
#modeb(1,1 {#true:node(1)} 1).
#modeb(1,not #count{var(node,any):p(var(node,any))}=1).
```

The tuple before `:` is explicit, so projected tuples need no `balanced` or
`unbalanced` flag. Repeated labels connect tuple terms, condition arguments,
and the result inside one declaration. Tuple and condition variables use
`input` or `any`; an equality `output` result is optional. Gentians accepts
multiple elements, including empty tuples, and comparison guards, including
ranges. Conditions inside each element may include negated atoms and
comparisons, or be empty; local variables need a positive atom or a Clingo-safe
comparison. Tuple terms may contain multiple variables. Recall limits uses of
that complete template.

Separate aggregates can reuse local variable names within `#maxv`; those local
bindings do not connect the aggregates or satisfy global inputs. Global uses
retain the safety checks described in [the language contract](language-bias.md).
Literals with global variables must form one connected component; safe but
disconnected components are pruned. Invented predicates may be strongly
negated, but their definitions follow declaration order and constraints cannot
consume them. These are language-bias search policies, not Clingo restrictions.
The anonymous variable `_` is accepted in positive body atoms and positive atom
conditions.

For a sum that must count repeated values at different positions, retain the
position in its tuple: `#sum{X,P:d(P,X)}` rather than `#sum{X:d(P,X)}`.

Aggregates can still cause infinite grounding when their conditions do not
provide a finite grounding domain.

## Comparison and arithmetic

Arithmetic and comparisons are exact `#modeb` templates:

```prolog
#modeb(1,var(numeric)+var(numeric)=var(numeric)).
#modeb(2,var(numeric)>=var(numeric)).
#modeb(1,(var(numeric,input)+1)*var(numeric,input)
         <= |var(numeric,input)-2|).
#modeb(1,1<var(numeric)<var(numeric)<10).
#modeb(1,var(numeric)=1..9).
```

They accept all Clingo arithmetic terms—`+`, `-`, `*`, `/`, `\`, `**`, `&`,
`?`, `^`, unary `-`, `~`, absolute value and intervals—and all six comparison
operators, including chained comparisons. `var(TYPE)` may omit its direction
inside a relation. Gentians infers a forward `expression = variable`
assignment, and bounded relations may produce several variables when Clingo
proves them safe. Compatible direction-implicit `var+var=var` and
`var-var=var` declarations compile into one canonical additive family with
combined recall, avoiding equivalent encodings before grounding. Explicitly
directed relations stay independent and are also checked by Clingo. External
`@function(...)` calls are rejected because task files do not carry a
host-language grounding context; ordinary symbolic function terms are valid.

Each mode permits only the complete expression it declares, keeping the space
finite, apart from that documented additive-family canonicalization. Numeric
relations enter `ArithmeticSystem`: linear systems are canonicalized
algebraically while nonlinear, bitwise and interval terms remain structurally
exact.

## Predicate invention

Declare an invented predicate once with `#invent(BODY_RECALL, ATOM_TEMPLATE)`.
It is generated in rule heads with recall 1 and in positive rule bodies with the
declared recall. Invented definitions are ordered by declaration and may depend
only on earlier invented predicates, preventing recursive invention cycles.

```prolog
#modeh(1,target(var(person,input),var(person,output))).
#modeb(1,father(var(person,input),var(person,output))).
#modeb(1,mother(var(person,input),var(person,output))).
#invent(2,target_1(var(person,input),var(person,output))).
```

Here `target_1/2` is learned in rule heads and may occur twice in rule bodies.

## Examples

Positive and negative examples use:

```
#pos({included}, {excluded}).
#neg({included}, {excluded}).
```

`included` and `excluded` can be empty, a single atom, or a conjunction of
atoms:

```
#pos({odd(1), odd(3), even(2)}, {}).
#neg({even(3)}, {}).
```

An example can optionally include a contextual ASP program as its third
argument:

```
#pos({target(a)}, {}, {seed(a). reachable(X) :- seed(X).}).
```

The context is active only while evaluating examples with that exact context.
Contextual facts, rules, constraints, choices, disjunctions, and aggregates are
supported. Global directives and weak constraints are rejected because they
cannot be isolated by the per-context ASP selector.

Dependency closure currently recognizes providers in the background or the
candidate hypothesis, not predicates supplied only by an example context. The
resulting learnability gap is documented as
[pending](language-bias.md#pending-predicates-provided-only-by-example-contexts).

## Retired directives

`#bias`, `#metarule`, `#predicate`, `#modem`, `#modeedge`, and `#edge` have been
removed and now raise explicit task errors. `#modeagg`, `#modearith` and
`#modecmp` are retired as well; textual aliases such as `add`, `lt`, or `geq` are
not parsed into operators. Modes and `#invent` remain supported. See
[the language contract and migration notes](language-bias.md#removed-meta-programming-directives).
