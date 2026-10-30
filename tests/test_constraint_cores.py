"""Generated constraints against an oracle that shares no code with the generator.

Two positive constraints over open predicates exclude the same models exactly
when their bodies are homomorphically equivalent. Each equivalence class has one
core, unique up to variable renaming and body order. So the exact clause space
holds one clause per connected core: anything more repeats a class, anything
less loses one.
"""

import re
from itertools import combinations, permutations, product
from pathlib import Path

import pytest

from gentians.arguments import Arguments
from gentians.clauses import generate_clause_space
from gentians.clauses import fact_compiler, mode_facts
from gentians.language import parse_file, parse_text

BENCHMARKS = Path(__file__).parents[1] / "benchmarks" / "gentians"

type Atom = tuple[str, ...]


def _homomorphic(source: set[Atom], target: set[Atom]) -> bool:
    atoms = sorted(source)

    def extend(index: int, mapping: dict[str, str]) -> bool:
        if index == len(atoms):
            return True
        for candidate in target:
            if candidate[0] != atoms[index][0] or len(candidate) != len(atoms[index]):
                continue
            extended = dict(mapping)
            pairs = zip(atoms[index][1:], candidate[1:], strict=True)
            if all(extended.setdefault(left, right) == right for left, right in pairs) and extend(index + 1, extended):
                return True
        return False

    return extend(0, {})


def _is_core(body: tuple[Atom, ...]) -> bool:
    atoms = set(body)
    return not any(_homomorphic(atoms, atoms - {atom}) for atom in atoms)


def _connected(body: tuple[Atom, ...]) -> bool:
    reached = {body[0]}
    pending = [body[0]]
    while pending:
        current = pending.pop()
        for atom in body:
            if atom not in reached and set(atom[1:]) & set(current[1:]):
                reached.add(atom)
                pending.append(atom)
    return len(reached) == len(body)


def _isomorphism_class(body: tuple[Atom, ...]) -> tuple[Atom, ...]:
    # Full permutation search on purpose: the oracle must stay simpler than the
    # code it checks.
    best = None
    for order in permutations(sorted(body)):
        names: dict[str, str] = {}
        renamed = tuple(
            (atom[0], *(names.setdefault(term, f"#{len(names)}") if term[0].isupper() else term for term in atom[1:]))
            for atom in order
        )
        if best is None or renamed < best:
            best = renamed
    assert best is not None
    return best


def _connected_cores(predicates: dict[str, int], max_body: int, max_variables: int) -> set[tuple[Atom, ...]]:
    classes = set()
    for size in range(1, max_body + 1):
        for count in range(1, max_variables + 1):
            names = tuple(f"V{index}" for index in range(count))
            atoms = [(name, *terms) for name, arity in predicates.items() for terms in product(names, repeat=arity)]
            for body in combinations(atoms, size):
                used = {term for atom in body for term in atom[1:]}
                if len(used) == count and _connected(body) and _is_core(body):
                    classes.add(_isomorphism_class(body))
    return classes


def _body(clause: str) -> tuple[Atom, ...]:
    head, separator, _rest = clause.partition(" :- ")
    atoms = []
    for negated, name, terms in re.findall(r"(not )?(\w+)\(([^)]*)\)", clause):
        section = "head " if separator and head != "#false" and not atoms else ""
        atoms.append((f"{section}not {name}" if negated else f"{section}{name}", *map(str.strip, terms.split(","))))
    atoms.extend(("<", left, right) for left, right in re.findall(r"\((V\d+)-(V\d+)\) < 0", clause))
    atoms.extend(("<", left, right) for right, left in re.findall(r"\(-(V\d+)\+(V\d+)\) < 0", clause))
    return tuple(atoms)


def _open_task(predicates: dict[str, int], max_body: int, max_variables: int) -> str:
    lines = [f"#maxv({max_variables}).", f"#maxbl({max_body}).", "#maxhl(0).", "#maxpl(20)."]
    for name, arity in predicates.items():
        lines.append(f"{{{name}({','.join(['1..4'] * arity)})}}.")
        lines.append(f"#modeb({max_body},{name}({','.join(['var(node,output)'] * arity)})).")
    return "\n".join(lines)


def _clauses(task) -> list[str]:
    return list(generate_clause_space(task, Arguments()).clauses)


@pytest.mark.parametrize(("predicates", "max_body", "max_variables", "expected"), [
    ({"p": 2}, 1, 3, 2),
    ({"p": 2}, 2, 2, 3),
    ({"p": 2}, 2, 4, 4),
    ({"p": 2}, 3, 3, 6),
    ({"p": 2}, 3, 4, 7),
    ({"p": 2}, 3, 5, 7),
    ({"p": 2}, 4, 3, 9),
    ({"p": 2}, 4, 4, 14),
    ({"p": 2, "q": 2}, 2, 3, 19),
    ({"p": 2, "q": 2}, 3, 3, 83),
    ({"p": 1, "q": 2}, 3, 3, 17),
])
def test_constraint_space_holds_exactly_one_clause_per_connected_core(predicates, max_body, max_variables, expected):
    clauses = _clauses(parse_text(_open_task(predicates, max_body, max_variables)))
    classes = [_isomorphism_class(_body(clause)) for clause in clauses]

    assert sorted(classes) == sorted(_connected_cores(predicates, max_body, max_variables))
    assert len(clauses) == expected


@pytest.mark.parametrize(("name", "expected"), [
    ("pedro", 4),
    ("constraints_paths", 7),
    ("constraints_cycles", 14),
    ("constraints_two_relations", 83),
    ("constraints_unary_binary", 17),
])
def test_constraint_benchmarks_match_their_documented_size(name, expected):
    assert len(_clauses(parse_file(str(BENCHMARKS / name)))) == expected


@pytest.mark.parametrize("task", [
    "#maxv(4). #maxbl(3). #maxhl(0). {p(1..3,1..3)}. {q(1..3)}. "
    "#modeb(3,p(var(node,output),var(node,output))). #modeb(2,not q(var(node,input))).",
    "#maxv(3). #maxbl(3). #maxhl(0). {p(1..3,1..3)}. "
    "#modeb(2,p(var(node,output),var(node,output))). #modeb(2,not p(var(node,input),var(node,input))).",
    "#maxv(3). #maxbl(3). #maxhl(0). #constant(colour,a). #constant(colour,b). {p(a;b,1..3,1..3)}. "
    "#modeb(3,p(const(colour),var(node,output),var(node,output))).",
    "#maxv(3). #maxbl(4). #maxhl(0). {r(1..3,1..3)}. "
    "#modeb(3,r(var(numeric,output),var(numeric,output))). #modeb(1,var(numeric,input)<var(numeric,input)).",
    "#maxv(3). #maxbl(3). #maxhl(1). {p(1..3,1..3)}. "
    "#modeh(1,target(var(node,input))). #modeb(3,p(var(node,output),var(node,output))).",
    "#maxv(4). #maxbl(2). #maxhl(1). {p(1..3,1..3)}. "
    "#modeh(1,target(var(node,input),var(node,input))). #modeb(2,p(var(node,output),var(node,output))).",
    "#maxv(3). #maxbl(2). #maxhl(1). {p(1..3,1..3)}. {r(1..3)}. "
    "#modeh(1,{c(var(node,input))}). #modeb(2,p(var(node,output),var(node,output))). #modeb(1,not r(var(node,input))).",
], ids=["negated-unary", "negated-binary", "constants", "comparison", "unary-head", "binary-head", "choice-head"])
def test_twins_merge_one_class_at_a_time(monkeypatch, task):
    # Heads, negation and comparisons have no core oracle, but renaming and body
    # order still must merge isomorphic clauses, and only those.
    merged = _clauses(parse_text(task))
    monkeypatch.setattr(fact_compiler, "twin_facts", lambda *_: [])
    unmerged = _clauses(parse_text(task))

    classes = {_isomorphism_class(_body(clause)) for clause in unmerged}
    assert len(unmerged) > len(merged)
    assert sorted(_isomorphism_class(_body(clause)) for clause in merged) == sorted(classes)
    assert set(merged) <= set(unmerged)


def test_symmetries_stay_inside_a_mode():
    # Swapping V0 and V1 turns one body into the other, but across two modes. A
    # symmetry never changes a mode, so ASP keeps both and meanings stay intact.
    clauses = _clauses(parse_text(
        "#maxv(2). #maxbl(3). #maxhl(0). {n(1..3)}. #modeb(2,n(var(numeric,output))). "
        "#modeb(1,var(numeric)<var(numeric)). #modeb(1,var(numeric)>var(numeric))."
    ))

    assert clauses == ["#false :- n(V0).", "#false :- n(V0); n(V1); (-V0+V1) < 0.", "#false :- n(V0); n(V1); (V0-V1) < 0."]


def test_symmetries_keep_a_form_that_orders_its_operands():
    # V1 != V0 is illegal, so the twin of a literal that orders its operands
    # must be read after swapping them.
    clauses = _clauses(parse_text(
        "#maxv(3). #maxbl(3). #maxhl(0). {r(1..3,1..3)}. "
        "#modeb(2,r(var(n,output),var(n,output))). #modeb(1,var(n,input)!=var(n,input))."
    ))

    assert "#false :- r(V0,V1); r(V1,V2); V0 != V2." in clauses
    assert "#false :- r(V0,V1); r(V2,V0); V1 != V2." not in clauses


@pytest.mark.parametrize("recall", [5, 6])
def test_a_large_symmetry_group_stays_sound_under_its_limit(monkeypatch, recall):
    # A dropped symmetry may keep twins but must never lose a class.
    monkeypatch.setattr(mode_facts, "TWIN_CELL_LIMIT", 2_000)
    task = parse_text(f"#maxv(3). #maxbl({recall}). #maxhl(0). {{p(1..3,1..3)}}. "
                      f"#modeb({recall},p(var(node,output),var(node,output))).")
    limited = _clauses(task)
    monkeypatch.undo()

    assert {_isomorphism_class(_body(clause)) for clause in limited} == {
        _isomorphism_class(_body(clause)) for clause in _clauses(task)
    }


def test_rules_with_a_head_merge_their_renamed_twins():
    clauses = _clauses(parse_text(
        "#maxv(3). #maxbl(2). #maxhl(1). {p(1..3,1..3)}. "
        "#modeh(1,target(var(node,input))). #modeb(2,p(var(node,output),var(node,output)))."
    ))

    # The start, middle and end of a path are different rules.
    assert "target(V0) :- p(V0,V1); p(V1,V2)." in clauses
    assert "target(V1) :- p(V0,V1); p(V1,V2)." in clauses
    assert "target(V2) :- p(V0,V1); p(V1,V2)." in clauses
    assert "target(V0) :- p(V0,V1); p(V2,V0)." not in clauses


@pytest.mark.parametrize("arguments", [["--parallel-mode=1"], ["--parallel-mode=4,split"]], ids=["serial", "parallel"])
def test_the_surviving_twin_does_not_depend_on_enumeration_order(arguments):
    task = parse_text(_open_task({"p": 2}, 3, 4))
    configured = Arguments()
    configured.clause_generation["clingo_arguments"] = arguments

    assert generate_clause_space(task, configured).clauses == (
        "#false :- p(V0,V0).",
        "#false :- p(V0,V1).",
        "#false :- p(V0,V1); p(V0,V2); p(V1,V2).",
        "#false :- p(V0,V1); p(V1,V0).",
        "#false :- p(V0,V1); p(V1,V2).",
        "#false :- p(V0,V1); p(V1,V2); p(V2,V0).",
        "#false :- p(V0,V1); p(V1,V2); p(V2,V3).",
    )
