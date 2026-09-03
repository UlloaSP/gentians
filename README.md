# GENTIANS: GENeTic algorithm for Inductive learning of ANswer Set programs.

GENTIANS is a tool to learn answer set programs from examples.
It also supports aggregates, comparison, and arithmetic operators.

## Installation
This project uses [uv](https://docs.astral.sh/uv/) for dependency management.
Install the project and its dependencies with:
```
uv sync
```

Run Python code inside the managed environment with:
```
uv run python your_script.py
```

Development checks:
```
uv run ruff check gentians
uv run ty check
uv run pytest
```

## Usage

Provide a file with background knowledge, positive and negative examples, and the language bias definition.
Benchmark tasks live in `benchmarks/gentians/` as plain text files.

For example, the task file owns its structural language bias:

```prolog
#maxv(4).
#maxbl(3).
#maxhl(1).
#maxpl(6).
```

Run it with:

```python
from gentians import Arguments, main

main(Arguments(
    filename="benchmarks/gentians/hamming_0.txt", # Task file to parse.
))
```

See [`docs/language-bias.md`](docs/language-bias.md) for syntax and `*`
semantics.

### Search configuration

GENTIANS searches candidate hypotheses built from a generated `RuleSpace`.
`gentians.language` owns task I/O, lexical framing, parsing, ASP syntax helpers,
and the typed `InductiveTask` IR. Standard ASP stays as Clingo AST nodes and
enters controls through `ProgramBuilder`. Candidate `RuleEntry` values retain
their AST beside canonical output text. `gentians.clauses` compiles task IR
into candidate clauses.
Clingo validates background ASP. Task files do not accept `#script` blocks.
The mandatory
`HypothesisGenerator` in `gentians.hypotheses` is plumbing used by evolutionary
strategies to preserve size, membership, bundle, and dependency invariants.

```python
arguments = Arguments(
    filename="benchmarks/gentians/coin.txt",
    iterations_genetic=0,
    fitness={
        "name": "cov_program",
        "clingo_arguments": [],
    },
)
main(arguments)
```

`fitness.name` is `cov_program` or `cov_balanced`. `cov_balanced` evaluates the
whole program like `cov_program`, but scores balanced accuracy linearly from 0
to 1. Evolutionary individuals may have variable sizes. Every fitness evaluation
creates a fresh Clingo control, grounds its candidate program, then solves it.
Whole-program fitness uses brave consequences.

Mutation defaults to `random_group`. `structural_neighbor` remains available as
an alternative that replaces rules with others sharing the same head:

```python
mutation={
    "name": "structural_neighbor",
    "probability": 0.9,
    "random_jump_probability": 0.1,
}
```

`random_jump_probability` preserves global exploration by allowing replacement
with a rule that has a different head.

Benchmark output records hypothesis generation, genetic generations, elapsed
search time, fitness evaluations, operator metrics, and Clingo phases.
`benchmarks/profile_baseline.py --cprofile` also writes one `.prof` per run.

### Reproducible experiment profiles

Edit `benchmarks/experiments.toml` to define datasets, run count, timeout, common
overrides, and named experiments. Results are isolated in `.benchmarks/<id>` and
indexed by `.benchmarks/experiments.json` for multi-experiment comparison.

```powershell
uv run python benchmarks/run_experiments.py --list
uv run python benchmarks/run_experiments.py cov_program_random_group_pop10_mut09
uv run python benchmarks/run_experiments.py cov_program_random_group_pop10_mut09 --force
uv run python benchmarks/run_experiments.py  # all configured experiments
```

An existing matching experiment is skipped. A changed config is marked stale and
requires `--force`, preventing accidental comparison with obsolete results.

If instead you prefer to define your own program and domain, keep reading.

## Language Bias Definition
You can define the language bias (i.e., atoms and literals that can appear in the head and body of rules) with the following syntax.
Each head declaration describes one complete allowed head:
```prolog
#modeh(1, head_template).
```
The template may be a normal atom, a disjunction, a choice, or a bounded
cardinality head:

```prolog
#modeh(1,a(var(node,input))).
#modeh(1,a(var(node,input,x));b(var(node,input,x))).
#modeh(1,{a(var(node,input,x));b(var(node,input,x))}).
#modeh(1,1 {a(var(node,input,x));b(var(node,input,x))} 1).
#modeh(1,-rejected(var(node,input))).
```

Separate declarations are alternatives and are never combined implicitly.
Head recall is therefore always `1`. The optional third `var` argument is a
head-local identity label: equal labels denote the same generated variable;
different labels denote different variables. An omitted label leaves that
identity unconstrained. `#maxhl` limits the number of atoms in one declared
head, not a later combination of declarations. Exact ASP conditions may be
written on individual elements; `#modec` additionally generates optional
conditions.

Safe empty bodies are learnable. Ground normal heads, disjunctions, choices,
and cardinality heads therefore produce facts; a variable head without a safe
source remains rejected, and the empty constraint `:-.` is never generated.

`#bias("...").` injects explicit ASP rules and constraints into the clause
generator. Bias rules can derive task-specific metarule predicates from
`selected/3`, `var_at/4`, `mode/5`, `predicate_symbol/3`, and the other reified
mode relations. Derived names use the reserved `bias_` namespace; weak
constraints and optimization directives are rejected. Once
any `#bias` is present, head variable labels are metadata only: equality or
inequality must be stated explicitly by a bias constraint over
`head_arg_label/4` and `var_at/4`. Without `#bias`, labels keep their default
identity semantics. See [the language-bias reference](docs/language-bias.md)
for the complete contract and examples.

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
local must be grounded by one of its positive atomic conditions; neither a
body nor a head conclusion grounds it. Global variables must be safe outside
the conditional.
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

Variables require exactly one direction: `input`, `output`, or `any`.
`input` must already be bound, `output` is produced by a positive body literal,
and `any` opts out of data-flow restrictions. Constants have no direction and
must be enumerated by `#constant(TYPE, VALUE)`. Modes containing `not` cannot
contain output variables. Types and directions are task declarations; Gentians
does not infer normal modes from background knowledge or examples.

Mode terms may contain nested functions and tuples. Every leaf stays explicit:
`var(...)` for a generated variable or `const(...)` for a declared ground
value. Predicate arity counts outer arguments; variable limits and directions
apply to nested placeholders.

## Examples definition
Positive examples must follow the syntax
```
#pos({included}, {excluded}).
```
while negative examples must follow the syntax
```
#neg({included}, {excluded}).
```
where, in both cases, `included` and `excluded` can be either empty, a single atom, or a conjunction of atoms.

An example can optionally include a contextual ASP program as its third argument:
```
#pos({target(a)}, {}, {seed(a). reachable(X) :- seed(X).}).
```
The context is active only while evaluating examples with that exact context.
Contextual facts, rules, constraints, choices, disjunctions, and aggregates are
supported. Global directives and weak constraints are rejected because they
cannot be isolated by the per-context ASP selector.

Some examples are:
```
#pos({odd(1), odd(3), even(2)}, {}).
#neg({even(3)}, {}).
```

## Aggregates in Language Bias
You can define aggregates in the language bias with:
```
#modeagg(recall, aggregation_function(aggregation_atom), balanced).
#modeagg(recall, aggregation_function(aggregation_atom), unbalanced).
```

where `aggregation_function` is the aggregation function (`sum` or `count`, for example) and `aggregation_atom` is a term of the form `name/arity` or `-name/arity`, representing the atom aggregating on.
If you want to aggregate over multiple atoms, you can use multiple aggregation atoms separated by commas.
The `balanced` option only generates aggregates whose tuple contains all condition variables.
The `unbalanced` option also generates smaller tuples, so it includes both balanced and unbalanced aggregate variants.

Examples:
```prolog
#modeagg(1, sum(x/3), balanced).
#modeagg(1, sum(x/3,size/1), balanced).
#modeagg(1, sum(p/2), unbalanced).
#modeagg(1, count(p/2), unbalanced).
```

Pay attention with aggregates since you may encounter an infinite grounding, so the program will never terminate.

## Comparison and Arithmetic Operators in Language Bias
Arithmetic and comparison syntax has one declaration:
```
#modearith(recall, operator).
#modearith(recall, relation_template).
```

The following comparison operators are considered: `lt` (<), `leq` (=<), `gt` (>), `geq` (>=), `eq` (=), and `neq` (!=).
The following arithmetic operators are considered: `add` (+), `sub` (-), `mul` (*), `div` (/), `mod` (`\`), and `abs` (absolute value).
Use recall to allow more occurrences of the same operator in one rule.
`relation_template` preserves a specific ASP expression instead of generating
an operator family. It supports nested `+`, `-`, `*`, `/`, `\`, `**`, bitwise
`&`, `?`, `^`, and `~`, unary minus, absolute value, functions, constants, and
all six comparison relations:

```prolog
#modearith(1,(var(numeric,input)+1)*var(numeric,input)
             <= var(numeric,input)).
#modearith(1,var(numeric,input)+1=var(numeric,output)).
```

Only equality may declare an output, and then exactly one output leaf is
allowed. `#modecmp` no longer exists; `eq`, `neq`, `lt`, `leq`, `gt`, and
`geq` are operator names of `#modearith`.
Arithmetic is represented as connected systems. Linear rows use primitive
integer coefficients and canonical row reduction, so auxiliaries may disappear
as in `X+X=T,T+T=Y` becoming `4*X-Y=0`. Independent rows remain a system instead
of being incorrectly collapsed into one equation. Multiplication, division,
modulo, absolute value, and comparisons remain exact relations in the same
system. Division and modulo carry an explicit nonzero-divisor condition.
`add` and `sub` contribute to one linear recall budget; an unbounded declaration
keeps that budget unbounded.
Likewise, `lt`/`gt` and `leq`/`geq` share canonical comparison modes with their
recalls combined.
The bias limits source operations. Generated rows and mandatory conditions are
part of their `ArithmeticSystem`; they do not consume extra recall or body slots.
Rules expose only this final system representation, not the source operator
literals used to derive it.

Examples:
```prolog
#modearith(1, neq).
#modearith(2, geq).
#modearith(1, add).
#modearith(1, mul).
#modearith(1, sub).
```

## Second-order metarules

Metarules instantiate predicate variables from explicit typed pools:

```prolog
#metarule(chain,"P(X,Z) :- Q(X,Y),R(Y,Z).").
#predicate(target,path/2).
#predicate(base,edge/2).
#modem(chain(target/2,base/2,base/2)).
```

Predicate variables are ordered by first appearance and their declared arity
must match every occurrence. A quoted metarule may contain several rules; one
instantiation is then an atomic rule bundle during initialization, mutation,
crossover, replacement, and dependency pruning. `#maxv` and `#maxbl` apply to
each rule, while `#maxpl` counts every rule in the bundle.
Use `P()` with a `/0` pool specification for a nullary predicate variable.

## Predicate Invention
Declare an invented predicate once with `#invent(BODY_RECALL, ATOM_TEMPLATE)`.
It is generated in rule heads with recall 1 and in positive rule bodies with the
declared recall. Invented definitions are ordered by declaration and may depend
only on earlier invented predicates, preventing recursive invention cycles.

Example:
```prolog
#modeh(1,target(var(person,input),var(person,output))).
#modeb(1,father(var(person,input),var(person,output))).
#modeb(1,mother(var(person,input),var(person,output))).
#invent(2,target_1(var(person,input),var(person,output))).
```

Here `target_1/2` is learned in rule heads and may occur twice in rule bodies.

## Main Available Options

Here we list only the main ones:

- `#maxv`: maximum distinct variables in one clause. Default 3.
- `#maxbl`: maximum body literals in one clause. Default 3.
- `#maxhl`: maximum head atoms in one clause. Default 1.
- `#maxpl`: maximum clauses in one candidate program. Default 6.
- Any structural limit accepts `*` when remaining mode recalls still make the
  hypothesis space finite.
- `filename`: task file to parse.
- `iterations_genetic`: number of genetic generations. `0` means unlimited and is the default.
- `fitness.name`: `cov_program` or `cov_balanced`.
- `HypothesisGenerator` is mandatory infrastructure: every initialization,
  mutation, and crossover returns an already dependency-closed valid program.
