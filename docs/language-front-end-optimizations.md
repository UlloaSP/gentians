# Optimizaciones del front-end de tareas

Estado: implementado y medido. Fecha: 2026-10-02.

El cambio se limita a `gentians/language/`, sus contratos y pruebas. Theory
atoms y definiciones theory se rechazan según la decisión del producto. También
se rechazan llamadas externas sin contexto y pools/rangos en átomos de ejemplos;
los pools/rangos siguen disponibles en el background y los contextos. Los
recalls de invenciones admiten `*` y los números de directivas usan dígitos
decimales ASCII.

## Protocolo y control

Control: implementación de `language/` en
`0e315c5796b34e5cf17cc5caaecd97b01d72676f`, antes de estos cambios.
Tratamiento: expansión conjunta de constantes sin pools de variantes
intermedias, caché acotada de kind por identidad, deduplicación temprana de
ejemplos/constantes y framing del background sin copia normalizada.

Comando para ambos estados, usando el mismo script y entorno:

```powershell
uv run --no-sync python -B benchmarks/profile_language.py --repeat 7
```

Para reproducir el control, coloca este mismo script en un checkout aislado del
commit indicado y ejecútalo con el mismo entorno Python. No reemplaces archivos
del worktree compartido. El script incorpora ese checkout en `sys.path`.

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

## Workloads

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

## Resultados

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

El pico Python de `deep_parse` aumenta con la retención de nodos de la caché
por identidad. La caché conserva como máximo 8192 entradas y retiene cada nodo
para impedir reutilización de su ID. Se acepta este coste a cambio de evitar el
hash estructural en consultas de kind. Las demás cachés estructurales conservan
sus límites.

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

