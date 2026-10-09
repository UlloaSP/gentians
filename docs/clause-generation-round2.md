# Segunda ronda: 20 oportunidades adicionales de generación

Continúa el [inventario 01–25](clause-generation-optimizations.md). Estos cambios
se comparan con el worktree resultante de esa ronda, no con el código original.
La columna de peso identifica doce intervenciones estructurales o dirigidas a
costes dominantes. No afirma veinte aceleraciones independientes: varias actúan
sobre la misma ruta y sus efectos deben medirse conjuntamente y por controles.
Los protocolos y resultados locales permanecen en `.debug`, fuera de commits.

| ID | Peso | Cambio nuevo y diferencia frente a la primera ronda | Activación y alcance |
| --- | --- | --- | --- |
| 26 | Alto | Materializar los bloques numéricos en C, incluyendo reconstrucción de variables y literales. Antes solo se copiaban símbolos en C y cada fila se reconstruía en Python. | Transporte native/auto; conserva orden, tails y presupuesto raw. |
| 27 | Medio | Compilar tablas densas de offsets por slot/mode. El decoder portable deja de construir una clave `(slot, mode)` y buscarla en un dict por literal. | Python y preparación del decoder C; no cambia scopes. |
| 28 | Alto | Fusionar construcción, formato y liberación de `clingo_ast_t` en C. Antes cada regla creaba y destruía un wrapper `ast.AST` Python para obtener texto. | Extensión opcional; fallback con el builder Python. Clingo sigue construyendo y formateando la regla completa. |
| 29 | Alto | Fábrica de AST literales por id de mode dentro de `RuleRecipes`. Sustituye en esta ruta la caché global cuyo lookup recibe el `ClauseMode` completo. | Acotada a 8192; pertenece al espacio y no mezcla tareas. |
| 30 | Alto | Preparar direcciones nativas junto a los AST de heads, literales y sistemas. Evita convertir cada `_rep` con CFFI cada vez que se arma una regla. | Owners acompañan cada dirección, también durante eviction; no pasan entre procesos. |
| 31 | Alto | Reemplazar la fuente `ReifiedClause` retenida por `(raw_count, ClauseMetadata)` al aceptar un representante. La primera ronda solo liberaba fuentes al finalizar. | Coste fuente, condiciones, preferencia por tamaño y empate textual intactos; IPC actualiza su formato interno directamente. |
| 32 | Medio | Internar objetos `ClauseMetadata` por las máscaras firmadas y coste resultantes. Antes se reutilizaba el cálculo de prefijos, pero se creaba otro objeto final. | Caché de 8192 por índice; costes diferentes no se mezclan. |
| 33 | Medio | Reutilizar traits aritméticos por `(mode_id, variables)`, excluyendo el slot. La caché anterior recibía el literal reificado completo. | Conserva máscara safe/numeric/output; section/slot no intervienen en esos traits. |
| 34 | Alto | Preparar la interfaz external/numeric del head una sola vez por head. Antes se recorría para cada uno de sus cuerpos aritméticos. | Caché acotada; forma completa del head y guards intactos. |
| 35 | Medio | Particionar builtins y atoms en una sola pasada, quitando el recorrido preliminar de detección. | Ruta aritmética; cuerpos sin builtin aún producen la misma receta vacía de sistemas. |
| 36 | Alto | Eliminar copias exactas de templates aritméticos antes del context-cache y del análisis de componentes. Antes se eliminaban al construir `ArithmeticSystem`, después de preparar contextos distintos. | Orientación, bindings y seguridad exactos; multiplicidad fuente sigue contando para recall y coste. |
| 37 | Medio | Retener el trait `ArithmeticSystem.linear` al construir el sistema. Evita recorrer sus relaciones para cada empate canónico. | Trait derivado fuera de igualdad/hash; remap lo vuelve a calcular. |
| 38 | Alto | Extender la prueba de independencia unary a `#maxv >= 1`. Antes el motor directo exigía exactamente uno. Linkedness fuerza una única variable compartida y density la llama V0. | Solo familia demostrada; no cambia `#maxv` ni la tarea. |
| 39 | Alto | Añadir heads normales unary input/any al motor de subconjuntos independiente. Antes solo admitía constraints sin heads. | Predicados distintos, tipo común, labels compatibles, propiedades excluidas y prueba original de optional constraints; otros heads usan ASP general. |
| 40 | Alto | Construir/formatear hasta 128 reglas directas por llamada nativa. La primera ronda procesaba cada combinación por separado. | Buffer acotado; output ordenado finalmente por `ClauseSpace`; sin diferir batches incrementales. |
| 41 | Alto | Derivar bindings forzados iguales desde una raíz anterior, sin abrir otra decisión de variable. | `bindings=properties`; únicamente atoms planos positivos del cuerpo con propiedad arg_equal compatible con tipos/labels. Constraints originales siguen presentes. |
| 42 | Alto | Excluir del dominio de elección un id ya usado en una posición anterior con arg_distinct probado. | `bindings=properties`; atoms planos, incluidos signos; puentes de propiedades permanecen en ASP. No interpreta constantes ni posiciones locales como argumentos planos. |
| 43 | Medio | Retener hasta ocho textos de facts por dominio exacto de slots en el generador. Antes cada preparación recompilaba modes, propiedades y θ. | Cache local al task y límites; assumptions/exact_size se añaden después. |
| 44 | Medio | Compartir `PropertyMaps` entre inferencia y compilación de facts. Antes se construía dos veces para los mismos modes. | `infer_maps=false` conserva su control previo; la compilación mantiene su filtro conservador. |
| 45 | Medio | Cachear el tamaño canónico del metaprograma fijo y de ocho textos de facts para métricas. Antes los solves repetidos volvían a formatear/parsear ese contenido diagnóstico. | Solo instrumentación; mismos campos, schema y contrato de charts. |

El decoder nativo mantiene una entrada Python por modelo y entrega valores
inmutables propios por bloques. No retiene `Model` ni un buffer perteneciente al
solver. La construcción fusionada usa las funciones del Clingo ya cargado,
preserva el ABI público 5.x y libera cada regla temporal después de formatearla.
No hay renderer manual de ASP ni reparsing de reglas completas.

`RuleRecipes` conserva los AST que respaldan las direcciones prestadas durante
la llamada nativa, aunque preparar un cuerpo largo expulse entradas de sus cachés.
El fallback construye AST nativos de la misma forma. Los consumidores siguen
pidiendo `Clause.statement`; no se cambia la evaluación del programa completo.

Las nuevas representaciones por propiedades permanecen optativas. Sus modelos
completos equivalen a los de la representación estándar, pero pueden cambiar
el orden de modelos y los prefijos incrementales, como cualquier modificación
del encoding. El motor directo solo se usa en generación completa; la incremental
conserva su enumeración ASP y presupuesto por modelos.

La validación diferencial compara texto, providers/deps firmados y coste fuente
de cada entrada. Cubre los 39 benchmarks con `--debug`, los cuatro Alzheimer,
controles en procesos nuevos, scopes/pools/heads, Unicode y buffers grandes,
eviction de owners, errores de registros, IPC y consumidores de ambas búsquedas.
En esta segunda ronda, cProfile cuenta `ModelRecords.push` cuando la reconstrucción nativa
ocurre por bloque, para no confundir llamadas de bloques con modelos capturados.
Su bucket de formato incluye construir/formatear/liberar la regla temporal
nativa; los costes acumulados no se suman ni se reescalan al neto de otra pasada.
La [tercera ronda](clause-generation-round3.md) introduce captura C sin callback
Python por modelo y verifica la cobertura mediante los constructores de filas.
