import random
from collections.abc import Generator, Iterator
from contextlib import closing, contextmanager
from functools import cached_property, lru_cache
from collections import OrderedDict
from pathlib import Path
from typing import cast

import clingo
from clingo.configuration import Configuration

from ..arguments import Arguments
from ..clingo_stats import clingo_statistics
from ..language.asp import add_program, parse_program
from ..language.ir.inductive_task import InductiveTask
from ..timing import (
    add,
    instrumentation,
    is_enabled,
    metric_enabled,
    net_time,
    phase,
    profile_phase,
    record_metric,
)
from .analysis.inference import _closed_world_properties
from .analysis.capabilities import ClauseCapabilities
from .analysis.task import (
    _clause_capabilities,
    _closed_world_contexts,
    _learned_predicates,
    _negated_predicates,
    _predicate_arg_types,
    _property_predicates,
    _task_nodes,
    _validate_invented_predicates,
)
from .canonicalization.clauses import ClauseCanonicalizer
from .clause_space import ClauseSpace
from .decoder import _clause_from_model, _ModelDecoder
from .fact_compiler import _facts
from .mode_compiler import (
    _clause_modes,
    _condition_limit,
    _section_capacity,
)
from .pruning import _prune_optional_constraints
from .subsets import SubsetClauses, independent_unary
from .execution import generation_gc
from .records import ModelRecords, _records
from .binding_facts import nominal_binding_facts, connected_binding_facts
from .component_facts import comparison_component_facts, PROJECTED_COMPONENTS
from .property_consumers import PropertyMaps
from .property_bindings import property_binding_facts


def _raise_on_clingo_error(code, message):
    if "error" in message:
        raise RuntimeError(f"{code}\n{message}")


CLAUSE_METAPROGRAM_MODULES = (
    "representation/schema.lp",
    "representation/aggregates.lp",
    "representation/arguments.lp",
    "representation/arithmetic.lp",
    "representation/conditionals.lp",
    "representation/literals.lp",
    "representation/operators.lp",
    "representation/output.lp",
    "representation/slots.lp",
    "representation/tuples.lp",
    "representation/variables.lp",
    "inference/numeric.lp",
    "legality/aggregates.lp",
    "legality/asp_safety.lp",
    "legality/clause_shape.lp",
    "legality/flow/declarations.lp",
    "legality/flow/closure.lp",
    "legality/flow/requirements.lp",
    "legality/flow/removal.lp",
    "legality/flow/seeds.lp",
    "legality/invention.lp",
    "legality/labels.lp",
    "legality/linkedness.lp",
    "legality/recall.lp",
    "legality/scopes.lp",
    "legality/typing.lp",
    "symmetry/aggregates.lp",
    "symmetry/arithmetic.lp",
    "symmetry/comparisons.lp",
    "symmetry/conditions.lp",
    "symmetry/slots.lp",
    "symmetry/variables.lp",
    "pruning/contradictions/comparisons.lp",
    "pruning/contradictions/numeric.lp",
    "pruning/policies/aggregates.lp",
    "pruning/policies/comparisons.lp",
    "pruning/policies/singletons.lp",
    "pruning/properties/acyclic.lp",
    "pruning/properties/antisymmetric.lp",
    "pruning/properties/arg_distinct.lp",
    "pruning/properties/arg_equal.lp",
    "pruning/properties/asymmetric.lp",
    "pruning/properties/cardinality_upper.lp",
    "pruning/properties/complement.lp",
    "pruning/properties/disjoint.lp",
    "pruning/properties/domains.lp",
    "pruning/properties/empty.lp",
    "pruning/properties/equivalent.lp",
    "pruning/properties/functional.lp",
    "pruning/properties/functional_set.lp",
    "pruning/properties/implies.lp",
    "pruning/properties/inverse.lp",
    "pruning/properties/irreflexive.lp",
    "pruning/properties/key.lp",
    "pruning/properties/mutex.lp",
    "pruning/properties/partition.lp",
    "pruning/properties/project_implies.lp",
    "pruning/properties/reflexive.lp",
    "pruning/properties/strict_order.lp",
    "pruning/properties/subsumption.lp",
    "pruning/properties/symmetric.lp",
    "pruning/properties/total_order.lp",
    "pruning/properties/transitive.lp",
    "pruning/properties/universal.lp",
    "pruning/redundancy/aggregates.lp",
    "pruning/redundancy/arithmetic.lp",
    "pruning/redundancy/comparisons.lp",
    "pruning/redundancy/conditions.lp",
    "pruning/redundancy/literals.lp",
    "pruning/redundancy/numeric.lp",
    "pruning/redundancy/tautologies.lp",
    "pruning/redundancy/theta.lp",
    "pruning/task/optional_constraints.lp",
)


# Reuse the fixed native program; parse_program already discards comments.
CLAUSE_METAPROGRAM = parse_program(
    "\n".join(
        (Path(__file__).with_name("metaprogram") / module).read_text()
        for module in CLAUSE_METAPROGRAM_MODULES
    )
)


@lru_cache(maxsize=1)
def _metaprogram_chars():
    return sum(map(len, map(str, CLAUSE_METAPROGRAM)))


class _ClauseGenerator:
    def __init__(self, task: InductiveTask, args: Arguments) -> None:
        self.task = task
        self.args = args
        choices = {"engine": ("auto", {"auto", "asp", "direct", "subsets"}),
                   "transport": ("auto", {"auto", "python", "native"}),
                   "callback": ("native", {"native", "python"}),
                   "storage": ("auto", {"auto", "packed", "recipes"}),
                   "bindings": ("standard", {"standard", "nominal", "properties", "connected"}),
                   "body": ("slots", {"slots", "counts"}),
                   "arithmetic": ("standard", {"standard", "components", "projected"}),
                   "strata": ("assumptions", {"assumptions", "ground"}),
                   "gc": ("normal", {"normal", "defer"})}
        for key, (default, accepted) in choices.items():
            value = args.clause_generation.get(key, default)
            if not isinstance(value, str) or value not in accepted:
                raise ValueError(f"clause_generation.{key} must be one of {', '.join(sorted(accepted))}")
        if args.clause_generation.get("transport") == "native" and _records is None:
            raise RuntimeError("native clause records are unavailable in this installation")
        configuration = args.clause_generation.get("configuration")
        if configuration is not None and (not isinstance(configuration, str) or configuration not in {
            "auto", "frumpy", "jumpy", "tweety", "handy", "crafty", "trendy"
        }):
            raise ValueError("unknown exhaustive Clingo generation configuration")
        workers = args.clause_generation.get("workers", 1)
        if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
            raise ValueError("clause_generation.workers must be a positive integer")
        if workers > 1 and args.clause_generation.get("engine", "auto") not in {"auto", "asp"}:
            raise ValueError("process partitions require the general asp engine")
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
        if metric_enabled("clingo"):
            # Keep enabled diagnostics inside the existing preparation phase.
            _ = self.capabilities
        self.modes = _clause_modes(task)
        self.modes_by_id = {mode.id: mode for mode in self.modes}
        self.fact_cache: OrderedDict[int, str] = OrderedDict()
        self.program_chars = lru_cache(maxsize=8)(
            lambda facts: sum(map(len, map(str, parse_program(facts)))) + _metaprogram_chars()
        )
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
                    len(mode.bindings)
                    for mode in self.modes
                    if mode.section == "head"
                ),
                default=0,
            )
            + self.body_slots
            * max(
                (
                    len(mode.bindings)
                    for mode in self.modes
                    if mode.section == "body"
                ),
                default=0,
            )
        )

    @cached_property
    def predicate_arg_types(self) -> dict[tuple[str, int, int], str]:
        return _predicate_arg_types(self.task, self.nodes)

    @cached_property
    def capabilities(self) -> ClauseCapabilities:
        return _clause_capabilities(self.task, self.predicate_arg_types)

    @cached_property
    def property_maps(self):
        return PropertyMaps(self.modes)

    @cached_property
    def projected_components(self):
        return (self.args.clause_generation.get("arithmetic") == "projected"
                and bool(comparison_component_facts(self.modes)))

    @cached_property
    def properties(self):
        return _closed_world_properties(
            _closed_world_contexts(self.task), _learned_predicates(self.task),
            _property_predicates(self.task), _negated_predicates(self.task),
            self.property_maps if self.args.clause_generation.get("infer_maps", True) else None,
        )

    @profile_phase("clause_generation")
    def _prepare(self, seed: int | None, by_size: bool = False, exact_size: int | None = None):
        facts = self._fact_text(by_size, exact_size)
        solver_arguments = self.solver_arguments()
        ctl = clingo.Control(solver_arguments, logger=_raise_on_clingo_error)
        if by_size or exact_size is not None:
            ctl.enable_cleanup = False
        if seed is not None:
            cast(Configuration, ctl.configuration.solve).parallel_mode = "1"
            solver_config = cast(Configuration, ctl.configuration.solver)[0]
            solver_config.seed = str(seed)
            solver_config.rand_freq = "1"
            solver_config.sign_def = "rnd"
        cast(Configuration, ctl.configuration.solve).models = "0"
        if self.projected_components:
            cast(Configuration, ctl.configuration.solve).project = "project"
        ctl.add("base", [], facts)
        add_program(ctl, CLAUSE_METAPROGRAM)
        measure = is_enabled() or metric_enabled("clingo")
        start = net_time() if measure else 0.0
        ctl.ground([("base", [])])
        grounding_seconds = net_time() - start if measure else 0.0
        add("clause_generation.grounding", grounding_seconds)
        decoder = _ModelDecoder(ctl.symbolic_atoms, self.modes_by_id)
        return ctl, decoder, facts, solver_arguments, grounding_seconds

    def solver_arguments(self) -> list[str]:
        configuration = self.args.clause_generation.get("configuration")
        arguments = _clause_space_args(self.args)
        explicit = any(arg == "--configuration" or arg.startswith("--configuration=") for arg in arguments)
        return [*([] if configuration in {None, "auto"} or explicit else [f"--configuration={configuration}"]),
                *arguments]

    def _fact_text(self, by_size=False, exact_size=None):
        body_slots = self.body_slots if exact_size is None else min(self.body_slots, exact_size)
        facts = self.fact_cache.get(body_slots)
        if facts is None:
            facts = _facts(self.task, self.modes, self.properties, self.max_variables,
                           self.head_slots, body_slots, self.property_maps)
            if len(self.fact_cache) >= 8:
                self.fact_cache.popitem(last=False)
            self.fact_cache[body_slots] = facts
        if self.args.clause_generation.get("bindings", "standard") == "nominal":
            facts += "\n" + "\n".join(nominal_binding_facts(self.modes))
        elif self.args.clause_generation.get("bindings", "standard") == "properties":
            facts += "\n" + "\n".join(property_binding_facts(self.modes, self.properties))
        elif self.args.clause_generation.get("bindings", "standard") == "connected":
            facts += "\n" + "\n".join(connected_binding_facts(self.modes))
        if self.args.clause_generation.get("arithmetic", "standard") in {"components", "projected"}:
            facts += "\n" + "\n".join(comparison_component_facts(self.modes))
        if self.projected_components:
            facts += "\n" + PROJECTED_COMPONENTS
        body_representation = self.args.clause_generation.get("body", "slots")
        if body_representation == "counts":
            facts += "\nbody_counts."
        elif body_representation != "slots":
            raise ValueError("clause_generation.body must be slots or counts")
        if self.prune_constraints:
            # Prune inside ASP enumeration, before decoding/canonicalization.
            # The static proof protects nonempty and constraint-only solutions.
            facts += "\nprune_optional_constraints."
        if by_size:
            facts += "\nenumerate_by_size."
        if exact_size is not None:
            facts += f"\n:- clause_body_size(Size), Size != {exact_size}."
        return facts

    def batches(
        self, size: int, seed: int | None, *,
        by_size: bool = False,
    ) -> Generator[ClauseSpace, None, None]:
        strata_policy = self.args.clause_generation.get("strata", "assumptions")
        if by_size and strata_policy == "ground":
            from dataclasses import replace
            # This prepares the smaller slot domain for each exact *total* cost.
            # Head/body attached conditions remain part of clause_body_size.
            config = {**self.args.clause_generation, "strata": "assumptions"}
            with phase("clause_generation"):
                child = _ClauseGenerator(self.task, replace(self.args, clause_generation=config))
                child.__dict__["properties"] = self.properties
            for budget in range(self.body_slots + 1):
                with closing(child._grounded_size_batches(size, seed, budget)) as batches:
                    yield from batches
            return
        if strata_policy not in {"assumptions", "ground"}:
            raise ValueError("clause_generation.strata must be assumptions or ground")
        yield from self._grounded_size_batches(size, seed, None, by_size=by_size)

    def _grounded_size_batches(self, size, seed, exact_size, *, by_size=False):
        ctl, decoder, facts, solver_arguments, grounding_seconds = self._prepare(
            seed, by_size or exact_size is not None, exact_size
        )
        with phase("clause_generation"):
            records = ModelRecords(decoder) if self.args.clause_generation.get("transport", "auto") != "python" and _records is not None else None
        strata = (
            [(atom.literal,) for atom in sorted(
                ctl.symbolic_atoms.by_signature("clause_body_size", 1),
                key=lambda atom: atom.symbol.arguments[0].number,
            )]
            if by_size and exact_size is None else [()]
        )
        for ordinal, assumptions in enumerate(strata):
            seconds = 0.0
            collect_metrics = metric_enabled("clingo")
            measure = is_enabled() or collect_metrics
            # The handle stays suspended between batches. Never retain a clingo.Model.
            # ponytail: grounding still covers the full bias; partition it if that dominates.
            try:
                with phase("clause_generation"):
                    start = net_time() if measure else 0.0
                    handle = ctl.solve(yield_=True, assumptions=assumptions)
                    elapsed = net_time() - start if measure else 0.0
                try:
                    iterator = iter(handle)
                    exhausted = False
                    while not exhausted:
                        with phase("clause_generation"), generation_gc(self.args.clause_generation.get("gc", "normal")):
                            canonicalizer = ClauseCanonicalizer(self.modes_by_id, self.max_variables,
                                                                pack=self.args.clause_generation.get("storage", "auto") == "packed")
                            models = 0
                            while not size or models < size:
                                if measure:
                                    start = net_time()
                                    model = next(iterator, None)
                                    elapsed += net_time() - start
                                else:
                                    model = next(iterator, None)
                                if model is None:
                                    exhausted = True
                                    break
                                models += 1
                                if records is None:
                                    canonicalizer.add(_clause_from_model(model, decoder))
                                else:
                                    block = records.push(model)
                                    if block is not None:
                                        for clause in records.clauses(block):
                                            canonicalizer.add(clause)
                                del model
                            if records is not None:
                                block = records.flush()
                                if block is not None:
                                    for clause in records.clauses(block):
                                        canonicalizer.add(clause)
                            seconds += elapsed
                            elapsed = 0.0
                            batch = ClauseSpace(canonicalizer.finish())
                            del canonicalizer
                        # No timing phase may span a yield: the consumer runs its GA here.
                        if models or not size:
                            yield batch
                            del batch
                finally:
                    with phase("clause_generation"):
                        start = net_time() if measure else 0.0
                        handle.__exit__(None, None, None)
                        elapsed = net_time() - start if measure else 0.0
                        seconds += elapsed
                        add("clause_generation.solving", seconds)
            finally:
                if collect_metrics:
                    with instrumentation():
                        self._record_solve(
                            ctl, facts, solver_arguments, seed,
                            grounding_seconds if ordinal == 0 else None, seconds,
                        )

    def clause_space(self) -> ClauseSpace:
        """Enumerate the complete space in one callback solve.

        Without batches nothing has to suspend the search, so models are decoded
        in the solver callback instead of crossing threads one at a time.
        """
        with phase("clause_generation"):
            workers = self.args.clause_generation.get("workers", 1)
            if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
                raise ValueError("clause_generation.workers must be a positive integer")
            if workers > 1:
                from .partitions import partitioned_space
                return partitioned_space(self, workers)
            engine = self.args.clause_generation.get("engine", "auto")
            if engine not in {"auto", "asp", "direct", "subsets"}:
                raise ValueError("clause_generation.engine must be auto, asp, direct or subsets")
            if engine != "asp":
                eligible = (not self.task.invented_predicates
                            and not self.task.language_bias_condition
                            and independent_unary(self.modes, self.max_variables, self.properties))
                if eligible:
                    return SubsetClauses(self.modes, self.body_slots, self.prune_constraints,
                                         self.head_slots).space(
                        "direct" if engine == "auto" else str(engine), self.solver_arguments(),
                        pack=(self.args.clause_generation.get("storage", "auto") == "packed"
                              or self.args.clause_generation.get("storage", "auto") == "auto"
                              and engine in {"auto", "direct"} and _records is not None),
                    )
                if engine != "auto":
                    raise ValueError(f"{engine} requires independent unary output-only body modes")
        ctl, decoder, facts, solver_arguments, grounding_seconds = self._prepare(None)
        with phase("clause_generation"):
            canonicalizer = ClauseCanonicalizer(self.modes_by_id, self.max_variables,
                                                pack=self.args.clause_generation.get("storage", "auto") == "packed")
            transport = self.args.clause_generation.get("transport", "auto")
            records = ModelRecords(decoder) if transport == "native" or transport == "auto" and _records is not None else None
        callback_seconds = 0.0
        collect_metrics = metric_enabled("clingo")
        measure = is_enabled() or collect_metrics

        def decode(model: clingo.Model) -> None:
            if records is None:
                canonicalizer.add(_clause_from_model(model, decoder))
            else:
                block = records.push(model)
                if block is not None:
                    for clause in records.clauses(block):
                        canonicalizer.add(clause)

        def measured_decode(model: clingo.Model) -> None:
            nonlocal callback_seconds
            start = net_time()
            decode(model)
            callback_seconds += net_time() - start

        def consume(block):
            assert records is not None
            for clause in records.clauses(block):
                canonicalizer.add(clause)

        seconds = 0.0
        try:
            with phase("clause_generation"):
                start = net_time() if measure else 0.0
                if records is not None and self.args.clause_generation.get("callback", "native") == "native":
                    _models, callback_seconds = records.solve(ctl, consume, measure)
                else:
                    ctl.solve(on_model=measured_decode if measure else decode)
                seconds = net_time() - start - callback_seconds if measure else 0.0
                add("clause_generation.solving", seconds)
                if records is not None:
                    block = records.flush()
                    if block is not None:
                        for clause in records.clauses(block):
                            canonicalizer.add(clause)
                return ClauseSpace(canonicalizer.finish())
        finally:
            if collect_metrics:
                with instrumentation():
                    self._record_solve(
                        ctl, facts, solver_arguments, None,
                        grounding_seconds, seconds,
                    )

    def _record_solve(
        self, ctl, facts, solver_arguments, seed,
        grounding_seconds, seconds,
    ) -> None:
        stats = clingo_statistics(ctl)
        clingo_arguments = " ".join(solver_arguments)
        if grounding_seconds is not None:
            record_metric(
                "clingo",
                {
                    "operation_category": "grounding",
                    "phase_context": "clause_generation",
                    "seconds": grounding_seconds,
                    "program_size": 1,
                    # Preserve the canonical character metric only while recording;
                    # normal generation loads facts directly through Clingo's parser.
                    "program_chars": self.program_chars(facts),
                    "stats_atoms": stats["atoms"],
                    "stats_rules": stats["rules"],
                    "clingo_arguments": clingo_arguments,
                    "model_limit": 0,
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
                "models": stats["models"],
                "program_size": 1,
                "has_numeric_evidence": self.capabilities.has_numeric_evidence,
                "allow_numeric_comparison": self.capabilities.allow_numeric_comparison,
                "allow_equality_comparison": self.capabilities.allow_equality_comparison,
                "allow_arithmetic": self.capabilities.allow_arithmetic,
                "allow_aggregates": self.capabilities.allow_aggregates,
                "allow_recursion": self.capabilities.allow_recursion,
                "clingo_arguments": clingo_arguments,
                "stats_choices": stats["choices"],
                "stats_conflicts": stats["conflicts"],
            },
        )

def generate_clause_space(task: InductiveTask, arguments: Arguments) -> ClauseSpace:
    with generation_gc(arguments.clause_generation.get("gc", "normal")):
        with phase("clause_generation"):
            generator = _ClauseGenerator(task, arguments)
        return generator.clause_space()


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
    if arguments.clause_generation.get("workers", 1) != 1:
        raise ValueError("incremental generation requires one resumable Control")
    if arguments.clause_generation.get("engine", "auto") not in {"auto", "asp"}:
        raise ValueError("incremental generation uses the general asp engine")
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
