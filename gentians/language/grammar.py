import re

TASK_GRAMMAR = r"""
task                = { statement } ;
statement           = directive | asp-statement ;
directive           = limit | mode | example | constant | invention ;
limit               = ("#maxv" | "#maxbl" | "#minhl" | "#maxhl" | "#maxpl")
                      "(" (integer | "*") ")" "." ;
mode                = ("#modeh" | "#modeha" | "#modehd" | "#modeb"
                    | "#modec")
                      "(" mode-payload ")" "." ;
example             = ("#pos" | "#neg") "(" asp-set "," asp-set
                      [ "," asp-set ] ")" "." ;
constant            = "#constant" "(" identifier "," ground-term ")" "." ;
invention           = "#invent" "(" recall "," atom-template ")" "." ;
asp-statement       = clingo-asp-statement ;
"""

# Retired names remain recognizable only to report explicit parser errors.
DIRECTIVE_NAMES = frozenset(
    {
        "#bias",
        "#constant",
        "#edge",
        "#invent",
        "#maxbl",
        "#maxhl",
        "#maxpl",
        "#maxv",
        "#metarule",
        "#minhl",
        "#modeagg",
        "#modearith",
        "#modeb",
        "#modec",
        "#modecmp",
        "#modeh",
        "#modeha",
        "#modehd",
        "#modeedge",
        "#modem",
        "#neg",
        "#pos",
        "#predicate",
    }
)

_DIRECTIVE_NAME = re.compile(r"^(#[a-z][A-Za-z0-9_]*)\b")


def directive_name(statement: str) -> str | None:
    match = _DIRECTIVE_NAME.match(statement.lstrip())
    if match is None or match.group(1) not in DIRECTIVE_NAMES:
        return None
    return match.group(1)
