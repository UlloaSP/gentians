import random
import time
from collections.abc import Callable
from functools import cached_property, wraps

from ..language.asp import AspProgram, symbolic_literal_predicate
from ..language.ir.inductive_task import InductiveTask
from ..clauses import ClauseSpace
from ..timing import add, current_phase
from .space import defined_predicates, prepare_space
from .types import Genome, ProgramText

_CACHE_SIZE = 65536


def _record_closure_time(method: Callable) -> Callable:
    @wraps(method)
    def measured(*args, **kwargs):
        started = time.perf_counter()
        result = method(*args, **kwargs)
        add(f"{current_phase()}.closure", time.perf_counter() - started)
        return result

    return measured


def _bits(mask: int):
    while mask:
        bit = mask & -mask
        yield bit
        mask ^= bit


class HypothesisGenerator:
    def __init__(
        self,
        task: InductiveTask,
        space: ClauseSpace,
        max_clauses: int,
    ) -> None:
        self.max_clauses = max_clauses
        self.has_positive_examples = bool(task.positive_examples)
        self.has_negative_examples = bool(task.negative_examples)
        self.space = prepare_space(task, space)
        self.clauses = self.space.clauses
        self.statements = self.space.statements
        self.clause_count = len(self.clauses)
        self.all_clauses = (1 << self.clause_count) - 1
        self.available_clauses = self.all_clauses
        self._available_ids: tuple[int, ...] = ()
        self.clause_ids = {
            clause: index for index, clause in enumerate(self.clauses)
        }

        background = defined_predicates(task.background)
        predicates = set(background)
        for entry in self.space.entries:
            predicates.update(entry.heads)
            predicates.update(entry.deps)
        self.predicate_ids = {
            predicate: index for index, predicate in enumerate(sorted(predicates))
        }
        self.background_mask = self._predicate_mask(background)
        self.invented_mask = self._predicate_mask(set(task.invented_predicates))
        target_predicates = {
            symbolic_literal_predicate(literal)
            for example in [*task.positive_examples, *task.negative_examples]
            for literal in (*example.included, *example.excluded)
        }
        self.target_mask = self._predicate_mask(target_predicates)
        self.head_masks = tuple(
            self._predicate_mask(entry.heads) for entry in self.space.entries
        )
        self.dep_masks = tuple(
            self._predicate_mask(entry.deps) for entry in self.space.entries
        )
        self.body_sizes = tuple(entry.body_literals for entry in self.space.entries)
        self.target_clauses = sum(
            1 << clause_id
            for clause_id, heads in enumerate(self.head_masks)
            if heads & self.target_mask
        )
        self.clauses_by_head: dict[int, int] = {}
        for clause_id, heads in enumerate(self.head_masks):
            clause_bit = 1 << clause_id
            for predicate_bit in _bits(heads):
                self.clauses_by_head[predicate_bit] = (
                    self.clauses_by_head.get(predicate_bit, 0) | clause_bit
                )
        self._render_cache: dict[Genome, ProgramText] = {}
        self._summary_cache: dict[Genome, tuple[int, int]] = {}
        self._build_cache: dict[tuple[Genome, Genome, Genome], Genome | None] = {}

    def set_available_clauses(self, clauses: Genome) -> None:
        """Restrict subsequent construction to a frozen subset of the space."""
        if not clauses or clauses & ~self.all_clauses:
            raise ValueError("clause pool must be a non-empty subset of the space")
        self.available_clauses = clauses
        self._available_ids = (
            () if clauses == self.all_clauses else tuple(self._ids(clauses))
        )

    def encode(self, program: ProgramText) -> Genome:
        genome = 0
        for clause in program:
            genome |= 1 << self.clause_ids[clause]
        return genome

    def render(self, genome: Genome) -> ProgramText:
        if genome not in self._render_cache:
            self._remember(
                self._render_cache,
                genome,
                tuple(self.clauses[clause_id] for clause_id in self._ids(genome)),
            )
        return self._render_cache[genome]

    def program(self, genome: Genome) -> AspProgram:
        return tuple(self.statements[clause_id] for clause_id in self._ids(genome))

    def all_subsets_evaluated(self, evaluated_count: int) -> bool:
        """Sufficient exhaustion proof, counting even dependency-invalid subsets.

        Callers supply the number of distinct admitted genomes in this space.
        Reaching the combinatorial upper bound proves exhaustion; falling short
        proves nothing. Stop counting as soon as that proof is impossible.
        """
        if self.available_clauses != self.all_clauses:
            return False
        total, combinations = 0, 1
        for size in range(1, min(self.max_clauses, self.clause_count) + 1):
            combinations = combinations * (self.clause_count - size + 1) // size
            total += combinations
            if total > evaluated_count:
                return False
        return total > 0 and total == evaluated_count

    @_record_closure_time
    def create(self, rng: random.Random) -> Genome | None:
        available_count = self.available_clauses.bit_count()
        if not available_count:
            return None
        limit = min(self.max_clauses, available_count)
        size = rng.randint(1, limit)
        return self._build(self._sample_clauses(size, rng), 0, rng)

    @_record_closure_time
    def mix(
        self,
        first: Genome,
        second: Genome,
        probabilities: tuple[float, float],
        rng: random.Random,
    ) -> Genome | None:
        return self._mix_one(
            first,
            second,
            probabilities[0],
            probabilities[1],
            rng,
        )

    def _mix_one(
        self,
        first: Genome,
        second: Genome,
        first_probability: float,
        second_probability: float,
        rng: random.Random,
        fixed: Genome = 0,
        forbidden: Genome = 0,
    ) -> Genome | None:
        """
        Mezcla dos genomas en cuatro fases: toma primero las cláusulas
        compartidas por ambos padres, luego añade cláusulas exclusivas de cada
        padre con probabilidad independiente por cláusula, y si no queda ninguna
        cláusula preferida escoge una cláusula aleatoria entre todas las presentes
        en cualquiera de los dos genomas.

        A continuación intenta construir el hijo final iterando por las
        cláusulas preferidas. En cada paso llama a _complete() para completar el
        conjunto parcial de cláusulas y solo acepta esa expansión si el tamaño
        resultante no supera el límite permitido. El conjunto "selected" se
        va quedando con la última expansión válida. Si no se selecciona
        ninguna cláusula, devuelve None.
        """
        preferred = first & second
        for clause_id in self._ids(first & ~second):
            if rng.random() < first_probability:
                preferred |= 1 << clause_id
        for clause_id in self._ids(second & ~first):
            if rng.random() < second_probability:
                preferred |= 1 << clause_id
        if not preferred and not (first | second):
            return fixed or None
        if not preferred:
            preferred = self._random_clause(first | second, rng)
        selected = fixed
        for clause_id in self._ids(preferred):
            expanded = self._complete(selected | (1 << clause_id), forbidden, rng)
            if expanded is not None and expanded.bit_count() <= self.max_clauses:
                selected = expanded
        if not selected:
            return None
        return selected

    @cached_property
    def constraint_clauses(self) -> Genome:
        """Clauses with no defined head predicate."""
        return sum(1 << i for i, entry in enumerate(self.space.entries) if not entry.heads)

    def _mutation_space(self, genome: Genome, mutable: Genome | None) -> tuple[Genome, Genome]:
        mutable = self.available_clauses if mutable is None else mutable & self.available_clauses
        return mutable, self.all_clauses & ~(genome | mutable)

    @_record_closure_time
    def mix_constraints(
        self, first: Genome, second: Genome, probabilities: tuple[float, float],
        rng: random.Random,
    ) -> Genome | None:
        mutable, forbidden = self._mutation_space(first, self.constraint_clauses)
        return self._mix_one(first & mutable, second & mutable, *probabilities, rng,
                             fixed=first & ~mutable, forbidden=forbidden)

    def operations(self, genome: Genome) -> list[str]:
        size = genome.bit_count()
        operations = []
        if size < self.max_clauses:
            operations.append("append")
        if size > 1:
            operations.append("remove")
        if genome and self.available_clauses & ~genome:
            operations.append("replace")
        return operations

    @_record_closure_time
    def append(self, genome: Genome, rng: random.Random, *, mutable: Genome | None = None) -> Genome | None:
        mutable, forbidden = self._mutation_space(genome, mutable)
        if not mutable & ~genome:
            return None
        for clause_id in self._random_available(genome, rng):
            if not mutable & (1 << clause_id):
                continue
            if candidate := self._build(genome | (1 << clause_id), forbidden, rng):
                if not (candidate ^ genome) & ~mutable:
                    return candidate
        return None

    @_record_closure_time
    def remove(
        self, genome: Genome, rng: random.Random, *, mutable: Genome | None = None,
        sources: Genome | None = None,
    ) -> Genome | None:
        mutable, _ = self._mutation_space(genome, mutable)
        roots = genome & mutable
        if sources is not None:
            roots &= sources
        for clause_id in self._random_ids(roots, rng):
            clause_bit = 1 << clause_id
            # Delete unsupported consumers transitively. Deletion never repairs
            # itself by inserting a different provider from the clause pool.
            remaining = self._drop_dependents(genome & ~clause_bit)
            # remaining is already closed; no full-ClauseSpace complement is
            # needed in the cache key to prevent insertion of new providers.
            if candidate := self._build(remaining, genome & ~remaining, rng):
                if not (candidate ^ genome) & ~mutable:
                    return candidate
        return None

    @_record_closure_time
    def replace(
        self, genome: Genome, rng: random.Random, *, same_head: bool = False,
        mutable: Genome | None = None, same_kind: bool = False,
    ) -> Genome | None:
        mutable, forbidden = self._mutation_space(genome, mutable)
        if not mutable & ~genome:
            return None
        for source_id in self._random_ids(genome & mutable, rng):
            source_bit = 1 << source_id
            base = genome & ~source_bit
            choices = mutable
            if same_kind:
                # Preserve the root's role, not its body or semantic strength.
                choices &= (self.constraint_clauses if source_bit & self.constraint_clauses
                            else ~self.constraint_clauses)
            if not choices & ~genome:
                continue
            available = (i for i in self._random_available(genome, rng) if choices & (1 << i))
            replacements = (
                (
                    clause_id
                    for clause_id in available
                    if self.head_masks[clause_id] == self.head_masks[source_id]
                )
                if same_head
                else available
            )
            for replacement_id in replacements:
                # The replacement head can sustain existing consumers. Remove
                # only those still unsupported, then close the new clause block.
                retained = self._drop_dependents(base, self.head_masks[replacement_id])
                removed = genome & ~retained
                if candidate := self._build(
                    retained | (1 << replacement_id), forbidden | removed, rng
                ):
                    if (candidate ^ genome) & ~mutable:
                        continue
                    return candidate
        return None

    def _drop_dependents(self, candidate: Genome, extra_heads: int = 0) -> Genome:
        """Keep the greatest dependency-closed subset, with optional new heads.

        Closure is syntactic: alternative providers and signed predicates count;
        mutually recursive clauses are not a proof of stable-model support.
        """
        while candidate:
            heads, _ = self._summary(candidate)
            provided = self.background_mask | heads | extra_heads
            unsupported = sum(
                1 << i for i in self._ids(candidate) if self.dep_masks[i] & ~provided
            )
            if not unsupported:
                break
            candidate &= ~unsupported
        return candidate

    def _sample_clauses(self, size: int, rng: random.Random) -> Genome:
        if self.available_clauses == self.all_clauses:
            if not self.invented_mask or not self.target_clauses:
                return sum(
                    1 << clause_id
                    for clause_id in rng.sample(range(self.clause_count), size)
                )
            invented_consumers = sum(
                1 << clause_id
                for clause_id in self._ids(self.target_clauses)
                if self.dep_masks[clause_id] & self.invented_mask
            )
            seed = self._random_clause(
                invented_consumers or self.target_clauses, rng
            )
            others = self._sample_ids(
                self.all_clauses & ~seed, size - 1, rng
            )
            return seed | sum(1 << clause_id for clause_id in others)

        available_targets = self.target_clauses & self.available_clauses
        if not self.invented_mask or not available_targets:
            return sum(
                1 << clause_id
                for clause_id in self._sample_ids(self.available_clauses, size, rng)
            )
        invented_consumers = sum(
            1 << clause_id
            for clause_id in self._ids(available_targets)
            if self.dep_masks[clause_id] & self.invented_mask
        )
        seeds = invented_consumers or available_targets
        seed = self._random_clause(seeds, rng)
        remaining = size - 1
        others = self._sample_ids(self.available_clauses & ~seed, remaining, rng)
        return seed | sum(1 << clause_id for clause_id in others)

    def _build(
        self, proposal: Genome, forbidden: Genome, rng: random.Random
    ) -> Genome | None:
        key = self.available_clauses, proposal, forbidden
        if key in self._build_cache:
            return self._build_cache[key]
        invalid = (
            not proposal
            or proposal.bit_count() > self.max_clauses
            or proposal & forbidden
            or proposal & ~self.available_clauses
        )
        if invalid:
            result = None
        else:
            result = self._complete(proposal, forbidden, rng)
        if result is not None or invalid:
            self._remember(self._build_cache, key, result)
        return result

    def _complete(
        self, candidate: Genome, forbidden: Genome, rng: random.Random
    ) -> Genome | None:
        if candidate & forbidden or candidate.bit_count() > self.max_clauses:
            return None
        failed: set[Genome] = set()
        remaining = max(64, self.clause_count)

        def search(completed: Genome) -> Genome | None:
            nonlocal remaining
            if completed & forbidden or completed.bit_count() > self.max_clauses:
                return None
            if completed in failed or remaining == 0:
                return None
            remaining -= 1
            heads, deps = self._summary(completed)
            missing = deps & ~(self.background_mask | heads)
            if not missing:
                if not self.has_negative_examples:
                    # Optional integrity constraints cannot add brave witnesses.
                    # Keep the nonempty-hypothesis invariant.
                    return completed & ~self.constraint_clauses or completed
                return completed
            if completed.bit_count() < self.max_clauses:
                missing_bit = min(
                    _bits(missing),
                    key=lambda bit: (
                        self.clauses_by_head.get(bit, 0) & ~completed & ~forbidden
                    ).bit_count(),
                )
                providers = (
                    self.clauses_by_head.get(missing_bit, 0)
                    & self.available_clauses
                    & ~completed
                    & ~forbidden
                )
                score_groups: dict[tuple[int, int, int], int] = {}
                for clause_id in self._ids(providers):
                    clause_heads = self.head_masks[clause_id]
                    clause_deps = self.dep_masks[clause_id]
                    if missing_bit & self.invented_mask and missing_bit & clause_deps:
                        continue
                    score = (
                        (clause_heads & missing).bit_count(),
                        -(
                            clause_deps & ~(self.background_mask | heads | clause_heads)
                        ).bit_count(),
                        -self.body_sizes[clause_id],
                    )
                    score_groups[score] = score_groups.get(score, 0) | (1 << clause_id)
                for score in sorted(score_groups, reverse=True):
                    for clause_id in self._random_ids(score_groups[score], rng):
                        if result := search(completed | (1 << clause_id)):
                            return result
            failed.add(completed)
            return None

        return search(candidate)

    def _summary(self, genome: Genome) -> tuple[int, int]:
        if genome not in self._summary_cache:
            heads = 0
            deps = 0
            for clause_id in self._ids(genome):
                heads |= self.head_masks[clause_id]
                deps |= self.dep_masks[clause_id]
            self._remember(self._summary_cache, genome, (heads, deps))
        return self._summary_cache[genome]

    def _random_clause(self, mask: int, rng: random.Random) -> int:
        return 1 << rng.choice(tuple(self._ids(mask)))

    def _random_ids(self, mask: int, rng: random.Random):
        clause_ids = list(self._ids(mask))
        while clause_ids:
            index = rng.randrange(len(clause_ids))
            clause_ids[index], clause_ids[-1] = clause_ids[-1], clause_ids[index]
            yield clause_ids.pop()

    def _random_available(self, excluded: Genome, rng: random.Random):
        if self.available_clauses == self.all_clauses:
            excluded_ids = tuple(self._ids(excluded))
            remaining = self.clause_count - len(excluded_ids)
            swaps: dict[int, int] = {}
            while remaining:
                compressed = rng.randrange(remaining)
                selected = swaps.get(compressed, compressed)
                remaining -= 1
                swaps[compressed] = swaps.get(remaining, remaining)
                clause_id = selected
                for excluded_id in excluded_ids:
                    if excluded_id > clause_id:
                        break
                    clause_id += 1
                yield clause_id
            return

        remaining = [
            clause_id for clause_id in self._available_ids
            if not excluded & (1 << clause_id)
        ]
        while remaining:
            yield remaining.pop(rng.randrange(len(remaining)))

    def _sample_ids(
        self, mask: int, size: int, rng: random.Random
    ) -> list[int]:
        available = (
            self._available_ids
            if mask == self.available_clauses and mask != self.all_clauses
            else tuple(self._ids(mask))
        )
        return rng.sample(available, min(size, len(available)))

    @staticmethod
    def _ids(mask: int):
        while mask:
            bit = mask & -mask
            yield bit.bit_length() - 1
            mask ^= bit

    @staticmethod
    def _remember(cache: dict, key, value) -> None:
        if len(cache) >= _CACHE_SIZE:
            cache.pop(next(iter(cache)))
        cache[key] = value

    def _predicate_mask(self, predicates) -> int:
        mask = 0
        for predicate in predicates:
            identifier = self.predicate_ids.get(predicate)
            if identifier is not None:
                mask |= 1 << identifier
        return mask
