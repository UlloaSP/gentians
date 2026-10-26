import hashlib
from collections.abc import Iterable


Genome = int
ProgramText = tuple[str, ...]


# Larger than CPython 3.14's free list of small ints (100 entries).
_INT_FREE_LIST = 256


def release_int_blocks() -> None:
    """Stop CPython from reusing genome-sized blocks for small ints.

    CPython 3.14 recycles freed small ints through a free list without
    shrinking their block. A genome operation with a small result, such as a
    disjoint `genome & mask`, leaves a genome-sized block there, and the next
    small int reuses it. Call this before creating small ints that must last:
    taking every cached int and refilling the list with fresh ones releases
    those blocks.
    """
    stale = [-(index + 1_000_000) for index in range(_INT_FREE_LIST)]
    fresh = [-(index + 2_000_000) for index in range(_INT_FREE_LIST)]
    # The fresh ints refill the list first, so the stale blocks are freed.
    del fresh, stale


def program_distance(first: Genome, second: Genome) -> float:
    """Jaccard distance between two programs' clause sets, in [0, 1]."""
    union = (first | second).bit_count()
    return 0.0 if not union else 1.0 - (first & second).bit_count() / union


def genome_key(genome: Genome) -> bytes:
    """Return a 128-bit digest that identifies a genome without retaining its bits."""
    return hashlib.sha256(genome.to_bytes((genome.bit_length() + 7) // 8, "little")).digest()[:16]


class GenomeTable[V]:
    """Map genomes to values by a 128-bit digest instead of retaining the genomes.

    A genome spans the highest clause id it contains, so search-long caches
    keyed by genomes grow with the ClauseSpace rather than the program.
    """

    __slots__ = ("_values",)

    def __init__(self, items: Iterable[tuple[Genome, V]] = ()) -> None:
        self._values = {genome_key(genome): value for genome, value in items}

    def __len__(self) -> int:
        return len(self._values)

    def __contains__(self, genome: Genome) -> bool:
        return genome_key(genome) in self._values

    def __getitem__(self, genome: Genome) -> V:
        return self._values[genome_key(genome)]

    def __setitem__(self, genome: Genome, value: V) -> None:
        self._values[genome_key(genome)] = value

    def get(self, genome: Genome) -> V | None:
        return self._values.get(genome_key(genome))
