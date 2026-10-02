# Optimización del Python de cláusulas

Experimento del 2 de octubre de 2026. Se implementaron diez cambios en
compilación, análisis, canonicalización e instrumentación sin modificar ningún
`.lp`, task file, límite del language bias ni regla de pruning.

## Cambios implementados

1. Variantes de comparación local cacheadas por compilación, incluidas las
   combinaciones rechazadas por la prueba de seguridad de Clingo.
2. Resúmenes de bindings e invertibilidad de términos calculados de abajo
   arriba; alternativas relativas de pools reutilizadas en esa compilación.
3. Particiones enumeradas por prefijos disjuntos, con una cota necesaria de
   capacidad de tuplas, conservando tamaños tres a seis y minimalidad.
4. Proyecciones inyectivas filtradas por dominios de posición antes de comprobar
   inclusión de tuplas. Las compatibles se consumen sin guardar su historial;
   los dominios uniformes usan `itertools.permutations` directamente.
5. Índice de función, condiciones y anchura de agregados para buscar modes más
   cortos sin recorrer todos los agregados por mode.
6. Consumo lazy de templates de cabeza y deduplicación de elementos antes de
   construir cada forma con sus bounds.
7. Índice de variables pendientes y heaps por posición original para orientar
   constraints lineales. Mantiene prioridad de constraints ya seguros y permite
   outputs de igualdades solo con coeficiente unidad.
8. Valores por posición y relaciones binarias invertidas compartidos dentro de
   cada contexto; dominios y signos numéricos reutilizan esos valores.
9. Key estructural calculada una vez por `ArithmeticSystem` inmutable, con una
   caché independiente después de remapearlo.
10. Clocks internos de grounding, solving y callbacks desactivados cuando no se
    solicitan timings ni métricas Clingo. Las métricas Clingo solas siguen
    midiendo duraciones; el tiempo del consumidor incremental queda fuera.

## Protocolo y control

Control: commit `68fb0c05b00231b17858ae4247434d9a18428853`, en un worktree
detached. Variante: ese commit con los cambios anteriores. Ambos usaron el
mismo ejecutable y dependencias: Python 3.14.6, Clingo 5.8.2, Windows 11
10.0.26200, Intel64 Family 6 Model 186 Stepping 2, `PYTHONHASHSEED=0`.

El harness [profile_clause_python.py](../benchmarks/profile_clause_python.py)
construye tareas sintéticas en memoria. Cada carga tiene un calentamiento y
siete muestras; se informa la mediana de `perf_counter`, sin fingerprinting ni
`tracemalloc` dentro de la región medida. La memoria se mide en una ejecución
adicional. Timings y rutas de métricas estaban desactivados. Las ejecuciones de
control y variante fueron secuenciales, sin tests o benchmarks simultáneos.

Para ejecutar la variante desde la raíz:

```powershell
$env:PYTHONHASHSEED = '0'
uv run python benchmarks/profile_clause_python.py --repeats 7 --memory
```

Para el control, copiar el mismo harness al worktree de ese commit y ejecutarlo
con el mismo Python. Solo cambian dos llamadas por la firma antigua:
`_collect_projection_implications(sources, targets, result)` y
`_partition_properties(relations)`, sin el argumento de posiciones ni su
construcción. Los datos, calentamiento, muestras y comprobación son idénticos;
el control construye sus índices internamente. Los resultados crudos se
conservaron fuera del repositorio, en directorios temporales distintos; no se
editaron ni reemplazaron resultados existentes.

## Cargas sintéticas

Tiempos en milisegundos. Pico en bytes de asignaciones Python observadas por
`tracemalloc`; no incluye toda la memoria nativa de Clingo ni representa RSS.

| Carga | Control ms | Variante ms | Pico control → variante |
| --- | ---: | ---: | ---: |
| Comparación local compartida entre 16 declaraciones de cabeza | 77.561 | 18.157 | 264565 → 257836 |
| Término con 180 funciones anidadas, bindings sin cachear | 104.238 | 5.385 | 47296 → 27592 |
| Facts de 100 agregados con condiciones distintas | 8.176 | 6.294 | 329018 → 363930 |
| Modes de cabeza combinable, 5 constantes y anchura hasta 3 | 57.372 | 57.604 | 398664 → 401668 |
| 20 relaciones diagonales binarias, sin partición válida | 294.050 | 12.139 | 12176 → 46648 |
| Proyección 8 → 5, 30 tuplas y dominios selectivos | 101.257 | 0.085 | 5920 → 34904 |
| Proyección 8 → 5, 30 tuplas y dominios uniformes | 111.551 | 111.950 | 1365448 → 1365624 |
| Orientación de 180 constraints en cadena inversa | 134.050 | 2.303 | 46992 → 94721 |
| 10000 lecturas de key de un sistema de 100 constraints | 71.290 | 0.357 | 2560 → 0 |
| Propiedades de 8 relaciones producto de 15 × 15 | 5.535 | 4.055 | 116888 → 181688 |
| Enumeración completa de la tarea pequeña del harness | 33.832 | 33.071 | 32676 → 32671 |
| Enumeración incremental, batch 64 y seed 31 | 35.915 | 34.258 | 36386 → 36349 |

Los doce fingerprints de resultados coincidieron. Son una comprobación de
estas cargas, no una prueba de equivalencia semántica general. La carga de
propiedades excluye la derivación de extensiones por Clingo. La de bindings
vacía su caché antes de cada muestra para medir el recorrido de términos.
Las lecturas de key usan el mismo sistema ya calentado: el pico cero mide nuevas
asignaciones durante lecturas, no la memoria del sistema ni su key retenida.

## Pipeline completo y cierre

`profile_clauses.py` produjo los mismos entries ordenados, textos, cabezas,
dependencias y costes de cuerpo que el control: `grandparent` 326,
`constant_colour` 2, `coloring` 59 y `subset_sum_unbalanced_ops` 49 cláusulas.

Se ejecutó también `profile_baseline.py` en ambos árboles y algoritmos:
datasets `grandparent constant_colour coloring`, tres runs, `--seed-base 31`
(seeds 32, 33 y 34), `--timeout-seconds 30`, `--set iterations_genetic=50`,
instrumentación `full` y el mismo Python. Los demás `Arguments` fueron los del
catálogo; incremental añadió solo `--set algorithm=incremental`. Cada variante
y algoritmo tuvo su propio `--out-dir` fuera del repositorio.

Medias de tres runs en milisegundos, control → variante. Total procede de
`total_execution`; los tipos se suman desde las fases del productor existente,
con grounding, solving, Python y closure separados.

| Algoritmo / dataset | Total | Grounding | Solving | Python | Closure |
| --- | ---: | ---: | ---: | ---: | ---: |
| steady_state / grandparent | 102.676 → 93.470 | 44.332 → 39.950 | 9.450 → 9.088 | 44.417 → 40.342 | 4.477 → 4.090 |
| steady_state / constant_colour | 28.943 → 28.775 | 20.632 → 20.507 | 0.855 → 0.859 | 7.264 → 7.211 | 0.192 → 0.197 |
| steady_state / coloring | 123.596 → 111.357 | 60.221 → 54.369 | 14.493 → 12.763 | 46.526 → 41.991 | 2.356 → 2.234 |
| incremental / grandparent | 77.761 → 73.076 | 41.610 → 38.357 | 5.332 → 5.195 | 29.008 → 27.759 | 1.810 → 1.765 |
| incremental / constant_colour | 28.561 → 26.652 | 20.518 → 18.886 | 0.376 → 0.398 | 7.414 → 7.170 | 0.253 → 0.198 |
| incremental / coloring | 62.248 → 60.893 | 31.706 → 32.368 | 5.347 → 4.921 | 24.157 → 22.663 | 1.037 → 0.942 |

Los 18 pares de runs conservaron el progreso GA salvo tiempos, tamaños de
`ClauseSpace`, llamadas de grounding/solving y resultados de éxito. Steady-state
encontró hipótesis perfectas en 1/3 runs de `grandparent`, 3/3 de
`constant_colour` y 0/3 de `coloring`; incremental obtuvo 0/3, 3/3 y 0/3.
Esto comprueba que el cambio no alteró esas trayectorias, no compara la calidad
estadística de los algoritmos.

## Límites y verificación

Las mejoras grandes se concentran en trabajo Python repetido o combinatorio.
La carga selectiva de proyección rechaza casi todas las mappings; la uniforme
no muestra ganancia. Una revisión con muestras intercaladas midió overhead fijo
en el caso mínimo 3 → 2 con una tupla: 5.683 → 9.453 ms por 1000 llamadas.
No se afirma una mejora universal de proyecciones.

Los índices de particiones, orientación y relaciones consumen más memoria.
El consumo lazy de cabezas evita materializar templates intermedios, pero esta
carga pequeña, que termina reteniendo todos los modes, no acredita una reducción
de tiempo ni de pico. El índice de agregados tiene un coste de construcción y
puede no compensar en tareas pequeñas. Las nuevas cachés de compilación acaban
con esa llamada; la key vive con su sistema.

Tres runs pequeños y mediciones secuenciales no permiten atribuir las diferencias
globales a estas optimizaciones: también varían grounding y closure, cuyo
algoritmo no cambió. Las diferencias de unos pocos milisegundos pueden ser ruido.
El schema 13, el productor y los charts siguen intactos. No se cambiaron tasas de
éxito, cobertura por regla ni cierre de hipótesis para obtener las ganancias.

Los tests contrastan facts y modes con referencias, prueban presencia y ausencia
de cláusulas, conservan contextos aislados y relaciones vacías, y comparan la
orientación con su prioridad original usando RNG fijo. También cubren las cuatro
combinaciones de timings/métricas Clingo en enumeración completa e incremental,
incluido no leer clocks al desactivar ambas.

Verificación final: `uv run pytest -q` pasó los 1733 tests; `uv run ruff check`
en cláusulas, timing, tests afectados y harness, y `uv run ty check` también
pasaron. La revisión independiente contrastó mundos cerrados aleatorios,
términos anidados y variantes de heads/facts contra el control.

Se recorrieron las cadenas de generación y canonicalización (compilación,
análisis, decode/render y tests), algoritmos (enumeración completa e incremental
y búsqueda con ambos), medición (timing, payload del productor y sus tests) y
documentación. No hubo cambios visibles del lenguaje ni cambios de estrategia;
la evaluación sigue aplicándose al programa candidato completo.
