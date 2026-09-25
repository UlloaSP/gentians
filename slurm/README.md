# Gentians en Shelob

Esta carpeta contiene la construcción de la imagen Singularity y el envío a
Slurm. Las matrices siguen en `benchmarks/experiments.toml`; el runner guarda los
resultados en `.benchmarks/experiments/<id>`.

El flujo es:

1. `gentians.def` crea un entorno con Python 3.14 y las dependencias de
   producción fijadas por `uv.lock`.
2. `build.sh` construye `images/gentians.sif` y comprueba Python y Clingo dentro
   del SIF. Basta ejecutarlo al preparar o actualizar la imagen.
3. `submit.sh` valida el ID y envía `job.sh` a Slurm con los recursos y las rutas
   de log indicados.
4. `job.sh` monta el checkout en la misma ruta dentro del contenedor y ejecuta
   `benchmarks/run_experiments.py` con Singularity.

Desde la raíz del repositorio en Shelob, construye la imagen:

```bash
bash slurm/build.sh
```

Esta orden necesita que la cuenta tenga configurados los rangos de `--fakeroot`
en Shelob. Singularity obtiene la base OCI indicada en `gentians.def`; no necesita
el daemon Docker. `uv` instala las dependencias del lock durante la construcción.
Los jobs no instalan paquetes al arrancar. `slurm/images/` queda fuera de Git.

Envía un experimento definido en el TOML:

```bash
bash slurm/submit.sh sdk-defaults/steady_state
```

Por defecto se solicitan una CPU, 8 GiB de memoria, 36 horas y la partición
`no-gpu`. Son límites iniciales, no requisitos medidos para todos los datasets.
Puedes cambiarlos en un envío sin editar el script:

```bash
GENTIANS_SLURM_MEM=16G GENTIANS_SLURM_TIME=2-00:00:00 \
  bash slurm/submit.sh ilasp-all-120s-30runs/gentians-steady_state
```

`submit.sh` imprime el ID del job. Slurm escribe stdout y stderr en `slurm/logs/`;
el runner escribe los artefactos en `.benchmarks/experiments/<id>`. El
`timeout_seconds` del TOML limita **cada run**, mientras que el tiempo de Slurm
debe cubrir el experimento completo. El launcher no añade `--force`.

No envíes jobs simultáneos contra el mismo checkout: el runner escribe un índice
compartido. Mantén estable la ruta del checkout si quieres reutilizar resultados,
porque sus fingerprints incluyen rutas absolutas. El log del job registra el
commit y el SHA-256 de la imagen usada.

Si `sbatch` responde `Invalid account or account/partition combination`, el
administrador del clúster debe corregir la asociación de la cuenta en Slurm.
Cambiar el experimento o la imagen no resuelve ese error.

## Campaña Gentians–ILASP: 29 tareas, 10 runs, 30 minutos

`comparison.env` muestra exactamente los tres IDs que se enviarán y los recursos
de Slurm. Los dos IDs de Gentians están en `benchmarks/experiments.toml`; el de
ILASP está en `benchmarks/ilasp_experiments.toml`. Gentians ejecuta
`steady_state` e `incremental` con semillas 1–10; ILASP ejecuta solo las
versiones 2 y 2i, diez veces por tarea. Los tres experimentos comparten los
29 datasets y un límite de 1800 segundos **por run**: 1160 runs en total.

Después de hacer `git pull` en Shelob, prepara una vez la imagen y el entorno
del runner de ILASP. El binario ILASP usa Python 3.10 y las bibliotecas del
nodo; el runner usa Python 3.14 instalado con `uv`:

```bash
cd /mnt/experiments/pablo.ulloa/gentians
bash slurm/build.sh
~/.local/bin/uv sync --frozen --no-dev
```

La construcción con `--fakeroot` requiere rangos `subuid/subgid` para la cuenta.
Además, la cuenta necesita una asociación válida en Slurm para poder enviar
jobs. En la última comprobación en Shelob faltaban ambos requisitos.

Con el entorno preparado, envía toda la campaña desde la raíz con:

```bash
bash slurm/submit-comparison.sh
```

El lanzador valida la matriz y envía tres jobs secuenciales: Gentians
`steady_state`, Gentians `incremental` e ILASP 2/2i. La dependencia `afterany`
permite que el siguiente arranque incluso si el anterior termina con error;
comprueba los tres logs. `comparison.env` solicita 7 días para cada job de
Gentians y 14 para ILASP, porque cada uno agrupa cientos de runs. El timeout
de 30 minutos por run se define en los TOML, no en este archivo. El lanzador
no usa `--force`: un resultado completo se conserva y se omite. Si un job de
Gentians acaba a mitad de un experimento, su runner reinicia ese experimento
al relanzarlo; el runner de ILASP sí conserva los runs terminados.

Para observar la cola y los nodos:

```bash
squeue -u "$USER" -o '%.18i %.30j %.10T %.10M %.10l %.20R'
sinfo -p no-gpu -o '%N %t %C %m'
tail -f slurm/logs/gentians-steady-29x10-<job-id>.out
```

Los resultados quedan en `.benchmarks/experiments/ilasp-all-1800s-10runs/`
y `.benchmarks/experiments/ilasp/all-1800s-10runs/`. Las tareas con agregados
del cuerpo usan espacios de cláusulas explícitos y versionados para ILASP;
el tiempo de generarlos queda fuera de su medición. La configuración y los
límites de esta comparación están en `docs/ilasp-experiments.md`.
