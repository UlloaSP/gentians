from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import cast

import clingo
from clingo import ast
from clingo.configuration import Configuration

from ...language.asp import (
    AspProgram,
    Predicate,
    add_program,
    clause_predicates,
    parse_program,
    symbolic_functions,
    without_show,
)
from ...language.ast_nodes import LOCATION, literal
from .ast_inspection import _children

# Integers stay integers; every other ground term is its canonical Clingo text.
# Native values hash and compare far faster than clingo.Symbol wrappers.
type GroundTerm = int | str


type GroundTuple = tuple[GroundTerm, ...]

type _Consequences = tuple[dict[Predicate, set[GroundTuple]], dict[Predicate, set[GroundTuple]]] | None


@dataclass(frozen=True, slots=True)
class ClosedWorld:
    """Relations of one evaluation context that no learned clause can change.

    A predicate is closed when neither a learned head nor any predicate it
    depends on can be defined by a learned clause. Clingo computes the brave and
    cautious consequences of the closed statements; a closed predicate is fixed
    when both agree, so its extension is identical in every stable model.

    An open predicate still has a lower bound: atoms that a normal background
    rule over closed predicates derives in every stable model, whatever clauses
    are learned. Learned clauses and other rules can only add to it.
    """

    extensions: dict[Predicate, frozenset[GroundTuple]]
    lower_bounds: dict[Predicate, frozenset[GroundTuple]]
    # Tuples of an unfixed closed predicate true in some model: every model's
    # extension lies inside, so its argument values are bounded by these.
    upper_bounds: dict[Predicate, frozenset[GroundTuple]]
    open: frozenset[Predicate]
    unfixed: frozenset[Predicate]
    program: AspProgram

    def extension(self, predicate: Predicate) -> frozenset[GroundTuple] | None:
        if predicate in self.open or predicate in self.unfixed:
            return None
        return self.extensions.get(predicate, frozenset())


def _closed_world(
    program: AspProgram, learned: frozenset[Predicate],
    relations_cache: dict[ast.AST, tuple[frozenset[Predicate], frozenset[Predicate]]] | None = None,
    consequences: Callable[[AspProgram], _Consequences] | None = None,
) -> ClosedWorld | None:
    """Return the fixed closed relations, or None when none can be trusted.

    None means the closed statements have no stable model, so no hypothesis can
    cover an example of this context, or that a rule touching open predicates
    has a head whose predicates cannot be read.
    """
    if relations_cache is None:
        relations_cache = {}
    relations = {}
    for statement in program:
        if statement.ast_type == ast.ASTType.Rule:
            relation = relations_cache.get(statement)
            if relation is None:
                heads, dependencies, _body_size = clause_predicates(statement)
                relation = relations_cache[statement] = heads, dependencies
            relations[statement] = relation
    open_predicates = _open_predicates(relations, learned)
    if open_predicates is None:
        return None
    closed_program = tuple(
        statement
        for statement in program
        if statement not in relations or not (
            relations[statement][0] & open_predicates
            or relations[statement][1] & open_predicates
        )
    )
    lower_rules = tuple(
        statement
        for statement in program
        if statement in relations
        and statement.head.ast_type == ast.ASTType.Literal
        and statement.head.sign == ast.Sign.NoSign
        and statement.head.atom.ast_type == ast.ASTType.SymbolicAtom
        and _head_predicates_known(statement.head)
        and bool(relations[statement][0])
        and relations[statement][0] <= open_predicates
        and not relations[statement][1] & open_predicates
    )
    bounds = (_consequences if consequences is None else consequences)(closed_program + lower_rules)
    if bounds is None:
        return None
    brave, cautious = bounds
    unfixed = frozenset(
        predicate
        for predicate in brave.keys() | cautious.keys()
        if predicate not in open_predicates
        and brave.get(predicate) != cautious.get(predicate)
    )
    extensions = {
        predicate: frozenset(tuples)
        for predicate, tuples in cautious.items()
        if predicate not in unfixed and predicate not in open_predicates
    }
    lower_bounds = {
        predicate: frozenset(tuples)
        for predicate, tuples in cautious.items()
        if predicate in open_predicates
    }
    upper_bounds = {
        predicate: frozenset(brave.get(predicate, ()))
        for predicate in unfixed
    }
    return ClosedWorld(
        extensions,
        lower_bounds,
        upper_bounds,
        open_predicates,
        unfixed,
        closed_program,
    )


def _open_predicates(
    relations: dict[ast.AST, tuple[frozenset[Predicate], frozenset[Predicate]]],
    learned: frozenset[Predicate],
) -> frozenset[Predicate] | None:
    open_predicates = set(learned)
    affected: dict[Predicate, list[ast.AST]] = {}
    for rule, (heads, dependencies) in relations.items():
        for predicate in heads | dependencies:
            affected.setdefault(predicate, []).append(rule)
    pending = list(sorted(learned))
    visited: set[ast.AST] = set()
    while pending:
        for rule in affected.get(pending.pop(), ()):
            if rule in visited:
                continue
            visited.add(rule)
            if not _head_predicates_known(rule.head):
                return None
            new = relations[rule][0] - open_predicates
            open_predicates.update(new)
            pending.extend(sorted(new))
    return frozenset(open_predicates)


def _head_predicates_known(node: ast.AST) -> bool:
    """Whether predicate extraction reads every symbolic head element."""
    pending = [node]
    while pending:
        node = pending.pop()
        if node.ast_type == ast.ASTType.SymbolicAtom:
            if not (symbolic_functions(node.symbol) or (
                node.symbol.ast_type == ast.ASTType.SymbolicTerm
                and node.symbol.symbol.type == clingo.SymbolType.Function
            )):
                return False
        elif node.ast_type == ast.ASTType.TheoryAtom:
            return False
        else:
            pending.extend(_children(node))
    return True


def _consequences(
    program: AspProgram,
) -> _Consequences:
    control = clingo.Control(["--models=0"], logger=lambda _code, _message: None)
    add_program(control, without_show(program))
    control.ground([("base", [])])
    results: list[dict[Predicate, set[GroundTuple]]] = []
    for mode in ("brave", "cautious"):
        cast(Configuration, control.configuration.solve).enum_mode = mode
        last: Sequence[clingo.Symbol] | None = None
        with control.solve(yield_=True) as handle:
            for model in handle:
                last = model.symbols(atoms=True)
        if last is None:
            return None
        results.append(_by_predicate(last))
    return results[0], results[1]


def _by_predicate(symbols: Sequence[clingo.Symbol]) -> dict[Predicate, set[GroundTuple]]:
    relations: dict[Predicate, set[GroundTuple]] = {}
    for symbol in symbols:
        if symbol.type != clingo.SymbolType.Function or not symbol.name:
            continue
        name = f"-{symbol.name}" if symbol.negative else symbol.name
        relations.setdefault((name, len(symbol.arguments)), set()).add(
            tuple(
                argument.number
                if argument.type == clingo.SymbolType.Number
                else str(argument)
                for argument in symbol.arguments
            )
        )
    return relations


# A candidate property proved by syntax still has to hold in every stable
# model: another rule may add tuples the syntax did not see. Each candidate is
# the body of a rule deriving its violation; it holds when assuming that
# violation is UNSAT.
CHECK_TIMEOUT_SECONDS = 2.0


def _fresh_violation_name(program: AspProgram) -> str:
    """Avoid predicates, fixed terms and macros in the task and proof bodies."""
    names: set[str] = set()
    pending = list(program)
    while pending:
        node = pending.pop()
        if "name" in node.keys():
            names.add(str(node.name))
        if node.ast_type == ast.ASTType.SymbolicTerm:
            symbols = [node.symbol]
            while symbols:
                symbol = symbols.pop()
                if symbol.type == clingo.SymbolType.Function:
                    names.add(symbol.name)
                    symbols.extend(symbol.arguments)
        pending.extend(_children(node))
    name = "gentians_violation"
    suffix = 0
    while name in names:
        suffix += 1
        name = f"gentians_violation_{suffix}"
    return name


def _hold_in_every_model(program: AspProgram, violations: list[str]) -> set[int]:
    """Indexes of violation bodies that no stable model of program satisfies."""
    if not violations:
        return set()
    probes = parse_program("\n".join(f":- {body}." for body in violations))
    name = _fresh_violation_name(program + probes)
    control = clingo.Control(logger=lambda _code, _message: None)
    add_program(control, program)
    proof_rules = tuple(
        probe.update(head=literal(ast.SymbolicAtom(ast.SymbolicTerm(
            LOCATION, clingo.Function(name, [clingo.Number(index)]),
        ))))
        for index, probe in enumerate(probes)
    )
    add_program(control, (ast.Program(LOCATION, "base", []), *proof_rules))
    control.ground([("base", [])])
    held: set[int] = set()
    for index in range(len(violations)):
        atom = control.symbolic_atoms[clingo.Function(name, [clingo.Number(index)])]
        if atom is None:
            held.add(index)
            continue
        with control.solve(assumptions=[(atom.symbol, True)], async_=True) as handle:
            if not handle.wait(CHECK_TIMEOUT_SECONDS):
                handle.cancel()
                continue
            if handle.get().unsatisfiable:
                held.add(index)
    return held


def _atom(predicate: Predicate, terms: list[str]) -> str:
    name, _arity = predicate
    return f"{name}({','.join(terms)})" if terms else name


def _arguments(predicate: Predicate, prefix: str = "A") -> list[str]:
    return [f"{prefix}{index}" for index in range(predicate[1])]


def _symmetric_violation(predicate: Predicate) -> str:
    left = _arguments(predicate)
    return f"{_atom(predicate, left)}, not {_atom(predicate, left[::-1])}"


def _arg_distinct_violation(predicate: Predicate, first: int, second: int) -> str:
    left = _arguments(predicate)
    left[second] = left[first]
    return _atom(predicate, left)


def _project_implies_violation(
    source: Predicate, target: Predicate, projection: tuple[int, ...]
) -> str:
    left = _arguments(source)
    return f"{_atom(source, left)}, not {_atom(target, [left[index] for index in projection])}"


def _cardinality_violation(predicate: Predicate, upper: int) -> str:
    left = _arguments(predicate)
    return f"#count{{{','.join(left) or '1'}: {_atom(predicate, left)}}} > {upper}"


def _dependency_violation(
    predicate: Predicate, inputs: tuple[int, ...], outputs: tuple[int, ...]
) -> str:
    """Two tuples agree on inputs and differ on some of outputs."""
    left = _arguments(predicate)
    right = [
        left[index] if index in inputs else f"B{index}"
        for index in range(predicate[1])
    ]
    differs = "; ".join(f"1: A{index} != B{index}" for index in outputs)
    return f"{_atom(predicate, left)}, {_atom(predicate, right)}, 1 <= #count{{{differs}}}"
