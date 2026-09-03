from dataclasses import dataclass

from .grammar import directive_name


@dataclass(frozen=True, slots=True)
class Statement:
    text: str
    line: int
    directive: str | None


def lex(source: str) -> tuple[Statement, ...]:
    statements: list[Statement] = []
    buffer: list[str] = []
    expected: list[str] = []
    line = 1
    start_line = 1
    quoted = False
    escaped = False
    line_comment = False
    block_comment_depth = 0
    skip_block_end = False
    annotated_statement = False

    def next_significant(offset: int) -> str:
        while offset < len(source):
            if source[offset].isspace():
                offset += 1
            elif source.startswith("%*", offset):
                depth = 1
                offset += 2
                while offset < len(source) and depth:
                    if source.startswith("%*", offset):
                        depth += 1
                        offset += 2
                    elif source.startswith("*%", offset):
                        depth -= 1
                        offset += 2
                    else:
                        offset += 1
                if depth:
                    return ""
            elif source[offset] == "%":
                end = source.find("\n", offset + 1)
                if end < 0:
                    return ""
                offset = end + 1
            else:
                return source[offset]
        return ""

    def emit() -> None:
        nonlocal buffer, annotated_statement
        text = "".join(buffer).strip()
        if text:
            if text.lstrip().startswith("#script"):
                raise ValueError(
                    f"line {start_line}: #script blocks are not supported in task files"
                )
            statements.append(Statement(text, start_line, directive_name(text)))
        buffer = []
        annotated_statement = False

    for index, char in enumerate(source):
        if skip_block_end:
            skip_block_end = False
            continue
        if block_comment_depth:
            if char == "\n":
                line += 1
            elif char == "%" and source[index + 1 : index + 2] == "*":
                block_comment_depth += 1
            elif char == "*" and source[index + 1 : index + 2] == "%":
                block_comment_depth -= 1
                skip_block_end = True
                if not block_comment_depth and buffer and not buffer[-1].isspace():
                    buffer.append(" ")
            continue
        if line_comment:
            if char == "\n":
                line_comment = False
                line += 1
                if buffer and not buffer[-1].isspace():
                    buffer.append("\n")
            continue
        if not quoted and char == "%":
            if source[index + 1 : index + 2] == "*":
                block_comment_depth = 1
            else:
                line_comment = True
            continue
        if not buffer and char.isspace():
            if char == "\n":
                line += 1
            continue
        if not buffer:
            start_line = line
        buffer.append(char)
        if char == "\n":
            line += 1
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
            continue
        if char in "([{":
            expected.append({"(": ")", "[": "]", "{": "}"}[char])
            continue
        if char in ")]}":
            if not expected or expected.pop() != char:
                raise ValueError(f"line {line}: unmatched {char}")
            if annotated_statement and not expected and char == "]":
                emit()
            continue
        if char != "." or expected:
            continue
        previous = source[index - 1] if index else ""
        following = source[index + 1] if index + 1 < len(source) else ""
        if previous == "." or following == ".":
            continue
        prefix = "".join(buffer).lstrip()
        if prefix.startswith((":~", "#heuristic", "#external")) and next_significant(
            index + 1
        ) == "[":
            annotated_statement = True
            continue
        emit()

    if quoted:
        raise ValueError(f"line {start_line}: unterminated string")
    if block_comment_depth:
        raise ValueError(f"line {line}: unterminated block comment")
    if expected:
        raise ValueError(f"line {start_line}: unclosed delimiter, expected {expected[-1]}")
    if "".join(buffer).strip():
        raise ValueError(f"line {start_line}: statement must end with '.'")
    return tuple(statements)
