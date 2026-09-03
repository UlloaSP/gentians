import re

TASK_GRAMMAR = r"""
task                = { statement } ;
statement           = directive | asp-statement ;
directive           = limit | mode | example | constant | invention
                    | bias | metarule | predicate-pool | metarule-mode ;
limit               = ("#maxv" | "#maxbl" | "#minhl" | "#maxhl" | "#maxpl")
                      "(" (integer | "*") ")" "." ;
mode                = ("#modeh" | "#modeha" | "#modehd" | "#modeb"
                    | "#modec" | "#modeagg" | "#modearith")
                      "(" mode-payload ")" "." ;
example             = ("#pos" | "#neg") "(" asp-set "," asp-set
                      [ "," asp-set ] ")" "." ;
constant            = "#constant" "(" identifier "," ground-term ")" "." ;
invention           = "#invent" "(" recall "," atom-template ")" "." ;
bias                = "#bias" "(" quoted-asp-program ")" "." ;
metarule            = "#metarule" "(" identifier "," quoted-asp-program ")" "." ;
predicate-pool      = "#predicate" "(" identifier "," signature ")" "." ;
metarule-mode       = "#modem" "(" identifier "(" signature-list ")" ")" "." ;
asp-statement       = clingo-asp-statement ;
"""

DIRECTIVE_NAMES = frozenset(
    {
        "#bias",
        "#constant",
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
