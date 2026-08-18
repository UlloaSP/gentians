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

GENTIANS always searches the generated hypothesis space. The mandatory
`ProgramGenerator` constructs every initial, mutated, and crossed program while preserving its
size, membership, and dependency invariants.

```python
arguments = Arguments(
    filename="benchmarks/gentians/coin.txt",
    iterations_genetic=0,
    fitness={
        "name": "cov_subprograms_mean",
        "max_as": 0,
        "clingo_arguments": [],
    },
)
main(arguments)
```

`fitness.name` is one of `cov_subprograms_mean`, `cov_subprograms_max`,
`cov_program`, or `trigram_cov`. `trigram_cov` evaluates the whole program like
`cov_program`, but scores balanced accuracy linearly from 0 to 1. Subprogram
fitness keeps every evolutionary individual at the fixed
size `min(#maxpl, hypothesis_space_size)` and evaluates its possible
subprograms. Program fitness evaluates the whole individual and permits variable
sizes. Every fitness evaluation creates a fresh Clingo control, grounds its
candidate program, then solves it. Whole-program fitness uses brave consequences.

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
uv run python benchmarks/run_experiments.py cov_subprograms_mean
uv run python benchmarks/run_experiments.py cov_subprograms_mean --force
uv run python benchmarks/run_experiments.py  # all configured experiments
```

An existing matching experiment is skipped. A changed config is marked stale and
requires `--force`, preventing accidental comparison with obsolete results.

If instead you prefer to define your own program and domain, keep reading.

## Language Bias Definition
You can define the language bias (i.e., atoms and literals that can appear in the head and body of rules) with the following syntax.
For head atoms
```prolog
#modeh(recall, atom_template).
```
For example, `#modeh(1,a(var(node,input),var(node,output))).` permits
`a(X,Y)` in a rule head.

For positive body literals
```prolog
#modeb(recall, atom_template, positive).
```
while for negative body literals
```prolog
#modeb(recall, atom_template, negative).
```
Every non-nullary argument is explicitly either a directed typed variable or a
typed constant placeholder:

```prolog
#constant(colour,red).
#constant(colour,green).

#modeh(1,target(var(node,input))).
#modeb(1,edge(var(node,input),var(node,output)),positive).
#modeb(1,colour(var(node,input),const(colour)),positive).
```

Variables require exactly one direction: `input`, `output`, or `any`.
`input` must already be bound, `output` is produced by a positive body literal,
and `any` opts out of data-flow restrictions. Constants have no direction and
must be enumerated by `#constant(TYPE, VALUE)`. Negative modes cannot contain
output variables. Types and directions are task declarations; Gentians does
not infer normal modes from background knowledge or examples.

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

where `aggregation_function` is the aggregation function (`sum` or `count`, for example) and `aggregation_atom` is a term of the form `name/arity`, representing the atom aggregating on.
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
You can define comparison operators and arithmetic operators in the language bias with:
```
#modecmp(recall, operator).
#modearith(recall, operator).
```

The following comparison operators are considered: `lt` (<), `leq` (=<), `gt` (>), `geq` (>=), `eq` (=), and `neq` (!=).
The following arithmetic operators are considered: `add` (+), `sub` (-), `mul` (*), `div` (/), `mod` (`\`), and `abs` (absolute value).
Use recall to allow more occurrences of the same operator in one rule.

Examples:
```prolog
#modecmp(1, neq).
#modecmp(2, geq).
#modearith(1, add).
#modearith(1, mul).
#modearith(1, sub).
```

## Predicate Invention
Declare an invented predicate once with `#invent(BODY_RECALL, ATOM_TEMPLATE)`.
It is generated in rule heads with recall 1 and in positive rule bodies with the
declared recall. Invented definitions are ordered by declaration and may depend
only on earlier invented predicates, preventing recursive invention cycles.

Example:
```prolog
#modeh(1,target(var(person,any),var(person,any))).
#modeb(1,father(var(person,any),var(person,any)),positive).
#modeb(1,mother(var(person,any),var(person,any)),positive).
#invent(2,target_1(var(person,any),var(person,any))).
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
- `fitness.name`: `cov_subprograms_mean`, `cov_subprograms_max`, or `cov_program`.
- `ProgramGenerator` is mandatory infrastructure: every initialization,
  mutation, and crossover returns an already dependency-closed valid program.
