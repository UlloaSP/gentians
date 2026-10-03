# Reutilización de componentes, expresiones y poda de aliases

Estado: implementado y medido el 2026-10-03. Continúa la
[pasada de máscaras y filas proporcionales](arithmetic-linear-reductions.md).
El control incluye todas aquellas mejoras. Los resultados siguientes no son
una comparación contra `HEAD` ni porcentajes acumulables con pasadas anteriores.

## Cambios

La partición de literales aritméticos conectados se calcula a partir de sus
máscaras de variables originales, independientemente de modes, coeficientes y
contextos. Una caché LRU global de hasta 8192 entradas conserva únicamente la
secuencia de máscaras y los índices de cada componente. Conserva el orden de
primera aparición de los componentes y el orden original de sus literales.
El recorrido repite la expansión hasta cerrar conexiones que aparecen más
tarde; no crea un dominio de tamaño `max_variables` ni un árbol union-find por
contexto. Usa los bindings originales para agrupar; la máscara de coeficientes
no nulos sigue decidiendo anclajes y auxiliares de la normalización.

`ArithmeticExpression.instantiate()` comparte hasta 8192 términos AST nativos
por **estructura exacta y ordenada**: operadores, argumentos, variables,
constantes y símbolos. Reutiliza el hash y la igualdad iterativos existentes.
No utiliza la clave algebraica: `V0+V1` y `V1+V0` pueden tener igual clave y
distinto texto. `ExpressionConstraint` y `TermComparisonConstraint` conservan
sus wrappers, outputs, seguridad y guards. Los consumidores construyen cambios
con `AST.update`; no modifican el término compartido. Las dos cachés sobreviven
a un batch, pero no retienen tareas, modes, controles ni modelos. Son límites
de entradas, no de bytes; expresiones grandes pueden retener árboles grandes.
El cálculo de una partición nueva recorre la pequeña secuencia de literales
hasta su cierre; su peor caso es cuadrático en el número de literales.

La compilación amplía la poda de filas proporcionales a aliases demostrablemente
seguros. Con hasta dos coeficientes no nulos cuya suma no sea cero, repetir una
variable no puede borrar la columna anclada. Por ejemplo, `p(X), 2*X=X,
4*X<2*X` ya puede rechazarse en Clingo. Las filas de más de dos columnas o de
suma cero emiten `numeric_linear_distinct_mode`: siguen requiriendo bindings
distintos, porque una cancelación total o parcial puede borrar el anclaje.
Se mantienen los guards anteriores: bindings ordenados iguales, anclaje positivo
plano y todos los builtins seleccionados elegibles para la ruta homogénea
numérica lineal. Python reutiliza sus analizadores existentes para preparar
esta prueba una vez; ASP no calcula productos de coeficientes.

En `pruning/redundancy/comparisons.lp`, los helpers de conflicto de tipos y
recall se derivan sólo para los modes `<` y `>` que los consumen. El pool nativo
`(lt; gt)` evita añadir otro predicado o facts. Esta simplificación conserva
los guards de tipos nominales, recall agotado y orientación inversa de `>`.

## Protocolo y control

Windows 11, Python 3.14.6, Clingo 5.8.2 e Intel Core i7-13700H. Tasks del catálogo
intactos; un hilo de Clingo y `stats=2`. El directorio local ignorado
`.benchmarks/experiments/arithmetic-components-20261003/` conserva:

- `control/gentians/`: snapshot completo de Python y ASP antes de esta pasada.
- `queens-replay.pkl` y `prod-replay.pkl`: los mismos streams inmutables usados
  anteriormente, con 6697 y 6858 modelos completos.
- `probe.py`: procesos nuevos para carga en Control, grounding, solve, decoder,
  canonicalización y `ClauseSpace` final. Parsing, análisis y preparación de
  facts quedan fuera del intervalo. Los reports incluyen hashes de fuente,
  facts, programa, tarea, argumentos y entorno.
- `replay.py`: los mismos modelos y modes, sin Clingo ni decoder en el intervalo.
  Incluye canonicalización y materialización final; excluye preparación,
  fingerprint y escritura. Las cachés nativas y de normalización se vacían
  antes de cada muestra.
- `work_counts.py`: cProfile sólo para contar trabajo, nunca para afirmar tiempo.
- `semantic.py`: enumeración completa y agotamiento incremental, seed 31 y
  batches de 113 modelos, con fingerprints de texto, metadatos y orden.
- `series.py`: cinco pares de procesos independientes, alternando C/P y P/C;
  perfiles y tests fuera de las series. Conserva cada report y su resumen.

La serie ASP compara el mismo Python y los mismos facts actuales, variando sólo
ASP congelado frente a ASP actual. Una segunda serie de replay usa afinidad
Windows `4` únicamente dentro de cada proceso medido y tres repeticiones frías
por proceso; cada par compara sus medianas. No cambia la afinidad de Gentians
en producción. Los resultados iniciales se conservan aunque salgan peores.

## Trabajo eliminado

Conteos sobre los mismos streams completos; fingerprints idénticos:

| Operación | 8queens control → actual | Caso mixto control → actual |
| --- | ---: | ---: |
| Contextos aritméticos calculados | 4959 → 4959 | 674 → 674 |
| Particiones de componentes calculadas | 4959 → 1391 | 674 → 84 |
| Hits de particiones reutilizadas | 0 → 3568 | 0 → 590 |
| Construcciones nativas de expresiones | 0 → 0 | 1044 → 165 |
| Nodos `Variable` construidos | 1009 → 1009 | 2333 → 1215 |
| Nodos `BinaryOperation` construidos | 1029 → 1029 | 2136 → 899 |
| Nodos `Comparison` construidos | 390 → 390 | 1066 → 1066 |
| Eliminaciones RREF | 4742 → 4742 | 67 → 67 |

En el caso mixto se evitan el 84,2% de las reconstrucciones de expresiones y el
57,9% de las operaciones binarias nativas. Los wrappers de comparación y las
566 normalizaciones de expresiones siguen existiendo. No se introduce una
caché global de sistemas normalizados ni se traslada la eliminación general.

En `proportional-expanded.lp`, la ampliación ASP cambia:

| Medida | Control → actual |
| --- | ---: |
| Modelos decodificados | 1862 → 1793 |
| Cláusulas finales | 390 → 390 |
| Átomos ground | 1809 → 1804 |
| Reglas ground | 6159 → 6146 |
| Variables internas del solver | 3646 → 3629 |
| Constraints internas, genéricas + binarias + ternarias | 16913 → 16845 |

Son 69 modelos adicionales rechazados antes de Python, un 3,7% en esta tarea
sintética. En los dos benchmarks del catálogo, grounding y estructura interna
del solver conservan sus conteos; no se atribuye a los helpers una reducción
de estructura que Clingo no muestra allí.

## Tiempos y límites de la evidencia

Medianas en segundos de cinco pares, con procesos nuevos:

| Intervalo | Control | Actual | Pares con menor wall |
| --- | ---: | ---: | ---: |
| Replay 8queens, afinidad libre | 0,7394 | 0,7341 | 4/5 |
| Replay mixto, afinidad libre | 0,4596 | 0,6049 | 1/5 |
| Replay 8queens, afinidad 4, mediana de tres repeticiones | 0,6348 | 0,6222 | 3/5 |
| Replay mixto, afinidad 4, mediana de tres repeticiones | 0,4006 | 0,3781 | 4/5 |
| Generación completa 8queens | 1,4883 | 1,4031 | 3/5 |
| Generación completa mixta | 0,8434 | 0,8345 | 4/5 |
| ASP aislado, proportional-expanded | 0,2751 | 0,2756 | 3/5 |

Las medianas CPU del replay libre son 0,7031 → 0,6406 y 0,4219 → 0,5625;
con afinidad son 0,5156 → 0,5313 y 0,3750 → 0,3594. La generación completa
da 1,4844 → 1,3125 y 0,7969 → 0,7656. El sintético ASP da 0,2813 → 0,2656.

La dispersión impide afirmar una aceleración global estable. Por ejemplo, la
generación completa de 8queens varía de 1,1428 a 1,9341 en control y de 1,1223
a 2,3038 en actual. El replay mixto cambia de dirección entre series. Se
conservan las reducciones por sus conteos reproducibles de trabajo y reutilización;
los porcentajes de construcciones evitadas no son porcentajes de tiempo ganado.

El desglose de generación completa conserva los límites de atribución:

| Fase | 8queens control → actual | Mixto control → actual |
| --- | ---: | ---: |
| Grounding | 0,0573 → 0,0487 | 0,0471 → 0,0527 |
| Decoder | 0,1655 → 0,1574 | 0,1525 → 0,1529 |
| Canonicalización | 0,6515 → 0,6122 | 0,4332 → 0,4179 |
| Solve excluyendo callbacks medidos | 0,5915 → 0,5621 | 0,1880 → 0,1893 |
| Materialización final | 0,0130 → 0,0137 | 0,0177 → 0,0171 |

Son medianas por campo, no sumandos de la mediana total. Tampoco son tiempos de
la búsqueda evolutiva. Closure, evaluación de cobertura, `timing.py`, schema y
charts no cambian ni se miden en este experimento. No se ha medido RSS ni se
afirma una reducción de memoria del proceso.

## Equivalencia y verificación

Los fingerprints completos e incrementales coinciden con el control en ocho
tareas: grandparent (326), 8queens (4797), subset_sum_double_and_prod (5547
completas / 5663 incrementales), simple_numeric (17), equality_chain (4),
proportional (8), proportional_expanded (390) y output_only (1).
La diferencia completa/incremental del caso mixto ya existe en el control.
Los batches coinciden exactamente salvo en el sintético ampliado: 20 → 19
batches, con la misma unión final, por los rechazos anteriores al presupuesto.

Los tests contrastan particiones con un grafo independiente, bridges que exigen
otra expansión, componentes desconectados y variables por encima de 64;
reutilización exacta frente a igualdad algebraica; AST.update; tipos y recalls
de ambos operadores estrictos; aliases seguros y cancelaciones total/parcial.
La poda también se compara con generación sin ese bloque ASP. Las formas con
anclaje cancelado se comprueban presentes, no sólo por conteo final.

La revisión independiente no encontró regresiones funcionales. Sus observaciones
de documentación se incorporaron a language-bias, task-language, arquitectura,
schema y vocabulario del metaprograma. La cadena afectada es compilación de
facts → metaprograma → canonicalización → generación completa e incremental →
documentación. Lexer, parser, IR de tarea, constructor de hipótesis, operadores
evolutivos y cobertura no necesitan cambios para estas reducciones.

Verificación final: 1280 tests de cláusulas, compilación, metaprograma, perfiles,
generación incremental y matriz de sintaxis pasaron; Ruff, `ty check` y
`git diff --check` también pasaron. No se añadieron thresholds de velocidad a
los tests, ni se modificaron tasks o resultados de experimentos anteriores.
