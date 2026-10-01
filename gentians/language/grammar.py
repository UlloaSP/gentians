import re

DELIMITERS = {"(": ")", "[": "]", "{": "}"}
_STRING_END = re.compile(r'\\[\s\S]|"')


def quoted_end(source: str, offset: int) -> int:
    """Return the end of a quoted span, or fail without interpreting ASP."""
    for match in _STRING_END.finditer(source, offset + 1):
        if match[0] == '"':
            return match.end()
    raise ValueError("unterminated string")


def source_position(source: str, offset: int) -> tuple[int, int]:
    start = source.rfind("\n", 0, offset) + 1
    return source.count("\n", 0, offset) + 1, len(source[start:offset].encode("utf-8")) + 1


def _directive_args(line: str, name: str) -> str:
    line = line.strip()
    if not line.startswith(f"{name}(") or not line.endswith(")."):
        raise ValueError(f"invalid directive: {line}")
    return line[len(name) + 1 : -2]


def _parse_recall(raw: str) -> int:
    raw = raw.strip()
    if raw == "*":
        return -1
    value = int(raw)
    if value < 1:
        raise ValueError("mode recall must be positive or unbounded")
    return value


def _strip_outer_braces(value: str) -> str:
    value = value.strip()
    if not (value.startswith("{") and value.endswith("}")):
        raise ValueError(f"expected braced value: {value}")
    return value[1:-1].strip()

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


class SourceError(ValueError):
    """Task diagnostic with source locations kept separate from quoted payloads."""

    def __init__(self, line: int, message: str, related_line: int | None = None, *, column: int | None = None) -> None:
        self.line = line
        self.message = message
        self.related_line = related_line
        self.column = column
        related = f" (related declaration on line {related_line})" if related_line else ""
        position = f" (column {column})" if column is not None else ""
        super().__init__(f"line {line}: {message}{related}{position}")
