# Reutilización aritmética y poda temprana

Estado: implementado y medido sobre un control congelado el 2026-10-03.
Continúa las [reducciones de materialización](clause-materialization-reductions.md).
El control incluye esas optimizaciones anteriores, no compara contra una versión
antigua que todavía reconstruía todos los literales reificados.
Estas mediciones describen esta pasada. El [seguimiento posterior](arithmetic-context-reductions.md)
sustituye los conjuntos derivados por máscaras y amplía la poda de igualdad;
sus resultados se comparan contra este estado, sin sumar los porcentajes.

## Cambios

- `ReifiedLiteral` deriva una vez `(mode_id, variables)` y su `frozenset` de
  variables. La canonicalización reutiliza ambos. Sección y slot siguen en su
  igualdad y hash; la clave canónica conserva por separado cabeza y cuerpo.
- `LinearConstraint.instantiate` comparte hasta 8192 AST por fila exacta,
  relación y anchura. Es una caché global de sintaxis sin contexto, sin modes ni
  controles. No usa la equivalencia algebraica de una expresión como clave de
  rendering. Los consumidores construyen cambios con `AST.update`, conservando
  el nodo compartido. El límite cuenta entradas, no bytes.
- Una sola fila evita construir una matriz y ejecutar RREF. Un auxiliar se
  elimina solo con coeficiente unitario **antes** de reducir por el gcd, como
  en el control. `2*aux` no se convierte en una eliminación integral implícita.
  Las desigualdades conservan su orientación y los ceros su resultado anterior.
- La orientación de restricciones ya seguras devuelve las mismas filas en el
  mismo orden, sin tablas de consumidores, colas ni assignments intermedios.
- `ClauseCanonicalizer` omite la preparación de aritmética por modelo cuando
  no hay ningún builtin de cuerpo en la tarea.
- Las comparaciones positivas simples dejan de emitir `strict_comparison_args`:
  la política de self comparisons ya cubre todos sus operadores. Los demás
  links estrictos conservan su comprobación.

Las cachés de sistemas y de representantes mantienen su scope anterior: un
`ClauseCanonicalizer` para el espacio completo y otro para cada batch.

## Qué pasa de ArithmeticSystem a Clingo

`pruning/contradictions/comparisons.lp` puede descartar `X=Y` junto con
`X<Y`, `Y<X` o `X!=Y` antes de decodificar, si:

1. La igualdad es positiva, simple y de variables nominalmente numéricas.
2. Todos los builtins **seleccionados** son comparaciones simples numéricas.
3. Un átomo positivo plano hace externa y segura al menos una variable del par.

El compilador emite `numeric_equality_mode` y las excepciones
`complex_numeric_builtin_mode` solo si la tarea tiene esa igualdad en el cuerpo.
Un mode complejo declarado pero no seleccionado no bloquea la poda.

La igualdad tiene coeficientes unitarios y una variable externa; la fila
estricta o distinta se reduce a cero tanto al eliminar un auxiliar como mediante
RREF. Son modelos que Python ya devolvía como `None`, no nuevos descartes del
`ClauseSpace`. La normalización general continúa en Python.

La tarea mínima local `simple-numeric.lp` conserva exactamente sus 17 entries,
incluidos texto, proveedores, dependencias y coste. Clingo enumera **17 modelos
en vez de 26**: nueve descartes dejan de construir formas Python intermedias.
Esto demuestra menos trabajo por modelo; su escala no permite afirmar una
mejora general de tiempo.

Dos límites comprobados impiden ampliar ese guard indiscriminadamente:

- Un componente sin variables externas puede conservar la forma estructural
  `V0=0, V0!=0`. Suprimirla sería cambiar el espacio existente.
- `p(X,Y), 2*X=Y, 2*X<Y` se rechaza; añadir `X*X=Y` al mismo componente puede
  conservar el conjunto mediante el fallback no lineal. Un par proporcional
  no basta para decidir qué hará el componente completo.

No se añaden productos cruzados de coeficientes en ASP: Clingo y Python no
comparten el mismo rango de enteros. La sonda `65536*65536=0` de Clingo acepta
la igualdad por desbordamiento; una traslación general de Gauss con esos
productos exigiría resolver ese límite.

## Protocolo reproducible

Entorno: Windows 11, Python 3.14.6 y Clingo 5.8.2, Intel Core i7-13700H.
Task files de `benchmarks/gentians/` sin cambios. El directorio local ignorado
`.benchmarks/experiments/arithmetic-reuse-20261003/` conserva scripts, control
Python y ASP completos, streams de datos inmutables y reports generados.
Los reports contienen hashes del código, facts y programa ASP efectivo.

`paired.py` reproduce un stream completo idéntico en orden control/candidato,
candidato/control, control/candidato. Vacía las cachés de normalización y AST
entre muestras; crea un canonicalizer nuevo. No mide decode ni solving. El
fingerprint completo se calcula después del intervalo cronometrado. Una pasada
cProfile separada cuenta funciones, sin atribuir su tiempo al benchmark.

`probe.py` crea un proceso y Control nuevos por muestra, con caches frías. El
total incluye carga de AST en Control, grounding, solving, callbacks y
`ClauseSpace` final. Excluye parsing/análisis/facts comunes, fingerprint y
serialización. Separa grounding, decode, canonicalización y materialización;
el residual de solve se obtiene restando callbacks, y puede verse afectado por
la planificación de threads. No mide búsqueda evolutiva ni closure.

Ejemplos desde la raíz, sin reemplazar reports anteriores:

```powershell
$experimentRoot = '.benchmarks/experiments/arithmetic-reuse-20261003'
uv run python "$experimentRoot/paired.py" --dataset 8queens --input "$experimentRoot/queens-replay.pkl" --out "$experimentRoot/replay-repeat.json"
uv run python "$experimentRoot/probe.py" --dataset 8queens --control --out "$experimentRoot/control-repeat.json"
uv run python "$experimentRoot/probe.py" --dataset 8queens --current-lp --out "$experimentRoot/production-repeat.json"
uv run python "$experimentRoot/semantic.py" --control --out "$experimentRoot/semantic-control-repeat.json"
uv run python "$experimentRoot/semantic.py" --out "$experimentRoot/semantic-production-repeat.json"
```

Los intervalos de tiempo son cortos y durante parte del experimento había otra
ejecución Python consumiendo CPU. Los counts y fingerprints son más firmes que
las diferencias de wall-clock. No se interpreta menos grounding como menos
tiempo, ni estos resultados locales como una aceleración universal.

## Resultados

La última serie `final-full-*.json` incluye la eliminación del fact duplicado
de comparaciones simples. Medianas de tres procesos por versión y tarea, con
un thread. `alzheimer_acetyl` usa dos procesos por versión y cinco threads en
`full-alzheimer_acetyl-*.json`. Cada celda expresa **control → producción**,
en segundos; las medianas de las fases no tienen por qué sumar la del total.

| Tarea | Grounding | Decode | Canonicalización | Solve residual | Materialización | Total | CPU del proceso |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `8queens` | 0.043 → 0.049 | 0.171 → 0.204 | 1.273 → 0.853 | 0.599 → 0.691 | 0.016 → 0.017 | 2.105 → 1.830 | 2.031 → 1.656 |
| `subset_sum_double_and_prod` | 0.040 → 0.037 | 0.117 → 0.111 | 0.373 → 0.342 | 0.146 → 0.140 | 0.013 → 0.013 | 0.694 → 0.650 | 0.641 → 0.609 |
| `alzheimer_acetyl` | 0.526 → 1.166 | 14.262 → 15.358 | 21.331 → 20.637 | 26.595 → 25.649 | 2.540 → 2.178 | 65.271 → 65.024 | 147.297 → 142.188 |

La repetición de 8queens mejora el total un 13.1%; una pareja se invierte por
la variación de carga. Una serie anterior, antes del último cambio de facts,
dio 1.832 → 1.201 segundos. Ambas quedan conservadas: no se selecciona la
serie más favorable para afirmar una ganancia estable del total. Alzheimer
también invierte el resultado entre parejas y no muestra una mejora estable.

El replay sobre el mismo stream elimina la diferencia de orden y solving.
Las medianas de canonicalización más materialización, en
`paired-queens-native.json` y `paired-prod-native.json`, son:

| Tarea | Control | Producción | Reducción local |
| --- | --- | --- | --- |
| `8queens` | 0.951 s | 0.539 s | 43.3% |
| `subset_sum_double_and_prod` | 0.388 s | 0.378 s | 2.5% |

Cada pareja mejora en 8queens; la tarea mixta tiene una pareja invertida y la
misma mediana de CPU (0.375 s). Su pequeña diferencia de tiempo no basta para
atribuir una aceleración general a estas optimizaciones.

Los counts de trabajo separan efectos comprobados del ruido temporal:

- 8queens conserva 6697 modelos y 4797 cláusulas. La pasada de counts separada
  `paired-queens-native-counts.json` confirma **7854 → 390** ejecuciones del
  constructor de AST lineales: 7464 reutilizaciones y 390 filas exactas únicas.
  Las matrices RREF pasan de 4774 a 4742 por el caso singleton.
- La tarea mixta conserva 6858 modelos y 5547 cláusulas. Comparte 44 de sus
  66 construcciones de filas nativas; RREF pasa de 75 a 67. Las 566
  normalizaciones de expresiones siguen siendo necesarias.
- Quitar `strict_comparison_args` duplicado en 8queens reduce los atoms de
  grounding de 3056 a 3055 y las reglas de 15255 a 15234. El solver conserva
  8840 variables y 44871 constraints: la poda duplicada ya no llegaba al solver.
- Alzheimer conserva 289326 modelos y cláusulas, con el mismo fingerprint
  completo en las cuatro ejecuciones.
- `final-simple-{control,production}.json` mide la tarea local mínima, aunque
  el argumento de catálogo para límites de ejecución es `grandparent`. La
  producción enumera 17 modelos frente a 26 del control, con los mismos
  17 entries. El total de esta sonda diminuta no mejora: 0.038 → 0.041 s.

## Generación incremental

`semantic.py` compara control y producción con seed 31, batch size 113 y
enumeración hasta agotar el espacio. Los fingerprints incluyen texto,
proveedores, dependencias y coste. Coinciden los outputs completos y las uniones
de lotes para grandparent, 8queens, la tarea mixta, la sonda numérica y el
componente sin externos. Los fingerprints de cada lote también coinciden en
los tres datasets del catálogo y en el componente sin externos.

La sonda numérica pasa de tres lotes a dos: la poda temprana elimina modelos
que antes consumían presupuesto aunque Python los rechazara. Su unión conserva
las 17 cláusulas. El prefijo y los límites de lotes pueden cambiar al mover
descartes a Clingo; no se afirma que la trayectoria evolutiva tenga que coincidir.

La canonicalización incremental conserva representantes por lote, tal como
documenta `generator.py`; no guarda el historial global. Por eso no se exige
que su unión textual sea igual a una canonicalización global: en la tarea mixta
ambas versiones conservan 5663 entries en la unión incremental frente a 5547
globales. El primer assert del script detectó esta diferencia ya existente en
el control; la comprobación correcta compara cada ruta contra su control.
Los reports finales son `semantic-{control,production}-v2.json`.

## Alternativas descartadas

La caché adicional por componente conservaba los mismos outputs, pero aumentaba
las entradas de 4959 a 6705 en 8queens y de 674 a 1342 en la tarea mixta. Solo
evitaba cuatro normalizaciones de expresiones en esta última. Se retiró.

Factorizar los diez shortcuts de comparaciones en tres constraints y vistas de
pares mantiene su significado; Clingo no encuentra discrepancias sobre todos
los grafos de tres IDs. Sin embargo, en 8queens aumenta variables internas de
8840 a 8935 y constraints de 44871 a 45146. El original sigue en producción.
La comparación exige caminos de exactamente dos aristas seleccionadas; usar
`inferred_lt` o closure no preserva ese contrato.

## Cadenas y verificación

Aplican modes/facts, metaprograma, decoder/IR reificado, canonicalización,
generación completa e incremental y documentación. Sintaxis, lenguaje declarado,
estrategias, evaluación de hipótesis completas y cierre de dependencias siguen
con su contrato anterior. No cambian fases de `timing.py`, schema, charts ni
preview. Los diagramas de flujo conservan las mismas etapas.

Los tests nuevos cubren guards de la poda, igualdad con output, exclusión de
cabezas, complejidad declarada/seleccionada, fallback sin externos, conservación
de todos los entries, signos, auxiliares enteros y AST compartidos sin mutación.
La revisión independiente contrastó 13024 normalizaciones singleton y 3200
orientaciones contra el control, con resultados exactos.

Verificación final: 1204 tests de generación, compilación, metaprograma,
decodificación, profiling, búsqueda incremental y `syntax_matrix`; Ruff en los
Python modificados, `uv run ty check` y `git diff --check`, todos correctos.
No se ejecutó la suite completa ni cambió el dashboard.
