# Grandparent

Grandparent through parent helper predicate.

**Source:** Metagol grandparent benchmark

## Data and language

`bk.lp` contains 8 background statements. `exs.lp` contains 7 positive and 8 negative examples.
`bias.lp` declares 2 head modes and 3 body modes. Limits: `#maxv(3)`, `#maxbl(3)`, `#maxhl(1)`, `#maxpl(3)`.

## Reference hypothesis

```prolog
target(A,B) :- target_1(A,C),target_1(C,B).
target_1(A,B) :- mother(A,B).
target_1(A,B) :- father(A,B).
```
