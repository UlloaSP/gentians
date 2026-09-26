# Glosario

Usa estos términos en código, docs y conversación.

- **Tarea inductiva**: archivo que contiene background ASP, ejemplos y language bias. También posee los límites estructurales.
- **`InductiveTask`**: IR parseado de la tarea inductiva. No es la hipótesis aprendida.
- **Language bias**: lenguaje finito permitido para las hipótesis. Incluye modes, recalls, tipos, direcciones, constantes, límites e invención.
- **Cláusula**: una cláusula ASP aprendible ya instanciada y canónica.
- **`Clause`**: AST y texto canónico de una cláusula junto a predicados definidos, dependencias y tamaño de cuerpo.
- **`ClauseSpace`**: conjunto ordenado y sin duplicados de cláusulas candidatas.
- **Hipótesis o programa candidato**: conjunto de cláusulas del `ClauseSpace` evaluado como una unidad bajo stable-model semantics.
- **`Genome`**: entero bitset que representa una hipótesis. El bit `i` selecciona la cláusula `i` del `ClauseSpace` preparado.
- **`Individual`**: genoma evaluado con score, marca de solución, firma de comportamiento y edad.
- **`SearchResult`**: hipótesis elegida, score y marca de solución devueltos por cualquier algoritmo completo.
- **Comportamiento**: pareja de máscaras `(pos_mask, neg_mask)`. La primera marca positivos cubiertos; la segunda, negativos cubiertos.
- **`Coverage`**: valor inmutable con las máscaras de comportamiento producidas por Clingo.
- **`EvaluationResult`**: score, marca de solución y comportamiento de un programa candidato evaluado.
- **Hipótesis perfecta**: cubre todos los ejemplos positivos y ningún negativo. Esto produce `best_found=True`.
- **Cierre de dependencias**: toda dependencia de una cláusula queda definida por el background o por alguna cabeza del mismo candidato.
- **Pruning**: exclusión de cláusulas o hipótesis inválidas, redundantes o imposibles antes de gastar evaluaciones de fitness.
- **`CoverageSolver`**: crea, groundea y resuelve un `clingo.Control` por candidato para obtener `Coverage`.

Usa `ClauseSpace` para cláusulas candidatas. Usa hipótesis o programa candidato
para el conjunto evaluado por fitness.
