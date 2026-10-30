# constraints_two_relations

Constraints over two open binary predicates with three body atoms and three variables. Exactly 83 clauses, one per connected core: twins only merge inside a mode, so p and q never exchange atoms.

Run from the repository root:

```powershell
uv run python benchmarks/profile_clauses.py --datasets constraints_two_relations
uv run pytest tests/test_constraint_cores.py -q
```
