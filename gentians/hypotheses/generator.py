import random

from ..clauses.parser import fragment_atoms
from ..clauses.program import Program
from ..clauses.rule_space import RuleSpace
from ..evolution.operator_types import MutationProposal
from ..evolution.types import Genome, ProgramText
from .common import bits, defined_predicates, prepare_space, record_generation_time

_CACHE_SIZE = 65536


class HypothesisGenerator:
    def __init__(
        self,
        program: Program,
        space: RuleSpace,
        max_clauses: int,
        rng: random.Random,
    ) -> None:
        self.max_clauses = max_clauses
        self.rng = rng
        self.space = prepare_space(program, space)
        self.rules = self.space.clauses
        self.rule_count = len(self.rules)
        self.all_rules = (1 << self.rule_count) - 1
        self.rule_ids = {rule: index for index, rule in enumerate(self.rules)}

        background = defined_predicates(program.background)
        predicates = set(background)
        for entry in self.space.entries:
            predicates.update(entry.heads)
            predicates.update(entry.deps)
        self.predicate_ids = {
            predicate: index for index, predicate in enumerate(sorted(predicates))
        }
        self.background_mask = self._predicate_mask(background)
        self.invented_mask = self._predicate_mask(set(program.invented_predicates))
        target_predicates = {
            (name, len(arguments))
            for example in [*program.positive_examples, *program.negative_examples]
            for fragment in (example.included, example.excluded)
            for name, arguments, _negative in fragment_atoms(fragment)
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
        for rule_id, entry in enumerate(self.space.entries):
            if entry.bundle is not None:
                self.bundle_masks[entry.bundle] = self.bundle_masks.get(
                    entry.bundle, 0
                ) | (1 << rule_id)
        self.rule_bundle_masks = tuple(
            self.bundle_masks.get(entry.bundle, 1 << rule_id)
            if entry.bundle is not None
            else 1 << rule_id
            for rule_id, entry in enumerate(self.space.entries)
        )
        self.target_rules = sum(
            1 << rule_id
            for rule_id, heads in enumerate(self.head_masks)
            if heads & self.target_mask
        )
        self.rules_by_head: dict[int, int] = {}
        for rule_id, heads in enumerate(self.head_masks):
            rule_bit = 1 << rule_id
            for predicate_bit in bits(heads):
                self.rules_by_head[predicate_bit] = (
                    self.rules_by_head.get(predicate_bit, 0) | rule_bit
                )
        self._render_cache: dict[Genome, ProgramText] = {}
        self._summary_cache: dict[Genome, tuple[int, int]] = {}
        self._build_cache: dict[tuple[Genome, Genome], Genome | None] = {}

    def encode(self, program: ProgramText) -> Genome:
        genome = 0
        for rule in program:
            genome |= 1 << self.rule_ids[rule]
        return genome

    def render(self, genome: Genome) -> ProgramText:
        if genome not in self._render_cache:
            self._remember(
                self._render_cache,
                genome,
                tuple(self.rules[rule_id] for rule_id in self._ids(genome)),
            )
        return self._render_cache[genome]

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
        if not self.rule_count:
            return None
        limit = min(self.max_clauses, self.rule_count)
        size = self.rng.randint(1, limit)
        return self._build(self._sample_rules(size), 0)

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
        Mezcla dos genomas en cuatro fases: toma primero las reglas
        compartidas por ambos padres, luego añade reglas exclusivas de cada
        padre con probabilidad independiente por regla, y si no queda ninguna
        regla preferida escoge una regla aleatoria entre todas las presentes
        en cualquiera de los dos genomas.

        A continuación intenta construir el hijo final iterando por las
        reglas preferidas. En cada paso llama a _complete() para completar el
        conjunto parcial de reglas y solo acepta esa expansión si el tamaño
        resultante no supera el límite permitido. El conjunto "selected" se
        va quedando con la última expansión válida. Si no se selecciona
        ninguna regla, devuelve None.
        """
        preferred = first & second
        for rule_id in self._ids(first & ~second):
            if self.rng.random() < first_probability:
                preferred |= 1 << rule_id
        for rule_id in self._ids(second & ~first):
            if self.rng.random() < second_probability:
                preferred |= 1 << rule_id
        if not preferred:
            preferred = self._random_rule(first | second)
        selected = 0
        for rule_id in self._ids(preferred):
            expanded = self._complete(selected | (1 << rule_id), 0)
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
        if program and self.all_rules & ~program:
            operations.append("replace")
        return operations

    def _apply_random_operation(self, program: Genome, operation: str) -> Genome | None:
        if operation == "append":
            for rule_id in self._random_available(program):
                if candidate := self._build(program | (1 << rule_id), 0):
                    return candidate
            return None
        if operation == "remove":
            for rule_id in self._random_ids(program):
                rule_bit = self.rule_bundle_masks[rule_id]
                if candidate := self._build(program & ~rule_bit, rule_bit):
                    return candidate
            return None
        if operation == "replace":
            for source_id in self._random_ids(program):
                source_bit = self.rule_bundle_masks[source_id]
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
            source_bit = self.rule_bundle_masks[source_id]
            base = program & ~source_bit
            replacements = (
                self._random_available(program)
                if random_jump
                else (
                    rule_id
                    for rule_id in self._random_available(program)
                    if self.head_masks[rule_id] == self.head_masks[source_id]
                )
            )
            for replacement_id in replacements:
                if candidate := self._build(base | (1 << replacement_id), source_bit):
                    return MutationProposal(candidate, "replace", not random_jump)
        return None

    def _sample_rules(self, size: int) -> Genome:
        if not self.invented_mask or not self.target_rules:
            return sum(
                1 << rule_id
                for rule_id in self.rng.sample(range(self.rule_count), size)
            )
        invented_consumers = sum(
            1 << rule_id
            for rule_id in self._ids(self.target_rules)
            if self.dep_masks[rule_id] & self.invented_mask
        )
        seeds = invented_consumers or self.target_rules
        seed = self._random_rule(seeds)
        remaining = size - 1
        others = self._sample_ids(self.all_rules & ~seed, remaining)
        return seed | sum(1 << rule_id for rule_id in others)

    def _build(self, proposal: Genome, forbidden: Genome) -> Genome | None:
        key = proposal, forbidden
        if key in self._build_cache:
            return self._build_cache[key]
        invalid = (
            not proposal
            or proposal.bit_count() > self.max_clauses
            or proposal & forbidden
            or proposal & ~self.all_rules
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
        remaining = max(64, self.rule_count)

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
                        self.rules_by_head.get(bit, 0) & ~completed & ~forbidden
                    ).bit_count(),
                )
                providers = (
                    self.rules_by_head.get(missing_bit, 0) & ~completed & ~forbidden
                )
                score_groups: dict[tuple[int, int, int], int] = {}
                for rule_id in self._ids(providers):
                    rule_heads = self.head_masks[rule_id]
                    rule_deps = self.dep_masks[rule_id]
                    if missing_bit & self.invented_mask and missing_bit & rule_deps:
                        continue
                    score = (
                        (rule_heads & missing).bit_count(),
                        -(
                            rule_deps & ~(self.background_mask | heads | rule_heads)
                        ).bit_count(),
                        -self.body_sizes[rule_id],
                    )
                    score_groups[score] = score_groups.get(score, 0) | (1 << rule_id)
                for score in sorted(score_groups, reverse=True):
                    for rule_id in self._random_ids(score_groups[score]):
                        if result := search(completed | (1 << rule_id)):
                            return result
            failed.add(completed)
            return None

        return search(candidate)

    def _bundle_closure(self, genome: Genome) -> Genome:
        expanded = genome
        for rule_id in self._ids(genome):
            expanded |= self.rule_bundle_masks[rule_id]
        return expanded

    def _summary(self, genome: Genome) -> tuple[int, int]:
        if genome not in self._summary_cache:
            heads = 0
            deps = 0
            for rule_id in self._ids(genome):
                heads |= self.head_masks[rule_id]
                deps |= self.dep_masks[rule_id]
            self._remember(self._summary_cache, genome, (heads, deps))
        return self._summary_cache[genome]

    def _random_rule(self, mask: int) -> int:
        return 1 << self.rng.choice(tuple(self._ids(mask)))

    def _random_ids(self, mask: int):
        rule_ids = list(self._ids(mask))
        while rule_ids:
            index = self.rng.randrange(len(rule_ids))
            rule_ids[index], rule_ids[-1] = rule_ids[-1], rule_ids[index]
            yield rule_ids.pop()

    def _random_available(self, excluded: Genome):
        excluded_ids = tuple(self._ids(excluded))
        remaining = self.rule_count - len(excluded_ids)
        swaps: dict[int, int] = {}
        while remaining:
            compressed = self.rng.randrange(remaining)
            selected = swaps.get(compressed, compressed)
            remaining -= 1
            swaps[compressed] = swaps.get(remaining, remaining)
            rule_id = selected
            for excluded_id in excluded_ids:
                if excluded_id > rule_id:
                    break
                rule_id += 1
            yield rule_id

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
