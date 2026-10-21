# Sudoku

Learn a 4x4 Sudoku: the choice rule that assigns one value to each cell and the
constraints that reject repeated values in a row, column, or block.

**Source:** Euler's Latin-square formulation: `x(R,C,V)` places value `V` in row
`R` and column `C`; a Sudoku is a Latin square whose 2x2 blocks also contain
every value.

## Data and language

`bk.lp` contains 4 background statements: the indices, the values, each cell's
block, and `same_block/4` for distinct cells in the same block. `x/3` is not in
the background; only the learned choice rule defines it.

`exs.lp` contains 100 positive and 100 negative examples. Each example is a
complete grid: inclusions list its `x/3` atoms and exclusions list the other 64
possible atoms. The positives are 100 distinct valid Sudokus out of 288. The
negatives are 20 each of:

- a valid Sudoku with an empty cell;
- a valid Sudoku with a second value in one cell;
- a value repeated in a row only;
- a value repeated in a column only;
- a Latin square with a value repeated in a block.

`bias.lp` declares 4 head modes (the choice rule with each lower and upper bound
present or absent) and 4 body modes. Limits: `#maxv(5)`, `#maxbl(3)`,
`#maxhl(1)`, `#maxpl(6)`.

## Reference hypothesis

```prolog
1 { x(R,C,V) : value(V) } 1 :- index(R), index(C).
:- x(R,C1,V), x(R,C2,V), C1 != C2.
:- x(R1,C,V), x(R2,C,V), R1 != R2.
:- x(R1,C1,V), x(R2,C2,V), same_block(R1,C1,R2,C2).
```

Dropping any of these rules makes the hypothesis incorrect. `1 { ... }` without
an upper bound is also correct: with every cell filled, the row constraint
already leaves exactly one value per cell.
