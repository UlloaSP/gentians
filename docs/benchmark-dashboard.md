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

`timing.phase()` registra total inclusivo y `.self`; `instrumentation()` excluye
el overhead de serialización y logging; `net_time()` descuenta instrumentación.
Añade el coste de fitness a la fase que pidió la evaluación. `closure` mide
trabajo del constructor de hipótesis. No inventes fases para hacer una gráfica
más cómoda.

El resultado canónico de tiempo es `total_execution`, cerrado antes de imprimir
el programa. Wall-clock sirve para timeouts y operación del runner, nunca como
sustituto de esa métrica.

## Benchmarks

- Los task files viven en `benchmarks/gentians/`. Cambiarlos modifica el problema, no solo un fixture.
- `benchmarks/catalog.py` asigna nombres de dataset a `Arguments`.
- `benchmarks/profile_clauses.py` mide generación de `ClauseSpace` aislada.
- `benchmarks/profile_baseline.py` ejecuta runs, recoge JSON/JSONL, CSV y `.prof`, y genera `dashboard_data.json`.
- `benchmarks/run_experiments.py` carga TOML, aplica overrides, fingerprinta configuración y marca resultados stale cuando deja de coincidir.
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
compartidas. `main.jsx` muestra un experimento. `ExperimentCompare.jsx` y
`charts/ComparisonCharts.jsx` comparan varios. Si cambia el payload, actualiza
productor, `DASHBOARD_SCHEMA_VERSION`, consumidores y tests juntos. Un dashboard
viejo debe fallar como stale, no reinterpretarse silenciosamente: se regenera con
`run_experiments.py --rebuild-dashboards`, que vuelve a agregar los artefactos
crudos de `runs/` con el productor actual.

Las agregaciones las calcula el productor. `dashboard_data.json` lleva solo lo
que dibuja la UI: la media del progreso por eje ya calculada y, por run, hasta
300 puntos que conservan mejoras y reinicios. Los artefactos crudos por run son
la fuente para regenerarlo y no se cargan en el navegador.

## Contrato de charts

No cambies estas gráficas salvo petición explícita:

- Progreso de búsqueda: `max`, `best` y `avg`; eje inicial `generación`, empezando en generación `0`. Alterna a evaluaciones de fitness o segundos, los ejes que comparan steady-state e incremental con el mismo coste. En una ejecución, líneas discontinuas marcan los reinicios de población.
- Resultado de operadores: una sola categoría por pareja `operador:estrategia`. `duplicate` significa resultado repetido tras normalizar/cerrar, no una categoría duplicada.
- Cards de tiempos: deben mostrar `total`, `clauses`, `clingo` y `python`; `total` es la media de `total_execution`, nunca wall-clock. `clauses` y `tiempo evolutivo` van juntas.
- Fases: `clause generation`, `initialization`, `selection`, `crossover`, `mutation`, `replacement` y `search orchestration`. No existe fase separada `fitness evaluation`: su coste pertenece a la fase que solicitó la evaluación. En incremental, `replacement` incluye renovación de lotes, reinicios y sondas de constraints.
- Tipos horizontales de tiempo: exactamente `python`, `grounding`, `solving` y `closure`.
- Tabla solver y gráficas Clingo: una fila o categoría por cada fase que realmente pidió Clingo; ninguna fase se omite ni se agrupa.
- Épocas incrementales: épocas medias por run según su motivo de cierre. Steady-state no tiene épocas y lo indica en vez de mostrar ceros.
- Resultado: muestra el algoritmo, `candidatas` como el mayor `ClauseSpace` preparado por run y los reinicios medios por run.
- Modelos solve por etapa: usa fases reales; `clause_generation` se muestra como `clauses`. No agrupa fases conocidas como `search setup`, `fitness search` ni `other`.
- Los títulos de charts identifican la métrica y son funcionales. No añadas títulos de página, hero copy ni texto ornamental.
- Comparación conserva todas las gráficas y divisiones de la vista individual. Cada experimento añade sus líneas, grupos, stacks o anillos; no se reemplazan por resúmenes distintos.
- En comparación, el color identifica siempre al experimento; métricas y divisiones usan líneas, símbolos, opacidad o trama. Las leyendas no multiplican `experimento × división` y todo debe distinguirse sin hover.
- Tabla de comparación: no muestra wall-clock. Usa `total_execution` y su delta; `grounding`, `solving` y `python` con sus deltas; `ground calls` y `solve calls`.
