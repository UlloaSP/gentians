from dataclasses import dataclass

from .head_template import HeadTemplate


@dataclass(frozen=True, slots=True)
class HeadDeclaration:
    recall: int
    template: HeadTemplate

    def __post_init__(self) -> None:
        if self.recall != 1:
            raise ValueError("complete head modes require recall 1")
    @property
    def width(self) -> int:
        return self.template.width
