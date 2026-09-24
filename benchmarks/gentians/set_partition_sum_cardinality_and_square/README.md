# Set Partition Sum Cardinality And Square

Two partitions must have equal square-sums and cardinalities.

**Source:** http://www.hakank.org/answer_set_programming/set_partition.lp

## Data and language

`bk.lp` contains 6 background statements. `exs.lp` contains 1 positive and 5 negative examples.
`bias.lp` declares 2 head modes and 6 body modes. Limits: `#maxv(4)`, `#maxbl(4)`, `#maxhl(1)`, `#maxpl(6)`.

## Reference hypothesis

```prolog
sum_partition_sq(P,S) :- partition(P), #sum{V : sq(P,V)} = S.
count_partition(P,C) :- partition(P), #count{I : p(P,I)} = C.
:- sum_partition_sq(P0,S0),sum_partition_sq(P1,S1),P0 != P1,S0 != S1.
:- count_partition(P0,C0),count_partition(P1,C1),P0 != P1,C0 != C1.
```
