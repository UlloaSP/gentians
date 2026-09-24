# Magic square (no diagonals)

Rows and columns must have equal sums.

**Source:** magic-square synthetic benchmark

## Data and language

`bk.lp` contains 5 background statements. `exs.lp` contains 72 positive and 27 negative examples.
`bias.lp` declares 2 head modes and 5 body modes. Limits: `#maxv(4)`, `#maxbl(4)`, `#maxhl(1)`, `#maxpl(6)`.

## Reference hypothesis

```prolog
sum_row(R,S) :- size(R), #sum{V : x(R,C,V)} = S.
sum_col(C,S) :- size(C), #sum{V : x(R,C,V)} = S.
:- sum_row(R0,S0),sum_row(R1,S1),R0 != R1,S0 != S1.
:- sum_col(C0,S0),sum_col(C1,S1),C0 != C1,S0 != S1.
```

## Example groups

The negative examples include assignments with invalid columns only, invalid rows only, and both rows and columns invalid.
