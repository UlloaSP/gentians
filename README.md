# GENTIANS

**GENeTic algorithm for Inductive learning of ANswer Set programs.**

Gentians learns answer set programs from examples. You give it background
knowledge in ASP, positive and negative examples, and a language bias; it
searches for a program that covers every positive example and no negative one.

Hypotheses can use the non-monotonic features of ASP: default and strong
negation, disjunctive, choice and cardinality heads, aggregates, comparisons,
arithmetic and predicate invention.

## How it works

Clingo plays two roles. First, it enumerates every legal clause allowed by the
language bias. Then, a steady-state genetic algorithm combines those clauses
into candidate programs, and Clingo evaluates each candidate as a whole under
stable-model semantics.

A clause has no fitness of its own: adding a rule can change the models of the
entire program. That is why Gentians always scores complete programs.

## Installation

Gentians uses [uv](https://docs.astral.sh/uv/):

```
uv sync
```

## Quick start

A task is a single file, or a directory with `bk.lp` (background), `exs.lp`
(examples) and `bias.lp` (language bias). An excerpt of
`benchmarks/gentians/grandparent`:

```prolog
% bk.lp
mother(i,a).
father(a,b).
father(b,d).

% exs.lp
#pos({target(i,b)}, {}).
#pos({target(a,d)}, {}).
#neg({target(a,b)}, {}).

% bias.lp
#maxv(3).
#maxbl(3).
#maxpl(3).
#modeh(1,target(var(person,input),var(person,output))).
#modeb(1,father(var(person,input),var(person,output))).
#modeb(1,mother(var(person,input),var(person,output))).
#invent(2,target_1(var(person,input),var(person,output))).
```

Run it from Python:

```python
from gentians import Arguments, main

main(Arguments(filename="benchmarks/gentians/grandparent"))
```

`benchmarks/gentians/` contains ready-made tasks, each with a `README.md`
describing the problem and its bounds.

## Documentation

- [Task language guide](docs/task-language.md): modes, examples, aggregates, arithmetic, invention.
- [Language bias contract](docs/language-bias.md): exact syntax and meaning.
- [Running and configuring Gentians](docs/usage.md): algorithms, variation and options.
- [Running benchmarks](docs/benchmarks.md): experiments, Alzheimer, ILASP comparison, Slurm.
- [Architecture](docs/architecture.md) and [pipeline](docs/pipeline.md): module responsibilities and invariants.
- [Decision records](docs/adr/) and experiment reports in [docs/](docs/).

## Development

```
uv run ruff check gentians
uv run ty check
uv run pytest
```

The benchmark dashboard is a Vite+ project in `.benchmarks/`; run `vp i` and
`vp dev` from that directory. Contributor and agent rules are in
[AGENTS.md](AGENTS.md).
