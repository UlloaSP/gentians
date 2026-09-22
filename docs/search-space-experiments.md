# Search-space experiment status

The executable matrix contains SDK-default and mutation-probability comparisons,
with 30-second timeouts.
The [current comparison](sdk-defaults-comparison.md) records the new measurements.
Older measurements remain historical evidence, not selectable implementations.

| Area | Current status | Historical report |
| --- | --- | --- |
| Dependency-subgraph crossover | Rejected and removed. It increased time and evaluations without improving success over `set_mix`. | [Rejected crossover](variation-policy.md#rejected-dependency-subgraph-crossover) |
| Pool sampling and persistent evaluation | Removed. Only steady-state and incremental remain. | [Incremental history](incremental-experiment.md) |
| Incremental retention | Bounded raw-clause archive retained; complete small spaces remain available. | [Retention and cache experiments](incremental-experiment.md) |
| Exact-program cache across batches | Rejected and removed. Normal search memoization remains. | [Cache results](incremental-experiment.md#rejected-exact-program-cache-9-september-2026) |
| Incremental restarts and constraint proposals | Fixed policies: restart headed spaces after 100 stagnant generations; up to 16 constraint proposals per new batch. No ablation switches. | [Constraint probes](incremental-crossover-experiment.md) |
| Batch 512, epochs 10, elites 5 | Rejected as defaults; old matrix entries removed. | [Incremental history](incremental-experiment.md) |
| Completeness and constraint-only mutation | Structural policy retained; experimental toggles removed. | [Mutation ablation](mutation-ablation-experiment.md) |
| Complete candidates without active constraints | Ordinary headed edits enabled; improves `even_odd` from 20/30 to 25/30 at 20.000 generations. | [No-constraint mutation](mutation-no-constraints-experiment.md) |
| Steady-state stagnation | Champion-preserving population restart after 100 stagnant generations in headed spaces; global evaluation cache retained. `even_odd` reaches 30/30 within 20.000 generations and all nine measured datasets reach 30/30. | [Steady-state restart](mutation-no-constraints-experiment.md#steady-state-restart) |
| Constraint coverage inheritance | Enabled by the SDK default. | [Inheritance](semantic-inheritance-experiment.md) |
| Constraint diagnosis and repair | Removed, including active matrix entries. | [Repair](semantic-repair-experiment.md) |
| Structural population initialization | Removed, including active matrix entries. | [Population diversity](population-diversity-experiment.md) |

Historical reports describe the source and settings at measurement time. Their
commands and option names are not the current API. Do not infer a universal
speedup from one group of seeds. In particular, the previous `search-current`
comparison explicitly disabled coverage inheritance and did not measure all SDK
defaults. Tests of catalogue IDs, counts and experimental settings were removed.
