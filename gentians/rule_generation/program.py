from dataclasses import dataclass, field

from .aggregate_declaration import AggregateDeclaration
from .example import Example
from .mode_declaration import ModeDeclaration
from .operator_declaration import OperatorDeclaration
from .parser import fragment_atoms

Signature = tuple[str, int]


@dataclass(slots=True)
class Program:
    """
    Class for input programs.
    """

    background: "list[str]"
    positive_examples: list[Example]
    negative_examples: list[Example]
    language_bias_head: list[ModeDeclaration]
    language_bias_body: list[ModeDeclaration]
    aggregate_modes: list[AggregateDeclaration] = field(default_factory=list)
    comparison_modes: list[OperatorDeclaration] = field(default_factory=list)
    arithmetic_modes: list[OperatorDeclaration] = field(default_factory=list)
    generated_language_bias_body: set[Signature] = field(default_factory=set)
    invented_predicates: tuple[Signature, ...] = ()

    def complete_language_bias(self, recall: int = 1) -> None:
        """
        Complete missing language bias from observed atoms.
        """
        signatures = _observed_signatures(self)
        if not self.language_bias_head and not self.language_bias_body:
            for name, arity in signatures:
                md = ModeDeclaration((str(recall), name, str(arity)), True)
                if md not in self.language_bias_head:
                    self.language_bias_head.append(md)

        if not self.language_bias_body:
            for (name, arity), seen_negative in signatures.items():
                md = ModeDeclaration(
                    (str(recall), name, str(arity), "positive"), False
                )
                if md not in self.language_bias_body:
                    self.language_bias_body.append(md)
                    self.generated_language_bias_body.add((name, arity))
                if seen_negative:
                    md = ModeDeclaration(
                        (str(recall), name, str(arity), "negative"), False
                    )
                    if md not in self.language_bias_body:
                        self.language_bias_body.append(md)
                        self.generated_language_bias_body.add((name, arity))


def _observed_signatures(program: Program) -> dict[Signature, bool]:
    signatures: dict[Signature, bool] = {}
    for rule in program.background:
        _collect_signatures(rule, signatures)
    for example in [*program.positive_examples, *program.negative_examples]:
        _collect_signatures(example.included, signatures)
        _collect_signatures(example.excluded, signatures, force_negative=True)
        _collect_signatures(example.context, signatures)
    return signatures


def _collect_signatures(
    fragment: str,
    signatures: dict[Signature, bool],
    force_negative: bool = False,
) -> None:
    for name, arguments, negative in fragment_atoms(fragment):
        _mark_signature(signatures, (name, len(arguments)), force_negative or negative)


def _mark_signature(
    signatures: dict[Signature, bool],
    signature: Signature,
    seen_negative: bool,
) -> None:
    signatures[signature] = signatures.get(signature, False) or seen_negative
