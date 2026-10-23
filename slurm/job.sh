#!/usr/bin/env bash
set -euo pipefail

# submit.sh pasa el ID por el entorno de Slurm; sin él no hay experimento que ejecutar.
: "${EXPERIMENT_ID:?Missing experiment ID}"
if [[ -n ${SLURM_JOB_ID:-} ]]; then
    # Slurm copia el script al spool; --chdir conserva la raíz del checkout.
    repo_root=$(pwd -P)
else
    script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
    repo_root=$(dirname -- "$script_dir")
fi
script_dir="$repo_root/slurm"
image="$script_dir/images/gentians.sif"

cd -- "$repo_root"
# Estos datos quedan en el log del job para identificar el código y la imagen usados.
printf 'Experiment: %s\nJob: %s\nNode: %s\n' \
    "$EXPERIMENT_ID" "${SLURM_JOB_ID:-local}" "$(hostname)"
printf 'Commit: '
# La opción vale solo para esta orden: NFS muestra el checkout con otro propietario.
git -c "safe.directory=$repo_root" rev-parse HEAD || true
sha256sum -- "$image"

# Conservamos la misma ruta absoluta dentro del contenedor: el runner la incluye
# en los fingerprints. --cleanenv evita heredar Python o paquetes del nodo.
# exec hace que la salida y el código de retorno del runner sean los del job.
# Las unidades van en secuencia y Clingo genera las cláusulas en un solo hilo:
# los tiempos no dependen de cuántos procesos compartan el nodo. --force deja que
# un job reencolado por Slurm repita el experimento aunque cambie su config; el
# runner de Gentians reinicia el experimento igualmente. El mismo --set en
# ilasp-job.sh mantiene coherente el índice compartido.
runner_args=("$EXPERIMENT_ID" --force --set 'clause_generation.clingo_arguments=[]')
if [[ -n ${EXPERIMENT_METHOD:-} ]]; then
    runner_args+=(--methods "$EXPERIMENT_METHOD")
fi
exec singularity exec --cleanenv \
    --bind "$repo_root:$repo_root" \
    --pwd "$repo_root" \
    "$image" python benchmarks/run_experiments.py "${runner_args[@]}"
