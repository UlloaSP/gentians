"""Generation-only execution policies. No policy changes task limits."""

import gc
from contextlib import contextmanager
from ..timing import current_phase, phase


@contextmanager
def generation_gc(policy: object):
    if not isinstance(policy, str) or policy not in {"normal", "defer"}:
        raise ValueError("clause_generation.gc must be normal or defer")
    enabled = gc.isenabled()
    if policy == "defer" and enabled:
        gc.disable()
    try:
        yield
    finally:
        if policy == "defer" and enabled:
            # Include collection in the generation measurement, including errors.
            try:
                if current_phase() == "clause_generation":
                    gc.collect()
                else:
                    with phase("clause_generation"):
                        gc.collect()
            finally:
                gc.enable()
