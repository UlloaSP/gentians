import importlib
import math

from benchmarks.catalog import arguments_for
from gentians.asp.clingo import ClingoInterface, build_fixed_coverage_program
from gentians.asp.coverage import Coverage
from gentians.asp.coverage import generate_clauses_for_coverage_interpretations
from gentians.evolution.fitness.coverage_fixed import coverage_fixed
from gentians.evolution.fitness.coverage_common import cached_fitness
from gentians.rule_generation.reader import read_program
from gentians.rule_generation.program import Example, Program
from gentians.rule_generation.rule_space import RuleSpace


def test_excluded_atoms_are_checked_individually():
    clauses = generate_clauses_for_coverage_interpretations(
        [Example(("ok", "bad(1), bad(f(2,3))"), True)],
        True,
    )

    assert "cpe(0):- bad(1)." in clauses
    assert "cpe(0):- bad(f(2,3))." in clauses
    assert "cpe(0):- bad(1), bad(f(2,3))." not in clauses


def test_coverage_fixed_penalizes_brave_negative_violation():
    program = Program(
        ["1 { a; b } 1."],
        [Example(("a", ""), True)],
        [Example(("a", ""), False)],
        [],
        [],
    )

    score, best_found = coverage_fixed(
        program, 0, [], 0.01, 0.002, 0.01
    )([])

    assert score == math.exp(10)
    assert best_found is False


def test_coverage_fixed_uses_brave_positive_coverage():
    program = Program(
        ["1 { a; b } 1."],
        [Example(("a", ""), True), Example(("b", ""), True)],
        [],
        [],
        [],
    )

    score, best_found = coverage_fixed(
        program, 0, [], 0.01, 0.002, 0.01
    )([])

    assert score == math.exp(15)
    assert best_found is True


def test_coverage_fixed_prefers_positive_coverage_over_clean_overconstraint():
    program = Program(
        ["1 { a; b } 1."],
        [Example(("a", ""), True)],
        [Example(("b", ""), False)],
        [],
        [],
    )
    evaluate = coverage_fixed(program, 0, [], 0.01, 0.002, 0.01)

    covering_score, _ = evaluate([":- b."])
    overconstrained_score, _ = evaluate([":- a.", ":- b."])

    assert covering_score > overconstrained_score


def test_coverage_fixed_uses_normal_fixed_coverage():
    program = Program(
        ["1 { a; b } 1."],
        [Example(("a", ""), True)],
        [Example(("b", ""), False)],
        [],
        [],
    )

    score, best_found = coverage_fixed(
        program,
        0,
        [],
        0.01,
        0.002,
        0.01,
    )([":- b."])

    assert math.isclose(score, math.exp(14.94))
    assert best_found is True


def test_coverage_fixed_uses_one_normal_search_for_fixed_coverage(monkeypatch):
    fixed_module = importlib.import_module("gentians.evolution.fitness.coverage_fixed")
    instances = []
    calls = []

    class FakeSolver:
        def __init__(self, lines, clingo_arguments):
            self.clingo_arguments = clingo_arguments
            instances.append(self)

        def extract_fixed_coverage(
            self,
            candidate_program,
            interpretation_pos,
            interpretation_neg,
        ):
            calls.append(
                (
                    tuple(candidate_program),
                    tuple(self.clingo_arguments),
                    bool(interpretation_pos),
                    bool(interpretation_neg),
                )
            )
            return Coverage([0], [0])

    monkeypatch.setattr(fixed_module, "ClingoInterface", FakeSolver)
    program = Program(
        [],
        [Example(("p", ""), True)],
        [Example(("n", ""), False)],
        [],
        [],
    )

    score, best_found = fixed_module.coverage_fixed(
        program,
        0,
        ["--project"],
        0.0,
        0.0,
        0.0,
    )([])

    assert instances[0].clingo_arguments == ["0", "--project"]
    assert calls == [
        ((), ("0", "--project"), True, True),
    ]
    assert (score, best_found) == (math.exp(10), False)


def test_coverage_fixed_rejects_sudoku_without_row_constraint():
    rules = [
        ":- same_row(V0,V0),same_col(V0,V0),same_block(V1,V1).",
        ":- same_row(V0,V0),same_col(V1,V1),same_block(V1,V1).",
        ":- same_row(V0,V1),same_col(V0,V0),same_block(V1,V1).",
        ":- same_row(V0,V1),same_col(V1,V0),same_block(V1,V1).",
        ":- value(V0,V1),value(V2,V1),same_block(V0,V2).",
        ":- value(V0,V1),value(V2,V1),same_col(V0,V2).",
    ]
    args = arguments_for("sudoku")
    program = read_program(args.filename)

    rule_space = RuleSpace.from_clauses(rules)
    _, best_found = coverage_fixed(
        program,
        int(args.fitness["max_as"]),
        list(args.fitness["clingo_arguments"]),
        float(args.fitness["size_penalty"]),
        float(args.fitness["literal_penalty"]),
        float(args.fitness["redundancy_penalty"]),
    )(rule_space.clauses)

    assert best_found is False


def test_coverage_fixed_penalizes_literals_and_redundancy():
    program = Program(
        ["ok.", "p(1).", "q(2)."],
        [Example(("ok", ""), True)],
        [],
        [],
        [],
    )
    rules = [
        "target :- ok,p(1),q(2).",
        "target :- ok,p(V0),q(V1),V0!=V1,V1!=V0.",
    ]
    evaluate = coverage_fixed(program, 0, [], 0.01, 0.002, 0.01)

    small_score, small_best = evaluate([rules[0]])
    redundant_score, redundant_best = evaluate([rules[1]])

    assert small_best is True
    assert redundant_best is True
    assert small_score > redundant_score


def test_cached_fitness_reuses_canonical_program_result():
    cache = {}
    calls = []

    def compute(candidate_program):
        calls.append(candidate_program)
        return 1.0, True

    score, best_found = cached_fitness(cache, [1, 0, 0], compute)

    assert (score, best_found) == (1.0, True)
    assert calls == [[0, 0, 1]]


def test_extract_fixed_coverage_does_not_dump_each_candidate(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    coverage = ClingoInterface(["base."], ["0", "--enum-mode=brave"]).extract_fixed_coverage(
        ["target :- base."],
        [Example(("target", ""), True)],
        [],
    )

    assert coverage.pos_mask == 1
    assert not (tmp_path / ".debug" / "clingo").exists()


def test_build_fixed_coverage_program_combines_static_program_and_rules():
    dump = build_fixed_coverage_program(
        ["base."],
        ["target :- base."],
        [Example(("target", ""), True)],
        [],
    )

    assert "base." in dump
    assert "pos_exs(0..0)." in dump
    assert "target :- base." in dump


