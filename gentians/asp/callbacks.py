class RuleCallback:
    """
    Used while parsing the AST with clingo: process
    is used as callback function to store values
    """

    def __init__(self) -> None:
        self.head = []
        self.body = []

    def process(self, stm):
        if "body" in stm.child_keys:
            bl = [str(lit).replace(" ", "") for lit in stm.body]
            self.body = bl
        if "head" in stm.child_keys:
            self.head = str(stm.head).replace(" ", "").split(";")


class CheckSanityRulesCallback:
    """
    Wrapper to check unsafe rules
    """

    def __init__(self) -> None:
        self.unsound_rule: bool = False

    def sink(self, x, y):
        # global for the error: info: global variable in tuple of aggregate element
        # or because there can be more errors
        self.unsound_rule = self.unsound_rule or (("unsafe" in y) or ("global" in y))


def wrapper_exit_callback(x, y):
    """
    Clingo callback: exit when there is an error
    """
    if "error" in y:
        raise RuntimeError(f"{x}\n{y}")


class WrapperStopIfWarn:
    """
    Wrapper for the clingo Control callback.
    """

    def __init__(self) -> None:
        self.atom_undefined = False

    def wrapper_warn_undefined_callback(self, x, y):
        """
        Clingo callback: exit when there is an atom undefined.
        Used when check coverage: if there is an atom undefined, clearly
        the program is not ok, so we can skip the check of the coverage.
        To do so, I check whether there is a warning of an atom undefined
        (excluding the ones for coverage positive and negative) in y.
        For instance:
        x = MessageCode.AtomUndefined
        y = <block>:24:10-19: info: atom does not occur in any rule head: tails(c2)
        Maybe there is a better (more robust) method of doing this.
        """
        continue_when_met = [
            "neg_exs(I)",
            "pos_exs(I)",
            "cni(I)",
            "cne(I)",
            "cpi(I)",
            "cpe(I)",
        ]
        self.atom_undefined = self.atom_undefined or not any(
            cwm in y for cwm in continue_when_met
        )
