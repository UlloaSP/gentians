# Set Partition Sum

Two partitions must have equal sums.

**Source:** http://www.hakank.org/answer_set_programming/set_partition.lp

## Data and language

`bk.lp` contains 9 background statements. `exs.lp` contains 2 positive and 30 negative examples.
`bias.lp` declares 1 head mode and 4 body modes. Limits: `#maxv(4)`, `#maxbl(4)`, `#maxhl(1)`, `#maxpl(6)`.

## Reference hypothesis

```prolog
sum_partition(P,S) :- partition(P), #sum{I : p(P,I)} = S.
:- sum_partition(P0,S0),sum_partition(P1,S1),P0 != P1,S0 != S1.
```
