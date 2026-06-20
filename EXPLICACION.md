# Explicacion del diseno actual y alternativa propuesta

Este documento resume la conversacion sobre el flujo de GENTIANS: stubs, variable placement, espacio de hipotesis, algoritmo genetico, fitness, ejemplos, language bias y una alternativa mas coherente.

## Resumen corto

La intuicion principal: el sistema mezcla dos ideas distintas.

- En un GA clasico, un individuo deberia ser un programa candidato.
- En este codigo, un individuo funciona mas como una bolsa de reglas, porque el fitness evalua muchos subconjuntos internos del individuo.

Eso hace el algoritmo caro, poco interpretable y con senal evolutiva confusa.

La forma mas limpia seria:

```text
task + bias
-> generar stubs una vez o incrementalmente con memoria
-> pruning temprano
-> variable placement una vez por stub
-> pruning temprano de reglas
-> pool de reglas candidatas
-> buscar programas como subconjuntos de ese pool
```

La busqueda final puede ser GA, pero probablemente encaja mejor un beam search o branch-and-bound.

## Flujo actual

El flujo principal esta en `gentians.py`:

```text
for it in range(arguments.iterations):
  sample stubs
  add best stubs from previous round
  variable placement
  build placed_list
  run genetic_solver
```

Eso significa:

- Stubs + variable placement se hacen una vez dentro de cada ronda externa.
- El GA no vuelve a hacer variable placement.
- Entre rondas externas se resamplean stubs y se rehace variable placement.
- `VariablePlacer` vive fuera del loop y mantiene cache, pero aun asi el diseno es basicamente reinicios aleatorios caros con poca memoria.

Con defaults:

```text
iterations = 100
clauses_to_sample = 1000
population_size = 50
iterations_genetic = 2000
clauses_per_individual = 6
```

## Stubs y variable placement

Un stub es una regla con huecos de variables, por ejemplo:

```prolog
target(_____) :- edge(_____,_____), color(_____).
```

Variable placement rellena esos huecos:

```prolog
target(V0) :- edge(V0,V1), color(V1).
target(V0) :- edge(V1,V0), color(V1).
...
```

La idea de usar ASP/Clingo para variable placement es buena. Las restricciones de seguridad, igualdad, agregados, comparaciones y aritmetica encajan bien en ASP.

Lo flojo es generar mucho y filtrar tarde. Mejor meter mas restricciones en el propio ASP de placement.

## Fitness actual

`evaluate_score` es el fitness.

Pero no evalua solo el programa completo. Hace esto:

```text
individuo = [r1, r2, r3, ...]
Clingo activa/desactiva reglas con {r(i)}
se calculan coberturas para muchos subconjuntos internos
Python calcula score para cada subconjunto
fitness del individuo = media de scores de subconjuntos
```

O sea:

```text
1 individuo -> 1 llamada Clingo -> muchos answer sets -> coverage de muchos subsets -> fitness medio
```

Esto no es una llamada por regla. Es una llamada por individuo, pero potencialmente enumera hasta `2^n` subconjuntos del individuo.

Problema conceptual:

- Si el individuo ya es un subconjunto de reglas del universo, evaluar sus sub-subconjuntos parece redundante.
- El GA ya deberia buscar subconjuntos del universo.
- Evaluar subconjuntos internos convierte el individuo en una bolsa de reglas, no en un programa candidato.

## Por que esto es ineficiente

Coste aproximado:

```text
individuos * generaciones * 2^reglas_por_individuo * coste_ASP
```

Ademas:

- Cada individuo nuevo crea `clingo.Control`, hace `add`, `ground`, `solve`.
- Crossover evalua dos hijos.
- Mutation puede evaluar dos mas.
- Muchos programas/subconjuntos se repiten, pero el diseno no reutiliza esa informacion de forma estructural.

ASP proposicional ya puede ser NP-completo para existencia de answer set. Aqui hay busqueda combinatoria encima del solver.

## Cafradas principales en GA

### Individuo mal definido

El individuo deberia ser el programa candidato. Aqui se comporta como pool local de reglas.

### Fitness por subconjuntos

El fitness mezcla calidad de muchos subconjuntos. Un individuo puede parecer bueno porque contiene una regla o subset bueno, aunque el programa completo sea malo.

### Crossover con indices desalineados

En `initialize_population`, `program` se ordena:

```python
program = sorted(program)
```

Pero `stub_indexes` y `prog_indexes` no se reordenan igual. Luego crossover y mutation asumen que esos indices siguen alineados con `program`.

Eso es un bug conceptual grande.

### Mutation modifica el objeto original

En `mutate`:

```python
new_element = element
```

Eso no copia. Mutar el hijo modifica el mismo objeto recibido.

### Rama de mutation muerta

`change_stub` se recibe como argumento, pero dentro se fuerza:

```python
change_stub = True
```

La rama de "cambiar solo placement" queda muerta.

### Tournament fragil

`random.sample(population, tournament_size)` rompe si `population_size < tournament_size`.

### Crossover puede no mezclar

`crossover_position` puede ser 0. Entonces los hijos pueden ser copias sin mezcla real.

Con un individuo de una sola regla, crossover no sirve.

### Final de ronda fragil

Al final se recorren los mejores con:

```python
for i in range(1, k_best_for_the_next_round + 1):
```

Eso salta `population[0]`, que es el mejor, y puede ir fuera de rango.

## Cafradas en coverage y ejemplos

### `#neg` parseado con regex de `#pos`

`_get_pos_neg_examples` busca `#pos(...)`, pero se usa tambien para `#neg(...)`. Eso puede romper parsing de negativos desde archivo.

### Parser limitado

No soporta bien:

- ejemplos multilinea;
- `#pos(id,{...},{...})`;
- `#neg(id,{...},{...})`;
- arities o recalls de varios digitos en mode declarations.

### Contexto mal manejado

El contexto de ejemplos se anade solo dentro del bloque donde existe `excluded`. Si un ejemplo tiene contexto sin excluded, se ignora.

Ademas, el contexto se anade como facts globales al mismo programa. Si distintos ejemplos tienen distintos contextos, se contaminan entre si.

### Off-by-one en ejemplos

Se genera:

```prolog
pos_exs(0..len).
neg_exs(0..len).
```

Deberia ser:

```prolog
pos_exs(0..len-1).
neg_exs(0..len-1).
```

Ahora crea un ejemplo fantasma.

## Cafradas en language bias y espacio de hipotesis

### `ModeDeclaration` y `Example` no deduplican por contenido

No tienen `__eq__`, asi que `if md not in lbh` y `if ex not in pe` comparan identidad de objeto, no contenido.

### Bias demasiado pobre

El language bias solo tiene:

```text
recall, name, arity, positive/negative
```

Faltan:

- tipos;
- modos input/output/constant;
- separacion target/background;
- allowed negation por predicado;
- restricciones declarativas mas fuertes.

Sin eso, el espacio de hipotesis explota y se filtra tarde.

### Automatic language bias peligroso

El modo automatico extrae firmas de background y ejemplos, y mete cada predicado tanto en `modeh` como en `modeb`.

Eso permite:

- aprender cabezas para predicados de background;
- redefinir predicates extensionales;
- meter target predicates en body;
- crear recursion rara;
- ampliar mucho el espacio sin buen control.

El bias inductivo deberia ser fuerte:

```text
modeh = solo targets aprendibles
modeb = solo predicados permitidos en body
```

## Que hace bien

No todo esta mal. Hay partes rescatables:

- La idea hibrida sampling + ASP + busqueda es razonable como prototipo.
- Usar ASP para variable placement tiene mucho sentido.
- Separar stub y placed rule es buena idea.
- `PlacedClause` agrupa placements de un mismo stub, lo cual es util.
- Soportar agregados, aritmetica y comparaciones es ambicioso.
- Usar Clingo para comprobar coverage tiene sentido.
- Canonicalizar reglas por orden tiene buena intencion, aunque ahora rompe indices.
- Filtrar reglas invalidas es necesario, aunque deberia hacerse antes o dentro de ASP.
- Retener stubs prometedores entre rondas tiene buena intuicion.
- Hay scripts de profiling/benchmarks, senal de que se midio algo.

Lo mejor: variable placement como problema ASP.

Lo peor: fitness/evolucion mezclan "programa candidato" con "pool de reglas".

## Pipeline mas logico

La forma mas limpia:

```text
background + rules + constraints + positives + negatives + bias
-> generar todos los stubs posibles bajo bounds
-> pruning temprano de stubs
-> variable placement
-> pruning temprano de reglas colocadas
-> pool de reglas candidatas
-> busqueda de programas como subconjuntos del pool
```

Si el espacio completo no explota, hacerlo una vez y listo.

Si explota, hacerlo incrementalmente, pero con memoria global:

```text
global_candidate_rules = set()

for layer/budget:
  new_stubs = generate_more_stubs()
  new_rules = place_variables(new_stubs)
  prune/deduplicate
  add to global pool
  continue search
```

No reiniciar todo cada ronda.

## GA limpio sobre pool fijo

Si se usa GA:

```text
candidate_rules = [r1, r2, ..., rn]
individual = subset(candidate_rules)
fitness = coverage(full individual)
selection = mejores programas
crossover = combinar rule IDs
mutation = add/remove/replace rule
```

No evaluar subconjuntos internos. El individuo ya es el subconjunto.

Fitness simple:

```text
score = pos_ratio - neg_weight * neg_ratio - size_penalty * len(program)
```

O lexicografico:

```text
1. mas positivos cubiertos
2. menos negativos cubiertos
3. menos reglas
```

## Beam search

Beam search construye programas paso a paso.

Tienes reglas candidatas:

```text
R = [r1, r2, r3, ..., rn]
```

Quieres:

```text
P = subset(R)
```

Algoritmo:

```text
beam = [empty_program]

for depth in 1..max_rules:
  candidates = []

  for P in beam:
    for r in R not in P:
      P2 = P + r
      score(P2)
      candidates.append(P2)

  beam = top K candidates
  if solved: return best
```

`K` es el ancho del beam. Por ejemplo, 50.

Ejemplo:

```text
nivel 0:
  []

nivel 1:
  [r7], [r2], [r99], ... keep top 50

nivel 2:
  [r7,r3], [r7,r44], [r2,r8], ... keep top 50

nivel 3:
  ...
```

Para evitar duplicados por permutacion:

```python
start = program[-1] + 1 if program else 0
for rule_id in range(start, len(rules)):
    child = program + (rule_id,)
```

Asi `[r1, r2]` y `[r2, r1]` no aparecen ambos.

## Branch-and-bound

Branch-and-bound poda ramas que no pueden ganar.

Ejemplos de poda:

- Si un programa ya cubre demasiados negativos y anadir reglas no puede arreglarlo, rama muerta.
- Si no puede cubrir suficientes positivos con las reglas restantes, rama muerta.
- Si el upper bound de score es peor que la mejor solucion actual, rama muerta.

Pseudobound:

```text
upper_bound(P) =
  current_pos_covered(P)
  + max_extra_pos_possible_from_remaining_rules

if upper_bound(P) < best_pos:
  prune
```

Con ASP algunos bounds exactos son dificiles, pero heuristicas sirven.

## Por que beam encaja mejor que GA aqui

Beam search:

- cada nodo es un programa real;
- cada expansion anade una regla;
- no hay crossover raro;
- no hay mutation destructiva;
- no hay subsets internos porque cada nodo ya es un subprograma;
- permite pruning natural;
- permite dedupe por sorted rule IDs;
- da interpretabilidad.

GA:

- puede funcionar sobre pool fijo;
- pero crossover de programas logicos no siempre preserva semantica;
- mutation add/remove/replace es mas razonable que slicing por posicion.

Ranking recomendado:

```text
1. Beam search / branch-and-bound con candidate rules pruned
2. GA sobre candidate pool fijo
3. Sampling incremental con pool global
4. Actual: sampling externo + placement + GA reset + subset fitness
```

## Conclusion

Las iteraciones externas actuales no tienen mucho sentido si el task y el bias no cambian. Como el sampling es aleatorio, cada ronda ve otra ventana del espacio, pero descarta casi todo al terminar.

Eso solo tendria sentido como exploracion incremental si el sistema conservara conocimiento global. Ahora parece mas un reinicio aleatorio caro.

La mejora conceptual mas importante:

```text
Dejar de evaluar subconjuntos dentro del individuo.
Hacer que individuo = programa candidato.
Construir un pool de reglas candidatas con pruning temprano.
Buscar subconjuntos del pool con beam search o GA limpio.
```

