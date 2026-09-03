# Gentians

Gentians es un solver de Inductive Logic Programming para aprender programas ASP. Su objetivo es buscar hipótesis no monótonas expresadas con sintaxis ASP mediante una heurística evolutiva. Clingo cumple dos papeles distintos: enumera reglas legales a partir del language bias y evalúa la semántica del programa candidato completo.

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
  -> Reader + validación
  -> Program, IR de la tarea inductiva
  -> análisis estático + compilación de modes
  -> facts + metaprograma ASP
  -> Clingo enumera y poda cláusulas
  -> decode + canonicalización
  -> RuleSpace
  -> HypothesisGenerator construye genomas cerrados
  -> search_solver aplica estrategias evolutivas
  -> fitness evalúa cada programa completo con Clingo
  -> mejor hipótesis + score + best_found

instrumentación -> artefactos de benchmark -> preview Vite
```

La distinción entre reglas e hipótesis es obligatoria:

- `HypothesisSpaceGenerator` tiene un nombre histórico. En la implementación actual genera el espacio finito de reglas individuales, un `RuleSpace`.
- `HypothesisGenerator` construye hipótesis completas a partir de ese `RuleSpace`, mantiene cierre de dependencias y las codifica como bitsets.
- Una regla no tiene cobertura o fitness estable por sí sola. ASP es no monótono y añadir una regla puede cambiar los modelos del programa completo.

No introduzcas optimizaciones que asuman contribuciones aditivas, cobertura fija por regla o equivalencia global a partir de los ejemplos. Una firma de cobertura solo expresa comportamiento sobre la tarea observada.

## Vocabulario canónico

Usa estos términos en código, docs y conversación:

- **Tarea inductiva**: archivo que contiene background ASP, ejemplos y language bias. También posee los límites estructurales.
- **`Program`**: IR parseado de la tarea inductiva. No es la hipótesis aprendida, pese al nombre de la clase.
- **Language bias**: lenguaje finito permitido para las hipótesis. Incluye modes, recalls, tipos, direcciones, constantes, límites, metarules, invención y `#bias` explícito.
- **Regla o cláusula**: una regla ASP aprendible ya instanciada y canónica.
- **`RuleEntry`**: texto de una regla junto a predicados definidos, dependencias, tamaño de cuerpo y bundle opcional.
- **`RuleSpace`**: conjunto ordenado y sin duplicados de reglas candidatas.
- **Hipótesis o programa candidato**: conjunto de reglas del `RuleSpace` evaluado como una unidad bajo stable-model semantics.
- **`Genome`**: entero bitset que representa una hipótesis. El bit `i` selecciona la regla `i` del `RuleSpace` preparado.
- **`Individual`**: genoma evaluado con score, marca de solución, firma de comportamiento y edad.
- **Comportamiento**: pareja de máscaras `(pos_mask, neg_mask)`. La primera marca positivos cubiertos; la segunda, negativos cubiertos.
- **Hipótesis perfecta**: cubre todos los ejemplos positivos y ningún negativo. Esto produce `best_found=True`.
- **Cierre de dependencias**: toda dependencia de una regla queda definida por el background o por alguna cabeza del mismo candidato.
- **Bundle**: grupo de reglas producido por una metarule. Es atómico durante generación y operadores.
- **Pruning**: exclusión de reglas o hipótesis inválidas, redundantes o imposibles antes de gastar evaluaciones de fitness.
- **Solver normal**: crea, groundea y resuelve un `clingo.Control` por candidato.
- **Solver pregrounded**: groundea una vez el universo de reglas guardadas y activa el candidato mediante externals.

No uses "hypothesis space" sin indicar si hablas de reglas candidatas o de programas candidatos. En código actual, `RuleSpace` elimina la ambigüedad.

## Semántica del producto

Una tarea puede declarar background ASP, ejemplos positivos y negativos con contexto opcional, límites `#maxv/#maxbl/#minhl/#maxhl/#maxpl`, heads normales, disyuntivas, choice o cardinalidad, negación fuerte, negación por defecto, variables tipadas y dirigidas, constantes, términos anidados, condicionales, aggregates, arithmetic, comparisons, predicate invention, metarules de segundo orden y meta-ASP mediante `#bias`.

`docs/language-bias.md` es el contrato de sintaxis y significado. Léelo completo antes de cambiar reader, grammar, modes, generación o pruning. `README.md` es el resumen de uso, no una segunda especificación.

Reglas semánticas que deben sobrevivir cualquier refactor:

- La tarea posee su significado. `Arguments` configura ejecución y estrategias, no redefine el language bias.
- Los tipos son nominales. Coincidencia de valores ground no une dominios.
- `input` debe estar ligado, `output` lo produce un literal positivo y `any` desactiva deliberadamente la restricción de flujo. Negación por defecto no produce variables.
- Los límites estructurales y recalls deben mantener finito el espacio. `*` significa ilimitado solo cuando los demás límites siguen cerrando el dominio.
- `#modeh` describe una cabeza completa. `#modeha` combina elementos choice/cardinality. `#modehd` combina elementos disyuntivos. Un recall nunca transforma una forma en otra.
- `#bias` admite reglas y constraints duros y define predicados reservados `bias_*`. No admite weak constraints ni directivas globales.
- Contextos de ejemplos se aíslan por selector. Un contexto nunca filtra hechos o constraints hacia otro ejemplo.
- Fitness fuerza consecuencias brave. Evalúa el programa candidato completo.
- Solver normal y pregrounded deben producir la misma cobertura en activaciones sucesivas.
- Canonicalización preserva semántica ASP. Deduplicar texto, renombrado de variables o sistemas aritméticos no autoriza aproximaciones semánticas.
- Dependencias con negación fuerte conservan el signo. `p/n` y `-p/n` son predicados distintos para cierre y recursión.

## Arquitectura objetivo y ubicación actual

Estos son límites del producto, aunque algunos todavía compartan paquete:

| Módulo | Responsabilidad | Ubicación actual |
|---|---|---|
| Reader, grammar, bias, entities y ASP AST | Parsear una tarea una sola vez, validar en el boundary y construir IR tipado. Usar `clingo.ast` para sintaxis y transformaciones ASP, no manipulación textual frágil. | `gentians/clauses/reader.py`, `parser.py`, entidades pequeñas de `clauses/` |
| Generación de reglas | Compilar bias y análisis estático a facts, enumerar cláusulas mediante metaprograma ASP, podar ilegalidad y redundancia, decodificar y canonicalizar. | `gentians/clauses/hypothesis_space.py`, `clauses/rules/**/*.lp`, `RuleSpace` |
| Generación de hipótesis | Construir programas candidatos, aplicar pruning mientras nacen y cerrar dependencias bajo `#maxpl` y bundles. | `gentians/hypotheses/` |
| Solver evolutivo | Un único algoritmo central con población, selección, crossover, mutación, replacement y fitness intercambiables. | `gentians/evolution/algorithms/search.py` y subpaquetes de estrategias |
| Evaluación ASP | Traducir ejemplos a cobertura y usar Clingo como oracle semántico. | `gentians/asp/`, `gentians/evolution/fitness/` |
| Docs | Mantener lenguaje, decisiones, arquitectura y experimentos con resultados. | `docs/`, `README.md` |
| Profiling y logging | Medir tiempo neto, fases, calidad, operadores y estadísticas Clingo sin contaminar la métrica observada. | `gentians/timing.py`, `gentians/asp/stats.py` |
| Benchmarks y runners | Definir datasets, matrices reproducibles, aislamiento, fingerprints y agregación. | `benchmarks/`, `benchmarks/gentians/` |
| Preview de benchmarks | Leer artefactos generados y mostrar detalle y comparación sin reinterpretar métricas. | `.benchmarks/` |

No crees paquetes vacíos para imitar esta tabla. Haz aparecer un límite físico cuando tenga lógica propia y reduzca acoplamiento real. Si mueves una frontera, conecta directamente todos los usos y elimina la ubicación anterior.

La tabla mezcla destino y estado real a propósito. La generación de hipótesis completas usa un bitset engine en Python; logging no tiene aún un módulo general separado de timing, métricas y callbacks. Trátalos como límites de producto pendientes, no como funciones ya implementadas ni como permiso para un refactor masivo no solicitado.

## Cómo se genera una regla

`read_program()` extrae primero `#bias` y `#metarule`, analiza directivas y background, valida duplicados y devuelve `Program`. El reader es el boundary de errores de sintaxis de la tarea.

`HypothesisSpaceGenerator` ejecuta este pipeline:

1. Inspecciona background, ejemplos y declaraciones para derivar tipos, dominios, closed-world properties y capacidades permitidas.
2. Compila declaraciones a `HypothesisMode` y facts reificados.
3. Carga los módulos `.lp` en el orden de `HYPOTHESIS_SPACE_RULE_MODULES`.
4. Clingo aplica límites, recall, linkedness, typing, ASP safety, flujo dirigido, coherencia y propiedades de pruning durante enumeración.
5. Python decodifica `selected/3` y `var_at/4` como `ReifiedClause`.
6. `_theta_reduced` elimina cuerpos con subcláusulas theta-equivalentes.
7. `ArithmeticSystem` normaliza relaciones conectadas y `canonical.key` elige un representante.
8. `RuleSpace` ordena y deduplica `RuleEntry`.

Prefiere pruning declarativo en los módulos `.lp` cuando la condición depende de la selección reificada. Usa Python para análisis estático de la tarea, AST, decodificación o canonicalización que no conviene recomputar dentro del solver. Evita generar un dominio enorme para filtrarlo después.

Un cambio de lenguaje suele tocar reader, entidades, compilación de modes/facts, metaprograma, decoder/render, `docs/language-bias.md` y tests de hipótesis. Recorre esa cadena completa. Una nueva sintaxis sin semántica de generación, o nueva semántica sin documentación, está incompleta.

## Cómo se genera y busca una hipótesis

`HypothesisGenerator` es la única autoridad para construir o transformar genomas. Prepara el `RuleSpace`, elimina reglas imposibles de cerrar y mantiene índices de heads, dependencies y bundles. Creación, append, remove, replace y crossover terminan en `_build()` y `_complete()`.

Invariantes del candidato:

- No está vacío.
- Solo contiene reglas del espacio preparado.
- No excede `#maxpl`.
- Incluye bundles completos.
- Todas sus dependencias tienen proveedor en background o en el candidato.
- Una transición destructiva no puede reintroducir la regla o bundle marcado como forbidden para reparar su propia eliminación.

Las estrategias no editan bits arbitrariamente. Selección opera sobre `Individual`; population, crossover y mutation piden genomas válidos a `HypothesisGenerator`; replacement conserva tamaño y orden por score. Los protocolos viven en `evolution/operator_types.py` y el estado compartido mínimo en `EvolutionContext`.

`search_solver` es el único bucle central. Construye factories desde `Arguments`, crea o acepta un `RuleSpace`, inicializa población, memoiza evaluaciones, registra generación 0, aplica selección, crossover, mutación y replacement, y termina al encontrar una hipótesis perfecta o agotar generaciones. `iterations_genetic=0` significa búsqueda sin límite de generaciones.

Al añadir una estrategia:

- Implementa un archivo y una clase top-level. `tests/test_strategy_layout.py` protege ese layout.
- Cumple el callable type existente. Extiende el protocolo solo si la categoría completa necesita datos nuevos.
- Regístrala en la factory de su subpaquete.
- Delega construcción y cierre a `HypothesisGenerator`.
- Usa el `random.Random` inyectado para reproducibilidad.
- Añade tests del comportamiento observable y de los invariantes, no tests que copien la implementación.

El archivo semántico agrupa por `Behavior` y conserva los `k` programas más cortos. Es una poda respecto a ejemplos presentes, no equivalencia ASP. `module_mix` transfiere cierres sintácticos de soporte, no módulos semánticos ASP.

## Fitness y Clingo

`create_fitness()` separa dos decisiones:

- Estrategia de score: `cov_program` o `cov_balanced`.
- Ejecución: solver `normal` o `pregrounded`.

Ambas estrategias reciben `Coverage` y devuelven `FitnessResult`. La condición de éxito es compartida. Mantén scoring separado de grounding/solving para poder comparar solvers sin cambiar el objetivo.

El solver normal recompone el programa estático de cobertura más el candidato en cada evaluación. El pregrounded transforma cada regla con `clingo.ast`, añade un external reservado y alterna activaciones sobre un solo `Control`. El coste de un universo groundeado grande puede superar el ahorro de ground calls. Decide con datos.

Antes de cambiar cobertura, prueba al menos inclusión, exclusión, tarea vacía en uno de los lados, contexts aislados, negación por defecto y varias activaciones del solver pregrounded.

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
- `benchmarks/profile_hypothesis.py` mide generación de `RuleSpace` aislada.
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
uv run python benchmarks/profile_hypothesis.py --datasets <dataset>
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
- Cards de tiempos: deben mostrar `total`, `hypothesis`, `clingo` y `python`; `total` es la media de `total_execution`, nunca wall-clock. `hypothesis` y `tiempo evolutivo` van juntas.
- Fases: `hypothesis space`, `pregrounding`, `initialization`, `selection`, `crossover`, `mutation`, `replacement` y `search orchestration`. No existe fase separada `fitness evaluation`: su coste pertenece a la fase que solicitó la evaluación.
- Tipos horizontales de tiempo: exactamente `python`, `grounding`, `solving` y `closure`.
- `pregrounding` solo mide creación y grounding del solver pregenerado; ejecución normal no inventa esa fase.
- Modelos solve por etapa: usa fases reales; `hypothesis_space` se muestra como `hypothesis`. No agrupa fases conocidas como `search setup`, `fitness search` ni `other`.
- Los títulos de charts identifican la métrica y son funcionales. No añadas títulos de página, hero copy ni texto ornamental.
- Comparación conserva todas las gráficas y divisiones de la vista individual. Cada experimento añade sus líneas, grupos, stacks o anillos; no se reemplazan por resúmenes distintos.
- En comparación, el color identifica siempre al experimento; métricas y divisiones usan líneas, símbolos, opacidad o trama. Las leyendas no multiplican `experimento × división` y todo debe distinguirse sin hover.
- Tabla de comparación: no muestra wall-clock. Usa `total_execution` y su delta; `grounding`, `solving` y `python` con sus deltas; `ground calls` y `solve calls`.

## Dónde vive cada cosa

- `gentians/gentians.py`: entry points `main`, `program_from_arguments` y `solve`.
- `gentians/arguments.py`: configuración pública del SDK y defaults evolutivos.
- `gentians/clauses/`: front-end de la tarea, IR, compilación, metaprograma y representación canónica de reglas.
- `gentians/clauses/rules/`: pruning ASP separado por core, safety, operators, aggregates y properties. El orden de carga es explícito.
- `gentians/hypotheses/`: plumbing de representación de genomas, cierre y transiciones válidas que usan las estrategias evolutivas.
- `gentians/evolution/algorithms/search.py`: orquestación evolutiva, caché de evaluaciones y archivo semántico.
- `gentians/evolution/{populations,selections,crossovers,mutations,replacements,fitness}/`: estrategias y factories.
- `gentians/asp/`: programa de cobertura, isolation de contexts, solvers y stats.
- `gentians/timing.py`: fases y export de métricas.
- `tests/test_hypothesis_space.py`: contrato principal del lenguaje y generación de reglas.
- `tests/test_evolution_operators.py`: genomas, cierre, operadores y search loop.
- `tests/test_fitness.py`: cobertura, contexts y equivalencia de solvers.
- `tests/test_profile_baseline.py`: semántica de tiempos y schema del dashboard.
- `tests/test_run_experiments.py`: manifests, fingerprints y matrices.
- `tests/test_strategy_layout.py`: forma de módulos de estrategias.
- `docs/adr/`: decisiones difíciles de revertir. ADR aceptada manda sobre comentarios históricos.
- `docs/*.json` y sus `.html`: fuentes y renders de diagramas de arquitectura y workflow. Actualiza ambos cuando el flujo cambie.

## Ruta de un cambio

Antes de editar, clasifica el cambio:

- Sintaxis o significado del task file: reader, entidad tipada, language spec, compilación, tests.
- Legalidad de una regla: análisis estático o metaprograma ASP, decoder/canonicalización si aplica.
- Legalidad de un programa candidato: `HypothesisGenerator`, nunca guards repartidos entre operadores.
- Política evolutiva: estrategia y factory. Mantén `search_solver` agnóstico cuando el contrato existente alcanza.
- Semántica o score: cobertura compartida y fitness. Demuestra equivalencia entre ejecuciones cuando no pretendes cambiar significado.
- Medición: `timing.py`, productor del dashboard, schema y preview como una cadena.
- Optimización: benchmark controlado antes y después. Conserva la versión simple si el efecto no se sostiene.

Una regla colocada en la capa equivocada suele duplicarse. Si crossover, mutation y population necesitan el mismo guard, ese guard pertenece al constructor de hipótesis.

## Verificación

Usa la prueba más pequeña que pueda fallar por el cambio:

```powershell
uv run pytest tests/test_hypothesis_space.py -q
uv run pytest tests/test_evolution_operators.py -q
uv run pytest tests/test_fitness.py -q
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
