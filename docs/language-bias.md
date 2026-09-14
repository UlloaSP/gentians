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
| `#minhl(N).` | At least `N` atoms in a head built by `#modeha` or `#modehd`. |
| `#maxhl(N).` | At most `N` atoms in one clause head. `0` permits only headless clauses. |
| `#maxpl(N).` | At most `N` clauses in one candidate hypothesis. |

`#maxv` and `#maxhl` follow ILASP terminology. `#maxpl` uses `p` for
program because `h` already means hypothesis/head in the surrounding language.

## Grammar

The executable front-end is split by responsibility. `parse_file()` performs
UTF-8 I/O and `parse_text()` orchestrates parsing. `gentians.language.lexer`
frames complete top-level statements while respecting strings, comments,
nested delimiters, ranges, and annotations. Declaration parsing lives in
`directives`, `declarations`, and `modes`. These modules build the
`InductiveTask` IR in `gentians.language.ir`: types, directions, recalls,
labels, and task limits. Generic ASP fragments keep Clingo's AST through
`gentians.language.asp`; Gentians does not define a competing ASP AST.
The complete background is parsed in one Clingo call while preserving original
task line locations. Background and every
example's included atoms, excluded atoms, and context remain as
`clingo.ast.AST` nodes inside `InductiveTask`. Each non-empty example field is
parsed directly; empty fields do not invoke Clingo. Candidate `Clause`
values retain their parsed clause beside their canonical output text. Retained
programs enter controls through
`ProgramBuilder`; rendering AST back to text is limited to diagnostics,
canonical output, and the single batched conversion of generated reified
clauses into Clingo AST nodes. Static analysis traverses those nodes directly.
`TASK_GRAMMAR` records top-level composition and the directive parsers enforce
the productions below.

Every background statement must parse through `clingo.ast`. Task files reject
`#script ... #end.` blocks; embedded host-language code is outside the task
language.

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
  when `#modeha` or `#modehd` is present. Its default is `1`.
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
  the finite recall capacities of `#modeha` and `#modehd`.
- `#maxpl(*).`: a candidate may contain every clause in the finite generated
  clause space.

All four directives may contain `*` when mode recalls still imply finite head
and body capacities. A section containing both an unbounded length and a mode
with recall `*` is invalid because it describes an infinite clause space:

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
finite clause space.

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
largest declared head. The positive-only pruning rule below can exclude the
headless alternative from enumeration without changing the declared syntax.

The optional third component of a head variable is a declaration-local
identity label. Reusing a label forces the corresponding positions to use one
variable. Different labels force different variables. Unlabelled positions
remain free. Labels must use compatible type declarations; their directions
may differ.
An element may carry an exact conditional attachment directly, such as
`#modeh(1,p(var(node,any)):node(var(node,any))).`. That condition is
indivisible from the element. Generated `#modec` conditions may additionally
attach to every element of a normal, disjunctive, choice, or cardinality head.

Every atom and aggregate argument is explicit. Its variables contain a nominal
type and one direction; `var(type)` without a direction is valid only inside a
relation, where the inference rules below apply.

Functions and tuples may nest without a depth limit. Their leaves remain
explicit `var(...)` or `const(...)` placeholders. Variable limits, typing,
directions, labels, safety, and rendering use those leaves in left-to-right
depth-first order. Predicate arity still counts outer arguments, so
`p(f(X,Y))` has arity 1 and two variable placeholders.

```ebnf
head-mode       = "#modeh(1,", head-template, ")." ;
body-mode       = "#modeb(", recall, ",", body-template, ")." ;
body-template   = atom-conditional-template
                | comparison-expression
                | aggregate-template ;
condition-mode  = "#modec(", recall, ",", literal-template, ")." ;
aggregate-head-mode = "#modeha(", [recall, ","], atom-template, ")." ;
disjunctive-head-mode = "#modehd(", [recall, ","], atom-template, ")." ;
head-template   = conditional-template
                | conditional-template, {";", conditional-template}
                | [integer], "{", conditional-template,
                  {";", conditional-template}, "}", [integer] ;
conditional-template = atom-template,
                       [":", literal-template, {",", literal-template}] ;
atom-conditional-template = ["not", whitespace], atom-template,
                            [":", literal-template, {",", literal-template}] ;
literal-template = ["not", whitespace], atom-template | comparison-expression ;
aggregate-template = aggregate-expression, "=", variable-argument ;
aggregate-expression = ("#count" | "#sum" | "#sum+" | "#min" | "#max"),
                       "{", mode-term, {",", mode-term}, ":",
                       atom-template, {",", atom-template}, "}" ;
atom-template   = ["-"], predicate, ["(", mode-term, {",", mode-term}, ")"] ;
mode-term       = variable-argument | constant-argument | function-term | tuple-term ;
function-term   = function, "(", mode-term, {",", mode-term}, ")" ;
tuple-term      = "(", ")"
                | "(", mode-term, ",", [mode-term, {",", mode-term}], ")" ;
variable-argument = "var(", type, ",", direction, [",", label], ")" ;
relation-variable-argument = "var(", type,
                             [",", direction, [",", label]], ")" ;
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

These declarations include `ready.` and `seed(a).` in the clause space. The same
applies to ground disjunctions, choices, and cardinality heads. A variable in a
bodyless head is still rejected unless its head-conditional scope grounds it;
Gentians does not turn nominal types into hidden domain literals. The empty
head and empty body combination is never emitted, so `:-.` cannot be learned.

## Removed meta-programming directives

`#bias`, `#metarule`, `#predicate`, and `#modem` are no longer supported.
The parser rejects each with its source line before compiling background ASP.
There is no compatibility mode or replacement payload in `InductiveTask`.

The language bias still consists of modes, recalls, types, variable labels,
constants, structural limits, and `#invent`. Variable labels always enforce
same-label equality and distinct-label inequality within their declared scope.
Task files cannot inject rules into the clause-enumeration metaprogram.

Second-order predicate templates and their atomic multi-rule bundles have been
removed from generation and hypothesis construction. Each learned clause is now
selected independently, subject to whole-program dependency closure and
`#maxpl`. Choice and disjunctive heads remain single ASP clauses, not bundles.
To migrate an old task, express its permitted clauses with the supported modes
and limits. Arbitrary meta-ASP restrictions have no automatic equivalent;
do not move their contents into background ASP, which has different semantics.
Predicate invention, aggregates, arithmetic, conditionals, strong negation, and
default negation remain supported.

## Aggregate head modes

`#modeha` is the ILASP aggregate-head declaration: each declaration contributes
compatible atoms that Gentians may combine into one choice/cardinality head.
It is distinct from exact body aggregates declared through `#modeb`.

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
be combined, subject to each recall. `#minhl` affects generated combinable
heads; explicit complete `#modeh` declarations remain unchanged.

Aggregate-head atoms support strong negation, typed directions, constants,
functions, tuples, and declaration-local labels. They cannot use default
negation. The normal safety and direction rules apply. `#modec` may attach
conditions independently to every generated element, and those conditions
still consume the clause-wide body budget. Elements of one aggregate head are
one structural component for linkedness, so compatible atoms may use distinct
variables grounded by distinct body literals.

With `#maxhl(*)`, all `#modeha` recalls must be finite. Gentians then derives
the maximum width from their summed recalls. This preserves a finite search
space before grounding.

## Disjunctive head modes

`#modehd` combines declarations exactly like `#modeha`, but emits a plain ASP
disjunction and never a choice or cardinality head:

```prolog
#constant(colour,red).
#constant(colour,blue).
#minhl(2).
#maxhl(2).
#modehd(2,painted(var(node,input),const(colour))).
```

This can generate `painted(V0,red);painted(V0,blue)`. Recall counts uses of a
declaration across constant expansions. A disjunction has at least two
elements; `#minhl`, `#maxhl`, safety, labels, `#modec`, and the finite-recall
requirement for `#maxhl(*)` otherwise behave as for `#modeha`. Keeping
`#modehd` separate makes the object-level ASP semantics explicit: recall never
implies disjunction or choice syntax.

## Conditional literals

`#modec` declares atoms or exact comparisons that may occur after the colon of
a conditional literal:

```prolog
#maxbl(3).
#modeh(1,target(var(node,input))).
#modeb(1,base(var(node,any))).
#modec(1,node(var(node,any))).
#modec(1,not blocked(var(node,input))).
#modec(1,var(numeric,input)<3).
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

An exact attachment may instead be written in `#modeh` or `#modeb`:

```prolog
#modeh(1,target(var(node,any)):node(var(node,any))).
#modeb(1,candidate(var(numeric,any)):var(numeric,input)<3).
```

Unlike a generated `#modec` attachment, it is never optional and stays on that
specific head element or body conclusion. Optional `#modec` conditions can be
added on top while the same clause-wide recall and `#maxbl` accounting remain
in force.

Atomic conditions support default negation, strong negation, constants, nested
functions, and tuples using the same grammar as `#modeb`. Exact comparison
conditions support the comparison-expression grammar of `#modeb`. Declare positive
and default-negated atom forms separately. Labels are declaration-local by
default and may appear in `#modeb` and `#modec` as well as head declarations.

ASP scoping determines conditional-variable safety. A variable used only in a
conditional is local. One of its positive atomic conditions must ground it;
the conditional conclusion does not do so in either a body or head element.
Every other conditional variable is
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

Aggregate condition variables are local or supplied by surrounding terms; the
aggregate result is `output`. Aggregates, arithmetic, and comparisons need no
separate directive: body modes use their exact Clingo syntax.

An aggregate body mode declares one nonempty aggregate element, one or more
positive atomic conditions, and one equality result:

```prolog
#modeb(1,#sum{var(numeric,any,value):
                p(var(partition,any,group),var(numeric,any,value))}=
         var(numeric,output,result)).
```

The tuple is part of the template. Listing every condition variable expresses
a full tuple; listing fewer variables expresses a projection. The retired
`#modeagg` directive's `balanced` and `unbalanced` expansion is not performed.
Declare each desired tuple shape directly. Recall belongs to that complete
shape and is not shared implicitly with other aggregate declarations.

Labels connect repeated placeholders within the aggregate. Tuple and condition
variables require `input` or `any`; the result must be an `output` variable.
For `#count`, `#sum`, and `#sum+`, that result has type `numeric`. Strong
negation is supported in condition atoms; default negation, multiple aggregate
elements, non-atomic conditions, range guards, and result-free aggregates are
not part of the aggregate mode language. A top-level aggregate tuple or
condition term may contain at most one variable placeholder.

Arithmetic and comparisons use the relation grammar:

```ebnf
relation-mode = "#modeb(", recall, ",", comparison-expression, ")." ;
comparison-expression = arithmetic-term, comparison-guard,
                        { comparison-guard } ;
comparison-guard = ("=" | "!=" | "<" | "<=" | ">" | ">="),
                   arithmetic-term ;
```

Here `arithmetic-term` is a Clingo arithmetic term whose placeholder leaves use
`relation-variable-argument` or `constant-argument` from the grammar above.

Gentians accepts every arithmetic term represented by Clingo's AST: nested
`+`, `-`, `*`, `/`, `\`, `**`, bitwise `&`, `?`, `^`, unary minus, bitwise
complement `~`, absolute value `|T|`, intervals `L..U`, integers, fixed terms,
functions, `var(...)`, and `const(...)`. Comparisons may be chained and may use
any of Clingo's six comparison operators:

```prolog
#modeb(1,var(numeric)+var(numeric)=var(numeric)).
#modeb(1,(var(numeric,input)+1)*var(numeric,input)
         <= |var(numeric,input)-2|).
#modeb(1,1<var(numeric)<var(numeric)<5).
#modeb(1,var(numeric)=1..9).
```

External `@function(...)` calls are rejected because task files cannot provide
the host-language grounding context they require. Ordinary symbolic function
terms remain supported.

Each declaration is one finite relation template; Gentians does not synthesize
arbitrary-depth expressions from the operators occurring in it. Recall limits
uses of that complete template. Compatible direction-implicit three-variable
addition and subtraction assignments are the one exception: Gentians compiles
them into a single canonical additive family and combines their recalls. This
removes alternative linear encodings before grounding. Explicitly directed
relations remain separate exact templates.

Inside a relation, `var(TYPE)` is shorthand for an unspecified direction.
Gentians infers the common forward assignment
`expression = var(TYPE)` as inputs on the expression and an output on the bare
variable. If Clingo proves that the whole relation is safe without prior
bindings, every unspecified variable is an output; this covers bounded chains
such as `1<X<Y<5` and interval assignments such as `X=1..9`. Otherwise an
unspecified variable must already be safe when the relation is selected.
Explicit `input`, `output`, and `any` remain available. A relation may produce
several variables, with any comparison operator, exactly when a synthetic
Clingo grounding proves those declared outputs safe. Default-negated
relations cannot produce variables.

For the anonymous forms `var(numeric)+var(numeric)=var(numeric)` and
`var(numeric)-var(numeric)=var(numeric)`, those inferred directions also mark
the declarations as members of the canonical additive family. Addition can
represent subtraction by orienting the same linear equality, so selecting both
forms does not create two independent operator alphabets. State directions
explicitly when their particular forward orientation is part of the language
bias rather than shorthand for the additive family.

Clingo is the authority for parsing and output safety; Gentians does not map
textual names such as `add` or `lt` to operators. `#modearith` and `#modecmp`
are retired and rejected explicitly.

After enumeration, every non-negated numeric relation is owned by its connected
`ArithmeticSystem`. Linear equalities and inequalities whose constant terms
cancel use canonical coefficient rows, including nested addition,
subtraction, unary minus, and multiplication by an integer.
Nonlinear, bitwise, interval, and other Clingo terms retain an exact structural
representation. Canonicalization never changes an operator into an
approximation. Emitted rules contain only the final system representation.

Readiness is a clause-wide fixed point, not textual body order. A zero-input
positive mode can seed a constraint, its outputs can make another literal
ready, and so on. Bundled atom modes use explicit `input`/`output` directions;
relation modes may use the safe inference described above. `any` remains
available only when a task intentionally opts out of mode-directed pruning.

Types are nominal task declarations. They constrain which positions may share
a generated variable; they do not add domain literals to learned rules. The
reserved type name `any` is invalid because every mode type must be explicit.
Aggregate tuple, condition, and result placeholders declare their types
directly. The integer `1` may be both a node identifier and a numeric value
without merging those nominal types.

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

### Positive-only constraint pruning

Pure integrity constraints remove stable models; they cannot create a brave
positive witness. Without negative examples, they are therefore optional in a
legal hypothesis that already has headed clauses. Positive examples may include
excluded atoms: their satisfying witness remains when constraints are removed.

Absence of negatives alone does **not** permit deleting every headless candidate.
Gentians requires nonempty hypotheses. A constraint-only program can be the only
solution when the background already covers the positives and all learnable
headed programs violate them.

Both exhaustive and incremental clause generation apply a conservative static test.
Early pruning activates only when:

- There is at least one positive example and no negative examples.
- The task permits a headed mode and `#maxhl` is not zero.
- The background contains ordinary ASP rules
  rather than directives such as `#const` or `#external`.
- Predicate extraction understands all background heads. Pooled
  symbolic heads such as `q(a;b).` and theory heads disable this optimization.
- At least one included positive atom has a signed predicate absent from every
  head in the background and in that example's own ordinary-rule context, whose
  heads must also be understood by predicate extraction.

This missing-predicate test proves that every perfect hypothesis must learn a
head. It is a sufficient condition, not a coverage solver or an approximation to
stable-model semantics. Definitions are overapproximated, so uncertain cases keep
constraints. Strong negation retains its sign, and contexts are inspected
independently. An absent predicate in one context cannot be supplied by another.

When the test succeeds, a fact enables an ASP constraint in
`clauses/metaprogram/core/constraints.lp`, excluding headless clause models
before decoding and canonicalization. Background and context constraints are
never removed.

Constraint-only languages, tasks without positives, and cases
where this proof fails retain their ordinary candidate space. The existing
hypothesis-construction normalization remains necessary for supplied
`ClauseSpace` values and cases not covered by the early proof. It removes optional
pure constraints only when a nonempty legal program remains.

This is pruning relative to brave coverage of the observed task, not a claim of
equivalence on unseen examples. It does not prove that all declared headed clauses
are constructible or that a solution exists. It adds no coverage solves.

### Execution options

These limits do not belong in `Arguments`. Options such as random seed,
population size, evolutionary operators, Clingo arguments, and enumeration
strategy remain runtime configuration because they change execution rather than
the legal hypothesis language.

The default `algorithm="steady_state"` enumerates the finite clause space after
pruning. `algorithm="incremental"` grounds the clause metaprogram once and consumes
bounded batches in increasing body budget, including attached conditions. It uses
one resumable solve per size. All legal sizes remain available; this preference
does not change the language. The generator pauses between batches and closes
when search finishes or fails. Exhaustion preserves the complete space if it fits
in the archive. After archive overflow, a new seeded pass can revisit discarded
clauses. This changes search order, not clause legality.

The `incremental.batch_size` budget counts models before theta reduction and
canonicalization. `incremental.archive_size` bounds the number of distinct raw
clauses retained across batches, before hypothesis dependency pruning. Providers
arriving later can therefore make earlier clauses constructible. All prepared
clauses are active while this archive contains every visited clause.

After overflow, the working space combines the bounded archive, fresh batch and
elite hypotheses with their providers. An active subset contains closed programs.
Providers and consumers outside the archive can still fail to meet; bounded
search does not guarantee discovery of every legal solution. These runtime limits
do not replace `#maxpl` and are not a byte limit on process memory. Whole-program
coverage uses the normal solver.


After enumeration exhaustion, incremental restarts a stalled population when
the prepared space contains learned clauses with heads and the champion has not
improved for 100 generations. It preserves the champion and generates remaining
hypotheses through `HypothesisGenerator`. Constraint-only spaces do not restart.

In constraint-only spaces with positive examples, incremental makes up to 16
extra proposals during initialization and batch renewal. Proposals extend the
best complete candidate with new clauses, or replace a clause at `#maxpl`.
`HypothesisGenerator` enforces legality and the evaluator evaluates whole-program
semantics. These fixed search policies do not alter the allowed language or
assume additive clause coverage.
