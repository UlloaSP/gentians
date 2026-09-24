# Euclid

Learn gcd recursion used by pairprime/2.

**Source:** Euclid algorithm synthetic benchmark

## Data and language

`bk.lp` contains 6 background statements. `exs.lp` contains 1 positive and 4 negative examples.
`bias.lp` declares 1 head mode and 6 body modes. Limits: `#maxv(5)`, `#maxbl(8)`, `#maxhl(1)`, `#maxpl(6)`.

## Reference hypothesis

```prolog
eucl(A,B,M) :- num(A),num(B), A < B, eucl(B,A,M).
eucl(A,Z,A) :- zero(Z), num(A).
eucl(A,B,M) :- num(A),num(B),zero(Z),A > B,B > Z,D = A \ B,eucl(B,D,M).
```
