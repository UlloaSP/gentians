# Experimento: pool de cláusulas congelado por épocas

Configuration location: this matrix now lives in `benchmarks/experiments.toml`
under `epoch-pool/` IDs. Worker arguments and output folders are unchanged.
The ID change makes old manifests stale; historical measurements below are not
rewritten. Commands below select named entries, not every matrix in the file.

Historical experiment: references below to `#bias`, metarules, or atomic bundles
describe the measured implementation, not the current language. That support has
been removed; see [the current contract](language-bias.md#removed-meta-programming-directives).

## Hipótesis

Un `clingo.Control` puede reutilizarse de forma segura durante una época si el
background, todos los contextos, el programa de cobertura y el pool completo de
cláusulas se groundean juntos. Cada cláusula del pool tiene un `#external` y
cada evaluación activa exactamente el subconjunto del programa candidato.

El pool no cambia dentro de la época. Una cláusula ausente no puede inyectarse
después: queda pendiente hasta reconstruir el `Control`.

## Implementación

El algoritmo `epoch_pool_genetic_search` conserva índices globales de `Genome`.
En cada reconstrucción:

1. Conserva las mejores `k` hipótesis completas, incluyendo el mejor programa
   global.
2. Forma el núcleo con la unión de sus cláusulas.
3. Completa el pool con hipótesis válidas generadas mediante un RNG separado.
4. Groundea conjuntamente background, contextos, cobertura y pool.
5. Restringe generación, crossover y mutación al pool hasta la próxima época.

No se asigna fitness a cláusulas aisladas. El tamaño configurado es un objetivo:
si el núcleo retenido lo supera, el algoritmo conserva el núcleo completo para
no romper bundles ni cierre de dependencias.

Con `k` igual al tamaño de población se conserva toda la población y se aísla
mejor el efecto del pool. Con `k` menor se descartan y regeneran los individuos
restantes; esa variante cambia también la dinámica evolutiva.

## Coste esperado

Sean `T` evaluaciones únicas, `R` generaciones, `E` generaciones por época,
`G0` el grounding del
background y los contextos, `GH` el grounding de un candidato, `GP` el grounding
del pool, y `Sfresh` y `Spool` los costes de solve correspondientes:

```text
actual: T × (G0 + GH + Sfresh)
pool:   ceil(R / E) × (G0 + GP) + T × Spool
```

El pool solo mejora tiempo si:

```text
(ceil(R / E) × (G0 + GP) / T) + Spool < G0 + GH + Sfresh
```

Reduce llamadas de grounding, pero puede aumentar el tamaño del solver y el
coste de cada solve. También restringe la búsqueda de la época de un
`ClauseSpace` de tamaño `M` a un pool efectivo `P`, aproximadamente de
`sum(C(M,i))` a `sum(C(P,i))` para tamaños de programa permitidos `i`.

## Matriz

`benchmarks/experiments.toml` fija `5queens` y `grandparent`, diez
runs y timeout de 100 segundos. No limita las generaciones: cada run termina
cuando encuentra una hipótesis perfecta o alcanza el timeout. Compara:

- Control con un `Control` nuevo por programa candidato.
- Tamaño objetivo `P`: 64, 128 y 256, con `E=50` y `k=10`.
- Cadencia `E`: 20, 50 y 100, con `P=128` y `k=10`.
- Retención `k=3` frente a `k=10`, con `P=128` y `E=50`.

Comando:

```powershell
uv run python benchmarks/run_experiments.py epoch-pool/control epoch-pool/pool_p128_e50_k10
```

Los artefactos se escriben en `.benchmarks/epoch-pool/<experimento>/` usando el
formato normal del runner. `program_size` en la fila de grounding registra el
tamaño efectivo del pool.

## Resultados

La matriz encontró una hipótesis perfecta en 137 de 140 ejecuciones. Hubo tres
timeouts. `PAR-1` es la media wall-clock con cada timeout valorado en 100
segundos. La mediana wall-clock, `total_execution`, generaciones, evaluaciones y
ground calls se calculan sobre runs resueltos. Ground calls incluye la llamada
de generación del `ClauseSpace` registrada por el dashboard.

Entorno: Python 3.14.6, Clingo 5.8.0, Intel Core i7-13700H y revisión
`ff57d65e60cce685da8c8a79d47cc162128d5c05`.

### 5queens

| Configuración | Éxitos | Timeouts | PAR-1 | Mediana wall | `total_execution` | Generaciones | Evaluaciones | Ground calls |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Control | 10/10 | 0 | 9,436 s | 7,094 s | 6,762 s | 1412 | 1030 | 1030,6 |
| `P=64, E=50, k=10` | 10/10 | 0 | 14,556 s | 15,396 s | 11,492 s | 3801 | 2230 | 77,5 |
| `P=128, E=50, k=10` | 10/10 | 0 | 16,576 s | 17,349 s | 13,619 s | 3104 | 1948 | 63,6 |
| `P=256, E=50, k=10` | 10/10 | 0 | 21,098 s | 17,750 s | 18,159 s | 2914 | 1809 | 59,8 |
| `P=128, E=20, k=10` | 10/10 | 0 | 24,988 s | 17,636 s | 21,269 s | 3618 | 2121 | 182,4 |
| `P=128, E=100, k=10` | 10/10 | 0 | 21,435 s | 20,626 s | 17,067 s | 5345 | 3311 | 55,1 |
| `P=128, E=50, k=3` | 10/10 | 0 | 14,880 s | 13,910 s | 12,249 s | 2125 | 1860 | 43,8 |

El control ganó. El pool más rápido, `P=64, E=50, k=10`, aumentó PAR-1 un
54,3 %. Redujo ground calls un 92,5 %, pero necesitó 2,69 veces más generaciones
y 2,17 veces más evaluaciones. `P=128, E=100, k=10` hizo aún menos groundings,
pero necesitó 5345 generaciones de media. El ahorro local no compensó la peor
trayectoria de búsqueda.

### grandparent

| Configuración | Éxitos | Timeouts | PAR-1 | Mediana wall | `total_execution` | Generaciones | Evaluaciones | Ground calls |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Control | 10/10 | 0 | 3,354 s | 1,796 s | 1,624 s | 3967 | 1222 | 1223,0 |
| `P=64, E=50, k=10` | 10/10 | 0 | 4,048 s | 2,010 s | 2,784 s | 2407 | 829 | 49,4 |
| `P=128, E=50, k=10` | 9/10 | 1 | 14,812 s | 1,822 s | 4,205 s | 1762 | 646 | 36,7 |
| `P=256, E=50, k=10` | 10/10 | 0 | 19,818 s | 9,886 s | 17,923 s | 3338 | 1201 | 68,1 |
| `P=128, E=20, k=10` | 10/10 | 0 | 20,330 s | 16,698 s | 17,920 s | 3464 | 1270 | 174,7 |
| `P=128, E=100, k=10` | 10/10 | 0 | 9,019 s | 2,962 s | 7,095 s | 4696 | 1307 | 48,5 |
| `P=128, E=50, k=3` | 8/10 | 2 | 27,802 s | 3,275 s | 7,872 s | 2885 | 1343 | 59,1 |

`P=64, E=50, k=10` redujo generaciones y evaluaciones, pero aun así aumentó
PAR-1 un 20,7 %: mantener y reconstruir el pool costó más que los groundings
evitados. `P=128, E=50, k=10` parece competitivo si solo se mira la mediana de
runs resueltos, pero tuvo un timeout. PAR-1 expone el coste real. Retener tres
élites produjo dos timeouts.

### Conclusión

Con tiempo hasta solución, el control gana en ambos datasets. El pool reduce el
grounding, pero restringe la búsqueda y cambia cuántas generaciones y
evaluaciones hacen falta. En `5queens` esa pérdida supera el ahorro. En
`grandparent`, donde el grounding individual es barato, también pesa el coste de
mantener el solver pooled. Estas configuraciones no justifican activar el pool
por defecto.
