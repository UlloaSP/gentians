# Mutación de hipótesis completas sin constraints activas

## Problema y cambio

`even_odd` podía alcanzar una hipótesis completa pero inconsistente en un
`ClauseSpace` sin constraints. La política protegía entonces todas sus cláusulas
con cabeza: solo permitía el intento especial de eliminación y después limitaba
las operaciones ordinarias a una máscara vacía. Algunas ejecuciones dejaban de
evaluar candidatos nuevos aunque continuaran produciendo generaciones.

El cambio conserva la protección cuando el espacio activo contiene constraints.
Cuando no contiene ninguna, una hipótesis completa no perfecta usa las mismas
operaciones ordinarias que una hipótesis no clasificada: append, remove y replace,
con el sorteo de firma de cabeza 90/10 y el cierre de dependencias habituales.
Las hipótesis perfectas siguen protegidas. La condición usa el espacio activo,
incluidas las renovaciones incrementales.

## Protocolo pareado

Se congelaron snapshots del código anterior y posterior. Cada variante ejecutó
las semillas 1–30 sobre `4queens`, `5queens`, `adj2red`, `clique`, `coin`,
`coloring`, `even_odd`, `grandparent` y `sudoku`. El orden anterior/posterior se
alternó por semilla y las ejecuciones fueron secuenciales.

Ambas variantes usaron los defaults del SDK, `steady_state`, población 10,
lexicase, `set_mix`, mutación 0,9 y un límite diagnóstico de 20.000 generaciones.
Cada proceso generó su propio `ClauseSpace`. La instrumentación fue idéntica y
se excluyó del tiempo observado. Los hashes de fuentes se comprobaron antes y
después. No hubo timeout en esta fase.

| Dataset | Anterior | Posterior | Búsquedas idénticas | Tiempo anterior, s | Tiempo posterior, s |
| --- | ---: | ---: | ---: | ---: | ---: |
| 4queens | 30/30 | 30/30 | 30/30 | 0,242 | 0,243 |
| 5queens | 30/30 | 30/30 | 30/30 | 7,149 | 7,264 |
| adj2red | 30/30 | 30/30 | 5/30 | 0,078 | 0,079 |
| clique | 30/30 | 30/30 | 30/30 | 0,072 | 0,071 |
| coin | 30/30 | 30/30 | 30/30 | 0,039 | 0,038 |
| coloring | 30/30 | 30/30 | 30/30 | 0,277 | 0,274 |
| even_odd | 20/30 | 25/30 | 2/30 | 0,112 | 0,167 |
| grandparent | 30/30 | 30/30 | 30/30 | 0,932 | 0,926 |
| sudoku | 30/30 | 30/30 | 30/30 | 0,071 | 0,070 |

Los tiempos son medias netas de `total_execution` entre soluciones; no incluyen
los runs que agotaron generaciones y por eso no representan el coste esperado
de `even_odd`. En los datasets con búsquedas idénticas, las diferencias pequeñas
son variación de ejecución. `adj2red` también puede entrar en el nuevo caso:
cambia trayectorias, pero conserva 30/30 y el mismo orden de tiempo.

## Validación de `even_odd` a 120 segundos

La variante posterior se ejecutó otra vez sin límite de generaciones y con 120
segundos por run. Resolvió 27/30. La media PAR1 wall-clock fue 13,018 s; entre
los 27 éxitos, `total_execution` medio fue 1,065 s y la mediana 0,112 s.

Las semillas 10 y 24, que fallaban al cortar en 20.000 generaciones, resolvieron
en 58.297 y 113.436 generaciones, respectivamente. Las semillas 11, 17 y 28
agotaron el timeout. Llegaron aproximadamente a 1,03–1,30 millones de
generaciones, pero solo a 4.310, 4.920 y 11.261 evaluaciones únicas. En sus
últimas 8.000 generaciones añadieron una, una y seis evaluaciones. La cola
restante es otro estancamiento por duplicados y convergencia de población; ya no
es la máscara vacía que este cambio corrige.

Si se compara con el resultado mostrado anteriormente para la misma matriz
(17/30 y 52,153 s PAR1), el cambio pasa a 27/30 y 13,018 s. Esa comparación usa
el artefacto previo mostrado, no una nueva repetición local del control sin
límite; el resultado pareado anterior es la evidencia aislada del cambio.

## Steady-state restart

La inspección de las tres colas restantes mostró convergencia de población: más
de un millón de generaciones producían muy pocos genomas nuevos. Se añadió al
bucle steady-state la misma señal fija ya usada por la búsqueda incremental:
100 generaciones sin una mejora estricta de score. El reinicio conserva el
campeón, vuelve a muestrear el resto de la población y mantiene las cachés
globales de individuos y evaluaciones. Por tanto, no vuelve a ejecutar Clingo
sobre un programa ya visto. Solo se aplica si el espacio preparado contiene
cláusulas encabezadas; la búsqueda solo-constraints conserva su trayectoria.

La variante con reinicio se ejecutó sobre los nueve datasets, las mismas 30
semillas, el límite de 20.000 generaciones y los mismos parámetros anteriores.
Se comparó con los resultados ya guardados de la variante de mutación ordinaria.
Las ejecuciones no fueron intercaladas de nuevo, por lo que los tiempos sirven
para comprobar el orden de magnitud, no para atribuir diferencias pequeñas al
reinicio. Éxitos, generaciones y evaluaciones sí describen las trayectorias
deterministas de cada snapshot.

| Dataset | Sin reinicio | Con reinicio | Trayectorias idénticas | Evaluaciones sin/con | Tiempo sin/con, s |
| --- | ---: | ---: | ---: | ---: | ---: |
| 4queens | 30/30 | 30/30 | 30/30 | 68 / 68 | 0,243 / 0,287 |
| 5queens | 30/30 | 30/30 | 30/30 | 1.541 / 1.541 | 7,264 / 7,021 |
| adj2red | 30/30 | 30/30 | 29/30 | 45 / 48 | 0,079 / 0,094 |
| clique | 30/30 | 30/30 | 30/30 | 26 / 26 | 0,071 / 0,083 |
| coin | 30/30 | 30/30 | 30/30 | 7 / 7 | 0,038 / 0,043 |
| coloring | 30/30 | 30/30 | 16/30 | 197 / 180 | 0,274 / 0,296 |
| even_odd | 25/30 | **30/30** | 13/30 | 212 / 233 | 0,167 / 0,211 |
| grandparent | 30/30 | 30/30 | 3/30 | 1.037 / 808 | 0,926 / 0,769 |
| sudoku | 30/30 | 30/30 | 30/30 | 8 / 8 | 0,070 / 0,079 |

`even_odd` resuelve las 30 semillas dentro de 20.000 generaciones; la media de
`total_execution` es 0,211 s y la mediana 0,148 s. Las semillas 11, 17 y 28,
que antes agotaban 120 segundos sin límite de generaciones, ahora resuelven en
0,149, 0,342 y 0,175 s netos en la matriz final. `grandparent` conserva
30/30 y baja de 1.037 a 808 evaluaciones medias. `5queens`, el caso
solo-constraints de la matriz, conserva exactamente las 30 trayectorias.

## Conclusión y límites

La primera corrección elimina una restricción incoherente: proteger generadoras
cuando no existe ninguna constraint con la que reparar negativos. El reinicio
posterior resuelve la causa residual, que era la convergencia de la población en
duplicados. Juntos llevan `even_odd` a 30/30 dentro del límite diagnóstico y
mantienen 30/30 en los otros ocho datasets. La medición cubre estas tareas y
semillas; no convierte una búsqueda estocástica en una garantía universal para
cualquier tarea.

Entorno: revisión base `52d75a4322bb3822685ca8678f5a3bbc82853770`, Python
3.14.6, Clingo 5.8.0, Windows 11 build 26200, Intel Core i7-13700H. Los runners,
snapshots, hashes y resultados crudos se conservan localmente bajo
`.benchmarks/experiments/mutation-no-constraints/`.
