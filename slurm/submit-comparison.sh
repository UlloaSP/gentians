#!/usr/bin/env bash
set -euo pipefail

methods=()
if [[ $# -gt 0 ]]; then
    if [[ $1 != --methods || $# -lt 2 ]]; then
        echo 'Usage: bash slurm/submit-comparison.sh [--methods gentians-steady_state gentians-incremental ilasp-2 ilasp-2i]' >&2
        exit 2
    fi
    shift
    methods=("$@")
fi
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
repo_root=$(dirname -- "$script_dir")
source "$script_dir/comparison.env"
command -v sbatch >/dev/null || { echo 'sbatch is required' >&2; exit 1; }
[[ -x "$repo_root/.venv/bin/python" ]] || { echo 'Prepare the runner with uv sync first' >&2; exit 1; }
selection=$("$repo_root/.venv/bin/python" - "$repo_root" "$COMPARISON_EXPERIMENT_ID" "${methods[@]}" <<'PY'
import sys
from pathlib import Path
root = Path(sys.argv[1])
sys.path.insert(0, str(root))
from benchmarks.run_experiments import METHODS, load_config
_, experiments = load_config(root / "benchmarks/experiments.toml")
experiment = next((item for item in experiments if item["id"] == sys.argv[2]), None)
if experiment is None:
    raise SystemExit(f"Unknown experiment: {sys.argv[2]}")
methods = list(dict.fromkeys(sys.argv[3:] or experiment["methods"]))
if any(method not in METHODS for method in methods):
    raise SystemExit(f"Unknown method; choose from {', '.join(METHODS)}")
print(" ".join(methods))
PY
)
read -r -a methods <<< "$selection"
if [[ " $selection " == *" gentians-"* ]]; then
    command -v singularity >/dev/null || { echo 'singularity is required' >&2; exit 1; }
    singularity sif list "$script_dir/images/gentians.sif" >/dev/null
fi
if [[ " $selection " == *" ilasp-"* ]]; then
    [[ -x "$repo_root/tools/ilasp/ILASP" ]] || { echo 'ILASP binary is not executable' >&2; exit 1; }
fi
mkdir -p -- "$script_dir/logs"
previous_job=''
for method in "${methods[@]}"; do
    if [[ $method == gentians-* ]]; then
        job_script="$script_dir/job.sh"
        job_time="$GENTIANS_SLURM_TIME"
    else
        job_script="$script_dir/ilasp-job.sh"
        job_time="$ILASP_SLURM_TIME"
    fi
    dependency=()
    if [[ -n $previous_job ]]; then
        dependency=(--dependency="afterany:$previous_job")
    fi
    job=$(sbatch --parsable "${dependency[@]}" \
        --job-name="$method" --partition="$GENTIANS_SLURM_PARTITION" \
        --nodes=1 --ntasks=1 --cpus-per-task="$GENTIANS_SLURM_CPUS" \
        --mem="$GENTIANS_SLURM_MEM" --time="$job_time" --chdir="$repo_root" \
        --output="$script_dir/logs/%x-%j.out" --error="$script_dir/logs/%x-%j.err" \
        --export="ALL,EXPERIMENT_ID=$COMPARISON_EXPERIMENT_ID,EXPERIMENT_METHOD=$method" "$job_script")
    printf '%s: %s\n' "$method" "$job"
    previous_job="$job"
done
