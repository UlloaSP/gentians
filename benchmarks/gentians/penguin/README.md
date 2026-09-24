# Penguin

Penguins are birds that do not fly.

**Source:** default-negation bird benchmark

## Data and language

`bk.lp` contains 7 background statements. `exs.lp` contains 1 positive and 1 negative examples.
`bias.lp` declares 1 head mode and 2 body modes. Limits: `#maxv(3)`, `#maxbl(3)`, `#maxhl(1)`, `#maxpl(6)`.

## Reference hypothesis

```prolog
penguin(X) :- bird(X), not flies(X).
```
