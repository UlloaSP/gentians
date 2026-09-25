# Pipeline de Gentians

Este documento recorre el flujo desde la tarea inductiva hasta la mejor
hipótesis y fija las invariantes que cada etapa debe conservar. Las fronteras
entre paquetes están en [architecture.md](architecture.md); el vocabulario, en
[glossary.md](glossary.md).

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

Clingo cumple dos papeles distintos: enumera cláusulas legales a partir del
language bias y evalúa la semántica del programa candidato completo.

La distinción entre cláusulas e hipótesis es obligatoria:

- `generate_clause_space()` genera el espacio finito de cláusulas individuales, un `ClauseSpace`.
- `HypothesisGenerator` construye hipótesis completas a partir de ese `ClauseSpace`, mantiene cierre de dependencias y las codifica como bitsets.
- Una cláusula no tiene cobertura o fitness estable por sí sola. ASP es no monótono y añadir una cláusula puede cambiar los modelos del programa completo.

No introduzcas optimizaciones que asuman contribuciones aditivas, cobertura fija
por regla o equivalencia global a partir de los ejemplos. Una firma de cobertura
solo expresa comportamiento sobre la tarea observada.

## Semántica del producto

Una tarea puede declarar background ASP, ejemplos positivos y negativos con
contexto opcional, límites `#maxv/#maxbl/#minhl/#maxhl/#maxpl`, heads normales,
disyuntivas, choice o cardinalidad, negación fuerte, negación por defecto,
variables tipadas y dirigidas, constantes, términos anidados, condicionales,
aggregates, arithmetic, comparisons y predicate invention.

`docs/language-bias.md` es el contrato de sintaxis y significado. Léelo completo
antes de cambiar lexer, grammar, parser, modes, generación o pruning.
`README.md` y [task-language.md](task-language.md) resumen el uso; no son una
segunda especificación.

Reglas semánticas que deben sobrevivir cualquier refactor:

- La tarea posee su significado. `Arguments` configura ejecución y estrategias, no redefine el language bias.
- Los tipos son nominales. Coincidencia de valores ground no une dominios.
- `input` debe estar ligado, `output` lo produce un literal positivo y `any` desactiva deliberadamente la restricción de flujo. Negación por defecto no produce variables.
- Los límites estructurales y recalls deben mantener finito el espacio. `*` significa ilimitado solo cuando los demás límites siguen cerrando el dominio.
- `#modeh` describe una cabeza completa. `#modeha` combina elementos choice/cardinality. `#modehd` combina elementos disyuntivos. Un recall nunca transforma una forma en otra.
- `#bias`, `#metarule`, `#predicate` y `#modem` se han retirado. El parser los rechaza explícitamente; usa modes y límites para declarar el lenguaje.
- Contextos de ejemplos se aíslan por selector. Un contexto nunca filtra hechos o constraints hacia otro ejemplo.
- Fitness fuerza consecuencias brave. Evalúa el programa candidato completo.
- La cobertura que requiere Clingo usa el solver normal y un `clingo.Control` nuevo. La herencia exacta de cobertura puede resolver una evaluación sin crear uno.
- Canonicalización preserva semántica ASP. Deduplicar texto, renombrado de variables o sistemas aritméticos no autoriza aproximaciones semánticas.
- Dependencias con negación fuerte conservan el signo. `p/n` y `-p/n` son predicados distintos para cierre y recursión.

## Cómo se genera una cláusula

`parse_file()` lee UTF-8 y delega en `parse_text()`. El lexer separa sentencias
completas sin romper strings, comentarios, delimitadores anidados, rangos o
anotaciones. El parser orquesta las declaraciones y construye `InductiveTask`;
`directives`, `declarations` y `modes` contienen sus gramáticas específicas.
Clingo sigue siendo la autoridad para la gramática y el AST de ASP. El background
se parsea en una sola llamada preservando las líneas originales; en ejemplos solo
se parsean los campos no vacíos. `InductiveTask` conserva background, átomos
incluidos y excluidos, y contextos como nodos `clingo.ast.AST`; `Clause` conserva
el nodo de cada cláusula candidata junto al texto canónico de salida. Los solvers
reciben los nodos mediante `ProgramBuilder`, sin volver a parsear el ASP retenido.

`generate_clause_space()` ejecuta este pipeline:

1. Inspecciona background, ejemplos y declaraciones para derivar tipos, dominios, closed-world properties y capacidades permitidas.
2. Compila declaraciones a `ClauseMode` y facts reificados.
3. Carga los módulos `.lp` en el orden de `CLAUSE_METAPROGRAM_MODULES`.
4. Clingo aplica límites, recall, linkedness, typing, ASP safety, flujo dirigido, coherencia y propiedades de pruning durante enumeración.
5. Python decodifica `selected/3` y `var_at/4` como `ReifiedClause`.
6. `_theta_reduced` elimina cuerpos con subcláusulas theta-equivalentes.
7. `ArithmeticSystem` normaliza relaciones conectadas y `canonical.key` elige un representante.
8. `ClauseSpace` ordena y deduplica `Clause`.

Prefiere pruning declarativo en los módulos `.lp` cuando la condición depende de
la selección reificada. Usa Python para análisis estático de la tarea, AST,
decodificación o canonicalización que no conviene recomputar dentro del solver.
Evita generar un dominio enorme para filtrarlo después.

Un cambio de lenguaje suele tocar lexer, parser, IR, compilación de modes/facts,
metaprograma, decoder/render, `docs/language-bias.md` y tests de hipótesis.
Recorre esa cadena completa. Una nueva sintaxis sin semántica de generación, o
nueva semántica sin documentación, está incompleta.

[clause-generation.md](clause-generation.md) detalla los módulos de esta etapa y
[metaprogram/README.md](metaprogram/README.md) el contrato del metaprograma.

## Cómo se genera y busca una hipótesis

`HypothesisGenerator` es la única autoridad para construir o transformar
genomas. Prepara el `ClauseSpace`, elimina cláusulas imposibles de cerrar y
mantiene índices de heads y dependencies. Añadir cierra los proveedores que
falten. Eliminar retira en cascada los consumidores sin proveedor, sin añadir
alternativas. Reemplazar considera la cabeza nueva antes de retirar consumidores
y cierra el bloque añadido. Los límites y las máscaras de protección se aplican
al cambio completo.

Invariantes del candidato:

- No está vacío.
- Solo contiene cláusulas del espacio preparado.
- No excede `#maxpl`.
- Todas sus dependencias tienen proveedor en background o en el candidato.
- Una transición destructiva no puede reintroducir la regla marcada como forbidden para reparar su propia eliminación.

Las factories de estrategias se conservan en todas las categorías aunque alguna
registre una sola implementación. `random_group` reúne los reemplazos por firma
de cabeza y las operaciones por bloques. `random_jump_probability=0.1` permite
cambiar de firma en un intento de reemplazo. En candidatos completos con
positivos y constraints disponibles, las reglas con cabeza solo pueden eliminarse
mediante el intento `complete_generator_removal_probability=0.1`; no existe
fallback irrestricto en ese caso. Si el espacio activo no contiene constraints,
la completitud no protege las cláusulas con cabeza: se permiten operaciones
ordinarias. Un candidato incompleto permite cambios encabezados y eliminación o
reemplazo de constraints, sin búsqueda de relajaciones. Con positivos y
negativos, los reemplazos conservan el tipo de raíz, encabezada o constraint; no
se añaden constraints mediante append. Crossover conserva su política propia.
[variation-policy.md](variation-policy.md) documenta las garantías y los límites.

Las estrategias no editan bits arbitrariamente. Selección opera sobre
`Individual`; population, crossover y mutation piden genomas válidos a
`HypothesisGenerator`; replacement conserva tamaño y orden por score. Los
protocolos viven en `evolution/operator_types.py` y el estado compartido mínimo
en `EvolutionContext`.

`steady_state_genetic_search` es el bucle del GA de estado estable. Construye
factories desde `Arguments`, crea o acepta un `ClauseSpace`, inicializa
población, memoiza evaluaciones, registra generación 0, aplica selección,
crossover, mutación y replacement, y termina al encontrar una hipótesis perfecta
o agotar generaciones. La estrategia de reinicio (`restarts/`, por defecto
`stagnation`) decide cuándo reiniciar y qué individuos sobreviven; cada
algoritmo reconstruye su población y sus cachés. Con `stagnation`, en espacios
con cláusulas encabezadas, steady-state reinicia tras 100 generaciones sin
mejorar el mejor score: conserva el campeón y toda la caché de evaluaciones, y
vuelve a muestrear el resto. Incremental solo reinicia con el espacio agotado y
limpia la caché salvo la de los supervivientes. Los espacios solo-constraints
no se reinician. `iterations_genetic=0` significa
búsqueda sin límite de generaciones.

Al añadir una estrategia:

- Implementa un archivo y una clase top-level. `tests/test_strategy_layout.py` protege ese layout.
- Cumple el callable type existente. Extiende el protocolo solo si la categoría completa necesita datos nuevos.
- Regístrala en la factory de su subpaquete.
- Delega construcción y cierre a `HypothesisGenerator`.
- Usa el `random.Random` inyectado para reproducibilidad.
- Añade tests del comportamiento observable y de los invariantes, no tests que copien la implementación.

El archivo semántico agrupa por `Behavior` y conserva los `k` programas más
cortos. Es una poda respecto a ejemplos presentes, no equivalencia ASP.
`module_mix` transfiere cierres sintácticos de soporte, no módulos semánticos
ASP.

## Evaluación y Clingo

`create_evaluator()` usa el score `cov_program`, calculado a partir de
`Coverage`; `CandidateEvaluator` devuelve `EvaluationResult` con score,
comportamiento y estados de completitud y consistencia, y comparte condición de
éxito y `CoverageSolver`.

Cuando hace falta resolver cobertura, el solver normal crea un `Control` nuevo,
añade background, programa estático de cobertura y candidato desde AST ya
retenido, groundea y resuelve. La herencia exacta de cobertura puede reutilizar
consecuencias ya demostradas y omitir ese Control.

Antes de cambiar cobertura, prueba al menos inclusión, exclusión, tarea vacía en
uno de los lados, contexts aislados y negación por defecto.
