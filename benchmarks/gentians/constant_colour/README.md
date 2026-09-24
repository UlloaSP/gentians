# Constant Colour

Learn which fixed colour identifies target nodes.

**Source:** synthetic constant-placeholder benchmark

## Data and language

`bk.lp` contains 3 background statements. `exs.lp` contains 2 positive and 1 negative examples.
`bias.lp` declares 1 head mode and 1 body mode. Limits: `#maxv(1)`, `#maxbl(1)`, `#maxhl(1)`, `#maxpl(1)`.

## Reference hypothesis

```prolog
target(X) :- colour(X,red).
```
