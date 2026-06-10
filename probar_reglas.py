from pathlib import Path
import re
import sys

import clingo


# Pega aqui las reglas que genero GENTIANS.
# Ejemplo:
# REGLAS = r"""
# eligible(X):- adult(X),active(X),not blocked(X),purchase(X,A),A >= 50.
# """
REGLAS = r"""
eligible(V0) :- adult(V1),newsletter(V1),not blocked(V0),verified(V0).
"""

ARCHIVO_TAREA = Path("pruebas3.txt")


def limpiar_reglas(texto: str) -> list[str]:
    reglas = []
    for raw in texto.splitlines():
        line = raw.strip()
        if not line or line.startswith("%"):
            continue
        if line.startswith("[") or line.startswith("]"):
            continue
        line = line.strip(",")
        if (line.startswith("'") and line.endswith("'")) or (
            line.startswith('"') and line.endswith('"')
        ):
            line = line[1:-1]
        if line and not line.endswith("."):
            line += "."
        reglas.append(line)
    return reglas


def parsear_tarea(path: Path):
    background = []
    positivos = []
    negativos = []

    ejemplo_re = re.compile(r"^#(pos|neg)\(\{([^{}]*)\},\{([^{}]*)\}\)\.$")

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("%"):
            continue
        if line.startswith("#modeh") or line.startswith("#modeb"):
            continue

        compact = line.replace(" ", "")
        match = ejemplo_re.match(compact)
        if match:
            tipo, incluido, excluido = match.groups()
            destino = positivos if tipo == "pos" else negativos
            destino.append((incluido, excluido))
            continue

        background.append(line)

    return background, positivos, negativos


def atomos(texto: str) -> list[str]:
    if not texto:
        return []
    return [a.strip() for a in texto.split(",") if a.strip()]


def cubre(programa: list[str], incluido: str, excluido: str) -> bool:
    extra = []
    for atom in atomos(incluido):
        extra.append(f":- not {atom}.")
    for atom in atomos(excluido):
        extra.append(f":- {atom}.")

    ctl = clingo.Control(["0"])
    ctl.add("base", [], "\n".join(programa + extra))
    ctl.ground([("base", [])])
    result = ctl.solve()
    return result.satisfiable


def main() -> int:
    if not ARCHIVO_TAREA.exists():
        print(f"ERROR: no existe {ARCHIVO_TAREA}")
        return 2

    reglas = limpiar_reglas(REGLAS)
    if not reglas:
        print("ERROR: pega reglas en REGLAS antes de ejecutar.")
        return 2

    background, positivos, negativos = parsear_tarea(ARCHIVO_TAREA)
    programa = background + reglas

    print("Reglas probadas:")
    for regla in reglas:
        print(f"  {regla}")
    print()

    ok_pos = []
    fail_pos = []
    for i, (incluido, excluido) in enumerate(positivos):
        (ok_pos if cubre(programa, incluido, excluido) else fail_pos).append(i)

    ok_neg = []
    fail_neg = []
    for i, (incluido, excluido) in enumerate(negativos):
        (fail_neg if cubre(programa, incluido, excluido) else ok_neg).append(i)

    print(f"Positivos cubiertos OK: {len(ok_pos)}/{len(positivos)} -> {ok_pos}")
    print(f"Positivos fallidos: {fail_pos}")
    print(f"Negativos rechazados OK: {len(ok_neg)}/{len(negativos)} -> {ok_neg}")
    print(f"Negativos cubiertos ERROR: {fail_neg}")
    print()

    if not fail_pos and not fail_neg:
        print("RESULTADO: OPTIMO")
        return 0

    print("RESULTADO: NO OPTIMO")
    return 1


if __name__ == "__main__":
    sys.exit(main())
