from pathlib import Path

from .parser import parse_aggregate_spec, split_top_level_args
from .program import AggregateDeclaration, Example, ModeDeclaration, OperatorDeclaration, Program


def _get_mode_declaration(
    s: str, for_head: bool
) -> "tuple[str,str,str] | tuple[str,str,str,str]":
    name = "#modeh" if for_head else "#modeb"
    parts = split_top_level_args(_directive_args(s, name))
    expected = 3 if for_head else 4
    if len(parts) != expected:
        raise ValueError(f"invalid {name} declaration: {s}")
    return tuple(part.strip() for part in parts)  # type: ignore[return-value]


def _get_pos_neg_examples(s: str) -> "tuple[str,str] | tuple[str,str,str]":
    name = "#pos" if s.startswith("#pos") else "#neg"
    parts = split_top_level_args(_directive_args(s, name))
    if len(parts) not in (2, 3):
        raise ValueError(f"invalid example declaration: {s}")
    return tuple(_strip_outer_braces(part.strip()) for part in parts)  # type: ignore[return-value]


def _get_aggregate_declaration(s: str) -> AggregateDeclaration:
    parts = split_top_level_args(_directive_args(s, "#modeagg"))
    if len(parts) != 3:
        raise ValueError(f"invalid #modeagg declaration: {s}")
    function, atoms = parse_aggregate_spec(parts[1])
    balance = parts[2].strip()
    if balance not in {"balanced", "unbalanced"}:
        raise ValueError(f"invalid #modeagg balance: {s}")
    return AggregateDeclaration(
        _parse_recall(parts[0]),
        function,
        atoms,
        balance == "unbalanced",
    )


def _get_operator_declaration(s: str, name: str) -> OperatorDeclaration:
    parts = split_top_level_args(_directive_args(s, name))
    if len(parts) != 2:
        raise ValueError(f"invalid {name} declaration: {s}")
    return OperatorDeclaration(_parse_recall(parts[0]), parts[1].strip())


def _directive_args(line: str, name: str) -> str:
    line = line.strip()
    if not line.startswith(f"{name}(") or not line.endswith(")."):
        raise ValueError(f"invalid directive: {line}")
    return line[len(name) + 1 : -2]


def _parse_recall(raw: str) -> int:
    raw = raw.strip()
    return -1 if raw == "*" else int(raw)


def _strip_outer_braces(value: str) -> str:
    value = value.strip()
    if not (value.startswith("{") and value.endswith("}")):
        raise ValueError(f"expected braced value: {value}")
    return value[1:-1].strip()


def read_program(filename: str):
    """
    Read the inductive task from file.
    """
    bg: "list[str]" = []
    pe: "list[Example]" = []
    ne: "list[Example]" = []
    lbh: "list[ModeDeclaration]" = []
    lbb: "list[ModeDeclaration]" = []
    aggregates: list[AggregateDeclaration] = []
    comparisons: list[OperatorDeclaration] = []
    arithmetic: list[OperatorDeclaration] = []

    for line in Path(filename).read_text(encoding="utf-8").splitlines():
        lc = line.rstrip().lstrip()
        if not lc or lc.startswith("%"):
            continue

        if lc.startswith("#modeh"):
            res = _get_mode_declaration(lc, True)
            md = ModeDeclaration(res, True)
            if md not in lbh:
                lbh.append(md)
        elif lc.startswith("#modeb"):
            res = _get_mode_declaration(lc, False)
            md = ModeDeclaration(res, False)
            if md not in lbb:
                lbb.append(md)
        elif lc.startswith("#pos"):
            res = _get_pos_neg_examples(lc)
            ex = Example(res, True)
            if ex not in pe:
                pe.append(ex)
        elif lc.startswith("#neg"):
            res = _get_pos_neg_examples(lc)
            ex = Example(res, False)
            if ex not in ne:
                ne.append(ex)
        elif lc.startswith("#modeagg"):
            aggregate = _get_aggregate_declaration(lc)
            if aggregate not in aggregates:
                aggregates.append(aggregate)
        elif lc.startswith("#modecmp"):
            comparison = _get_operator_declaration(lc, "#modecmp")
            if comparison not in comparisons:
                comparisons.append(comparison)
        elif lc.startswith("#modearith"):
            operator = _get_operator_declaration(lc, "#modearith")
            if operator not in arithmetic:
                arithmetic.append(operator)
        else:
            bg.append(lc)

    return Program(bg, pe, ne, lbh, lbb, aggregates, comparisons, arithmetic)
