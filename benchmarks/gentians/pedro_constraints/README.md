# Pedro constraints

Clause-generation benchmark for constraints over two positive binary
predicates, `p/2` and `q/2`, with freely shared variables.

`bias.lp` permits up to four variables and two body atoms, each predicate with
recall one, and no head modes: bodies contain `p`, `q`, or `p` and `q`.
`bk.lp` leaves both predicates open on four nodes so fixed background
properties do not remove candidate forms. `exs.lp` contains no examples: this
case profiles enumeration rather than inductive search or coverage.

```powershell
uv run python benchmarks/profile_clauses.py --datasets pedro_constraints
```
