import re
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import product
from typing import Literal, TypeAlias

from .term_binding import TermBinding

TermKind: TypeAlias = Literal[
    "variable",
    "constant",
    "fixed",
    "function",
    "tuple",
    "arithmetic",
]


@dataclass(frozen=True, slots=True)
class TermTemplate:
    """Recursive term syntax used by declarations and compiled modes."""

    kind: TermKind
    value: str = ""
    arguments: tuple["TermTemplate", ...] = ()
    type: str = ""
    direction: str = ""
    label: str = ""

    def __post_init__(self) -> None:
        if self.kind not in {
            "variable",
            "constant",
            "fixed",
            "function",
            "tuple",
            "arithmetic",
        }:
            raise ValueError(f"invalid term kind: {self.kind}")
        if self.kind in {"variable", "constant"}:
            if not re.fullmatch(r"[a-z][A-Za-z0-9_]*", self.type):
                raise ValueError(f"invalid mode argument type: {self.type}")
            if self.value or self.arguments:
                raise ValueError("mode placeholders cannot contain syntax")
        elif self.type or self.direction or self.label:
            raise ValueError("concrete terms cannot declare mode bindings")

        if self.kind == "variable":
            if self.direction not in {"", "input", "output", "any"}:
                raise ValueError("variables require input, output, or any direction")
            if self.label and not re.fullmatch(r"[a-z][A-Za-z0-9_]*", self.label):
                raise ValueError(f"invalid variable label: {self.label}")
        elif self.kind == "constant":
            if self.direction or self.label:
                raise ValueError("constant placeholders cannot have direction or label")
        elif self.kind == "fixed":
            if not self.value or self.arguments:
                raise ValueError("fixed terms require one rendered value")
        elif self.kind in {"function", "arithmetic"}:
            if not self.value or not self.arguments:
                raise ValueError(f"{self.kind} terms require an operator and arguments")
        elif self.kind == "tuple" and self.value:
            raise ValueError("tuple terms cannot have a name")

    @classmethod
    def variable(
        cls, type_name: str, direction: str, label: str = ""
    ) -> "TermTemplate":
        return cls("variable", type=type_name, direction=direction, label=label)

    @classmethod
    def constant(cls, type_name: str) -> "TermTemplate":
        return cls("constant", type=type_name)

    @classmethod
    def fixed(cls, value: str) -> "TermTemplate":
        return cls("fixed", value=value)

    def bindings(self, path: tuple[int, ...] = ()) -> tuple[TermBinding, ...]:
        if self.kind == "variable":
            return (TermBinding(path, self.type, self.direction, self.label),)
        return tuple(
            binding
            for index, argument in enumerate(self.arguments)
            for binding in argument.bindings((*path, index))
        )

    def constant_types(self) -> frozenset[str]:
        if self.kind == "constant":
            return frozenset((self.type,))
        return frozenset(
            type_name
            for argument in self.arguments
            for type_name in argument.constant_types()
        )

    def shape(self) -> tuple[object, ...]:
        if self.kind == "variable":
            return ("variable",)
        if self.kind == "fixed":
            return ("fixed", self.value)
        return (
            self.kind,
            self.value,
            tuple(argument.shape() for argument in self.arguments),
        )

    def concretizations(
        self, constants: dict[str, tuple[str, ...]]
    ) -> tuple["TermTemplate", ...]:
        if self.kind == "constant":
            return tuple(TermTemplate.fixed(value) for value in constants[self.type])
        if not self.arguments:
            return (self,)
        return tuple(
            TermTemplate(self.kind, self.value, arguments)
            for arguments in product(
                *(argument.concretizations(constants) for argument in self.arguments)
            )
        )

    def render(self, variables: Iterator[str]) -> str:
        if self.kind == "variable":
            return next(variables)
        if self.kind == "constant":
            raise ValueError(
                "constant placeholder must be concretized before rendering"
            )
        if self.kind == "fixed":
            return self.value
        rendered = tuple(argument.render(variables) for argument in self.arguments)
        if self.kind == "function":
            return f"{self.value}({','.join(rendered)})"
        if self.kind == "tuple":
            suffix = "," if len(rendered) == 1 else ""
            return f"({','.join(rendered)}{suffix})"
        if self.value == "abs":
            return f"|{rendered[0]}-{rendered[1]}|"
        return self.value.join(rendered)
