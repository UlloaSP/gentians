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
de combinaciones son posibles trabajos posteriores. No están implementados ni
medidos en este experimento. Ninguna variante demuestra una mejora general de
complejidad ni de generalización fuera de los ejemplos observados.

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
