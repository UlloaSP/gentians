from dataclasses import dataclass

from clingo import ast

from ..asp import AspProgram, parse_example_fields, render_literals, render_program
from ..grammar import SourceError


@dataclass(frozen=True, slots=True)
class Example:
    """Included, excluded, and contextual atoms from one example."""

    included: tuple[ast.AST, ...]
    excluded: tuple[ast.AST, ...]
    context: AspProgram
    positive: bool

    @classmethod
    def parse(
        cls,
        values: tuple[tuple[str, int, int], ...],
        positive: bool,
    ) -> "Example":
        context_source, context_line, context_column = values[2] if len(values) == 3 else ("", 1, 1)
        if context_source and not context_source.endswith((".", "]")):
            context_source += "."
        try:
            included, excluded, context = parse_example_fields(
                values[0], values[1], (context_source, context_line, context_column)
            )
        except ValueError as error:
            detail = error.message if isinstance(error, SourceError) else str(error)
            if isinstance(error, SourceError):
                raise SourceError(error.line, f"invalid example: {detail}", column=error.column) from None
            raise ValueError(f"invalid example: {detail}") from None
        if any(statement.ast_type != ast.ASTType.Rule for statement in context):
            invalid = next(
                statement for statement in context if statement.ast_type != ast.ASTType.Rule
            )
            raise SourceError(
                context_line + invalid.location.begin.line - 1, "unsupported statement in example context: "
                f"{invalid.ast_type}", column=invalid.location.begin.column + (context_column - 1 if invalid.location.begin.line == 1 else 0)
            )
        return cls(
            included,
            excluded,
            context,
            positive,
        )

    @property
    def included_text(self) -> str:
        return render_literals(self.included)

    @property
    def excluded_text(self) -> str:
        return render_literals(self.excluded)

    @property
    def context_text(self) -> str:
        return "\n".join(render_program(self.context))
