# Hamming 1 Unbalanced

Distance must equal hd/1; retain the position to count repeated differences.

**Source:** Hamming-distance synthetic benchmark

## Data and language

`bk.lp` contains 6 background statements. `exs.lp` contains 24 positive and 40 negative examples.
`bias.lp` declares 0 head modes and 4 body modes. Limits: `#maxv(4)`, `#maxbl(3)`, `#maxhl(1)`, `#maxpl(6)`.

## Reference hypothesis

```prolog
:- hd(D), S != D, #sum{X,P : d(P,X)} = S.
```

## Notes

- Historical id retained; projecting away P loses multiplicity and is not Hamming distance.
