import time


class Individual:
    def __init__(
        self,
        program: "list[str]",
        stub_indexes: "list[int]",
        prog_indexes: "list[int]",
        score: float,
        is_best: bool = False,  # does this cover everything positive and no negative?
        l_best_indexes: "list[int]" = [],  # best indexes, if it is the best
    ) -> None:
        self.program = program
        # stub_indexes is a list of int representing the index of the stub
        # clauses selected
        self.stub_indexes = stub_indexes
        # prog_indexes is a list of int representing the index of the program
        # selected for the stub_indexes clauses - maybe not needed
        self.prog_indexes = prog_indexes
        self.score = score
        self.is_best = is_best
        self.l_best_indexes = l_best_indexes
        self.generated_timestamp = time.time()

    def __str__(self) -> str:
        return f"Program: {self.program} - score: {self.score}"

    def __repr__(self) -> str:
        return self.__str__()
