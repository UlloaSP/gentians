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
