# Cómo funciona la mutación actual

Los diagramas reflejan `RandomGroupMutation` y `HypothesisGenerator`, no una
arquitectura propuesta. No se ha cambiado el algoritmo para hacerlos.

## Abrir los diagramas

1. [Flujo general, salidas y reintentos](mutation-flow.html).
2. [Permisos según completitud y ejemplos](mutation-permissions.html).
3. [Añadir, eliminar y reemplazar por bloques](mutation-operations.html).
4. [Filtros y alternativas del reemplazo](mutation-replacement.html).

Cada HTML es autónomo. Las filas del mapa de permisos son casos alternativos;
las del mapa de operaciones son operaciones alternativas, no pasos consecutivos.
En el detalle de reemplazo, las filas descomponen los filtros y la construcción.
Las condiciones escritas en los nodos limitan las transiciones: una opción
apagada no se ejecuta por aparecer en el dibujo.

★ identifica un valor por defecto o vigente en el perfil indicado, incluso si
ese valor desactiva una opción. No significa que siempre se recorra esa rama.
Los sorteos y las condiciones del programa determinan el recorrido concreto.
Los controles propios del visor y su atributo `html lang` permanecen en inglés;
el contenido escrito del diagrama está en español.

## Valores exactos

| Opción | SDK `Arguments()` | Benchmark `recommended/general` | Efecto |
| --- | --- | --- | --- |
| `mutation.name` | ★ `random_group` | ★ `random_group` | Única estrategia registrada; la factory se conserva. |
| `probability` | ★ `0.9` | ★ `0.9` | Intentar mutar en el 90% de llamadas. |
| `completeness_guidance` | ★ `true` | ★ `true` | Usar el estado efectivo del programa de entrada. |
| `constraint_only_random` | ★ `false` | ★ `true` | Excepción cuando todo el espacio activo son constraints. |
| `random_jump_probability` | ★ `0.1` | ★ `0.1` | En reemplazos ordinarios, permitir otra firma de cabeza. |
| `complete_generator_removal_probability` | ★ `0.1` | ★ `0.1` | Intentar eliminar una raíz encabezada de un candidato completo. |
| `body_local_probability` | ★ `0.0` | ★ `0.0` | Desactivada la vecindad de un elemento del cuerpo. |
| `duplicate_retries` | ★ `0` | ★ `0` | Un intento externo; no reintentar por duplicado. |
| `repair_probability` | ★ `0.0` | ★ `0.0` | Desactivada la preferencia de reparación diagnosticada. |
| `evaluation.constraint_diagnosis` | ★ `false` | ★ `false` | No calcular cobertura potencial sin constraints. |
| `evaluation.constraint_inheritance` | ★ `false` | ★ `true` | Reutilización exacta de cobertura; no cambia permisos de mutación. |

Los nombres de las opciones de las filas intermedias pertenecen a `mutation`.
Estos valores no dependen del nombre del dataset. La excepción solo-constraints
depende del `ClauseSpace` activo, no de que el benchmark sea 5queens.

## 1. Entrada y clasificación

La entrada es el genoma que entrega crossover, no necesariamente uno de los
padres evaluados. Se sortea una sola vez la probabilidad de mutar. Si no toca,
se devuelve el mismo genoma con `skipped=True`, sin clasificarlo.

Si toca mutar, se obtiene el estado:

- Con la excepción solo-constraints activa y sin cláusulas encabezadas en el
  espacio disponible, solo se consulta `context.results`. No se evalúa un
  genoma desconocido para decidir la mutación.
- Fuera de esa excepción, con guía de completitud, `_result(classify=True)`
  consulta primero la caché. Si falta, existen positivos y hay evaluador en el
  contexto, evalúa el programa de entrada. Esa evaluación cuenta en el total.
- Sin guía, la propuesta ordinaria no usa clasificación. La reparación
  experimental puede consultar un resultado ya guardado sin forzar evaluación.

Una solución conocida se devuelve con `skipped=True`. Después se prepara la
reparación opcional y se descarta el estado para la propuesta ordinaria si está
activa la excepción solo-constraints o está desactivada la guía.

Un resultado completo significa que cubre todos los positivos de la tarea.
Consistente significa que no cubre ningún negativo. En esta mutación la
consistencia no introduce otra máscara: interviene en `is_solution` junto con
la completitud, y posteriormente en la evaluación del resultado.

## 2. Permisos ordinarios

| Estado efectivo, con positivos | Añadir | Eliminar | Reemplazar |
| --- | --- | --- | --- |
| Completo | Solo constraints | Constraints; excepción encabezada del 10% | Solo constraints |
| Incompleto | Solo encabezadas y su cierre permitido | Encabezadas o constraints | Ambos tipos; con negativos, conservar el tipo de raíz |
| No clasificado o estado descartado | Ambos tipos | Ambos tipos | Ambos tipos |

La restricción sin negativos se aplica después: no introducir constraints
nuevas. Las existentes pueden retirarse. Además, el constructor normaliza
candidatos cerrados sin negativos retirando constraints cuando queda una
hipótesis no vacía. Esa normalización también debe respetar la máscara del
cambio completo.

Sin positivos, la completitud vacía no protege generadoras. Se usa el caso sin
clasificación efectiva para los permisos, aunque pueda existir un resultado
guardado. La salida temprana por solución conocida sigue siendo aplicable.

En un completo con positivos y reglas encabezadas se sortea la eliminación
especial una vez por llamada, antes del bucle de reintentos. Si sale, cada
propuesta ordinaria prueba primero `remove(..., sources=headed)`. Puede retirar
la raíz y sus consumidores, también encabezados. Si consigue un cambio válido,
lo devuelve antes de barajar las operaciones ordinarias. Si no, continúa con
solo constraints. No hay alternativa que permita reemplazar generadoras.
Esta eliminación es un intento de simplificación, no una prueba de redundancia
ni una garantía de conservar la completitud.

## 3. Qué operación se prueba primero

`operations(genome)` forma una lista según el tamaño actual:

- `append` si el tamaño es menor que `#maxpl`.
- `remove` si contiene más de una cláusula.
- `replace` si el genoma no está vacío y existe alguna cláusula disponible no
  seleccionada.

Después `rng.shuffle` baraja esa lista. No hay prioridad fija y las operaciones
aceptadas no tienen necesariamente probabilidad 1/3: algunas pueden ser
inelegibles o no encontrar un cambio permitido. Se devuelve el primer cambio
válido, sin compararlo por fitness con otras alternativas. Si una operación
falla se prueba la siguiente; si todas fallan se devuelve el mismo genoma,
esta vez sin marcar que se omitió la mutación.

## 4. Cambiar una raíz puede cambiar varias reglas

El constructor es la única autoridad que modifica genomas.

- Añadir selecciona una raíz nueva permitida e incorpora proveedores que
  falten. El bloque completo debe caber en `#maxpl` y en `mutable`.
- Eliminar retira la raíz y después los consumidores que ya no tengan ningún
  proveedor. Repite hasta cerrar dependencias. Si existe un proveedor
  alternativo en el candidato o en el BK, el consumidor puede permanecer.
  No incorpora proveedores nuevos para reparar la eliminación.
- Reemplazar considera primero la cabeza de la cláusula nueva al calcular
  consumidores que pueden permanecer. Después retira los no soportados y cierra
  las dependencias del bloque añadido. Las cláusulas retiradas quedan
  prohibidas para ese cierre.

Por ejemplo, con BK `a.` y candidato `{p :- q., q :- a., r :- a.}`, eliminar
`q :- a.` también retira `p :- q.`. Queda `r :- a.`. En cambio, reemplazar
`q :- a.` por otra cláusula que defina `q/0` puede conservar el consumidor.
El ejemplo muestra cierre sintáctico, no contribución semántica o fitness.

Siempre se comprueban disponibilidad, no vacío, límite de tamaño, dependencias
y permisos sobre todos los bits modificados. Una raíz autorizada no basta si
su cascada altera una cláusula protegida.

El cierre prueba proveedores con prioridad estructural: más dependencias
faltantes resueltas, menos dependencias nuevas y cuerpo menor. Empates usan el
RNG. Tiene un presupuesto interno de búsqueda, por lo que un intento fallido
no prueba inexistencia matemática de todo cierre posible.

## 5. Firma de cabeza y localidad del cuerpo

En cada intento de la operación `replace`, fuera de la excepción solo-constraints,
se sortea `same_head`: 90% exige la misma firma y 10% no la exige. No son 90%
y 10% de todas las mutaciones, sino de esos intentos de reemplazo.

La firma usada aquí es `head_masks`: el conjunto de predicados definidos,
incluidos aridad y signo. No exige el mismo texto completo de cabeza, las mismas
variables ni conservar por sí sola la forma normal, disyuntiva o choice.
Conservar el tipo de raíz significa únicamente constraint frente a encabezada.
Todos los reemplazos siguen perteneciendo al lenguaje permitido.

El salto no obliga a cambiar firma y no anula `mutable` ni la conservación de
tipo. Si se exigió misma firma y no se encontró reemplazo, no se vuelve a
intentar automáticamente con otra firma.

La localidad del cuerpo es otra opción independiente, apagada. Si se activa,
busca añadir, quitar o sustituir un elemento del cuerpo en la escritura AST
canónica existente, con el mismo texto AST de cabeza. No infiere renombrados
adicionales de variables. Por tanto es más estricta que `same_head`.
Si no encuentra candidato, repite la operación sin localidad del cuerpo,
conservando los demás filtros. No hay búsqueda especial de relajación de
constraints.

## 6. Reparación experimental y reintentos

Para usar reparación deben cumplirse todas estas condiciones: probabilidad
positiva, resultado conocido incompleto, diagnóstico potencial conocido,
ejemplos positivos y constraints disponibles. Si la cobertura potencial es
completa, el objetivo es cambiar constraints; si no lo es, cambiar encabezadas.
Se exige un objetivo no vacío y acertar el sorteo. La máscara elegida se
intersecta con los permisos de la propuesta diagnosticada.

Si la propuesta guiada no cambia el genoma, se intenta la política ordinaria.
Si produce un cambio, se comprueba directamente el historial. Un cambio guiado
duplicado no provoca por sí mismo una propuesta ordinaria: consume el intento
externo. La preferencia y el sorteo de eliminación especial no se repiten al
reintentar; las propuestas vuelven a partir del genoma original.

El máximo de intentos externos es `duplicate_retries + 1`. Se devuelve antes
si la propuesta está omitida, no existe `context.seen` o el resultado no figura
en ese historial. Agotado el presupuesto, se devuelve la última propuesta,
incluso duplicada o sin cambio. El bucle de búsqueda decide si admitirla y usa
su caché para no volver a evaluar el mismo candidato.

## Evidencia y comprobación

Fuentes inspeccionadas:

- [Factory y parámetros](../gentians/evolution/mutations/__init__.py).
- [Decisiones y propuestas](../gentians/evolution/mutations/random_group.py).
- [Obtención de estado](../gentians/evolution/variation.py).
- [Operaciones y cierre](../gentians/hypotheses/generator.py).
- [Vecindad sintáctica](../gentians/hypotheses/body_neighborhood.py).
- [Admisión y evaluación](../gentians/algorithms/steady_state_genetic.py).
- [Defaults del SDK](../gentians/arguments.py) y [perfil recomendado](../benchmarks/experiments.toml).

Cada fuente JSON acompaña al HTML correspondiente. Los cuatro diagramas pasan
los nueve controles showcase, sin errores ni avisos. La comprobación de Chrome
cubre 1440×900, 1600×1000, 1920×1080 y 2048×1320. Los recibos conservan hashes
de fuente y HTML; la revisión visual se registra aparte de la prueba automática.
Véase [el recibo de entrega](mutation-diagrams.receipt.json).
