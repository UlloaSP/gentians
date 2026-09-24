# Subset Sum Double And Sum

Return twice a coordinate sum.

**Source:** double subset-sum synthetic benchmark

## Data and language

`bk.lp` contains 5 background statements. `exs.lp` contains 3 positive and 3 negative examples.
`bias.lp` declares 1 head mode and 2 body modes. Limits: `#maxv(6)`, `#maxbl(4)`, `#maxhl(1)`, `#maxpl(6)`.

## Reference hypothesis

```prolog
ok(S) :- #sum{X,Y : el(X,Y)} = A, #sum{Y,X : el(X,Y)} = A, S = A + A.
```
