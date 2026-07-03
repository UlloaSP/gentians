from dataclasses import dataclass, field
import re
import sys

from clingo import ast

from ..asp.callbacks import RuleCallback
from .parser import extract_name_arity


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
    aggregation_function: str = ""
    aggregation_atoms: "list[tuple[str,int]]" = field(default_factory=list)
    arithmetic_operator: str = ""
    comparison_operator: str = ""

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
        self.aggregation_function = ""
        self.aggregation_atoms = []
        self.arithmetic_operator = ""
        self.comparison_operator = ""

    def add_aggregate(self, aggregate_str: str):
        """
        Add an aggregates function to the mode declaration.
        """
        # aggregate_str comes from Arguments.aggregates.
        pattern = r"(\w+)\(([^)]+)\)"
        match = re.match(pattern, aggregate_str)

        if match:
            name = match.group(1)
            if name not in ["count", "sum", "avg", "min", "max"]:
                print(
                    "\033[91m"
                    + "Error: "
                    + f"Error: Invalid aggregate function name: {name}"
                    + "\033[0m"
                )
                sys.exit(-1)
            self.aggregation_function = name
            pairs = re.findall(r"(\w+)/(\d+)", match.group(2))
            if pairs:
                for pair in pairs:
                    self.aggregation_atoms.append((pair[0], int(pair[1])))
        else:
            print(
                "\033[91m"
                + "Error: "
                + f"Error: Invalid aggregate function syntax: {aggregate_str}"
                + "\033[0m"
            )
            sys.exit(-1)

    def special_mode_declaration(self) -> bool:
        return any(
            [
                self.aggregation_function != "",
                self.arithmetic_operator != "",
                self.comparison_operator != "",
            ]
        )


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

    def auto_generate_language_bias(self, recall: int) -> None:
        """
        Automatically generate the language bias.
        """
        # cleanup the existing language bias: so I can run the examples with language bias
        # and just add a flag to ignore it and generating it automatically
        self.language_bias_head = [
            m for m in self.language_bias_head if m.special_mode_declaration()
        ]
        self.language_bias_body = [
            m for m in self.language_bias_body if m.special_mode_declaration()
        ]

        name_arity: dict[tuple[str, int], None] = {}

        r = RuleCallback()
        for rule in self.background:
            ast.parse_string(rule, r.process)
            for h in r.head + r.body:  # head and body
                name_arity.setdefault(extract_name_arity(h), None)

        for e in self.positive_examples + self.negative_examples:
            to_consider = [e.included, e.excluded]
            for s in to_consider:
                if len(s) > 0:
                    s = ":- " + s + "."
                    ast.parse_string(s, r.process)
                    for atom in r.body:
                        name_arity.setdefault(extract_name_arity(atom), None)

        positive_or_negative = "positive" if recall > 0 else "negative"
        recall = abs(recall)

        for na in name_arity:
            md = ModeDeclaration((str(recall), str(na[0]), str(na[1])), True)
            if md not in self.language_bias_head:
                self.language_bias_head.append(md)
            md = ModeDeclaration(
                (str(recall), str(na[0]), str(na[1]), positive_or_negative), False
            )
            if md not in self.language_bias_body:
                self.language_bias_body.append(md)

    def invent_predicates(self, n_predicates: int) -> None:
        """
        Enables predicate invention: it adds n predicates in the
        modeh and modeb declarations.
        """
        for i in range(n_predicates):
            self.language_bias_head.append(
                ModeDeclaration(("1", f"__inv_{i}__", "1"), True)
            )
            self.language_bias_head.append(
                ModeDeclaration(("1", f"__inv_{i}__", "2"), True)
            )
            self.language_bias_body.append(
                ModeDeclaration(("1", f"__inv_{i}__", "1", "positive"), False)
            )
            self.language_bias_body.append(
                ModeDeclaration(("1", f"__inv_{i}__", "2", "positive"), False)
            )
