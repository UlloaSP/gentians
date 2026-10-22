# Pedro cabeza

Clause-generation benchmark for rules over three positive binary predicates,
`p/2`, `q/2` and `r/2`, with freely shared variables.

`bias.lp` permits up to four variables, two body atoms and one head atom. Each
predicate may be the head and may occur once in the body. Headless constraints
remain legal. `bk.lp` leaves the three predicates open on four nodes so fixed
background properties do not remove candidate forms. `exs.lp` contains no
examples: this case profiles enumeration rather than inductive search or
coverage.

```powershell
uv run python benchmarks/profile_clauses.py --datasets pedro_cabeza
```
