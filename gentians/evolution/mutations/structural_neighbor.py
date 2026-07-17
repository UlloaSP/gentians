from __future__ import annotations

from itertools import permutations, product
import re

from ...rule_generation.parser import split_top_level_args
from ..evolution_context import EvolutionContext
from ..operator_types import MutationProposal
from ..types import Genome


_VARIABLE = re.compile(
    r"(?<![A-Za-z0-9_])([A-Z][A-Za-z0-9_]*|_[A-Za-z0-9_]+)(?![A-Za-z0-9_])"
)
_MAX_STRUCTURAL_VARIABLES = 6


class StructuralNeighborMutation:
    def __init__(
        self,
        probability: float,
        context: EvolutionContext,
        random_jump_probability: float,
        sample_size: int,
    ) -> None:
        if not 0.0 <= random_jump_probability <= 1.0:
            raise ValueError("random_jump_probability must be between 0 and 1")
        if sample_size < 1:
            raise ValueError("sample_size must be at least 1")
        self.probability = probability
        self.random_jump_probability = random_jump_probability
        self.sample_size = sample_size
        shapes = {entry.text: _rule_shape(entry.text) for entry in context.space.entries}
        self.heads = {rule: shape[0] for rule, shape in shapes.items()}
        self.shapes = {rule: shape[1] for rule, shape in shapes.items()}
        buckets: dict[tuple[str, ...], list[str]] = {}
        for entry in context.space.entries:
            buckets.setdefault(self.heads[entry.text], []).append(entry.text)
        self.rules_by_head = {heads: tuple(rules) for heads, rules in buckets.items()}
        self.global_positions = {
            rule: index for index, rule in enumerate(context.space.clauses)
        }
        self.local_positions = {
            rule: index
            for rules in self.rules_by_head.values()
            for index, rule in enumerate(rules)
        }

    def __call__(self, genome: Genome, context: EvolutionContext) -> MutationProposal:
        if context.rng.random() >= self.probability:
            return MutationProposal(genome)
        operations = ["replace", "append", "remove"]
        context.rng.shuffle(operations)
        for operation in operations:
            if operation == "replace":
                replacement = self._replacement(genome, context)
                if replacement is not None:
                    candidate, local, distance, pool_size = replacement
                    return MutationProposal(
                        candidate,
                        operation=operation,
                        local=local,
                        structural_distance=distance,
                        candidate_pool_size=pool_size,
                    )
            elif operation == "append":
                available = [
                    rule for rule in context.space.clauses if rule not in genome
                ]
                context.rng.shuffle(available)
                for rule in available:
                    if candidate := context.generator.append(genome, rule):
                        return MutationProposal(
                            candidate, operation=operation, local=False
                        )
            else:
                removable = list(genome)
                context.rng.shuffle(removable)
                for rule in removable:
                    if candidate := context.generator.remove(genome, rule):
                        return MutationProposal(
                            candidate, operation=operation, local=False
                        )
        return MutationProposal(genome)

    def _replacement(
        self,
        genome: Genome,
        context: EvolutionContext,
    ) -> tuple[Genome, bool, float, int] | None:
        sources = list(genome)
        context.rng.shuffle(sources)
        for source in sources:
            replacement = self._replacement_for(source, genome, context)
            if replacement is not None:
                return replacement
        return None

    def _replacement_for(
        self,
        source: str,
        genome: Genome,
        context: EvolutionContext,
    ) -> tuple[Genome, bool, float, int] | None:
        current = set(genome)
        source_shape = self.shapes[source]
        local = context.rng.random() >= self.random_jump_probability
        head = self.heads[source]
        rules = self.rules_by_head[head] if local else context.space.clauses
        excluded = (
            {rule for rule in current if self.heads[rule] == head}
            if local
            else current
        )
        pool_size = len(rules) - len(excluded)
        if pool_size == 0:
            rules = context.space.clauses
            excluded = current
            pool_size = len(rules) - len(excluded)
            local = False
        positions = self.local_positions if local else self.global_positions
        sample_size = self.sample_size if local else pool_size
        sampled = _sample_available(
            rules,
            excluded,
            sample_size,
            pool_size,
            positions,
            context,
        )
        context.rng.shuffle(sampled)
        distances = [
            (
                _multiset_jaccard_distance(source_shape, self.shapes[rule]),
                rule,
            )
            for rule in sampled
        ]
        if local:
            distances.sort(key=lambda item: item[0])
        for distance, replacement in distances:
            candidate = context.generator.replace(genome, source, replacement)
            if candidate is not None:
                return candidate, local, distance, pool_size
        if local:
            global_pool = len(context.space) - len(current)
            sampled = _sample_available(
                context.space.clauses,
                current,
                global_pool,
                global_pool,
                self.global_positions,
                context,
            )
            context.rng.shuffle(sampled)
            for replacement in sampled:
                candidate = context.generator.replace(genome, source, replacement)
                if candidate is not None:
                    return (
                        candidate,
                        False,
                        _multiset_jaccard_distance(
                            source_shape, self.shapes[replacement]
                        ),
                        global_pool,
                    )
        return None


def _rule_shape(rule: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    head, separator, body = rule.strip().removesuffix(".").partition(":-")
    literals = split_top_level_args(body) if separator else []
    head_literals = _split_top_level(head, ";") if head.strip() else []
    variables = tuple(
        dict.fromkeys(
            match.group(1)
            for fragment in [*head_literals, *literals]
            for match in _VARIABLE.finditer(fragment)
        )
    )
    if len(variables) > _MAX_STRUCTURAL_VARIABLES:
        raise ValueError(
            "structural_neighbor supports rules with at most "
            f"{_MAX_STRUCTURAL_VARIABLES} variables"
        )
    head_variables = tuple(
        variable
        for variable in variables
        if any(variable in _VARIABLE.findall(literal) for literal in head_literals)
    )
    body_variables = tuple(
        variable for variable in variables if variable not in set(head_variables)
    )
    best: tuple[tuple[str, ...], tuple[str, ...]] | None = None
    for head_names in _canonical_assignments(head_variables, head_literals):
        for body_names in _canonical_assignments(
            body_variables,
            literals,
            fixed=head_names,
            offset=len(head_variables),
        ):
            names = {**head_names, **body_names}

            def normalize(fragment: str) -> str:
                return _VARIABLE.sub(
                    lambda match: f"V{names[match.group(1)]}", fragment
                ).replace(" ", "")

            shape = (
                tuple(sorted(normalize(literal) for literal in head_literals)),
                tuple(sorted(normalize(literal) for literal in literals)),
            )
            if best is None or shape < best:
                best = shape
    return best if best is not None else ((), ())


def _canonical_assignments(
    variables: tuple[str, ...],
    fragments: list[str],
    *,
    fixed: dict[str, int] | None = None,
    offset: int = 0,
):
    fixed = fixed or {}
    grouped: dict[tuple[str, ...], list[str]] = {}
    for variable in variables:
        signature = tuple(
            sorted(
                _variable_role(fragment, variable, fixed)
                for fragment in fragments
                if variable in _VARIABLE.findall(fragment)
            )
        )
        grouped.setdefault(signature, []).append(variable)
    groups = []
    next_label = offset
    for signature in sorted(grouped):
        names = tuple(grouped[signature])
        labels = tuple(range(next_label, next_label + len(names)))
        groups.append((names, labels))
        next_label += len(names)
    for assignment in product(*(permutations(labels) for _names, labels in groups)):
        yield {
            variable: label
            for (group_names, _labels), group_assignment in zip(
                groups, assignment, strict=True
            )
            for variable, label in zip(group_names, group_assignment, strict=True)
        }


def _variable_role(
    fragment: str, variable: str, fixed: dict[str, int]
) -> str:
    return _VARIABLE.sub(
        lambda match: (
            "$SELF"
            if match.group(1) == variable
            else f"V{fixed[match.group(1)]}"
            if match.group(1) in fixed
            else "$VAR"
        ),
        fragment,
    ).replace(" ", "")


def _split_top_level(fragment: str, separator: str) -> list[str]:
    parts: list[str] = []
    start = 0
    stack: list[str] = []
    pairs = {"(": ")", "[": "]", "{": "}"}
    for index, char in enumerate(fragment):
        if char in pairs:
            stack.append(pairs[char])
        elif stack and char == stack[-1]:
            stack.pop()
        elif char == separator and not stack:
            parts.append(fragment[start:index].strip())
            start = index + 1
    tail = fragment[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def _multiset_jaccard_distance(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    left_index = right_index = intersection = 0
    while left_index < len(left) and right_index < len(right):
        if left[left_index] == right[right_index]:
            intersection += 1
            left_index += 1
            right_index += 1
        elif left[left_index] < right[right_index]:
            left_index += 1
        else:
            right_index += 1
    union = len(left) + len(right) - intersection
    return 0.0 if union == 0 else 1.0 - intersection / union


def _sample_available(
    rules: tuple[str, ...],
    current: set[str],
    sample_size: int,
    available: int,
    positions: dict[str, int],
    context: EvolutionContext,
) -> list[str]:
    target = min(sample_size, available)
    excluded = sorted(positions[rule] for rule in current)
    sampled = context.rng.sample(range(available), target)
    result = []
    for compressed in sampled:
        index = compressed
        for excluded_index in excluded:
            if excluded_index > index:
                break
            index += 1
        result.append(rules[index])
    return result
