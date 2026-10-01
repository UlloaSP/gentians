import re
from collections.abc import Iterator
from dataclasses import dataclass

from .grammar import SourceError, directive_name

_COMMENT_MARKER = re.compile(r"%\*|\*%|%")


@dataclass(frozen=True, slots=True)
class Statement:
    text: str
    line: int
    directive: str | None


def _comment_end(source: str, offset: int) -> tuple[int, bool]:
    """Skip one comment; line comments also apply inside nested blocks."""
    if not source.startswith("%*", offset):
        end = source.find("\n", offset + 1)
        return (len(source) if end < 0 else end + 1), True
    depth = 1
    offset += 2
    while match := _COMMENT_MARKER.search(source, offset):
        marker = match[0]
        offset = match.end()
        if marker == "%*":
            depth += 1
        elif marker == "*%":
            depth -= 1
            if not depth:
                return offset, True
        else:
            end = source.find("\n", offset)
            if end < 0:
                break
            offset = end + 1
    return len(source), False


def lex(source: str) -> Iterator[Statement]:
    """Yield complete statements in source order, retaining their start lines."""
    buffer: list[str] = []
    expected: list[str] = []
    line = 1
    start_line = 1
    quoted = False
    escaped = False
    annotated_statement = False
    pairs = {"(": ")", "[": "]", "{": "}"}

    def next_significant(offset: int) -> str:
        while offset < len(source):
            if source[offset].isspace():
                offset += 1
            elif source[offset] == "%":
                offset, closed = _comment_end(source, offset)
                if not closed:
                    return ""
            else:
                return source[offset]
        return ""

    def emit(text: str) -> Statement:
        nonlocal buffer, annotated_statement
        if text.startswith("#script"):
            raise SourceError(
                start_line, "#script blocks are not supported in task files"
            )
        buffer = []
        annotated_statement = False
        return Statement(text, start_line, directive_name(text))

    index = 0
    while index < len(source):
        char = source[index]
        if not quoted and char == "%":
            end, closed = _comment_end(source, index)
            newlines = source.count("\n", index, end)
            line += newlines
            if buffer:
                if newlines:
                    buffer.append("\n" * newlines)
                elif source.startswith("%*", index) and not buffer[-1].isspace():
                    buffer.append(" ")
            if not closed:
                raise SourceError(line, "unterminated block comment")
            index = end
            continue
        index += 1
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
        if char in pairs:
            expected.append(pairs[char])
            continue
        if char in ")]}":
            if not expected or expected.pop() != char:
                raise SourceError(line, f"unmatched {char}")
            if annotated_statement and not expected and char == "]":
                yield emit("".join(buffer).strip())
            continue
        if char != "." or expected:
            continue
        previous = source[index - 2] if index > 1 else ""
        following = source[index] if index < len(source) else ""
        if previous == "." or following == ".":
            continue
        text = "".join(buffer).strip()
        if text.startswith((":~", "#heuristic", "#external")) and next_significant(index) == "[":
            annotated_statement = True
            continue
        yield emit(text)

    if quoted:
        raise SourceError(start_line, "unterminated string")
    if expected:
        raise SourceError(start_line, f"unclosed delimiter, expected {expected[-1]}")
    if "".join(buffer).strip():
        raise SourceError(start_line, "statement must end with '.'")
