# 5 queens

5-queens column and diagonal constraints.

**Source:** http://www.hakank.org/answer_set_programming/nqueens.lp

## Data and language

`bk.lp` contains 4 background statements. `exs.lp` contains 10 positive and 35 negative examples.
`bias.lp` declares 0 head modes and 4 body modes. Limits: `#maxv(5)`, `#maxbl(5)`, `#maxhl(1)`, `#maxpl(6)`.

## Reference hypothesis

```prolog
:- q(X1,Y), q(X2,Y), X1 < X2.
:- q(X1,Y1), q(X2,Y2), X1 < X2, Y1 + X1 = Z, Z = Y2 + X2.
:- q(X1,Y1), q(X2,Y2), X1 < X2, Y1 - X1 = Z, Z = Y2 - X2.
```
