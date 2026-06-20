import re

from .program import Example, ModeDeclaration, Program


def _get_mode_declaration(
    s: str, for_head: bool = False
) -> "tuple[str,str,str] | tuple[str,str,str,str]":
    if for_head:
        regex = r"#modeh\((\d+|\*),(.*),(\d+)\)."
    else:
        regex = r"#modeb\((\d+|\*),(.*),(\d+),(positive|negative)\)."
    return re.findall(regex, s)[0]


def _get_pos_neg_examples(s: str) -> "tuple[str,str] | tuple[str,str,str]":
    # TODO: improve this
    regex3 = r"^#(?:pos|neg)\(\{([^{}]*)\},\{([^{}]*)\},\{([^{}]*)\}\)\.$"
    regex2 = r"^#(?:pos|neg)\(\{([^{}]*)\},\{([^{}]*)\}\)\.$"
    res = re.findall(regex3, s)
    if len(res) > 0:
        return res[0]
    else:
        res = re.findall(regex2, s)
        return res[0]


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
            res = _get_mode_declaration(lc.replace(" ", ""), True)
            if len(res) > 0:
                md = ModeDeclaration(res, True)
                if md not in lbh:
                    lbh.append(md)
        elif lc.startswith("#modeb"):
            res = _get_mode_declaration(lc.replace(" ", ""), False)
            if len(res) > 0:
                md = ModeDeclaration(res, False)
                if md not in lbb:
                    lbb.append(md)
        elif lc.startswith("#pos"):
            lc = lc.replace(" ", "")
            res = _get_pos_neg_examples(lc)
            ex = Example(res, True)
            if ex not in pe:
                pe.append(ex)
        elif lc.startswith("#neg"):
            lc = lc.replace(" ", "")
            res = _get_pos_neg_examples(lc)
            ex = Example(res, False)
            if ex not in ne:
                ne.append(Example(res, False))
        else:
            bg.append(lc)

    return Program(bg, pe, ne, lbh, lbb)
