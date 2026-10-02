# Running benchmarks

Benchmark task directories live under `benchmarks/gentians/`. Named experiments
live in `benchmarks/experiments.toml`. Maintainer rules for metrics, dashboard
payloads and charts are in [benchmark-dashboard.md](benchmark-dashboard.md).

## Experiments

Edit `benchmarks/experiments.toml` to define datasets, run count, timeout,
common overrides, and named experiments. Results are isolated in
`.benchmarks/experiments/<id>` and indexed by
`.benchmarks/experiments/experiments.json` for multi-experiment comparison. The
entire `.benchmarks/experiments/` directory is ignored by Git and can be deleted
to remove all local results and experiment snapshots. The Vite source remains
outside that directory. Run `uv run python benchmarks/run_experiments.py --list`
to recreate the index without running benchmarks.

```powershell
uv run python benchmarks/run_experiments.py --list
uv run python benchmarks/run_experiments.py sdk-defaults/steady_state sdk-defaults/incremental
uv run python benchmarks/run_experiments.py --summary
```

The `sdk-defaults` experiments compare steady-state and incremental search on
5queens and grandparent, with ten runs and a 30-second timeout. See
[the current comparison](sdk-defaults-comparison.md). Other named experiments,
including Alzheimer, keep their own dataset lists and limits in the same TOML
file.

Run *i* of every dataset uses seed `seed_base + i`, with runs numbered from 1 and
`seed_base = 42`. Run 1 of any dataset or experiment therefore uses seed 43, so
datasets and experiments are matched run by run.

Matching results may be reused. The fingerprint includes source and metaprogram
contents, task contents, effective arguments and the worker's Python and Clingo
versions. A change requires `--force` to replace the selected result. A source
change during a run marks its result stale. The manifest retains these inputs.

## Historical results

`--historical-index <ids>` keeps saved results viewable after their
configuration changes. They stay historical until the experiment runs again with
the current configuration; `--list` and new runs keep that status. The index
retains the manifest's original status, including `stale` when source changed
during execution, so historical results can still be distinguished by provenance.

When the dashboard schema changes, rebuild saved dashboards from their raw run
artifacts instead of rerunning:

```powershell
uv run python benchmarks/run_experiments.py --rebuild-dashboards <ids>
```

This rewrites only `dashboard_data.json` with the current aggregation. Metrics a
run never recorded stay absent: older runs show no restart marks and empty
operator-score charts.

## Output

Each experiment directory holds `runs.csv`, `dashboard_data.json` and `runs/`,
the only raw copy: one log, resource snapshot, timings and progress file per run,
plus operator, clause, quality, Clingo and epoch events, all gzip-compressed when
the run ends. ILASP runs store their raw output as `.out.gz` and `.err.gz`. They
record clause generation, genetic generations, elapsed search time, fitness
evaluations, operator metrics and Clingo phases. `--summary` and
`--rebuild-dashboards` read `runs/` directly.
`benchmarks/profile_baseline.py --cprofile` also writes one `.prof` per run.

## Alzheimer

The `alzheimer/incremental` experiment runs the four Alzheimer's drug-design
tasks from [Cropper's ILP datasets](https://huggingface.co/datasets/andrewcropper/ilp-datasets/blob/main/alzheimer/README.md):

```powershell
uv run python benchmarks/run_experiments.py alzheimer/incremental
```

To profile clause generation for all four tasks:

```powershell
uv run python benchmarks/profile_clauses.py --datasets alzheimer
```

For each dataset, the terminal reports final canonical, deduplicated clauses;
generation time split into grounding, solving and Python; task loading and JSON
serialization/write time; clauses per second; amortized microseconds per clause;
Clingo models, choices, conflicts, ground atoms and rules; and peak process RSS.
The JSON snapshot keeps its existing entries and raw metrics format.

`Final clauses / generation wall-clock` measures the observed generation cost,
including profiling and metric export. `Final clauses / net generation` uses
the instrumented generation time, excluding recorded instrumentation overhead.
Both exclude task loading and the clause snapshot's JSON serialization/write;
`Final clauses / total wall-clock` includes those costs. Python is the residual
generation time after subtracting grounding and solving, including preparation,
decoding, canonicalization and deduplication. Solving excludes model callbacks.

Clingo models have already survived ASP legality, symmetry and pruning
constraints. `Post-enumeration retention` is final clauses divided by those
models; `Removed/merged after enumeration` counts the difference. Neither
measures pruning inside Clingo. Pre-pruning candidate counts, raw candidate
throughput and global survival are reported as unavailable rather than inferred
from solver choices or conflicts. Rates with a zero denominator are unavailable.
Peak RSS is the operating system's high-water mark for the process, including
JSON serialization and earlier datasets in the same invocation; run one dataset
per invocation to avoid accumulating earlier peaks.

For a detailed Python profile, add `--cprofile`:

```powershell
uv run python benchmarks/profile_clauses.py --datasets alzheimer_acetyl --cprofile
```

After the regular report, this runs clause generation a second time with the
same task and arguments, checks identical `ClauseSpace` entries, and verifies
that cProfile captured every enumerated model callback. It prints function
self-time buckets for decode, clause construction, canonicalization, visible
key/hash/dedup and append/storage calls, mixed canonicalizer and `ClauseSpace`
bookkeeping, `clingo.Symbol` access/conversion, AST-to-text conversion, other
Clingo bindings, and preparation/orchestration. The hottest functions also show
call counts and cumulative time. Self times form a disjoint partition;
cumulative times overlap and must not be added. Implicit tuple hashing and dict
assignments cannot be isolated by cProfile and remain in the enclosing
function's bucket. These are function buckets, not exact stage timers.
Generated clause dataclass methods retain their class names, and remaining
function-label collisions are disambiguated before export so no function's
self time is overwritten.

The second pass saves `<dataset>.python-profile.prof` for `pstats` or a profile
viewer, plus `<dataset>.python-profile.json` with all function rows, bucket
totals, callback counts, arguments and environment. Profiling affects timings
and second-pass caches may be warm: its seconds do not decompose the first
pass's Python total and are not rescaled to it. The first report retains the
regular throughput, JSON format and process-memory measurement. In the current
decoder, model literals are read directly; Symbol conversions primarily belong
to preparation of the index rather than each decoded model.

The Alzheimer task directories preserve the source facts and examples. Their
Popper predicate types are translated to Gentians modes with explicit
input/output directions, recall 2 for property lookup and recall 1 for
comparisons. Gentians limits each clause to five body literals and each
hypothesis to three clauses. These are explicit search bounds for this
benchmark, not limits supplied by the source.

## ILASP comparison

The [Gentians–ILASP comparison](ilasp-experiments.md) configures 29 datasets, 30
runs and a 120-second timeout for both Gentians algorithms and ILASP 2, 2i, 3
and 4. Its runner supports native Linux and Windows through WSL; body aggregate
tasks use complete explicit clause spaces on the ILASP side.

## Slurm

For Slurm execution on Shelob, see [the project-owned launcher](../slurm/README.md).
