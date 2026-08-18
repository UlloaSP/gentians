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

For example if you want to run the hamming task, you can use
```python
from gentians import Arguments, main

main(Arguments(
    filename="benchmarks/gentians/hamming_0.txt", # Task file to parse.
    max_depth=3,                                 # Max literals in each rule.
    max_variables=4,                             # Max variables allowed in one rule.
))
```
where `filename` specifies the task file, `max_depth` sets the maximum length of a clause (number of literals), and `max_variables` sets the maximum number of variables in a rule.

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
size `min(max_program_clauses, hypothesis_space_size)` and evaluates its possible
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
```
#modeh(recall, atom, arity).
```
define an atom `atom` with arity `arity` that can appear at most once in the head.
For example, with `#modeh(1,a,2)` you may obtain `a(X,Y)` in the head.

For positive body literals
```
#modeb(recall, atom, arity, positive).
```
while for negative body literals
```
#modeb(recall, atom, arity, negative).
```
with the same syntax as for head atoms.
Here, `positive` and `negative` are reserved keywords so they should be written as they are.
For example, with `#modeb(1, a, 2, positive)` you may obtain `a(X,Y)` in the body while with `#modeb(1, a, 2, negative)` you may also obtain not `a(X,Y)`.

Argument directions are optional:
```
#modeh(1,target,2,(+,-)).
#modeb(1,edge,2,positive,(+,-)).
```
`+` is an input variable, `-` an output variable, and `?` unrestricted. Body
inputs must be reachable from head inputs through outputs of positive body
literals; every head output must be produced by one. Negative modes cannot
declare outputs. Gentians currently generates variables only, so constant (`#`)
mode arguments are not supported.

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

## Automatic Language Bias
You can leave the solver discovering missing language bias automatically.
This scans positive and negative examples and background knowledge and extracts the signature for each observed atom.
If no `#modeh` and no `#modeb` are provided, it generates both head and body bias.
If `#modeh` is provided but `#modeb` is missing, it keeps the explicit head bias and generates only body bias.
If `#modeb` is provided, it does not generate head bias, because the task may be learning constraints.
Generated bias assumes a closed world over the input file: a signature is generated only if it appears in background knowledge or examples.
Generated body bias always includes the positive mode for observed atoms and includes the negative mode only when that atom appears negated or in an excluded example.
If you also declare aggregates, comparison operators, or arithmetic operators, these will be kept.

Example: suppose we have in the program
```
a:- b.
#pos({f(1)},{f(1,a)}).
```
and no explicit language bias. This translates into:
```
#modeh(1, a, 0).
#modeh(1, f, 1).
#modeh(1, f, 2).
#modeh(1, b, 0).
#modeb(1, a, 0, positive).
#modeb(1, f, 1, positive).
#modeb(1, f, 2, positive).
#modeb(1, f, 2, negative).
#modeb(1, b, 0, positive).
```

Currently, pay attention when using this together with aggregates, since you may encounter an infinite loop while grounding the program.

## Predicate Invention
Declare an invented predicate once with `#invent(BODY_RECALL, NAME, ARITY)`.
It is generated in rule heads with recall 1 and in positive rule bodies with the
declared recall. Invented definitions are ordered by declaration and may depend
only on earlier invented predicates, preventing recursive invention cycles.

Example:
```prolog
#modeh(1,target,2).
#modeb(1,father,2,positive).
#modeb(1,mother,2,positive).
#invent(2,target_1,2).
```

Here `target_1/2` is learned in rule heads and may occur twice in rule bodies.

## Main Available Options

Here we list only the main ones:
- `max_variables`: maximum number of variables to consider in a rule. Default 3.
- `max_depth`: maximum number of literals in a rule (number of atoms in the head + number of literals in the body). Default 3.
- `disjunctive_head_length`: maximum number of atoms in disjunctive head. Default 1.
- `max_candidate_clauses`: maximum number of candidate clauses to generate. `0` means all.
- `max_program_clauses`: maximum number of clauses in one candidate program. Default 6.
- `filename`: task file to parse.
- `iterations_genetic`: number of genetic generations. `0` means unlimited and is the default.
- `fitness.name`: `cov_subprograms_mean`, `cov_subprograms_max`, or `cov_program`.
- `ProgramGenerator` is mandatory infrastructure: every initialization,
  mutation, and crossover returns an already dependency-closed valid program.
- `admission`: `reject_duplicates` or `allow_duplicates`.

