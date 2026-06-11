# Ejemplos con `-e`

Comandos para lanzar ejemplos integrados. Ejecutar desde raiz del repo.

Comando base:

```powershell
uv run .\.venv\Scripts\gentians.exe -e NOMBRE_EJEMPLO
```

## Ejemplos simples

```powershell
uv run .\.venv\Scripts\gentians.exe -e coin -v 1
uv run .\.venv\Scripts\gentians.exe -e even_odd -v 1
uv run .\.venv\Scripts\gentians.exe -e animals_bird -v 1
uv run .\.venv\Scripts\gentians.exe -e adjacent_to_red -d 4 -v 1
uv run .\.venv\Scripts\gentians.exe -e grandparent -v 1
```

## Grafos, sudoku y reinas

```powershell
uv run .\.venv\Scripts\gentians.exe -e coloring -dh 3 -d 4 -v 1
uv run .\.venv\Scripts\gentians.exe -e clique -d 7 --comparison neq -v 1 --variables=2
uv run .\.venv\Scripts\gentians.exe -e sudoku -d 3
uv run .\.venv\Scripts\gentians.exe -e 4queens -d 5 -v 1 --arithm add sub --comparison lt --variables 3
uv run .\.venv\Scripts\gentians.exe -e 5queens -d 5 -v 1 --arithm add sub --comparison lt --variables 3
```

## Hamming

```powershell
uv run .\.venv\Scripts\gentians.exe -e hamming_0 -d 3 --aggregates "sum(d/2)" --comparison neq -v 1 --variables=4
uv run .\.venv\Scripts\gentians.exe -e hamming_1 -d 3 --aggregates "sum(d/2)" --comparison neq -v 1 --variables=4
uv run .\.venv\Scripts\gentians.exe -e hamming_0 -d 3 --aggregates "sum(d/2)" "count(d/2)" --comparison neq --verbose=2 --variables=4 -ua
uv run .\.venv\Scripts\gentians.exe -e hamming_1 -d 3 --aggregates "sum(d/2)" "count(d/2)" --comparison neq --verbose=2 --variables=4 -ua
```

## Subset sum

```powershell
uv run .\.venv\Scripts\gentians.exe -e subset_sum -d 3 --aggregates "sum(el/1)" "count(el/1)" --comparison neq -v 1 -ua
uv run .\.venv\Scripts\gentians.exe -e subset_sum -d 3 --aggregates "sum(el/1)" "count(el/1)" --comparison neq geq leq -v 1 -ua
uv run .\.venv\Scripts\gentians.exe -e subset_sum_double -d 4 --aggregates "sum(el/2)" "sum(el/2)" --arithm add --verbose=2 --variables=3
uv run .\.venv\Scripts\gentians.exe -e subset_sum_double -d 4 --aggregates "sum(el/2)" "sum(el/2)" --arithm add --verbose=2 --variables=3 -ua
uv run .\.venv\Scripts\gentians.exe -e subset_sum_double -d 4 --aggregates "sum(el/2)" "sum(el/2)" "count(el/2)" "count(el/2)" --arithm add --verbose=2 --variables=3 -ua
uv run .\.venv\Scripts\gentians.exe -e subset_sum_double_and_sum -d 4 --aggregates "sum(el/2)" "sum(el/2)" --arithm add -v 1 --variables=4
uv run .\.venv\Scripts\gentians.exe -e subset_sum_double_and_prod -d 4 --aggregates "sum(el/2)" "sum(el/2)" --arithm add mul sub -v 1 --variables=5
uv run .\.venv\Scripts\gentians.exe -e subset_sum_double_and_prod -d 4 --aggregates "sum(el/2)" "sum(el/2)" --arithm add mul sub -v 1 --variables=5 -ua
uv run .\.venv\Scripts\gentians.exe -e subset_sum_triple -d 4 --aggregates "sum(el/3)" "sum(el/3)" "sum(el/3)" -v 1 --variables=4
```

## Knapsack

```powershell
uv run .\.venv\Scripts\gentians.exe -e knapsack -d 4 --aggregates "sum(weight/2)" "sum(value/2)" --comparison geq leq -v 1 --variables=4 -ua
```

## Cuadrados y particiones

```powershell
uv run .\.venv\Scripts\gentians.exe -e magic_square_no_diag --aggregates "sum(x/3)" --comparison neq
uv run .\.venv\Scripts\gentians.exe -e latin_square -d 4 --aggregates "count(x/3)" --comparison neq -v 1 --variables=4 -ua
uv run .\.venv\Scripts\gentians.exe -e set_partition_sum_new -d 4 --verbose=2 --comparison neq neq --variables 4 --aggregates "sum(p/2)" -ua
uv run .\.venv\Scripts\gentians.exe -e set_partition_sum_and_cardinality_new -d 4 --verbose=2 --comparison neq neq --variables 4 --aggregates "sum(p/2)" "count(p/2)" -ua
uv run .\.venv\Scripts\gentians.exe -e set_partition_sum -d 4 -v 1 --comparison neq neq --variables 4 --aggregates "sum(p/2)" -ua
uv run .\.venv\Scripts\gentians.exe -e set_partition_sum_and_cardinality -d 4 -v 1 --comparison neq neq --variables 4 --aggregates "sum(p/2)" "count(p/2)" -ua
uv run .\.venv\Scripts\gentians.exe -e set_partition_sum_cardinality_and_square -d 4 -v 1 --comparison neq neq --variables 4 --aggregates "sum(p/2)" "count(p/2)" "sum(sq/2)" -ua
```

## Plantilla usuario

```powershell
uv run .\.venv\Scripts\gentians.exe -e user_defined
```

Nota: `euclid` existe en `gentians/example_programs.py`, pero no esta habilitado en choices del CLI `-e`.
