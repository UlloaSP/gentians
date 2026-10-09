#!/usr/bin/env bash
set -euo pipefail

# Cada envío ejecuta un ID declarado en benchmarks/experiments.toml.
# La forma del ID también impide introducir separadores o argumentos de shell.
if [[ $# -ne 1 || ! "$1" =~ ^[a-z0-9][a-z0-9_-]*(/[a-z0-9][a-z0-9_-]*)*$ ]]; then
    echo 'Usage: bash slurm/submit.sh <experiment-id>' >&2
    exit 2
fi

experiment_id=$1
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
repo_root=$(dirname -- "$script_dir")
image="$script_dir/images/gentians.sif"

command -v sbatch >/dev/null || { echo 'sbatch is required' >&2; exit 1; }
command -v singularity >/dev/null || { echo 'singularity is required' >&2; exit 1; }
[[ -f "$image" ]] || { echo "Build the image first: bash slurm/build.sh" >&2; exit 1; }
singularity sif list "$image" >/dev/null || { echo "Invalid image: $image" >&2; exit 1; }
# Validamos el ID con tomllib dentro de la imagen porque el Python del nodo es 3.10.
# Esto evita reservar recursos para un nombre que el runner rechazaría al arrancar.
singularity exec --cleanenv \
    --bind "$repo_root:$repo_root" --pwd "$repo_root" \
    "$image" python -c '
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]).parents[1]))
from benchmarks.run_experiments import load_config, expand_experiments
_, definitions = load_config(Path(sys.argv[1]))
methods = expand_experiments(definitions)
selected = [item for item in methods if sys.argv[2] in (item["id"], item["experiment_id"])]
if not selected:
    raise SystemExit(f"Unknown experiment: {sys.argv[2]}")
if any(item["tool"] != "gentians" for item in selected):
    raise SystemExit("Use submit-comparison.sh for experiments with external tools")
' "$repo_root/benchmarks/experiments.toml" "$experiment_id"

mkdir -p -- "$script_dir/logs"
# Slurm usa el nombre y el ID del job para producir logs distintos por envío.
job_name="gentians-${experiment_id//\//-}"
# Los valores GENTIANS_SLURM_* permiten ajustar recursos sin editar el script.
# El límite --time cubre el experimento entero, no el timeout de cada run.
# El runner recibe el ID; sus resultados quedan en .benchmarks/experiments/.
job_id=$(sbatch --parsable \
    --job-name="$job_name" \
    --partition="${GENTIANS_SLURM_PARTITION:-no-gpu}" \
    --nodes=1 --ntasks=1 \
    --cpus-per-task="${GENTIANS_SLURM_CPUS:-1}" \
    --mem="${GENTIANS_SLURM_MEM:-8G}" \
    --time="${GENTIANS_SLURM_TIME:-1-12:00:00}" \
    --chdir="$repo_root" \
    --output="$script_dir/logs/%x-%j.out" \
    --error="$script_dir/logs/%x-%j.err" \
    --export="ALL,EXPERIMENT_ID=$experiment_id" \
    "$script_dir/job.sh")
printf 'Submitted %s as Slurm job %s\n' "$experiment_id" "$job_id"
