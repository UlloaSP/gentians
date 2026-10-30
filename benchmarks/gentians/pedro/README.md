# Pedro

Clause-generation benchmark for constraints over a single positive binary
predicate, `p/2`, with freely shared variables.

`bias.lp` permits up to four variables and two body atoms, with recall two and
no head modes. `bk.lp` leaves `p/2` open on four nodes so fixed background
properties do not remove candidate forms. `exs.lp` contains no examples: this
case profiles enumeration rather than inductive search or coverage.

Run from the repository root:

```powershell
uv run python benchmarks/profile_clauses.py --datasets pedro
uv run python benchmarks/profile_clauses.py --datasets pedro --debug
```

The debug snapshot is `.debug/clauses/pedro.json`. Print its generated rules:

```powershell
(Get-Content -Raw .debug/clauses/pedro.json | ConvertFrom-Json).entries.text
```

The generator produces four clauses, one per connected core: two with one body
atom (`p(V0,V0)` and `p(V0,V1)`) and two with two (the 2-cycle and the directed
path). `tests/test_constraint_cores.py` checks this against a brute-force oracle.
