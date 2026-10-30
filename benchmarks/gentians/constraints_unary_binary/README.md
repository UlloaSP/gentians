# constraints_unary_binary

Constraints mixing an open unary and an open binary predicate with three body atoms and three variables. Exactly 17 clauses, one per connected core.

Run from the repository root:

```powershell
uv run python benchmarks/profile_clauses.py --datasets constraints_unary_binary
uv run pytest tests/test_constraint_cores.py -q
```
