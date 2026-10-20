# Generador independiente de tareas ILASP

Lee un `.las` y genera sus **reglas candidatas con coste**, como `ILASP -s`.
Funciona con Python y Clingo, sin ILASP, WSL, REA, Ghidra ni acceso a red en
ejecución. No añade dependencias al proyecto.

Desde la raíz del repositorio:

```powershell
uv run python -m tools.ilasp.standalone benchmarks/ilasp/coin.las
uv run python -m tools.ilasp.standalone ruta/tarea.las --emit-asp > generador.lp
uv run python -m tools.ilasp.standalone ruta/tarea.las --json
uv run python -m tools.ilasp.standalone ruta/metarules.las --expand-metarules
```

La salida predeterminada usa `coste ~ regla`. `--json` conserva también los
atributos y distingue los selectores generados por `#modem`. La enumeración
termina antes de escribir resultados: un error no publica un espacio parcial.
Se eliminan duplicados y se ordena la salida de forma determinista.

Opciones de generación: `-ml N` / `--max-body-literals N`,
`--max-rule-length N`, `--max-wc-length N`, `-na` / `--no-aggregates`,
`-nc` / `--no-constraints`, `--strict-types`, `--override-default-sm` y
`--learn-heuristics`. `-s` y `-st` son aliases de generación y emisión ASP.
`--version`, `-mw` y `--expand-sm` se aceptan con el comportamiento de `-s`:
no cambian esa enumeración ni expanden selectores.
Los valores predeterminados reproducen el generador recuperado de ILASP 4.4.1.

## Entrada y significado

Implementa `#modeh`, `#modeha`, `#modeb`, `#modec`, `#modeo`, `#modem`, recall,
`positive`, `negative`, `symmetric`, `anti_reflexive`, `non_recursive`, `var`, `const`, constantes,
tipos, límites `#maxv`/`#maxp`/`#minhl`/`#maxhl`,
`#disallow_multiple_head_variables`, pesos, `#predicate`, `#bias` y espacios
explícitos `coste ~ regla`, incluido coste cero. Las opciones de mode desconocidas
producen un aviso y siguen disponibles como `constraint/2` para `#bias`, igual
que en ILASP. Admite `#include` relativo al archivo que lo contiene.
Clingo analiza las reglas explícitas; el lector añade predicados variables
`P(X)` y `P`, que el output nativo representa como `#P(X)` y `#P`.
El compiler de modes maneja funciones anidadas, tuplas de dos o más elementos,
rangos y aritmética reificada con el orden del ejecutable.

Conserva el metaprograma recuperado, incluidos sus dos encodings de saturación.
El decoder cubre reglas normales, disyunciones, choices, constraints,
condicionales y weak constraints. No calcula cobertura individual de cláusulas.
Background, ejemplos `#pos`/`#neg`/`#opt`, orderings, `#max_penalty` e inyecciones
de búsqueda no modifican el espacio estático de candidatos. Los bloques
`#ilasp_script` y `#script` del nivel de tarea se reconocen y omiten, igual que
en la ruta `-s` contrastada.

`#bias` se añade al generador. `--override-default-sm` retira el encoding
predeterminado y permite generar exclusivamente mediante ese ASP, incluso sin
modes. El usuario conserva la responsabilidad de dar un programa con grounding
finito; no se trunca ni se limita silenciosamente su espacio. El ASP de `#bias`
puede incluir Python de Clingo y funciones `@f()`: se ejecutan durante la
generación. Esto es distinto de los scripts del nivel de tarea. Los strings de
`#bias` admiten saltos de línea literales y conservan los backslashes conforme
al lexer nativo. `--emit-asp` los conserva sin ejecutar el generador.
La API usa el entorno Python estándar de Clingo, compartido entre llamadas;
no aísla scripts arbitrarios de tareas diferentes.

## Metarules

Como ILASP 4.4.1, la salida predeterminada enumera selectores:

```text
5 ~ closure(p1,edge).
```

`--expand-metarules` produce JSON e incluye el campo `program` con las reglas
ASP de cada selector. Ese conjunto es **una única unidad seleccionable de
coste 5**, aunque contenga varias cláusulas. No se debe dividir en candidatos
con costes independientes. La expansión incluye reglas ordinarias del
background que dependan directamente del mismo selector.

La expansión opcional admite guards positivos independientes, repeticiones del
mismo guard y argumentos anónimos. Rechaza dependencias entre selectores,
referencias dentro de agregados/condicionales, definiciones de selectores y
dependencias negativas: especializarlas requiere tratar la hipótesis completa.
Ese rechazo afecta a la expansión, no a la generación de selectores `-s`.

## API

```python
from tools.ilasp.standalone import generate, read_task

task = read_task("tarea.las")
for entry in generate(task):
    print(entry.cost, entry.rule, entry.attributes, entry.meta)
```

`compile_task(task, options)` devuelve el generador ASP. `expand_metarule(task,
entry)` devuelve una tupla de reglas del programa asociado. `Options` solo
configura los límites y flags propios de esta herramienta; no altera
`Arguments` ni el lenguaje de Gentians.

## Verificación y límites

```powershell
uv run pytest tests/test_ilasp_standalone.py -q
uv run python -m tools.ilasp.validate_standalone
```

Las capturas de 271 casos del oracle ILASP 4.4.1 contienen 4 777 elementos con
coste. El replay comprueba igualdad de conjuntos completos, normalizando el
orden de conjunciones, condiciones y elementos de cabezas/agregados mediante
el AST de Clingo. Normaliza cotas estrictas de agregados enteros a cotas
inclusivas equivalentes, como imprime ILASP. Conserva nombres de variables,
signos, pesos y tuplas de weak constraints. Incluye 80 combinaciones con seed
fija y las declaraciones de generación de nueve tareas públicas del autor,
contrastadas antes como tareas completas. También hay pruebas semánticas de metarules y una
prueba que prohíbe abrir ILASP o lanzar procesos durante la generación.

Para repetir contra un ejecutable instalado en Linux:

```bash
uv run python -m tools.ilasp.validate_standalone --oracle '["./tools/ilasp/ILASP","-s","{task}"]'
```

El comando del oracle es un array JSON, sin shell. En Windows puede contener
`wsl`, su entorno y `{task_wsl}`. `--update` regenera las capturas usando ese
comando únicamente si todas las comparaciones pasan.

La compatibilidad comprobada es con la generación de candidatos de **4.4.1**.
El alcance cubre las ramas y opciones de generación estática identificadas en
esa compilación. No implementa el optimizador de hipótesis, el análisis de
conflictos ni el driver PyLASP. Python arbitrario o ASP de grounding infinito no
garantizan una enumeración que termine; no hay truncamiento silencioso.
La validación diferencial no demuestra equivalencia para toda entrada posible
ni para extensiones futuras del parser.

Se conserva una peculiaridad del decoder nativo: una choice sin átomos de
cabeza se imprime como `.` o como un constraint sin sus límites. `.` no es una
regla ASP ejecutable. Para inspeccionar la representación completa, usar
`--emit-asp`; esta compatibilidad con la salida nativa no demuestra equivalencia
semántica de ese caso degenerado. También se conservan costes y cotas
peculiares de choices y la pérdida nativa de paréntesis aritméticos al
decodificar modes. Las reglas explícitas sí mantienen su agrupación.
Las representaciones custom que el propio decoder nativo convierte en ASP
inválido, como weak constraints sin peso o prioridad, producen un error
explícito. No se publican como reglas válidas.

Procedencia y comparación de tareas del repositorio:
[informe](../../../docs/ilasp-reverse-engineering.md).
