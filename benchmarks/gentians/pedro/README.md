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

The current generator produces five clauses: two with one body atom and three
with two. They represent four logical equivalence classes; the two directed-path
forms remain equivalent under variable renaming and body permutation.
