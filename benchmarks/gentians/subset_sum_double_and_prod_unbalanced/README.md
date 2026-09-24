# Subset Sum Double And Prod Unbalanced

Projected aggregate variant returning product of coordinate sums.

**Source:** double subset-sum synthetic benchmark

## Data and language

`bk.lp` contains 5 background statements. `exs.lp` contains 5 positive and 5 negative examples.
`bias.lp` declares 1 head mode and 4 body modes. Limits: `#maxv(5)`, `#maxbl(4)`, `#maxhl(1)`, `#maxpl(6)`.

## Reference hypothesis

```prolog
ok(P) :- #sum{X : el(X,Y)} = A, #sum{Y : el(X,Y)} = B, P = A * B.
```
