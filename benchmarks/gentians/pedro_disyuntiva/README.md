# Pedro disyuntiva

Clause-generation benchmark for disjunctive rules over four positive binary
predicates, `p/2`, `q/2`, `r/2` and `t/2`, with freely shared variables.

`bias.lp` permits up to four variables and two body atoms. A head is one atom
from `#modeh` or a disjunction of two atoms from `#modehd`; a predicate may
occur twice in one disjunction. Each predicate may occur once in the body, and
headless constraints remain legal. `bk.lp` leaves the four predicates open on
four nodes so fixed background properties do not remove candidate forms.
`exs.lp` contains no examples: this case profiles enumeration rather than
inductive search or coverage.

```powershell
uv run python benchmarks/profile_clauses.py --datasets pedro_disyuntiva
```
