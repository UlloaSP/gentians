# Gentians

Gentians es un solver de Inductive Logic Programming que aprende programas ASP. Busca hipótesis no monótonas, expresadas con sintaxis ASP, mediante un algoritmo evolutivo. Clingo cumple dos papeles distintos: enumera las cláusulas legales a partir del language bias y evalúa la semántica del programa candidato completo.

Gentians no es una librería genética genérica ni un wrapper genérico de Clingo. El algoritmo evolutivo existe para explorar programas ASP válidos sin perder sus invariantes sintácticos y semánticos.

## Lo que no se negocia

### 1. Expresividad no monótona

Una cláusula no tiene cobertura ni fitness estable por sí sola: añadirla puede cambiar los modelos del programa completo. Nunca asumas contribuciones aditivas, cobertura fija por regla ni equivalencia global a partir de los ejemplos. La solución más rápida que aprende otro lenguaje es una regresión.

### 2. La tarea posee su significado

La tarea inductiva define el language bias y sus límites. `Arguments` configura ejecución y estrategias; nunca redefine el lenguaje. `docs/language-bias.md` es el contrato de sintaxis y significado: léelo completo antes de tocar lexer, parser, modes, generación o pruning.

### 3. Una autoridad por concepto

`HypothesisGenerator` es la única autoridad para construir o transformar genomas y mantener el cierre de dependencias. La legalidad de una regla vive en el análisis estático o el metaprograma ASP. Si varios operadores necesitan el mismo guard, ese guard pertenece al constructor de hipótesis.

### 4. Medir antes de afirmar

Un cambio de rendimiento necesita una medición reproducible. Una intuición sobre Clingo, grounding o búsqueda no cuenta como resultado. Grounding, solving, Python y closure se miden por separado; reducir llamadas no implica reducir tiempo.

## Glosario mínimo

- **Tarea inductiva**: background ASP, ejemplos y language bias. `InductiveTask` es su IR, no la hipótesis.
- **Cláusula / `ClauseSpace`**: una cláusula candidata canónica / el conjunto ordenado y sin duplicados de ellas.
- **Hipótesis o programa candidato**: conjunto de cláusulas evaluado como una unidad bajo stable-model semantics. `Genome` es su bitset.
- **Hipótesis perfecta**: cubre todos los positivos y ningún negativo; produce `best_found=True`.
- **Cierre de dependencias**: toda dependencia queda definida por el background o por una cabeza del mismo candidato.

Usa `ClauseSpace` para cláusulas candidatas e hipótesis para lo que evalúa el fitness. Glosario completo: [docs/glossary.md](docs/glossary.md).

## Tres formas de romper Gentians

1. **Tocar la tarea creyendo tocar un fixture.** Los task files de `benchmarks/gentians/` son el problema. Cambiarlos cambia el experimento.
2. **Borrar resultados sin querer.** `run_experiments.py --force` borra el directorio exacto del experimento antes de repetirlo. Úsalo solo para reemplazar ese resultado. Nunca edites a mano JSON o CSV generados.
3. **Pisar trabajo ajeno.** El worktree puede contener experimentos sin commit. Consérvalos. Elimina los smoke tests temporales que crees.

## Recorre toda la cadena

El defecto más común es un cambio correcto en una capa e incompleto en las demás. Antes de darlo por terminado, di cuáles de estas cadenas aplicaban:

- **Lenguaje.** Lexer, parser, IR, compilación de modes/facts, metaprograma, decoder/render, `docs/language-bias.md` y tests de generación. Sintaxis sin semántica de generación, o semántica sin documentación, está incompleta.
- **Algoritmos.** `steady_state` e `incremental` comparten `SearchResult`, evaluación y estrategias, no su bucle ni su estado. Decide qué pasa en cada uno.
- **Estrategias.** Las factories de cada categoría evolutiva son la frontera de configuración aunque registren una sola estrategia. No las elimines. Una estrategia nueva se registra allí y delega el cierre a `HypothesisGenerator`.
- **Cobertura.** Prueba inclusión, exclusión, un lado vacío, contexts aislados y negación por defecto.
- **Medición.** `timing.py`, productor del dashboard, `DASHBOARD_SCHEMA_VERSION`, preview y tests cambian juntos. Los charts tienen un contrato fijo: no los cambies sin petición explícita.
- **Docs.** Comprueba si el cambio deja inexacta alguna guía existente.

## Verificación

Usa la prueba más pequeña que pueda fallar por el cambio:

```powershell
uv run pytest tests/test_clause_space.py -q
uv run pytest tests/test_evolution_operators.py -q
uv run pytest tests/test_evaluation.py -q
uv run pytest tests/test_profile_baseline.py -q
uv run ruff check <paths-tocados>
uv run ty check
```

- Ejecuta la suite completa solo en cambios transversales o cuando se pida.
- Tests de generación demuestran presencia de formas válidas y ausencia de formas podadas.
- Tests evolutivos fijan seed o inyectan RNG.
- Tests de rendimiento no afirman velocidad con thresholds frágiles. Benchmarks no sustituyen tests semánticos.
- UI: `vp build` desde `.benchmarks/` como mínimo; `vp test` si cambian cálculos o schema. En ese directorio usa siempre `vp`.

## Documentación

- Cambios visibles del task language actualizan `docs/language-bias.md` y el resumen de `docs/task-language.md`.
- Una decisión va a `docs/adr/` solo si es difícil de revertir, sorprendente y resultado de un tradeoff real.
- Un experimento conserva protocolo, control, variables, entorno, resultados y límites. Una idea sin medición se marca como no implementada.
- Los diagramas describen código existente. Si cambia el flujo de un `docs/*.json`, actualiza su `.html`.
- No hagas commit de planes, scratch ni resultados locales de benchmark.

## Cómo funciona

```text
task file -> InductiveTask -> modes + metaprograma ASP -> Clingo enumera y poda
  -> decode + canonicalización -> ClauseSpace -> HypothesisGenerator
  -> búsqueda evolutiva -> CandidateEvaluator (programa completo) -> SearchResult
```

Detalle de cada etapa e invariantes: [docs/pipeline.md](docs/pipeline.md).

## Dónde vive el código

- `gentians/language/`: lectura, lexer, parser y el IR `InductiveTask`. Clingo es la autoridad de la gramática ASP.
- `gentians/clauses/`: análisis estático, compilación de modes, metaprograma `.lp`, decodificación y canonicalización.
- `gentians/hypotheses/`: `HypothesisGenerator`, genomas y cierre de dependencias.
- `gentians/algorithms/`: solo los dos algoritmos, como wiring legible de un vistazo, y sus métricas en `algorithms/metrics/`.
- `gentians/search/`: pasos que los algoritmos conectan: candidatos, población, cruce, lotes de cláusulas, renovación y presupuesto.
- `gentians/evolution/`: `Individual`, `EvolutionContext`, protocolos y una factory por categoría de estrategia.
- `gentians/evaluation/`: cobertura, score y `CoverageSolver`, independiente de `evolution/`.
- `benchmarks/` produce métricas; `.benchmarks/` es el preview Vite que las consume.

Antes de un refactor, una simplificación o un cambio de frontera, lee [docs/architecture.md](docs/architecture.md): dueño del concepto, consumidores, invariantes, tests, estructura deseada y ruta de cada tipo de cambio. Para medición y benchmarks, [docs/benchmark-dashboard.md](docs/benchmark-dashboard.md).

## Criterio

- Entiende el flujo completo antes de editar. Implementa el cambio mínimo en la capa dueña del concepto. Reutiliza stdlib, Clingo y código existente antes de añadir abstracciones o dependencias.
- Cambia APIs internas de forma directa y actualiza todos sus usos. Sin wrappers, adaptadores temporales ni capas de compatibilidad.
- Combinatoria y constraints van declarativos en ASP cuando es más directo. Parsing, AST, canonicalización, cachés y orquestación van en Python. No generes un dominio enorme para filtrarlo después.
- Canonicalizar preserva semántica ASP. `p/n` y `-p/n` son predicados distintos.
- Dataclasses pequeñas e inmutables para el dominio. Los dicts de configuración se quedan en `Arguments` y las factories.
- Orden determinista de modes, reglas y outputs. Aleatoriedad solo mediante el RNG de la búsqueda.
- Sin interfaces de una implementación ni configuración para valores que no varían, salvo las factories evolutivas.
- Si una regla de este archivo choca con la tarea, dilo claramente y pide confirmación antes de romperla.
