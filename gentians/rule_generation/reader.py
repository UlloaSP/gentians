from .parser import split_top_level_args
from .program import Example, ModeDeclaration, Program


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


def _directive_args(line: str, name: str) -> str:
    line = line.strip()
    if not line.startswith(f"{name}(") or not line.endswith(")."):
        raise ValueError(f"invalid directive: {line}")
    return line[len(name) + 1 : -2]


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

    fp = open(filename, "r")
    lines = fp.read().splitlines()
    fp.close()

    for line in lines:
        lc = line.rstrip().lstrip()

        if lc.startswith("#modeh"):
            res = _get_mode_declaration(lc, True)
            if len(res) > 0:
                md = ModeDeclaration(res, True)
                if md not in lbh:
                    lbh.append(md)
        elif lc.startswith("#modeb"):
            res = _get_mode_declaration(lc, False)
            if len(res) > 0:
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
                ne.append(Example(res, False))
        else:
            bg.append(lc)

    return Program(bg, pe, ne, lbh, lbb)
