#!/usr/bin/env bash
set -euo pipefail

# submit.sh pasa el ID por el entorno de Slurm; sin él no hay experimento que ejecutar.
: "${GENTIANS_EXPERIMENT_ID:?Missing experiment ID}"
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
repo_root=$(dirname -- "$script_dir")
image="$script_dir/images/gentians.sif"

cd -- "$repo_root"
# Estos datos quedan en el log del job para identificar el código y la imagen usados.
printf 'Experiment: %s\nJob: %s\nNode: %s\n' \
    "$GENTIANS_EXPERIMENT_ID" "${SLURM_JOB_ID:-local}" "$(hostname)"
printf 'Commit: '
# La opción vale solo para esta orden: NFS muestra el checkout con otro propietario.
git -c "safe.directory=$repo_root" rev-parse HEAD || true
sha256sum -- "$image"

# Conservamos la misma ruta absoluta dentro del contenedor: el runner la incluye
# en los fingerprints. --cleanenv evita heredar Python o paquetes del nodo.
# exec hace que la salida y el código de retorno del runner sean los del job.
exec singularity exec --cleanenv \
    --bind "$repo_root:$repo_root" \
    --pwd "$repo_root" \
    "$image" python benchmarks/run_experiments.py "$GENTIANS_EXPERIMENT_ID"
