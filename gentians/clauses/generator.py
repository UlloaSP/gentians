from pathlib import Path
import random
from collections.abc import Generator, Iterator
from contextlib import closing, contextmanager
from typing import cast

import clingo
from clingo.configuration import Configuration

from ..arguments import Arguments
from ..clingo_stats import clingo_stat, ground_stats
from ..timing import (
    add,
    instrumentation,
    metric_enabled,
    net_time,
    phase,
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

    @profile_phase("clause_generation")
    def _prepare(self, model_limit: int, seed: int | None, by_size: bool = False):
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
        if by_size:
            facts += "\nenumerate_by_size."
        fact_program = parse_program(facts)
        solver_arguments = [str(model_limit), *_clause_space_args(self.args)]
        ctl = clingo.Control(solver_arguments, logger=_raise_on_clingo_error)
        if by_size:
            # Keep symbolic literal indices valid across all size assumptions.
            ctl.enable_cleanup = False
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
        add("clause_generation.grounding", grounding_seconds)
        model_index = _model_literal_index(ctl.symbolic_atoms, self.modes_by_id)
        return ctl, model_index, fact_program, solver_arguments, grounding_seconds

    def batches(
        self, size: int, seed: int | None, *, model_limit: int = 0,
        by_size: bool = False,
    ) -> Generator[ClauseSpace, None, None]:
        ctl, model_index, fact_program, solver_arguments, grounding_seconds = self._prepare(
            model_limit, seed, by_size
        )
        strata = (
            [(atom.literal,) for atom in sorted(
                ctl.symbolic_atoms.by_signature("clause_body_size", 1),
                key=lambda atom: atom.symbol.arguments[0].number,
            )]
            if by_size else [()]
        )
        for ordinal, assumptions in enumerate(strata):
            seconds = 0.0
            collect_metrics = metric_enabled("clingo")
            # The handle stays suspended between batches. Never retain a clingo.Model.
            # ponytail: grounding still covers the full bias; partition it if that dominates.
            try:
                with phase("clause_generation"):
                    start = net_time()
                    handle = ctl.solve(yield_=True, assumptions=assumptions)
                    elapsed = net_time() - start
                try:
                    iterator = iter(handle)
                    exhausted = False
                    while not exhausted:
                        with phase("clause_generation"):
                            clauses: list[ReifiedClause] = []
                            models = 0
                            while not size or models < size:
                                start = net_time()
                                model = next(iterator, None)
                                elapsed += net_time() - start
                                if model is None:
                                    exhausted = True
                                    break
                                models += 1
                                clause = _clause_from_model(model, model_index)
                                if _theta_reduced(clause, self.modes_by_id):
                                    clauses.append(clause)
                                del model
                            seconds += elapsed
                            elapsed = 0.0
                            entries = canonicalize_clauses(
                                clauses, self.modes_by_id, self.max_variables
                            )
                            batch = ClauseSpace(entries)
                        # No timing phase may span a yield: the consumer runs its GA here.
                        if models or not size:
                            yield batch
                            del batch, entries, clauses
                finally:
                    with phase("clause_generation"):
                        start = net_time()
                        handle.__exit__(None, None, None)
                        elapsed = net_time() - start
                        seconds += elapsed
                        add("clause_generation.solving", seconds)
            finally:
                if collect_metrics:
                    with instrumentation():
                        self._record_solve(
                            ctl, fact_program, solver_arguments, model_limit, seed,
                            grounding_seconds if ordinal == 0 else None, seconds,
                        )

    def _record_solve(
        self, ctl, fact_program, solver_arguments, model_limit, seed,
        grounding_seconds, seconds,
    ) -> None:
        stats = ctl.statistics
        models = clingo_stat(stats, "summary", "models", "enumerated")
        grounded = ground_stats(stats)
        clingo_arguments = " ".join(solver_arguments)
        if grounding_seconds is not None:
            record_metric(
                "clingo",
                {
                    "operation_category": "grounding",
                    "phase_context": "clause_generation",
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
                "phase_context": "clause_generation",
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

def generate_clause_space(task: InductiveTask, arguments: Arguments) -> ClauseSpace:
    with phase("clause_generation"):
        generator = _ClauseGenerator(task, arguments)
    with closing(generator.batches(0, None)) as batches:
        return next(batches)


@contextmanager
def incremental_clause_batches(
    task: InductiveTask, arguments: Arguments, size: int, rng: random.Random,
) -> Iterator[Iterator[ClauseSpace]]:
    """Ground once and enumerate by increasing body budget; close on exit or failure.

    The budget counts models before pruning. Canonicalization deduplicates each
    batch; equivalent clauses may occur in different batches. No history of all
    clauses is retained, and the iterator ends when enumeration is exhausted.
    Each body size has one resumable solve. Ordering changes the visited prefix,
    not the legal clause space.
    """
    if isinstance(size, bool) or not isinstance(size, int) or size < 1:
        raise ValueError("clause batch size must be a positive integer")
    with phase("clause_generation"):
        generator = _ClauseGenerator(task, arguments)
    with closing(generator.batches(
        size, rng.randrange(2**31), by_size=True
    )) as batches:
        yield batches


def _clause_space_args(args: Arguments) -> list[str]:
    value = args.clause_generation.get("clingo_arguments", [])
    if isinstance(value, list):
        return [str(item) for item in value]
    raise ValueError("clause_generation.clingo_arguments must be a list")
