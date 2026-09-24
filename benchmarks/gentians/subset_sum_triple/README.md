# Subset Sum Triple

Return sums that agree across all three tuple positions.

**Source:** triple subset-sum synthetic benchmark

## Data and language

`bk.lp` contains 5 background statements. `exs.lp` contains 2 positive and 4 negative examples.
`bias.lp` declares 1 head mode and 1 body mode. Limits: `#maxv(4)`, `#maxbl(4)`, `#maxhl(1)`, `#maxpl(6)`.

## Reference hypothesis

```prolog
ok(S) :- #sum{X,Y,Z : el(X,Y,Z)} = S, #sum{Y,X,Z : el(X,Y,Z)} = S, #sum{Z,X,Y : el(X,Y,Z)} = S.
```
