import itertools
import sys

import re
from collections import defaultdict

from clingo import ast
from clingo import Control

### Print utilities
YELLOW = "\33[93m"
RED = "\033[91m"
END = "\033[0m"

UNDERSCORE_SIZE = 5


class AggregateElement:
    def __init__(
        self,
        position_var_terms: "list[int]",
        position_var_atom: "list[int]",
        var_eq: int,
    ) -> None:
        self.position_var_terms = position_var_terms
        self.position_var_atom = position_var_atom
        self.var_eq = var_eq  # for the variable after the = sign

    def __str__(self) -> str:
        return (
            "Term: "
            + " ".join([str(a) for a in self.position_var_terms])
            + " - Atoms: "
            + " ".join([str(a) for a in self.position_var_atom])
            + f" - Eq: {self.var_eq}"
        )

    def __repr__(self) -> str:
        return self.__str__()

    def __eq__(self, __value: object) -> bool:
        return (
            self.position_var_atom == __value.position_var_atom
            and self.var_eq == __value.var_eq
            and self.position_var_terms == __value.position_var_terms
        )


class RuleCallback:
    """
    Used while parsing the AST with clingo: process
    is used as callback function to store values
    """

    def __init__(self) -> None:
        self.head = []
        self.body = []

    def process(self, stm):
        # if "body" in stm.child_keys:
        # print(stm.child_keys)
        # print(stm)
        # print(stm.keys())

        if "body" in stm.child_keys:
            bl = [str(lit).replace(" ", "") for lit in stm.body]
            self.body = bl
        if "head" in stm.child_keys:
            # print(stm.head)
            self.head = str(stm.head).replace(" ", "").split(";")
            # print(h)
            # print(str(lit) for lit in stm.head)


class CheckSanityRulesCallback:
    """
    Wrapper to check unsafe rules
    """

    def __init__(self) -> None:
        self.unsound_rule: bool = False

    def sink(self, x, y):
        # global for the error: info: global variable in tuple of aggregate element
        # print(f"x: {x}")
        # print(f"y: {y}")
        # print(("unsafe" in y) or ("global" in y))
        # or because there can be more errors
        self.unsound_rule = self.unsound_rule or (("unsafe" in y) or ("global" in y))


def wrapper_exit_callback(x, y):
    """
    Clingo callback: exit when there is an error
    """
    if "error" in y:
        print(x)
        print(y)
        sys.exit()


class WrapperStopIfWarn:
    """
    Wrapper for the clingo Control callback.
    """

    def __init__(self) -> None:
        self.atom_undefined = False

    def wrapper_warn_undefined_callback(self, x, y):
        """
        Clingo callback: exit when there is an atom undefined.
        Used when check coverage: if there is an atom undefined, clearly
        the program is not ok, so we can skip the check of the coverage.
        To do so, I check whether there is a warning of an atom undefined
        (excluding the ones for coverage positive and negative) in y.
        For instance:
        x = MessageCode.AtomUndefined
        y = <block>:24:10-19: info: atom does not occur in any rule head: tails(c2)
        Maybe there is a better (more robust) method of doing this.
        """
        continue_when_met = [
            "neg_exs(I)",
            "pos_exs(I)",
            "cni(I)",
            "cne(I)",
            "cpi(I)",
            "cpe(I)",
        ]
        self.atom_undefined = self.atom_undefined or not any(
            cwm in y for cwm in continue_when_met
        )


def print_error_and_exit(message: str):
    """
    Prints the error message 'message' and exits.
    """
    print(RED + "Error: " + message + END)
    sys.exit(-1)


def print_warning(message: str):
    """
    Prints the warning message 'message'.
    """
    print(YELLOW + "Warning: " + message + END)


###


def find_symmetric_answer_sets(current_as: str) -> "list[str]":
    """
    Given an answer set current_as returns all the
    symmetric solutions, i.e., all the ones that have
    another permutation of the same variables.
    """
    i = 0
    while True:
        # count the used variables
        if not f"v{i}" in current_as:
            break
        i += 1

    n_vars = i - 1

    l_vars = [i for i in range(1, n_vars + 1)]  # from 1 since v0 is fixed at pos 0
    l_vars_name = ["v" + str(a) for a in l_vars]
    # print(l_vars)
    # print(l_vars_name)

    # this is n! # COMPLEX
    perm = itertools.permutations(l_vars)
    # TODO: is it possible to write an ASP rule to prune the permutations
    # instead of adding a set of constraints? This would be much faster.

    perms: "list[str]" = []
    for p in perm:
        # print(p)
        lc = current_as
        l1 = ["v_" + str(a) for a in p]
        for f, r in zip(l_vars_name, l1):
            lc = lc.replace(f, r)
        lc = lc.replace("_", "")
        perms.append(lc)
    # print(perms)

    # print(f"--- Permutation {current_as} {l_vars} ---")
    # print(perms)
    return perms


def from_list_to_as(current_list: "list[list[int]]") -> str:
    """
    From
    [[0,3],[1,5],[2,4]]
    to
    v0(0) v0(3) v1(1) v1(5) v2(2) v2(4)
    """
    return " ".join([f"v{idx}({el})" for idx, l in enumerate(current_list) for el in l])


def from_as_to_list(current_as: str) -> "list[list[int]]":
    """
    From
    v0(0) v0(3) v1(1) v1(5) v2(2) v2(4)
    to
    [[0,3],[1,5],[2,4]]
    """

    # Use regex to find all matches of the form vX(Y)
    matches = re.findall(r"v(\d+)\((\d+)\)", current_as)

    # Dictionary to hold lists for each vX
    groups = defaultdict(list)

    for prefix, number in matches:
        groups[prefix].append(int(number))

    # Convert the dictionary values to a list of lists and sort by prefix
    return [sorted(groups[str(i)]) for i in range(len(groups))]


def get_atoms(clause: str) -> "list[str]":
    """
    Get the atoms from a clause.
    """
    r = RuleCallback()
    ast.parse_string(clause, r.process)
    return r.head + r.body


def is_unsound(clause: str) -> bool:
    """
    Returns true if the rule is unsafe.
    """
    l = CheckSanityRulesCallback()
    ctl = Control(logger=l.sink)
    ctl.add("base", [], clause)
    try:
        ctl.ground([("base", [])])
    except:
        pass

    return l.unsound_rule


def is_valid_rule(clause: str) -> bool:
    """
    Checks whether a rule is valid:
    - safe and sound rule
    - no two or more equal atoms
    - comparison operators applied to two different variables
    - result of arithmetic operations different from input variables
    TODO: can this be done with an ASP constraint to avoid generating
    invalid rules?
    """

    if is_unsound(clause):
        return False

    comparison_operators = ["<=", ">=", "!=", "==", ">", "<"]
    arithmetic_operators = ["+", "-", "*", "/"]

    atoms_list: "list[str]" = get_atoms(clause)

    if len(atoms_list) != len(list(set(atoms_list))):
        return False

    for atom in atoms_list:
        if any(op in atom for op in comparison_operators):
            matches = re.findall(r"V\d", atom)
            v0, v1 = matches
            if v0 == v1:
                return False

        elif any(op in atom for op in arithmetic_operators):
            matches = re.findall(r"V\d", atom)
            v0, v1, v2 = matches
            # this is ok since the structure of arithmetic operators is
            # fixed to be _ op _ = _
            # v0 and v1 can be the same, V0 + V0 = V1 is valid
            if v0 == v2 or v1 == v2:
                return False

    return True


def get_duplicated_positions(clause: str) -> "list[list[list[str]]]":
    """
    Returns the positions with the same atoms:
    :- a(_____),q(_____,_____),q(_____,_____),a(_____),q(_____,_____) gets
    [[['0'], ['5']], [['1', '2'], ['3', '4'], ['6', '7']]]
    """
    atoms_list = get_atoms(clause.replace("_" * 5, "_"))  # replace otherwise error
    uniques = list(set(atoms_list))
    dup_pos: "list[list[list[str]]]" = []
    for el in uniques:
        current_variable_position = 0
        ld: "list[list[str]]" = []
        for atom in atoms_list:
            n_vars = atom.count("_")
            if atom == el:
                # duplicated
                lt: "list[str]" = []
                for nv in range(n_vars):
                    lt.append(str(nv + current_variable_position))
                if len(lt) > 0:
                    ld.append(lt)
            current_variable_position += n_vars
        if len(ld) > 0:
            dup_pos.append(ld)
    return dup_pos


def get_same_atoms(sampled_stub: str) -> "tuple[list[str],int]":
    """
    Returns the samei/n atoms for ASP to prune solutions with repeated atoms
    % same2(Id,PosV0,posV1)
    % indica che l'atomo di id ha 2 variabili le cui posizioni sono
    % (0,1) e (2,3)
    same2(0,0,1).
    same2(0,2,3).
    """
    dp = get_duplicated_positions(sampled_stub)
    to_add: "list[str]" = []
    max_p = 0
    for index, position_list_list in enumerate(dp):
        # print(len(position_list_list))
        if len(position_list_list) > 1:
            for dup_pos in position_list_list:
                s = f"same{len(dup_pos)}({index},{','.join(dup_pos)})."
                to_add.append(s)
                if len(dup_pos) > max_p:
                    max_p = len(dup_pos)
    return to_add, max_p


def get_aggregates(clause: str) -> "list[AggregateElement]":
    """
    Extracts the variables in the aggregates in the clause
    """
    # t_1, ..., t_k : \phi()
    # t1, ..., tk are terms
    # \phi is a literal
    # #sum{ _____,_____ : a  ( _____,_____ )} = _____, #sum{ _____,_____ : a  ( _____,_____ )} = _____
    # i need to return, a list of list. Each sublist contains the
    # variables in the terms
    open_brackets = [i for i, ch in enumerate(clause) if ch == "{"]
    closed_brackets = [i for i, ch in enumerate(clause) if ch == "}"]

    aggregates: "list[AggregateElement]" = []

    prev_pos = 0
    prev_count = 0
    for s, e in zip(open_brackets, closed_brackets):
        var_terms = []
        var_atom = []
        current_index = clause[prev_pos:s].count("_____") + prev_count
        aggr = clause[s + 1 : e]
        aggr = aggr.split(":")
        n_terms = aggr[0].count("_____")
        n_var_in_atom = aggr[1].count("_____")
        var_terms = list(range(current_index, n_terms + current_index))
        var_atom = list(
            range(current_index + n_terms, n_var_in_atom + current_index + n_terms)
        )

        # print(aggr)
        # print(f"current index: {current_index}")
        # print(f"var terms: {var_terms}")
        # print(f"var atom: {var_atom}")

        prev_pos = e
        prev_count = current_index + n_terms + n_var_in_atom

        aggregates.append(AggregateElement(var_terms, var_atom, prev_count))

    return aggregates


def contains_arithmetic(stub: str) -> bool:
    return "+" in stub or "-" in stub or "*" in stub or "/" in stub


def contains_comparison(stub: str) -> bool:
    return ">" in stub or "<" in stub or "==" in stub or "!=" in stub


def get_arithmetic_or_comparison_position(
    stub: str,
) -> "tuple[list[list[int]],list[list[int]]]":
    """
    Extracts the positions of the variables involved in arithmetic or
    comparison operators.
    """
    els = stub.replace(" ", "").split("_____")
    pos_arithmetic: "list[list[int]]" = []
    pos_comparison: "list[list[int]]" = []
    for index, el in enumerate(els):
        if (
            el == ">"
            or el == ">="
            or el == "<"
            or el == "<="
            or el == "=="
            or el == "!="
        ):
            pos_comparison.append([index - 1, index])

        if el == "+" or el == "-" or el == "*" or el == "/":
            pos_arithmetic.append([index - 1, index, index + 1])

    return pos_arithmetic, pos_comparison
