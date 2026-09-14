# Panorama de capacidades ILP relevantes para Gentians

Estado de la investigación: 2026-09-13. Esta nota separa semántica, lenguaje
aprendible, sesgo y algoritmo. Las capacidades atribuidas a sistemas externos
describen las versiones de los artículos o manuales citados; no garantizan el
comportamiento de una versión posterior sin consultar su documentación.

## Resumen ejecutivo

CDILP, MIL, aprendizaje desde interpretaciones parciales, invención de
predicados y recursión no son opciones mutuamente excluyentes:

- **La semántica inductiva** decide qué significa cubrir un ejemplo: entailment
  clásico, existencia de un stable model (*brave*), universalidad sobre stable
  models (*cautious*) o preferencia entre stable models.
- **El lenguaje de hipótesis** decide qué puede aprenderse: cláusulas definidas,
  reglas normales con negación por defecto, disyunciones, choice rules,
  constraints, weak constraints, aggregates o predicados auxiliares.
- **El sesgo inductivo** delimita ese lenguaje: modes, tipos, direcciones,
  recalls, metarules, límites estructurales y restricciones sobre programas.
- **El objetivo** decide qué solución se prefiere: consistencia perfecta,
  tamaño mínimo, coste de ejemplos no cubiertos, MDL o una función de dominio.
- **El algoritmo** decide cómo se recorre el espacio: meta-encoding ASP,
  búsqueda iterativa, CDILP, subconjunto suficiente de FastLAS, learning from
  failures, meta-interpretación, abducción o búsqueda evolutiva.

Gentians ocupa una combinación poco habitual: aprende programas ASP expresivos,
los evalúa completos bajo stable-model semantics y usa búsqueda evolutiva sobre
un `ClauseSpace` finito. Ya tiene interpretaciones parciales contextuales,
cobertura brave, constraints, negación fuerte y por defecto, aggregates,
recursión declarada e invención prescriptiva. No implementa CDILP, MIL,
ordering examples, aprendizaje de weak constraints ni penalizaciones por
ejemplo. Estas ausencias no son sinónimos de “ILP incompleto”: son puntos
distintos del espacio de diseño.

## 1. Cinco ejes que conviene no mezclar

| Eje | Pregunta | Opciones representativas |
| --- | --- | --- |
| Semántica del ejemplo | ¿Cuándo cubre `B ∪ H` un ejemplo? | Entailment; brave; cautious; orden entre stable models |
| Lenguaje objetivo | ¿Qué forma puede tener `H`? | Horn/definite; normal ASP; choice/disjunction; hard/weak constraints; aggregates |
| Sesgo | ¿Qué hipótesis son legales? | Modes; tipos/direcciones; metarules; restricciones de hipótesis; límites |
| Objetivo | ¿Qué hipótesis gana? | Perfecta; mínima; penalizada; MDL; score de dominio |
| Algoritmo | ¿Cómo se busca? | MIL; XHAIL; meta-level ASP; CDILP; FastLAS; LFF/Popper; GA |

Dos consecuencias prácticas:

1. Adoptar CDILP no concede automáticamente recursión ni invención de
   predicados. CDILP necesita un lenguaje de hipótesis y una relación de
   cobertura ya definidos.
2. Añadir metarules no equivale a “mejorar el buscador”. Cambia el sesgo y, con
   él, las unidades que se enumeran y la forma de expresar invención.

## 2. Interpretaciones parciales y stable-model semantics

### 2.1 Definición

Una interpretación parcial es un par `e = <I, E>` de átomos ground incluidos y
excluidos. Un stable model `A` la extiende cuando `I ⊆ A` y `E ∩ A = ∅`.

En Learning from Answer Sets (LAS):

- un ejemplo positivo se cubre si **existe** un stable model que lo extiende;
  es una condición brave;
- un ejemplo negativo se satisface si **ningún** stable model lo extiende;
  es una prohibición universal y permite expresar propiedades cautious.

Ésta es la definición publicada por
[ILASP para partial interpretations](https://doc.ilasp.com/specification/cdpis.html)
y procede del marco LAS de
[Law, Russo y Broda, 2014](https://doi.org/10.1007/978-3-319-11558-0_22).
No debe confundirse “ejemplo negativo” con “átomo que debe ser falso”: tanto
positivos como negativos contienen conjuntos de inclusiones y exclusiones.

Ejemplos conceptuales:

```prolog
% Algún stable model contiene p.
#pos({p}, {}).

% Ningún stable model contiene q.
#neg({q}, {}).

% Todo stable model contiene r: se prohíbe un modelo que excluya r.
#neg({}, {r}).
```

Esto muestra una sutileza importante: brave y cautious no tienen por qué ser
dos switches del solver. Una condición cautious puede formularse como ausencia
de un contraejemplo mediante una interpretación parcial negativa. Si el programa
no tiene stable models, la prohibición se cumple de forma vacía; cuando importa
la existencia de un modelo debe añadirse también una exigencia positiva.

### 2.2 Contextos

Una context-dependent partial interpretation añade un programa `C_e` específico
del ejemplo. La cobertura se calcula sobre `B ∪ H ∪ C_e`, no sobre un background
global adulterado con todos los contextos. ILASP2i explota esta estructura para
procesar tareas con muchos ejemplos sin construir desde el principio una única
representación monolítica; el artículo informa mejoras de hasta dos órdenes de
magnitud frente a ILASP2 en sus experimentos, manteniendo el marco semántico
([Law, Russo y Broda, 2016](https://arxiv.org/abs/1608.01946)).

Los contextos sirven para representar distintas instancias con una sola teoría:
grafos distintos, escenas distintas o episodios distintos. Son una propiedad
del dato inductivo, no una estrategia de búsqueda.

### 2.3 Ordering examples

Las interpretaciones parciales dicen qué stable models deben existir o no.
No pueden identificar una weak constraint solo por su efecto, porque una weak
constraint ordena modelos sin cambiar cuáles son stable models. Learning from
Ordered Answer Sets (LOAS) añade pares de ejemplos y una relación de preferencia
([Law, Russo y Broda, 2015](https://arxiv.org/abs/1507.06566)).

- **Brave ordering:** existe al menos un par de stable models compatibles con
  los ejemplos que respeta el orden.
- **Cautious ordering:** todos los pares compatibles respetan el orden.

ILASP documenta operadores `<`, `>`, `<=`, `>=`, `=` y `!=`, junto con ambas
cuantificaciones ([manual de ordering examples](https://doc.ilasp.com/specification/cdoes.html)).
Éste es un canal de supervisión distinto de `#pos/#neg`; añadirlo exige
representar preferencias y aprender weak constraints, no cambiar únicamente
`--enum-mode` de Clingo.

## 3. No monotonía y expresividad ASP

### 3.1 Negación por defecto frente a negación fuerte

`not p(X)` es negación por defecto: depende de que `p(X)` no sea derivable en
el stable model considerado. `-p(X)` es negación fuerte o clásica: es un literal
con signo explícito. Las dos pueden combinarse (`not -p(X)`) y no son
intercambiables. La semántica estable hace que añadir una regla pueda crear o
eliminar stable models; por ello la contribución de una cláusula no es, en
general, aditiva ni estable fuera del programa completo.

XHAIL fue una transición temprana importante desde ILP Horn hacia aprendizaje
no monótono: extiende HAIL mediante razonamiento abductivo para aprender
programas normales con negation as failure
([Ray, 2009](https://doi.org/10.1016/j.jal.2008.10.007)). ILASP amplía el objetivo
a normal rules, choice rules y hard/weak constraints
([visión del sistema ILASP](https://arxiv.org/abs/2005.00904)).

### 3.2 Hard constraints, choice/disjunction y aggregates

- Una **integrity constraint** elimina stable models. Puede impedir un ejemplo
  negativo, pero también destruir el único testigo brave de un positivo.
- Una **choice rule** expresa alternativas no deterministas; una cabeza
  disyuntiva tiene semántica distinta aunque ambas puedan producir varios
  stable models.
- Una **weak constraint** no elimina modelos: establece costes y preferencias.
- Un **aggregate** (`#count`, `#sum`, etc.) es un constructor del lenguaje
  objeto ASP. Poder usar aggregates al enumerar cláusulas no implica aprender
  funciones de preferencia ni objetivos de optimización.

La sintaxis y semántica normativa de reglas, negación fuerte, aggregates y weak
constraints está en
[ASP-Core-2](https://arxiv.org/abs/1911.04326); la guía oficial de
[Potassco/clingo](https://potassco.org/guide/) cubre la implementación práctica.

Estas formas aumentan expresividad y combinatoria. Deben habilitarse mediante un
language bias finito y pruebas semánticas; no son casillas inocuas de rendimiento.

## 4. Recursión

Una hipótesis es recursiva cuando existe un ciclo en el grafo de dependencias
entre predicados definidos. La autorrecursión directa es solo el caso más simple;
también existe recursión mutua. Normalmente hacen falta:

- una regla base;
- una regla inductiva;
- condiciones de tipado, connectedness y orden que eviten programas inútiles o
  evaluaciones que no terminan en sistemas Prolog;
- una semántica que defina ciclos positivos y ciclos a través de negación.

Recursión es capacidad del lenguaje, no algoritmo. Metagol la obtiene
instanciando metarules recursivas; Popper genera programas recursivos y aprende
restricciones a partir de fallos; un sistema ASP puede permitir que un
predicado de cabeza aparezca en cuerpos y delegar el significado a stable-model
semantics.

El artículo de Metagol muestra que MIL soporta programas recursivos e invención
mediante sustituciones metalógicas en un meta-intérprete Prolog
([Muggleton et al., 2015](https://doi.org/10.1007/s10994-014-5471-y)). El
artículo original de Popper aprende programas definite recursivos mínimos y
subraya que restricciones como “recursión sin caso base” permiten podar
programas redundantes
([Cropper y Morel, 2021](https://doi.org/10.1007/s10994-020-05934-z)).

En ASP no basta con copiar los criterios operacionales de Prolog. Una recursión
positiva, una estratificada con `not` y un ciclo negativo no tienen la misma
semántica. Cualquier poda debe justificarse sobre el fragmento ASP concreto.

## 5. Predicate invention

Predicate invention (PI) introduce símbolos auxiliares no observados
directamente. Puede:

- factorizar una teoría larga;
- expresar conceptos intermedios que el vocabulario de background no ofrece;
- hacer posible una descomposición recursiva;
- reducir tamaño del programa y, bajo ciertos supuestos, complejidad muestral.

También expande mucho el espacio: hay que decidir número de predicados, aridad,
tipos, dónde pueden aparecer, dependencias y si se permiten ciclos.

Hay dos estilos principales:

1. **Invención guiada por metarules.** Variables de predicado se instancian
   durante la prueba. Metagol es el ejemplo canónico; puede inventar auxiliares
   mientras aprende recursión
   ([Muggleton et al., 2015](https://doi.org/10.1007/s10994-014-5471-y)).
2. **Invención prescriptiva.** El usuario declara de antemano nombre, aridad y
   normalmente tipos del auxiliar; el learner descubre sus cláusulas. Reduce la
   búsqueda, pero no descubre automáticamente cuántos auxiliares hacen falta.

PI tampoco implica MIL. Puede incorporarse a búsqueda por restricciones. El
trabajo posterior *Predicate Invention by Learning From Failures* formula PI
dentro de LFF ([Cropper et al., 2021](https://arxiv.org/abs/2104.14426)).

Conviene evaluar PI por capacidad y coste, no como una bandera siempre positiva.
Un auxiliar puede mejorar compacidad, pero también producir renombrados
simétricos y programas semánticamente equivalentes que multiplican la búsqueda.

## 6. MIL y metarules

Meta-Interpretive Learning (MIL) usa un meta-intérprete y metarules: plantillas
de segundo orden que restringen la forma de las cláusulas. Por ejemplo, una
metarule `chain` representa esquemáticamente:

```text
P(A,B) :- Q(A,C), R(C,B).
```

El learner busca sustituciones para `P`, `Q` y `R`, no combinaciones arbitrarias
de literales. Esto aporta un sesgo estructural fuerte, reutilizable y adecuado
para recursión e invención. A cambio:

- el éxito depende críticamente de que las metarules correctas estén presentes;
- el fragmento clásico de Metagol es definite/Datalog ejecutado con Prolog, no
  programas ASP generales con varios stable models;
- equivalencias, ordenamientos y terminación se razonan en el marco MIL, no se
  transfieren automáticamente a negación no estratificada, choice rules o
  aggregates ASP.

Metagol representa hipótesis como sustituciones de variables existenciales de
metarules y usa un meta-intérprete modificado para probar ejemplos
([artículo primario](https://doi.org/10.1007/s10994-014-5471-y),
[repositorio oficial](https://github.com/metagol/metagol)). ILASP ofrece una
simulación experimental de metarules mediante reglas meta-nivel, `#predicate`
y `#modem`, y advierte que puede ser menos eficiente que un espacio equivalente
definido explícitamente
([documentación oficial](https://doc.ilasp.com/specification/metarules.html)).

Por tanto, “añadir MIL” a Gentians no sería reutilizar su directiva de invención.
Supondría otra representación del bias, enumeración de sustituciones de segundo
orden y reglas claras para traducirlas al fragmento ASP admitido.

## 7. CDILP: aprendizaje inductivo guiado por conflictos

Conflict-driven ILP generaliza la idea de aprender restricciones a partir de
un candidato fallido:

1. se busca una hipótesis óptima respecto a las restricciones acumuladas;
2. se comprueba su cobertura real;
3. si falla un ejemplo, el análisis produce una **coverage constraint** que
   explica una familia de hipótesis con el mismo defecto;
4. la restricción se añade y la búsqueda continúa.

La ganancia no proviene de evaluar una cláusula aisladamente, sino de excluir
regiones del espacio de hipótesis con una condición válida. ILASP3 e ILASP4 son
instancias de CDILP. El trabajo formal compara distintas formas de traducir y
propagar conflictos e informa mejor escalabilidad que versiones ILASP previas,
especialmente con ruido
([Law, 2023](https://doi.org/10.1017/S1471068422000011)). ILASP3 traduce cada
ejemplo a una condición precisa, potencialmente grande, y lo procesa como
máximo una vez; ILASP4 aprende condiciones más pequeñas y generales, pero puede
revisitar ejemplos. La propagación puede compartir una condición entre ejemplos
que fallan por el mismo motivo.

CDILP y CDCL no son lo mismo. CDCL aprende cláusulas durante una resolución SAT;
CDILP usa esa inspiración en un bucle inductivo cuyo conflicto es “esta
hipótesis no cubre este ejemplo”. Clingo puede hacer CDCL internamente mientras
el learner exterior sigue siendo un GA sin CDILP.

La condición difícil para Gentians sería obtener restricciones generalizables
y correctas bajo su fragmento completo: default negation, disjunction, choice,
aggregates y contexts. Una caché de `Genome -> EvaluationResult`, una firma de
cobertura o descartar duplicados no constituye CDILP.

## 8. Ruido, scoring y optimalidad

Hay tres problemas diferentes:

- **Datos duros:** toda interpretación parcial debe satisfacerse.
- **Datos blandos/ruidosos:** puede incumplirse un ejemplo pagando una
  penalización.
- **Búsqueda aproximada:** el learner puede detenerse sin demostrar optimalidad,
  aunque los ejemplos sigan siendo duros en la definición de solución.

ILASP permite asignar a cada ejemplo una penalización positiva y minimiza
`|H| + coste de ejemplos no cubiertos`; ausencia de penalización significa coste
infinito
([manual de ruido](https://doc.ilasp.com/specification/noise.html)). ILASP3
formaliza esta extensión para partial interpretations y ordering examples
([Law, Russo y Broda, 2018](https://arxiv.org/abs/1808.08441)).

FastLAS generaliza el criterio con scoring functions de dominio y construye un
subconjunto `OPT`-sufficient del espacio que conserva al menos una solución
óptima bajo sus supuestos. La versión FastLAS del artículo se restringe a
Observational Predicate Learning —los predicados aprendidos se observan
directamente en ejemplos—, scoring descomponible y no soporta recursión ni PI
([Law et al., 2020](https://doi.org/10.1609/aaai.v34i03.5678)). El trabajo
FastNonOPL posterior levanta la restricción observacional para una clase más
amplia mediante generación abductiva de posibilidades; sigue sin convertir ese
aprendizaje indirecto en invención automática de nuevos símbolos
([Law et al., 2021](https://doi.org/10.24963/ijcai.2021/267)).

Popper 2021 buscaba programas definite textualmente mínimos y no soportaba
ruido ni PI en la versión evaluada. Su repositorio actual documenta un modo
`--noisy` con objetivo MDL; esto ilustra por qué hay que fechar cada comparación
([artículo](https://doi.org/10.1007/s10994-020-05934-z),
[repositorio oficial](https://github.com/logic-and-learning-lab/Popper)).

Un score continuo de cobertura puede guiar un GA sin convertir ejemplos en
blandos: la condición de solución puede seguir exigiendo todos los positivos y
ningún negativo. Tampoco ofrece una prueba de optimalidad.

## 9. Familias de algoritmos y sistemas

| Sistema/familia | Semántica y lenguaje en la fuente citada | Búsqueda | Fortaleza principal | Límite que importa aquí |
| --- | --- | --- | --- | --- |
| XHAIL | Programas normales, NAF; ejemplos positivos/negativos | Abducción, saturación/generalización y selección | ILP no monótono temprano; Event Calculus | Menor alcance ASP que ILASP moderno; no es MIL ni CDILP |
| ILASP1/2/2i | LAS/LOAS; normal, choice, hard y weak constraints | Meta-level ASP; ILASP2i procesa contextos iterativamente | Semántica ASP expresiva; garantías de optimalidad del marco | Meta-encoding puede crecer mucho |
| ILASP3/4 | LAS ruidoso y LOAS; lenguaje ILASP | CDILP: hipótesis, comprobación, coverage constraints | Conflictos podan familias; bueno con muchos/noisy examples | Requiere análisis de conflicto correcto por tipo de ejemplo |
| FastLAS (AAAI 2020) | ASP con NAF; OPL y scoring restringido | Construye subconjunto `OPT`-sufficient y optimiza | Escala con espacios grandes; scoring de dominio | En esa versión: sin recursión ni PI; no LAS general multi-modelo |
| Metagol/MIL | Programas definite guiados por metarules | Prueba meta-interpretativa y metasustituciones | Recursión, PI, pocos ejemplos, fuerte sesgo estructural | No equivale a aprender ASP general no monótono |
| Popper/LFF | Principalmente programas definite; recursión | Generate/test/constrain; aprende restricciones de fallos | Programas mínimos, dominios potencialmente infinitos | Artículo 2021 sin PI/ruido; semántica Prolog distinta de ASP |
| Gentians actual | Programa ASP candidato completo; partial interpretations contextuales | Enumeración ASP de cláusulas + GA steady-state o incremental | Lenguaje ASP amplio y búsqueda anytime | Heurístico: sin prueba de completitud/optimalidad del resultado |

Fuentes principales de la tabla: XHAIL
([Ray 2009](https://doi.org/10.1016/j.jal.2008.10.007)); ILASP y evolución de
versiones ([Law et al. 2020](https://arxiv.org/abs/2005.00904)); CDILP
([Law 2021](https://arxiv.org/abs/2101.00058)); FastLAS
([Law et al. 2020](https://doi.org/10.1609/aaai.v34i03.5678)); Metagol
([Muggleton et al. 2015](https://doi.org/10.1007/s10994-014-5471-y)); Popper
([Cropper y Morel 2021](https://doi.org/10.1007/s10994-020-05934-z)).

## 10. Qué soporta Gentians hoy

Esta sección se basa en contratos y código del repositorio, no en analogías con
otros sistemas.

| Dimensión | Estado | Evidencia local y matiz |
| --- | --- | --- |
| Partial interpretations | Sí | `#pos/#neg` con incluidos y excluidos; [README](../README.md#examples-definition) y [`Example`](../gentians/language/ir/example.py) |
| Context-dependent examples | Sí | Tercer campo ASP aislado por selector; [`compiler.py`](../gentians/evaluation/compiler.py) |
| Cobertura brave | Sí | Se fuerza enumeración brave y se unen máscaras de todos los modelos; [`evaluation/__init__.py`](../gentians/evaluation/__init__.py), [`solver.py`](../gentians/evaluation/solver.py) |
| Propiedades cautious | Parcial, vía negativos | `#neg({}, {p})` prohíbe todo contraejemplo sin `p`; no hay tipo separado de ejemplo cautious |
| Ordering examples / preferencias | No | Grammar solo declara `#pos/#neg`; [`grammar.py`](../gentians/language/grammar.py) |
| Weak constraints aprendibles | No | No hay modo de hipótesis ni ordering examples; weak constraints se rechazan en contextos; [README](../README.md#examples-definition) |
| Default y strong negation | Sí | Formas independientes; [language bias](language-bias.md#conditional-literals) |
| Hard constraints | Sí | Cabeza vacía legal bajo límites y pruning documentado; [language bias](language-bias.md#positive-only-constraint-pruning) |
| Choice/cardinality heads | Sí | `#modeh` completo y combinación `#modeha`; [language bias](language-bias.md#aggregate-head-modes) |
| Disjunctive heads | Sí | `#modehd`; [language bias](language-bias.md#disjunctive-head-modes) |
| Body aggregates | Sí | Templates aggregate exactos en `#modeb`; [README](../README.md#aggregates-in-language-bias) |
| Arithmetic/comparisons/conditionals | Sí | Relaciones exactas en `#modeb` y condiciones opcionales con `#modec`; [language bias](language-bias.md#conditional-literals) |
| Recursión | Sí, explícita | Se activa cuando un predicado permitido en cabeza aparece en body/condition positivo; [`task_analysis.py`](../gentians/clauses/task_analysis.py) |
| Predicate invention | Sí, prescriptiva | `#invent(recall, template)` crea modo de cabeza y body positivo; el símbolo, aridad, tipos y direcciones los declara el usuario; [language bias](language-bias.md#predicate-invention) |
| Ciclos entre inventados | No | Las dependencias inventadas se ordenan por declaración para impedir ciclos; tests en [`test_clause_space.py`](../tests/test_clause_space.py) |
| MIL/metarules | No | `#metarule`, `#predicate` y `#modem` se retiraron y se rechazan; [language bias](language-bias.md#removed-meta-programming-directives) |
| CDILP | No | Los bucles implementados son GA steady-state e incremental; [`algorithms/`](../gentians/algorithms/) |
| LFF/Popper | No | No existe bucle generate-test-constrain que derive restricciones de generalización/especialización desde fallos |
| Noise penalties | No | Ejemplos no tienen ID/peso; [`Example`](../gentians/language/ir/example.py) |
| Score | Uno, heurístico | `cov_program = exp(10·(TPR−FPR))` cuando hay ambas clases; [`scoring.py`](../gentians/evaluation/scoring.py) |
| Solución perfecta | Sí | Todos los positivos cubiertos y ningún negativo cubierto; [`evaluator.py`](../gentians/evaluation/evaluator.py) |
| Garantía de óptimo global | No | El GA devuelve mejor encontrado al hallar solución, agotar generaciones o presupuesto; no certifica mínima longitud |

### Lectura precisa de la cobertura actual

Gentians crea un `clingo.Control` nuevo para cada evaluación no heredada, añade
background, programa de cobertura y **programa candidato completo**, y acumula
`extended_p/1` y `extended_n/1` sobre modelos brave. La cobertura de una cláusula
aislada no se usa como fitness. Esto preserva el rasgo esencial de ASP: añadir
una regla o constraint puede cambiar el conjunto completo de stable models.

Con positivos `P`, negativos `N`, positivos cubiertos `cp` y negativos cubiertos
`cn`, el score actual es:

```text
exp(10 · (cp/|P| - cn/|N|))
```

cuando ambas clases existen; usa solo el término disponible si una clase está
vacía. El score no penaliza tamaño de hipótesis y todos los ejemplos tienen el
mismo peso. Un candidato puede lograr buen score sin ser solución; `best_found`
solo corresponde a cobertura positiva completa y cero cobertura negativa.

### Lectura precisa de invención y recursión

`#invent` no descubre un símbolo ni una metarule. Declara un auxiliar concreto y
genera permisos de cabeza/body tipados. Además, Gentians exige cierre de
dependencias del programa candidato: todo predicado requerido debe venir del
background o estar definido por otra cláusula del mismo candidato. Esto es más
fuerte que seleccionar bits arbitrarios, pero no es prueba meta-interpretativa.

La recursión de predicados declarados se permite por el language bias. Los
inventados, en cambio, siguen un orden acíclico. Por ello “soporta recursión” y
“no permite ciclos de invención” son afirmaciones compatibles.

## 11. Opciones de evolución razonables para Gentians

### A. Penalizaciones por ejemplo: extensión pequeña en concepto, transversal en contrato

Añadir pesos a `#pos/#neg` sería la ampliación más próxima al diseño actual:
mantendría partial interpretations y el solver de cobertura. Aun así exige
cambiar grammar, `Example`, score, condición de solución, métricas, docs y tests.
Debe decidirse si un ejemplo finito puede incumplirse y qué significa
`best_found`; no basta con cambiar la fórmula numérica.

Valor: datos reales con etiquetas imperfectas o prioridades distintas. Riesgo:
confundir “mejor candidato del GA” con óptimo penalizado demostrado.

### B. Objetivo de tamaño o MDL: ortogonal al ruido

Puede preferirse cobertura y después menor número de cláusulas/literales, o
combinar ambos costes. Esto no requiere CDILP, pero modifica selección,
comparación de individuos y resultado. Un escalar exponencial con empate por
tamaño y un orden lexicográfico no son equivalentes; el contrato debe escoger.

Valor: programas más interpretables y menor sobreajuste. Riesgo: optimizar
brevedad antes de cobertura o atribuir optimalidad global a una búsqueda
heurística.

### C. CDILP como algoritmo nuevo, no como parche al GA

Un CDILP real encaja como otro algoritmo completo que reutiliza `ClauseSpace`,
`HypothesisGenerator`, `CandidateEvaluator` y `SearchResult`, pero necesita:

- representación de restricciones sobre hipótesis;
- extracción de un conflicto semánticamente válido desde cada fallo;
- un optimizador que encuentre la siguiente hipótesis bajo esas restricciones;
- pruebas de corrección para positivos, negativos, contexts y cada forma ASP.

Valor potencial: poda no local y explicable de grandes familias. Riesgo alto:
una generalización válida para definite clauses puede ser falsa bajo programas
no monótonos. La firma observada `(pos_mask, neg_mask)` no prueba equivalencia
global y por sí sola no genera coverage constraints.

### D. Ordering examples y weak constraints: nueva modalidad de producto

Permitir preferencias requiere IR de pares de ejemplos, semántica brave/cautious
del orden, generación de weak constraints y comparación por niveles/pesos ASP.
No es una extensión de aggregates ni del score del GA.

Valor: preference learning y políticas de optimización. Coste: toda la cadena de
lenguaje, generación, evaluación y documentación. Solo compensa si existen casos
de uso concretos que necesiten aprender preferencias, no meramente clasificar.

### E. MIL/metarules: mantener como algoritmo/lenguaje alternativo

Reintroducir `#metarule/#predicate/#modem` únicamente por compatibilidad añadiría
dos biases solapados y mucha combinatoria. Si se desea MIL, conviene definir
primero el fragmento objetivo: definite/Datalog sería mucho más viable que
metarules arbitrarias sobre todo ASP. Su unidad natural es la metasustitución o
un bundle de cláusulas, mientras Gentians selecciona cláusulas independientes
con cierre; la frontera es arquitectónica.

Valor: tareas de síntesis composicional con fuerte sesgo y pocos ejemplos.
Riesgo: hacer el lenguaje más difícil sin aportar ventajas a tareas ASP
no monótonas actuales.

### F. Ampliar predicate invention

Tres escalones distintos:

1. mantener PI prescriptiva actual;
2. permitir recursión mutua controlada entre inventados;
3. inventar automáticamente número, aridad o tipos de auxiliares.

Cada escalón multiplica simetrías y necesidades de canonicalización. El segundo
requiere semántica y cierre para componentes fuertemente conexas; el tercero se
acerca a MIL o PI por restricciones. No deben agruparse bajo una única opción.

### G. Mantener recursión como propiedad declarativa

El enfoque actual —recursión solo cuando modes lo permiten— es coherente con el
coste combinatorio. Mejoras útiles serían pruning demostrado para reglas base y
ciclos improductivos, nunca prohibiciones copiadas de Prolog sin validar stable
models. Toda optimización necesitaría benchmark reproducible y tests de
presencia/ausencia de cláusulas.

## 12. Priorización

Para el producto descrito hoy:

1. **Documentar como capacidades existentes** partial interpretations
   contextuales, brave coverage, cautious por contraejemplo negativo, recursión
   explícita e invención prescriptiva. No necesitan una nueva etiqueta de
   algoritmo.
2. **Si hay datos imperfectos**, diseñar penalizaciones por ejemplo y el contrato
   de `SearchResult` antes de estudiar CDILP. Es valor de usuario independiente
   del método de búsqueda.
3. **Si el problema real es convergencia**, medir primero GA steady-state e
   incremental. CDILP merece un algoritmo separado solo con una familia de
   coverage constraints correcta para el fragmento ASP objetivo.
4. **Si el caso de uso es preference learning**, abordar juntos ordering
   examples y weak constraints. Uno sin el otro no completa LOAS.
5. **No reintroducir MIL por catálogo de features.** Hacerlo solo para tareas que
   necesitan templates de segundo orden e invención composicional y tras fijar
   un fragmento semántico estrecho.

La dirección técnicamente más importante es conservar la evaluación del
programa candidato completo. Ninguna optimización debe asumir cobertura fija por
cláusula, contribuciones aditivas o equivalencia semántica global derivada solo
de los ejemplos observados.

## Referencias primarias

- Law, M.; Russo, A.; Broda, K. (2014), *Inductive Learning of Answer Set
  Programs*. [DOI](https://doi.org/10.1007/978-3-319-11558-0_22).
- Law, M.; Russo, A.; Broda, K. (2015), *Learning Weak Constraints in Answer Set
  Programming*. [arXiv](https://arxiv.org/abs/1507.06566).
- Law, M.; Russo, A.; Broda, K. (2016), *Iterative Learning of Answer Set
  Programs from Context Dependent Examples*.
  [arXiv](https://arxiv.org/abs/1608.01946).
- Law, M.; Russo, A.; Broda, K. (2018), *Inductive Learning of Answer Set
  Programs from Noisy Examples*. [arXiv](https://arxiv.org/abs/1808.08441).
- Law, M.; Russo, A.; Broda, K. (2020), *The ILASP System for Inductive Learning
  of Answer Set Programs*. [arXiv](https://arxiv.org/abs/2005.00904).
- Law, M. (2023), *Conflict-driven Inductive Logic Programming*.
  [DOI](https://doi.org/10.1017/S1471068422000011) y
  [preprint](https://arxiv.org/abs/2101.00058).
- Law, M. et al. (2020), *FastLAS: Scalable Inductive Logic Programming
  Incorporating Domain-Specific Optimisation Criteria*.
  [DOI](https://doi.org/10.1609/aaai.v34i03.5678).
- Law, M. et al. (2021), *Scalable Non-observational Predicate Learning in ASP*.
  [DOI](https://doi.org/10.24963/ijcai.2021/267).
- Muggleton, S. H. et al. (2015), *Meta-interpretive Learning of Higher-order
  Dyadic Datalog: Predicate Invention Revisited*.
  [DOI](https://doi.org/10.1007/s10994-014-5471-y).
- Cropper, A.; Morel, R. (2021), *Learning Programs by Learning from Failures*.
  [DOI](https://doi.org/10.1007/s10994-020-05934-z).
- Cropper, A. et al. (2021), *Predicate Invention by Learning From Failures*.
  [arXiv](https://arxiv.org/abs/2104.14426).
- Ray, O. (2009), *Nonmonotonic Abductive Inductive Learning*.
  [DOI](https://doi.org/10.1016/j.jal.2008.10.007).
- Calimeri, F. et al. (2020), *ASP-Core-2 Input Language Format*.
  [arXiv](https://arxiv.org/abs/1911.04326).
- [Manual oficial de ILASP](https://doc.ilasp.com/).
- [Guía oficial de Potassco/clingo](https://potassco.org/guide/).
- [Repositorio oficial de Metagol](https://github.com/metagol/metagol).
- [Repositorio oficial de Popper](https://github.com/logic-and-learning-lab/Popper).
- [Repositorio oficial de FastLAS](https://github.com/spike-imperial/FastLAS).
