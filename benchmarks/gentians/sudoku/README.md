# Sudoku

Reject equal values in same row, column, or block.

**Source:** ILASP Sudoku benchmark

## Data and language

`bk.lp` contains 9 background statements. `exs.lp` contains 1 positive and 3 negative examples.
`bias.lp` declares 0 head modes and 4 body modes. Limits: `#maxv(3)`, `#maxbl(3)`, `#maxhl(1)`, `#maxpl(6)`.

## Reference hypothesis

```prolog
:- value(C0,V),value(C1,V),same_row(C0,C1).
:- value(C0,V),value(C1,V),same_col(C0,C1).
:- value(C0,V),value(C1,V),same_block(C0,C1).
```
