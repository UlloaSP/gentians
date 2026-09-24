# Coin

Choose heads or tails for each coin.

**Source:** https://doc.ilasp.com/specification/cdpis.html

## Data and language

`bk.lp` contains 3 background statements. `exs.lp` contains 2 positive and 0 negative examples.
`bias.lp` declares 2 head modes and 3 body modes. Limits: `#maxv(3)`, `#maxbl(3)`, `#maxhl(1)`, `#maxpl(6)`.

## Reference hypothesis

```prolog
heads(C) :- coin(C), not tails(C).
tails(C) :- coin(C), not heads(C).
```
