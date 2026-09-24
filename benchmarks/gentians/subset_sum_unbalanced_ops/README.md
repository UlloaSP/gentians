# Subset Sum Unbalanced Ops

Explicit projected aggregate plus extra comparisons variant.

**Source:** subset-sum synthetic benchmark

## Data and language

`bk.lp` contains 5 background statements. `exs.lp` contains 1 positive and 0 negative examples.
`bias.lp` declares 1 head mode and 6 body modes. Limits: `#maxv(3)`, `#maxbl(3)`, `#maxhl(1)`, `#maxpl(6)`.

## Reference hypothesis

```prolog
s(S) :- #sum{X : el(X)} = S.
```
