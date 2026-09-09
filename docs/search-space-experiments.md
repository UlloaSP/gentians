# Experimentos del espacio de búsqueda

Los resultados siguientes corresponden a la comparación del 7 de septiembre de
2026 sobre los task files originales de `5queens` y `grandparent`. El protocolo,
las semillas, los cortes y todas las métricas están en
[el informe de lotes y completitud](sampled-pool-experiment.md).

| Variante implementada | Resultado observado | Decisión |
| --- | --- | --- |
| Pool congelado desde el espacio exhaustivo | Reduce grounding de 5queens, pero aumenta tiempo total en ambos datasets. | No sustituye al control. |
| Generación de lotes acotados por época | Reduce el conjunto de cláusulas residente; empeora tiempo y evaluaciones hasta solución. Presenta un timeout en grandparent. | Experimental y descartada en esta comparación. |
| Operadores guiados por completitud | Mejora la media observada de grandparent y empeora la de 5queens. | Opción explícita; no es el comportamiento por defecto. |
| Lotes y operadores combinados | El tiempo acumulado de cuatro runs de 5queens impide mejorar la media del control incluso suponiendo coste cero para los restantes. | Descartada con autorización del usuario; grandparent no se ejecutó. |

Reutilizar el metaprograma ya groundeado para producir lotes y mejorar el muestreo
de combinaciones eran trabajos pendientes en esa comparación. La enumeración
continua se implementó y midió después en el experimento sintético descrito a
continuación. Ninguna variante demuestra una mejora general de complejidad ni
de generalización fuera de los ejemplos observados.

## Enumeración continua sobre 1.149.016 cláusulas

El 8 de septiembre de 2026 se compararon lotes reiniciados y enumeración continua
con evaluación fresca, tres semillas y 500 generaciones por run. El tiempo neto
medio bajó de 72,248 a 16,138 segundos y la generación de cláusulas de 64,383 a
6,539 segundos. Los groundings y solves del generador pasaron de diez a uno por
run. El ahorro principal fue Python; no se limita a evitar grounding repetido.

Ninguna variante encontró una hipótesis perfecta en ese presupuesto. La
enumeración continua obtuvo peor score en las tres semillas y cubrió más
negativos. Tres runs adicionales sin límite de generaciones agotaron el timeout
de 180 segundos sin solución. El cambio reduce el coste de generación, pero esta medición no
establece una búsqueda mejor. Sigue siendo una opción experimental desactivada
por defecto mediante `clause_pool.enabled=false`. Protocolo, resultados por
semilla y limitaciones figuran en [el informe del millón de cláusulas](million-clauses-experiment.md).

## Enumeración incremental por longitud

La validación posterior con cinco semillas nuevas, 11 a 15, conservó el task
sintético y el presupuesto de 500 generaciones. Ordenar por tamaño de cuerpo,
incluyendo condiciones adjuntas, superó al pool con sampling reiniciado en score
y tiempo neto en las cinco parejas. El score medio pasó de 58,688 a 4544,984 y el
tiempo neto de 129,932 a 14,691 segundos. La cobertura media de positivos bajó de
56 a 47,6 sobre 57; los negativos cubiertos bajaron de 14,8 a cero sobre 25.
Ningún método encontró una hipótesis perfecta.

El generador conserva un grounding y un solve reanudable por longitud. No elimina
cláusulas largas ni evalúa cláusulas por separado. `body_size` es ahora el orden
predeterminado de incremental, que sigue desactivado por defecto. El pool
reiniciado y el orden continuo original siguen disponibles como controles.
El orden fijo de ejecución y la carga variable del host limitan la precisión del
ratio de tiempo. Los resultados, modelos consumidos y protocolo están en
[el informe del millón de cláusulas](million-clauses-experiment.md#independent-validation-results).

La comparación posterior con 30 segundos netos de presupuesto y generaciones
ilimitadas también favoreció incremental en las cinco semillas. El score medio
fue 8718,316 frente a 24,079 del pool. Cubrió 52 positivos y 0,2 negativos de media,
frente a 56,8 y 17,4. Ninguna ejecución encontró solución perfecta. El corte es
cooperativo: un lote en curso llevó un control a 37,196 segundos totales, pero
ninguna evaluación posterior al plazo pudo mejorar el resultado devuelto.

## Reintentos y reserva de candidatos completos

El 7 de septiembre de 2026 se midieron el control actual, tres reintentos de
mutación ante duplicados, una plaza reservada para candidatos completos y su
combinación. Se ejecutaron 158 runs con seeds emparejados, timeout de 300 segundos
y sin límite de generaciones. No hubo timeouts. Dos runs de 5queens se omitieron
por el criterio autorizado de tiempo acumulado frente a diez originales.

Los reintentos redujeron generaciones de 5queens, pero no mejoraron su tiempo
frente al control actual y aumentaron las evaluaciones de grandparent. La reserva
y la combinación tampoco superaron al original en 5queens. Ambos parámetros
están implementados como opciones experimentales, con valor cero por defecto.
El [informe completo](directed-exploration-experiment.md) conserva configuración,
entorno, tiempos individuales, evaluaciones, descomposición temporal y límites
de la comparación.

## Localidad de cuerpo 80% y reemplazo global 20%

La comparación posterior ejecutó de nuevo original, actual y localidad 80%.
El índice busca una edición de literal de cuerpo manteniendo la cabeza exacta,
con fallback global y sin asumir relajación. En grandparent, diez seeds dieron
una media de 0,395 s frente a 0,569 s del actual y 1,536 s del original. En los
tres seeds medidos de 5queens empeoró las evaluaciones y el tiempo; se descartaron
los siete restantes porque el acumulado superaba los diez originales completos.
La opción se retiró el 2026-09-08. El [informe de localidad](body-locality-experiment.md)
conserva protocolo, índice, memoria, tiempos individuales y límites de evidencia.
# Mutation regression ablation and structural policy

The five batches in [the mutation ablation report](mutation-ablation-experiment.md)
contain 322 successful executions with full instrumentation, 300-second timeouts
and no generation limit. They reject global removal of completeness guidance,
head-filter removal, skipping only the head draw, and delayed classification as
ways to recover original 5queens performance while preserving grandparent gains.
The unsuccessful delayed-classification implementation was removed.

The retained option is `mutation.constraint_only_random=true`, false by default.
It uses unrestricted random edits in active pools containing only constraints and
retains directed mutation when headed clauses exist. It permits constraint
additions to incomplete candidates because they can improve negative coverage,
even though they cannot recover positives. A whole-program evaluator test covers
that counterexample to the earlier "useless addition" assumption. This is a search
preference, not a semantic pruning proof or a dataset-name branch.

The final interleaved confirmation ran ten seeds per dataset and implementation.
Mean net 5queens time was 6.090 seconds for historical original, 9.686 for current
control and 5.569 for the structural option. Grandparent means were 1.495, 0.484
and 0.485 seconds. Every recorded non-time GA field matched original in 5queens
and current control in grandparent. Earlier original-first batches had larger
timing gaps despite identical search counts, so the small final lead over original
5queens is not treated as a general speedup. See the report for every rejected
configuration, matched-prefix controls, source hashes and phase costs.
# Exact constraint-coverage inheritance

The `semantic-inheritance/control` and `semantic-inheritance/partial` entries
compare the current structural mutation policy with and without proof-based
coverage reuse. Three paired batches, 120 successful runs with a 30-second
timeout and unlimited generations, preserved every non-time GA trajectory.
The final implementation reduced 5queens mean net time from 7.192765 to 6.440562
seconds, with 36.76% fewer candidate-example queries. Grandparent remained
effectively unchanged, 0.525014 versus 0.522700 seconds; the optimization disables
itself when the prepared space contains no constraints. Earlier implementations
added overhead there. The feature remains opt-in pending unseen-seed validation.
See [all variants, guarantees and limits](semantic-inheritance-experiment.md).

## Constraint diagnosis and repair preference

`semantic-repair/control`, `semantic-repair/diagnosis` and
`semantic-repair/repair80` compare the latest inheritance baseline with an exact
positive-coverage ceiling and an optional role-directed mutation preference.
Only 5queens and grandparent were tested, with ten scheduled paired seeds,
30-second wall timeouts and no generation cap. Across two batches, 94 of 95
attempted runs succeeded; one timeout stopped that variant's remaining five
first-batch runs.

Diagnosis alone preserved all recorded non-time GA trajectories. After fixing
an inert random draw on spaces without constraints, final repair still increased
5queens mean net time from 4.767414 to 8.028273 seconds and evaluations from
1029.6 to 2000.4. Grandparent kept the control trajectory, with means 0.524320
and 0.546950 seconds. A correct diagnosis did not identify an effective repair.
Both options remain disabled by default. Whole-program mutation effects are
logged from existing evaluations, without additive rule credit. See
[all tested variants and limitations](semantic-repair-experiment.md).

## Structural diversity at initialization

`population-diversity/control` and `population-diversity/structural` compare
random initialization with bounded structural oversampling, size balancing and
Jaccard-distance selection. Only selected candidates receive fitness evaluations.
All 80 paired runs succeeded across 5queens, grandparent, coloring and knapsack,
with ten runs per variant, 30-second timeouts and unlimited generations.

Mean evaluations changed from 1029.6 to 1503.0 in 5queens, 446.1 to 1079.7 in
grandparent, 207.4 to 163.4 in coloring and 13.6 to 10.7 in knapsack. Mean net
times changed by +32.85%, +140.11%, -19.32% and -0.70% respectively. The new
strategy is retained as experimental, not selected for `recommended/general`.
Structural diversification did not provide a consistent cross-task benefit.
See [protocol, medians, initialization costs and limitations](population-diversity-experiment.md).

## Steady-state e incremental con timeout de 30 segundos

La comparación del 9 de septiembre de 2026 ejecutó diez runs por algoritmo y
dataset, con semillas emparejadas y sin límite de generaciones. Steady-state
resolvió 10/10 en 5queens y 10/10 en grandparent. Incremental resolvió 7/10 y 2/10,
respectivamente; los otros once runs agotaron el timeout de proceso de 30 segundos.
Los tiempos netos medios entre soluciones fueron 5,312 y 0,439 segundos para
steady-state, frente a 6,093 y 0,158 para incremental. Esta última media de
grandparent solo representa dos éxitos y no indica mejor rendimiento global.
Todos los éxitos tuvieron score 22026,466. Los timeouts no exportaron score final.
El protocolo y cada run están en [el informe incremental](incremental-experiment.md#completed-paired-results).
