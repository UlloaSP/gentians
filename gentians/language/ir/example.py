from dataclasses import dataclass

from clingo import ast

from ..asp import AspProgram, parse_example_fields, render_literals, render_program


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
        values: tuple[str, str] | tuple[str, str, str],
        positive: bool,
        line: int = 1,
    ) -> "Example":
        context_source = values[2].strip() if len(values) == 3 else ""
        if context_source and not context_source.endswith((".", "]")):
            context_source += "."
        try:
            included, excluded, context = parse_example_fields(
                values[0], values[1], context_source
            )
        except ValueError as error:
            raise ValueError(f"line {line}: invalid example: {error}") from None
        if any(statement.ast_type != ast.ASTType.Rule for statement in context):
            invalid = next(
                statement for statement in context if statement.ast_type != ast.ASTType.Rule
            )
            raise ValueError(
                f"line {line}: unsupported statement in example context: "
                f"{invalid.ast_type}"
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
