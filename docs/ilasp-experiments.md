# Comparación Gentians–ILASP: 29 benchmarks, 120 s

La matriz compara Gentians `steady_state`, Gentians `incremental` e ILASP.
Cada algoritmo de Gentians ejecuta 30 runs por dataset; ILASP ejecuta una sola
vez cada tarea y versión, porque la búsqueda es determinista. El timeout es
de 120 segundos. Por defecto se seleccionan ILASP `2` y `2i`: 1 798 ejecuciones
en total. Añadir `ilasp-3` e `ilasp-4` a `--methods` incluye las cuatro versiones y lleva el total
a 1 856. Un timeout no cancela las demás tareas o versiones.

Una sola entrada, `ilasp-all-120s-30runs`, vive en
`benchmarks/experiments.toml`. Define datasets, runs de Gentians, timeout y los
cuatro métodos por defecto una vez. Gentians usa instrumentación `full` para
conservar todos los datos del preview Vite y los defaults del SDK salvo el
algoritmo. `--methods` sustituye la selección de métodos de esa invocación;
ILASP siempre realiza una ejecución por tarea y versión. La configuración de
su ejecutable y traducción vive en `[tools.ilasp]` del mismo TOML.

## Tareas y espacio de cláusulas

Los nueve datasets existentes conservan sus `.las` con modes: `4queens`,
`5queens`, `adj2red`, `clique`, `coin`, `coloring`, `even_odd`, `grandparent`,
`sudoku`.

Los otros veinte declaran funciones de agregado en el cuerpo del language bias:

- `hamming_0`, `hamming_1`, `hamming_0_unbalanced`, `hamming_1_unbalanced`.
- `knapsack`, `latin_square`, `magic_square_no_diag`.
- `set_partition_sum`, `set_partition_sum_and_cardinality`,
  `set_partition_sum_cardinality_and_square`.
- `subset_sum`, `subset_sum_unbalanced`, `subset_sum_unbalanced_ops`,
  `subset_sum_double`, `subset_sum_double_unbalanced`,
  `subset_sum_double_unbalanced_count`, `subset_sum_double_and_sum`,
  `subset_sum_double_and_prod`, `subset_sum_double_and_prod_unbalanced`,
  `subset_sum_triple`.

Solo estos veinte usan el [formato explícito de ILASP](https://doc.ilasp.com/specification/explicit_hypothesis_space.html):

```prolog
2 ~ s(V1) :- #sum{V0:el(V0)}=V1.
```

`benchmarks/export_ilasp_aggregates.py` genera **todo el `ClauseSpace` canónico**
de cada tarea, incluidas sus cláusulas sin agregado. No selecciona reglas por
cobertura, por fitness ni a partir de la solución comentada. El coste entero
positivo es el número de literales de cuerpo más un átomo de cabeza para
reglas normales; las constraints no suman cabeza. Cada agregado cuenta como
un literal de cuerpo. El coste orienta la minimización de ILASP y no es el
score de Gentians.

El exportador conserva el background y los campos incluidos, excluidos y
contextos de los ejemplos. Traduce choices singleton sin límites como
`{el(1)}.` a `0 {el(1)} 1.`, exigido por el parser de ILASP y semánticamente
equivalente. No altera las tareas de Gentians. Los `.las` incluyen el SHA256
del texto fuente normalizado a UTF-8/LF; Git conserva LF en estos archivos
porque este ejecutable rechaza CRLF.

Para regenerar los veinte archivos versionados:

```bash
uv run python benchmarks/export_ilasp_aggregates.py
```

También se puede seleccionar uno con `--datasets subset_sum`. El exportador
rechaza datasets explícitamente seleccionados sin modes de agregado de cuerpo.

## Lanzamiento en Shelob / Linux nativo

ILASP está en `tools/ilasp/ILASP`, con permiso ejecutable en Git. Requiere
Linux x86_64, Python 3.10 y sus bibliotecas, libstdc++ y GNU `timeout`;
[requisitos del binario](../tools/ilasp/README.md). Shelob ya dispone de ellos.
El runner de benchmarks usa el Python del proyecto, distinto del Python 3.10
enlazado por ILASP.

Después de sincronizar esta revisión en `~/gentians`:

```bash
cd ~/gentians
export PATH="$HOME/.local/bin:$PATH"
uv sync
uv run python benchmarks/run_experiments.py ilasp-all-120s-30runs
```

Para elegir herramientas, algoritmos y versiones:

```bash
uv run python benchmarks/run_experiments.py ilasp-all-120s-30runs --methods gentians-steady_state gentians-incremental ilasp-2 ilasp-2i ilasp-3 ilasp-4
uv run python benchmarks/run_experiments.py ilasp-all-120s-30runs --methods gentians-incremental ilasp-2i
```

El runner ejecuta los métodos secuencialmente en la misma máquina. Evita
invocaciones simultáneas si vas a comparar tiempos. La primera orden lanza
la matriz completa.

## Windows con WSL

El runner detecta Windows y usa WSL; desde Linux, incluido un shell dentro de
WSL, ejecuta directamente. La configuración actual selecciona `kali-linux`
en Windows. `distro = "Ubuntu-22.04"` en `[tools.ilasp]` selecciona otra
distribución y `distro = ""` usa la predeterminada de WSL. Las rutas relativas se resuelven
desde la raíz del repositorio, independientemente del directorio de trabajo.

En la instalación local de Kali, el Python 3.10 auxiliar sigue estando en
`/tmp/ilasp-python310/root/usr`. Ese runtime no está incluido en Git y puede
desaparecer al limpiar `/tmp`; una distribución con las dependencias del binario
instaladas no lo necesita.

Añade este campo a la tabla `[tools.ilasp]` existente si necesitas ese runtime:

```toml
python_runtime = "/tmp/ilasp-python310/root/usr"
```

`python_runtime` es opcional y establece `PYTHONHOME` y `LD_LIBRARY_PATH`
solo para ILASP, con una ruta Linux. `executable` permite usar otro binario
mediante una ruta del repositorio o una ruta absoluta. Una ruta absoluta Linux
en Windows se interpreta dentro de WSL. No hay rutas temporales obligatorias
en la configuración versionada.

## Resultados y límites de comparación

Todos los métodos escriben en
`.benchmarks/experiments/ilasp-all-120s-30runs/<método>/`, cada uno con
`runs.csv`, `runs/` y manifest propio. Gentians conserva su
`dashboard_data.json` y las métricas que consume Vite. ILASP conserva stdout,
stderr y sus tiempos internos. El fingerprint incluye las tareas, el runner,
el runtime y el binario cuando es accesible desde Python.

Cada run guarda su hipótesis en `_hypothesis.lp.gz` si llegó a producir un
candidato, y su informe en `_validation.json.gz`. El comprobador independiente
`benchmarks/check_hypothesis.py` usa el background y los ejemplos originales;
solo reconoce los auxiliares aritméticos auditados de la traducción ILASP.
Crea un programa ASP nuevo por ejemplo, con contexto aislado, y guarda el
programa y su modelo testigo. Exige extensión para todos los positivos y
ausencia de extensión para todos los negativos. La validación tiene un
timeout propio (`validation_timeout_seconds`) y queda fuera de los tiempos
del learner. Un candidato ausente o una validación interrumpida no cuentan
como éxito.

```bash
uv run python benchmarks/run_experiments.py ilasp-all-120s-30runs --summary
```

El runner conserva resultados completos. `--force` reemplaza el directorio
de cada método seleccionado; úsalo solo para repetirlo deliberadamente.
Elegir otros métodos no altera los fingerprints ni las salidas de los demás.
Los resultados históricos no se reescriben ni se reducen a un run.
Si cambia el código o la configuración del método, el runner exige `--force`.
El índice usa el runtime guardado de cada método para no invalidar dashboards
de Gentians al ejecutarse después un job de ILASP fuera del contenedor.

En los veinte datasets explícitos, la generación del `ClauseSpace` se realiza
**antes** de medir ILASP. Gentians sí incluye generación de cláusulas dentro
de `total_execution`. Por tanto, estos tiempos no representan pipelines
equivalentes. En los nueve datasets con modes, ILASP genera su propio espacio.

El espacio explícito iguala las cláusulas individuales exportadas, no las
políticas de búsqueda de programas: Gentians aplica cierre de dependencias,
no vaciedad y `#maxpl`; ILASP usa sus propias condiciones y minimiza el coste
de las reglas. La exportación no impone un límite de número de reglas a ILASP.

ILASP usa `%% Total` como tiempo interno. GNU `timeout` envía SIGINT al llegar
a 120 s y concede cinco segundos antes de SIGKILL; ese margen no se añade a
PAR1. Wall-clock se conserva como dato operacional y no sustituye
`total_execution` de Gentians. Al publicar resultados, conserva también la
revisión del código y las versiones de Python, Clingo y el hardware.

Esta configuración no contiene resultados de la matriz completa.

## Campaña de 30 minutos por run

La nueva matriz `ilasp-all-1800s-10runs` conserva las 29 tareas anteriores.
Compara Gentians `steady_state` e `incremental` con ILASP 2 y 2i por defecto.
Cada algoritmo de Gentians realiza diez runs por dataset e ILASP realiza uno
por tarea y versión, con un límite de 1800 segundos por run: 638 runs en total.
Las cuatro versiones de ILASP llevan el total a 696. Los demás
parámetros de Gentians son los defaults del SDK; la instrumentación es `full`.

La única definición está en `benchmarks/experiments.toml`. Se lanza localmente con:

```powershell
uv run python benchmarks/run_experiments.py ilasp-all-1800s-10runs
```

Los `.las` y los límites `-ml` son los
mismos que en la matriz anterior. En los veinte datasets con agregados de
cuerpo, ILASP recibe el espacio explícito versionado y el tiempo de generarlo
queda fuera de sus runs. Por eso la comparación de tiempo completo entre
ambos sistemas mantiene esa limitación. Un timeout registra un resultado
censurado; la satisfacibilidad de la tarea no garantiza que cada método halle
una hipótesis dentro del presupuesto ni dentro de su espacio permitido.

`slurm/comparison.env` selecciona ese ID y los recursos. Desde la raíz
del checkout en Shelob, después de construir la imagen y sincronizar `uv`,
`bash slurm/submit-comparison.sh` envía los jobs en orden;
`bash slurm/submit-comparison.sh --methods gentians-steady_state gentians-incremental ilasp-2 ilasp-2i ilasp-3 ilasp-4`
elige las cuatro versiones junto a ambos algoritmos. Cada método tiene su
propio job. El log de cada job
registra nodo, commit y hash del ejecutable o imagen. Los resultados de esta
campaña todavía no se han medido.
