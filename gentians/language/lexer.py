import re
from collections.abc import Iterator
from dataclasses import dataclass, field

from .grammar import DELIMITERS, SourceError, directive_name, quoted_end, source_position

_COMMENT_MARKER = re.compile(r"%\*|\*%|%")
_TEXT_MARKER = re.compile(r'["%]')


@dataclass(frozen=True, slots=True, eq=False)
class Statement:
    """A framed source token; equality uses token identity, not partial metadata."""

    line: int
    directive: str | None
    source: str = field(repr=False, compare=False)
    start: int = field(repr=False, compare=False)
    end: int = field(repr=False, compare=False)
    column: int = field(repr=False, compare=False)

    @property
    def text(self) -> str:
        """Normalize only payloads requested by declaration parsers."""
        chunks: list[str] = []
        span_start = index = self.start
        while match := _TEXT_MARKER.search(self.source, index, self.end):
            index = match.start()
            if match[0] == '"':
                index = quoted_end(self.source, index)
                continue
            if span_start < index:
                chunks.append(self.source[span_start:index])
            index, _closed = _comment_end(self.source, index)
            newlines = self.source.count("\n", match.start(), index)
            if newlines:
                chunks.append("\n" * newlines)
            elif chunks and not chunks[-1][-1].isspace():
                chunks.append(" ")
            span_start = index
        chunks.append(self.source[span_start:self.end])
        return "".join(chunks).strip()

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
    """Frame source spans without copying background payloads."""
    expected: list[tuple[str, int]] = []
    line = start_line = column = start_column = 1
    column_index = 0
    start: int | None = None
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

    def emit(end: int) -> Statement:
        nonlocal start, annotated
        assert start is not None
        if source.startswith("#script", start):
            raise SourceError(start_line, "#script blocks are not supported in task files")
        result = Statement(start_line, directive_name(source, start, end), source, start, end, start_column)
        start = None
        annotated = False
        return result

    index = 0
    while index < size:
        char = source[index]
        if char == "%":
            end, closed = _comment_end(source, index)
            if not closed:
                error_line, error_column = source_position(source, index)
                raise SourceError(error_line, "unterminated block comment", column=error_column)
            newlines = source.count("\n", index, end)
            line += newlines
            if newlines:
                column, column_index = 1, source.rfind("\n", index, end) + 1
            index = end
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
            start, start_line, start_column = index, line, column
        if char == '"':
            try:
                end = quoted_end(source, index)
            except ValueError:
                error_line, error_column = source_position(source, index)
                raise SourceError(error_line, "unterminated string", column=error_column) from None
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
            expected.append((DELIMITERS[char], index - 1))
            continue
        if char in ")]}":
            if not expected or expected.pop()[0] != char:
                error_column = column + len(source[column_index:index - 1].encode("utf-8"))
                raise SourceError(line, f"unmatched {char}", column=error_column)
            if annotated and not expected and char == "]":
                yield emit(index)
            continue
        if char != "." or expected:
            continue
        previous = source[index - 2] if index > 1 else ""
        following = source[index] if index < size else ""
        if previous == "." or following == ".":
            continue
        if source.startswith((":~", "#heuristic", "#external"), start) and next_significant(index) == "[":
            annotated = True
            continue
        yield emit(index)

    if expected:
        delimiter, offset = expected[-1]
        error_line, error_column = source_position(source, offset)
        raise SourceError(error_line, f"unclosed delimiter, expected {delimiter}", column=error_column)
    if start is not None:
        raise SourceError(start_line, "statement must end with '.'")
