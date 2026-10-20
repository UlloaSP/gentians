# Ingeniería inversa de ILASP

## Alcance

Inspección de los días 15 y 16 de octubre de 2026 de la generación y poda del espacio de
cláusulas de ILASP. Combina documentación primaria, salidas del ejecutable y
análisis estático con REA/Ghidra. No es una reconstrucción completa de ILASP ni
un benchmark de rendimiento.

El [README del ejecutable](../tools/ilasp/README.md) identifica la copia local
como ILASP 4.4.1, compilada el 11 de noviembre de 2024. La documentación web no
está versionada por esa compilación; sus afirmaciones requieren contraste local.
El binario es ELF PIE Linux x86-64, conserva `.symtab` y no contiene secciones
`.debug*`. SHA-256 comprobado antes y después de las pruebas:
`816edec521b48f88bd078960e6b4a1c99723e1f64ea20a502eebd496d89dc6c5`.

## Resultado comprobado

### Generación independiente desde `.las`

La recuperación se convirtió en una herramienta ejecutable:

```powershell
uv run python -m tools.ilasp.standalone benchmarks/ilasp/coin.las
```

El [código y su contrato](../tools/ilasp/standalone/README.md) contienen un lector
de declaraciones ILASP, compilación de modes, decoder de todas las ramas del
generador recuperado y expansión opcional de metarules independientes. Solo
importa stdlib y Clingo; no importa Gentians ni inicia procesos. Se mantiene
separado del parser, IR, `ClauseSpace` y búsqueda evolutiva de Gentians.

La verificación posterior cubre:

| Control | Resultado |
| --- | --- |
| 271 casos capturados, incluido `coin` | 4 777 elementos con coste; igualdad completa con `ILASP -s`, tanto en replay como contra el ejecutable. |
| Nueve tareas públicas del autor | 2 249 elementos con coste; igualdad completa. Sus declaraciones se incluyen en el corpus capturado con URL y SHA-256 de los originales. |
| 80 combinaciones de modes con seed `44116` | Igualdad completa; combinan formas, recalls, opciones, tipos, constantes y flags. Incluidas en los 271 casos. |
| Enumeración de 28 tareas existentes de `benchmarks/ilasp/` | 59 543 elementos con coste; ninguna diferencia. |
| Compilación de las 13 tareas con modes de ese directorio | Generadores ASP iguales tras normalizar orden sintáctico con Clingo, incluidas las cinco tareas cuya enumeración del oracle no terminó en el límite. |
| Tests independientes del oracle | 307 pruebas pasan; incluyen semántica de metarules/agregados, errores atómicos, scripts y prohibición de abrir ILASP/lanzar subprocesos. |
| Comprobaciones estáticas | Ruff sobre los archivos nuevos y `uv run ty check` pasan. |

Las capturas reproducibles viven en
[tests/fixtures/ilasp-space.json](../tests/fixtures/ilasp-space.json) y
[tests/fixtures/ilasp-space-extensions.json](../tests/fixtures/ilasp-space-extensions.json),
producidas por el oracle, no editadas a mano. El
[replay diferencial](../tools/ilasp/validate_standalone.py) permite repetirlas
con o sin ejecutable. Se comparan conjuntos de reglas **con coste**, no solo
sus tamaños. La normalización ordena cuerpos, condiciones y elementos de
cabezas/agregados; normaliza cotas estrictas de agregados enteros a inclusivas
equivalentes, como imprime ILASP. No renombra variables ni cambia signos,
pesos o tuplas.

Protocolo de tareas existentes: lectura sin modificaciones, ILASP 4.4.1 `-s`
con flags predeterminados, timeout de 30 s por tarea del oracle; después,
`python -m tools.ilasp.standalone archivo.las` con timeout de 60 s. La comparación
usa `weighted_rules` del replay. `5queens` y las cuatro tareas `alzheimer_*`
agotaron el tiempo del oracle: no se presentan como enumeraciones verificadas.
El control separado `-st` de esas tareas sí terminó y coincide con el compiler.
No se han medido mejoras de rendimiento ni se ha cambiado el problema inductivo.

Entorno: Windows/PowerShell, Python del proyecto mediante `uv`, Clingo 5.8.2;
oracle Linux en WSL `kali-linux` con `libpython3.10` y su biblioteca estándar
externas al repositorio. El generador independiente se ejecuta directamente en
Windows. Los logs y salidas extensas de esta sesión se conservan en
`C:\tmp\gentians-ilasp-re\repo-validation` y `...\oracle`.

La ampliación se conserva en `...\complete`, `...\fuzz` y `...\public`.
Las tareas públicas completas se descargaron del
[sitio del autor](https://www.doc.ic.ac.uk/~ml1909/ILASP/) sin modificar las
tareas del repositorio: `agentA/B/C`, `hamiltonA/B`, `journey2` y
`schedulingA/B/C`. Para las tres `agent` se usó `-ml=5 -nc`; el resto usa
defaults. Tras comparar los originales se extrajeron únicamente declaraciones
de generación y candidatos explícitos para los fixtures; sus espacios siguen
coincidiendo con las capturas de las tareas completas.

La auditoría posterior recuperó `yyparse` (306 605 caracteres), `yylex`
(31 235) y el constructor de modes (24 225), y revisó las opciones leídas por
`createSearchSpace`. Se añadieron `--learn-heuristics`, opciones de mode
simbólicas, coste explícito cero, ejemplos `#opt`, scripts del nivel de tarea,
predicados variables de aridad cero y el orden nativo de reificación aritmética.
Las pruebas de decoder custom fijan condiciones locales, tipos y tuplas weak,
múltiples pesos/cabezas/cotas y cotas negativas de choices.

También se contrastó Python embebido en `#bias`: funciones que devuelven
constantes, pools y costes. Es parte del generador, mientras que `#script` y
`#ilasp_script` del nivel de tarea se omiten en `-s`. El lexer nativo admite
newlines literales en strings de bias y solo desescapa comillas; el lector
independiente conserva esa semántica. Se habilita el soporte estándar de
`clingo.script`, con su contexto Python compartido entre llamadas.

Para esos controles se completó el runtime externo del oracle con CFFI 1.15.1
y el paquete Python Clingo 5.7.1, que coincide con `libclingo version 5.7.1`
presente en el binario. Viven en `C:\tmp\gentians-ilasp-re\python310-cffi` y se
añaden al `PYTHONPATH` de WSL; no cambian dependencias ni archivos del proyecto.
El replay final completo está en `...\complete\live-replay-final.log`.

También se recuperaron con REA/Ghidra `Utils::replace_arithmetic` (`0x2e6d60`,
29 786 caracteres de pseudocódigo) y `nCr` (`0x24fb30`, 5 662 caracteres). Junto
al decoder principal permiten explicar el coste no lineal de choices: para
`n` átomos se multiplica `n` por la suma de los coeficientes de los tamaños
entre sus límites. La rutina nativa devuelve `2**n` cuando el tamaño excede
`n` o es negativo; se conserva esa peculiaridad. Los costes explícitos `cost/2` se suman y
reemplazan al coste sintáctico; los dominios añadidos por `strict_types` no
cuentan. Son comportamientos contrastados, no estimaciones de longitud.

Están implementadas todas las ramas y opciones de generación estática
identificadas en la compilación inspeccionada. El alcance es **generación de candidatos**:
no se han reconstruido la búsqueda óptima, los conflictos o la ejecución de
PyLASP. El README explicita límites de grounding y del parser, y rechaza
expansiones de metarules que perderían dependencias del programa completo.

### Extracción inicial del ASP

**El generador ASP se puede extraer y ejecutar de forma independiente.** Para
`benchmarks/ilasp/coin.las`, el encoding extraído produce exactamente las mismas
59 cláusulas con sus costes que `ILASP -s`, normalizando únicamente el orden de
literales del cuerpo mediante el AST de Clingo. No faltan ni sobran cláusulas.

El código está disponible directamente en
[tools/ilasp/recovered/](../tools/ilasp/recovered/README.md):
[metaprograma común](../tools/ilasp/recovered/search-space.lp),
[bias compilado de coin](../tools/ilasp/recovered/coin-bias.lp) y
[generador completo de coin](../tools/ilasp/recovered/coin-generator.lp).
El fragmento común coincide byte a byte con el exportado para `grandparent`
usando las mismas opciones. Los `.lp` conservan la salida original de ILASP.

La enumeración independiente con pyclingo 5.8.2 produce 157 modelos completos,
pero solo 59 representaciones visibles distintas. Contar modelos completos sin
deduplicar los átomos mostrados sobreestima aquí el espacio de cláusulas.

Las pruebas leyeron la tarea existente sin modificarla. Este control incluye
reglas normales, constraints y negación por defecto. No demuestra por sí solo
equivalencia para choices, disyunción, condicionales, weak constraints ni otros
bias, ni la corrección global de todos los criterios de poda.

## Opciones reales de ILASP 4.4.1

La compilación local utiliza **`-st`** para imprimir el generador. El comando
histórico `-s -t` emite un aviso en stderr indicando que `-t` está retirado y que
debe usarse `-st`; aun así termina con código 0 e imprime las cláusulas de `-s`.
Por tanto, ni el código de salida ni el manual antiguo bastan para identificar
esa salida como un metaprograma.

El mismo aviso recomienda `ilasp.cdilp.get_current_asp_program()` en PyLASP para
consultar los encodings de búsqueda. Esa llamada no se ha ejercitado en este
análisis. Sí se ha obtenido el script predeterminado con `--version=4 -p`: el
bucle llama a `solve`, busca contraejemplos, analiza conflictos, añade constraints
de cobertura y vuelve a resolver. Para esa configuración aparecen estrategias
`all-ufs`, `single-as` y `single-as-pair`. Esto describe el script emitido, no una
reconstrucción de la implementación C++ de esos métodos.

## Encoding extraído

La salida de `-st` para `coin` ocupa 10 844 bytes. Contiene:

- Declaraciones compiladas `possible_head`, `possible_body`, `at`, `mapping`,
  `recall`, tipos y los límites efectivos de la generación.
- Selección del tipo de regla y límites de cuerpo y longitud. Las ramas de
  choices, disyunción o weak constraints están presentes en el encoding general;
  su presencia textual no significa que el bias concreto las pueda instanciar.
- Seguridad mediante `occurs_pos` y `occurs_non_pos`, y guards que excluyen
  determinadas coincidencias entre cabeza, cuerpo positivo y cuerpo negativo.
- Un primer bloque de saturación que trabaja con mapeos de variables y
  constantes sobre el cuerpo, introducido por el propio ejecutable como un
  mecanismo para evitar reglas equivalentes adicionales.
- Un segundo bloque `saturate2` que compara átomos de cabeza/cuerpo bajo mapeos,
  discrimina colisiones de variables y aplica comparaciones de orden.

La lectura de los dos últimos bloques apunta a reducción de cuerpos redundantes
y de variantes por renombrado, respectivamente. Es una interpretación del ASP
recuperado, pendiente de una demostración de cada criterio para todas las formas
de regla. No autoriza a trasladar esas podas a Gentians sin comprobar su lenguaje,
su coste y sus invariantes no monótonos.

## Análisis nativo y límites de la descompilación

REA identifica `LanguageBias::createSearchSpace` en `0x2527f0` dentro de la
imagen cargada por Ghidra y relaciona esa dirección con el offset de archivo
`0x1527f0`. La entrada `.cold` aparece por separado en `0x196e76`: consultar solo
el nombre resulta ambiguo. Lo mismo sucede con `Task::writeSearchSpace`, cuya
entrada principal está en `0x230da0`.

El ensamblado de la función principal confirma llamadas a `clingo_control_new`,
`clingo_control_add`, `clingo_control_ground`, `Clingo::Control::solve` y lectura
de símbolos de modelos. También muestra construcción de `NafLiteral` y
`BackgroundRule`, inserción en `Task::s_m` y ordenación posterior. Esta evidencia
establece la ruta nativa de enumeración y decodificación, sin atribuir a cada
regla una cobertura independiente del programa candidato completo.

El primer perfil predeterminado de Ghidra marca erróneamente el thunk de
`std::__ostream_insert` como `hasNoReturn=true`. REA lo señala expresamente: el
pseudocódigo de `createSearchSpace` queda truncado antes de las llamadas a Clingo
que sí están en el ensamblado. Por eso ese pseudocódigo inicial no se utiliza
como reconstrucción completa. Se conserva en `07-create-search-space-pseudocode.json`
y en `ilasp-default-analysis.snapshot.json` para inspeccionar la limitación.

La segunda pasada desactiva, mediante la opción soportada
`REA_GHIDRA_DISABLED_ANALYZERS`, los analizadores `Non-Returning Functions -
Discovered` y `Non-Returning Functions - Known`. El perfil resultante conserva
el cuerpo principal de generación: el pseudocódigo pasa de 3 713 a 143 944
caracteres y contiene la ruta completa hasta Clingo y la decodificación. Su
digest es `df4c63197642be560a938c901535efd32903b3514161da135010d1ec1f6fb91b`.
Los flags desactivados y las limitaciones quedan registrados en las respuestas
originales, sin parchear REA, Ghidra ni el binario.

En esa salida se observa la opción **`--project`** de Clingo. Esto concuerda con
que la enumeración independiente sin proyección obtenga 157 modelos pero solo
59 representaciones mostradas. También se recupera
`ModeDeclaration::asp_representation` en `0x244680`: construye las declaraciones
`possible_*`, `recall`, `constraint`, `at` y `mapping` que aparecen en el ASP.
`LanguageBias::setup` delega en `createSearchSpace`; `Task::writeSearchSpace`
recorre después `Task::s_m` e invoca la salida de cada elemento.

La descompilación sigue siendo aproximada: Ghidra advierte que la propagación
de tipos no converge y señala una transferencia terminal a la entrada `.cold`
cuya causa no establece. Los tipos, límites de funciones y llamadas virtuales
requieren contraste con ensamblado. El comparador de ordenación recuperado llama
a un método virtual y compara dos enteros; no se ha identificado aquí ese método
con suficiente certeza como para atribuirle un coste concreto.

## Entorno y evidencias

Se instaló un entorno independiente en WSL Kali Linux x86-64:

- Node.js 24.14.1.
- REA 6.5.0, fijado por versión e instalado con npm fuera del repositorio.
- Ghidra 12.1.4 y Temurin JDK 21.0.12.1+1.

Las herramientas viven en `/home/ulloa/.local/share/gentians-ilasp-re/`. Se
verificaron los SHA-256 publicados de Node, Ghidra y el JDK antes de extraerlos.
`rea doctor --provider ghidra --json` devuelve `healthy: true`, incluido el
decompilador nativo Linux x86-64 y el JDK. Se accede a REA mediante su servidor
stdio; no se modificó la configuración global de MCP ni las dependencias de
Gentians. [Instalación de REA](https://github.com/morluto/rea/blob/main/docs/installation.md).

Las evidencias locales se guardan en `C:\tmp\gentians-ilasp-re\evidence\`:

- `ilasp-probes.json`: comandos exactos, hashes, códigos de salida y tamaños.
- `coin-generator.stdout`: generador ASP original.
- `coin-space.stdout`: las 59 cláusulas y sus costes.
- `coin-old-flags.stderr`: aviso de retirada de `-t`.
- `coin-pylasp4.stdout`: bucle PyLASP emitido por ILASP4.
- `coin-models.json` y `coin-space-validation.json`: enumeración y comparación.
- `rea-doctor.json` y las respuestas originales de REA: diagnóstico y análisis
  nativo, con identidad del artefacto y direcciones cuando las devuelve el motor.
- `create-search-space-recovered.cpp` y `mode-declaration-recovered.cpp`:
  pseudocódigo original de Ghidra, sin corrección manual de sus tipos.
- `ilasp-analysis.snapshot.json`: ocho registros de evidencia de la segunda
  pasada. Su recibo indica cero entradas primitivas y cero workflows cacheados;
  este snapshot no evita una nueva importación al repetir la descompilación.

Los scripts de preparación, captura y comparación están en
`C:\tmp\gentians-ilasp-re\`. Son auxiliares locales de este análisis.

El lanzador `/home/ulloa/.local/share/gentians-ilasp-re/rea` fija las versiones,
las rutas de Java/Ghidra y el perfil de analizadores anterior. Permite seguir
consultando el binario sin añadir dependencias al proyecto.

## Reproducir la extracción y la comparación

En WSL, con el runtime Python 3.10 ya usado por el runner del proyecto:

```bash
export LD_LIBRARY_PATH=/tmp/ilasp-python310/root/usr/lib/x86_64-linux-gnu
export PYTHONHOME=/tmp/ilasp-python310/root/usr
tools/ilasp/ILASP -st benchmarks/ilasp/coin.las > /tmp/coin-generator.lp
tools/ilasp/ILASP -s benchmarks/ilasp/coin.las > /tmp/coin-space.txt
tools/ilasp/ILASP --version=4 -p benchmarks/ilasp/coin.las > /tmp/coin-pylasp.py
```

Para repetir el control exacto con los auxiliares conservados, desde PowerShell
en la raíz del repositorio:

```powershell
wsl -d kali-linux -- python3 /mnt/c/tmp/gentians-ilasp-re/probe-ilasp.py
uv run python -m clingo C:\tmp\gentians-ilasp-re\evidence\coin-generator.stdout 0 --outf=2 > C:\tmp\gentians-ilasp-re\evidence\coin-models.json
uv run python C:\tmp\gentians-ilasp-re\compare-space.py
```

El decoder del control es deliberadamente limitado a las formas observadas en
`coin` y rechaza otras mediante assertions. La comparación usa el parser/AST de
Clingo; no interpreta coincidencia en ejemplos como equivalencia de programas.

Para repetir las consultas nativas, conservadas en `native-requests.json`:

```powershell
wsl -d kali-linux -- python3 /mnt/c/tmp/gentians-ilasp-re/rea-client.py /mnt/c/tmp/gentians-ilasp-re/native-requests.json
```

Ese comando importa y analiza de nuevo el binario y puede tardar varios minutos.
Para consultar los resultados ya obtenidos, basta leer los `.cpp` y las
respuestas JSON originales del directorio de evidencias.

## Hechos documentados

El manual antiguo documenta **`-s -t`** para imprimir la definición ASP del
espacio de hipótesis, incluida la representación de los modes. La sustitución
local por `-st` está comprobada arriba. Si hay alguna declaración mode, ILASP incorpora un
programa ASP predeterminado; `#bias` permite ampliarlo con reglas o constraints.
`--override-default-sm` desactiva esa interpretación predeterminada y conserva la
representación de modes y el ASP aportado por `#bias`.
[Definición ASP del espacio](https://doc.ilasp.com/specification/meta_asp_hypothesis_space.html).

Las salidas tienen propósitos distintos:

- `-s` o `--search-space`: cláusulas generadas a partir del mode bias.
- `-t` o `--task-program`, usado solo: representación ASP de la tarea que utiliza
  ILASP2. No debe identificarse con el generador que imprime `-s -t`.
- `-p`: script PyLASP correspondiente a la configuración elegida.
- `--debug` o `-d`: hipótesis intermedias e información adicional en ILASP2i/3/4.

[Parámetros oficiales](https://doc.ilasp.com/parameters.html).

El contrato público del generador asigna cada answer set a una cláusula:
`head/1` y `body/1` representan reglas normales y constraints; `naf/1` codifica
negación por defecto y `var__/1`, variables. `in_head/1` con `lb/1` y `ub/1`
representa choice rules. También se documentan disyunción, weak constraints y
literales condicionales. Este formato permite relacionar el encoding recuperado
con las cláusulas impresas.
[Representación y decodificación](https://doc.ilasp.com/specification/meta_asp_hypothesis_space.html).

Los modes restringen posiciones de cabeza/cuerpo, tipos, constantes, recall y
número de variables. Las opciones `positive`, `anti_reflexive` y `symmetric`
restringen negación por defecto, argumentos repetidos y variantes simétricas,
respectivamente. El manual declara que se omiten reglas que no pueden aparecer
en una solución óptima; ilustra la eliminación de
`p :- q(V1), q(V2).` frente a `p :- q(V1).`. Esto no especifica todos los criterios
internos de poda ni autoriza a deducir equivalencia a partir de los ejemplos.
[Mode declarations](https://doc.ilasp.com/specification/mode_declarations.html).

Existe además una entrada explícita `longitud ~ regla`, útil como control para
separar generación y búsqueda.
[Espacio explícito](https://doc.ilasp.com/specification/explicit_hypothesis_space.html).

## Límites de la investigación

El corpus no constituye una prueba universal para toda combinación de ASP y
Python arbitrarios. Grounding infinito, scripts que no terminan y salidas
nativas que son ASP inválido se distinguen de una enumeración válida terminada.
El contrato detalla esos casos y la expansión opcional de metarules acopladas.

Reproducir el ASP de poda no demuestra que todos sus criterios conserven
hipótesis óptimas; esa sería una investigación semántica adicional sobre el
learner. Tampoco se reconstruyeron todos los tipos y llamadas virtuales de
C++. Las conclusiones de compatibilidad se apoyan en reglas/costes observados,
en el encoding literal y en los probes diferenciadores de cada rama.

## Disponibilidad y límites de las fuentes

El [repositorio oficial de releases](https://github.com/ilaspltd/ILASP-releases)
consultado distribuye ILASP y remite al manual; no se ha recuperado de él una
implementación C++ del generador. Sí hay una representación ASP públicamente
inspeccionable mediante la opción local `-st`. Esa salida es un artefacto del ejecutable: no
equivale al código fuente original.

La [referencia oficial de PyLASP](https://ilasp.com/PyLASP) presenta la extensión
Python como mecanismo de personalización y confirma el uso de `-p`; su descarga
completa agotó el tiempo de espera durante esta consulta. No se atribuyen aquí a
PyLASP capacidades adicionales a las observadas en el script local. Las pruebas
anteriores ejecutan ILASP para inspección; no ejecutan campañas de benchmarks.

## Verificación y cadenas del repositorio

Las cadenas afectadas son **lenguaje/generación de la herramienta independiente**
y **documentación**: lector, compilación, encoding recuperado, decoder, CLI y
tests diferenciales cambian juntos. No se cambian lexer, parser, IR, modes, metaprograma,
`HypothesisGenerator`, algoritmos, estrategias, evaluación ni dashboard de
Gentians. No se modificaron tareas inductivas ni resultados de benchmarks.
Los `.lp` de `tools/ilasp/recovered/` son artefactos de esta inspección y no están
conectados al generador de Gentians.

Las pruebas comparan reglas y costes completos, no solo presencia o tamaños.
Se ejecutaron los 307 tests propios de esta herramienta, Ruff y ty. No se
ejecutó la suite completa de Gentians: su código de producción, algoritmos,
estrategias, cobertura, métricas y dashboard no cambian. No aplica la cadena de
medición de rendimiento ni se modifican sus charts.
