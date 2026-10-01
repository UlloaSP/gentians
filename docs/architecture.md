# Arquitectura de Gentians

Este documento describe la estructura que debe guiar cambios y propuestas de
simplificación. `AGENTS.md` contiene las reglas de trabajo; `pipeline.md`, el
recorrido de cada etapa y sus invariantes; `docs/language-bias.md` define la
sintaxis y el significado de las tareas.
El diagrama de la implementación conectada vive en
`gentians-architecture.json` y su render `gentians-architecture.html`.

## Flujo y fronteras

```text
tarea inductiva -> language -> InductiveTask -> clauses -> ClauseSpace
  -> hypotheses -> Genome -> algorithms (search + evolution)
  -> evaluation -> Coverage / EvaluationResult -> SearchResult

algorithms + clauses + evaluation -> timing / métricas -> benchmarks -> .benchmarks
```

| Frontera | Dueña de | Ubicación actual |
|---|---|---|
| Lenguaje de tareas | Leer UTF-8, separar sentencias, validar directivas y construir el IR tipado. Delega la gramática ASP a `clingo.ast`. | `gentians/language/` y `language/ir/` |
| Cláusulas | Analizar la tarea, compilar modes y facts, enumerar y podar con Clingo, decodificar y canonicalizar cláusulas. | `gentians/clauses/`, `analysis/`, `canonicalization/`, `metaprogram/` |
| Hipótesis | Preparar el `ClauseSpace`, construir genomas válidos y mantener el cierre de dependencias. | `gentians/hypotheses/` |
| Algoritmos | Conectar los pasos de cada bucle completo de búsqueda, registrar su progreso y devolver `SearchResult`. | `gentians/algorithms/`, métricas en `algorithms/metrics/` |
| Runtime de búsqueda | Pasos que los algoritmos conectan: caché de candidatos, población, cruce, lotes de cláusulas, renovación, presupuesto y `SearchResult`. | `gentians/search/` |
| Evolución | Definir `Individual`, `EvolutionContext`, operadores, estrategias y sus factories. | `gentians/evolution/` |
| Evaluación | Evaluar el programa candidato completo con Clingo y producir cobertura, score y condición de solución. | `gentians/evaluation/` |
| Medición | Atribuir fases, excluir instrumentación y exportar métricas y estadísticas Clingo. | `gentians/timing.py`, `gentians/clingo_stats.py`, módulos `metrics.py` |
| Experimentos | Definir datasets y matrices, ejecutar runs y producir artefactos comparables. | `benchmarks/`, tareas en `benchmarks/gentians/` |
| Preview | Leer los artefactos producidos por Python y mostrarlos sin recalcular métricas. | `.benchmarks/` |
| Documentación | Contrato del lenguaje, decisiones, arquitectura y experimentos medidos. | `docs/`, resumen en `README.md` y `docs/task-language.md` |

`gentians/gentians.py` contiene los entry points y selecciona el algoritmo;
`gentians/arguments.py` contiene la configuración pública de ejecución. Ninguno
de ellos redefine el language bias de una tarea inductiva.

## Estructura deseada

- `language/` es dueño del parsing y de `InductiveTask`; `clauses/` recibe ese
  IR y entrega `ClauseSpace`. En `clauses/metaprogram/`, `representation/`
  deriva la representación reificada, `inference/` sus consecuencias,
  `legality/` la legalidad, `symmetry/` los representantes y `pruning/` la poda.
  `representation/schema.lp` declara predicados opcionales; el orden de carga
  es explícito. `docs/metaprogram/` explica ese contrato.
- Las plantillas en `language/ir/` representan el language bias y sus bindings,
  no un programa candidato. Conservan los metadatos que Clingo no interpreta
  sobre términos y guards nativos de Clingo. `language/terms.py` interpreta las
  anotaciones `var` y `const`, recorre sus bindings y realiza las sustituciones;
  no existe otro árbol de sintaxis de términos. Cada literal posee su expansión
  de constantes, compartida por cabezas, condicionales y agregados. Los modes
  se decodifican desde los nodos parseados, también al expandir pools, sin volver
  a parsear átomos ni argumentos. `clauses/canonicalization/` ensambla
  `ast.Rule` y conserva el nodo hasta evaluación; Clingo es dueño del formato
  textual. No añadas renderers ASP manuales ni conversiones de la cláusula
  completa de texto a AST en esta frontera.
  `HeadTemplate` conserva una forma nativa de Clingo y elementos completos:
  signos y condiciones pertenecen a cada literal, sin listas paralelas ni otra
  representación de límites u operadores. Las declaraciones comparten la
  validación de labels y anonimato; el parser consume sus argumentos completos
  para verificar constantes, respetando los roles de conclusión y condición.
  `InductiveTask` conserva las cabezas como `HeadTemplate`, sin otra declaración
  que envuelva el mismo dato y un recall fijo. El parser valida recall `1`; la
  plantilla posee la validación de cabeza. La inspección ASP consume AST
  retenidos, sin helpers de parsing de texto usados solo por los tests. Las
  pruebas de seguridad de outputs construyen reglas AST y las cargan con
  `ProgramBuilder`; Clingo conserva la autoridad del grounding.
  El lexer consume completos los marcadores de comentarios anidados y respeta
  comentarios de línea dentro de bloques, también al buscar anotaciones.
  El parser deduplica ejemplos y modes mediante claves de diccionarios ordenados,
  conservando la primera localización; las constantes usan claves por tipo.
  `ArithmeticLiteral` conserva expresión, resultado y procedencia de la familia
  aditiva; no almacena una complejidad fija sin consumidores.
  `#modeha` y `#modehd` comparten parsing de recall opcional y aridad de la
  directiva. El parsing ASP recoge diagnósticos en su única llamada a Clingo;
  localizar un error no vuelve a parsear la fuente.
  Las expansiones de constantes calculan una vez las alternativas independientes
  de guards, elementos y condiciones por llamada y conservan el orden de su
  producto cartesiano. Las directivas rechazan argumentos finales vacíos;
  `#modeagg`, `#modearith` y `#modecmp` fallan como directivas retiradas antes
  de convertirse en background ASP.
  `InductiveTask.constants` conserva valores `SymbolicTerm` de Clingo por tipo
  nominal. Se parsean al leer la declaración y se reutilizan al expandir
  placeholders, sin guardar texto intermedio ni volver a parsear el valor.
- `hypotheses/` es la única autoridad sobre legalidad y transiciones de
  `Genome`. Ningún operador ni algoritmo duplica su cierre de dependencias.
- `algorithms/` contiene solo los algoritmos y sus métricas. Cada archivo de
  algoritmo es wiring: crea estrategias y runtime, y muestra el orden de los
  pasos de un vistazo. La lógica de cada paso vive en `search/`; lo que un
  paso registra por generación o por época vive en `algorithms/metrics/`.
  `steady_state_genetic.py` e `incremental_clause_genetic.py` comparten
  `Candidates`, `Population`, `create_offspring`, evaluación y estrategias,
  pero cada uno conserva su política de búsqueda.
- `search/` es el runtime compartido. `clause_pool.py` y `renewal.py` solo los
  usa incremental. Una diferencia real entre algoritmos se expresa como una
  llamada o un argumento visible en el wiring, no como una copia del paso.
- `evolution/{populations,selections,crossovers,mutations,replacements,restarts}/`
  conserva una factory por categoría y clases de estrategia separadas. La
  factory es la frontera de selección y validación de configuración aunque hoy
  registre una sola estrategia. Al añadir una estrategia, se registra allí.
  `operator_types.py` y `EvolutionContext` son el contrato común mínimo.
- `evaluation/` es independiente de `evolution/`. `CoverageSolver` evalúa la
  hipótesis completa bajo semántica de modelos estables. Si debe resolver
  cobertura, crea un `clingo.Control` nuevo; la herencia exacta puede evitar
  esa llamada. Una cláusula aislada no tiene fitness estable.
- `timing.py` conserva la atribución de fases y el tiempo neto; los módulos
  `metrics.py` construyen filas del dominio que poseen. Logging general sigue
  siendo una frontera de producto pendiente, no un paquete que haya que crear
  preventivamente.
- `benchmarks/` produce las métricas y `.benchmarks/` las consume. El contrato
  del payload se cambia en productor, schema, preview y tests a la vez.

Esta estructura expresa propiedad del concepto, no una obligación de crear
paquetes. Una frontera física nueva necesita lógica propia y menos acoplamiento
real. Si se mueve una frontera, se actualizan todos sus usos y se elimina la
ubicación anterior.

## Ruta de un cambio

Antes de editar, clasifica el cambio:

- Sintaxis o significado del task file: lexer, parser, IR tipado, language spec, compilación, tests.
- Legalidad de una regla: análisis estático o metaprograma ASP, decoder/canonicalización si aplica.
- Legalidad de un programa candidato: `HypothesisGenerator`, nunca guards repartidos entre operadores.
- Algoritmo completo: wiring en `gentians/algorithms/`, pasos en `gentians/search/`, métricas en `algorithms/metrics/`.
- Política evolutiva: estrategia y factory bajo `gentians/evolution/`. Mantén `steady_state_genetic_search` agnóstico cuando el contrato existente alcanza.
- Semántica o score: cobertura compartida y fitness. Demuestra equivalencia entre ejecuciones cuando no pretendes cambiar significado.
- Medición: `timing.py`, productor del dashboard, schema y preview como una cadena.
- Optimización: benchmark controlado antes y después. Conserva la versión simple si el efecto no se sostiene.

Una regla colocada en la capa equivocada suele duplicarse. Si crossover,
mutation y population necesitan el mismo guard, ese guard pertenece al
constructor de hipótesis.

## Cómo decidir una simplificación

1. Identifica la frontera dueña, sus entradas y salidas, y los consumidores y
   tests del código considerado. Revisa si la forma actual sostiene una
   extensión ya admitida, una invariante o una decisión documentada.
2. Busca en todo el recorrido afectado: código muerto, datos reconstruidos,
   trabajo duplicado, capas que solo delegan y lógica ubicada fuera de su
   frontera. No fijes de antemano un número de hallazgos.
3. Propón el cambio mínimo dentro de la frontera propietaria. Explica qué se
   elimina, qué comportamiento permanece y qué prueba lo comprobaría. Una
   factory de estrategias con una implementación sigue cumpliendo el contrato
   estructural anterior.
4. Si el cambio toca lenguaje, generación, cobertura o pruning, comprueba
   legalidad y semántica ASP con los tests de esa cadena. Si alega mejorar
   rendimiento, exige una medición reproducible antes de concluirlo.

Los tests principales están en `tests/test_clause_space.py` (lenguaje y
cláusulas), `test_evolution_operators.py` y `test_incremental_*.py` (genomas,
operadores y algoritmos), `test_evaluation.py` (cobertura),
`test_profile_baseline.py` (tiempos y dashboard), `test_run_experiments.py`
(runner) y `test_strategy_layout.py` (estructura de estrategias).
`tests/syntax_matrix/` recorre la cadena completa por construcción ASP: cada
`cases/<eje>/<caso>.lp` es una tarea mínima cuya hipótesis de referencia
(`% expect:`) debe sobrevivir a generación y cierre, ser perfecta y aprenderse
con ambos algoritmos. Una construcción nueva del task language añade allí su
caso; un hueco conocido se marca con `% xfail:`. Las ADR
aceptadas en `docs/adr/` prevalecen sobre comentarios históricos.
