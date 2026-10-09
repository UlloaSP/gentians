#!/usr/bin/env bash
set -euo pipefail

: "${EXPERIMENT_ID:?Missing experiment ID}"
: "${EXPERIMENT_METHOD:?Missing experiment method}"
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
repo_root=$(dirname -- "$script_dir")
cd -- "$repo_root"

# El runner usa Python 3.14 preparado con uv. El binario ILASP usa las
# bibliotecas del nodo, incluido libpython3.10, y ejecuta GNU timeout por run.
printf 'Experiment: %s\nJob: %s\nNode: %s\n' \
    "$EXPERIMENT_ID" "${SLURM_JOB_ID:-local}" "$(hostname)"
printf 'Commit: '
git -c "safe.directory=$repo_root" rev-parse HEAD || true
"$repo_root/.venv/bin/python" --version
sha256sum -- "$repo_root/tools/ilasp/ILASP"

exec "$repo_root/.venv/bin/python" \
    benchmarks/run_experiments.py "$EXPERIMENT_ID" --methods "$EXPERIMENT_METHOD"
