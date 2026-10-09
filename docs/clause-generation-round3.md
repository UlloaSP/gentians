# Tercera ronda de generación

Continúa las [25 primeras intervenciones](clause-generation-optimizations.md) y
las [20 siguientes](clause-generation-round2.md). Los snapshots usan como referencia
el estado posterior a esas 45 intervenciones. Los tres controles «round2 → final»
importan ese código congelado en el brazo A; los demás contrastan opciones de
las fuentes finales. Resultados y protocolo reproducible
permanecen en `.debug/generation-round3-20261007/`, fuera de commits.

| Línea | Implementación | Alcance y límite |
| --- | --- | --- |
| Callback nativo | El callback C copia cada modelo a filas propias y entrega bloques a Python, sin crear un wrapper `Model` por modelo. | Generación completa con extensión; el iterador incremental conserva su presupuesto por modelo. Handle cerrado también ante error, owners vivos, excepción Python restaurada y acceso de varios hilos serializado. |
| Recetas compactas | `PackedRecipe` guarda índices numéricos de literales compartidos por su `RuleRecipes` propietario y los sistemas aritméticos exactos. | Packing al aceptar representantes y en el motor directo. El consumidor reconstruye la receta solo al pedir AST; Clingo conserva formato y sintaxis. `storage=recipes` permite el control. |
| Componentes estrictos | `arithmetic=projected` enumera una clase por conjunto de edges estrictos y fuente no comparativa exacta. | Usa la familia probada de `components`: comparaciones `<`/`>` input numeric sin labels ni condiciones. Los testigos fuente satisfacen los checks originales; tienen igual multiplicidad fuente y metadata. Otras familias conservan la enumeración estándar. |
| Prefijos tipados | `bindings=connected` construye la partición global por ocurrencia: reutilizar un id del mismo tipo o introducir el siguiente id denso. | Atoms planos y heads normales sin scopes, pools ni condiciones. El flujo de inputs/outputs y todas las propiedades permanecen en ASP; no exige que el orden sintáctico sea orden de ejecución. |
| Matriz de encodings | Comparaciones exhaustivas por caso y controles repetidos de las alternativas. | Configuración de ejecución; ningún task file cambia. No se seleccionan rutas por nombre de benchmark ni se atribuye velocidad a una observación aislada. |

`storage=auto` compacta en la especialización directa nativa probada y conserva
recetas en ASP e incremental. Los controles del millón muestran menor RSS con
packing; los tiempos de acetyl varían entre controles. El experimento contrasta
también un solo hilo para examinar el efecto de la planificación paralela.
Esta elección conservadora usa el
guard de la familia y el motor, sin excepciones por nombre de dataset.
`storage=packed` conserva la alternativa de memoria para cualquier motor.
En los controles ABBA seriales, `packed` ahorra 25,8 MiB en acetyl y 97,4 MiB
en Euclid, y aumenta sus medianas de tiempo un 2,6 % y un 1,4 %, respectivamente.
Son dos observaciones por brazo; los rangos completos se conservan.

La proyección entrega menos testigos a Python; no elimina necesariamente todas
las decisiones internas del solver. En el pase debug de Euclid con `5,split`
llega a un modelo por cláusula canónica, pero aumenta fuertemente los conflictos
y la RSS del proceso y empeora el tiempo total. Con un hilo, los controles
repetidos muestran una mejora de tiempo; la configuración importa. No se activa
por defecto ni se presenta
la reducción de modelos como una mejora del conjunto. El control sin
instrumentación y las estadísticas completas se conservan en el experimento.
La equivalencia de un componente no se
deduce de la cobertura de ejemplos. La sustitución general de componentes
aritméticos completos, especialmente no lineales, sigue fuera de esta familia.
La ruta tipada construye dominios directamente en ASP y reutiliza su legalidad;
no duplica en Python los numerosos guards del metaprograma para Alzheimer.

Los pools son locales al propietario, incluidos sus mode ids y bindings. Un
`Clause` conserva a ese propietario, aunque desaparezca el `ClauseSpace` de
origen. No se usan índices ni punteros nativos de otro task o proceso. El IPC
conserva recetas estructurales; el padre compacta después de reconciliar fuentes.
Una cláusula archivada mantiene todo el pool de su lote, incluidos literales
de representantes que después se reemplazan o deduplican por texto. El tamaño
del pool puede importar cuando se conservan pocas cláusulas de un lote grande;
el ahorro de la receta individual no demuestra menor RSS incremental.
Tanto `steady_state` como `incremental` consumen los mismos statements y metadata
firmada. Sus bucles y la evaluación no monótona del programa no cambian.

En la ruta nativa, los timers atribuyen captura y entrega al coste de callbacks,
con clocks desactivados cuando no hay instrumentación. El self time de
`_records.solve` en cProfile mezcla solve y captura: aparece fuera del denominador
Python. Los constructores `ReifiedClause` comprueban la cobertura del profiler
por modelo, sin confundir bloques con modelos. Los timings normales siguen
separando grounding, solving y trabajo restante, sin cambiar schema o charts.

Los errores de entrega Python y SIGINT detienen Clingo mediante `goon=false`
y una terminación normal; el callback guarda la excepción original y la restaura
después de cerrar el handle. Esto permite reutilizar el Control y evita convertir
un error Python en un error interno del solver paralelo. Los fallos reales de
captura/API devuelven error y establecen el estado TLS en cada hilo afectado;
Clingo no garantiza reutilización después de esos fallos de API.

## Verificación y lectura de los resultados

La matriz aplica la ruta final, `packed`, `connected`, `projected`, `nominal`,
`properties`, `counts`, `frumpy` y `trendy` a los 39 benchmarks del catálogo.
Incluye los cuatro Alzheimer, el caso de más de un millón y Euclid. Cada pase
usa `profile_clauses.py --debug` y compara el snapshot completo con el control
posterior a la segunda ronda; no basta con comparar el número de cláusulas.
Las estadísticas completas de Clingo se guardan en otro pase exhaustivo.
La combinación proyectada serial también completa los 39 casos con igualdad
exacta; el censo estándar serial de Euclid añade su referencia. Son 118 censos
exhaustivos completos: 39 estándar y 39 proyectados con `5,split`, 39
proyectados con un hilo y ese estándar serial adicional.
El censo inicial por encoding detiene el solver después del primer modelo y se
etiqueta como tal: sus variables internas no son `#maxv`, ni se confunden con
los contadores finales de una enumeración completa.

Los controles ABBA usan procesos nuevos y desactivan timers, estadísticas y
exportación. Conservan dos observaciones por brazo, el rango y un fingerprint
completo; ese tamaño de muestra no demuestra una ganancia universal. cProfile
se ejecuta aparte en los 39 benchmarks, incluidos Alzheimer y Euclid, y verifica
cobertura por modelo. Los
resultados detallados y sus límites están en el informe local derivado, junto
a los logs y manifests, sin sustituir ni editar las salidas de los productores.

En Euclid, el control serial de proyección reduce la mediana de 458,868 a
249,719 segundos (45,6 %), con dos medidas por brazo. El control con `5,split`
la aumenta de 455,855 a 682,100 segundos y añade aproximadamente 1,86 GiB de
RSS. La opción se mantiene explícita: menos modelos no determina por sí solo
una configuración más rápida.

Para elegir la combinación serial medida, configura la ejecución:

```python
arguments.clause_generation.update({
    "arithmetic": "projected",
    "workers": 1,
    "clingo_arguments": ["--parallel-mode=1"],
})
```

El guard del language bias decide si la proyección aplica. Las otras familias
conservan la ruta estándar; no se modifica el límite de variables ni el lenguaje.

El perfil completo de Euclid captura los 4.626.311 modelos fuente. La igualdad
profunda de `Expression` acumula 17.885.860 llamadas y el 24,7 % del self time
Python/bindings. Los cuatro Alzheimer ya entregan un modelo por cláusula
canónica; allí siguen pesando decode, preparación de partes, render y
almacenamiento de resultados distintos. Estos perfiles localizan costes y no
se reescalan al tiempo sin instrumentación.

Aplican las cadenas de lenguaje/generación, consumidores de hipótesis,
medición y documentación. Se conservan sintaxis, evaluación del programa
completo y bucles de ambos algoritmos. La medición cambia captura y el productor
de cProfile, sin añadir campos al schema del dashboard ni modificar sus charts.
El diagrama de generación actualiza tanto su fuente JSON como su HTML.

La verificación de fuentes finales incluye la suite completa, los tests de esta
ronda, Ruff, `ty check` y un wheel instalado en un directorio aislado. Los tests
de callbacks cubren errores Python, SIGINT real, ejecución con varios hilos y
reutilización del Control. Los tests de representación cubren scopes, pools,
heads, tipos, signos, aritmética, fallback portable, IPC y vida de los owners.
La política automática y los presupuestos incrementales se comprueban también.
