# Synthetic Million

Deterministic constraint-learning stress task.

## Data and language

`bk.lp` contains 827 background statements. `exs.lp` contains 57 positive and 25 negative examples.
`bias.lp` declares 0 head modes and 32 body modes. Limits: `#maxv(1)`, `#maxbl(6)`, `#maxhl(0)`, `#maxpl(6)`.

Regenerate these files with `uv run python -m benchmarks.synthetic_million`. The seed is 20260908.

## Notes

- Legal clauses: 1,149,016; up to six per hypothesis.
