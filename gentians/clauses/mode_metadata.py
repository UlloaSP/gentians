from collections import OrderedDict
from functools import lru_cache

from .clause_mode import ClauseMode
from .metadata import ClauseMetadata
from .predicate_index import PredicateIndex


class ModeMetadata:
    def __init__(self, modes: dict[int, ClauseMode]) -> None:
        self.index = PredicateIndex(
            predicate for mode in modes.values()
            for predicates in (mode.head_predicates, mode.head_dependencies, mode.dependencies)
            for predicate in predicates
        )
        self.heads = {mode.id: (self.index.mask(mode.head_predicates),
                               self.index.mask(mode.head_dependencies), mode.condition_count)
                      for mode in modes.values()}
        self.bodies = {mode.id: (self.index.mask(mode.dependencies), 1 + mode.condition_count)
                       for mode in modes.values()}
        body_partials: OrderedDict[tuple[int, ...], tuple[int, int]] = OrderedDict()

        @lru_cache(maxsize=8192)
        def head_prefix(ids: tuple[int, ...]) -> tuple[int, int, int]:
            if not ids:
                return 0, 0, 0
            h = d = c = 0
            for mode_id in ids:
                mh, md, mc = self.heads[mode_id]
                h |= mh
                d |= md
                c += mc
            return h, d, c

        @lru_cache(maxsize=8192)
        def body_prefix(ids: tuple[int, ...]) -> tuple[int, int]:
            # Long biases do not consume Python's call stack. Reuse the longest
            # cached mode prefix, then fold only the missing suffix.
            d = c = 0
            if not ids:
                return d, c
            position = len(ids) - 1
            while position > 0:
                cached = body_partials.get(ids[:position])
                if cached is not None:
                    d, c = cached
                    break
                position -= 1
            for position in range(position, len(ids)):
                mode_id = ids[position]
                md, mc = self.bodies[mode_id]
                d |= md
                c += mc
                prefix = ids[:position + 1]
                if len(body_partials) >= 8192:
                    body_partials.popitem(last=False)
                body_partials[prefix] = d, c
            return d, c

        self.head_prefix = head_prefix
        self.body_prefix = body_prefix
        self.from_masks = lru_cache(maxsize=8192)(
            lambda head, deps, cost: ClauseMetadata(head, deps, cost, self.index)
        )

    def for_modes(self, head: tuple[int, ...], body: tuple[int, ...]) -> ClauseMetadata:
        h, hd, hc = self.head_prefix(head)
        bd, bc = self.body_prefix(body)
        return self.from_masks(h, hd | bd, hc + bc)
