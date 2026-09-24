# Knapsack

Reject selections whose total weight exceeds max_weight/1.

**Source:** knapsack synthetic benchmark

## Data and language

`bk.lp` contains 7 background statements. `exs.lp` contains 2 positive and 2 negative examples.
`bias.lp` declares 0 head modes and 3 body modes. Limits: `#maxv(4)`, `#maxbl(3)`, `#maxhl(1)`, `#maxpl(6)`.

## Reference hypothesis

```prolog
:- max_weight(Max), Sum > Max, #sum{Weight,Value : el(Value,Weight)} = Sum.
```
