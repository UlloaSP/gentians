#!/usr/bin/env bash
set -euo pipefail

# Envía los tres jobs en orden para no solapar mediciones ni escrituras del índice.
if [[ $# -ne 0 ]]; then
    echo 'Usage: bash slurm/submit-comparison.sh' >&2
    exit 2
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
repo_root=$(dirname -- "$script_dir")
image="$script_dir/images/gentians.sif"
source "$script_dir/comparison.env"

command -v sbatch >/dev/null || { echo 'sbatch is required' >&2; exit 1; }
command -v singularity >/dev/null || { echo 'singularity is required' >&2; exit 1; }
[[ -f "$image" ]] || { echo 'Build the image first: bash slurm/build.sh' >&2; exit 1; }
singularity sif list "$image" >/dev/null || { echo "Invalid image: $image" >&2; exit 1; }
[[ -x "$repo_root/.venv/bin/python" ]] || {
    echo 'Prepare the ILASP runner first: ~/.local/bin/uv sync --frozen --no-dev' >&2
    exit 1
}
[[ -x "$repo_root/tools/ilasp/ILASP" ]] || { echo 'ILASP binary is not executable' >&2; exit 1; }

# Comprobamos la matriz antes de reservar recursos. Los dos algoritmos y las dos
# versiones de ILASP deben medir las mismas 29 tareas, diez veces y durante 1800 s.
"$repo_root/.venv/bin/python" - "$repo_root" \
    "$GENTIANS_STEADY_ID" "$GENTIANS_INCREMENTAL_ID" "$ILASP_EXPERIMENT_ID" <<'PY'
import sys
import tomllib
from pathlib import Path

root = Path(sys.argv[1])
steady_id, incremental_id, ilasp_id = sys.argv[2:]
gentians = tomllib.loads((root / "benchmarks/experiments.toml").read_text(encoding="utf-8"))
ilasp = tomllib.loads((root / "benchmarks/ilasp_experiments.toml").read_text(encoding="utf-8"))
gentians_by_id = {entry["id"]: entry for entry in gentians["experiment"]}
ilasp_by_id = {entry["id"]: entry for entry in ilasp["experiment"]}

try:
    steady = gentians_by_id[steady_id]
    incremental = gentians_by_id[incremental_id]
    ilasp_run = ilasp_by_id[ilasp_id]
except KeyError as error:
    raise SystemExit(f"Unknown campaign experiment: {error}") from error

datasets = steady["datasets"]
if len(datasets) != 29 or len(set(datasets)) != 29:
    raise SystemExit("The campaign must contain 29 distinct datasets")
for entry, algorithm in ((steady, "steady_state"), (incremental, "incremental")):
    if (entry["datasets"] != datasets or entry["runs"] != 10
            or entry["timeout_seconds"] != 1800
            or entry["overrides"].get("algorithm") != algorithm):
        raise SystemExit(f"Invalid Gentians campaign entry: {entry['id']}")
if (ilasp_run["datasets"] != datasets or ilasp_run["versions"] != ["2", "2i"]
        or ilasp_run["runs"] != 10 or ilasp_run["timeout_seconds"] != 1800
        or set(datasets) != set(ilasp_run["max_body_length"])):
    raise SystemExit(f"Invalid ILASP campaign entry: {ilasp_id}")
print("Campaign: 29 datasets × 10 runs × 4 methods = 1160 runs")
PY

mkdir -p -- "$script_dir/logs"

# afterany conserva la secuencia aunque un job termine con error o timeout.
# Cada ID tiene un directorio propio; revisa los logs si un job falla.
steady_job=$(sbatch --parsable \
    --job-name=gentians-steady-29x10 \
    --partition="$GENTIANS_SLURM_PARTITION" \
    --nodes=1 --ntasks=1 --cpus-per-task="$GENTIANS_SLURM_CPUS" \
    --mem="$GENTIANS_SLURM_MEM" --time="$GENTIANS_SLURM_TIME" \
    --chdir="$repo_root" \
    --output="$script_dir/logs/%x-%j.out" --error="$script_dir/logs/%x-%j.err" \
    --export="ALL,GENTIANS_EXPERIMENT_ID=$GENTIANS_STEADY_ID" \
    "$script_dir/job.sh")
printf 'Gentians steady_state: %s\n' "$steady_job"

incremental_job=$(sbatch --parsable \
    --dependency="afterany:$steady_job" \
    --job-name=gentians-incremental-29x10 \
    --partition="$GENTIANS_SLURM_PARTITION" \
    --nodes=1 --ntasks=1 --cpus-per-task="$GENTIANS_SLURM_CPUS" \
    --mem="$GENTIANS_SLURM_MEM" --time="$GENTIANS_SLURM_TIME" \
    --chdir="$repo_root" \
    --output="$script_dir/logs/%x-%j.out" --error="$script_dir/logs/%x-%j.err" \
    --export="ALL,GENTIANS_EXPERIMENT_ID=$GENTIANS_INCREMENTAL_ID" \
    "$script_dir/job.sh")
printf 'Gentians incremental: %s (after %s)\n' "$incremental_job" "$steady_job"

ilasp_job=$(sbatch --parsable \
    --dependency="afterany:$incremental_job" \
    --job-name=ilasp-29x10 \
    --partition="$GENTIANS_SLURM_PARTITION" \
    --nodes=1 --ntasks=1 --cpus-per-task="$GENTIANS_SLURM_CPUS" \
    --mem="$GENTIANS_SLURM_MEM" --time="$ILASP_SLURM_TIME" \
    --chdir="$repo_root" \
    --output="$script_dir/logs/%x-%j.out" --error="$script_dir/logs/%x-%j.err" \
    --export="ALL,ILASP_EXPERIMENT_ID=$ILASP_EXPERIMENT_ID" \
    "$script_dir/ilasp-job.sh")
printf 'ILASP 2 and 2i: %s (after %s)\n' "$ilasp_job" "$incremental_job"
