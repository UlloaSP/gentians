"""Compile modes to the recovered ASP, then decode projected answer sets."""

from collections import defaultdict
from dataclasses import dataclass
from math import comb
from pathlib import Path
import re

import clingo
from clingo import ast
from clingo.script import enable_python

from .task import Mode, Task, _tokens, parse_asp, parse_candidate, render_candidate, split_fields


@dataclass(frozen=True)
class Options:
    max_body_literals: int = 3
    max_rule_length: int = 5
    max_wc_length: int = 3
    no_aggregates: bool = False
    no_constraints: bool = False
    strict_types: bool = False
    override_default_sm: bool = False
    learn_heuristics: bool = False


@dataclass(frozen=True, order=True)
class Entry:
    cost: int
    rule: str
    attributes: tuple[str, ...] = ()
    meta: bool = False

    def __str__(self) -> str:
        return f"{self.cost} ~ {self.rule}"


_KINDS = {"modeb": "body", "modec": "conditional", "modeh": "head",
          "modeha": "aggregate_head", "modem": "meta", "modeo": "opt"}
_PLACEHOLDER = re.compile(r"const\(([^)]*)\)|var\(([^),]*)\)")
_META_PLACEHOLDER = re.compile(r"const\(([^)]*)\)|var\(([^),]*)\)|([a-z][A-Za-z_0-9]*)\s*/\s*(\d+)")


def _reify_arithmetic(source: str) -> str:
    """Reproduce Utils::replace_arithmetic, whose range precedence differs from Clingo."""
    tokens = list(_tokens(source))
    depth = 0
    operators = []
    skip = -1
    for start, end, token in tokens:
        if start < skip:
            continue
        if token == "(":
            depth += 1
        elif token == ")":
            depth -= 1
        elif not depth and token in ("+", "-", "*", "/", "\\", "<", ">", "=", "!"):
            op = source[start:end]
            if token in ("<", ">", "=", "!") and source[end:end + 1] == "=":
                op += "="
                end += 1
            operators.append((start, end, op))
            skip = end
    if operators:
        start, end, op = operators[0]
        left, right = source[:start].strip(), source[end:].strip()
        if not left or not right:
            raise ValueError(f"ILASP cannot reify a unary operator in this mode: {source}")
        op = "=" if op == "==" else op
        return f"bin_exp({clingo.String(op)}, {_reify_arithmetic(left)}, {_reify_arithmetic(right)})"
    parts, begin, opening, depth = [], 0, 0, 0
    for start, end, token in tokens:
        if token == "(":
            if depth == 0:
                opening = start
            depth += 1
        elif token == ")":
            depth -= 1
            if depth == 0:
                parts.append(source[begin:opening + 1])
                parts.append(", ".join(_reify_arithmetic(field) for field in split_fields(source[opening + 1:start])))
                parts.append(")")
                begin = end
    parts.append(source[begin:])
    return "".join(parts)


def _mode_source(mode: Mode, prefix: str = "V") -> tuple[str, tuple[tuple[str, str], ...], bool]:
    nodes = parse_asp(f":- {mode.source}.")
    if len(nodes) != 1 or nodes[0].ast_type != ast.ASTType.Rule or len(nodes[0].body) != 1:
        raise ValueError(f"expected a single mode literal: {mode.source}")
    literal = nodes[0].body[0]
    if literal.ast_type != ast.ASTType.Literal or literal.sign != ast.Sign.NoSign:
        raise ValueError("use the (negative) mode option for default negation")
    bindings: list[tuple[str, str]] = []

    def replace(match: re.Match[str]) -> str:
        index = len(bindings)
        if match[1] is not None:
            bindings.append(("const", match[1]))
        elif match[2] is not None:
            bindings.append(("var", match[2]))
        else:
            bindings.append(("meta", f"{match[3]},{match[4]}"))
        return f"{prefix}{index}"

    pattern = _META_PLACEHOLDER if mode.kind == "modem" else _PLACEHOLDER
    source = "".join(token for _, _, token in _tokens(mode.source) if not token.isspace())
    result = _reify_arithmetic(pattern.sub(replace, source))
    return result, tuple(bindings), literal.atom.ast_type == ast.ASTType.Comparison


def _compile_mode(mode: Mode, index: int) -> tuple[list[str], set[str]]:
    template, bindings, comparison = _mode_source(mode)
    kind = _KINDS[mode.kind]
    possible = f"possible_{kind}({index}, {template})"
    domains = [f"{'const' if typ == 'meta' else typ}(V{i}, {name})"
               for i, (typ, name) in enumerate(bindings)]
    options = list(mode.options)
    if comparison:
        options.extend(option for option in ("positive", "anti_reflexive") if option not in options)
    if "anti_reflexive" in options and len(bindings) == 2:
        domains.append("V0 != V1")
    lines = [possible + (" :- " + ", ".join(domains) if domains else "") + ".",
             f"recall({index}, {mode.recall})."]
    lines.extend(f"constraint({index}, {option})." for option in options)
    lines.extend(f"at({template}, {i}, V{i}) :- {possible}."
                 for i, (typ, _) in enumerate(bindings) if typ == "var")
    mapped, _, _ = _mode_source(mode, "M")
    mapping = ["var_assignment(I)", possible]
    mapping.extend(f"var_assign(I, V{i}, M{i})" if typ == "var" else f"V{i} = M{i}"
                   for i, (typ, _) in enumerate(bindings))
    lines.append(f"mapping(I, {template}, {mapped}) :- {', '.join(mapping)}.")
    return lines, {name for typ, name in bindings if typ == "var"}


def compile_task(task: Task, options: Options = Options()) -> str:
    lines, types = [], set()
    for index, mode in enumerate(sorted(task.modes, key=lambda m: list(_KINDS).index(m.kind))):
        compiled, mode_types = _compile_mode(mode, index)
        lines.extend(compiled)
        types.update(mode_types)
    lines.extend(f"var_type({typ})." for typ in sorted(types))
    lines.extend(f"const({value}, {typ})." for typ, value in sorted(task.constants, key=lambda p: p[0]))
    for weight in task.weights:
        name = "integer_weight" if weight.lstrip("-").isdigit() else "type_weight"
        lines.append(f"{name}({weight}).")
    limits = {"maxv": 3, "maxp": 2, "max_body_literals": options.max_body_literals,
              "max_rule_length": options.max_rule_length, "max_wc_length": options.max_wc_length,
              "maxhl": 2, "minhl": 1}
    limits.update(task.limits)
    lines.extend(f"{key}({value})." for key, value in limits.items())
    lines.extend(f"meta_predicate({typ}, {predicate}, {arity})." for typ, predicate, arity in task.predicates)
    for flag in ("strict_types", "no_aggregates", "no_constraints"):
        if getattr(options, flag):
            lines.append(f"{flag}.")
    if task.dmhv:
        lines.append("dmhv.")
    if not options.override_default_sm:
        lines.append("\n" + (Path(__file__).parents[1] / "recovered/search-space.lp").read_text(encoding="utf-8"))
        if options.learn_heuristics:
            lines.append((Path(__file__).parents[1] / "recovered/heuristics.lp").read_text(encoding="utf-8"))
    lines.extend(task.bias)
    # An overridden generator still uses the same decoder interface.
    if options.override_default_sm:
        lines.extend(f"#show {sig}." for sig in ("head/1", "in_head/1", "body/1", "body/2",
                     "condition/2", "weak_body/1", "lb/1", "ub/1", "priority/1", "weight/1",
                     "cost/2", "meta_rule_instance/0", "attribute/1"))
    return "\n".join(lines) + "\n"


def _term(symbol: clingo.Symbol) -> str:
    if symbol.type != clingo.SymbolType.Function:
        return str(symbol)
    args = symbol.arguments
    if symbol.name == "var__" and len(args) == 1:
        return f"V{args[0].number}"
    if symbol.name == "bin_exp" and len(args) == 3:
        return f"{_term(args[1])} {args[0].string} {_term(args[2])}"
    if symbol.name == "minus" and len(args) == 1:
        return f"-{_term(args[0])}"
    if not symbol.name:
        return "(" + ", ".join(map(_term, args)) + ("," if len(args) == 1 else "") + ")"
    return ("" if symbol.positive else "-") + symbol.name + (
        "(" + ", ".join(map(_term, args)) + ")" if args else "")


def _literal(symbol: clingo.Symbol, *, head: bool = False) -> str:
    negative = symbol.type == clingo.SymbolType.Function and symbol.name == "naf" and len(symbol.arguments) == 1
    if negative:
        symbol = symbol.arguments[0]
    text = _term(symbol)
    return ("not " if negative and not head else "") + text


def _variables(symbol: clingo.Symbol) -> set[int]:
    if symbol.type != clingo.SymbolType.Function:
        return set()
    if symbol.name == "var__":
        return {symbol.arguments[0].number}
    return set().union(*(_variables(arg) for arg in symbol.arguments))


class _Canonical(ast.Transformer):
    def visit(self, node: ast.AST, *args, **kwargs) -> ast.AST:
        node = node.update(**self.visit_children(node, *args, **kwargs))
        if node.ast_type in {ast.ASTType.Rule, ast.ASTType.Minimize}:
            node = node.update(body=sorted(node.body, key=str))
        if "condition" in node.keys():
            node = node.update(condition=sorted(node.condition, key=str))
        if node.ast_type in {ast.ASTType.Aggregate, ast.ASTType.Disjunction,
                             ast.ASTType.HeadAggregate, ast.ASTType.BodyAggregate}:
            node = node.update(elements=sorted(node.elements, key=str))
        if node.ast_type in {ast.ASTType.Aggregate, ast.ASTType.BodyAggregate}:
            for field, left in (("left_guard", True), ("right_guard", False)):
                guard = getattr(node, field)
                if guard is not None and guard.comparison in {ast.ComparisonOperator.LessThan, ast.ComparisonOperator.GreaterThan}:
                    less = guard.comparison == ast.ComparisonOperator.LessThan
                    operation = ast.BinaryOperator.Plus if less == left else ast.BinaryOperator.Minus
                    bound = ast.BinaryOperation(guard.term.location, operation, guard.term,
                                                ast.SymbolicTerm(guard.term.location, clingo.Number(1)))
                    comparator = ast.ComparisonOperator.LessEqual if less else ast.ComparisonOperator.GreaterEqual
                    node = node.update(**{field: guard.update(comparison=comparator, term=bound)})
        return node


def _canonical(source: str) -> str:
    if source.strip() == ".":
        # The native decoder prints an empty choice head as an empty rule.
        return "."
    nodes, names = parse_candidate(source)
    if len(nodes) != 1 or nodes[0].ast_type not in {ast.ASTType.Rule, ast.ASTType.Minimize}:
        raise ValueError(f"expected a single ASP rule, got {source}")
    return render_candidate(_Canonical()(nodes[0]), names)


def _decode(symbols: list[clingo.Symbol]) -> Entry:
    atoms: dict[tuple[str, int], list[tuple[clingo.Symbol, ...]]] = defaultdict(list)
    for symbol in symbols:
        atoms[symbol.name, len(symbol.arguments)].append(tuple(symbol.arguments))
    conditions: dict[clingo.Symbol, list[clingo.Symbol]] = defaultdict(list)
    for condition, target in atoms["condition", 2]:
        conditions[target].append(condition)

    def literal(symbol: clingo.Symbol, *, head: bool = False) -> str:
        result = _literal(symbol, head=head)
        if symbol in conditions:
            result += " : " + ", ".join(_literal(c) for c in conditions[symbol])
        return result

    body_symbols = [a[0] for a in atoms["body", 1] + atoms["weak_body", 1]]
    body = [literal(s) for s in body_symbols]
    body.extend(f"{_term(typ)}({_term(var)})" for var, typ in atoms["body", 2])
    heads = [a[0] for a in atoms["head", 1]]
    aggregate = [a[0] for a in atoms["in_head", 1]]
    for target in conditions:
        if target not in body_symbols + aggregate:
            raise ValueError(f"condition/2 requires a body or aggregate-head target: {target}")
    # strict_types inserts domain literals, which do not contribute to cost.
    cost = len(body_symbols) + len(atoms["condition", 2]) + len(heads)
    if atoms["weak_body", 1]:
        if not atoms["priority", 1] or not atoms["weight", 1]:
            raise ValueError("a generated weak constraint requires weight/1 and priority/1")
        priority = _term(atoms["priority", 1][-1][0])
        weight = "".join(_term(args[0]) for args in atoms["weight", 1])
        semantic = [symbol for key in ("head", "in_head", "body", "weak_body", "condition")
                    for (name, _), values in atoms.items() if name == key for args in values for symbol in args]
        variables = sorted(set().union(*(_variables(s) for s in semantic)), key=lambda v: f"V{v}")
        terms = "".join(f",V{index}" for index in variables)
        source = f":~ {'; '.join(body)}. [{weight}@{priority}{terms}]"
    else:
        head = "; ".join(literal(s, head=True) for s in (aggregate or heads[-1:]))
        if aggregate and atoms["lb", 1]:
            lower = atoms["lb", 1][-1][0].number
            upper = atoms["ub", 1][-1][0].number if atoms["ub", 1] else 0
            head = f"{lower} {{ {head} }} {upper}"
            n = len(aggregate)
            # Preserve ILASP 4.4.1's recovered nCr behaviour outside 0..n.
            cost += n * sum(comb(n, k) if 0 <= k <= n else 2 ** n for k in range(lower, upper + 1))
        else:
            cost += len(aggregate)
        source = head + (" :- " + "; ".join(body) if body else "") + "."
    if atoms["cost", 2]:
        cost = sum(a[0].number for a in atoms["cost", 2])
    return Entry(cost, _canonical(source), tuple(sorted(str(a[0]) for a in atoms["attribute", 1])),
                 bool(atoms["meta_rule_instance", 0]))


def generate(task: Task, options: Options = Options()) -> tuple[Entry, ...]:
    entries = {Entry(cost, _canonical(source)) for cost, source in task.explicit}
    # In 4.4.1 -s, only a mode declaration activates generated candidates.
    if not task.modes and not options.override_default_sm:
        return tuple(sorted(entries))
    # Native Clingo enables scripts embedded in #bias's generator ASP.
    # Top-level task scripts have already been excluded by the task reader.
    enable_python()
    control = clingo.Control(["0", "--project=show", "--warn=none"], logger=lambda _, message: None)
    control.add("base", [], compile_task(task, options))
    control.ground([("base", [])])
    with control.solve(yield_=True) as handle:
        for model in handle:
            entries.add(_decode(model.symbols(shown=True)))
        result = handle.get()
    if not result.exhausted:
        raise RuntimeError("search-space enumeration was interrupted; output is incomplete")
    return tuple(sorted(entries))
