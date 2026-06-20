import re

from .utils import print_error_and_exit, RuleCallback
from clingo import ast


def extract_name_arity(atom: str) -> "tuple[str,int]":
    """
    Extracts name and arity from an atom.
    """
    pattern = r"\{?(\w+)(?:\((.*?)\))?\}?"
    match = re.match(pattern, atom)
    if match:
        function_name = match.group(1)  # Extract function name
        args = match.group(2)  # Extract arguments (if any)
        if args:
            # Split arguments while keeping nested parentheses intact
            arguments = re.findall(r"\w+\(.*?\)|\w+", args)
        else:
            arguments = []

        if function_name.startswith(
            "not"
        ):  # to support literal, space after not is removed
            function_name = function_name[3:]
        return (function_name, len(arguments))

    print_error_and_exit(f"Error in extract_name_arity: {atom}")
    return (atom, -1)


class Example:
    """
    Class for examples in the input file.
    Members of the tuple, in order: included, excluded, and context.
    """

    def __init__(
        self, s: "tuple[str,str] | tuple[str,str,str]", positive: bool
    ) -> None:
        self.included: str = s[0]
        self.excluded: str = s[1]
        self.context: str = s[2] if len(s) == 3 else ""
        self.positive: bool = positive

    def __str__(self) -> str:
        return f"Example: {self.included} - {self.excluded} - {self.context} - {self.positive}"

    def __repr__(self) -> str:
        return self.__str__()


class ModeDeclaration:
    """
    Class for mode declarations in the input file.
    Members of the tuple, in order: recall, name, arity, and positive/negative.
    """

    def __init__(
        self, s: "tuple[str,str,str] | tuple[str,str,str,str]", head: bool
    ) -> None:
        if s[0] == "*":
            self.recall: int = 100
        else:
            self.recall: int = int(s[0])
        self.name: str = s[1]
        self.arity: int = int(s[2])
        self.positive: bool = True
        if len(s) == 4:
            if s[3] == "negative":
                self.positive = False
        self.head: bool = head

        self.aggregation_function: str = ""
        self.aggregation_atoms: "list[tuple[str,int]]" = []
        self.arithmetic_operator: str = ""
        self.comparison_operator: str = ""

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
                print_error_and_exit(f"Error: Invalid aggregate function name: {name}")
            self.aggregation_function = name
            pairs = re.findall(r"(\w+)/(\d+)", match.group(2))
            if pairs:
                for pair in pairs:
                    self.aggregation_atoms.append((pair[0], int(pair[1])))
        else:
            print_error_and_exit(
                f"Error: Invalid aggregate function syntax: {aggregate_str}"
            )

    def special_mode_declaration(self) -> bool:
        return any(
            [
                self.aggregation_function != "",
                self.arithmetic_operator != "",
                self.comparison_operator != "",
            ]
        )

    def __str__(self) -> str:
        s = f"ModeDeclaration: recall: {self.recall} - name: {self.name} - arity: {self.arity} - positive: {self.positive} - head: {self.head}"
        if self.aggregation_function != "":
            s += f" - aggregate: {self.aggregation_function} - atoms: {self.aggregation_atoms}"
        if self.arithmetic_operator != "":
            s += f" - arithmetic: {self.arithmetic_operator}"
        if self.comparison_operator != "":
            s += f" - comparison: {self.comparison_operator}"
        return s

    def __repr__(self) -> str:
        return self.__str__()


class Program:
    """
    Class for input programs.
    """

    def __init__(
        self,
        bg: "list[str]",
        pos: "list[Example]",
        neg: "list[Example]",
        mode_head: "list[ModeDeclaration]",
        mode_body: "list[ModeDeclaration]",
    ) -> None:
        self.background: "list[str]" = bg
        self.positive_examples: "list[Example]" = pos
        self.negative_examples: "list[Example]" = neg
        self.language_bias_head: "list[ModeDeclaration]" = mode_head
        self.language_bias_body: "list[ModeDeclaration]" = mode_body

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

        name_arity_list: "list[tuple[str,int]]" = []

        r = RuleCallback()
        for rule in self.background:
            ast.parse_string(rule, r.process)
            for h in r.head + r.body:  # head and body
                na = extract_name_arity(h)
                if na not in name_arity_list:
                    name_arity_list.append(na)

        for e in self.positive_examples + self.negative_examples:
            to_consider = [e.included, e.excluded]
            for s in to_consider:
                if len(s) > 0:
                    s = ":- " + s + "."
                    ast.parse_string(s, r.process)
                    for atom in r.body:
                        na = extract_name_arity(atom)
                        if na not in name_arity_list:
                            name_arity_list.append(na)

        positive_or_negative = "positive" if recall > 0 else "negative"
        recall = abs(recall)

        for na in name_arity_list:
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

    def __str__(self) -> str:
        return f"Program: {self.background} - {self.positive_examples} - {self.negative_examples} - {self.language_bias_head} - {self.language_bias_body}"

    def __repr__(self) -> str:
        return self.__str__()


class Parser:
    """
    Class for parsing the input file.
    """

    def __init__(self, filename: str) -> None:
        self.filename: str = filename

    def _get_mode_declaration(
        self, s: str, for_head: bool = False
    ) -> "tuple[str,str,str] | tuple[str,str,str,str]":
        if for_head:
            regex = r"#modeh\((\d+|\*),(.*),(\d+)\)."
        else:
            regex = r"#modeb\((\d+|\*),(.*),(\d+),(positive|negative)\)."
        return re.findall(regex, s)[0]

    def _get_pos_neg_examples(self, s: str) -> "tuple[str,str] | tuple[str,str,str]":
        # TODO: improve this
        regex3 = r"^#(?:pos|neg)\(\{([^{}]*)\},\{([^{}]*)\},\{([^{}]*)\}\)\.$"
        regex2 = r"^#(?:pos|neg)\(\{([^{}]*)\},\{([^{}]*)\}\)\.$"
        res = re.findall(regex3, s)
        if len(res) > 0:
            return res[0]
        else:
            res = re.findall(regex2, s)
            return res[0]

    def read_from_file(self):
        """
        Read the inductive task from file.
        """
        bg: "list[str]" = []
        pe: "list[Example]" = []
        ne: "list[Example]" = []
        lbh: "list[ModeDeclaration]" = []
        lbb: "list[ModeDeclaration]" = []

        fp = open(self.filename, "r")
        lines = fp.read().splitlines()
        fp.close()

        for line in lines:
            lc = line.rstrip().lstrip()

            if lc.startswith("#modeh"):
                res = self._get_mode_declaration(lc.replace(" ", ""), True)
                if len(res) > 0:
                    md = ModeDeclaration(res, True)
                    if md not in lbh:
                        lbh.append(md)
            elif lc.startswith("#modeb"):
                res = self._get_mode_declaration(lc.replace(" ", ""), False)
                if len(res) > 0:
                    md = ModeDeclaration(res, False)
                    if md not in lbb:
                        lbb.append(md)
            elif lc.startswith("#pos"):
                lc = lc.replace(" ", "")
                res = self._get_pos_neg_examples(lc)
                ex = Example(res, True)
                if ex not in pe:
                    pe.append(ex)
            elif lc.startswith("#neg"):
                lc = lc.replace(" ", "")
                res = self._get_pos_neg_examples(lc)
                ex = Example(res, False)
                if ex not in ne:
                    ne.append(Example(res, False))
            else:
                bg.append(lc)

        return Program(bg, pe, ne, lbh, lbb)
