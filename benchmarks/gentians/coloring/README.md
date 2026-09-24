# Coloring

Three-color graph coloring.

**Source:** graph-coloring synthetic benchmark

## Data and language

`bk.lp` contains 11 background statements. `exs.lp` contains 6 positive and 4 negative examples.
`bias.lp` declares 1 head mode and 5 body modes. Limits: `#maxv(3)`, `#maxbl(4)`, `#maxhl(3)`, `#maxpl(4)`.

## Reference hypothesis

```prolog
red(X);green(X);blue(X) :- node(X).
:- e(X,Y), red(X), red(Y).
:- e(X,Y), green(X), green(Y).
:- e(X,Y), blue(X), blue(Y).
```
