from dataclasses import dataclass, field

from .parser import Predicate, fragment_atoms


@dataclass(init=False, slots=True)
class Example:
    """
    Class for examples in the input file.
    Members of the tuple, in order: included, excluded, and context.
    """

    included: str
    excluded: str
    context: str
    positive: bool

    def __init__(self, s: "tuple[str,str] | tuple[str,str,str]", positive: bool) -> None:
        self.included = s[0]
        self.excluded = s[1]
        self.context = s[2] if len(s) == 3 else ""
        self.positive = positive


@dataclass(init=False, slots=True)
class ModeDeclaration:
    """
    Class for mode declarations in the input file.
    Members of the tuple, in order: recall, name, arity, and positive/negative.
    """

    recall: int
    name: str
    arity: int
    positive: bool
    head: bool

    def __init__(self, s: "tuple[str,str,str] | tuple[str,str,str,str]", head: bool) -> None:
        if s[0] == "*":
            self.recall = -1
        else:
            self.recall = int(s[0])
        self.name = s[1]
        self.arity = int(s[2])
        self.positive = True
        if len(s) == 4:
            if s[3] == "negative":
                self.positive = False
        self.head = head


@dataclass(frozen=True, slots=True)
class AggregateDeclaration:
    recall: int
    function: str
    atoms: tuple[Predicate, ...]
    unbalanced: bool


@dataclass(frozen=True, slots=True)
class OperatorDeclaration:
    recall: int
    operator: str


@dataclass(slots=True)
class Program:
    """
    Class for input programs.
    """

    background: "list[str]"
    positive_examples: "list[Example]"
    negative_examples: "list[Example]"
    language_bias_head: "list[ModeDeclaration]"
    language_bias_body: "list[ModeDeclaration]"
    aggregate_modes: list[AggregateDeclaration] = field(default_factory=list)
    comparison_modes: list[OperatorDeclaration] = field(default_factory=list)
    arithmetic_modes: list[OperatorDeclaration] = field(default_factory=list)

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
                if seen_negative:
                    md = ModeDeclaration(
                        (str(recall), name, str(arity), "negative"), False
                    )
                    if md not in self.language_bias_body:
                        self.language_bias_body.append(md)

Signature = tuple[str, int]


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
