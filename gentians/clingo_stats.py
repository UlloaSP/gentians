"""The few Clingo statistics the metrics record.

`Control.statistics` converts the whole statistics tree to Python on every new
control, which dominated the cost of recording metrics. This module reads only
the values used, through Clingo's statistics C API. That API is private to the
clingo package; tests compare it with `Control.statistics`.
"""

from clingo._internal import _c_call, _lib


def clingo_statistics(ctl) -> dict[str, float]:
    """Return models, atoms, rules, choices and conflicts of the last solve.

    A missing path reads as 0. Atoms and rules take the larger of the program
    and step totals, as incremental grounding reports them in either.
    """
    stats = _c_call("clingo_statistics_t*", _lib.clingo_control_statistics, ctl._rep)
    root = _c_call("uint64_t", _lib.clingo_statistics_root, stats)

    def value(*path: str) -> float:
        key = root
        for name in path:
            if _c_call("clingo_statistics_type_t", _lib.clingo_statistics_type, stats, key) != (
                _lib.clingo_statistics_type_map
            ):
                return 0.0
            encoded = name.encode()
            if not _c_call("bool", _lib.clingo_statistics_map_has_subkey, stats, key, encoded):
                return 0.0
            key = _c_call("uint64_t", _lib.clingo_statistics_map_at, stats, key, encoded)
        if _c_call("clingo_statistics_type_t", _lib.clingo_statistics_type, stats, key) != (
            _lib.clingo_statistics_type_value
        ):
            return 0.0
        return _c_call("double", _lib.clingo_statistics_value_get, stats, key)

    return {
        "models": value("summary", "models", "enumerated"),
        "atoms": max(value("problem", "lp", "atoms"), value("problem", "lpStep", "atoms")),
        "rules": max(value("problem", "lp", "rules"), value("problem", "lpStep", "rules")),
        "choices": value("solving", "solvers", "choices"),
        "conflicts": value("solving", "solvers", "conflicts"),
    }
