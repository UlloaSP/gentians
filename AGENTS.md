# Rules

use `caveman`and `ponytail`skills in ultra mode.
Si haces smoke tests, al terminar los eliminas.
Para el .benchmarks/ vite project usa la herramienta `vp`.
No dejes wrappers, adaptadores temporales, adaptadores sobre adaptadores, ni capas de compatibilidad innecesarias. Si una API interna debe cambiar, haz breaking change y conecta los usos directos despues.

## Benchmark charts contract

No cambies estas gráficas salvo petición explícita:

- Progreso de búsqueda: `max`, `best` y `avg`; eje inicial `generación`, empezando en generación `0`. Puede alternar a evaluaciones de fitness o segundos.
- Resultado de operadores: una sola categoría por pareja `operador:estrategia`. `duplicate` significa resultado repetido tras normalizar/cerrar, no una categoría duplicada.
- Cards de tiempos: deben mostrar `total`, `hypothesis`, `clingo` y `python`; `total` es la media de `total_execution`, nunca wall-clock. `hypothesis` y `tiempo evolutivo` van juntas.
- Fases: `hypothesis space`, `pregrounding`, `initialization`, `selection`, `crossover`, `mutation`, `replacement` y `search orchestration`. No existe fase separada `fitness evaluation`: su coste pertenece a la fase que solicitó la evaluación.
- Tipos horizontales de tiempo: exactamente `python`, `grounding`, `solving` y `closure`.
- `pregrounding` solo mide creación y grounding del solver pregenerado; ejecución normal no inventa esa fase.
- Modelos solve por etapa: usa fases reales; `hypothesis_space` se muestra como `hypothesis`. No agrupa fases conocidas como `search setup`, `fitness search` ni `other`.
- Los títulos de charts identifican la métrica y son funcionales. No añadas títulos de página, hero copy ni texto ornamental.
- Comparación conserva todas las gráficas y divisiones de la vista individual. Cada experimento añade sus líneas, grupos, stacks o anillos; no se reemplazan por resúmenes distintos.
- En comparación, el color identifica siempre al experimento; métricas y divisiones usan líneas, símbolos, opacidad o trama. Las leyendas no multiplican `experimento × división` y todo debe distinguirse sin hover.
- Tabla de comparación: no muestra wall-clock. Usa `total_execution` y su delta; `grounding`, `solving` y `python` con sus deltas; `ground calls` y `solve calls`.
