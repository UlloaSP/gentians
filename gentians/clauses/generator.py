from pathlib import Path
import random
from typing import cast

import clingo
from clingo.configuration import Configuration

from ..arguments import Arguments
from ..clingo_stats import clingo_stat, ground_stats
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
    parse_program,
)
from ..language.ir.inductive_task import InductiveTask
from .reified_clause import ReifiedClause
from .clause_space import ClauseSpace
from .canonicalizer import canonicalize_clauses
from .task_analysis import (
    _clause_capabilities,
    _predicate_arg_types,
    _prune_optional_constraints,
    _valid_aggregate_specs,
    _validate_invented_predicates,
)
from .extensions import _task_nodes
from .decoder import _clause_from_model, _model_literal_index, _theta_reduced
from .fact_compiler import _facts
from .mode_compiler import (
    _clause_modes,
    _condition_limit,
    _section_capacity,
    _variable_arity,
)


def _raise_on_clingo_error(code, message):
    if "error" in message:
        raise RuntimeError(f"{code}\n{message}")


CLAUSE_METAPROGRAM_MODULES = (
    "core/slots.lp",
    "core/limits.lp",
    "core/constraints.lp",
    "core/recall.lp",
    "core/arguments.lp",
    "core/head_labels.lp",
    "core/literals.lp",
    "core/conditionals.lp",
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


class _ClauseGenerator:
    def __init__(self, task: InductiveTask, args: Arguments) -> None:
        self.task = task
        self.args = args
        self.prune_constraints = _prune_optional_constraints(task)
        self.nodes = _task_nodes(task)
        if task.max_head_literals is not None and any(
            head.width > task.max_head_literals for head in task.language_bias_head
        ):
            raise ValueError("#modeh element count exceeds #maxhl")
        if (
            task.language_bias_aggregate_head
            and task.max_head_literals is not None
            and task.min_aggregate_head_literals > task.max_head_literals
        ):
            raise ValueError("#minhl cannot exceed #maxhl")
        _validate_invented_predicates(task, self.nodes)
        self.predicate_arg_types = _predicate_arg_types(task, self.nodes)
        self.aggregate_specs = _valid_aggregate_specs(task, self.nodes)
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
        self.head_slots = _section_capacity(task.max_head_literals, self.modes, "head")
        self.body_slots = _section_capacity(task.max_body_literals, self.modes, "body")
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

    def generate(self, model_limit: int = 0, seed: int | None = None) -> ClauseSpace:
        facts = _facts(
            self.task,
            self.modes,
            self.predicate_arg_types,
            self.max_variables,
            self.head_slots,
            self.body_slots,
        )
        if self.prune_constraints:
            # Prune inside ASP enumeration, before decoding/canonicalization.
            # The static proof protects nonempty and constraint-only solutions.
            facts += "\nprune_optional_constraints."
        fact_program = parse_program(facts)
        solver_arguments = [str(model_limit), *_clause_space_args(self.args)]
        ctl = clingo.Control(solver_arguments, logger=_raise_on_clingo_error)
        if seed is not None:
            # Randomized prefixes are bounded samples, not uniform samples of clauses.
            cast(Configuration, ctl.configuration.solve).parallel_mode = "1"
            solver_config = cast(Configuration, ctl.configuration.solver)[0]
            solver_config.seed = str(seed)
            solver_config.rand_freq = "1"
            solver_config.sign_def = "rnd"
        cast(Configuration, ctl.configuration.solve).models = str(model_limit)
        add_program(ctl, fact_program)
        add_program(ctl, CLAUSE_METAPROGRAM)
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
                        + sum(map(len, map(str, CLAUSE_METAPROGRAM))),
                        "stats_atoms": grounded["atoms"],
                        "stats_rules": grounded["rules"],
                        "clingo_arguments": clingo_arguments,
                        "model_limit": model_limit,
                        "sampling_seed": seed,
                        "sampling_configuration": (
                            {"parallel_mode": "1", "rand_freq": "1", "sign_def": "rnd"}
                            if seed is not None else None
                        ),
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

        entries = canonicalize_clauses(clauses, self.modes_by_id, self.max_variables)
        return ClauseSpace(entries)


@profile_phase("clause_generation")
def generate_clause_space(task: InductiveTask, arguments: Arguments) -> ClauseSpace:
    return _ClauseGenerator(task, arguments).generate()


@profile_phase("clause_generation")
def sample_clause_space(
    task: InductiveTask, arguments: Arguments, size: int, rng: random.Random
) -> ClauseSpace:
    """Decode at most size models; canonicalize only this batch, not the full space."""
    if isinstance(size, bool) or not isinstance(size, int) or size < 1:
        raise ValueError("clause batch size must be a positive integer")
    return _ClauseGenerator(task, arguments).generate(size, rng.randrange(2**31))


def _clause_space_args(args: Arguments) -> list[str]:
    value = args.clause_generation.get("clingo_arguments", [])
    if isinstance(value, list):
        return [str(item) for item in value]
    raise ValueError("clause_generation.clingo_arguments must be a list")
