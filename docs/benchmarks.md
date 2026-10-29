# Running benchmarks

Benchmark task directories live under `benchmarks/gentians/`. Named experiments
live in `benchmarks/experiments.toml`. Maintainer rules for metrics, dashboard
payloads and charts are in [benchmark-dashboard.md](benchmark-dashboard.md).

## Experiments

Edit `benchmarks/experiments.toml` to define datasets, Gentians run count, timeout,
default methods, tool options and common overrides. Select methods with
`--methods`; deterministic external learners run once per task/method.
Results are isolated in
`.benchmarks/experiments/<id>` and indexed by
`.benchmarks/experiments/experiments.json` for multi-experiment comparison. The
entire `.benchmarks/experiments/` directory is ignored by Git and can be deleted
to remove all local results and experiment snapshots. The Vite source remains
outside that directory. Run `uv run python benchmarks/run_experiments.py --list`
to recreate the index without running benchmarks.

```powershell
uv run python benchmarks/run_experiments.py --list
uv run python benchmarks/run_experiments.py
uv run python benchmarks/run_experiments.py --summary
```

The active local suite compares positive:negative score weights **1:1 and 10:1**
with steady state and populations **10 and 100**. Each configuration has five
matched seeds and a **300-second timeout per run**, on three synthetic coloring
tasks plus unchanged `coloring` and `set_partition_sum` controls. See the
[protocol, known solutions, and calibration](score-experiments.md).
The previous SDK, Alzheimer, and ILASP matrices have been removed from the active
TOML; their saved results remain on disk. Historical comparison documents record
the earlier protocols rather than current experiment IDs.

Run *i* of every dataset uses seed `seed_base + i`, with runs numbered from 1 and
`seed_base = 42`. Run 1 of any dataset or experiment therefore uses seed 43, so
datasets and experiments are matched run by run.

### Parallel execution

Each experiment, method and dataset is one unit, and up to `--jobs` units run at
once. The default is half the CPUs available to the process, which under Slurm
means the CPUs of the job, not of the node; `--jobs 1` runs the units in
sequence. The Slurm jobs always pass `--jobs 1`. Units write their run artifacts to the shared `runs/` directory and
their run index to `.parts/`. When the last unit of an experiment ends, the parts
are merged into `runs.csv` in configured dataset order and the dashboard is built
once. An experiment with `stop_on_timeout` keeps its datasets in a single unit,
because its first timeout screens out the whole configuration.

Concurrent units share CPU and memory. Wall-clock times, and therefore which
runs reach the timeout, depend on the load. The manifest records `jobs`; compare
times only between experiments run with the same value. Seeds and the result
fingerprint do not depend on `jobs`, so a result is reused regardless of it.

Each experiment is reset only when its first unit starts. After a unit fails, no
new unit starts: experiments already started keep their completed runs with
status `failed`, and the others keep their saved results.

Matching results may be reused. The fingerprint includes source and metaprogram
contents, task contents, effective arguments and the worker's Python and Clingo
versions. A change requires `--force` to replace the selected result. A source
change during a run marks its result stale. The manifest retains these inputs.

`--set PATH=JSON` overrides an `Arguments` field in every Gentians experiment,
after the TOML overrides. Its value is part of the saved config and the
fingerprint, so every run that indexes a result directory must pass the same
`--set`. The Slurm jobs pass `--set clause_generation.clingo_arguments=[]`:
clause generation runs on one Clingo thread instead of `--parallel-mode=5,split`.

## Historical results

Every index write (`--list`, a run or a dashboard rebuild) marks a saved result
historical once its fingerprint no longer matches the current code and
configuration, and keeps it viewable with its original metadata. It stays
historical until the experiment runs again with the current configuration. The
index retains the manifest's original status, including `stale` when source
changed during execution, so historical results can still be distinguished by
provenance. Only finished results with a dashboard or `runs.csv` qualify;
partial runs and directories saved under another experiment ID stay `stale`.
Saved external results with `runs.csv` can also be historical; this does not
create a Gentians dashboard or mark unmeasured metrics as available.

When the dashboard schema changes, rebuild saved dashboards from their raw run
artifacts instead of rerunning:

```powershell
uv run python benchmarks/run_experiments.py --rebuild-dashboards <ids>
```

This rewrites only `dashboard_data.json` with the current aggregation. Metrics a
run never recorded stay absent: older runs show no restart marks and empty
operator-score charts.

## Output

Each Gentians experiment directory holds `runs.csv`, `dashboard_data.json` and `runs/`,
the only raw copy: one log, resource snapshot, timings and progress file per run,
plus operator, clause, quality, Clingo and epoch events, all gzip-compressed when
the run ends. Gentians records clause generation, genetic generations, elapsed search time, fitness
evaluations, operator metrics and Clingo phases. `--summary` and
`--rebuild-dashboards` read `runs/` directly.
`benchmarks/profile_baseline.py --cprofile` also writes one `.prof` per run.
External learners keep `runs.csv` and `runs/`; ILASP stores stdout and stderr
as `.out.gz` and `.err.gz` and records its own internal timing phases.

Every learner saves `<dataset>_run_<n>_hypothesis.lp.gz` when it has a candidate,
plus `_validation.json.gz` and a separate ASP program for each example under
`_validation_programs/`. Validation checks the complete hypothesis against the
original background and isolated contexts: every positive must extend a stable
model and no negative may extend one. Its own timeout is configured with
`validation_timeout_seconds`; validation is outside measured learner time.
An unavailable candidate is recorded as `missing_hypothesis`, and validation
timeouts remain unknown. A checker that exits abnormally, or leaves an unfinished
report, is recorded as `error` with its exit code and its own error message.
Gentians checkpoints completed improvements so external
timeouts preserve its best available candidate. Both Gentians algorithms stop at
an operation boundary and export accumulated metrics, with up to five extra
seconds to close. Periodic metric checkpoints remain available if a stuck worker
requires a forced kill; their unfinished tail may be missing. Only verified
hypotheses count as successes; `reported_success` retains Gentians' original
result flag.

## Alzheimer

The four Alzheimer's drug-design tasks from
[Cropper's ILP datasets](https://huggingface.co/datasets/andrewcropper/ilp-datasets/blob/main/alzheimer/README.md)
remain in the catalog. Their earlier experiment definitions are no longer in
the active local TOML. The historical `alzheimer/population-10` and
`alzheimer/population-100` campaigns compared Gentians
steady-state and incremental with populations of 10 and 100 respectively,
plus ILASP 2 and 2i. Each used only the four Alzheimer datasets, 30 Gentians
runs per dataset/algorithm, one ILASP run per dataset/version and a 7200-second
timeout per run, with full Gentians metrics.
ILASP inputs under `benchmarks/ilasp/`
preserve the original background and examples, typed modes, recalls and positive
polarity; they use six variables and `-ml=5`. Gentians' direction pruning and
three-clause program bound are not imposed by this ILASP mode-bias translation.

To profile clause generation for all four tasks:

```powershell
uv run python benchmarks/profile_clauses.py --datasets alzheimer
```

By default, the terminal prints a table with benchmark name, final canonical
clause count, generation wall-clock seconds, final clauses per second, mean
microseconds per final clause and peak RSS in MiB. Generation includes preparation,
grounding, decoding, canonicalization and storage; it excludes task loading.
The peak belongs to each benchmark's generation, not to the whole process: it is
the OS high-water mark when that generation raises it, and otherwise the largest
resident size sampled every 20 ms, which can miss shorter spikes. It excludes
generation worker processes.
Compact mode disables generation instrumentation and writes no snapshots,
metrics or profiling files. `--out-dir` is used only in debug mode.

Use `--debug` for the detailed report and JSON snapshots:

```powershell
uv run python benchmarks/profile_clauses.py --datasets alzheimer --debug
```

In debug mode, the terminal reports final canonical, deduplicated clauses;
generation time split into grounding, solving and Python; task loading and JSON
serialization/write time; clauses per second; amortized microseconds per clause;
Clingo models, choices, conflicts, ground atoms and rules; and peak process RSS.
The JSON snapshot keeps its existing entries and raw metrics format.
Beside it, `<dataset>.lp` holds the complete clause-generation program: the
task facts and the metaprogram that Clingo receives. Its first line gives the
command, for example `clingo <file> 0 --parallel-mode=5,split`. Each model is
one reified clause, `selected/3` and `var_at/4` over mode ids, before Python
decoding and canonicalization. Tasks enumerated by the direct engine get the
equivalent program too. The file is written outside the reported times.
Entries are written incrementally, without a second list and a complete JSON
string in memory. Direct enumeration reports zero grounding/solving and no
Clingo model statistics. With process partitions, worker durations are summed
process-work seconds and are reported separately from parent wall time; the
parent's peak RSS excludes child processes. These runs cannot be compared as
Python CPU time by subtracting the overlapping worker totals from wall time.

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

For a detailed Python profile, add `--debug --cprofile`. `--cprofile` requires
`--debug` because it prints diagnostics and saves `.prof` and JSON files:

```powershell
uv run python benchmarks/profile_clauses.py --datasets alzheimer_acetyl --debug --cprofile
```

After the regular report, this runs clause generation a second time with the
same task and arguments, checks identical `ClauseSpace` entries, and verifies
that cProfile captured every enumerated model through either Python model
decoding or native row materialization. Each numeric row constructs one
`ReifiedClause`; block calls are never treated as captured models. A direct
engine has no Clingo callbacks; a partitioned profile covers only the parent
and cannot validate callback counts inside workers. It prints function
self-time buckets for decode, clause construction, canonicalization, visible
key/hash/dedup and append/storage calls, mixed canonicalizer and `ClauseSpace`
bookkeeping, `clingo.Symbol` access/conversion, AST-to-text conversion, other
Clingo bindings, and preparation/orchestration. The hottest functions also show
call counts and cumulative time. Self times form a disjoint partition;
cumulative times overlap and must not be added. Implicit tuple hashing and dict
assignments cannot be isolated by cProfile and remain in the enclosing
function's bucket. These are function buckets, not exact stage timers.
Rule text joins cached element texts in Python; only the first rendering of
each element reaches `clingo_ast_to_string`.
The native `_records.solve` self time mixes Clingo solving and record capture.
It has its own bucket and stays outside the Python denominator; normal phase
timers measure capture/delivery separately when instrumented. Missed Python
profiler coverage of model constructors remains an error, including with parallel
Clingo, rather than silently assuming that every returned model was profiled.
Generated clause dataclass methods retain their class names, and remaining
function-label collisions are disambiguated before export so no function's
self time is overwritten.

The second pass saves `<dataset>.python-profile.prof` for `pstats` or a profile
viewer, plus `<dataset>.python-profile.json` with all function rows, bucket
totals, callback counts, arguments and environment. Profiling affects timings
and second-pass caches may be warm: its seconds do not decompose the first
pass's Python total and are not rescaled to it. The first report retains the
regular throughput, JSON format and process-memory measurement. In the current
decoder, true reified symbols are copied once per model into a reused native
buffer. Symbol argument/name/number conversions belong to preparation of the
lookup rather than each decoded model.

To investigate decoder alternatives independently of production generation:

```powershell
uv run python benchmarks/profile_clause_decoder.py --datasets alzheimer_acetyl --limit 32768 --out .benchmarks/experiments/decoder-research/same-models.json
uv run python benchmarks/profile_clause_decoder.py --datasets alzheimer_acetyl --materialize --repeats 2 --out .benchmarks/experiments/decoder-research/full-pairs.json
```

The first command alternates five decoders on identical live models and checks
exact reified equality. The second uses the production canonicalizer and final
storage in independent exhaustive runs, reversing decoder order on alternating
pairs. It checks exhaustion, model/clauses counts and a SHA256 of all ordered
clause text and metadata. Timings separate preparation, grounding, decode,
canonicalization, callback wall time, solving residual and final storage.
Task loading, output hashing and report writing are outside its total.
Production generation uses the one-copy decoder. The other shown-symbol
variants and frozen truth-probe control remain benchmark-only. The decoder uses
Clingo's private Python binding. Protocol, primary
sources and measured limits: [decoder research](clause-decoder-research.md).

The Alzheimer task directories preserve the source facts and examples. Their
Popper predicate types are translated to Gentians modes with explicit
input/output directions, recall 2 for property lookup and recall 1 for
comparisons. Gentians limits each clause to five body literals and each
hypothesis to three clauses. These are explicit search bounds for this
benchmark, not limits supplied by the source.

## ILASP comparison

The historical [Gentiansâ€“ILASP comparison](ilasp-experiments.md) used 29 datasets and
a 120-second timeout. Both Gentians algorithms ran 30 times per dataset; ILASP
ran once per dataset and version, selecting 2 and 2i by default. One command
launches the methods configured in the active TOML, in parallel per dataset. Those historical
matrix IDs are no longer configured; to run an external learner, first define
its task selection and `[tools.ilasp]` settings in the common TOML:

```powershell
uv run python benchmarks/run_experiments.py <experiment-id> --methods ilasp-2 ilasp-2i
```

`benchmarks/experiments.toml` defines datasets, Gentians `runs`, timeout,
instrumentation and default `methods` once per experiment. `[tools.ilasp]`
configures its executable, WSL distribution, optional Python runtime and body
lengths. Include `ilasp-3` or `ilasp-4` in `--methods` to run other versions;
ILASP always runs once per task/version. Results are separated by method under
`.benchmarks/experiments/<id>/<method>/`. Changing the selection preserves other
methods' outputs. Gentians uses full instrumentation in these matrices and
keeps its Vite dashboard format.

To add a learner such as FastLAS, implement its backend, register methods in
`METHODS` and its execution function in `RUNNERS` in `run_experiments.py`, and
add its options under `[tools.<name>]`. The execution function receives the
experiment restricted to one unit's datasets, its output directory and a run
index path. The backend must save the hypothesis, call `validate_run`, and write
that index with status, success and artifact paths.
Include learner task and executable contents in `execution_inputs` and add its
preflight checks. FastLAS itself is not implemented yet. The runner
supports native Linux and Windows through WSL; body aggregate
tasks use complete explicit clause spaces on the ILASP side.

## Slurm

For Slurm execution on Shelob, see [the project-owned launcher](../slurm/README.md).
