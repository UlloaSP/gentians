# Contextos aritméticos compactos y cadenas de igualdad

Estado: implementado y verificado el 2026-10-03. Esta pasada continúa la
[reutilización aritmética](arithmetic-reuse-reductions.md). Su control congelado
incluye todos los cambios de aquella pasada; los resultados siguientes miden
sólo esta diferencia y no acumulan sus porcentajes con mediciones anteriores.
El [seguimiento de la ruta lineal](arithmetic-linear-reductions.md) evita también
los conjuntos de los misses lineales y añade poda de filas proporcionales;
su control es el estado final de esta pasada.

## Cambios implementados

- `ReifiedLiteral` deriva una máscara de variables en lugar de un `frozenset`.
  Conserva la clave, el orden de bindings y la igualdad que incluye sección y
  slot. Los enteros de Python permiten IDs superiores a 63 y variables repetidas.
- `canonical_arithmetic_clause` acumula external, safe y numeric con máscaras.
  Las tres máscaras forman parte de la clave de la caché existente. Sólo un miss
  materializa los tres conjuntos que consume la normalización general; un hit
  no construye ninguno. Las comprobaciones de inclusión de variables de un
  literal también reutilizan su máscara. No se añade otra caché ni otro dominio.
- `ArithmeticSystem.instantiate` materializa directamente una relación única
  cuando no es un `ExpressionConstraint`. Evita preparar listas, conjuntos de
  deduplicación y hashes nativos en ese caso. Las expresiones conservan el camino
  que emite y deduplica sus guards de denominadores.
- `_finish_normalization` aplica sus dos filtros durante la ordenación final.
  Elimina dos conjuntos intermedios de restricciones por normalización terminada,
  conservando el descarte de contradicciones, la deduplicación y el orden.
- `comparisons.lp` rechaza una comparación estricta o disequality entre variables
  conectadas por igualdades simples seleccionadas. La vista simétrica expresa
  igualdad de valores; no intercambia bindings de modes con direcciones distintas.

La caché de sistemas mantiene su límite de 8192 entradas y su scope por
canonicalizer: uno para generación completa y otro por lote incremental.
Parsing, AST, canonicalización general y orquestación siguen en Python.

## Qué se traslada a Clingo

La poda anterior detectaba un par explícito como `X=Y, X<Y`. Ahora también
detecta `X=Y, Y=Z, X<Z`, la orientación estricta inversa y `X!=Z`. Usa una
closure de las igualdades seleccionadas sobre IDs de variables, con estos guards:

1. Las igualdades son positivas, simples y nominalmente numéricas.
2. Todos los builtins seleccionados del cuerpo son comparaciones simples
   numéricas. Declarar un builtin complejo sin seleccionarlo no bloquea la poda.
3. Un átomo positivo plano del cuerpo hace externa y segura alguna variable
   del componente de igualdad, aunque no sea un extremo de la comparación.

Las filas de igualdad tienen coeficientes unitarios. Con ese anclaje externo,
la eliminación de auxiliares y RREF reducen a cero la comparación estricta o
distinta entre variables conectadas. Python ya rechazaba ese sistema antes de
orientarlo; la poda anticipa el rechazo a la decodificación.

Los componentes sin externos y los sistemas con otro builtin seleccionado
conservan sus fallbacks estructurales o de expresiones. No se trasladan Gauss,
productos de coeficientes ni equivalencias basadas en ejemplos a ASP. La closure
trabaja con IDs y evita el problema de rangos enteros distintos de Python y
Clingo descrito en el experimento anterior.

## Protocolo

Entorno: Windows 11, Python 3.14.6, Clingo 5.8.2 e Intel Core i7-13700H.
Los task files de `benchmarks/gentians/` permanecen intactos. El directorio local
ignorado `.benchmarks/experiments/arithmetic-context-20261003/` conserva el
control Python y ASP completos, scripts, streams inmutables y reports generados.
Los controles proceden del estado inmediatamente anterior a estos cambios,
no de `HEAD`.

`counts.py` reproduce un stream completo idéntico en un proceso nuevo por
versión. Prepara los literales fuera de cProfile y mide llamadas durante
canonicalización y materialización final. No atribuye el tiempo de cProfile al
benchmark. Los counts de conjuntos se derivan de ejecuciones medidas y
constructores auditados; una comprobación adicional cuenta las normalizaciones
que terminaron sin devolver `None`. Los reports auditados son
`counts-*-{control,production}-audited.json`.

El tamaño de valores retenidos suma `sys.getsizeof` una vez por identidad de
cada valor external, safe o numeric conservado en las claves. Excluye diccionario,
tuplas de clave, claves de builtins, literales, AST y memoria nativa. No mide RSS
ni el pico de memoria del proceso; puede contar enteros que Python ya comparte.

`probe.py` usa un proceso y Control nuevos, cachés frías y un thread. Separa
grounding, decode, canonicalización, materialización y residual de solving.
El total incluye cargar AST en Control, grounding y solving con callbacks;
excluye parsing, análisis y facts comunes, fingerprint y serialización.
No mide evaluación evolutiva ni cierre de dependencias.

Ejemplos desde la raíz, creando reports nuevos:

```powershell
$experimentRoot = '.benchmarks/experiments/arithmetic-context-20261003'
uv run python "$experimentRoot/counts.py" --dataset 8queens --input "$experimentRoot/queens-replay.pkl" --control --out "$experimentRoot/counts-control-repeat.json"
uv run python "$experimentRoot/counts.py" --dataset 8queens --input "$experimentRoot/queens-replay.pkl" --out "$experimentRoot/counts-production-repeat.json"
uv run python "$experimentRoot/probe.py" --dataset grandparent --source "$experimentRoot/equality-chain.lp" --control --out "$experimentRoot/chain-control-repeat.json"
uv run python "$experimentRoot/probe.py" --dataset grandparent --source "$experimentRoot/equality-chain.lp" --current-lp --out "$experimentRoot/chain-production-repeat.json"
uv run python "$experimentRoot/semantic.py" --control --out "$experimentRoot/semantic-control-repeat.json"
uv run python "$experimentRoot/semantic.py" --out "$experimentRoot/semantic-production-repeat.json"
```

`grandparent` aporta la configuración de ejecución de las sondas locales; la
tarea medida en esos dos comandos es `equality-chain.lp`, no la del catálogo.
Para el replay mixto se usan `--dataset subset_sum_double_and_prod` e
`--input "$experimentRoot/prod-replay.pkl"`.

## Menos formas intermedias

Cada celda expresa control → producción. Los fingerprints incluyen texto,
proveedores, dependencias y coste, con el mismo orden determinista.

| Medida | `8queens` | `subset_sum_double_and_prod` |
| --- | --- | --- |
| Modelos del stream | 6697 → 6697 | 6858 → 6858 |
| Cláusulas finales | 4797 → 4797 | 5547 → 5547 |
| Cálculos de sistemas | 4959 → 4959 | 674 → 674 |
| `frozenset` de contexto construidos | 20076 → 14877 | 20418 → 2022 |
| Conjuntos intermedios de los dos filtros | 9216 → 0 | 134 → 0 |
| Llamadas a hash nativo de AST | 15710 → 14702 | 2226 → 2186 |
| Entradas en la caché de sistemas | 4959 → 4959 | 674 → 674 |
| Identidades de valores de contexto retenidas | 14877 → 5 | 2022 → 7 |
| Bytes de esos valores de contexto | 3954296 → 140 | 616208 → 196 |

Los outputs exactos coinciden en ambas tareas. Las 4608 normalizaciones finales
de 8queens y las 67 de la tarea mixta terminan sin el retorno temprano de
contradicción; por tanto los counts de los dos conjuntos retirados corresponden
a constructores que el control sí ejecutaba. Los conjuntos auxiliares de
coeficientes de igualdad y comparación estricta siguen siendo necesarios.

La reducción de valores retenidos describe sólo la porción de clave indicada
en el protocolo. No equivale a reducir el proceso de varios megabytes a cientos
de bytes, ni demuestra por sí sola una aceleración total.

## Poda de la tarea mínima

`equality-chain-{control,production}.json` conserva exactamente las cuatro
cláusulas finales y su metadata, con fingerprint
`5af05c01336a04c6ad9bf6d45d22badc396382ccda4a3f58f125df37529edd0f`.

| Medida | Control | Producción |
| --- | --- | --- |
| Modelos enumerados | 43 | 7 |
| Cláusulas finales | 4 | 4 |
| Átomos grounded | 919 | 925 |
| Reglas grounded | 2306 | 2330 |
| Variables del solver | 1266 | 1287 |
| Constraints generales + binarias + ternarias | 5625 | 5697 |

Se evitan 36 modelos que Python descartaba. La closure añade estructura al
grounding y al solver: menos modelos no implica menos grounding ni una mejora
general del tiempo. Esta tarea diminuta demuestra la poda adicional y su
equivalencia, no un porcentaje de aceleración para el catálogo.

## Generación completa e incremental

`semantic-{control,production}.json` enumera hasta agotar cada tarea, con seed 31
y batch size 113. Coinciden los fingerprints completos y los de las uniones
incrementales de grandparent, 8queens, la tarea mixta, `simple_numeric`,
`equality_chain` y `output_only`.

Los fingerprints de cada lote coinciden en los tres datasets de catálogo y en
las sondas numérica simple y sin externos. `equality_chain` pasa de cuatro lotes
a tres: los modelos descartados temprano ya no consumen presupuesto. Conserva
la misma unión de cuatro cláusulas; sus prefijos pueden cambiar y no se exige
la misma trayectoria de búsqueda evolutiva.

La tarea mixta conserva en ambas versiones 5547 cláusulas globales y 5663 en
la unión incremental. Es la diferencia previa entre representantes globales
y por lote; la comparación valida cada ruta contra su control.
Una revisión independiente comprobó además 54 entradas ordenadas de cuatro
sondas pequeñas, incluyendo outputs dirigidos, comparaciones, builtins complejos
y scopes locales con negación.

## Límite de las mediciones de tiempo

La serie prevista alternaba control/producción y producción/control durante
cinco parejas por tarea. Se interrumpió por la variación de carga observada;
los reports incompletos `full-*.json` se conservan sin seleccionar una pareja
favorable ni publicar una mediana de una serie sin terminar.

Alzheimer usa aquí sólo el prefijo determinista de 10000 modelos, con un thread,
no sus 289326 modelos completos. Su pareja registra 26.05 → 77.97 segundos de
wall-clock, mientras la CPU del proceso registra 13.86 → 12.20 segundos. El
fingerprint del prefijo coincide. La divergencia entre wall-clock y CPU, y las
inversiones entre parejas de las otras tareas, impiden atribuir esos tiempos
al cambio. Esta pasada afirma menos construcciones, hashes y modelos en los
casos medidos; no afirma una mejora estable de tiempo total.

## Cadenas y verificación

Aplican IR reificado, metaprograma de poda, canonicalización, materialización,
generación completa e incremental y documentación. No se altera sintaxis ni
compilación de modes/facts en esta pasada. Evaluación de hipótesis completas,
`HypothesisGenerator`, estrategias y los bucles de ambos algoritmos conservan
su contrato. Tampoco cambian `timing.py`, schema, charts, preview ni las etapas
de los diagramas existentes.

Los tests nuevos comprueban IDs superiores a 63, repetición de variables,
ausencia de conjuntos en hits, singleton sin hash nativo, cadenas en ambas
orientaciones, anclaje interno y externo, ausencia de anclaje y guards de
complejidad. Las pruebas diferenciales de generación comparan todos los entries
contra la variante sin esta poda, incluyendo metadata y modos de output.

Verificación final: 1221 tests de generación, compilación, metaprograma,
decodificación, profiling, búsqueda incremental y `syntax_matrix`; Ruff sobre
los Python modificados, `uv run ty check` y `git diff --check`, correctos.
No se ejecutó la suite completa ni se modificó el dashboard.
