import time
from collections.abc import Callable
from functools import wraps

from ...rule_generation.parser import Predicate, clause_predicates
from ...rule_generation.program import Program
from ...rule_generation.rule_entry import RuleEntry
from ...rule_generation.rule_space import RuleSpace
from ...timing import add, current_phase


def record_generation_time(method: Callable) -> Callable:
    @wraps(method)
    def measured(*args, **kwargs):
        started = time.perf_counter()
        result = method(*args, **kwargs)
        # Benchmark schema keeps "closure" as the invariant-work time category.
        add(f"{current_phase()}.closure", time.perf_counter() - started)
        return result

    return measured


def prepare_space(program: Program, space: RuleSpace) -> RuleSpace:
    background = defined_predicates(program.background)
    entries = prune_uncloseable_rules(space.entries, background)
    return RuleSpace.from_entries(entries)


def defined_predicates(lines: list[str]) -> set[Predicate]:
    defined: set[Predicate] = set()
    for line in lines:
        heads, _deps, _body = clause_predicates(line)
        defined.update(heads)
    return defined


def prune_uncloseable_rules(
    entries: tuple[RuleEntry, ...], background: set[Predicate]
) -> list[RuleEntry]:
    kept = list(entries)
    while True:
        providers = set(background)
        for entry in kept:
            providers.update(entry.heads)
        filtered = [entry for entry in kept if entry.deps <= providers]
        if len(filtered) == len(kept):
            return kept
        kept = filtered


def bits(mask: int):
    while mask:
        bit = mask & -mask
        yield bit
        mask ^= bit
