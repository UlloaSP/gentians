import re
from collections.abc import Iterator
from dataclasses import dataclass, field

from .grammar import DELIMITERS, SourceError, directive_name, quoted_end, source_position

_COMMENT_MARKER = re.compile(r"%\*|\*%|%")


@dataclass(frozen=True, slots=True)
class Statement:
    text: str
    line: int
    directive: str | None
    source: str = field(repr=False, compare=False)
    start: int = field(repr=False, compare=False)
    end: int = field(repr=False, compare=False)
    column: int = field(repr=False, compare=False)

    def locate_error(self, error: SourceError) -> SourceError:
        """Map a normalized fragment diagnostic back to its original source."""
        lines = self.text.split("\n")
        target = sum(len(part.encode("utf-8")) + 1 for part in lines[:error.line - 1])
        target += (error.column or 1) - 1
        index, consumed = self.start, 0
        previous = ""
        while index < self.end:
            if self.source[index] == "%":
                end, _closed = _comment_end(self.source, index)
                newlines = self.source.count("\n", index, end)
                padding = newlines or int(bool(previous) and not previous.isspace())
                consumed += padding
                previous = "\n" if newlines else " " if padding else previous
                index = end
                continue
            end = quoted_end(self.source, index) if self.source[index] == '"' else index + 1
            span = self.source[index:end]
            width = len(span.encode("utf-8"))
            if consumed + width > target:
                index += len(span.encode("utf-8")[:max(0, target - consumed)].decode("utf-8", errors="ignore"))
                break
            consumed += width
            previous = span[-1]
            index = end
        line, column = source_position(self.source, index)
        return SourceError(line, error.message, column=column)


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
    """Frame statements with text spans; read strings and comments in bulk."""
    chunks: list[str] = []
    expected: list[str] = []
    line = start_line = column = start_column = 1
    column_index = 0
    start: int | None = None
    span_start = 0
    annotated = False
    size = len(source)

    def next_significant(offset: int) -> str:
        while offset < size:
            if source[offset].isspace():
                offset += 1
            elif source[offset] == "%":
                offset, closed = _comment_end(source, offset)
                if not closed:
                    return ""
            else:
                return source[offset]
        return ""

    def emit(text: str, end: int) -> Statement:
        nonlocal chunks, start, annotated
        if text.startswith("#script"):
            raise SourceError(start_line, "#script blocks are not supported in task files")
        assert start is not None
        result = Statement(text, start_line, directive_name(text), source, start, end, start_column)
        chunks = []
        start = None
        annotated = False
        return result

    index = 0
    while index < size:
        char = source[index]
        if char == "%":
            end, closed = _comment_end(source, index)
            newlines = source.count("\n", index, end)
            line += newlines
            if newlines:
                column, column_index = 1, source.rfind("\n", index, end) + 1
            if start is not None:
                if span_start < index:
                    chunks.append(source[span_start:index])
                if newlines:
                    chunks.append("\n" * newlines)
                elif chunks and not chunks[-1][-1].isspace():
                    chunks.append(" ")
            if not closed:
                raise SourceError(line, "unterminated block comment")
            index = span_start = end
            continue
        if start is None:
            if char.isspace():
                index += 1
                if char == "\n":
                    line += 1
                    column, column_index = 1, index
                continue
            column += len(source[column_index:index].encode("utf-8"))
            column_index = index
            start, start_line, span_start, start_column = index, line, index, column
        if char == '"':
            try:
                end = quoted_end(source, index)
            except ValueError:
                raise SourceError(start_line, "unterminated string") from None
            newlines = source.count("\n", index, end)
            line += newlines
            if newlines:
                column, column_index = 1, source.rfind("\n", index, end) + 1
            index = end
            continue
        index += 1
        if char == "\n":
            line += 1
            column, column_index = 1, index
        if char in DELIMITERS:
            expected.append(DELIMITERS[char])
            continue
        if char in ")]}":
            if not expected or expected.pop() != char:
                error_column = column + len(source[column_index:index - 1].encode("utf-8"))
                raise SourceError(line, f"unmatched {char}", column=error_column)
            if annotated and not expected and char == "]":
                chunks.append(source[span_start:index])
                yield emit("".join(chunks).strip(), index)
            continue
        if char != "." or expected:
            continue
        previous = source[index - 2] if index > 1 else ""
        following = source[index] if index < size else ""
        if previous == "." or following == ".":
            continue
        chunks.append(source[span_start:index])
        span_start = index
        text = "".join(chunks).strip()
        if text.startswith((":~", "#heuristic", "#external")) and next_significant(index) == "[":
            annotated = True
            continue
        yield emit(text, index)

    if expected:
        raise SourceError(start_line, f"unclosed delimiter, expected {expected[-1]}")
    if start is not None:
        raise SourceError(start_line, "statement must end with '.'")
