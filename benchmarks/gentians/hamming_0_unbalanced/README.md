# Hamming 0 Unbalanced

Projected aggregate variant; distance must equal hd/1.

**Source:** Hamming-distance synthetic benchmark

## Data and language

`bk.lp` contains 6 background statements. `exs.lp` contains 8 positive and 56 negative examples.
`bias.lp` declares 0 head modes and 4 body modes. Limits: `#maxv(4)`, `#maxbl(3)`, `#maxhl(1)`, `#maxpl(6)`.

## Reference hypothesis

```prolog
:- hd(D), S != D, #sum{X : d(P,X)} = S.
```
