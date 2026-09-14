# Comparación de 5-queens con ILASP

## Entrada

La traducción está en `benchmarks/ilasp/5queens.las`. Conserva el background,
los 10 ejemplos positivos y los 35 negativos de
`benchmarks/gentians/5queens.txt`. No incluye las reglas objetivo comentadas en
el archivo original ni ninguna cláusula generada por Gentians.

El language bias se traduce a estas declaraciones ILASP:

```prolog
#maxv(5).
#modeb(2,q(var(numeric),var(numeric))).
#modeb(1,var(numeric)<var(numeric)).
#modeb(2,var(numeric)+var(numeric)=var(numeric)).
```

Gentians reúne `add` y `sub` en una única familia aditiva y suma sus recalls.
Por eso la declaración aditiva de ILASP usa recall 2; las permutaciones de
`A+B=C` expresan también las restas necesarias. El límite de cinco literales de
cuerpo se pasa a ILASP como `-ml=5`.

ILASP no ofrece un equivalente directo de `#maxpl(6)`. En 5-queens la
hipótesis objetivo tiene tres constraints, por lo que ese límite no debería ser
activo. Tampoco hay `#modeh`: el espacio contiene únicamente constraints.

## Protocolo

Se ejecutó ILASP 4.4.1 desde WSL Kali Linux, secuencialmente para evitar
competencia entre variantes:

```bash
bash benchmarks/run_ilasp_5queens.sh
```

El runner aplica a cada variante el comando equivalente a:

```bash
timeout --signal=INT --kill-after=5s 180s \
  /mnt/c/tmp/ILASP --version=<2|2i|3|4> -ml=5 \
  benchmarks/ilasp/5queens.las
```

El binario necesitó las bibliotecas de Python 3.10 extraídas localmente en
`/tmp/ilasp-python310/root/usr`. El runner permite cambiar binario, runtime,
timeout, entrada y salida mediante variables de entorno.

## Resultados con mode bias

| Versión ILASP | Resultado | Presupuesto | Tiempo de pared |
|---|---:|---:|---:|
| 2 | timeout | 180 s | 185.013126 s |
| 2i | timeout | 180 s | 185.015260 s |
| 3 | timeout | 180 s | 185.026578 s |
| 4 | timeout | 180 s | 185.010351 s |

Los cinco segundos adicionales corresponden al periodo de gracia de
`timeout --kill-after=5s`. Los cuatro procesos terminaron con estado 137 y sus
archivos de salida quedaron vacíos: ninguna variante imprimió una hipótesis
antes del corte.

Como referencia, los artefactos locales `sdk-defaults` de Gentians contienen
estas medias de `total_execution` para el mismo task file:

| Algoritmo Gentians | Media | Soluciones | Runs | Cláusulas disponibles |
|---|---:|---:|---:|---:|
| `steady_state` | 5.640195 s | 10 | 10 | 4797 |
| `incremental` | 9.821015 s | 8 | 10 | 1853 iniciales |

Con el corte de 180 segundos, ILASP necesitó más de 31.9 veces la media de
`steady_state` y más de 18.3 veces la media de `incremental` sin devolver una
solución. Son cotas inferiores, no tiempos de resolución de ILASP.

La comparación conserva ejemplos y background y aproxima el bias de forma
semántica, pero los espacios de hipótesis no son idénticos: Gentians e ILASP
aplican generadores, canonicalización y pruning distintos. Además, las cifras
de Gentians proceden de artefactos locales anteriores y las de ILASP de WSL;
sirven como comparación operativa, no como un benchmark controlado de los
motores en el mismo proceso y entorno.

## Resultados con el ClauseSpace explícito

El segundo experimento reemplaza por completo los `#modeb` por las 4797
cláusulas generadas por Gentians. Cada constraint se entrega a ILASP como:

```text
body_literals ~ constraint
```

El archivo se genera una vez, antes de medir ILASP:

```powershell
uv run python benchmarks/export_ilasp_5queens.py
```

El resultado contiene los mismos 10 positivos, 35 negativos, cero modes y
esta distribución de reglas explícitas:

| Longitud | Cláusulas |
|---:|---:|
| 1 | 2 |
| 2 | 7 |
| 3 | 97 |
| 4 | 881 |
| 5 | 3810 |

Las ejecuciones usan el mismo límite de 180 segundos y el mismo runner, con
`ILASP_TASK` apuntando al archivo explícito:

```bash
ILASP_TASK=.benchmarks/experiments/ilasp-5queens-explicit/5queens-explicit.las \
ILASP_OUTPUT=.benchmarks/experiments/ilasp-5queens-explicit \
bash benchmarks/run_ilasp_5queens.sh
```

| Versión ILASP | Resultado | Tiempo de pared | Total informado por ILASP |
|---|---:|---:|---:|
| 2 | solución | 5.424149 s | 5.352 s |
| 2i | solución | 12.042102 s | 11.977 s |
| 3 | solución | 129.340602 s | 129.090 s |
| 4 | solución | 13.436746 s | 13.364 s |

Las cuatro variantes devolvieron dos constraints de coste total 8. Uno contiene
la ecuación de una familia de diagonales. El otro prohíbe pares transpuestos de
la forma `q(X,Y), q(Y,X)` bajo un orden entre `X` e `Y`. La hipótesis satisface
los 45 ejemplos, pero no recupera literalmente las dos reglas diagonales del
objetivo comentado: aprovecha una regularidad más específica del conjunto de
entrenamiento. Las diferencias entre versiones son renombrados de variables u
orientaciones algebraicamente equivalentes de esas dos cláusulas explícitas.

Frente a la media local de Gentians `steady_state` (5.640195 s), ILASP 2 quedó
en 0.96 veces ese tiempo, ILASP 2i en 2.14, ILASP 3 en 22.93 e ILASP 4 en 2.38.
Frente a `incremental` (9.821015 s), los factores son 0.55, 1.23, 13.17 y 1.37,
respectivamente.

Esta segunda medición concede a ILASP el `ClauseSpace` ya generado. El tiempo
de exportación y generación de cláusulas queda fuera de su cronómetro, mientras
que `total_execution` de Gentians sí incluye la generación. El resultado mide
principalmente la búsqueda de hipótesis sobre el mismo conjunto materializado,
no el pipeline completo de ambos sistemas.
