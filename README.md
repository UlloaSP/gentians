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

GENTIANS searches candidate hypotheses built from a generated `ClauseSpace`.
`gentians.language` owns task I/O, lexical framing, parsing, ASP syntax helpers,
and the typed `InductiveTask` IR. Background, examples, contexts, bias, and
candidate clauses stay as Clingo AST nodes and enter controls through
`ProgramBuilder`. The background is parsed once; only non-empty example fields
invoke Clingo. The static coverage program is retained as AST instead of being
reparsed for every candidate. Candidate `Clause` values retain their AST
beside canonical output text. `gentians.clauses` compiles task IR into candidate
clauses.
Clingo validates background ASP. Task files do not accept `#script` blocks.
The mandatory
`HypothesisGenerator` in `gentians.hypotheses` is plumbing used by evolutionary
strategies to preserve size, membership, and dependency invariants.
`Genome` is the bitset genotype, the rendered ASP hypothesis is its phenotype,
and `Individual` couples one genome to its evaluation and logical birth order.

```python
arguments = Arguments(
    filename="benchmarks/gentians/coin.txt",
    iterations_genetic=0,
    evaluation={
        "scoring": "cov_program",
        "clingo_arguments": [],
    },
    algorithm="incremental",
    incremental={
        "batch_size": 128,
        "epoch_generations": 50,
        "elite_count": 10,
    },
)
main(arguments)
```

`evaluation.scoring` is `cov_program`, which scores whole-program coverage.
Evolutionary individuals record whether they cover every positive example
and avoid every negative example. Replacement has no behavior-specific
tie-break. The benchmark dashboard reports complete, incomplete, consistent,
inconsistent, and perfect candidate rates. Coverage inheritance is enabled by
default. Unresolved coverage queries create and ground a fresh Clingo control;
fully inherited results need no new control. `algorithm="incremental"`
selects `incremental_clause_genetic_search`. Generation grounds once and visits
increasing body budgets, including attached conditions, with a resumable seeded
solve for each size. Each batch consumes at most `incremental.batch_size` models
before pruning and canonicalization. Generation pauses while the GA searches.
Whole-program evaluation uses brave consequences.

Each epoch retains the highest-scoring hypotheses and the champion. A bounded
archive keeps the first `incremental.archive_size` distinct clauses before
hypothesis dependency pruning. This lets providers and consumers from different
batches meet. The working `ClauseSpace` combines the archive, the next batch and
elite programs. When the archive contains every visited clause, all prepared
clauses remain active. Once the finite space is exhausted, search continues on
that complete space without rebuilding indices or clearing caches each epoch.

After exhaustion, a space containing learned clauses with heads can restart a
stalled population after 100 generations without a better champion score. The champion and
its evaluation survive, the other evaluation caches are cleared, and the existing
population strategy fills the remaining slots with closed hypotheses. Every
improvement resets the stagnation counter. Constraint-only spaces do not restart.
Normal, choice and disjunctive heads use the same rule;
whole-program ASP evaluation is unchanged.

For constraint-only spaces with positive examples, incremental tries up to 16
extra proposals during initialization and each batch renewal. It extends the best
complete candidate using new clauses, or replaces a clause at the program-size
limit. Every proposal is a valid hypothesis evaluated as a whole ASP program.
This is a fixed part of incremental search. Historical measurements on
5queens, 4queens and nested large spaces are in the
[constraint-probe report](docs/incremental-crossover-experiment.md).

If the archive overflows, the active mask selects retained programs and random
closed candidates. Exhaustion starts a new seeded enumeration pass so discarded
clauses can return. Each pass grounds once and enumerates increasing body budgets.
This bounded search is neither uniform sampling nor complete hypothesis search.
A supplied `ClauseSpace` bypasses generation. The archive limits clause count,
not bytes: the working space also contains the fresh batch and elite programs,
and Clingo, caches and instrumentation consume additional memory.

Restarted batch sampling and frozen-pool evaluation have been removed.
`algorithm="steady_state"` remains the default and materializes the full clause
space. Both algorithms use the normal evaluator. `#maxpl` still limits complete
hypotheses; unbounded task limits can allow large retained programs.

Mutation adds, replaces or removes a root clause and its dependency block.
Complete programs keep their headed clauses unchanged, except for a configurable
10% attempt to delete a headed block. Incomplete programs can edit headed clauses
or remove and replace constraints. With negatives present, incomplete candidates
replace roots within their role, headed or constraint, and do not append pure
constraints. Constraint replacement does not require structural relaxation.
Without negative examples, construction removes
optional pure constraints whenever a nonempty legal program remains.

Clause generation also prunes headless models before decoding when a static
missing-predicate proof establishes that a positive example needs a learned
head. This applies to exhaustive enumeration and incremental batches. It preserves
constraint-only languages and uncertain cases. Absence of negatives alone is not sufficient to
prune every constraint because hypotheses must remain nonempty. The exact
conditions are documented in [language bias](docs/language-bias.md#positive-only-constraint-pruning).

Mutation classifies its actual input through the cached evaluator when positives
exist, including crossover offspring and homogeneous spaces. Known solutions
remain unchanged. Classification evaluations count toward search cost.
Consistency alone does not freeze headed clauses; tasks without positives do not
freeze them either. The default `set_mix` crossover retains its preference for complete
recipient heads, including its 10% unrestricted escape and fallback.
The separate `completeness` and `structural_neighbor` mutation names have been
removed. Mutation uses `random_group`.
Lexicase selects distinct parents within each mating event. An already evaluated crossover result may still
serve as the base for mutation, and in that case mutation bypasses its probability
gate. Selection and variation still run once per generation.
It does not certify coverage or preserve complete recipient heads. `set_mix` remains the default; a
matched steady-state experiment is prepared in `benchmarks/experiments.toml`.
See [variation policy](docs/variation-policy.md) for guarantees and exceptions.

Historical pool experiments and their measurements remain documented in
[`docs/pool-policy-experiment.md`](docs/pool-policy-experiment.md) and
[`docs/million-clauses-experiment.md`](docs/million-clauses-experiment.md).
Their retired configurations are no longer executable on the current API.
Current standard-task runs are recorded in [the incremental report](docs/incremental-experiment.md).

Complete search algorithms live in `gentians.algorithms` and return a
`SearchResult`. `steady_state_genetic_search` replaces population members after
each offspring. `incremental_clause_genetic_search` uses the same operators while
renewing a bounded working clause space. Its loop lives in
`gentians/algorithms/incremental_clause_genetic.py`; the adjacent modules own
the rest of its lifecycle:

- `incremental_clause_pool.py`: batch enumeration, bounded archive and active clauses.
- `incremental_candidates.py`: evaluation/admission caches, logical age and recoding
  retained programs when the prepared space changes.
- `incremental_population.py`: initialization, refill, renewal, restarts and constraint probes.
- `incremental_offspring.py`: one mating event and evaluation phase attribution.
- `incremental_progress.py`: generation and epoch metrics.
- `search_budget.py`: net-time deadline and best result evaluated within budget.

Evolutionary operators live in `gentians.evolution`; candidate evaluation lives in
`gentians.evaluation` so exact or greedy algorithms can reuse it.

Mutation has one implementation, `random_group`, selected through the existing
mutation factory. Replacement normally preserves the set of signed head
predicate signatures, not the exact head expression or body:

```python
mutation={
    "name": "random_group",
    "probability": 0.9,
    "random_jump_probability": 0.1,
    "complete_generator_removal_probability": 0.1,
}
```

`random_jump_probability` permits a different head on 10% of replacement
attempts. It does not override complete-candidate protection.
`complete_generator_removal_probability` reserves a separate 10% chance to try
deleting a headed dependency block. Its offspring still requires evaluation;
deletion is not proof of redundancy. Both defaults are configurable. If a complete
candidate has no legal constraint edit or allowed deletion, mutation leaves it
unchanged. This restriction can block candidates whose solution requires a headed
replacement. Benchmark timings belong to their recorded source versions.

Constraint-only mutation uses unrestricted random edits
when the active clause space contains only constraints, while preserving the directed
policy in spaces with headed clauses. It permits constraint additions to incomplete
candidates, which can improve negative coverage without recovering positives.
Set it to false to disable this policy. See [the mutation ablation report](docs/mutation-ablation-experiment.md)
for controls, timings and limitations.

Benchmark output records clause generation, genetic generations, elapsed
search time, fitness evaluations, operator metrics, and Clingo phases.
`benchmarks/profile_baseline.py --cprofile` also writes one `.prof` per run.

### Reproducible experiment profiles

Edit `benchmarks/experiments.toml` to define datasets, run count, timeout, common
overrides, and named experiments. Results are isolated in `.benchmarks/experiments/<id>` and
indexed by `.benchmarks/experiments/experiments.json` for multi-experiment comparison.
The entire `.benchmarks/experiments/` directory is ignored by Git and can be
deleted to remove all local results and experiment snapshots. The Vite source
remains outside that directory. Run `uv run python benchmarks/run_experiments.py
--list` to recreate the index without running benchmarks.
The active matrix contains only steady-state and incremental on 5queens and
grandparent, ten runs each, with a 30-second process timeout and unlimited
generations. It inherits SDK defaults; the algorithm is the only override.
Historical matrices and tests asserting their contents have been removed.

```powershell
uv run python benchmarks/run_experiments.py --list
uv run python benchmarks/run_experiments.py sdk-defaults/steady_state sdk-defaults/incremental
uv run python benchmarks/run_experiments.py --summary
```

Matching results may be reused. The fingerprint includes source and metaprogram
contents, task contents, effective arguments and the worker's Python and Clingo
versions. A change requires `--force` to replace the selected result. A source
change during a run marks its result stale. The manifest retains these inputs.
See [the current comparison](docs/sdk-defaults-comparison.md).
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

Variable labels always retain their declared identity semantics.
`#bias`, `#metarule`, `#predicate`, and `#modem` have been removed and now
raise explicit task errors. Modes and `#invent` remain supported. See
[the language contract and migration notes](docs/language-bias.md#removed-meta-programming-directives).

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

The recommended shared benchmark configuration uses structural mutation and
exact constraint-coverage inheritance. The default algorithm remains `steady_state`. The same settings run 5queens,
grandparent, coloring and knapsack, with ten runs each, a 30-second timeout per
run and no generation limit. A timeout skips remaining runs of that dataset.
This is the best-supported combination across these measured tasks, not a claim
of optimality for every ASP task. Historical matrices remain in the same TOML.

```powershell
uv run python benchmarks/run_experiments.py sdk-defaults/steady_state
```

Here we list only the main ones:

- `population.name`: `random`, which samples valid programs through `HypothesisGenerator`.
- `#maxv`: maximum distinct variables in one clause. Default 3.
- `#maxbl`: maximum body literals in one clause. Default 3.
- `#maxhl`: maximum head atoms in one clause. Default 1.
- `#maxpl`: maximum clauses in one candidate program. Default 6.
- Any structural limit accepts `*` when remaining mode recalls still make the
  clause space finite.
- `filename`: task file to parse.
- `iterations_genetic`: number of genetic generations. `0` means unlimited and is the default.
- `evaluation.scoring`: `cov_program`.
- `evaluation.constraint_inheritance`: exact coverage reuse for pure
  integrity-constraint changes, using the normal solver. Default `true`.
  Unresolved examples still use a fresh Clingo control. See
  [the experiment and guarantees](docs/semantic-inheritance-experiment.md).
- `algorithm`: `steady_state` (default) or `incremental`.
- `incremental.batch_size`: raw models per new clause batch. Default `128`.
- `incremental.archive_size`: retained distinct clauses before dependency pruning. Default `8192`.
- `incremental.epoch_generations`: generations between batches. Default `50`.
- `incremental.elite_count`: complete hypotheses retained at renewal. Default `10`.
- `incremental.time_limit_seconds`: optional positive net-time budget, including
  clause generation. Default `None`. `iterations_genetic=0` disables the generation
  limit. In-flight operations finish before returning, but late evaluations cannot
  improve the timed result. The benchmark runner's `timeout_seconds=0` disables
  its separate process timeout.
- `HypothesisGenerator` is mandatory infrastructure: every initialization,
  mutation, and crossover returns an already dependency-closed valid program.
