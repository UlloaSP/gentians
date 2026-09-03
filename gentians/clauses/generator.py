from pathlib import Path

import clingo
from clingo import ast

from ..arguments import Arguments
from ..asp.callbacks import wrapper_exit_callback
from ..asp.stats import clingo_stat, ground_stats
from ..timing import (
    add,
    current_phase,
    instrumentation,
    metric_enabled,
    net_time,
    profile_phase,
    record_metric,
)
from ..language.asp import (
    add_program,
    clause_predicates,
    parse_program,
)
from ..language.ir.inductive_task import InductiveTask
from .reified_clause import ReifiedClause
from .clause import Clause
from .clause_space import ClauseSpace
from .canonicalizer import canonicalize_clauses
from .task_analysis import (
    _clause_capabilities,
    _predicate_arg_types,
    _task_fragments,
    _valid_aggregate_specs,
    _validate_invented_predicates,
)
from .properties import _term_variables
from .decoder import _clause_from_model, _model_literal_index, _theta_reduced
from .fact_compiler import _facts
from .mode_compiler import (
    _clause_modes,
    _condition_limit,
    _section_capacity,
    _variable_arity,
)

def _clause_head_width(clause: ast.AST) -> int:
    head = clause.head
    if (
        head.ast_type == ast.ASTType.Literal
        and head.atom.ast_type == ast.ASTType.BooleanConstant
    ):
        return 0
    if head.ast_type in {ast.ASTType.Literal, ast.ASTType.ConditionalLiteral}:
        return 1
    if head.ast_type in {ast.ASTType.Disjunction, ast.ASTType.Aggregate}:
        return len(head.elements)
    return 0


def clause_space_metrics(
    task: InductiveTask, clause_space: ClauseSpace
) -> dict[str, object]:
    invented = set(task.invented_predicates)
    return {
        "metric": "clause_generation",
        "clauses": len(clause_space),
        "invented_predicates": len(invented),
        "invented_definition_clauses": sum(
            bool(entry.heads & invented) for entry in clause_space.entries
        ),
        "invented_consumer_clauses": sum(
            bool(entry.deps & invented) for entry in clause_space.entries
        ),
    }

CLAUSE_METAPROGRAM_MODULES = (
    "core/slots.lp",
    "core/limits.lp",
    "core/constraints.lp",
    "core/recall.lp",
    "core/arguments.lp",
    "core/head_labels.lp",
    "core/literals.lp",
    "core/conditionals.lp",
    "core/bias.lp",
    "core/tuple_helpers.lp",
    "aggregates/roles.lp",
    "safety/linkedness.lp",
    "safety/typing.lp",
    "safety/variables.lp",
    "safety/asp_safety.lp",
    "safety/mode_directed.lp",
    "operators/comparisons.lp",
    "operators/arithmetic.lp",
    "operators/arithmetic_domain.lp",
    "aggregates/canonicalization.lp",
    "aggregates/safety.lp",
    "aggregates/duplicates.lp",
    "properties/arg_equal.lp",
    "properties/arg_distinct.lp",
    "properties/symmetric.lp",
    "properties/asymmetric.lp",
    "properties/strict_order.lp",
    "properties/equivalent.lp",
    "properties/inverse.lp",
    "properties/disjoint.lp",
    "properties/universal.lp",
    "properties/empty.lp",
    "properties/partition.lp",
    "properties/key.lp",
    "properties/reflexive.lp",
    "properties/total_order.lp",
    "properties/subsumption.lp",
    "properties/irreflexive.lp",
    "properties/antisymmetric.lp",
    "properties/implies.lp",
    "properties/project_implies.lp",
    "properties/complement.lp",
    "properties/mutex.lp",
    "properties/functional.lp",
    "properties/functional_set.lp",
    "properties/cardinality_upper.lp",
    "properties/transitive.lp",
    "properties/acyclic.lp",
    "core/coherence.lp",
    "core/duplicates.lp",
)
CLAUSE_METAPROGRAM = parse_program(
    "\n".join(
        (Path(__file__).with_name("metaprogram") / module).read_text()
        for module in CLAUSE_METAPROGRAM_MODULES
    )
)

class ClauseGenerator:
    def __init__(self, task: InductiveTask, args: Arguments) -> None:
        self.task = task
        self.args = args
        self.fragments = _task_fragments(task)
        if task.max_head_literals is not None and any(
            head.width > task.max_head_literals
            for head in task.language_bias_head
        ):
            raise ValueError("#modeh element count exceeds #maxhl")
        if (
            task.language_bias_aggregate_head
            and task.max_head_literals is not None
            and task.min_aggregate_head_literals > task.max_head_literals
        ):
            raise ValueError("#minhl cannot exceed #maxhl")
        _validate_invented_predicates(task, self.fragments)
        self.predicate_arg_types = _predicate_arg_types(task, self.fragments)
        self.aggregate_specs = _valid_aggregate_specs(task, self.fragments)
        self.capabilities = _clause_capabilities(
            task, self.predicate_arg_types, self.aggregate_specs
        )
        self.modes = _clause_modes(
            task,
            self.capabilities,
            self.predicate_arg_types,
            self.aggregate_specs,
        )
        self.modes_by_id = {mode.id: mode for mode in self.modes}
        self.head_slots = _section_capacity(
            task.max_head_literals, self.modes, "head"
        )
        self.body_slots = _section_capacity(
            task.max_body_literals, self.modes, "body"
        )
        if task.max_body_literals is None:
            self.body_slots += _condition_limit(task)
        self.max_variables = (
            task.max_variables
            if task.max_variables is not None
            else self.head_slots
            * max(
                (
                    _variable_arity(mode)
                    for mode in self.modes
                    if mode.section == "head"
                ),
                default=0,
            )
            + self.body_slots
            * max(
                (
                    _variable_arity(mode)
                    for mode in self.modes
                    if mode.section == "body"
                ),
                default=0,
            )
        )

    def generate(self) -> ClauseSpace:
        facts = _facts(
            self.task,
            self.modes,
            self.predicate_arg_types,
            self.max_variables,
            self.head_slots,
            self.body_slots,
        )
        if not self.task.bias:
            facts += "\ndefault_variable_identity."
        fact_program = parse_program(facts)
        solver_arguments = ["0", *_clause_space_args(self.args)]
        ctl = clingo.Control(solver_arguments, logger=wrapper_exit_callback)
        add_program(ctl, fact_program)
        add_program(ctl, CLAUSE_METAPROGRAM)
        add_program(ctl, self.task.bias)
        start = net_time()
        ctl.ground([("base", [])])
        grounding_seconds = net_time() - start
        phase = current_phase()
        add(f"{phase}.grounding", grounding_seconds)
        model_index = _model_literal_index(ctl.symbolic_atoms, self.modes_by_id)

        clauses: list[ReifiedClause] = []
        seconds = 0.0
        collect_metrics = metric_enabled("clingo")
        start = net_time()
        with ctl.solve(yield_=True) as handle:
            seconds += net_time() - start
            iterator = iter(handle)
            while True:
                start = net_time()
                try:
                    model = next(iterator)
                except StopIteration:
                    seconds += net_time() - start
                    break
                seconds += net_time() - start
                clause = _clause_from_model(model, model_index)
                if _theta_reduced(clause, self.modes_by_id):
                    clauses.append(clause)
            start = net_time()
        seconds += net_time() - start
        add(f"{phase}.solving", seconds)
        if collect_metrics:
            with instrumentation():
                stats = ctl.statistics
                models = clingo_stat(stats, "summary", "models", "enumerated")
                grounded = ground_stats(stats)
                clingo_arguments = " ".join(solver_arguments)
                record_metric(
                    "clingo",
                    {
                        "operation_category": "grounding",
                        "phase_context": phase,
                        "seconds": grounding_seconds,
                        "program_size": 1,
                        "program_chars": sum(map(len, map(str, fact_program)))
                        + sum(map(len, map(str, CLAUSE_METAPROGRAM)))
                        + sum(len(str(statement)) for statement in self.task.bias),
                        "stats_atoms": grounded["atoms"],
                        "stats_rules": grounded["rules"],
                        "clingo_arguments": clingo_arguments,
                    },
                )
                record_metric(
                    "clingo",
                    {
                        "operation_category": "solving",
                        "phase_context": phase,
                        "seconds": seconds,
                        "models": models,
                        "program_size": 1,
                        "has_numeric_evidence": self.capabilities.has_numeric_evidence,
                        "allow_numeric_comparison": self.capabilities.allow_numeric_comparison,
                        "allow_equality_comparison": self.capabilities.allow_equality_comparison,
                        "allow_arithmetic": self.capabilities.allow_arithmetic,
                        "allow_aggregates": self.capabilities.allow_aggregates,
                        "allow_recursion": self.capabilities.allow_recursion,
                        "clingo_arguments": clingo_arguments,
                        "stats_choices": clingo_stat(
                            stats, "solving", "solvers", "choices"
                        ),
                        "stats_conflicts": clingo_stat(
                            stats, "solving", "solvers", "conflicts"
                        ),
                    },
                )

        entries = canonicalize_clauses(
            clauses, self.modes_by_id, self.max_variables
        )
        return ClauseSpace(entries)


@profile_phase("clause_generation")
def build_clause_space(task: InductiveTask, arguments: Arguments) -> ClauseSpace:
    clause_space = ClauseGenerator(task, arguments).generate()
    if task.metarule_programs:
        entries = list(clause_space.entries)
        known_clauses = {entry.text for entry in entries}
        bundle_offset = (
            max(
                (entry.bundle for entry in entries if entry.bundle is not None),
                default=-1,
            )
            + 1
        )
        for bundle, clauses in enumerate(task.metarule_programs, bundle_offset):
            for clause_ast in clauses:
                clause_text = str(clause_ast)
                if clause_text in known_clauses:
                    raise ValueError(
                        "metarule clause duplicates another generated clause: "
                        f"{clause_text}"
                    )
                known_clauses.add(clause_text)
                heads, deps, body_literals = clause_predicates(clause_ast)
                head_literals = _clause_head_width(clause_ast)
                if (
                    task.max_head_literals is not None
                    and head_literals > task.max_head_literals
                ):
                    raise ValueError(f"metarule exceeds #maxhl: {clause_text}")
                if (
                    task.max_body_literals is not None
                    and body_literals > task.max_body_literals
                ):
                    raise ValueError(f"metarule exceeds #maxbl: {clause_text}")
                variables = _term_variables(clause_ast)
                if (
                    task.max_variables is not None
                    and len(variables) > task.max_variables
                ):
                    raise ValueError(f"metarule exceeds #maxv: {clause_text}")
                entries.append(
                    Clause(
                        clause_text,
                        clause_ast,
                        heads,
                        deps,
                        body_literals,
                        bundle,
                    )
                )
        clause_space = ClauseSpace.from_entries(entries)
    if metric_enabled("candidate"):
        with instrumentation():
            record_metric(
                "candidate",
                clause_space_metrics(task, clause_space),
            )
    return clause_space

def _clause_space_args(args: Arguments) -> list[str]:
    value = args.clause_generation.get("clingo_arguments", [])
    if isinstance(value, list):
        return [str(item) for item in value]
    raise ValueError("clause_generation.clingo_arguments must be a list")
