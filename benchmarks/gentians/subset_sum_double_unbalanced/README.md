# Subset Sum Double Unbalanced

Projected aggregate variant for both coordinate sums.

**Source:** double subset-sum synthetic benchmark

## Data and language

`bk.lp` contains 5 background statements. `exs.lp` contains 3 positive and 3 negative examples.
`bias.lp` declares 3 head modes and 4 body modes. Limits: `#maxv(3)`, `#maxbl(4)`, `#maxhl(1)`, `#maxpl(6)`.

## Reference hypothesis

```prolog
s0(S) :- #sum{X : el(X,Y)} = S.
s1(S) :- #sum{Y : el(X,Y)} = S.
ok(S) :- s0(S),s1(S).
```
