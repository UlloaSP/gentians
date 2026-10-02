# Optimizaciones del front-end de tareas

Estado: implementado y medido. Fecha: 2026-10-02.

El cambio se limita a `gentians/language/`, sus contratos y pruebas. Theory
atoms y definiciones theory se rechazan según la decisión del producto. También
se rechazan llamadas externas sin contexto y pools/rangos en átomos de ejemplos;
los pools/rangos siguen disponibles en el background y los contextos. Los
recalls de invenciones admiten `*` y los números de directivas usan dígitos
decimales ASCII.

## Primera ronda: protocolo y control

Control: implementación de `language/` en
`0e315c5796b34e5cf17cc5caaecd97b01d72676f`, antes de estos cambios.
Tratamiento: expansión conjunta de constantes sin pools de variantes
intermedias, caché acotada de kind por identidad, deduplicación temprana de
ejemplos/constantes y framing del background sin copia normalizada.

Comando para ambos estados, usando el mismo script y entorno:

```powershell
uv run --no-sync python -B benchmarks/profile_language.py --repeat 7
```

Para reproducir esta ronda, usa la versión del script presente en
`c9501c74a4e631b7c686f3d467eba20f9fe53615` tanto en ese checkout como en uno
aislado del control indicado. Esa versión contiene los siete workloads de la
primera ronda. No reemplaces archivos del worktree compartido. El script
incorpora su checkout en `sys.path`.

Cada workload se calienta una vez, ejecuta siete muestras con GC previo y
compara todos los outputs con el del calentamiento. Una ejecución adicional
con `tracemalloc`, fuera de las muestras de tiempo, mide el pico Python. El JSON
emitido conserva las muestras y el SHA-256 del output; esos JSON locales no se
versionan ni se editan. Los hashes del control y del tratamiento coinciden en
los siete workloads.

Entorno: Python 3.14.6, Clingo 5.8.2,
Windows-11-10.0.26200-SP0. La medición comprende Python y las llamadas nativas del
front-end, incluido parsing y construcción/formato de AST. No ejecuta grounding,
solving, cierre de hipótesis ni búsqueda; no atribuye una mejora a esas fases.
No modifica `timing.py`, el schema ni el dashboard.

### Workloads

- `first_nested_variant`: primera expansión de una cabeza con
  `p(f(const(t),const(t),const(t),const(t),const(t)))` y cinco constantes:
  3125 variantes posibles. El consumidor solicita solo una.
- `deep_kind` y `shallow_kind`: 1000 consultas de kind sobre un término
  retenido, respectivamente con 600 funciones anidadas y una anotación variable.
- `deep_parse`: parsing de un mode atómico con 600 funciones anidadas.
- `repeated_examples`: parsing de 300 ejemplos idénticos, cada uno con
  inclusión, exclusión y contexto no vacíos.
- `background_lex` y `background_parse`: 3000 hechos con strings y
  comentarios de bloque, midiendo framing y parsing completo respectivamente.

### Resultados

Tiempos: mediana en milisegundos. Cociente: control / tratamiento.
Picos: bytes asignados visibles a `tracemalloc`.

| Workload | Antes ms | Después ms | Cociente | Pico Python antes | Pico Python después |
| --- | ---: | ---: | ---: | ---: | ---: |
| `first_nested_variant` | 114.748 | 0.350 | 327.66 | 913576 | 7098 |
| `deep_kind` | 43.281 | 0.220 | 196.29 | 9088 | 9032 |
| `shallow_kind` | 1.033 | 0.232 | 4.46 | 9385 | 9032 |
| `deep_parse` | 41.200 | 24.234 | 1.70 | 15035 | 63066 |
| `repeated_examples` | 94.838 | 5.437 | 17.44 | 8719 | 8917 |
| `background_lex` | 25.474 | 19.456 | 1.31 | 573368 | 573142 |
| `background_parse` | 71.681 | 64.230 | 1.12 | 1109725 | 930094 |

La primera variante deja de consumir las 3125 combinaciones del término:
el pico Python baja de 913576
a 7098 bytes. La expansión
conserva un valor actual por nodo y actualiza únicamente caminos con constantes
cambiadas, también entre términos de distintos elementos y guards.

El shortcut de ejemplos reduce las llamadas de parsing de sus campos de 900 a
3, más la única llamada del background. Sigue conservando la primera aparición,
la polaridad y el contexto; los duplicados no idénticos se deduplican por IR.

En la primera ronda, el pico Python de `deep_parse` aumentó con la retención de
nodos de la caché por identidad. Esa implementación conservaba hasta 8192
entradas globales y retenía cada nodo para impedir reutilización de su ID; las
demás cachés seguían siendo estructurales. La segunda ronda reemplaza esa
retención global y las restantes claves estructurales.

## Segunda ronda: los diez cambios

Control: `gentians/language/` en
`c9501c74a4e631b7c686f3d467eba20f9fe53615`, que ya incluye la primera ronda.
Tratamiento: el código actual de `language/`. Las diez mejoras son:

1. Kind, argumentos, binding, bindings y tipos de constantes comparten
   metadatos por identidad, sin hash estructural del AST. Los paths de bindings
   se guardan relativos y los resúmenes de constantes se calculan de abajo arriba.
2. El parsing libera sus metadatos al terminar o fallar. La caché temporal tiene
   hasta 8192 entradas y la caché para consultas externas hasta 1024; son límites
   de entradas, no de bytes. La preparación de expansiones libera su scope antes
   de entregar la primera variante.
3. La deduplicación de ejemplos compara inclusión y exclusión como conjuntos,
   conservando el orden, repeticiones y posiciones del primer ejemplo.
   Contexto, polaridad e inclusión/exclusión siguen siendo partes separadas.
4. Los campos de ejemplos ya validados se reutilizan dentro de una tarea aunque
   los ejemplos completos sean distintos. La caché distingue átomos ground de
   contextos y nunca guarda errores.
5. Las recetas de expansión representan cada subárbol sin constantes como un
   solo nodo, sin recorrerlo de nuevo.
6. El producto cartesiano mantiene el orden anterior, avanza primero el dominio
   de la derecha y actualiza solo hojas cambiadas y sus ancestros. Las variantes
   entregadas siguen siendo inmutables.
7. La validación recorre las colecciones de modes con `chain`, sin construir
   tuplas intermedias con todos los elementos.
8. Los marcadores `@`, `&` y `#theory` en strings/comentarios no activan
   una inspección completa adicional del AST. Las extensiones reales conservan
   su rechazo.
9. Los errores semánticos señalan el nodo inválido: términos de ejemplos,
   tipos, direcciones y labels. Un dominio de constantes ausente apunta a su
   primera referencia textual, también en pools factorizados.
10. El splitter devuelve spans recortados de argumentos. Todos sus consumidores
    conservan offsets directamente, sin volver a localizar strings mediante
    búsquedas que podían confundir argumentos repetidos.

### Protocolo reproducible

Usa el script actual y un checkout o snapshot aislado del control indicado:

```powershell
uv run --no-sync python -B benchmarks/profile_language.py --repeat 7 --baseline-root <checkout-control>
```

El snapshot usado en esta medición contenía el paquete `language/` del control,
sin cambios, y un `gentians/__init__.py` vacío. El profiler importa ese paquete
bajo un namespace separado; las cachés Python de control y tratamiento no se
mezclan. Ambos comparten el mismo Clingo y entorno. Cada workload se calienta
en ambos estados; siete muestras alternan cuál se ejecuta primero, con GC previo.
Las comparaciones de outputs y el SHA-256 se calculan fuera del temporizador.
En la enumeración del forest se comparan todos los AST y su orden; su formato
también queda fuera del tiempo de expansión. El pico Python se mide en otra
ejecución con `tracemalloc`, fuera de las muestras de tiempo.

El script añade a los siete workloads históricos:

- `deep_arguments`, `deep_bindings` y `deep_constant_types`: 1000 consultas
  del metadato correspondiente sobre el término retenido de profundidad 600.
- `shared_example_fields`: 300 ejemplos con los mismos dos campos ground y
  300 contextos distintos; se comparan los tres campos de todos los ejemplos.
- `first_fixed_forest_variant`: primera expansión de un forest con una rama
  fija de profundidad 300 y una hoja `const(t)`.
- `sparse_forest_variants`: las 256 combinaciones de ocho términos de
  profundidad 20, cada uno con una hoja de dos constantes.
- `quoted_marker_background`: los 3000 hechos del background histórico más
  un string con los tres marcadores; parsing y formato completo del background.

La medición de vida útil construye primero veinte fuentes distintas de
profundidad 300. Activa `tracemalloc` solo para parsearlas y descartar cada
resultado; fuerza GC y mide bytes retenidos y pico. Este caso no conserva IR ni
llama a los helpers externos entre tareas.

### Resultados

Mismo entorno de la primera ronda: Python 3.14.6, Clingo 5.8.2 y
Windows-11-10.0.26200-SP0. Medianas en ms, cociente control/tratamiento y picos
Python en bytes. Los outputs coinciden en los catorce workloads.

| Workload | Antes ms | Después ms | Cociente | Pico Python antes | Pico Python después |
| --- | ---: | ---: | ---: | ---: | ---: |
| `first_nested_variant` | 0.328 | 0.400 | 0.82 | 7098 | 9093 |
| `deep_kind` | 0.222 | 0.290 | 0.76 | 9032 | 9032 |
| `shallow_kind` | 0.202 | 0.291 | 0.69 | 9032 | 9032 |
| `deep_parse` | 68.378 | 47.872 | 1.43 | 63066 | 349957 |
| `repeated_examples` | 9.289 | 8.504 | 1.09 | 8823 | 10634 |
| `background_lex` | 28.779 | 30.635 | 0.94 | 573095 | 573095 |
| `background_parse` | 126.039 | 131.022 | 0.96 | 925441 | 926433 |
| `deep_arguments` | 130.356 | 0.432 | 301.54 | 465 | 176 |
| `deep_bindings` | 132.041 | 0.482 | 273.72 | 465 | 216 |
| `deep_constant_types` | 124.087 | 0.416 | 298.00 | 465 | 176 |
| `shared_example_fields` | 200.017 | 60.680 | 3.30 | 244598 | 309403 |
| `first_fixed_forest_variant` | 20.719 | 0.375 | 55.25 | 38288 | 4148 |
| `sparse_forest_variants` | 918.502 | 828.393 | 1.11 | 143562 | 150000 |
| `quoted_marker_background` | 711.208 | 138.456 | 5.14 | 919653 | 919846 |

| Vida útil: veinte tareas descartadas | Control | Tratamiento |
| --- | ---: | ---: |
| Bytes Python retenidos tras GC | 3058343 | 64 |
| Pico Python durante parsing | 3138266 | 185125 |

Los campos compartidos bajan de 200.017 a 60.680 ms; la primera expansión con
la rama fija baja de 20.719 a 0.375 ms. El parsing con marcadores entre comillas
baja de 711.208 a 138.456 ms. La enumeración completa del forest reduce el
tiempo un 9.8%; las consultas de metadatos calientes evitan hashes del término
profundo y muestran una diferencia mayor.

Hay costes medidos: 1000 consultas de kind cuestan unos 0.07–0.09 ms más y la
primera variante del caso pequeño unos 0.07 ms más. El pico temporal de
`deep_parse` sube de 63066 a 349957 bytes porque se retienen más metadatos
durante cada parsing, mientras que la memoria retenida entre tareas descartadas
cae en el caso medido. Los campos compartidos también usan más memoria temporal.
El lexer del background, cuyo recorrido no cambia, varía un 6.5%; el parsing
ordinario varía un 4.0% en sentido desfavorable. Estas diferencias pequeñas
se documentan como tales y no justifican una afirmación de mejora general.


## Límites y verificación

Son workloads sintéticos locales con caches calientes; los cocientes grandes
de consultas aisladas no describen la velocidad del solver. No se midió el RSS
ni la memoria nativa de Clingo. El tiempo del background tiene una diferencia
modesta y está sujeto al ruido de la máquina compartida. La generación completa
sigue reteniendo las cláusulas y variantes finales que necesita.

Las pruebas fijan rechazo de sintaxis no soportada, posiciones originales,
finitud de recalls, orden exacto de expansión, ausencia de consumo anticipado y
reutilización inmutable. La cadena aplicable es lenguaje y documentación;
generación, la matriz de sintaxis con ambos algoritmos y cobertura verifican
los consumidores sin modificar `clauses/` ni los `.lp`.

Verificación final de la segunda ronda: 1449 pruebas pasan. No se ejecuta la
suite completa; estas pruebas cubren los productores y consumidores afectados.

```powershell
uv run --no-sync python -B -m pytest tests/test_language.py tests/test_language_frontend.py tests/test_language_frontend_optimizations.py -q -p no:cacheprovider
# 498 passed
uv run --no-sync python -B -m pytest tests/test_clause_space.py tests/test_clause_compilation.py -q -p no:cacheprovider
# 503 passed
uv run --no-sync python -B -m pytest tests/syntax_matrix tests/test_evaluation.py -q -p no:cacheprovider
# 448 passed
uv run --no-sync ruff check gentians/language benchmarks/profile_language.py tests/test_language.py tests/test_language_frontend.py tests/test_language_frontend_optimizations.py
uv run --no-sync ty check
```

Ruff y `ty` pasan. Las regresiones nuevas cubren también cachés liberadas ante
errores, límites de entradas, paths relativos, subárboles fijos, variantes
compartidas inmutables, campos cacheados y cobertura con contexts aislados,
inclusión vacía y negación por defecto. La revisión independiente no deja
hallazgos Important/Critical. No cambian los bucles de búsqueda, las estrategias,
la evaluación de programas completos ni el contrato de métricas/dashboard.
