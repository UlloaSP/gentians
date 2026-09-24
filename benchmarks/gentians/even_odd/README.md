# Even Odd

Mutual recursion for even and odd numbers.

**Source:** https://github.com/stassa/louise/blob/master/data/examples/even_odd.pl

## Data and language

`bk.lp` contains 5 background statements. `exs.lp` contains 1 positive and 3 negative examples.
`bias.lp` declares 2 head modes and 3 body modes. Limits: `#maxv(3)`, `#maxbl(3)`, `#maxhl(1)`, `#maxpl(6)`.

## Reference hypothesis

```prolog
even(X) :- odd(Y),prev(X,Y).
odd(X) :- even(Y),prev(X,Y).
```
