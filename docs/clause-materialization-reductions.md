# Reutilización en la materialización de cláusulas

Experimento del 3 de octubre de 2026. Control: `b7fea7a`, después de las
reducciones de tuple-mutex y dominios de variables. Se integraron dos cachés
Python acotadas. Tareas, ASP y condiciones de pruning conservan su significado.

## Implementación

- El decoder de cada `Control` reutiliza `ReifiedLiteral` por sección, slot,
  mode e ids de variables. Son valores inmutables sin modelos ni handles
  nativos. Su caché LRU conserva como máximo 8192 entradas y termina con el
  decoder; incremental puede reutilizarlas entre sus lotes.
- `ClauseCanonicalizer.finish()` reutiliza proveedores, dependencias y coste
  de cuerpo por las secuencias completas de modes de cabeza y cuerpo. Estos
  datos no dependen de los bindings. La caché LRU también tiene 8192 entradas,
  vive solo durante esa materialización y usa los modes de esa tarea. Cada
  lote incremental mantiene su propia materialización.

Las claves conservan signos, multiplicidad de condiciones y cuerpos distintos.
Expulsar una entrada solo exige reconstruir un valor; no poda cláusulas. El
representante canónico se elige antes de calcular metadatos. Construcción y
renderizado del AST usan las APIs existentes de Clingo. `ClauseSpace` conserva
deduplicación y orden final.
La evaluación sigue consumiendo la hipótesis completa.

El helper de metadatos sustituye directamente a `_clause_from_reified`; se
actualizaron todos sus consumidores. cProfile clasifica su coste en el mismo
bucket de construcción. No cambian fases, productor, schema ni charts del
dashboard. La carga `head_metadata` de `profile_clause_followups.py` sigue
midiendo cálculo sin caché; no demuestra la ganancia de `finish()`.

## Protocolo y reproducción

Python 3.14.6, Clingo 5.8.2, Windows 11 e Intel Core i7-13700H. Los controles
ASP y Python se congelaron antes de editar producción. Sources, tareas,
argumentos, programas efectivos, reports y scripts quedan en
`.benchmarks/experiments/encoding-order-20261003/`. Los JSON son salidas del
harness, sin edición manual.

Se separaron tres mediciones, sin cProfile:

1. Decode de los mismos 65.536 modelos vivos con ambas variantes, alternando
   cuál va primero y exigiendo igualdad de cada `ReifiedClause`.
2. Replay de las 289.326 cláusulas reificadas de Alzheimer fuera de Clingo.
   Tres muestras por variante, orden alternado y caché de instanciación vacía.
   El stream retenido no mide el pico de memoria del pipeline.
3. Enumeración exhaustiva integrada: control Python congelado y producción
   sobre los mismos facts y ASP, `5,split`, `stats=2`, controles nuevos y sin
   captura del stream. Dos muestras por variante en orden ABBA. El intervalo
   incluye añadir el programa, grounding, preparar el decoder, solving,
   callbacks y construir `ClauseSpace`; excluye preparación común de tarea y
   facts, fingerprinting y escritura de reports. Clocks iguales en callbacks
   separan decode, canonicalización y el residual de solving. Ese residual es
   wall-clock fuera del callback, no CPU nativa pura.

Closure y búsqueda evolutiva no participan en estos intervalos. Los clocks de
callback pueden afectar al scheduling con varios threads; las diferencias
no se extrapolan a todas las tareas.

Reproducción local desde la raíz, conservando el control congelado:

```powershell
uv run python .benchmarks/experiments/encoding-order-20261003/python.py --mode live --limit 65536 --out .benchmarks/experiments/encoding-order-20261003/literal-live-repeat.json
uv run python .benchmarks/experiments/encoding-order-20261003/python.py --mode replay --capture .benchmarks/experiments/encoding-order-20261003/replay.pkl --repeats 3 --out .benchmarks/experiments/encoding-order-20261003/metadata-replay-repeat.json
uv run python .benchmarks/experiments/encoding-order-20261003/research.py --variants control production --python-control --repeats 2 --out .benchmarks/experiments/encoding-order-20261003/python-integrated-repeat.json
```

## Resultados

| Medida | Control | Reutilización |
| --- | ---: | ---: |
| Decode acumulado de los mismos 65.536 modelos | 2,395 s | 2,188 s |
| Materialización final del replay completo, mediana | 1,923 s | 0,934 s |
| Enumeración integrada, mediana del intervalo descrito | 36,742 s | 36,048 s |
| Decode integrado, mediana | 11,183 s | 10,215 s |
| Materialización final integrada, mediana | 1,385 s | 1,117 s |
| CPU del proceso integrada, mediana | 87,094 s | 89,406 s |

Decode aislado baja un 8,6% y la etapa final del replay un 51,4%. La
enumeración completa baja aproximadamente un 1,9% en estas cuatro muestras,
mientras CPU aumenta un 2,7%; no se demuestra una mejora global estable.
Las ganancias verificadas pertenecen a las etapas Python indicadas.

Cada enumeración integrada solicita 1.683.196 literales reificados. Producción
tiene 863 fallos y 1.682.333 aciertos; el control construye un `ReifiedLiteral`
por solicitud. Esto no mide todas las asignaciones Python ni demuestra una
reducción del pico RSS. El replay de metadatos registra 261.624 aciertos y
27.702 fallos; 16.828 valores de metadatos distintos explican por qué 8192
entradas no eliminan todos los fallos.

Las enumeraciones completas conservan 289.326 modelos y cláusulas, con el
hash de texto y metadatos
`44f8cb5181ee57dc45c6aec1947d03aea0dd50321825321489fa6f79d7461836`.
Variables internas, constraints y reglas ground no cambian con estas cachés.

## Otras reducciones investigadas

Cadenas de orden de modes, prefijos para comparar bindings y una alternativa
a los mínimos de primera aparición apenas reducen o aumentan el encoding.
Eliminar una propagación redundante de linkedness solo ahorra 156 variables
y 780 constraints internos en la prueba de tamaño. No se integraron.

La alternativa más prometedora proyecta aristas transitivas sobre sus extremos.
Para una relación irreflexiva, una variable por placeholder y la exclusión
existente de self-pairs prueban que el atajo no puede ocupar el slot de ninguna
arista del camino. La vista de atajos conserva un testigo concreto con
`not flow_needed(Slot)`. La transitividad general conserva sus restricciones
de slots y el triángulo acíclico, su orden original.

| Encoding en Alzheimer | Variables internas | Constraints internos |
| --- | ---: | ---: |
| Control actual | 26.158 | 450.849 |
| Proyección de aristas del prototipo | 34.339 | 338.016 |

El prototipo conserva el hash completo, pero las cuatro ejecuciones tienen
tiempos muy variables y no acreditan una mejora consistente. El primer control
además capturaba el stream, por lo que no es un control temporal equivalente.
Reducir constraints no basta para integrarlo. Estos cambios ASP quedan
**no implementados**.

También se comparó producción con uno y cinco threads en orden ABBA, dos
muestras por configuración. El mismo hash completo se conserva. Un thread
usa aproximadamente un 51% menos CPU del proceso, pero tarda más:
medianas de 45,680 s frente a 38,775 s con cinco. El residual de solving pasa
de 13,183 a 31,867 s; los callbacks Python de un thread son más baratos,
pero no compensan la búsqueda nativa. No se cambió el default. Son medidas
de esta tarea, no una política general de selección de threads.

## Verificación y cadenas aplicables

Pasaron 1177 tests de cláusulas, compilación, pruning, sintaxis, perfiles y
enumeración/búsqueda incremental. Las regresiones nuevas cubren slots y
bindings, aislamiento entre decoders y tareas, signos y costes de condiciones.
Una revisión independiente contrastó cada decode y los entries ordenados con
el control en casos de cabezas, agregados, aritmética y términos anidados.
Ruff en los paths Python modificados y `uv run ty check` también pasan.

`grandparent` (326 cláusulas), `8queens` (4797) y
`subset_sum_double_unbalanced_count` (21005) conservan sus hashes completos.
Con seed 31 y lotes de 113 modelos, también coinciden los fingerprints de cada
lote incremental y de su unión entre control y producción.

Aplicaban generación (decode, canonicalización y metadatos), algoritmos
(materialización completa y por lotes), diagnóstico de perfiles y docs. No
cambian sintaxis o significado del lenguaje, estrategias, cierre de dependencias
ni contrato de cobertura.
