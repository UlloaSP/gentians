#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 0 ]]; then
    echo 'Usage: bash slurm/build.sh' >&2
    exit 2
fi

# Localizamos la raíz a partir de este script para poder invocarlo desde cualquier directorio.
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
repo_root=$(dirname -- "$script_dir")
image_dir="$script_dir/images"
image="$image_dir/gentians.sif"
# Construimos con otro nombre y sustituimos la imagen final solo tras verificarla.
temporary_image="$image_dir/gentians.$$.tmp.sif"

command -v singularity >/dev/null || { echo 'singularity is required' >&2; exit 1; }
mkdir -p -- "$image_dir"
# Si falla algún paso, retiramos únicamente la imagen temporal de este proceso.
trap 'rm -f -- "$temporary_image"' EXIT

cd -- "$repo_root"
# %files en gentians.def toma pyproject.toml y uv.lock desde esta raíz.
# --fakeroot necesita los rangos /etc/subuid y /etc/subgid de esta cuenta.
singularity build --fakeroot "$temporary_image" "$script_dir/gentians.def"
# Comprobamos el intérprete y Clingo dentro del SIF antes de publicarlo.
singularity exec --cleanenv "$temporary_image" python -c \
    'import sys, clingo; assert sys.version_info >= (3, 14); assert clingo.__version__ == "5.8.2"'
mv -f -- "$temporary_image" "$image"
echo "Image ready: $image"
