# Adjacent To Red

Nodes adjacent to a red-colored node.

**Source:** https://github.com/metagol/metagol/blob/master/examples/adjacent-to-red.pl

## Data and language

`bk.lp` contains 12 background statements. `exs.lp` contains 2 positive and 3 negative examples.
`bias.lp` declares 1 head mode and 5 body modes. Limits: `#maxv(3)`, `#maxbl(4)`, `#maxhl(1)`, `#maxpl(6)`.

## Reference hypothesis

```prolog
target(A) :- edge(A,B),colour(B,C),red(C).
```
