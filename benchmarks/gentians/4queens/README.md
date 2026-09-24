# 4 queens

4-queens constraints.

**Source:** http://www.hakank.org/answer_set_programming/nqueens.lp

## Data and language

`bk.lp` contains 4 background statements. `exs.lp` contains 2 positive and 22 negative examples.
`bias.lp` declares 0 head modes and 4 body modes. Limits: `#maxv(3)`, `#maxbl(5)`, `#maxhl(1)`, `#maxpl(6)`.

## Reference hypothesis

```prolog
:- q(V0,V1),q(V1,V0).
:- V0+V2=V1,q(V2,V1),q(V1,V0).
```
