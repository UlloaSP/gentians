# Medición, benchmarks y preview

Reglas para mantener la instrumentación, los experimentos y el preview Vite como
una sola cadena. Cómo lanzar experimentos: [benchmarks.md](benchmarks.md).

## Profiling y logging

La instrumentación se activa mediante rutas de entorno:

- `GENTIANS_TIMINGS_PATH`: totales y llamadas por métrica.
- `GENTIANS_GA_METRICS_PATH`: progreso por generación, incluida la marca de reinicio.
- `GENTIANS_INCREMENTAL_METRICS_PATH`: una fila por época del algoritmo incremental y el motivo de su cierre.
- `GENTIANS_CANDIDATE_METRICS_PATH`: tamaño y propiedades del espacio de reglas.
- `GENTIANS_OPERATOR_METRICS_PATH`: resultados de selección, crossover, mutation y replacement. El hijo del crossover solo tiene score si alguna evaluación ya lo cubrió, normalmente la clasificación de mutation.
- `GENTIANS_QUALITY_METRICS_PATH`: score, cobertura y tamaño del candidato.
- `GENTIANS_CLINGO_METRICS_PATH`: grounding, solving y estadísticas de Clingo.
- `GENTIANS_HYPOTHESIS_PATH`: checkpoint atómico de la mejor hipótesis evaluada, también durante inicialización. El tiempo de escritura se atribuye a instrumentación.

`timing.phase()` registra total inclusivo y `.self`; `instrumentation()` excluye
el overhead de serialización y logging; `net_time()` descuenta instrumentación.
Añade el coste de fitness a la fase que pidió la evaluación. `closure` mide
trabajo del constructor de hipótesis. No inventes fases para hacer una gráfica
más cómoda.
`timing.is_enabled()` refleja también la activación explícita con
`set_enabled(True)`, sin depender de que exista una ruta de entorno. La generación
de cláusulas activa sus clocks internos cuando timings o métricas Clingo los
necesitan; las métricas Clingo sin timings siguen conservando sus duraciones.
Esto no cambia campos, productor, `DASHBOARD_SCHEMA_VERSION` ni charts.

`benchmarks/profile_clause_python.py` aísla cargas reproducibles de compilación,
análisis y canonicalización, además de enumeración completa e incremental.
Reporta medianas y fingerprints deterministas; `--memory` mide las asignaciones
pico por separado, fuera de las muestras de tiempo. Los resultados son locales,
no un payload del dashboard. Protocolo y límites del experimento:
[optimización del Python de cláusulas](clause-python-optimizations.md).

`benchmarks/profile_clauses.py` imprime por defecto una tabla con benchmark,
número de cláusulas, segundos de generación, cláusulas por segundo, microsegundos
medios por cláusula y pico RSS de esa generación, sin guardar archivos. `--debug`
activa el informe detallado y los JSON. `--debug --cprofile` añade una segunda pasada independiente
con cProfile y un desglose por tiempos propios de funciones. Comprueba que el
`ClauseSpace` coincide y que todos los callbacks aparecen en el perfil. Guarda
`.prof` y un JSON local con funciones, buckets y entorno; los tiempos detallados
incluyen el efecto del profiler y no se escalan al total Python de la primera
pasada. Sus buckets no añaden fases a `timing.py` ni campos al productor,
schema o preview del dashboard. Límites y uso: [benchmarks.md](benchmarks.md).

El resultado canónico de tiempo es `total_execution`, cerrado antes de imprimir
el programa. Wall-clock sirve para timeouts y operación del runner, nunca como
sustituto de esa métrica.

La instrumentación guarda el primer checkpoint y el primer registro GA sin
esperar al siguiente evento. Después guarda durante la ejecución: eventos JSONL por
lotes de hasta 1024 filas y al llegar al siguiente evento tras un segundo;
timings también cada segundo y el historial GA cada diez segundos. Los snapshots
de timings incluyen las fases abiertas sin cerrar ni modificar sus acumuladores.
La escritura se atribuye a instrumentación. El cierre normal exporta las filas
pendientes y los totales definitivos. No cambia el formato de los artefactos,
el payload del productor, su schema ni el contrato de los charts del preview.

El timeout de Gentians permite que steady-state e incremental terminen la
operación en curso y devuelvan la mejor evaluación completa, incluso durante
inicialización. El runner da hasta cinco segundos adicionales para cerrar las
métricas y los recursos; conserva el estado `timeout` y el código 124. Si el
worker no responde, lo mata y conserva el último checkpoint: los eventos o
generaciones posteriores a ese guardado pueden faltar y el snapshot de recursos
queda censurado. Si no llegó a evaluar ningún candidato, no inventa una hipótesis.
El checkpoint de la mejor hipótesis tiene prioridad sobre el programa impreso
al final. Los datos perdidos por timeouts anteriores no se pueden reconstruir.
Su sustitución atómica reintenta hasta veinte veces los bloqueos temporales de
lectores, con pausas de 50 ms atribuidas a instrumentación. Un error persistente
se propaga conservando el checkpoint anterior; no se ignora ni cambia permisos.

Un crash del worker detiene el método, conserva el run fallido y sus artefactos,
y devuelve un código de error a Slurm. Los workers activan `faulthandler` para
conservar la traza de un fallo nativo. Los timeouts siguen el protocolo del
experimento; un `SIGKILL` anterior al plazo se registra como fallo, no como
timeout. La condición de éxito depende de la comprobación independiente de la
hipótesis guardada, también cuando se recupera de un checkpoint.
Los fingerprints incluyen el código C y las extensiones nativas disponibles,
además del código Python, los metaprogramas y las tareas.

Desde schema 14, `generation_worker` conserva por partición modelos, atoms,
rules, choices, conflicts y segundos de trabajo de grounding, solving y callback.
Los procesos se solapan: el productor excluye esas filas de `clingoSummary` y
los charts de tiempos de pared. `clause_generation.worker_*_work` tampoco se
resta del elapsed. Con particiones, el residual del padre incluye orquestación,
IPC y espera; no mide CPU Python de los hijos. `profile_clauses.py --debug`
muestra explícitamente la descomposición de pared como N/A y el trabajo agregado
por separado. cProfile con workers solo observa el padre, y comprueba el espacio
final sin afirmar que observa los callbacks de los hijos.

## Benchmarks

- Los task files viven en `benchmarks/gentians/`. Cambiarlos modifica el problema, no solo un fixture.
- `benchmarks/catalog.py` asigna nombres de dataset a `Arguments`.
- `benchmarks/profile_clauses.py` mide generación de `ClauseSpace` aislada. Con `--debug`, su informe distingue tiempos, throughput final, modelos posteriores al pruning ASP, retención posterior a la enumeración y pico RSS del proceso; [benchmarks.md](benchmarks.md) define los denominadores y límites. Schema 14 distingue el trabajo de los procesos de los tiempos de pared, conservando el contrato de los charts.
- `benchmarks/profile_baseline.py` ejecuta runs y guarda una sola copia cruda por run en `runs/`: log, recursos, timings, progreso y métricas por evento, todos comprimidos con gzip al terminar el run; solo un `.prof` de cProfile queda sin comprimir. Escribe `runs.csv` como índice y construye `dashboard_data.json` leyendo `runs/` dataset a dataset. No escribe copias concatenadas. Los lectores aceptan cada artefacto sin comprimir o como `.gz`.
- `benchmarks/run_experiments.py` carga el único TOML, selecciona herramientas y algoritmos con `--methods`, aplica overrides y controla fingerprints. Cada método guarda su manifest; el índice comprueba código y configuración usando el runtime registrado de ese método, aunque otro job se ejecute fuera de su contenedor.
- Gentians conserva sus métricas, `dashboard_data.json` y contrato de schema 20. Los métodos externos guardan tiempos propios y no fabrican fases de Gentians ni dashboards.
- Cada run guarda `_hypothesis.lp.gz` si produjo un candidato y `_validation.json.gz`. `benchmarks/check_hypothesis.py` crea un programa ASP independiente por ejemplo y comprueba la hipótesis completa con el background original y su contexto aislado. Guarda esos programas y los modelos testigo; un timeout del comprobador queda como desconocido. Esta validación tiene presupuesto propio y ocurre después de cerrar los tiempos del learner. `success` solo es verdadero si la comprobación pasa; `reported_success` conserva la declaración original de Gentians.
- `benchmarks/experiments.toml` reúne todas las matrices. Añade experimentos de investigación con IDs prefijados, como `pool-policy/control`, y una diferencia interpretable frente a su control. Conserva sus parámetros en el mismo archivo; no crees TOML separados.
- Resultados generados viven bajo `.benchmarks/experiments/<experimento>/` y están ignorados. No edites JSON o CSV generados a mano.
- Para comparar algoritmos, fija datasets, seeds, runs, timeout y todos los parámetros salvo la variable estudiada. Registra versión de Python, Clingo, hardware y revisión del código cuando publiques conclusiones.
- Cinco runs detectan efectos grandes, no establecen una tasa de éxito precisa. Lee éxito junto a tiempo y cobertura.
- `docs/search-space-experiments.md` registra ideas realmente medidas, variantes rechazadas y límites de la evidencia. No presentes una idea de esa tabla como implementación actual.

```powershell
uv sync
uv run python benchmarks/run_experiments.py --list
uv run python benchmarks/run_experiments.py <experiment-id>
uv run python benchmarks/profile_clauses.py --datasets <dataset>
```

Usa `--force` solo cuando se pretende reemplazar el resultado del experimento.
El runner borra el directorio exacto de salida antes de repetirlo.
En matrices de métodos borra solo `.benchmarks/experiments/<id>/<método>/`
para los métodos seleccionados; conserva los demás resultados.

## Preview de benchmarks

`.benchmarks/` contiene el código fuente Vite versionado. Todos los resultados,
snapshots y builds de experimentos viven en `.benchmarks/experiments/`, ignorado
como una unidad. La UI obtiene `experiments/experiments.json` y cada
`dashboard_data.json` relativo a ese índice; no calcula una verdad paralela al
agregador Python.

Desde `.benchmarks/`, con `vp`:

```powershell
vp i
vp dev
vp build
vp test
```

`src/metrics.js` define schema, orden de fases, tipos y agregaciones
compartidas. `main.jsx` muestra un experimento con todas sus gráficas.
`ExperimentCompare.jsx` compara varios con la tabla, el gráfico Pareto y la curva de runs resueltas. Si cambia el payload, actualiza
productor, `DASHBOARD_SCHEMA_VERSION`, consumidores y tests juntos. Un dashboard
viejo debe fallar como stale, no reinterpretarse silenciosamente: se regenera con
`run_experiments.py --rebuild-dashboards`, que vuelve a agregar los artefactos
crudos de `runs/` con el productor actual.

Las agregaciones las calcula el productor. `dashboard_data.json` lleva solo lo
que dibuja la UI: la media del progreso por eje ya calculada y, por run, hasta
300 puntos que conservan mejoras y reinicios. Los artefactos crudos por run son
la fuente para regenerarlo y no se cargan en el navegador.

Cada fila de `_quality_metrics` describe un candidato evaluado, en orden de
evaluación, e incluye desde schema 15 `positive_mask` y `negative_mask`: el bit
`i` en hexadecimal es el ejemplo `i` del orden de la tarea. El productor asigna
cada fila a su generación con las evaluaciones acumuladas del historial GA y
divide las generaciones del dataset en hasta 20 rangos iguales, compartidos por
todas sus runs. Para que la UI filtre por run y rango sin recalcular, `quality`
guarda por run las celdas `[positivos, negativos, rango, evaluados, best]`.
Desde schema 18 cada registro del historial GA describe la cobertura de la
población viva: `positive_coverage`, `negative_avoidance`,
`champion_negative_avoidance` y `behavior_diversity`; desde schema 19 el
dashboard añade la diversidad de programas, el tamaño medio y los reinicios de
cada run, `runCosts` con el coste en que terminó cada run y
`quality.finalCoverage` con la cobertura del mejor candidato de cada run
(máscaras de cobertura distintas / tamaño). `quality.populationCoverage`
conserva hasta 300 generaciones por run y la media, generación a generación,
de las runs que siguen buscando. Desde schema 20, `totalStd` es la desviación
típica muestral (n − 1) del `total_execution` de las runs medidas, o `null` con
menos de dos.
La dificultad por ejemplo usa las máscaras y los textos de los ejemplos, que
el productor lee de la tarea; las runs anteriores a schema 15 no tienen máscaras
y esa gráfica queda vacía.

## Contrato de charts

No cambies estas gráficas salvo petición explícita:

- Progreso de búsqueda: `max`, `best` y `avg`; eje inicial `generación`, empezando en generación `0`. Alterna a evaluaciones de fitness o segundos, los ejes que comparan steady-state e incremental con el mismo coste. En una ejecución, líneas discontinuas marcan los reinicios de población.
- Resultado de operadores: una sola categoría por pareja `operador:estrategia`. `duplicate` significa resultado repetido tras normalizar/cerrar, no una categoría duplicada.
- Cards de tiempos: deben mostrar `total`, `clauses`, `clingo` y `python`; `total` es la media de `total_execution` ± su desviación típica, nunca wall-clock. `clauses` y `tiempo evolutivo` van juntas.
- Fases: `clause generation`, `initialization`, `selection`, `crossover`, `mutation`, `replacement`, `renewal` y `search orchestration`. No existe fase separada `fitness evaluation`: su coste pertenece a la fase que solicitó la evaluación. `renewal` solo aparece en incremental: cambio de lote, relleno de la población y sondas de constraints tras el cambio. Los reinicios por estancamiento siguen en `replacement` en ambos algoritmos. Las ejecuciones anteriores al schema 13 cuentan la renovación dentro de `replacement`.
- Tipos horizontales de tiempo: exactamente `python`, `grounding`, `solving` y `closure`.
- Tabla solver y gráficas Clingo: una fila o categoría por cada fase que realmente pidió Clingo; ninguna fase se omite ni se agrupa.
- Épocas incrementales: épocas medias por run según su motivo de cierre. Steady-state no tiene épocas y lo indica en vez de mostrar ceros.
- Facilidad de satisfacer criterios de cobertura: tres barras apiladas al 100%. Positivos separa complete de incomplete, negativos separa consistent de inconsistent y combinado reparte los mismos candidatos en complete + consistent, solo complete, solo consistent y ninguno. Cada tramo lleva su nombre y porcentaje; el criterio cumplido usa el tono saturado y su complemento el mismo tono apagado.
- Candidatos evaluados por cobertura: positivos en X y negativos en Y invertido. Muestra la media de las runs o una ejecución, hasta un rango de generaciones; por defecto el último, con todas las evaluaciones. El color va de claro (inicio) a oscuro (final) según el rango medio de las evaluaciones; marca el frente no dominado y el punto ideal.
- Runs resueltas según coste: curva de éxito acumulado por generaciones, evaluaciones o segundos; el final es la tasa de éxito.
- Mejor individuo de cada run: cobertura del mejor candidato de cada run, resueltas y sin resolver por separado.
- Evolución de la cobertura: un punto por generación de la población viva, con los reinicios marcados en una ejecución: positivos cubiertos y negativos evitados de media, negativos evitados por el mejor individuo comportamientos de cobertura distintos, programas distintos y tamaño medio en el eje derecho; media de las runs que siguen buscando o una ejecución.
- Dificultad por ejemplo: porcentaje medio por run de evaluados que cumple cada ejemplo, de más difícil a más fácil dentro de positivos y negativos.
- Resultado: muestra el algoritmo, `candidatas` como el mayor `ClauseSpace` preparado por run y los reinicios medios por run.
- Modelos solve por etapa: usa fases reales; `clause_generation` se muestra como `clauses`. No agrupa fases conocidas como `search setup`, `fitness search` ni `other`.
- Los títulos de charts identifican la métrica y son funcionales. No añadas títulos de página, hero copy ni texto ornamental.
- Comparación muestra la tabla, el gráfico Pareto de tiempo frente a best encontrados, cuyo tooltip incluye la desviación típica del tiempo, y la curva de runs resueltas según coste de cada experimento. Las gráficas detalladas viven en la vista de cada experimento. En todos ellos el color identifica siempre al experimento.
- Tabla de comparación: no muestra wall-clock. Usa `total_execution` ± su desviación típica y su delta; `grounding`, `solving` y `python` con sus deltas; `ground calls` y `solve calls`.
