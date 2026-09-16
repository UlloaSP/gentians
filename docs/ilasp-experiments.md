# Comparación Gentians–ILASP: 29 benchmarks, 30 runs, 120 s

La matriz compara Gentians `steady_state`, Gentians `incremental` e ILASP
`2`, `2i`, `3` y `4`. Cada sistema ejecuta 30 runs por dataset con timeout de
120 segundos: 5 220 ejecuciones en total. Gentians usa las semillas 1–30;
las repeticiones de ILASP no reciben una seed. Un timeout no cancela las
repeticiones restantes.

Las dos entradas de Gentians viven en `benchmarks/experiments.toml`, con
instrumentación `light` y los defaults del SDK salvo el algoritmo. La entrada
`all-120s-30runs` de `benchmarks/ilasp_experiments.toml` contiene las cuatro
versiones de ILASP. Estas entradas no sustituyen resultados de matrices anteriores.

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
uv run python benchmarks/run_experiments.py ilasp-all-120s-30runs/gentians-steady_state ilasp-all-120s-30runs/gentians-incremental
uv run python benchmarks/run_ilasp_experiments.py --config benchmarks/ilasp_experiments.toml all-120s-30runs
```

Ejecuta ambos comandos de benchmark secuencialmente en la misma máquina.
Cada runner es secuencial; evita ejecutar ambos a la vez si vas a comparar
tiempos. Los comandos anteriores lanzan la matriz completa, no solo una prueba.

## Windows con WSL

El runner detecta Windows y usa WSL; desde Linux, incluido un shell dentro de
WSL, ejecuta directamente. La configuración actual selecciona `kali-linux`
en Windows. `--distro Ubuntu-22.04` selecciona otra distribución y
`--distro ""` usa la predeterminada de WSL. Las rutas relativas se resuelven
desde la raíz del repositorio, independientemente del directorio de trabajo.

En la instalación local de Kali, el Python 3.10 auxiliar sigue estando en
`/tmp/ilasp-python310/root/usr`. Ese runtime no está incluido en Git y puede
desaparecer al limpiar `/tmp`; una distribución con las dependencias del binario
instaladas no lo necesita.

```powershell
uv run python benchmarks/run_ilasp_experiments.py all-120s-30runs --distro kali-linux --python-runtime /tmp/ilasp-python310/root/usr
```

`--python-runtime` es opcional y establece `PYTHONHOME` y `LD_LIBRARY_PATH`
solo para ILASP, con una ruta Linux. `--executable` permite usar otro binario
mediante una ruta del repositorio o una ruta absoluta. Una ruta absoluta Linux
en Windows se interpreta dentro de WSL. No hay rutas temporales obligatorias
en la configuración versionada.

## Resultados y límites de comparación

Gentians escribe en `.benchmarks/experiments/ilasp-all-120s-30runs/`;
ILASP, en `.benchmarks/experiments/ilasp/all-120s-30runs/`. ILASP conserva
stdout y stderr por ejecución, `runs.csv`, `summary.csv` y un manifest con
configuración, fingerprint y datos del host. El fingerprint incluye las tareas,
el runner y el binario cuando es accesible desde el proceso Python.

```bash
uv run python benchmarks/run_ilasp_experiments.py all-120s-30runs --summary
uv run python benchmarks/run_experiments.py ilasp-all-120s-30runs/gentians-steady_state ilasp-all-120s-30runs/gentians-incremental --summary
```

Los runners conservan resultados completos. `--force` reemplaza el directorio
del experimento seleccionado; úsalo solo para repetirlo deliberadamente.

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
