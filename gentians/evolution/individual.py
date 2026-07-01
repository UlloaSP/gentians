import time


class Individual:
    def __init__(
        self,
        program: list[str],
        score: float,
        is_best: bool,  # does this cover everything positive and no negative?
        l_best_indexes: list[int],  # best indexes, if it is the best
    ) -> None:
        self.program = program
        self.score = score
        self.is_best = is_best
        self.l_best_indexes = l_best_indexes
        self.generated_timestamp = time.time()
        self.signature = tuple(sorted(self.program))

    def refresh_signature(self) -> None:
        self.signature = tuple(sorted(self.program))

    def __str__(self) -> str:
        return f"Program: {self.program} - score: {self.score}"

    def __repr__(self) -> str:
        return self.__str__()
