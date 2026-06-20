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
    aggregates=["sum(d/2)", "count(d/2)"],       # Aggregates allowed in generated rules.
    comparison_operators=["neq"],                # Comparison operators allowed in bodies.
    verbosity=2,                                 # 0 quiet, 1 sampled clauses, 2 placements.
    max_variables=4,                             # Max variables allowed in one rule.
    unbalanced_aggregates=True,                  # Allow unbalanced aggregate variables.
))
```
where `filename` specifies the task file, `max_depth` sets the maximum length of a clause (number of literals), `aggregates` lists the allowed aggregates, in this case `#sum` over `d/2` and `#count` over `d/2`, `comparison_operators` lists allowed comparison operators, in this case `!=` (`neq`), `verbosity` sets the verbosity level, `max_variables` sets the maximum number of variables in a rule, and `unbalanced_aggregates` allows unbalanced aggregates.

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

Some examples are:
```
#pos({odd(1), odd(3), even(2)}, {}).
#neg({even(3)}, {}).
```

## Aggregates in Language Bias
You can define aggregates in the language bias via `Arguments(aggregates=...)` (not directly in the source file, by now).

For one aggregation atom you can use:
`"aggregation_function(aggregation_atom)"`
where `aggregation_function` is the aggregation function (`sum` or `count`, for example) and `aggregation_atom` is a term of the form `name/arity`, representing the atom aggregating on.
If you want to aggregate over multiple atoms, you can use multiple aggregation atoms separated by commas.
You can pass multiple aggregates.

Examples:
```python
# defines a `#sum` aggregate over `x/3`
Arguments(aggregates=["sum(x/3)"])
# defines a `#sum` aggregate over `x/3` and `size/1`
Arguments(aggregates=["sum(x/3,size/1)"])
# defines a `#sum` aggregate over `p/2` and a `#count` aggregate also over `p/2`
Arguments(aggregates=["sum(p/2)", "count(p/2)"])
# defines a `#sum` aggregate over `p/2` and a #count aggregate over `q/2`
Arguments(aggregates=["sum(p/2)", "count(q/2)"])
```

Pay attention with aggregates since you may encounter an infinite grounding, so the program will never terminate.

## Comparison and Arithmetic Operators in Language Bias
You can define comparison operators and arithmetic operators in the language bias via `Arguments(comparison_operators=...)` and `Arguments(arithmetic_operators=...)`, respectively (not directly in the source file, by now).

The following comparison operators are considered: `lt` (<), `leq` (=<), `gt` (>), `geq` (>=), `eq` (=), and `neq` (!=).
The following arithmetic operators are considered: `add` (+), `sub` (-), `mul` (*), `div` (/), and `abs` (absolute value).
You can pass multiple comparison and arithmetic.

Examples:
```python
Arguments(comparison_operators=["neq"])
Arguments(comparison_operators=["neq", "geq"])
Arguments(arithmetic_operators=["add"])
Arguments(arithmetic_operators=["add", "mul", "sub"])
```

## Automatic Language Bias
You can leave the solver discovering the language bias automatically.
This scans positive and negative examples and background knowledge and extracts the signature for each atom in the examples and each head and body literal in background knowledge.
Then, it adds each signature as mode bias for the head and for the body.
You can activate this with `Arguments(automatic_language_bias=n)` where `n` is a number: if it is positive, indicates the recall for each literal (i.e., all literals will have the same recall); if it is negative, its absolute value indicates the recall for each literal and also states that these can be negated literals.
Note that `automatic_language_bias` ignores the language bias defined in the program file (i.e., `#modeb` and `#modeh`).
If you also use `aggregates`, `comparison_operators`, or `arithmetic_operators`, these will be kept.

Example: suppose we have in the program
```
a:- b.
#pos({f(1)},{f(1,a)}).
```
`automatic_language_bias=1` translates into:
```
#modeh(1, a, 0).
#modeh(1, f, 1).
#modeh(1, f, 2).
#modeh(1, b, 0).
#modeb(1, a, 0, positive).
#modeb(1, f, 1, positive).
#modeb(1, f, 2, positive).
#modeb(1, b, 0, positive).
```
If `automatic_language_bias=-1` is used, the `#modeb` above will have `negative` instead of `positive` as fourth argument.

Currently, pay attention when using this together with aggregates, since you may encounter an infinite loop while grounding the program.

## Predicate Invention
You can enable predicate invention with `Arguments(predicate_invention=N)` where `N` is the number of predicates to invent.
For each `i` in `{1, ..., N}` it generates a predicate `__inv_i__` with arity 1 and 2 to consider in the head and body of clauses.

Example:
```python
Arguments(predicate_invention=1)
```

## Main Available Options

Here we list only the main ones:
- `max_variables`: maximum number of variables to consider in a rule. Default 3.
- `max_depth`: maximum number of literals in a rule (number of atoms in the head + number of literals in the body). Default 3.
- `disjunctive_head_length`: maximum number of atoms in disjunctive head. Default 1.
- `clauses_to_sample`: number of clauses to sample. Default 1000.
- `unbalanced_aggregates`: enable unbalanced aggregates. Default false.
- `filename`: task file to parse.
- `comparison_operators`: enable comparison operators. Values: `lt`,`leq`,`gt`,`geq`,`eq`,`neq`. Repeat an operator to increase recall. Example: `["lt", "lt"]`.
- `arithmetic_operators`: enable arithmetic operators. Values: `add`,`sub`,`mul`,`div`,`abs`. Repeat an operator to increase recall. Example: `["add", "add"]`.
- `aggregates`: enable aggregates. Use atoms like `sum(a/1)`. Multiple atoms can be separated by a comma, such as `sum(a/1,b/1)`.
