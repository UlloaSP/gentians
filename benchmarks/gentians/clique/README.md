# Clique

Accept cliques of size 3.

**Source:** synthetic clique benchmark

## Data and language

`bk.lp` contains 20 background statements. `exs.lp` contains 2 positive and 2 negative examples.
`bias.lp` declares 0 head modes and 4 body modes. Limits: `#maxv(2)`, `#maxbl(7)`, `#maxhl(1)`, `#maxpl(6)`.

## Reference hypothesis

```prolog
:- in(X), in(Y), X != Y, ne(X,Y), ne(Y,X).
```
