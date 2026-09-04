# Gentians

Gentians es un solver de Inductive Logic Programming para aprender programas ASP. Su objetivo es buscar hipótesis no monótonas expresadas con sintaxis ASP mediante una heurística evolutiva. Clingo cumple dos papeles distintos: enumera cláusulas legales a partir del language bias y evalúa la semántica del programa candidato completo.

Gentians no es una librería genética genérica ni un wrapper genérico de Clingo. El algoritmo evolutivo existe para explorar programas ASP válidos sin perder sus invariantes sintácticos y semánticos.

## Reglas de trabajo

- Usa los skills `unslop`, `caveman` y `ponytail` en modo ultra en cada turno. Lee sus instrucciones antes de actuar. Mantén el chat corto, pero escribe documentación durable con frases completas y precisas.
- Entiende el flujo completo antes de editar. Localiza consumidores, invariantes y tests del concepto tocado.
- Implementa el cambio mínimo en la capa propietaria del concepto. Reutiliza stdlib, Clingo y código existente antes de añadir abstracciones o dependencias.
- Conserva cambios ajenos del worktree. El repositorio puede contener experimentos sin commit.
- Si haces smoke tests temporales, elimínalos al terminar.
- Para el proyecto Vite de `.benchmarks/`, usa `vp` desde ese directorio.
- Cambia APIs internas de forma directa. Actualiza todos los usos en el mismo cambio. No dejes wrappers, adaptadores temporales, adaptadores sobre adaptadores ni capas de compatibilidad innecesarias.
- Un cambio de rendimiento necesita medición reproducible. Una intuición sobre Clingo, grounding o búsqueda no cuenta como resultado.

## Modelo mental

El flujo actual es:

```text
task file
  -> language lexer + parser + validación
  -> InductiveTask, IR de la tarea inductiva
  -> análisis estático + compilación de modes
  -> facts + metaprograma ASP
  -> Clingo enumera y poda cláusulas
  -> decode + canonicalización
  -> ClauseSpace
  -> HypothesisGenerator construye genomas cerrados
  -> steady_state_genetic_search aplica estrategias evolutivas
  -> CandidateEvaluator obtiene cobertura y score del programa completo
  -> mejor hipótesis + score + best_found

instrumentación -> artefactos de benchmark -> preview Vite
```

La distinción entre cláusulas e hipótesis es obligatoria:

- `generate_clause_space()` genera el espacio finito de cláusulas individuales, un `ClauseSpace`.
- `HypothesisGenerator` construye hipótesis completas a partir de ese `ClauseSpace`, mantiene cierre de dependencias y las codifica como bitsets.
- Una cláusula no tiene cobertura o fitness estable por sí sola. ASP es no monótono y añadir una cláusula puede cambiar los modelos del programa completo.

No introduzcas optimizaciones que asuman contribuciones aditivas, cobertura fija por regla o equivalencia global a partir de los ejemplos. Una firma de cobertura solo expresa comportamiento sobre la tarea observada.

## Vocabulario canónico

Usa estos términos en código, docs y conversación:

- **Tarea inductiva**: archivo que contiene background ASP, ejemplos y language bias. También posee los límites estructurales.
- **`InductiveTask`**: IR parseado de la tarea inductiva. No es la hipótesis aprendida.
- **Language bias**: lenguaje finito permitido para las hipótesis. Incluye modes, recalls, tipos, direcciones, constantes, límites, metarules, invención y `#bias` explícito.
- **Cláusula**: una cláusula ASP aprendible ya instanciada y canónica.
- **`Clause`**: AST y texto canónico de una cláusula junto a predicados definidos, dependencias, tamaño de cuerpo y bundle opcional.
- **`ClauseSpace`**: conjunto ordenado y sin duplicados de cláusulas candidatas.
- **Hipótesis o programa candidato**: conjunto de cláusulas del `ClauseSpace` evaluado como una unidad bajo stable-model semantics.
- **`Genome`**: entero bitset que representa una hipótesis. El bit `i` selecciona la cláusula `i` del `ClauseSpace` preparado.
- **`Individual`**: genoma evaluado con score, marca de solución, firma de comportamiento y edad.
- **`SearchResult`**: hipótesis elegida, score y marca de solución devueltos por cualquier algoritmo completo.
- **Comportamiento**: pareja de máscaras `(pos_mask, neg_mask)`. La primera marca positivos cubiertos; la segunda, negativos cubiertos.
- **`Coverage`**: valor inmutable con las máscaras de comportamiento producidas por Clingo.
- **`EvaluationResult`**: score, marca de solución y comportamiento de un programa candidato evaluado.
- **Hipótesis perfecta**: cubre todos los ejemplos positivos y ningún negativo. Esto produce `best_found=True`.
- **Cierre de dependencias**: toda dependencia de una cláusula queda definida por el background o por alguna cabeza del mismo candidato.
- **Bundle**: grupo de cláusulas producido por una metarule. Es atómico durante generación y operadores.
- **Pruning**: exclusión de cláusulas o hipótesis inválidas, redundantes o imposibles antes de gastar evaluaciones de fitness.
- **`CoverageSolver`**: crea, groundea y resuelve un `clingo.Control` por candidato para obtener `Coverage`.

Usa `ClauseSpace` para cláusulas candidatas. Usa hipótesis o programa candidato para el conjunto evaluado por fitness.

## Semántica del producto

Una tarea puede declarar background ASP, ejemplos positivos y negativos con contexto opcional, límites `#maxv/#maxbl/#minhl/#maxhl/#maxpl`, heads normales, disyuntivas, choice o cardinalidad, negación fuerte, negación por defecto, variables tipadas y dirigidas, constantes, términos anidados, condicionales, aggregates, arithmetic, comparisons, predicate invention, metarules de segundo orden y meta-ASP mediante `#bias`.

`docs/language-bias.md` es el contrato de sintaxis y significado. Léelo completo antes de cambiar lexer, grammar, parser, modes, generación o pruning. `README.md` es el resumen de uso, no una segunda especificación.

Reglas semánticas que deben sobrevivir cualquier refactor:

- La tarea posee su significado. `Arguments` configura ejecución y estrategias, no redefine el language bias.
- Los tipos son nominales. Coincidencia de valores ground no une dominios.
- `input` debe estar ligado, `output` lo produce un literal positivo y `any` desactiva deliberadamente la restricción de flujo. Negación por defecto no produce variables.
- Los límites estructurales y recalls deben mantener finito el espacio. `*` significa ilimitado solo cuando los demás límites siguen cerrando el dominio.
- `#modeh` describe una cabeza completa. `#modeha` combina elementos choice/cardinality. `#modehd` combina elementos disyuntivos. Un recall nunca transforma una forma en otra.
- `#bias` admite reglas y constraints duros y define predicados reservados `bias_*`. No admite weak constraints ni directivas globales.
- Contextos de ejemplos se aíslan por selector. Un contexto nunca filtra hechos o constraints hacia otro ejemplo.
- Fitness fuerza consecuencias brave. Evalúa el programa candidato completo.
- Cada evaluación usa el solver normal y un `clingo.Control` nuevo.
- Canonicalización preserva semántica ASP. Deduplicar texto, renombrado de variables o sistemas aritméticos no autoriza aproximaciones semánticas.
- Dependencias con negación fuerte conservan el signo. `p/n` y `-p/n` son predicados distintos para cierre y recursión.

## Arquitectura objetivo y ubicación actual

Estos son límites del producto, aunque algunos todavía compartan paquete:

| Módulo | Responsabilidad | Ubicación actual |
|---|---|---|
| Lenguaje de tareas | Leer UTF-8, separar sentencias completas, parsear directivas, delegar ASP a `clingo.ast` y construir un IR tipado. | `gentians/language/parser.py`, `lexer.py`, `grammar.py`, `asp.py`, `directives.py`, `declarations.py`, `modes.py`, `metarules.py`, `language/ir/` |
| Generación de cláusulas | Compilar bias y análisis estático a facts, enumerar cláusulas mediante metaprograma ASP, podar ilegalidad y redundancia, decodificar y canonicalizar. | `gentians/clauses/generator.py`, `clauses/metaprogram/**/*.lp`, `ClauseSpace` |
| Generación de hipótesis | Construir programas candidatos, aplicar pruning mientras nacen y cerrar dependencias bajo `#maxpl` y bundles. | `gentians/hypotheses/` |
| Algoritmos de búsqueda | Resolver una tarea completa y devolver `SearchResult`. Cada algoritmo posee su bucle; la implementación actual es un GA de estado estable. | `gentians/algorithms/` |
| Evolución | Proveer individuo, contexto, operadores y estrategias usados por algoritmos evolutivos. | `gentians/evolution/` |
| Evaluación | Compilar ejemplos, obtener cobertura con Clingo y convertirla en score y condición de solución. | `gentians/evaluation/` |
| Docs | Mantener lenguaje, decisiones, arquitectura y experimentos con resultados. | `docs/`, `README.md` |
| Profiling y logging | Medir tiempo neto, fases, calidad, operadores y estadísticas Clingo sin contaminar la métrica observada. | `gentians/timing.py`, `gentians/clingo_stats.py` |
| Benchmarks y runners | Definir datasets, matrices reproducibles, aislamiento, fingerprints y agregación. | `benchmarks/`, `benchmarks/gentians/` |
| Preview de benchmarks | Leer artefactos generados y mostrar detalle y comparación sin reinterpretar métricas. | `.benchmarks/` |

No crees paquetes vacíos para imitar esta tabla. Haz aparecer un límite físico cuando tenga lógica propia y reduzca acoplamiento real. Si mueves una frontera, conecta directamente todos los usos y elimina la ubicación anterior.

La tabla mezcla destino y estado real a propósito. La generación de hipótesis completas usa un bitset engine en Python; logging no tiene aún un módulo general separado de timing, métricas y callbacks. Trátalos como límites de producto pendientes, no como funciones ya implementadas ni como permiso para un refactor masivo no solicitado.

## Cómo se genera una cláusula

`parse_file()` lee UTF-8 y delega en `parse_text()`. El lexer separa sentencias completas sin romper strings, comentarios, delimitadores anidados, rangos o anotaciones. El parser orquesta las declaraciones y construye `InductiveTask`; `directives`, `declarations`, `modes` y `metarules` contienen sus gramáticas específicas. Clingo sigue siendo la autoridad para la gramática y el AST de ASP. El background se parsea en una sola llamada preservando las líneas originales; en ejemplos solo se parsean los campos no vacíos. `InductiveTask` conserva background, átomos incluidos y excluidos, contextos, `#bias` y metarules como nodos `clingo.ast.AST`; `Clause` conserva el nodo de cada cláusula candidata junto al texto canónico de salida. Los solvers reciben los nodos mediante `ProgramBuilder`, sin volver a parsear el ASP retenido.

`generate_clause_space()` ejecuta este pipeline:

1. Inspecciona background, ejemplos y declaraciones para derivar tipos, dominios, closed-world properties y capacidades permitidas.
2. Compila declaraciones a `ClauseMode` y facts reificados.
3. Carga los módulos `.lp` en el orden de `CLAUSE_METAPROGRAM_MODULES`.
4. Clingo aplica límites, recall, linkedness, typing, ASP safety, flujo dirigido, coherencia y propiedades de pruning durante enumeración.
5. Python decodifica `selected/3` y `var_at/4` como `ReifiedClause`.
6. `_theta_reduced` elimina cuerpos con subcláusulas theta-equivalentes.
7. `ArithmeticSystem` normaliza relaciones conectadas y `canonical.key` elige un representante.
8. `ClauseSpace` ordena y deduplica `Clause`.

Prefiere pruning declarativo en los módulos `.lp` cuando la condición depende de la selección reificada. Usa Python para análisis estático de la tarea, AST, decodificación o canonicalización que no conviene recomputar dentro del solver. Evita generar un dominio enorme para filtrarlo después.

Un cambio de lenguaje suele tocar lexer, parser, IR, compilación de modes/facts, metaprograma, decoder/render, `docs/language-bias.md` y tests de hipótesis. Recorre esa cadena completa. Una nueva sintaxis sin semántica de generación, o nueva semántica sin documentación, está incompleta.

## Cómo se genera y busca una hipótesis

`HypothesisGenerator` es la única autoridad para construir o transformar genomas. Prepara el `ClauseSpace`, elimina cláusulas imposibles de cerrar y mantiene índices de heads, dependencies y bundles. Creación, append, remove, replace y crossover terminan en `_build()` y `_complete()`.

Invariantes del candidato:

- No está vacío.
- Solo contiene cláusulas del espacio preparado.
- No excede `#maxpl`.
- Incluye bundles completos.
- Todas sus dependencias tienen proveedor en background o en el candidato.
- Una transición destructiva no puede reintroducir la regla o bundle marcado como forbidden para reparar su propia eliminación.

Las estrategias no editan bits arbitrariamente. Selección opera sobre `Individual`; population, crossover y mutation piden genomas válidos a `HypothesisGenerator`; replacement conserva tamaño y orden por score. Los protocolos viven en `evolution/operator_types.py` y el estado compartido mínimo en `EvolutionContext`.

`steady_state_genetic_search` es el bucle del GA de estado estable. Construye factories desde `Arguments`, crea o acepta un `ClauseSpace`, inicializa población, memoiza evaluaciones, registra generación 0, aplica selección, crossover, mutación y replacement, y termina al encontrar una hipótesis perfecta o agotar generaciones. `iterations_genetic=0` significa búsqueda sin límite de generaciones.

Al añadir una estrategia:

- Implementa un archivo y una clase top-level. `tests/test_strategy_layout.py` protege ese layout.
- Cumple el callable type existente. Extiende el protocolo solo si la categoría completa necesita datos nuevos.
- Regístrala en la factory de su subpaquete.
- Delega construcción y cierre a `HypothesisGenerator`.
- Usa el `random.Random` inyectado para reproducibilidad.
- Añade tests del comportamiento observable y de los invariantes, no tests que copien la implementación.

El archivo semántico agrupa por `Behavior` y conserva los `k` programas más cortos. Es una poda respecto a ejemplos presentes, no equivalencia ASP. `module_mix` transfiere cierres sintácticos de soporte, no módulos semánticos ASP.

## Evaluación y Clingo

`create_evaluator()` elige la estrategia de score `cov_program` o `cov_balanced`. Ambas reciben `Coverage`; `CandidateEvaluator` devuelve `EvaluationResult` con score, comportamiento y estados de completitud y consistencia, y comparte condición de éxito y `CoverageSolver`.

El solver normal crea un `Control` por evaluación, añade background, programa estático de cobertura y candidato desde AST ya retenido, groundea y resuelve.

Antes de cambiar cobertura, prueba al menos inclusión, exclusión, tarea vacía en uno de los lados, contexts aislados y negación por defecto.

## Profiling y logging

La instrumentación se activa mediante rutas de entorno:

- `GENTIANS_TIMINGS_PATH`: totales y llamadas por métrica.
- `GENTIANS_GA_METRICS_PATH`: progreso por generación.
- `GENTIANS_CANDIDATE_METRICS_PATH`: tamaño y propiedades del espacio de reglas.
- `GENTIANS_OPERATOR_METRICS_PATH`: resultados de selección, crossover, mutation y replacement.
- `GENTIANS_QUALITY_METRICS_PATH`: score, cobertura y tamaño del candidato.
- `GENTIANS_CLINGO_METRICS_PATH`: grounding, solving y estadísticas de Clingo.

`timing.phase()` registra total inclusivo y `.self`; `instrumentation()` excluye el overhead de serialización y logging; `net_time()` descuenta instrumentación. Añade el coste de fitness a la fase que pidió la evaluación. `closure` mide trabajo del constructor de hipótesis. No inventes fases para hacer una gráfica más cómoda.

El resultado canónico de tiempo es `total_execution`, cerrado antes de imprimir el programa. Wall-clock sirve para timeouts y operación del runner, nunca como sustituto de esa métrica.

## Benchmarks

- Los task files viven en `benchmarks/gentians/`. Cambiarlos modifica el problema, no solo un fixture.
- `benchmarks/catalog.py` asigna nombres de dataset a `Arguments`.
- `benchmarks/profile_clauses.py` mide generación de `ClauseSpace` aislada.
- `benchmarks/profile_baseline.py` ejecuta runs, recoge JSON/JSONL, CSV y `.prof`, y genera `dashboard_data.json`.
- `benchmarks/run_experiments.py` carga TOML, aplica overrides, fingerprinta configuración y marca resultados stale cuando deja de coincidir.
- `benchmarks/experiments.toml` es la matriz ordinaria. Configs de investigación separadas deben declarar una sola diferencia interpretable frente al control.
- Resultados generados viven bajo `.benchmarks/<experimento>/` y están ignorados. No edites JSON o CSV generados a mano.
- Para comparar algoritmos, fija datasets, seeds, runs, timeout y todos los parámetros salvo la variable estudiada. Registra versión de Python, Clingo, hardware y revisión del código cuando publiques conclusiones.
- Cinco runs detectan efectos grandes, no establecen una tasa de éxito precisa. Lee éxito junto a tiempo y cobertura.
- `docs/search-space-experiments.md` registra ideas realmente medidas, variantes rechazadas y límites de la evidencia. No presentes una idea de esa tabla como implementación actual.

Comandos habituales:

```powershell
uv sync
uv run python benchmarks/run_experiments.py --list
uv run python benchmarks/run_experiments.py <experiment-id>
uv run python benchmarks/profile_clauses.py --datasets <dataset>
```

Usa `--force` solo cuando se pretende reemplazar el resultado del experimento. El runner borra el directorio exacto de salida antes de repetirlo.

## Preview de benchmarks

`.benchmarks/` contiene a la vez código fuente Vite versionado y resultados locales ignorados. La UI obtiene `experiments.json` y cada `dashboard_data.json`; no calcula una verdad paralela al agregador Python.

Desde `.benchmarks/`:

```powershell
vp i
vp dev
vp build
vp test
```

`src/metrics.js` define schema, orden de fases, tipos y agregaciones compartidas. `main.jsx` muestra un experimento. `ExperimentCompare.jsx` y `charts/ComparisonCharts.jsx` comparan varios. Si cambia el payload, actualiza productor, `DASHBOARD_SCHEMA_VERSION`, consumidores y tests juntos. Un dashboard viejo debe fallar como stale, no reinterpretarse silenciosamente.

## Contrato de charts de benchmarks

No cambies estas gráficas salvo petición explícita:

- Progreso de búsqueda: `max`, `best` y `avg`; eje inicial `generación`, empezando en generación `0`. Puede alternar a evaluaciones de fitness o segundos.
- Resultado de operadores: una sola categoría por pareja `operador:estrategia`. `duplicate` significa resultado repetido tras normalizar/cerrar, no una categoría duplicada.
- Cards de tiempos: deben mostrar `total`, `clauses`, `clingo` y `python`; `total` es la media de `total_execution`, nunca wall-clock. `clauses` y `tiempo evolutivo` van juntas.
- Fases: `clause generation`, `pregrounding`, `initialization`, `selection`, `crossover`, `mutation`, `replacement` y `search orchestration`. No existe fase separada `fitness evaluation`: su coste pertenece a la fase que solicitó la evaluación.
- Tipos horizontales de tiempo: exactamente `python`, `grounding`, `solving` y `closure`.
- `pregrounding` solo mide creación y grounding del solver pregenerado; ejecución normal no inventa esa fase.
- Modelos solve por etapa: usa fases reales; `clause_generation` se muestra como `clauses`. No agrupa fases conocidas como `search setup`, `fitness search` ni `other`.
- Los títulos de charts identifican la métrica y son funcionales. No añadas títulos de página, hero copy ni texto ornamental.
- Comparación conserva todas las gráficas y divisiones de la vista individual. Cada experimento añade sus líneas, grupos, stacks o anillos; no se reemplazan por resúmenes distintos.
- En comparación, el color identifica siempre al experimento; métricas y divisiones usan líneas, símbolos, opacidad o trama. Las leyendas no multiplican `experimento × división` y todo debe distinguirse sin hover.
- Tabla de comparación: no muestra wall-clock. Usa `total_execution` y su delta; `grounding`, `solving` y `python` con sus deltas; `ground calls` y `solve calls`.

## Dónde vive cada cosa

- `gentians/gentians.py`: entry points `main`, `task_from_arguments` y `solve`.
- `gentians/arguments.py`: configuración pública del SDK y defaults evolutivos.
- `gentians/language/`: lexer, gramática de alto nivel, parser, parsers de declaraciones, utilidades `clingo.ast` e IR tipado de la tarea.
- `gentians/clauses/`: compilación, metaprograma, pruning y representación canónica de cláusulas.
- `gentians/clauses/metaprogram/`: pruning ASP separado por core, safety, operators, aggregates y properties. El orden de carga es explícito.
- `gentians/hypotheses/`: plumbing de representación de genomas, cierre y transiciones válidas que usan las estrategias evolutivas.
- `gentians/algorithms/`: algoritmos completos de búsqueda y su resultado común; `steady_state_genetic.py` contiene el GA actual.
- `gentians/evolution/{populations,selections,crossovers,mutations,replacements}/`: plumbing evolutivo, estrategias y factories.
- `gentians/evaluation/`: compilación de cobertura, `CoverageSolver`, scoring y resultado de evaluación.
- `gentians/clingo_stats.py`: lectura compartida de estadísticas Clingo.
- `gentians/timing.py`: fases y export de métricas.
- `tests/test_clause_space.py`: contrato principal del lenguaje y generación de cláusulas.
- `tests/test_evolution_operators.py`: genomas, cierre, operadores y search loop.
- `tests/test_evaluation.py`: cobertura, contexts, scoring y solver.
- `tests/test_profile_baseline.py`: semántica de tiempos y schema del dashboard.
- `tests/test_run_experiments.py`: manifests, fingerprints y matrices.
- `tests/test_strategy_layout.py`: forma de módulos de estrategias.
- `docs/adr/`: decisiones difíciles de revertir. ADR aceptada manda sobre comentarios históricos.
- `docs/*.json` y sus `.html`: fuentes y renders de diagramas de arquitectura y workflow. Actualiza ambos cuando el flujo cambie.

## Ruta de un cambio

Antes de editar, clasifica el cambio:

- Sintaxis o significado del task file: lexer, parser, IR tipado, language spec, compilación, tests.
- Legalidad de una regla: análisis estático o metaprograma ASP, decoder/canonicalización si aplica.
- Legalidad de un programa candidato: `HypothesisGenerator`, nunca guards repartidos entre operadores.
- Algoritmo completo: `gentians/algorithms/`; comparte `SearchResult`, no el estado interno ni el bucle.
- Política evolutiva: estrategia y factory bajo `gentians/evolution/`. Mantén `steady_state_genetic_search` agnóstico cuando el contrato existente alcanza.
- Semántica o score: cobertura compartida y fitness. Demuestra equivalencia entre ejecuciones cuando no pretendes cambiar significado.
- Medición: `timing.py`, productor del dashboard, schema y preview como una cadena.
- Optimización: benchmark controlado antes y después. Conserva la versión simple si el efecto no se sostiene.

Una regla colocada en la capa equivocada suele duplicarse. Si crossover, mutation y population necesitan el mismo guard, ese guard pertenece al constructor de hipótesis.

## Verificación

Usa la prueba más pequeña que pueda fallar por el cambio:

```powershell
uv run pytest tests/test_clause_space.py -q
uv run pytest tests/test_evolution_operators.py -q
uv run pytest tests/test_evaluation.py -q
uv run pytest tests/test_profile_baseline.py -q
uv run ruff check <paths-tocados>
uv run ty check
```

Elige los archivos relevantes. Ejecuta la suite completa solo para cambios transversales o cuando se pida. Para UI, ejecuta al menos `vp build` desde `.benchmarks/`; usa `vp test` cuando cambien cálculos o schema.

Tests de generación deben demostrar presencia de formas válidas y ausencia de formas podadas. Tests evolutivos deben fijar seed o inyectar RNG. Tests de rendimiento no deben afirmar velocidad con thresholds frágiles. Benchmarks no sustituyen tests semánticos.

## Documentación

- Cambios visibles del task language actualizan `docs/language-bias.md` y el resumen correspondiente de `README.md`.
- Una decisión va a `docs/adr/` solo cuando sea difícil de revertir, sorprendente y resultado de un tradeoff real.
- Experimentos conservan protocolo, control, variables, entorno, resultados y límites. Una idea sin medición se marca como no implementada.
- Los diagramas describen código existente. No dibujes arquitectura futura como si ya estuviera conectada.
- No commits de planes, scratch ni resultados locales de benchmark.

## Criterio técnico

- Deja la combinatoria y constraints declarativos en ASP cuando esa representación sea más directa. Deja parsing, AST, canonicalización, cachés y orquestación en Python.
- Prefiere dataclasses inmutables y pequeñas para entidades de dominio. Evita dicts sin contrato dentro del core; los dicts de configuración quedan en el boundary de `Arguments` y factories.
- Conserva orden determinista de modes, reglas y outputs. Aleatoriedad solo mediante el RNG de la búsqueda.
- Corrige causas comunes una vez. No añadas guards equivalentes en cada estrategia.
- Evita una interfaz con una implementación, factories fuera de categorías intercambiables y configuración para valores que no varían.
- Mide coste de grounding, solving, Python y closure por separado. Reducir calls no implica reducir tiempo.
- Protege expresividad no monótona. La solución más rápida que aprende otro lenguaje es una regresión.
