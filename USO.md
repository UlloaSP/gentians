# Uso rapido de `pruebas.txt`

Este archivo muestra ejecuciones de prueba para `pruebas.txt`.
Los comandos crean salidas en `resultados_pruebas/`.

## Flags principales

`-f .\pruebas.txt`
Archivo de entrada con conocimiento base, ejemplos positivos, ejemplos negativos y bias de lenguaje.

`-it N` o `--iterations N`
Numero de ciclos externos. En cada ciclo se muestrean clausulas, se colocan variables y se ejecuta algoritmo genetico.
Mas alto = mas oportunidades de encontrar buen programa, mas tiempo.

`-s N` o `--samples N`
Numero de clausulas candidatas a muestrear por ciclo.
Mas alto = espacio de busqueda mas amplio, mas tiempo/memoria.

`-p N` o `--pop-size N`
Tamano de poblacion del algoritmo genetico.
Debe ser al menos 12 porque el torneo interno usa 12 individuos.
Mas alto = busqueda mas diversa, mas coste.

`-itg N` o `--iterations-genetic N`
Iteraciones internas del algoritmo genetico por ciclo externo.
Mas alto = mas refinamiento de programas candidatos.

`-c N` o `--clauses N`
Maximo de clausulas por programa candidato.
Mas alto permite soluciones mas complejas, pero agranda mucho la busqueda.

`-d N` o `--depth N`
Maximo de literales por regla. Cuenta cabeza y cuerpo.
Mas alto permite reglas mas expresivas, pero genera mas combinaciones.

`-vars N` o `--variables N`
Maximo numero de variables distintas por regla.
Mas alto permite reglas con mas relaciones entre argumentos.

`-v N` o `--verbosity N`
Nivel de detalle de salida. Valores permitidos: `0`, `1`, `2`.
`0` = basico. `1` = muestra clausulas muestreadas. `2` = salida mas detallada de colocacion de variables.

`--comparison ...`
Activa operadores de comparacion en reglas candidatas.
Valores permitidos: `lt` (`<`), `leq` (`<=`), `gt` (`>`), `geq` (`>=`), `eq` (`=`), `neq` (`!=`).
Ejemplo: `--comparison geq gt lt neq`.

`--arithm ...`
Activa operadores aritmeticos.
Valores permitidos: `add`, `sub`, `mul`, `div`, `abs`.
Ejemplo: `--arithm add sub`.

`--aggregates ...`
Activa agregados sobre predicados.
Formato: `"sum(predicado/aridad)"`, `"count(predicado/aridad)"`, etc.
Ejemplo: `--aggregates "sum(purchase/2)" "count(purchase/2)"`.

`-ua` o `--unbalanced-agg`
Permite agregados no balanceados. Puede ampliar busqueda y provocar grounding mas grande.
Usar sobre todo cuando pruebas `--aggregates`.

`-alb=N`
Activa descubrimiento automatico de language bias con recall `N`.
Si `N > 0`, genera body literals positivos.
Si `N < 0`, genera body literals negativos.
Ignora `#modeh/#modeb` manuales, salvo operadores especiales ya pasados por flags.

`--invention=N`
Activa invencion de `N` predicados auxiliares internos.
Puede descubrir reglas intermedias, pero agranda el espacio de busqueda.

`--profile`
Ejecuta con `cProfile` y anade estadisticas de rendimiento al final de la salida.

`--version`
Imprime version y termina.

`--help`
Muestra ayuda completa del ejecutable.

## Preparar directorio de resultados

```powershell
New-Item -ItemType Directory -Force .\resultados_pruebas
```

## Ver ayuda y version

```powershell
uv run .\.venv\Scripts\gentians.exe --help > .\resultados_pruebas\00_help.txt
uv run .\.venv\Scripts\gentians.exe --version > .\resultados_pruebas\01_version.txt
```

## Ejecucion minima

Configuracion pequena para comprobar que el fichero carga y que el flujo completo arranca.

```powershell
uv run .\.venv\Scripts\gentians.exe -f .\pruebas.txt -it 1 -s 80 -p 20 -itg 80 -c 3 -d 3 -vars 3 -v 1 > .\resultados_pruebas\10_minima.txt
```

## Mas busqueda

Mas muestras, mas iteraciones geneticas, mas clausulas por programa.

```powershell
uv run .\.venv\Scripts\gentians.exe -f .\pruebas.txt -it 3 -s 300 -p 60 -itg 400 -c 5 -d 4 -vars 3 -v 1 > .\resultados_pruebas\20_busqueda.txt
```

## Comparacion y aritmetica

Permite generar reglas con operadores de comparacion y suma/resta.
El problema contiene hechos numericos (`age/2`, `purchase/2`) para que estos flags tengan sentido.

```powershell
uv run .\.venv\Scripts\gentians.exe -f .\pruebas.txt -it 2 -s 250 -p 60 -itg 300 -c 5 -d 4 -vars 4 --comparison geq gt lt neq --arithm add sub -v 1 > .\resultados_pruebas\30_comparison_arithm.txt
```

## Agregados

Permite agregados sobre compras. Usar con cuidado: agregados amplian mucho el espacio de busqueda.

```powershell
uv run .\.venv\Scripts\gentians.exe -f .\pruebas.txt -it 2 -s 250 -p 60 -itg 300 -c 5 -d 4 -vars 4 --aggregates "sum(purchase/2)" "count(purchase/2)" -ua -v 1 > .\resultados_pruebas\40_aggregates.txt
```

## Bias automatico

Ignora `#modeh/#modeb` manuales y descubre bias desde hechos, reglas y ejemplos.

```powershell
uv run .\.venv\Scripts\gentians.exe -f .\pruebas.txt -alb=1 -it 2 -s 200 -p 50 -itg 250 -c 4 -d 3 -vars 3 -v 1 > .\resultados_pruebas\50_alb.txt
```

## Invencion de predicados

Anade predicados internos `__inv_*__` al espacio de busqueda.

```powershell
uv run .\.venv\Scripts\gentians.exe -f .\pruebas.txt --invention=1 -it 2 -s 250 -p 60 -itg 300 -c 5 -d 4 -vars 4 -v 1 > .\resultados_pruebas\60_invention.txt
```

## Perfilado

Genera salida de profiling al final del log.

```powershell
uv run .\.venv\Scripts\gentians.exe -f .\pruebas.txt -it 1 -s 150 -p 40 -itg 150 -c 4 -d 3 -vars 3 --profile > .\resultados_pruebas\70_profile.txt
```

## Ejecucion completa combinada

Prueba amplia con comparacion, aritmetica, agregados e invencion.
Puede tardar mas que las anteriores.

```powershell
uv run .\.venv\Scripts\gentians.exe -f .\pruebas.txt -it 4 -s 600 -p 80 -itg 700 -c 6 -d 5 -vars 4 --comparison geq gt lt neq --arithm add sub --aggregates "sum(purchase/2)" "count(purchase/2)" -ua --invention=1 -v 2 > .\resultados_pruebas\80_completa.txt
```

## Probar reglas generadas

Cuando GENTIANS imprima reglas candidatas, copialas en `probar_reglas.py`, dentro de:

```python
REGLAS = r"""
eligible(X):- adult(X),active(X),not blocked(X),purchase(X,A),A >= 50.
"""
```

Luego ejecuta:

```powershell
uv run python .\probar_reglas.py
```

El script lee `pruebas.txt`, carga conocimiento base y ejemplos, anade tus reglas pegadas y comprueba cobertura.

## Resultado optimo esperado

Atomos correctos para `eligible/1`:

```prolog
eligible(alice).
eligible(dave).
```

Atomos que NO deben salir:

```prolog
eligible(bob).
eligible(carol).
eligible(erin).
eligible(frank).
```

Regla optima simple esperada:

```prolog
eligible(X):- adult(X),active(X),not blocked(X),purchase(X,A),A >= 50.
```

Salida optima de `probar_reglas.py`:

```text
Positivos cubiertos OK: 3/3 -> [0, 1, 2]
Positivos fallidos: []
Negativos rechazados OK: 5/5 -> [0, 1, 2, 3, 4]
Negativos cubiertos ERROR: []

RESULTADO: OPTIMO
```

## `pruebas3.txt`: facil grande sin operadores

Este archivo esta pensado para sacar reglas mas facil que `pruebas.txt`.
No requiere `--comparison`, `--arithm`, `--aggregates`, `-ua` ni `--invention`.

Auto-config:

```powershell
uv run python .\auto_gentians.py .\pruebas3.txt --preset balanced
uv run python .\auto_gentians.py .\pruebas3.txt --preset balanced --run --out .\resultados_pruebas\auto_pruebas3.txt
```

Comando recomendado:

```powershell
uv run .\.venv\Scripts\gentians.exe -f .\pruebas3.txt -it 8 -s 800 -p 80 -itg 1200 -c 3 -d 4 -vars 2 -v 1 > .\resultados_pruebas\90_pruebas3.txt
```

Regla optima esperada:

```prolog
eligible(X):- adult(X),active(X),not blocked(X).
```



> uv run .\.venv\Scripts\gentians.exe -f .\pruebas2.txt -it 1 -s 30 -p 100 -itg 5000 -c 6 -d 5 -vars 4 -v 0 > .\resultados_pruebas\80_completa.txt
> Si se lanza muchas veces hay casos donde se queda tiempo infinito esperando o saca errores random


> uv run python .\auto_gentians.py .\pruebas3.txt --preset exhaustive --run --out .\resultados_pruebas\auto_pruebas3.txt
> command que saca el comando anterior
> poner reglas y archivo base en probar_reglas.py
> uv run probar_reglas.py