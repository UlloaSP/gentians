from ..context import EvolutionContext
from ...hypotheses import Genome


def _bits(mask: int):
    """Yield each selected clause or predicate as a one-bit mask."""
    while mask:
        bit = mask & -mask
        yield bit
        mask ^= bit


class ComponentMixCrossover:
    """Exchange closed dependency islands between two parent hypotheses.

    A graph edge joins a clause that needs a predicate to every parent clause
    that can define it. A connected component is therefore an indivisible
    island: taking only part of it could leave a dependency without a provider.

    For every island, crossover may keep the version from the first parent, the
    version from the second parent, or their union. It never searches the wider
    ClauseSpace, repairs a child, retries a failed choice, or evaluates fitness.
    """

    def __init__(self, probability: float) -> None:
        if isinstance(probability, bool) or not 0.0 <= probability <= 1.0:
            raise ValueError("crossover probability must be between 0 and 1")
        self.probability = probability

    def __call__(
        self, first: Genome, second: Genome, context: EvolutionContext,
    ) -> Genome | None:
        if context.rng.random() >= self.probability:
            return None
        if context.results is not None:
            for parent in (first, second):
                result = context.results.get(parent)
                if result is not None and result.is_solution:
                    return parent
        hypotheses = context.hypotheses
        if first == second:
            return self._normalize_constraints(first, context)

        # Crossover transmits only clauses already present in either parent.
        union = first | second

        # Build an undirected dependency graph over that parental union.
        # Dependencies supplied by background need no learned provider and do
        # not connect otherwise independent clauses.
        neighbors = {bit: 0 for bit in _bits(union)}
        for clause_bit in neighbors:
            clause_id = clause_bit.bit_length() - 1
            dependencies = (
                hypotheses.dep_masks[clause_id] & ~hypotheses.background_mask
            )
            providers = 0
            for predicate_bit in _bits(dependencies):
                providers |= (
                    hypotheses.clauses_by_head.get(predicate_bit, 0) & union
                )
            neighbors[clause_bit] |= providers
            for provider in _bits(providers):
                neighbors[provider] |= clause_bit

        # Extract connected components. Each component contains every parental
        # provider linked to any consumer inside the same island.
        components = []
        unseen = union
        while unseen:
            component = frontier = unseen & -unseen
            while frontier:
                bit = frontier & -frontier
                frontier ^= bit
                reached = neighbors[bit] & ~component
                component |= reached
                frontier |= reached
            unseen &= ~component
            components.append(component)

        # Begin with one valid parent. Its current version of every component is
        # always a feasible fallback, so no closure repair or retry is needed.
        selected = context.rng.choice((first, second))
        context.rng.shuffle(components)
        for component in components:
            # A and B may carry different closed versions of the same island.
            # Their union matters when each parent contains a different provider,
            # as with father/mother helpers in grandparent.
            versions = [first & component, second & component]
            if versions[0] == versions[1]:
                continue
            if component not in versions:
                versions.append(component)

            # Replace only this island. Ignore versions that would empty the
            # hypothesis or exceed the task's #maxpl limit.
            retained = selected & ~component
            size = retained.bit_count()
            feasible = [
                version for version in versions
                if 0 < size + version.bit_count() <= hypotheses.max_clauses
            ]
            selected = retained | context.rng.choice(feasible)
        return self._normalize_constraints(selected, context)

    @staticmethod
    def _normalize_constraints(genome: Genome, context: EvolutionContext) -> Genome:
        hypotheses = context.hypotheses
        if not hypotheses.has_negative_examples:
            # Constraints cannot add brave positive witnesses. Drop them when a
            # headed clause remains, while preserving the nonempty invariant.
            return genome & ~hypotheses.constraint_clauses or genome
        return genome
