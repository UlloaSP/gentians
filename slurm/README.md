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

## Campaña Gentians–ILASP: 29 tareas, 30 minutos por run

`comparison.env` selecciona `COMPARISON_EXPERIMENT_ID` y los recursos
de Slurm. La única definición vive en `benchmarks/experiments.toml` y declara
los métodos por defecto. Gentians ejecuta
`steady_state` e `incremental` diez veces por tarea; ILASP ejecuta una sola
vez cada tarea y versión. Por defecto usa 2 y 2i. Todos los métodos comparten
los 29 datasets y un límite de 1800 segundos **por run**: 638 runs en total.

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

Selecciona herramientas y algoritmos con el mismo flag del runner local:

```bash
bash slurm/submit-comparison.sh --methods gentians-incremental ilasp-2i
bash slurm/submit-comparison.sh --methods gentians-steady_state gentians-incremental ilasp-2 ilasp-2i ilasp-3 ilasp-4
```

Con los dos algoritmos y las cuatro versiones se ejecutan 696 runs. Cada
job recibe `EXPERIMENT_ID` y `EXPERIMENT_METHOD`, y llama al runner común
con `--methods` para ejecutar solo su método.

El lanzador valida la matriz y envía un job por método, cuatro por defecto:
Gentians `steady_state`, Gentians `incremental`, ILASP 2 e ILASP 2i.
La dependencia `afterany`
permite que el siguiente arranque incluso si el anterior termina con error;
comprueba los logs de cada método. `comparison.env` solicita 7 días para cada job de
Gentians y 3 para cada versión de ILASP. El timeout
de 30 minutos por run se define en el TOML común. El lanzador
no usa `--force`: un resultado completo se conserva y se omite. Si un job de
Gentians acaba a mitad de un experimento, su runner reinicia ese experimento
al relanzarlo; el runner de ILASP sí conserva los runs terminados.

Para observar la cola y los nodos:

```bash
squeue -u "$USER" -o '%.18i %.30j %.10T %.10M %.10l %.20R'
sinfo -p no-gpu -o '%N %t %C %m'
tail -f slurm/logs/gentians-steady_state-<job-id>.out
```

Los resultados quedan en `.benchmarks/experiments/ilasp-all-1800s-10runs/<método>/`.
Gentians conserva los dashboards para Vite. Cada run guarda su hipótesis y la
comprobación ASP independiente contra los ejemplos originales. El índice
conserva el runtime registrado de cada método, por lo que los jobs nativos de
ILASP pueden actualizarlo sin invalidar resultados del contenedor. Las tareas con agregados
del cuerpo usan espacios de cláusulas explícitos y versionados para ILASP;
el tiempo de generarlos queda fuera de su medición. La configuración y los
límites de esta comparación están en `docs/ilasp-experiments.md`.
