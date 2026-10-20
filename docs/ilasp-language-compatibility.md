# Contrato de generación de cláusulas de ILASP

Contrato actualizado el **16 de octubre de 2026** para el
[generador independiente](../tools/ilasp/standalone/README.md). El objetivo es
reproducir el conjunto de elementos con coste de **`ILASP 4.4.1 -s`** de la copia
local identificada en [el informe](ilasp-reverse-engineering.md). La herramienta
usa Python y Clingo; el ejecutable solo es necesario para validar con el oracle.

Se auditaron lexer/parser nativo, constructor y compilador de modes, opciones
leídas por `createSearchSpace` y decoder. El ASP predeterminado se conserva
completo, con ambos encodings de saturación. El corpus reproducible contiene
**271 casos y 4 777 elementos con coste** y compara conjuntos completos.
La matriz recoge el comportamiento observado de esta compilación, incluso
cuando difiere del manual web.

## Entrada de generación

| Entrada | Comportamiento implementado y contrastado |
| --- | --- |
| `#modeh`, `#modeha`, `#modeb`, `#modec`, `#modeo` | Cabezas normales/disyuntivas, cabezas choice, cuerpos, condiciones y cuerpos weak; formas con recall y opciones. |
| Recall | Entero no negativo; omisión y cero no imponen cota propia. Permanecen los límites globales. |
| Opciones | `positive`, `negative`, `symmetric`, `anti_reflexive`, `non_recursive`; se emiten como `constraint/2`. Opciones simbólicas desconocidas avisan y se conservan para el bias personalizado. |
| `var(t)`, `const(t)`, `#constant(t,c)` | Tipado sintáctico y sustituciones; incluye `any`, constantes funcionales, strings y rangos. No exige un predicado de background para cada tipo. |
| Términos de mode | Funciones anidadas, tuplas de al menos dos elementos, rangos, comparaciones y aritmética reificada según la rutina nativa. |
| `#maxv`, `#maxp`, `#minhl`, `#maxhl` | Defaults `3`, `2`, `1`, `2`; la tarea puede reemplazarlos. |
| `#disallow_multiple_head_variables` | Emite `dmhv` y aplica el constraint recuperado, sin reinterpretarlo como otra poda. |
| `#weight(w)` | Pesos enteros o variables de un tipo autorizado, incluidos pesos negativos reificados. El peso ASP es distinto del coste seleccionable. |
| `#predicate(t,p/a)`, `#modem(c,m(...))` | Predicados tipados, `any/a`, aridad cero y selectores de metarules. El entero inicial obligatorio de `#modem` representa coste. |
| `n ~ regla` | Espacio explícito con coste no negativo, incluido cero; reglas normales, disyunciones, choices, constraints, agregados, condicionales y weak constraints. |
| Predicados variables | `P(X)` y `P` en reglas explícitas/plantillas; se muestran como `#P(X)` y `#P`. Se preservan las variables ordinarias de argumentos y tuplas. |
| `#bias("ASP")` | Amplía el generador o lo define con `--override-default-sm`. Incluye ASP con optimización y scripting Python de Clingo. |
| Strings de bias | Admiten newlines literales; el lexer nativo solo desescapa comillas, repetidamente, y conserva otros backslashes. No son strings JSON. |
| `#include "archivo"` | Resolución relativa a cada archivo; los ciclos producen error. |

Clingo analiza ASP, con una transformación reversible para predicados variables
de ILASP. Esto no convierte cualquier AST de Clingo en un mode válido: el
ejecutable rechaza varias formas y algunas entradas aceptadas abortan al generar.
Referencias: [modes](https://doc.ilasp.com/specification/mode_declarations.html),
[espacio explícito](https://doc.ilasp.com/specification/explicit_hypothesis_space.html),
[metarules](https://doc.ilasp.com/specification/metarules.html).

## Opciones efectivas

| Opción | Default o efecto |
| --- | --- |
| `-ml`, `--max-body-literals` | `3`; límite de cuerpo ordinario. |
| `--max-rule-length` | `5`; límite ordinario, incluidas condiciones. |
| `--max-wc-length` | `3`; límite de cuerpo weak. |
| `-na`, `--no-aggregates` | Excluye choices del encoding predeterminado. |
| `-nc`, `--no-constraints` | Excluye hard constraints del encoding predeterminado. |
| `--strict-types` | Añade dominios `body(V,T)` sin aumentar el coste sintáctico. |
| `--override-default-sm` | Omite el encoding predeterminado; conserva modes y bias. Activa bias sin modes. |
| `--learn-heuristics` | Añade el bloque nativo [heuristics.lp](../tools/ilasp/recovered/heuristics.lp). |
| `-s`, `-st` | Genera elementos o emite el generador ASP. |

Son las opciones que afectan al espacio en la ruta inspeccionada. Los algoritmos
de `--version` comparten generación. `-mw` y `--expand-sm` no cambian `-s`; se
aceptan sin expandir selectores. La CLI independiente añade JSON y expansión
opcional de metarules; no acepta todos los parámetros de aprendizaje.
[Parámetros públicos](https://doc.ilasp.com/parameters.html)

## Representación, decoder y poda

| Átomos mostrados por el generador | Elemento decodificado |
| --- | --- |
| `head/1`, `body/1` | Regla normal o constraint. |
| `in_head/1`, `lb/1`, `ub/1` | Choice; sin cota inferior, disyunción. |
| `condition/2` | Condición de un literal de cuerpo o cabeza agregada. |
| `weak_body/1`, `weight/1`, `priority/1` | Weak constraint; conserva variables globales y locales en la tupla. |
| `body/2` | Dominios de tipos, separados de los literales que cuentan coste. |
| `var__/1`, `naf/1`, `minus/1`, `bin_exp/3` | Variables, negación por defecto, menos y operadores reificados. |
| `cost/2`, `attribute/1`, `meta_rule_instance/0` | Coste explícito, atributos y marca de selector. |

La autoridad de legalidad y poda es el [ASP recuperado](../tools/ilasp/recovered/search-space.lp).
Conserva seguridad, condiciones locales, recalls, coincidencias cabeza/cuerpo,
negación y ambas saturaciones. No se reemplazan por renombrado sintáctico ni
por cobertura de ejemplos. [Meta ASP público](https://doc.ilasp.com/specification/meta_asp_hypothesis_space.html)

Se reproducen detalles del decoder: coste combinatorio de choices y fallback de
`nCr` fuera de `0..n`; suma de `cost/2`; orden de lectura de múltiples cabezas,
pesos y cotas custom; variables de condiciones/tipos en tuplas weak; pérdida de
agrupación aritmética al imprimir términos reificados. Los espacios explícitos
conservan sus paréntesis y el orden de tuplas. Las cotas estrictas de agregados
enteros se normalizan a inclusivas equivalentes, como imprime ILASP.

La salida se deduplica y ordena determinísticamente. El comparador normaliza el
orden de cuerpos, condiciones y elementos de cabezas/agregados. No renombra
variables ni cambia pesos, signos o tuplas.

## Aprendizaje y scripts

Background, `#pos`, `#neg`, `#opt`, orderings brave/cautious/optimal,
`#max_penalty` e inyección de búsqueda no alteran el espacio estático contrastado.
Los bloques `#ilasp_script` y `#script` del nivel de tarea se omiten sin ejecutar.
Python **dentro del ASP de `#bias`** forma parte del generador y sus funciones
`@f()` sí se ejecutan. Usa el contexto estándar compartido de Clingo; no aísla
scripts de distintas tareas. `--emit-asp` conserva el código sin ejecutarlo.

`-s` produce selectores de metarules, incluso para plantillas de varias reglas.
La expansión opcional conserva cada programa como una unidad con coste y admite
guards positivos independientes. Rechaza dependencias acopladas o negativas
entre selectores, que requieren la hipótesis completa. Esa restricción no reduce
la generación de selectores `-s`.
[Metarules](https://doc.ilasp.com/specification/metarules.html), [PyLASP](https://ilasp.com/PyLASP)

## Límites y verificación

Están implementadas todas las ramas y opciones de generación estática
identificadas en esta compilación. No hay una prueba universal de equivalencia
para ASP/Python arbitrarios. Un bias con grounding infinito o Python que no
termina tampoco garantiza una enumeración finita en ILASP. Los errores no se
convierten en espacios truncados.

Las representaciones que el propio decoder nativo convierte en ASP inválido
producen error: por ejemplo, weak constraints sin peso/prioridad o ciertos
símbolos negativos custom. Se conserva la salida degenerada `.` de choices
vacías para compatibilidad; no es ASP ejecutable. No se reconstruyen optimizador
de hipótesis, conflictos ni driver PyLASP, ni se promete soporte de versiones
futuras. Este código queda separado del lenguaje y la búsqueda de Gentians.

```powershell
uv run pytest tests/test_ilasp_standalone.py -q
uv run python -m tools.ilasp.validate_standalone
```

Las capturas [originales](../tests/fixtures/ilasp-space.json) y
[ampliadas](../tests/fixtures/ilasp-space-extensions.json) incluyen 80 combinaciones
con seed `44116` y nueve tareas públicas del autor. Estas conservan URL y SHA-256
del original: sus declaraciones de generación se extrajeron después de contrastar
las tareas completas. El replay permite repetir las comparaciones contra el
oracle con `--oracle`. Los JSON se producen por captura, sin ajustes manuales.
