# constraints_cycles

Constraints over one open binary predicate with four body atoms and four variables, where literal permutations multiply the renamed twins of each body. Exactly 14 clauses, one per connected core.

Run from the repository root:

```powershell
uv run python benchmarks/profile_clauses.py --datasets constraints_cycles
uv run pytest tests/test_constraint_cores.py -q
```
