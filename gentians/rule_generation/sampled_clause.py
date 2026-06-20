from .program import ModeDeclaration
from ..constants import UNDERSCORE_SIZE


class Literal:
    def __init__(
        self, mode_bias: ModeDeclaration, negated: bool, index_in_mode_bias_list: int
    ) -> None:
        self.mode_bias: ModeDeclaration = mode_bias
        self.negated: bool = negated
        self.index_in_mode_bias_list: int = index_in_mode_bias_list

    def get_stub_representation(self) -> str:
        """
        Returns the string representation of the mode declaration.
        """
        s = self.mode_bias.name
        if self.mode_bias.arity > 0:
            s += "("
            for i in range(0, self.mode_bias.arity):
                s += ("_" * UNDERSCORE_SIZE) + ","
            s = s[:-1] + ")"
        return s if (not self.negated) else f"not {s}"

    def __str__(self) -> str:
        return f"{'negated' if self.negated else ''} {self.mode_bias}"

    def __repr__(self) -> str:
        return self.__str__()


class Clause:
    def __init__(
        self, head: "list[Literal]", body: "list[Literal]", instantiated: "list[str]"
    ) -> None:
        self.head: "list[Literal]" = head
        self.body: "list[Literal]" = body
        self.instantiated: "list[str]" = instantiated

    def __eq__(self, value: object) -> bool:
        return sorted(self.instantiated) == sorted(value.instantiated)

    def __str__(self) -> str:
        return f"head:{self.head} - body:{self.body}"

    def __repr__(self) -> str:
        return self.__str__()
