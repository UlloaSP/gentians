import itertools
import re
from collections import defaultdict


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

    # this is n! # COMPLEX
    perm = itertools.permutations(l_vars)
    # TODO: is it possible to write an ASP rule to prune the permutations
    # instead of adding a set of constraints? This would be much faster.

    perms: "list[str]" = []
    for p in perm:
        lc = current_as
        l1 = ["v_" + str(a) for a in p]
        for f, r in zip(l_vars_name, l1):
            lc = lc.replace(f, r)
        lc = lc.replace("_", "")
        perms.append(lc)

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


def from_symbols_to_list(symbols) -> "list[list[int]]":
    groups = defaultdict(list)
    for symbol in symbols:
        if not symbol.name.startswith("v") or len(symbol.arguments) != 1:
            continue
        groups[symbol.name[1:]].append(symbol.arguments[0].number)
    return [sorted(groups[str(i)]) for i in range(len(groups))]
