import clingo
import pytest

from gentians.clingo_stats import clingo_statistics


def _from_dict(stats: dict) -> dict[str, float]:
    def value(*path):
        current = stats
        for key in path:
            if not isinstance(current, dict) or key not in current:
                return 0.0
            current = current[key]
        return float(current) if isinstance(current, (int, float)) else 0.0

    return {
        "models": value("summary", "models", "enumerated"),
        "atoms": max(value("problem", "lp", "atoms"), value("problem", "lpStep", "atoms")),
        "rules": max(value("problem", "lp", "rules"), value("problem", "lpStep", "rules")),
        "choices": value("solving", "solvers", "choices"),
        "conflicts": value("solving", "solvers", "conflicts"),
    }


@pytest.mark.parametrize("arguments", [["0"], ["0", "--enum-mode=brave"], ["0", "--stats=2"]])
def test_reads_the_same_values_as_the_full_statistics_tree(arguments):
    ctl = clingo.Control(arguments)
    ctl.add("base", [], "{a(1..20)}. b(X) :- a(X), not a(X+1). :- #count{X: b(X)} > 2.")
    ctl.ground([("base", [])])
    ctl.solve()

    assert clingo_statistics(ctl) == _from_dict(ctl.statistics)
    assert clingo_statistics(ctl)["models"] > 0


def test_reads_step_totals_after_incremental_grounding():
    ctl = clingo.Control(["0"])
    ctl.add("base", [], "p(1).")
    ctl.add("step", ["t"], "p(t+1) :- p(t). {q(t)}.")
    ctl.ground([("base", [])])
    ctl.solve()
    ctl.ground([("step", [clingo.Number(1)])])
    ctl.solve()

    assert clingo_statistics(ctl) == _from_dict(ctl.statistics)


def test_missing_statistics_read_as_zero():
    ctl = clingo.Control()
    ctl.add("base", [], "a.")
    ctl.ground([("base", [])])

    assert clingo_statistics(ctl) == _from_dict(ctl.statistics)
