# Animals Bird

Birds are animals with feather covering.

**Source:** https://github.com/logic-and-learning-lab/Popper/tree/main/examples/animals_bird

## Data and language

`bk.lp` contains 49 background statements. `exs.lp` contains 3 positive and 13 negative examples.
`bias.lp` declares 1 head mode and 8 body modes. Limits: `#maxv(3)`, `#maxbl(3)`, `#maxhl(1)`, `#maxpl(6)`.

## Reference hypothesis

```prolog
bird(A) :- has_covering(A,C),feathers(C).
```
