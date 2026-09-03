import random

from ..language.asp import AspProgram, symbolic_literal_predicate
from ..language.ir.inductive_task import InductiveTask
from ..clauses import ClauseSpace
from ..evolution.operator_types import MutationProposal
from ..evolution.types import Genome, ProgramText
from .common import bits, defined_predicates, prepare_space, record_generation_time

_CACHE_SIZE = 65536


class HypothesisGenerator:
    def __init__(
        self,
        task: InductiveTask,
        space: ClauseSpace,
        max_clauses: int,
        rng: random.Random,
    ) -> None:
        self.max_clauses = max_clauses
        self.rng = rng
        self.space = prepare_space(task, space)
        self.clauses = self.space.clauses
        self.statements = self.space.statements
        self.clause_count = len(self.clauses)
        self.all_clauses = (1 << self.clause_count) - 1
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
        self.bundle_masks: dict[int, int] = {}
        for clause_id, entry in enumerate(self.space.entries):
            if entry.bundle is not None:
                self.bundle_masks[entry.bundle] = self.bundle_masks.get(
                    entry.bundle, 0
                ) | (1 << clause_id)
        self.clause_bundle_masks = tuple(
            self.bundle_masks.get(entry.bundle, 1 << clause_id)
            if entry.bundle is not None
            else 1 << clause_id
            for clause_id, entry in enumerate(self.space.entries)
        )
        self.target_clauses = sum(
            1 << clause_id
            for clause_id, heads in enumerate(self.head_masks)
            if heads & self.target_mask
        )
        self.clauses_by_head: dict[int, int] = {}
        for clause_id, heads in enumerate(self.head_masks):
            clause_bit = 1 << clause_id
            for predicate_bit in bits(heads):
                self.clauses_by_head[predicate_bit] = (
                    self.clauses_by_head.get(predicate_bit, 0) | clause_bit
                )
        self._render_cache: dict[Genome, ProgramText] = {}
        self._program_cache: dict[Genome, AspProgram] = {}
        self._summary_cache: dict[Genome, tuple[int, int]] = {}
        self._build_cache: dict[tuple[Genome, Genome], Genome | None] = {}

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
        if genome not in self._program_cache:
            self._remember(
                self._program_cache,
                genome,
                tuple(self.statements[clause_id] for clause_id in self._ids(genome)),
            )
        return self._program_cache[genome]

    @record_generation_time
    def create_population(self, size: int) -> list[Genome]:
        population: list[Genome] = []
        seen: set[Genome] = set()
        failed_attempts = 0
        while len(population) < size and failed_attempts < 64:
            candidate = self._create()
            if candidate is not None and candidate not in seen:
                population.append(candidate)
                seen.add(candidate)
                failed_attempts = 0
            else:
                failed_attempts += 1
        return population

    def _create(self) -> Genome | None:
        if not self.clause_count:
            return None
        limit = min(self.max_clauses, self.clause_count)
        size = self.rng.randint(1, limit)
        return self._build(self._sample_clauses(size), 0)

    @record_generation_time
    def mutate_random(self, program: Genome) -> MutationProposal:
        operations = self._possible_operations(program)
        self.rng.shuffle(operations)
        for operation in operations:
            if candidate := self._apply_random_operation(program, operation):
                return MutationProposal(candidate, operation=operation, local=False)
        return MutationProposal(program)

    @record_generation_time
    def mutate_structural(
        self,
        program: Genome,
        random_jump_probability: float,
    ) -> MutationProposal:
        operations = self._possible_operations(program)
        self.rng.shuffle(operations)
        for operation in operations:
            if operation == "replace":
                if result := self._structural_replacement(
                    program, random_jump_probability
                ):
                    return result
            elif candidate := self._apply_random_operation(program, operation):
                return MutationProposal(candidate, operation=operation, local=False)
        return MutationProposal(program)

    @record_generation_time
    def mix(
        self,
        first: Genome,
        second: Genome,
        probabilities: tuple[tuple[float, float], ...],
    ) -> tuple[Genome, ...]:
        return tuple(
            child
            for first_probability, second_probability in probabilities
            if (
                child := self._mix_one(
                    first, second, first_probability, second_probability
                )
            )
            is not None
        )

    def _mix_one(
        self,
        first: Genome,
        second: Genome,
        first_probability: float,
        second_probability: float,
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
            if self.rng.random() < first_probability:
                preferred |= 1 << clause_id
        for clause_id in self._ids(second & ~first):
            if self.rng.random() < second_probability:
                preferred |= 1 << clause_id
        if not preferred:
            preferred = self._random_clause(first | second)
        selected = 0
        for clause_id in self._ids(preferred):
            expanded = self._complete(selected | (1 << clause_id), 0)
            if expanded is not None and expanded.bit_count() <= self.max_clauses:
                selected = expanded
        if not selected:
            return None
        return selected

    def _possible_operations(self, program: Genome) -> list[str]:
        size = program.bit_count()
        operations = []
        if size < self.max_clauses:
            operations.append("append")
        if size > 1:
            operations.append("remove")
        if program and self.all_clauses & ~program:
            operations.append("replace")
        return operations

    def _apply_random_operation(self, program: Genome, operation: str) -> Genome | None:
        if operation == "append":
            for clause_id in self._random_available(program):
                if candidate := self._build(program | (1 << clause_id), 0):
                    return candidate
            return None
        if operation == "remove":
            for clause_id in self._random_ids(program):
                clause_bit = self.clause_bundle_masks[clause_id]
                if candidate := self._build(program & ~clause_bit, clause_bit):
                    return candidate
            return None
        if operation == "replace":
            for source_id in self._random_ids(program):
                source_bit = self.clause_bundle_masks[source_id]
                base = program & ~source_bit
                for replacement_id in self._random_available(program):
                    if candidate := self._build(
                        base | (1 << replacement_id), source_bit
                    ):
                        return candidate
        return None

    def _structural_replacement(
        self,
        program: Genome,
        random_jump_probability: float,
    ) -> MutationProposal | None:
        for source_id in self._random_ids(program):
            random_jump = self.rng.random() < random_jump_probability
            source_bit = self.clause_bundle_masks[source_id]
            base = program & ~source_bit
            replacements = (
                self._random_available(program)
                if random_jump
                else (
                    clause_id
                    for clause_id in self._random_available(program)
                    if self.head_masks[clause_id] == self.head_masks[source_id]
                )
            )
            for replacement_id in replacements:
                if candidate := self._build(base | (1 << replacement_id), source_bit):
                    return MutationProposal(candidate, "replace", not random_jump)
        return None

    def _sample_clauses(self, size: int) -> Genome:
        if not self.invented_mask or not self.target_clauses:
            return sum(
                1 << clause_id
                for clause_id in self.rng.sample(range(self.clause_count), size)
            )
        invented_consumers = sum(
            1 << clause_id
            for clause_id in self._ids(self.target_clauses)
            if self.dep_masks[clause_id] & self.invented_mask
        )
        seeds = invented_consumers or self.target_clauses
        seed = self._random_clause(seeds)
        remaining = size - 1
        others = self._sample_ids(self.all_clauses & ~seed, remaining)
        return seed | sum(1 << clause_id for clause_id in others)

    def _build(self, proposal: Genome, forbidden: Genome) -> Genome | None:
        key = proposal, forbidden
        if key in self._build_cache:
            return self._build_cache[key]
        invalid = (
            not proposal
            or proposal.bit_count() > self.max_clauses
            or proposal & forbidden
            or proposal & ~self.all_clauses
        )
        if invalid:
            result = None
        else:
            result = self._complete(proposal, forbidden)
        if result is not None or invalid:
            self._remember(self._build_cache, key, result)
        return result

    def _complete(self, candidate: Genome, forbidden: Genome) -> Genome | None:
        candidate = self._bundle_closure(candidate)
        if candidate & forbidden or candidate.bit_count() > self.max_clauses:
            return None
        failed: set[Genome] = set()
        remaining = max(64, self.clause_count)

        def search(completed: Genome) -> Genome | None:
            nonlocal remaining
            completed = self._bundle_closure(completed)
            if completed & forbidden or completed.bit_count() > self.max_clauses:
                return None
            if completed in failed or remaining == 0:
                return None
            remaining -= 1
            heads, deps = self._summary(completed)
            missing = deps & ~(self.background_mask | heads)
            if not missing:
                return completed
            if completed.bit_count() < self.max_clauses:
                missing_bit = min(
                    bits(missing),
                    key=lambda bit: (
                        self.clauses_by_head.get(bit, 0) & ~completed & ~forbidden
                    ).bit_count(),
                )
                providers = (
                    self.clauses_by_head.get(missing_bit, 0) & ~completed & ~forbidden
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
                    for clause_id in self._random_ids(score_groups[score]):
                        if result := search(completed | (1 << clause_id)):
                            return result
            failed.add(completed)
            return None

        return search(candidate)

    def _bundle_closure(self, genome: Genome) -> Genome:
        expanded = genome
        for clause_id in self._ids(genome):
            expanded |= self.clause_bundle_masks[clause_id]
        return expanded

    def _summary(self, genome: Genome) -> tuple[int, int]:
        if genome not in self._summary_cache:
            heads = 0
            deps = 0
            for clause_id in self._ids(genome):
                heads |= self.head_masks[clause_id]
                deps |= self.dep_masks[clause_id]
            self._remember(self._summary_cache, genome, (heads, deps))
        return self._summary_cache[genome]

    def _random_clause(self, mask: int) -> int:
        return 1 << self.rng.choice(tuple(self._ids(mask)))

    def _random_ids(self, mask: int):
        clause_ids = list(self._ids(mask))
        while clause_ids:
            index = self.rng.randrange(len(clause_ids))
            clause_ids[index], clause_ids[-1] = clause_ids[-1], clause_ids[index]
            yield clause_ids.pop()

    def _random_available(self, excluded: Genome):
        excluded_ids = tuple(self._ids(excluded))
        remaining = self.clause_count - len(excluded_ids)
        swaps: dict[int, int] = {}
        while remaining:
            compressed = self.rng.randrange(remaining)
            selected = swaps.get(compressed, compressed)
            remaining -= 1
            swaps[compressed] = swaps.get(remaining, remaining)
            clause_id = selected
            for excluded_id in excluded_ids:
                if excluded_id > clause_id:
                    break
                clause_id += 1
            yield clause_id

    def _sample_ids(self, mask: int, size: int) -> list[int]:
        available = tuple(self._ids(mask))
        return self.rng.sample(available, min(size, len(available)))

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
