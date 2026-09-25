export const CHART_DESCRIPTIONS = {
  "Tiempo total_execution":
    "Media aritmética de total_execution entre las ejecuciones instrumentadas del benchmark. total_execution se cierra antes de imprimir la hipótesis y excluye el coste de serializar la instrumentación. La barra usa segundos; menos es mejor.",
  "Fases por tipo":
    "Cada barra es el tiempo medio de una fase, separado en python, grounding, solving y closure. Para cada ejecución se suman las llamadas de la métrica; después se promedian las ejecuciones. python = tiempo self de la fase − grounding − solving − closure, limitado a cero. El tiempo no atribuido se incorpora a search orchestration para que la suma coincida con total_execution.",
  "Porcentajes de tiempo por tipo":
    "Clauses suma clause generation. Evolution suma initialization, selection, crossover, mutation, replacement y search orchestration. Cada segmento es 100 × tiempo del tipo / tiempo del bloque, por lo que cada barra suma 100%. El tooltip muestra también los segundos y tiempo del bloque / total_execution.",
  "Progreso de búsqueda":
    "max es el mayor fitness de la población, avg su media y best so far el mejor valor observado hasta entonces. El eje X puede ser la generación, las evaluaciones de fitness acumuladas o los segundos netos desde el inicio de la búsqueda; las evaluaciones y los segundos comparan steady-state e incremental con el mismo coste. La vista media la calcula el agregador Python con todas las generaciones registradas: en una rejilla de hasta 300 posiciones del eje arrastra hacia delante el último valor de cada ejecución y calcula la media; la banda muestra mínimo y máximo, y best es el máximo de max entre ejecuciones. La vista de una ejecución muestra hasta 300 puntos: siempre el primero, el último, cada mejora de best so far y cada reinicio, más puntos equiespaciados. Las líneas discontinuas marcan las generaciones en las que la estrategia de reinicio remuestreó la población; el punto marcado ya incluye la población reiniciada.",
  "Resultado operadores":
    "Para cada pareja operador:estrategia se calculan tasas por ejecución y luego se promedian entre ejecuciones. valid = resultados nuevos válidos / slots; en replacement usa aceptados / slots. duplicate = resultados repetidos después de normalizar y cerrar / slots. invalid/failed = resultados inválidos / slots. skipped = slots omitidos / slots. Las categorías pueden no sumar 1 cuando describen condiciones independientes o faltan datos.",
  "Mejora operadores":
    "Las tasas se calculan por ejecución y después se promedian. En crossover y mutation, el denominador son resultados válidos con score original y nuevo; improved cuenta los que aumentan score. Crossover compara su hijo con el mejor padre y mutation compara el programa mutado con el hijo del crossover. El hijo del crossover solo tiene score cuando alguna evaluación ya lo cubrió, normalmente la clasificación de mutation. En replacement, el denominador es accepted + not competitive e improved compara candidato con víctima. worse/equal es el resto del mismo denominador.",
  "Impacto score operadores":
    "Media por ejecución del cambio de score y después media entre ejecuciones. Para crossover y mutation, delta = new_score − original_score en resultados válidos con ambos scores; crossover usa el mejor padre como original y mutation usa el hijo del crossover. Para replacement, delta = candidate_score − victim_score en reemplazos aceptados. Positivo indica mejora media; negativo, empeoramiento.",
  "Pérdida de ganancias de crossover":
    "Considera mutaciones aplicadas a hijos de crossover con score mayor que su mejor padre. perdida = casos en que el programa mutado puntúa por debajo de ese hijo / eventos con ganancia de crossover; preservada = el resto del mismo denominador. Solo cuentan hijos con score conocido. Las tasas se calculan por ejecución y después se promedian.",
  "Épocas incrementales":
    "Solo el algoritmo incremental divide la búsqueda en épocas. Cada barra es el número medio de épocas por ejecución que terminaron por ese motivo: renovación del lote tras epoch_generations, reinicio por la estrategia de reinicio con el espacio agotado, espacio de hipótesis agotado, solución o límite de generaciones. El resumen da épocas por run y la media por época de generaciones, evaluaciones y cláusulas activas.",
  "Candidatos evaluados por cobertura (media por run)":
    "Cada punto agrupa programas candidatos con el mismo comportamiento (positivos cubiertos, negativos cubiertos). El tamaño de la burbuja usa count / runs instrumentados. count es el número total de evaluaciones en ese comportamiento y meanScore la media de sus scores. Un rombo indica que al menos un candidato del grupo fue una hipótesis perfecta.",
  "Facilidad de satisfacer criterios de cobertura":
    "Para cada ejecución se divide el número de candidatos que cumple el criterio entre todos sus candidatos evaluados y se multiplica por 100; la barra es la media de esos porcentajes. complete cubre todos los positivos, consistent no cubre negativos y complete + consistent cumple ambas condiciones. Las variantes incomplete e inconsistent son sus complementos respectivos.",
  "Programas evaluados por tamaño":
    "Cuenta todas las evaluaciones instrumentadas agrupadas por número de cláusulas del programa candidato. El eje X es el tamaño del programa y el eje Y el número total de evaluaciones, sumado entre ejecuciones.",
  "Best encontrados por tamaño":
    "Para cada ejecución que encontró una hipótesis perfecta se conserva el tamaño de ese programa ganador. La barra cuenta cuántas ejecuciones terminaron con un ganador de cada número de cláusulas; cada ejecución aporta como máximo una unidad.",
  "Stats Clingo":
    "atoms y rules son la media por ejecución de la media observada por llamada de Clingo. choices, conflicts y models son primero la suma de las llamadas solve de cada ejecución y después la media entre ejecuciones. Se usa escala logarítmica porque los órdenes de magnitud pueden diferir mucho.",
  "Bottleneck Clingo":
    "Agrupa por operación (grounding o solving) y fase solicitante. Para cada ejecución suma los segundos de todas las llamadas del grupo y después promedia entre ejecuciones. Se ordenan los grupos por tiempo descendente y se muestran los seis con mayor coste positivo.",
  "Modelos solve por etapa":
    "Usa las fases reales en las que el algoritmo pidió solve; clause_generation se muestra como clauses. Para cada fase suma los modelos producidos por sus llamadas solve dentro de una ejecución y después promedia entre ejecuciones. El sector representa modelos medios de la fase / modelos medios de todas las fases. modelos/solve divide modelos medios entre llamadas solve medias del mismo grupo.",
  "Coste Clingo por fase":
    "Para cada contexto de fase y categoría, suma los segundos de sus llamadas dentro de cada ejecución y después calcula la media entre ejecuciones. La barra apila grounding y solving; su longitud es el coste medio total de Clingo solicitado por esa fase.",
  "Llamadas Clingo por contexto":
    "Cuenta llamadas de grounding y solve por fase en cada ejecución y después calcula la media entre ejecuciones. Las dos barras no representan duración: muestran cuántas veces la fase pidió cada operación a Clingo.",
  "Tiempo total vs best medidos":
    "Cada punto usa X = media de total_execution e Y = 100 × best_found / runs instrumentados. El tamaño usa 100 × runs instrumentados / runs totales. La cruz marca los valores del baseline. La frontera Pareto conecta experimentos para los que no existe otro con tiempo igual o menor y tasa de best igual o mayor, con al menos una mejora estricta.",
};

export function chartDescription(title) {
  return CHART_DESCRIPTIONS[title] || "Descripción de cálculo no disponible.";
}
