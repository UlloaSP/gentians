# Latin Square

Every row and column must contain all values.

**Source:** Latin-square synthetic benchmark

## Data and language

`bk.lp` contains 5 background statements. `exs.lp` contains 4 positive and 20 negative examples.
`bias.lp` declares 2 head modes and 6 body modes. Limits: `#maxv(4)`, `#maxbl(3)`, `#maxhl(1)`, `#maxpl(6)`.

## Reference hypothesis

```prolog
count_row(R,S) :- cell(R), #count{V : x(R,C,V)} = S.
count_col(C,S) :- cell(C), #count{V : x(R,C,V)} = S.
:- count_row(R,S), size(N), S != N.
:- count_col(C,S), size(N), S != N.
```
