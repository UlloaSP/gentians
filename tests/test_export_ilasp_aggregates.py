from collections import Counter
from pathlib import Path

import clingo
import pytest
from clingo import ast

from benchmarks.catalog import CASES, arguments_for
from benchmarks.export_ilasp_aggregates import (
    background_statement,
    has_body_aggregates,
    render_task,
)
from benchmarks.run_experiments import load_config
from benchmarks.run_ilasp_experiments import load_experiments
from gentians.clauses import generate_clause_space
from gentians.clauses.canonicalization.expression import ArithmeticExpression
from gentians.clauses.canonicalization.expression_constraint import ExpressionConstraint
from gentians.evaluation import create_evaluator
from gentians.gentians import task_from_arguments
from gentians.hypotheses import HypothesisGenerator
from gentians.language.parser import parse_text
from gentians.language.asp import parse_rule
from gentians.language.ast_nodes import BINARY_OPERATORS, UNARY_OPERATORS, LOCATION

ROOT = Path(__file__).resolve().parents[1]
AGGREGATES = [
    name for name in sorted(CASES)
    if has_body_aggregates(task_from_arguments(arguments_for(name)))
]


def _expression(node: ast.AST) -> ArithmeticExpression:
    if node.ast_type == ast.ASTType.Variable:
        return ArithmeticExpression.var(int(node.name.removeprefix("V")))
    if node.ast_type == ast.ASTType.SymbolicTerm:
        if node.symbol.type == clingo.SymbolType.Number:
            return ArithmeticExpression.const(node.symbol.number)
        return ArithmeticExpression.fixed(str(node))
    if node.ast_type == ast.ASTType.BinaryOperation:
        operator = next(key for key, value in BINARY_OPERATORS.items() if value == node.operator_type)
        left, right = _expression(node.left), _expression(node.right)
        if operator == "*":
            for coefficient, term in ((left, right), (right, left)):
                if coefficient.constant is not None and term.variable is not None:
                    return ArithmeticExpression("scale", (coefficient, term))
        return ArithmeticExpression(operator, (left, right))
    if node.ast_type == ast.ASTType.UnaryOperation:
        if node.operator_type == ast.UnaryOperator.Absolute and node.argument.ast_type == ast.ASTType.BinaryOperation and node.argument.operator_type == ast.BinaryOperator.Minus:
            return ArithmeticExpression("abs", (_expression(node.argument.left), _expression(node.argument.right)))
        operator = next(key for key, value in UNARY_OPERATORS.items() if value == node.operator_type)
        return ArithmeticExpression(operator, (_expression(node.argument),))
    return ArithmeticExpression.fixed(str(node))


class _ComparisonKeys(ast.Transformer):
    def visit_Comparison(self, node: ast.AST) -> ast.AST:
        if len(node.guards) != 1:
            return node
        guard = node.guards[0]
        relation = {
            ast.ComparisonOperator.Equal: "eq",
            ast.ComparisonOperator.NotEqual: "ne",
            ast.ComparisonOperator.LessThan: "lt",
            ast.ComparisonOperator.LessEqual: "le",
        }.get(guard.comparison)
        if relation is None:
            return node
        left, right = _expression(node.term), _expression(guard.term)
        expression = left if right.constant == 0 else ArithmeticExpression("-", (left, right))
        key = ExpressionConstraint(expression, relation).key
        return ast.Comparison(
            ast.SymbolicTerm(LOCATION, clingo.String(repr(key))),
            [ast.Guard(ast.ComparisonOperator.Equal, ast.SymbolicTerm(LOCATION, clingo.Number(0)))],
        )


def _weighted_export(text: str) -> tuple[str, Counter[tuple[int, str]]]:
    """Keep the task exact; compare all candidates and costs independently of format.

    Clingo formatting can select a different expression representative for the
    same canonical arithmetic key. Use Gentians' existing expression keys for
    those relations, preserving every other part of each complete rule.
    """
    prefix, candidates = [], Counter()
    for line in text.splitlines():
        cost, separator, rule = line.partition(" ~ ")
        if separator:
            candidates[int(cost), str(_ComparisonKeys()(parse_rule(rule)))] += 1
        else:
            prefix.append(line)
    return "\n".join(prefix), candidates


@pytest.mark.parametrize("dataset", AGGREGATES)
def test_checked_in_export_is_complete_and_current(dataset: str) -> None:
    arguments = arguments_for(dataset)
    task = task_from_arguments(arguments)
    space = generate_clause_space(task, arguments)
    exported = ROOT / "benchmarks/ilasp" / f"{dataset}.las"
    assert _weighted_export(exported.read_text(encoding="utf-8")) == _weighted_export(render_task(task, space, Path(arguments.filename)))
    assert b"\r" not in exported.read_bytes()
    assert len(space) > 0
    assert all(clause.body_literals + bool(clause.heads) > 0 for clause in space.entries)


@pytest.mark.parametrize(("dataset", "solution"), [
    ("subset_sum_triple",
     "ok(V3) :- #sum{V0,V1,V2:el(V0,V1,V2)}=V3,"
     "#sum{V0,V1,V2:el(V1,V0,V2)}=V3,#sum{V0,V1,V2:el(V1,V2,V0)}=V3."),
    ("subset_sum_double_and_prod",
     "ok(V4) :- #sum{V0,V1:el(V0,V1)}=V2,#sum{V0,V1:el(V1,V0)}=V3,V2*V3=V4."),
    ("subset_sum_double_and_prod_unbalanced",
     "ok(V4) :- #sum{V0:el(V0,V1)}=V2,#sum{V0:el(V1,V0)}=V3,V2*V3=V4."),
    ("hamming_1_unbalanced",
     ":- hd(V0),#sum{V1,V2:d(V2,V1)}=V3,V0-V3!=0."),
])
def test_previously_unsatisfiable_benchmarks_have_exported_perfect_hypotheses(dataset, solution):
    solution = str(parse_rule(solution))
    arguments = arguments_for(dataset)
    task = task_from_arguments(arguments)
    space = generate_clause_space(task, arguments)
    hypotheses = HypothesisGenerator(task, space, task.max_program_clauses or len(space))
    genome = hypotheses.encode((solution,))
    assert create_evaluator(task, arguments.evaluation)(hypotheses.program(genome)).is_solution
    clause = next(clause for clause in space.entries if clause.text == solution)
    cost = clause.body_literals + bool(clause.heads)
    _, candidates = _weighted_export((ROOT / "benchmarks/ilasp" / f"{dataset}.las").read_text())
    assert candidates[cost, str(_ComparisonKeys()(parse_rule(solution)))] == 1


def test_singleton_choice_translation_preserves_stable_models() -> None:
    source = "{p(1)}."
    translated = background_statement(source)
    assert translated == "0 {p(1)} 1."

    def models(program):
        control = clingo.Control(["0"])
        control.add("base", [], program)
        control.ground([("base", [])])
        with control.solve(yield_=True) as handle:
            return {tuple(sorted(map(str, model.symbols(atoms=True)))) for model in handle}

    assert models(source) == models(translated) == {(), ("p(1)",)}


def test_export_preserves_included_excluded_and_context(tmp_path: Path) -> None:
    source = tmp_path / "context.txt"
    source.write_text("""
#maxv(2).
#maxbl(1).
#modeh(1,total(var(numeric,output))).
#modeb(1,#sum{var(numeric,any,x):value(var(numeric,any,x))}=var(numeric,output,s)).
#pos({total(3)}, {total(4)}, {value(1). value(2).}).
#neg({total(9)}, {total(3)}, {value(3).}).
""", newline="\n")
    task = parse_text(source.read_text())
    space = generate_clause_space(task, arguments_for("subset_sum"))
    exported = render_task(task, space, source)
    assert "#pos({total(3)}, {total(4)}, {value(1).\nvalue(2).})." in exported
    assert "#neg({total(9)}, {total(3)}, {value(3).})." in exported
    assert "2 ~ total(" in exported
    source.write_bytes(source.read_bytes().replace(b"\n", b"\r\n"))
    assert render_task(task, space, source) == exported


def test_comparison_matrix_matches_all_six_algorithms() -> None:
    ilasp = next(experiment for experiment in load_experiments(ROOT / "benchmarks/ilasp_experiments.toml")
                 if experiment.id == "all-120s-30runs")
    _, experiments = load_config(ROOT / "benchmarks/experiments.toml")
    gentians = [experiment for experiment in experiments
                if experiment["id"].startswith("ilasp-all-120s-30runs/")]
    assert len(AGGREGATES) == 20
    assert len(ilasp.datasets) == len(set(ilasp.datasets)) == 29
    assert set(AGGREGATES) <= set(ilasp.datasets)
    assert ilasp.versions == ("2", "2i", "3", "4")
    assert ilasp.runs == 30 and ilasp.timeout_seconds == 120
    assert {experiment["overrides"]["algorithm"] for experiment in gentians} == {"steady_state", "incremental"}
    for experiment in gentians:
        assert experiment["datasets"] == list(ilasp.datasets)
        assert experiment["runs"] == 30 and experiment["timeout_seconds"] == 120
        assert experiment["seed_base"] == 42
        assert not experiment.get("stop_on_timeout", False)
    for dataset in ilasp.datasets:
        content = (ilasp.task_dir / f"{dataset}.las").read_text(encoding="utf-8")
        assert (" ~ " in content) == (dataset in AGGREGATES)
