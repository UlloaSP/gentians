# Implementación de las 25 oportunidades de generación

El inventario distingue cambios automáticos de alternativas optativas. Una
implementación no implica una mejora de velocidad en todas las tareas. Los
protocolos y resultados locales se guardan fuera de Git; [benchmarks.md](benchmarks.md)
define la medición y [clause-generation.md](clause-generation.md) describe las APIs.
No se cambian task files ni se usa cobertura por cláusula para deduplicar.
La continuación con veinte cambios distintos figura en
[la segunda ronda](clause-generation-round2.md).

| ID | Implementación | Activación / límite |
| --- | --- | --- |
| 01 | `Clause` conserva recetas nativas; `RuleRecipes` construye AST bajo demanda con caché acotada. Los consumidores piden solo statements seleccionados. | Automática; conserva sintaxis nativa completa. |
| 02 | `SubsetClauses` enumera combinaciones después de probar independencia sobre modes, tipos, signos, recall y propiedades. | `engine=auto/direct`, completa; nunca por nombre de benchmark. |
| 03 | Particiones por primer modo del cuerpo, Controls independientes, IPC estructural y reconciliación canónica global. | `workers>1`; CPU acotada, un hilo por Control. |
| 04 | Extensión C opcional copia símbolos a registros numéricos y entrega bloques propios de 128. | En esta primera ronda, completa conserva un callback Python por modelo; incremental consume cada Model del iterador. La [tercera ronda](clause-generation-round3.md) sustituye el callback completo por captura nativa. Auto mantiene fallback Python; native forzado exige extensión. |
| 05 | Tabla de componentes con interfaz external/safe/numeric, relaciones exactas sin repetición y equivalencias de pequeños esqueletos `<`/`>` compiladas antes de bindings completos. | Tabla automática; `arithmetic=components` elimina copias de comparaciones estrictas antes de entregar modelos en la familia probada. |
| 06 | Texto reutilizado solo cuando las relaciones no lineales coinciden exactamente, incluida orientación y seguridad. | Automática; una clave semántica sola no basta. |
| 07 | Cuerpo por multiplicidades y ocurrencias derivadas; motor ASP de subconjuntos para la familia independiente. | `body=counts` general; `engine=subsets` restringido. |
| 08 | Elección previa de tipos nominales compatibles por variable global. | `bindings=nominal`; fallback para scopes locales, términos no planos y `any`. |
| 09 | Offsets θ de patrones de repetición posibles bajo recalls compartidos; preparación acotada y fallback exacto. | Automática; chequeo ASP conserva grupos acoplados. |
| 10 | Máscaras firmadas para providers/dependencias; sets solo al consumirlos. | Automática; `p/n` y `-p/n` distintos. |
| 11 | Capacidades positivas por predicado excluyen joins transitivos y triángulos imposibles por recall. | Automática; negativos y puentes conservados. |
| 12 | Mapas disjoint/tuple-mutex incompatibles por tipos filtrados antes de facts. | Automática; conservadora ante constantes/pools. |
| 13 | FD positivas comprueban ausencia del binding objetivo sin segundo dominio de salida. | Automática; guard `arg` protege posiciones fijas; negativos conservan known-unequal. |
| 14 | Formatter de Clingo con buffer creciente reutilizable y una llamada en el caso común. | Automática; UTF-8 y reglas grandes conservados. |
| 15 | Clave no aritmética directa desde literales; wrapper canónico solo para representantes nuevos. | Automática; slots fuera de equivalencia. |
| 16 | Rule builder nativo reutiliza ubicación y arrays CFFI; AST mantiene ownership propio. | Automática; sintaxis de Clingo. |
| 17 | Finalización libera representantes al transferirlos; índices de texto ya deduplicados transfieren propiedad. | Automática; coste fuente mínimo entre textos iguales. |
| 18 | Traits de bindings y tablas de sistemas/componentes comparten análisis para la misma interfaz. | Automática; cachés de 8192, sin retrasar batches. |
| 19 | Controls con dominio reducido y coste total exacto, incluyendo condiciones adjuntas. | Incremental `strata=ground`; assumptions por defecto. |
| 20 | Presets de Clingo; argumentos explícitos prevalecen y cada Control fuerza modelos ilimitados. | `configuration`; sin cambio evolutivo. |
| 21 | Decoder reutiliza estado/listas, prepara offsets y limpia posiciones tocadas. | Automática; Python e incremental incluidos. |
| 22 | Metadata por mode y folding iterativo de prefijos con retención acotada. | Automática; familia independiente suma bits disjuntos directamente. |
| 23 | Inferencia evita proyecciones sin consumidores compatibles; conserva puentes indirectos. | Automática; `infer_maps=false` como control. |
| 24 | Snapshot JSON entrada por entrada sin segunda lista/string completos. | `profile_clauses.py --debug`; fuera del neto de generación. |
| 25 | Scope de GC difiere colecciones, incluye colección final y restaura estado en `finally`. | `gc=defer`; normal por defecto. |

La propuesta 05 implementa representación canónica de componentes en Python y
la alternativa de precompilar equivalencias de pequeños esqueletos antes de
enumerar bindings completos. La poda optativa conserva cualquier alternativa
individual y elimina solo una copia posterior de la misma comparación estricta.
Rechaza familias con otros operadores, labels en comparaciones, outputs de
comparaciones o scopes locales: liberar recall puede activar otras podas.
Los atoms sin condiciones conservan pools y términos anidados; la forma completa
del head y sus guards permanece intacta. La sustitución general de raw literals por
componentes aritméticos completos sigue pendiente y no se presenta como resuelta.
La especialización conserva el espacio completo; sus prefijos de modelos y
fronteras de batches incrementales pueden cambiar.

La deduplicación textual corrige además un defecto anterior: diferentes keys
aritméticas podían imprimir el mismo texto, y su coste dependía del orden de
modelos. Ahora gana la fuente legal de menor coste; los guards sintéticos del
AST no cuentan como source literals. Para comparar, se conserva el baseline
histórico intacto y se genera un control con únicamente esta corrección.

La verificación cubre tres cadenas: lenguaje/generación (modes, facts,
metaprograma, decoder, recetas y tests); consumidores de hipótesis (materialización
y cierre firmado); medición (timing, productor, schema 14 y preview). Ambas
estrategias evolutivas consumen `ClauseSpace`; sus bucles, evaluación y score
siguen intactos. Los charts excluyen trabajo de procesos que se solapa con pared.
