# constraints_paths

Constraints over one open binary predicate with three body atoms and four variables. Exactly seven clauses, one per connected core: two with one atom, two with two (the 2-cycle and the path), and three with three (the 3-cycle, the 3-path and the transitive triangle).

Run from the repository root:

```powershell
uv run python benchmarks/profile_clauses.py --datasets constraints_paths
uv run pytest tests/test_constraint_cores.py -q
```
