# Máscaras en la ruta lineal y poda de filas proporcionales

Estado: implementado y medido el 2026-10-03. Continúa los
[contextos compactos y cadenas de igualdad](arithmetic-context-reductions.md).
El control congelado incluye aquella pasada completa; no compara contra `HEAD`
ni acumula sus porcentajes con los experimentos anteriores.

La [pasada posterior de componentes y expresiones](arithmetic-components-reductions.md)
añade reutilización de particiones y términos, restringe los helpers de
comparaciones a sus consumidores y amplía la poda a aliases de dos columnas
sin cancelación del anclaje. El protocolo y los resultados de esta página
describen el control anterior a esa ampliación.

## Menos representaciones en Python

Las máscaras external, safe y numeric llegan ahora directamente a
`_canonical_systems`. La ruta lineal conserva máscaras para componentes,
auxiliares, variables seguras y variables pendientes durante la orientación.
Sólo las rutas de expresiones o fallback materializan sus conjuntos anteriores.

`LinearConstraint` deriva y conserva una máscara de **coeficientes no nulos**.
No usa las variables originales del literal: bindings repetidos pueden cancelar
coeficientes. Su propiedad `variables` conserva el contenido anterior como vista
de conveniencia, pero ya no retiene otro conjunto por fila. Máscara, igualdad y
hash son independientes; remapping crea una fila con su propia máscara.

La eliminación mantiene la prioridad por variable e índice de fila y sólo
elimina auxiliares con coeficiente unitario antes del gcd. La orientación mantiene
la prioridad de filas seguras, el orden de assignments y los guards existentes.
No se añade otra caché. Las cachés de sistemas, normalización y AST conservan
sus límites y scopes, con claves de auxiliares enteras en lugar de conjuntos.
Los dos consumidores de profiling actualizan esa interfaz interna directamente.

## Otra contradicción que decide Clingo

La compilación reutiliza los mismos analizadores de linealidad, coeficientes y
filas primitivas que la canonicalización. Empareja una vez una igualdad y una
comparación estricta o disequality cuyas filas homogéneas sean proporcionales,
por ejemplo `2*X=Y` junto con `4*X<2*Y` o `-4*X!=-2*Y`.

Los facts `numeric_linear_conflict` y `nonlinear_builtin_mode` se emiten sólo
cuando existe un par no simple; los pares de comparaciones simples continúan
usando la poda anterior. ASP aplica la nueva poda únicamente cuando:

1. Los bindings coinciden completos y en el mismo orden; no intercambia outputs.
2. Todas las posiciones tienen coeficientes no nulos y bindings distintos.
3. Un átomo positivo plano del cuerpo ancla alguna variable de esa fila.
4. Todos los builtins seleccionados son elegibles para normalización homogénea
   numérica lineal. Declarar otro builtin sin seleccionarlo no bloquea la poda.

Así, la fila estricta o distinta se reduce a cero mediante la igualdad. El anclaje
pertenece a un coeficiente real y hace que Python normalice ese componente;
el guard de linealidad evita su fallback de expresiones. Python ya devolvía
`None` antes de orientar. Coeficientes y proporcionalidad se calculan una vez
con enteros de Python; Clingo sólo compara selección y bindings, sin productos
de coeficientes que puedan desbordar.

Bindings repetidos, coeficientes nulos, términos no homogéneos, tipos no numéricos
y sistemas con otro builtin seleccionado conservan el camino anterior. No se
traslada Gauss general, no se decide por cobertura de ejemplos y no se cambia
la evaluación no monótona de hipótesis completas.

## Protocolo

Windows 11, Python 3.14.6, Clingo 5.8.2 e Intel Core i7-13700H. Task files del
catálogo intactos. El directorio local ignorado
`.benchmarks/experiments/arithmetic-shared-20261003/` conserva control Python y
ASP completos, scripts, streams inmutables y reports generados. No se reemplaza
ningún resultado anterior ni se editan JSON o CSV a mano.

`work_counts.py` usa procesos nuevos y el mismo stream completo, con literales
preparados fuera de cProfile. Cuenta llamadas durante canonicalización y
materialización; fingerprint queda fuera. Su tiempo no se usa como benchmark.

`timed_series.py` ejecuta cinco parejas por versión, tarea y ruta, alternando
control/producción y producción/control, con procesos nuevos y un thread. No
coincide con tests ni otros perfiles del agente. El replay vacía cachés e incluye
canonicalización y materialización, excluyendo decode, Clingo y preparación.
La generación completa separa grounding, decode, canonicalización, materialización
y residual de solving; incluye cargar AST en Control, excluye parsing/análisis/facts
comunes, fingerprint y serialización. No mide búsqueda evolutiva ni closure.

## Conteos del stream idéntico

Cada celda expresa control → producción. Todos los fingerprints completos
incluyen texto, proveedores, dependencias y coste, en orden determinista.

| Medida | `8queens` | `subset_sum_double_and_prod` |
| --- | --- | --- |
| Modelos | 6697 → 6697 | 6858 → 6858 |
| Cláusulas | 4797 → 4797 | 5547 → 5547 |
| Cálculos de sistemas | 4959 → 4959 | 674 → 674 |
| Conjuntos de contexto materializados por `_variables` | 14877 → 0 | 2022 → 1698 |
| Consultas al conjunto de variables de filas lineales | 24386 → 0 | 368 → 0 |
| Consultas a máscaras de filas lineales | 0 → 24386 | 0 → 368 |
| Normalizaciones | 4774 → 4774 | 75 → 75 |
| Matrices RREF | 4742 → 4742 | 67 → 67 |
| Sistemas de expresiones | 0 → 0 | 566 → 566 |

Se retiran formas intermedias, no cálculos algebraicos necesarios. La tarea mixta
sigue materializando tres conjuntos por cada uno de sus 566 sistemas de
expresiones; por eso su reducción es menor. Las entradas en la caché de sistemas
siguen siendo 4959 y 674 respectivamente.

## Tiempo: distinguir la fase del total

Medianas de cinco procesos por versión, en segundos. El total del replay es
**canonicalización más materialización**, no la ejecución completa de Gentians.

| Replay | Control | Producción | Parejas con menor wall-clock |
| --- | --- | --- | --- |
| `8queens`, wall-clock | 0.661 | 0.559 | 4 de 5 |
| `8queens`, CPU | 0.609 | 0.531 | — |
| Tarea mixta, wall-clock | 0.403 | 0.404 | 2 de 5 |
| Tarea mixta, CPU | 0.375 | 0.375 | — |

8queens mejora un 15.4% en esta fase local; una pareja se invierte. La tarea
mixta no muestra una mejora estable. La serie de generación completa registra:

| Tarea | Grounding | Decode | Canonicalización | Solve residual | Materialización | Total | CPU |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `8queens` | 0.061 → 0.056 | 0.317 → 0.169 | 1.326 → 0.680 | 1.054 → 0.606 | 0.027 → 0.016 | 2.795 → 1.531 | 2.266 → 1.500 |
| Tarea mixta | 0.052 → 0.052 | 0.155 → 0.156 | 0.460 → 0.450 | 0.196 → 0.195 | 0.018 → 0.018 | 0.887 → 0.874 | 0.844 → 0.859 |

Las medianas de fases no tienen por qué sumar la del total. En 8queens el control
varía entre 1.408 y 5.128 segundos, la producción entre 1.334 y 2.103. Decode y
solving también bajan aunque no cambian su implementación, modelos ni estructura
grounded del solver. No se atribuye todo ese descenso al cambio Python ni se
publica ese porcentaje como aceleración general. En la tarea mixta se invierten
tres parejas y la CPU mediana aumenta ligeramente.

Esta serie usa la primera forma ASP; la forma final elimina una vista unary.
Ninguna de estas dos tareas declara los pares nuevos: la poda no se activa y
las estadísticas de grounding y estructura del solver coinciden con el control.
Su reducción medida es la ruta Python; las sondas siguientes miden la poda final.

## Poda ASP final

`proportional.lp` enumera 19 → 16 modelos, con las mismas ocho cláusulas.
La versión final proyecta slots antes de comparar bindings y elimina una vista
unary intermedia. Una variante con conditional literal era semánticamente
equivalente, pero se retiró por aumentar el grounding:

| Sonda mínima | Átomos | Reglas | Variables del solver |
| --- | --- | --- | --- |
| Control sin poda | 667 | 1364 | 780 |
| Primera versión con helpers | 713 | 1462 | 853 |
| Variante con conditional literal, descartada | 809 | 1595 | 863 |
| Versión final con proyecciones | 709 | 1458 | 853 |

Menos helpers escritos no implica menos estructura interna en Clingo.
La escala de esta sonda no permite afirmar una aceleración.

`proportional-expanded.lp` permite tres variables y más recalls. Compara el
mismo **Python actual y los mismos facts** con ASP congelado frente al ASP final;
los dos reports indican `control=false`. Aísla la poda de la reducción Python.
Conserva exactamente 390 cláusulas y su metadata, con fingerprint
`17ed69ebf5922ed80fbcdf64321673e2e230538752256c913c1adec840ddd694`.

| Sonda ampliada | Sin la nueva poda | Con la poda final |
| --- | --- | --- |
| Modelos | 2372 | 1862 |
| Átomos grounded | 1748 | 1809 |
| Reglas grounded | 5948 | 6159 |
| Variables del solver | 3462 | 3646 |
| Constraints generales + binarias + ternarias | 16183 | 16913 |
| Grounding, mediana de cinco parejas | 0.03697 s | 0.03714 s |
| Decode | 0.04062 s | 0.03304 s |
| Canonicalización | 0.13803 s | 0.12727 s |
| Solve residual | 0.05275 s | 0.04535 s |
| Materialización | 0.00115 s | 0.00118 s |
| Total | 0.27173 s | 0.24750 s |
| CPU | 0.250 s | 0.250 s |

Las cinco parejas reducen wall-clock: 8.9% de mediana en **esta tarea sintética**,
con 510 modelos menos y más estructura grounded. La CPU mediana coincide;
no se extrapola ese porcentaje al catálogo ni a la búsqueda evolutiva.

## Reproducción y verificación

Ejemplos desde la raíz, creando reports nuevos:

```powershell
$experimentRoot = '.benchmarks/experiments/arithmetic-shared-20261003'
uv run python "$experimentRoot/replay.py" --dataset 8queens --input "$experimentRoot/queens-replay.pkl" --control --repeats 1 --out "$experimentRoot/replay-control-repeat.json"
uv run python "$experimentRoot/replay.py" --dataset 8queens --input "$experimentRoot/queens-replay.pkl" --repeats 1 --out "$experimentRoot/replay-production-repeat.json"
uv run python "$experimentRoot/probe.py" --dataset grandparent --source "$experimentRoot/proportional-expanded.lp" --out "$experimentRoot/expanded-without-pruning-repeat.json"
uv run python "$experimentRoot/probe.py" --dataset grandparent --source "$experimentRoot/proportional-expanded.lp" --current-lp --out "$experimentRoot/expanded-projected-repeat.json"
uv run python "$experimentRoot/semantic.py" --control --out "$experimentRoot/semantic-control-repeat.json"
uv run python "$experimentRoot/semantic.py" --out "$experimentRoot/semantic-production-repeat.json"
```

En las sondas, `grandparent` aporta configuración de ejecución; la tarea es el
archivo indicado por `--source`. Para counts se usa `work_counts.py` con los
mismos argumentos dataset/input/control/out del replay, sin `--repeats`.

`semantic-{control,production}-final.json` conserva outputs completos y uniones
incrementales exactos en ocho tareas, con seed 31 y batch size 113. Los fingerprints
por lote también coinciden salvo en la sonda ampliada: pasa de 25 a 20 lotes,
con la misma unión de 390 cláusulas. La tarea mixta mantiene la diferencia previa
de 5547 globales frente a 5663 representantes por lote. No se exige una trayectoria
evolutiva idéntica al anticipar descartes que consumían presupuesto.

Una revisión independiente comparó 1200 sistemas lineales y diez tareas pequeñas
contra el control. Las regresiones cubren IDs mayores de 63, cancelaciones,
bindings repetidos o parcialmente distintos, escala negativa, coeficientes nulos,
guards de homogeneidad y otros builtins seleccionados.

Verificación: 1240 tests en la pasada amplia; diez casos añadidos después se
verificaron en una pasada focalizada de 273 tests. Los 109 tests de metaprograma
pasaron con el ASP final. Ruff y `uv run ty check` correctos.
Aplican compilación de facts, schema ASP, metaprograma, representación lineal,
canonicalización, generación completa/incremental, consumidores de profiling y
documentación. Sintaxis, evaluación de hipótesis, cierre y estrategias conservan
su contrato. No cambian fases de `timing.py`, dashboard, schema de métricas, charts,
preview ni diagramas de flujo.
