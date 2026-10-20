"""Frame ILASP declarations; delegate actual ASP syntax to Clingo."""

from dataclasses import dataclass
from pathlib import Path
import re
import warnings

import clingo
from clingo import ast

_SCRIPT = re.compile(r"#(?:ilasp_script|script)\b")


def parse_asp(source: str) -> tuple[ast.AST, ...]:
    nodes: list[ast.AST] = []
    errors: list[str] = []
    try:
        ast.parse_string(source, nodes.append, logger=lambda _, message: errors.append(message))
    except RuntimeError as error:
        raise ValueError("\n".join(errors) or str(error)) from None
    return tuple(n for n in nodes if n.ast_type not in {ast.ASTType.Program, ast.ASTType.Comment})


def _tokens(source: str, *, scripts: bool = False):
    """Yield meaningful characters, treating strings/comments as indivisible tokens."""
    i = 0
    while i < len(source):
        start = i
        script = _SCRIPT.match(source, i) if scripts and source[i] == "#" else None
        if script:
            end = re.search(r"(?m)^[ \t]*#end\s*\.", source[i + len(script[0]):])
            if end is None:
                raise ValueError(f"unterminated {script[0]} block")
            i += len(script[0]) + end.end()
            yield start, i, " "
        elif source.startswith("%*", i):
            depth = 1
            i += 2
            while depth and i < len(source):
                if source.startswith("%*", i):
                    depth += 1
                    i += 2
                elif source.startswith("*%", i):
                    depth -= 1
                    i += 2
                elif source[i] == "%":
                    end = source.find("\n", i)
                    i = len(source) if end < 0 else end
                else:
                    i += 1
            if depth:
                raise ValueError("unterminated ASP block comment")
            yield start, i, " "
        elif source[i] == "%":
            end = source.find("\n", i)
            i = len(source) if end < 0 else end
            yield start, i, " "
        elif source[i] == '"':
            i += 1
            while i < len(source) and source[i] != '"':
                i += 2 if source[i] == "\\" else 1
            if i >= len(source):
                raise ValueError("unterminated ASP string")
            i += 1
            yield start, i, source[start:i]
        else:
            i += 1
            yield start, i, source[start:i]


def split_fields(source: str) -> tuple[str, ...]:
    parts, stack, begin = [], [], 0
    for start, end, token in _tokens(source):
        if token in ("(", "[", "{"):
            stack.append(token)
        elif token in (")", "]", "}"):
            if not stack or stack.pop() != {")": "(", "]": "[", "}": "{"}[token]:
                raise ValueError("unbalanced ILASP declaration")
        elif token == "," and not stack:
            parts.append(source[begin:start].strip())
            begin = end
    if stack:
        raise ValueError("unbalanced ILASP declaration")
    parts.append(source[begin:].strip())
    return tuple(parts)


def _meta_source(source: str) -> tuple[str, dict[str, str]]:
    prefix = "ilaspmeta_"
    while prefix in source:
        prefix += "x_"
    names: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        name = prefix + match[1]
        names[name] = match[1]
        return name + "("

    parts, plain = [], []

    def flush() -> None:
        parts.append(re.sub(r"(?<![\w])#?([A-Z][A-Za-z_0-9]*)\s*\(", replace, "".join(plain)))
        plain.clear()

    for _, _, token in _tokens(source):
        if token.startswith('"'):
            flush()
            parts.append(token)
        else:
            plain.append(token)
    flush()
    source = "".join(parts)
    lexemes = list(re.finditer(r'"(?:[^"\\]|\\.)*"|:-|:~|#[a-z_]+|#?[A-Za-z_][A-Za-z_0-9]*|\d+|[^\s]', source))
    stack: list[tuple[str, bool, bool]] = []
    parts, begin = [], 0
    for i, match in enumerate(lexemes):
        token = match[0]
        previous = lexemes[i - 1][0] if i else ""
        following = lexemes[i + 1][0] if i + 1 < len(lexemes) else ""
        if token in {"(", "[", "{"}:
            aggregate = token == "{" and previous in {"#count", "#sum", "#min", "#max", "#sum+", "#minimize", "#maximize"}
            stack.append((token, aggregate, aggregate))
        elif token in {")", "]", "}"}:
            if stack:
                stack.pop()
        elif token in {":", ";"} and stack and stack[-1][1]:
            stack[-1] = (stack[-1][0], True, token == ";")
        elif (re.fullmatch(r"#?[A-Z][A-Za-z_0-9]*", token)
              and not any(frame[0] in {"(", "["} or frame[2] for frame in stack)
              and previous in {"", ":-", ":~", ";", ",", "{", ":", "not", "|"}
              and following in {"", ":-", ",", ";", ".", ":", "}", "|"}):
            original = token.removeprefix("#")
            name = prefix + original
            names[name] = original
            parts.extend((source[begin:match.start()], name))
            begin = match.end()
    parts.append(source[begin:])
    return "".join(parts), names


def parse_candidate(source: str) -> tuple[tuple[ast.AST, ...], dict[str, str]]:
    source, names = _meta_source(source)
    return parse_asp(source), names


def render_candidate(node: ast.AST, names: dict[str, str]) -> str:
    source = str(node)
    if not names:
        return source
    # Function names are restored outside strings; a string can contain the
    # same spelling without denoting a predicate variable.
    parts, plain = [], []

    def flush() -> None:
        parts.append(re.sub(r"\b[A-Za-z_][A-Za-z_0-9]*\b",
                            lambda m: "#" + names[m[0]] if m[0] in names else m[0], "".join(plain)))
        plain.clear()

    for _, _, token in _tokens(source):
        if token.startswith('"'):
            flush()
            parts.append(token)
        else:
            plain.append(token)
    flush()
    return "".join(parts)


def statements(source: str) -> tuple[str, ...]:
    # PyLASP is a search driver. Like ILASP -s/-st, generation does not execute it.
    clean = "".join(token for _, _, token in _tokens(source, scripts=True))
    result, stack, begin, i = [], [], 0, 0
    tokens = list(_tokens(clean))
    while i < len(tokens):
        start, end, token = tokens[i]
        if token in ("(", "[", "{"):
            stack.append(token)
        elif token in (")", "]", "}"):
            if not stack or stack.pop() != {")": "(", "]": "[", "}": "{"}[token]:
                raise ValueError("unbalanced task statement")
        elif token == "." and not stack:
            if clean[start:start + 2] == "..":
                i += 2
                continue
            fragment = clean[begin:end].strip()
            # The period of a weak constraint precedes its weight annotation.
            if re.match(r"(?:\d+\s*~\s*)?:~", fragment):
                j = end
                while j < len(clean) and clean[j].isspace():
                    j += 1
                if j >= len(clean) or clean[j] != "[":
                    raise ValueError("weak constraint is missing its weight annotation")
                annotation = next((e for s, e, t in tokens[i + 1:] if s >= j and t == "]"), None)
                if annotation is None:
                    raise ValueError("unterminated weak constraint annotation")
                end = annotation
                while i + 1 < len(tokens) and tokens[i + 1][0] < end:
                    i += 1
            result.append(clean[begin:end].strip())
            begin = end
        i += 1
    if stack or clean[begin:].strip():
        raise ValueError(f"unterminated task statement: {clean[begin:].strip()[:100]}")
    return tuple(result)


@dataclass(frozen=True)
class Mode:
    kind: str
    recall: int
    source: str
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class Task:
    modes: tuple[Mode, ...]
    constants: tuple[tuple[str, str], ...]
    predicates: tuple[tuple[str, str, int], ...]
    weights: tuple[str, ...]
    limits: tuple[tuple[str, int], ...]
    bias: tuple[str, ...]
    explicit: tuple[tuple[int, str], ...]
    background: tuple[str, ...]
    dmhv: bool = False


_LEARNING = {"pos", "neg", "opt", "brave_ordering", "cautious_ordering", "optimal_ordering", "max_penalty", "inject"}
_LIMITS = {"maxv", "maxp", "maxhl", "minhl"}


def parse_task(source: str) -> Task:
    modes, constants, predicates, weights, limits, bias, explicit, background = ([] for _ in range(8))
    dmhv = False
    for statement in statements(source):
        weighted = re.fullmatch(r"(\d+)\s*~\s*(.*)", statement, re.S)
        if weighted:
            cost, rule = int(weighted[1]), weighted[2]
            if len(parse_candidate(rule)[0]) != 1:
                raise ValueError(f"expected one explicit rule with nonnegative cost: {statement}")
            explicit.append((cost, rule))
            continue
        match = re.fullmatch(r"#([a-z_]+)(?:\s*\((.*)\))?\s*\.", statement, re.S)
        if not match:
            background.append(statement)
            continue
        name, payload = match[1], match[2]
        fields = split_fields(payload) if payload is not None else ()
        if name in {"modeh", "modeha", "modeb", "modec", "modeo", "modem"}:
            args = list(fields)
            if name == "modem" and (not args or not re.fullmatch(r"\d+", args[0])):
                raise ValueError("#modem requires its cost as the first argument")
            recall = int(args.pop(0)) if args and re.fullmatch(r"-?\d+", args[0]) else 0
            if not 1 <= len(args) <= 2 or recall < 0:
                raise ValueError(f"invalid mode declaration: {statement}")
            options = ()
            if len(args) == 2:
                if not args[1].startswith("(") or not args[1].endswith(")"):
                    raise ValueError(f"invalid mode options: {statement}")
                options = split_fields(args[1][1:-1])
                if any(not re.fullmatch(r"[a-z][A-Za-z_0-9]*", option) for option in options):
                    raise ValueError(f"invalid mode option: {statement}")
                for option in dict.fromkeys(options):
                    if option not in {"positive", "negative", "symmetric", "anti_reflexive", "non_recursive"}:
                        warnings.warn(f'unknown constraint in mode declaration: "{option}"', UserWarning, stacklevel=2)
            modes.append(Mode(name, recall, args[0], options))
        elif name == "constant" and len(fields) == 2:
            constants.append((fields[0], fields[1]))
        elif name == "predicate" and len(fields) == 2:
            signature = re.fullmatch(r"([a-z][A-Za-z_0-9]*)\s*/\s*(\d+)", fields[1])
            if signature is None:
                raise ValueError(f"invalid predicate schema: {statement}")
            predicates.append((fields[0], signature[1], int(signature[2])))
        elif name == "weight" and len(fields) == 1:
            weights.append(fields[0])
        elif name in _LIMITS and len(fields) == 1:
            limits.append((name, int(fields[0])))
        elif name == "bias" and len(fields) == 1:
            if not re.fullmatch(r'"(?:\\.|[^"\\])*"', fields[0], re.S):
                raise ValueError("#bias requires an ASP string")
            # ILASP's lexer accepts literal newlines and only unescapes quotes.
            # Parsing this as a Clingo string changes backslashes in embedded ASP/Python.
            value = fields[0][1:-1]
            while '\\"' in value:
                value = value.replace('\\"', '"')
            bias.append(value)
        elif name == "disallow_multiple_head_variables" and not fields:
            dmhv = True
        elif name in _LEARNING:
            # These configure whole-program learning, not clause generation.
            continue
        elif name in {"const", "show", "external", "project", "defined", "heuristic", "edge", "minimize", "maximize"}:
            background.append(statement)
        else:
            raise ValueError(f"unsupported task directive: {statement}")
    return Task(tuple(modes), tuple(constants), tuple(predicates), tuple(weights), tuple(limits),
                tuple(bias), tuple(explicit), tuple(background), dmhv)


def read_task(path: str | Path) -> Task:
    path = Path(path)
    active: set[Path] = set()

    def read(current: Path) -> str:
        current = current.resolve()
        if current in active:
            raise ValueError(f"cyclic #include: {current}")
        active.add(current)
        chunks = []
        for statement in statements(current.read_text(encoding="utf-8-sig")):
            include = re.fullmatch(r'#include\s*("(?:[^"\\]|\\.)*")\s*\.', statement)
            chunks.append(read(current.parent / clingo.parse_term(include[1]).string) if include else statement)
        active.remove(current)
        return "\n".join(chunks)

    return parse_task(read(path))
