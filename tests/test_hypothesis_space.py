import copy
from pathlib import Path
import random
import re

import clingo
import pytest
from benchmarks.catalog import CASES
from gentians.arguments import Arguments
from gentians.asp.normal_coverage_solver import NormalCoverageSolver
from gentians import timing
from gentians.rule_generation import hypothesis_space
from gentians.rule_generation.parser import (
    clause_predicates,
    extract_name_arity,
    fragment_atoms,
    parse_atom,
)
from gentians.rule_generation.reader import read_program
from gentians.rule_generation.hypothesis_space import (
    HypothesisSpaceGenerator,
    _hypothesis_space_args,
)
from gentians.rule_generation.arithmetic_expression import ArithmeticExpression
from gentians.rule_generation.arithmetic_system import (
    ArithmeticSystem,
    canonical_arithmetic_clause,
)
from gentians.rule_generation.linear_constraint import LinearConstraint
from gentians.rule_generation.literal_template import render_literal
from gentians.rule_generation.aggregate_declaration import AggregateDeclaration
from gentians.rule_generation.expression_constraint import ExpressionConstraint
from gentians.rule_generation.example import Example
from gentians.rule_generation.aggregate_literal import AggregateLiteral
from gentians.rule_generation.arithmetic_literal import ArithmeticLiteral
from gentians.rule_generation.atom_literal import AtomLiteral
from gentians.rule_generation.atom_template import AtomTemplate
from gentians.rule_generation.comparison_literal import ComparisonLiteral
from gentians.rule_generation.conditional_literal import ConditionalLiteral
from gentians.rule_generation.head_declaration import HeadDeclaration
from gentians.rule_generation.head_template import HeadTemplate
from gentians.rule_generation.hypothesis_mode import HypothesisMode
from gentians.rule_generation.mode_declaration import ModeDeclaration
from gentians.rule_generation.operator_declaration import OperatorDeclaration
from gentians.rule_generation.program import Program
from gentians.rule_generation.reified_clause import ReifiedClause
from gentians.rule_generation.reified_literal import ReifiedLiteral
from gentians.rule_generation.rule_space import RuleSpace
from gentians.rule_generation.term_template import TermTemplate


def _generate(program, max_body_literals=3, max_variables=3):
    program.max_body_literals = max_body_literals
    program.max_variables = max_variables
    return HypothesisSpaceGenerator(program, Arguments()).generate()


def _mode(
    recall: int,
    name: str,
    arity: int,
    *,
    head: bool = False,
    positive: bool = True,
    type_name: str = "numeric",
) -> ModeDeclaration | HeadDeclaration:
    atom = AtomTemplate(
        name,
        tuple(TermTemplate.variable(type_name, "any") for _ in range(arity)),
    )
    return (
        HeadDeclaration(recall, HeadTemplate("normal", (atom,)))
        if head
        else ModeDeclaration(recall, AtomLiteral(atom, not positive))
    )


def _normal_hypothesis_mode(
    id: int,
    recall_group: int,
    section: str,
    name: str,
    arity: int,
    recall: int,
    *,
    positive: bool = True,
    types: tuple[str, ...] = (),
    fixed: tuple[str | None, ...] = (),
    head_form: int | None = None,
) -> HypothesisMode:
    terms = tuple(
        TermTemplate.fixed(value)
        if value is not None
        else TermTemplate.variable(types[index] if types else "any", "")
        for index, value in enumerate(fixed or (None,) * arity)
    )
    head = HeadTemplate("normal", (AtomTemplate(name, terms),)) if section == "head" else None
    return HypothesisMode(
        id,
        recall_group,
        section,
        recall,
        AtomLiteral(AtomTemplate(name, terms), not positive),
        head_form,
        0,
        head,
    )


def _arithmetic_hypothesis_mode(
    id: int,
    arity: int,
    operator: str,
    recall: int = 1,
) -> HypothesisMode:
    assert arity == 3
    return HypothesisMode(
        id,
        id,
        "body",
        recall,
        ArithmeticLiteral(
            TermTemplate(
                "arithmetic",
                operator,
                (
                    TermTemplate.variable("numeric", ""),
                    TermTemplate.variable("numeric", ""),
                ),
            ),
            TermTemplate.variable("numeric", ""),
        ),
    )


def _comparison_hypothesis_mode(id: int, operator: str) -> HypothesisMode:
    term = TermTemplate.variable("any", "")
    return HypothesisMode(
        id,
        id,
        "body",
        1,
        ComparisonLiteral(operator, (term, term)),
    )


def test_valid_aggregate_specs_skips_predicate_scan_without_aggregates(monkeypatch):
    def fail_if_called(program):
        raise AssertionError("predicate scan should not run without aggregate specs")

    monkeypatch.setattr(hypothesis_space, "_available_predicates", fail_if_called)

    assert hypothesis_space._valid_aggregate_specs(Program(["p(1)."], [], [], [], [])) == []


def test_hypothesis_generator_computes_valid_aggregate_specs_once(monkeypatch):
    calls = 0

    def aggregate_specs(program, fragments):
        nonlocal calls
        calls += 1
        return [AggregateDeclaration(1, "sum", (("p", 1),), False)]

    monkeypatch.setattr(hypothesis_space, "_valid_aggregate_specs", aggregate_specs)

    hypothesis_space.HypothesisSpaceGenerator(
        Program(
            ["p(1)."],
            [],
            [],
            [_mode(1, "target", 1, head=True)],
            [_mode(1, "p", 1, positive=True)],
            [AggregateDeclaration(1, "sum", (("p", 1),), False)],
        ),
        Arguments(),
    )

    assert calls == 1


def test_hypothesis_generator_decodes_models_without_shown_symbols(monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("hypothesis generation must not materialize shown symbols")

    monkeypatch.setattr(clingo.Model, "symbols", fail_if_called)
    program = Program(
        ["edge(1,2)."],
        [],
        [],
        [_mode(1, "target", 1, head=True)],
        [_mode(1, "edge", 2, positive=True)],
        max_variables=2,
        max_body_literals=2,
    )

    clauses = HypothesisSpaceGenerator(program, Arguments()).generate().clauses

    assert "target(V0) :- edge(V0,V1)." in clauses


def test_hypothesis_encoding_prunes_duplicates_without_output_atoms():
    rules = hypothesis_space.HYPOTHESIS_SPACE_RULES

    assert ":- same_normal_literal(" in rules
    assert ":- same_mode_literal(" in rules
    assert "code_prefix(" not in rules
    assert "#show lit/4." not in rules


def test_model_decoder_uses_gapless_and_nondecreasing_slot_invariants():
    class FakeModel:
        def __init__(self, true_literals):
            self.true_literals = true_literals
            self.calls = []

        def is_true(self, literal):
            self.calls.append(literal)
            return literal in self.true_literals

    model = FakeModel({102, 202, 203, 112, 212, 214, 133})
    index = (
        (
            "body",
            0,
                ((1, (0, 1), 101), (2, (0, 1), 102)),
            (((0, 201), (1, 202)), ((0, 203), (1, 204))),
        ),
        (
            "body",
            1,
                ((1, (0, 1), 111), (2, (0, 1), 112)),
            (((0, 211), (1, 212)), ((0, 213), (1, 214))),
        ),
            ("body", 2, ((2, (), 122), (3, (), 123)), ()),
            ("body", 3, ((3, (), 133),), ()),
    )

    clause = hypothesis_space._clause_from_model(model, index)

    assert [(literal.mode_id, literal.variables) for literal in clause.body] == [
        (2, (1, 0)),
        (2, (1, 1)),
    ]
    assert 111 not in model.calls
    assert 133 not in model.calls


def test_facts_do_not_emit_redundant_control_flags():
    facts = hypothesis_space._facts(
        Program([], [], [], [], []),
        [],
        {},
        3,
        1,
        4,
    )

    assert "max_body(4)." in facts
    assert "constraints_allowed." not in facts
    assert "canonical_prune." not in facts
    assert "prune_arithmetic_identities." not in facts
    assert "normal_mode(0)." not in facts


def test_facts_do_not_emit_redundant_strict_comparison_mode():
    program = Program(
        [],
        [],
        [],
        [],
        [],
        [],
        [OperatorDeclaration(1, "lt")],
    )
    modes = [
        HypothesisMode(
            0,
            0,
            "body",
            1,
            ComparisonLiteral(
                "<",
                (
                    TermTemplate.variable("numeric", ""),
                    TermTemplate.variable("numeric", ""),
                ),
            ),
        )
    ]
    facts = hypothesis_space._facts(
        program,
        modes,
        {},
        3,
        1,
        3,
    )

    fact_lines = set(facts.splitlines())

    assert "less_than_comparison_mode(0)." in fact_lines
    assert "comparison_mode(0)." not in fact_lines
    assert "symmetric_comparison_mode(0)." not in fact_lines
    assert "strict_comparison_mode(0)." not in fact_lines
    assert "strict_comparison_available." not in fact_lines


def test_facts_do_not_emit_redundant_arithmetic_mode():
    modes = [
        _arithmetic_hypothesis_mode(0, 3, "+")
    ]
    facts = hypothesis_space._facts(
        Program([], [], [], [], [], [], [], [OperatorDeclaration(1, "add")]),
        modes,
        {},
        3,
        1,
        3,
    )

    fact_lines = set(facts.splitlines())

    assert "add_mode(0)." in fact_lines
    assert "arithmetic_mode(0)." not in fact_lines


def test_facts_do_not_emit_derived_numeric_domain_args():
    facts = hypothesis_space._facts(
        Program([], [], [], [], []),
        [
            _normal_hypothesis_mode(
                0, 0, "body", "p", 2, 1, types=("numeric", "any")
            )
        ],
        {("p", 2, 0): "numeric"},
        3,
        1,
        3,
    )

    fact_lines = set(facts.splitlines())

    assert "mode_arg_type(0,0,numeric)." in fact_lines
    assert "mode_arg_type(0,1,any)." not in fact_lines
    assert "domain_numeric_arg(0,2,0)." not in fact_lines


def test_facts_emit_only_strong_positive_numeric_domain_property():
    facts = hypothesis_space._facts(
        Program(["p(1).", "p(2)."], [], [], [], []),
        [],
        {},
        3,
        1,
        3,
    )

    assert "numeric_domain_positive." in facts
    assert "numeric_domain_nonnegative." not in facts
    assert "zero_not_in_numeric_domain." not in facts


def _reset_timing_state() -> None:
    timing.reset()


def test_candidate_rule_space_runs_inside_hypothesis_space_phase(monkeypatch):
    _reset_timing_state()
    monkeypatch.setattr(timing, "_enabled", True)
    phases = []

    class FakeHypothesisSpaceGenerator:
        def __init__(self, program, args):
            pass

        def generate(self):
            phases.append(timing.current_phase())
            return RuleSpace.from_clauses(["p."])

    monkeypatch.setattr(
        hypothesis_space, "HypothesisSpaceGenerator", FakeHypothesisSpaceGenerator
    )

    clauses = hypothesis_space.build_hypothesis_space(
        Program([], [], [], [], []), Arguments()
    )

    assert phases == ["hypothesis_space"]
    assert clauses.clauses == ("p.",)
    assert "hypothesis_space" in timing._totals
    assert "total_execution.grounding" not in timing._totals
    _reset_timing_state()


def test_hypothesis_space_is_generated_each_time(monkeypatch):
    generated = []

    class FakeHypothesisSpaceGenerator:
        def __init__(self, program, args):
            pass

        def generate(self):
            generated.append(True)
            return RuleSpace.from_clauses(["p."])

    monkeypatch.setattr(
        hypothesis_space, "HypothesisSpaceGenerator", FakeHypothesisSpaceGenerator
    )
    program = Program([], [], [], [], [])

    first = hypothesis_space.build_hypothesis_space(program, Arguments())
    second = hypothesis_space.build_hypothesis_space(program, Arguments())

    assert first.clauses == second.clauses == ("p.",)
    assert generated == [True, True]


def test_hypothesis_space_clingo_times_use_current_phase(monkeypatch):
    _reset_timing_state()
    monkeypatch.setattr(timing, "_enabled", True)
    program = Program(
        ["p(1)."],
        [],
        [],
        [_mode(1, "target", 1, head=True)],
        [_mode(1, "p", 1, positive=True)],
    )

    with timing.phase("outer"):
        HypothesisSpaceGenerator(program, Arguments()).generate()

    assert "outer.grounding" in timing._totals
    assert "outer.solving" in timing._totals
    assert "hypothesis_space.solving" not in timing._totals
    _reset_timing_state()


def test_unbalanced_aggregate_variants_share_recall():
    program = Program(
        ["el(1,2).", "el(2,3)."],
        [],
        [],
        [_mode(1, "ok", 1, head=True)],
        [],
        [AggregateDeclaration(1, "sum", (("el", 2),), True)],
        max_variables=8,
        max_body_literals=6,
    )
    clauses = HypothesisSpaceGenerator(program, Arguments()).generate().clauses

    assert not any("#sum{V0:el(V0,V0)}" in clause for clause in clauses)
    assert any("#sum{V0:el(V0,V1)}" in clause for clause in clauses)
    assert not any("#sum{V0,V1:el(V0,V1)}" in clause for clause in clauses)
    assert not any(clause.count("#sum{") > 1 for clause in clauses)


def test_atom_parser_handles_nested_arguments():
    assert parse_atom("same_row((X1,Y),(X2,Y))") == (
        "same_row",
        ["(X1,Y)", "(X2,Y)"],
    )
    assert extract_name_arity("same_row((X1,Y),(X2,Y))") == (
        "same_row",
        2,
    )


def test_recursive_syntax_tracks_nested_bindings_and_renders_concrete_terms():
    term = TermTemplate(
        "function",
        "pair",
        (
            TermTemplate.variable("node", "input"),
            TermTemplate(
                "tuple",
                arguments=(
                    TermTemplate.constant("symbol"),
                    TermTemplate.variable("node", "output"),
                ),
            ),
        ),
    )
    concrete = term.concretizations({"symbol": ("a",)})[0]
    literal = AtomLiteral(AtomTemplate("nested", (concrete,)))

    assert [binding.path for binding in literal.atom.bindings()] == [
        (0, 0),
        (0, 1, 1),
    ]
    assert render_literal(literal, (2, 5)) == "nested(pair(V2,(a,V5)))"


def test_reader_parses_recursive_function_and_tuple_mode_terms(tmp_path):
    task = tmp_path / "structured-reader.txt"
    task.write_text(
        "#modeh(1,target(box(var(node,input,x),"
        "pair((const(colour),var(node,output,y)))))).\n"
        "#constant(colour,red).\n",
        encoding="utf-8",
    )

    atom = read_program(str(task)).language_bias_head[0].template.elements[0]

    assert atom.terms[0].kind == "function"
    assert atom.terms[0].value == "box"
    assert atom.terms[0].arguments[1].arguments[0].kind == "tuple"
    assert [binding.path for binding in atom.bindings()] == [
        (0, 0),
        (0, 1, 0, 1),
    ]
    assert [binding.label for binding in atom.bindings()] == ["x", "y"]


def test_reader_rejects_invalid_recursive_mode_terms(tmp_path):
    declarations = (
        "#modeb(1,p(f)).",
        "#modeb(1,p((var(node,input)))).",
        "#modeb(1,p(var(node,input,extra,label))).",
        "#modeb(1,p(f(not))).",
        "#modeb(1,p(f(var(node,input,label)))).",
    )

    for index, declaration in enumerate(declarations):
        task = tmp_path / f"invalid-structured-{index}.txt"
        task.write_text(declaration + "\n", encoding="utf-8")
        with pytest.raises(ValueError):
            read_program(str(task))


def test_closed_world_extensions_ignore_compound_variable_terms():
    extensions = hypothesis_space._closed_world_extensions(
        [
            "cell((1..4,1..4)).",
            "same_row((X1,Y),(X2,Y)) :- cell((X1,Y)), cell((X2,Y)).",
        ]
    )

    assert ("cell", 1) not in extensions
    assert ("same_row", 2) not in extensions


def test_atom_parser_does_not_treat_not_prefix_as_negation():
    assert parse_atom("notable(X)") == ("notable", ["X"])
    assert parse_atom("not notable(X)") == ("notable", ["X"])


def test_hypothesis_space_args_keep_numeric_strings():
    args = Arguments(hypothesis_space={"clingo_arguments": ["0", "--project"]})

    assert _hypothesis_space_args(args) == ["0", "--project"]


def test_hypothesis_space_args_reject_string():
    args = Arguments(hypothesis_space={"clingo_arguments": "--project"})

    try:
        _hypothesis_space_args(args)
    except ValueError as exc:
        assert "clingo_arguments" in str(exc)
    else:
        raise AssertionError("string clingo_arguments should fail")


def test_star_recall_uses_section_limit():
    mode = _mode(-1, "p", 1)
    facts = hypothesis_space._facts(
        Program([], [], [], [], [mode]),
        [
            _normal_hypothesis_mode(0, 0, "body", "p", 1, mode.recall)
        ],
        {},
        2,
        2,
        3,
    )

    assert "mode(body,0,0,1,3)." in facts
    assert "group_recall(0,2)." not in facts
    assert "\nrecall(" not in facts
    assert "positive_mode(0)." not in facts
    assert "normal_mode(0)." not in facts


def test_group_recall_uses_tightest_mode_recall():
    facts = hypothesis_space._facts(
        Program([], [], [], [], []),
        [
            _normal_hypothesis_mode(0, 7, "body", "p", 1, 3),
            _normal_hypothesis_mode(1, 7, "body", "q", 1, 1),
        ],
        {("p", 1): 0, ("q", 1): 1},
        3,
        1,
        5,
    )

    assert "mode(body,0,0,1,3)." in facts
    assert "mode(body,1,1,1,1)." in facts
    assert "group_recall(7,1)." not in facts
    assert "group_recall(7,3)." not in facts


def test_reader_parses_structural_limits_and_star(tmp_path):
    task = tmp_path / "task.txt"
    task.write_text(
        "\n".join(
            ["#maxv(*).", "#maxbl(2).", "#maxhl(0).", "#maxpl(*)."]
        ),
        encoding="utf-8",
    )

    program = read_program(str(task))

    assert program.max_variables is None
    assert program.max_body_literals == 2
    assert program.max_head_literals == 0
    assert program.max_program_clauses is None


def test_reader_requires_type_and_direction_for_variable_modes(tmp_path):
    task = tmp_path / "task.txt"
    task.write_text("#modeh(1,target(var(person))).\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid mode argument"):
        read_program(str(task))


def test_reader_uses_not_for_body_mode_polarity(tmp_path):
    task = tmp_path / "task.txt"
    task.write_text(
        "\n".join(
            (
                "#modeb(1,p(var(person,input))).",
                "#modeb(2,not p(var(person,input))).",
                "#modeb(1,notable).",
            )
        ),
        encoding="utf-8",
    )

    program = read_program(str(task))

    assert [
        (
            mode.recall,
            mode.literal.atom.name,
            not mode.literal.default_negated,
        )
        for mode in program.language_bias_body
    ] == [(1, "p", True), (2, "p", False), (1, "notable", True)]


def test_reader_keeps_strong_and_default_negation_independent(tmp_path):
    task = tmp_path / "strong-negation.txt"
    task.write_text(
        "\n".join(
            (
                "#modeh(1,-p(var(person,input))).",
                "#modeb(1,-q(var(person,input))).",
                "#modeb(1,not -r(var(person,input))).",
            )
        ),
        encoding="utf-8",
    )

    program = read_program(str(task))
    head = program.language_bias_head[0].template.elements[0]
    positive_body = program.language_bias_body[0].literal
    default_negative_body = program.language_bias_body[1].literal

    assert head.signature == ("-p", 1)
    assert head.unsigned_signature == ("p", 1)
    assert head.render(iter(("V0",))) == "-p(V0)"
    assert positive_body.atom.signature == ("-q", 1)
    assert not positive_body.default_negated
    assert default_negative_body.atom.signature == ("-r", 1)
    assert default_negative_body.default_negated
    assert default_negative_body.render(iter(("V0",))) == "not -r(V0)"
    generator = HypothesisSpaceGenerator(program, Arguments())
    assert generator.predicate_arg_types[("p", 1, 0)] == "person"
    assert ("-p", 1, 0) not in generator.predicate_arg_types


def test_parser_preserves_strong_negation_in_atoms_and_rule_dependencies():
    assert fragment_atoms("-p(a), not -q(a)") == (
        ("-p", ("a",), False),
        ("-q", ("a",), True),
    )
    assert clause_predicates("-p(X) :- q(X), not -r(X).") == (
        frozenset((("-p", 1),)),
        frozenset((("q", 1), ("-r", 1))),
        2,
    )


def test_dependency_closure_does_not_confuse_positive_and_strong_providers():
    from gentians.evolution.program_generators.common import prepare_space

    space = RuleSpace.from_clauses(["target(X) :- -source(X)."])
    positive_background = Program(["source(a)."], [], [], [], [])
    strong_background = Program(["-source(a)."], [], [], [], [])

    assert not prepare_space(positive_background, space)
    assert prepare_space(strong_background, space).clauses == space.clauses


@pytest.mark.parametrize(
    "declaration",
    [
        "#modeb(1,p(var(person,input)),positive).",
        "#modeh(1,not p(var(person,input))).",
        "#modeb(1,not not p(var(person,input))).",
        "#modeb(1,not).",
        "#modeb(1,not(var(person,input))).",
    ],
)
def test_reader_rejects_invalid_mode_polarity_syntax(tmp_path, declaration):
    task = tmp_path / "task.txt"
    task.write_text(f"{declaration}\n", encoding="utf-8")

    with pytest.raises(ValueError):
        read_program(str(task))


def test_reader_rejects_output_variables_in_negative_modes(tmp_path):
    task = tmp_path / "task.txt"
    task.write_text(
        "#modeb(1,not p(var(person,output))).\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="cannot produce output"):
        read_program(str(task))


def test_constant_modes_expand_declared_ground_terms_without_variables(tmp_path):
    task = tmp_path / "task.txt"
    task.write_text(
        "\n".join(
            (
                "#maxv(0).",
                "#maxbl(1).",
                "#maxhl(1).",
                "#maxpl(1).",
                "q(a).",
                "q(b).",
                "#constant(symbol,a).",
                "#constant(symbol,b).",
                "#modeh(1,p(const(symbol))).",
                "#modeb(1,q(const(symbol))).",
            )
        ),
        encoding="utf-8",
    )

    program = read_program(str(task))
    clauses = HypothesisSpaceGenerator(program, Arguments()).generate().clauses

    assert program.constants == {"symbol": ("a", "b")}
    assert set(clauses) == {
        ":- q(a).",
        ":- q(b).",
        "p(a).",
        "p(b).",
        "p(a) :- q(a).",
        "p(a) :- q(b).",
        "p(b) :- q(a).",
        "p(b) :- q(b).",
    }


def test_constant_mode_requires_declared_values(tmp_path):
    task = tmp_path / "task.txt"
    task.write_text("#modeh(1,p(const(symbol))).\n", encoding="utf-8")

    with pytest.raises(ValueError, match="require #constant"):
        read_program(str(task))


def test_unbounded_section_requires_finite_mode_recalls():
    program = Program(
        ["p(1)."],
        [],
        [],
        [],
        [_mode(-1, "p", 1, positive=True)],
        max_body_literals=None,
    )

    with pytest.raises(ValueError, match=r"#maxbl\(\*\)"):
        HypothesisSpaceGenerator(program, Arguments())


def test_all_structural_limits_accept_star_with_finite_recalls(tmp_path):
    task = tmp_path / "task.txt"
    task.write_text(
        "\n".join(
            [
                "#maxv(*).",
                "#maxbl(*).",
                "#maxhl(*).",
                "#maxpl(*).",
                "p(1).",
                "#modeh(1,target(var(term,any))).",
                "#modeb(1,p(var(term,any))).",
            ]
        ),
        encoding="utf-8",
    )
    program = read_program(str(task))
    generator = HypothesisSpaceGenerator(program, Arguments())

    assert generator.head_slots == 1
    assert generator.body_slots == 1
    assert generator.max_variables == 2
    assert "target(V0) :- p(V0)." in generator.generate().clauses


def test_reader_deduplicates_equal_directives(tmp_path):
    task = tmp_path / "task.txt"
    task.write_text(
        "\n".join(
            [
                "#pos({ a(1) }, {}).",
                "#pos({ a(1) }, {}).",
                "#neg({ b(1) }, {}).",
                "#neg({ b(1) }, {}).",
                "#modeh(1, a(var(term,any))).",
                "#modeh(1, a(var(term,any))).",
                "#modeb(1, b(var(term,any))).",
                "#modeb(1, b(var(term,any))).",
            ]
        ),
        encoding="utf-8",
    )

    program = read_program(str(task))

    assert len(program.positive_examples) == 1
    assert len(program.negative_examples) == 1
    assert len(program.language_bias_head) == 1
    assert len(program.language_bias_body) == 1


def test_invent_replaces_head_and_body_modes(tmp_path):
    task = tmp_path / "task.txt"
    task.write_text(
        "#invent(2,helper(var(term,any),var(term,any))).\n",
        encoding="utf-8",
    )

    program = read_program(str(task))

    assert program.invented_predicates == (("helper", 2),)
    assert [
        (
            head.recall,
            head.template.elements[0].name,
            len(head.template.elements[0].terms),
        )
        for head in program.language_bias_head
    ] == [(1, "helper", 2)]
    assert [
        (
            mode.recall,
            mode.literal.atom.name,
            len(mode.literal.atom.terms),
            not mode.literal.default_negated,
        )
        for mode in program.language_bias_body
    ] == [(2, "helper", 2, True)]


def test_invent_rejects_duplicate_explicit_modes(tmp_path):
    task = tmp_path / "task.txt"
    task.write_text(
        "#invent(2,helper(var(term,any),var(term,any))).\n"
        "#modeh(1,helper(var(term,any),var(term,any))).\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must not also use"):
        read_program(str(task))


def test_invent_rejects_duplicate_signature(tmp_path):
    task = tmp_path / "task.txt"
    task.write_text(
        "#invent(1,helper(var(term,any),var(term,any))).\n"
        "#invent(2,helper(var(term,any),var(term,any))).\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate #invent"):
        read_program(str(task))


def test_invent_rejects_observed_predicate(tmp_path):
    task = tmp_path / "task.txt"
    task.write_text(
        "helper(a).\n#invent(1,helper(var(term,any))).\n",
        encoding="utf-8",
    )
    program = read_program(str(task))

    with pytest.raises(ValueError, match="must not be observed"):
        HypothesisSpaceGenerator(program, Arguments()).generate()


def test_invented_predicates_are_stratified_and_excluded_from_constraints(tmp_path):
    task = tmp_path / "task.txt"
    task.write_text(
        "\n".join(
            [
                "base(a).",
                "#pos({target(a)},{}).",
                "#modeh(1,target(var(term,any))).",
                "#modeb(1,base(var(term,any))).",
                "#modeb(1,target(var(term,any))).",
                "#invent(1,early(var(term,any))).",
                "#invent(1,late(var(term,any))).",
            ]
        ),
        encoding="utf-8",
    )
    program = read_program(str(task))

    clauses = _generate(program, 3, 1).clauses

    assert "late(V0) :- early(V0)." in clauses
    assert "early(V0) :- late(V0)." not in clauses
    assert "early(V0) :- early(V0)." not in clauses
    assert "early(V0) :- target(V0)." not in clauses
    assert "late(V0) :- target(V0)." not in clauses
    assert not any(
        clause.startswith(":-") and ("early(" in clause or "late(" in clause)
        for clause in clauses
    )


def test_invented_definition_cannot_call_target_through_aggregate(tmp_path):
    task = tmp_path / "task.txt"
    task.write_text(
        "\n".join(
            [
                "target(a).",
                "#modeh(1,target(var(term,any))).",
                "#modeagg(1,count(target/1),balanced).",
                "#invent(1,helper(var(term,any))).",
            ]
        ),
        encoding="utf-8",
    )
    program = read_program(str(task))

    clauses = _generate(program, 3, 2).clauses

    assert not any(
        clause.startswith("helper(") and ":target(" in clause
        for clause in clauses
    )


def test_hypothesis_space_prunes_arg_distinct_modes_before_rendering():
    program = Program(
        ["edge(1,2)."],
        [],
        [],
        [_mode(1, "target", 2, head=True)],
        [_mode(1, "edge", 2, positive=True)],
    )
    clauses = _generate(program, 2).clauses

    assert not any("edge(V0,V0)" in clause for clause in clauses)
    assert "target(V0,V1) :- edge(V0,V1)." in clauses


def test_arg_distinct_still_prunes_body_self_pair_without_irreflexive_property():
    program = Program(
        ["p(a,b).", "p(b,a).", "guard(a).", "guard(b)."],
        [],
        [],
        [],
        [
            _mode(2, "p", 2, positive=True),
            _mode(2, "guard", 1, positive=True),
        ],
    )
    clauses = _generate(program, 2, 2).clauses

    assert not any("p(V0,V0)" in clause or "p(V1,V1)" in clause for clause in clauses)


def test_missing_bias_is_not_inferred_from_background():
    program = Program(["p(1,2)."], [], [], [], [])

    clauses = _generate(program, 2, 2).clauses

    assert program.language_bias_head == []
    assert program.language_bias_body == []
    assert clauses == ()


def test_explicit_body_bias_enables_recursion():
    program = Program(
        ["p(1,2)."],
        [],
        [],
        [_mode(1, "p", 2, head=True)],
        [_mode(1, "p", 2, positive=True)],
    )

    clauses = _generate(program, 2, 2).clauses

    assert "p(V1,V0) :- p(V0,V1)." in clauses


def test_hypothesis_space_keeps_task_declared_unobserved_body_modes():
    program = Program(
        ["base(a)."],
        [Example(("target(a)", ""), True)],
        [],
        [_mode(1, "target", 1, head=True)],
        [
            _mode(1, "base", 1, positive=True),
            _mode(1, "ghost", 1, positive=True),
            _mode(1, "ghost", 1, positive=False),
        ],
    )

    generator = HypothesisSpaceGenerator(program, Arguments())
    clauses = generator.generate().clauses

    assert "target(V0) :- base(V0)." in clauses
    assert any(
        isinstance(mode.literal, AtomLiteral)
        and mode.literal.atom.name == "ghost"
        for mode in generator.modes
    )
    assert not any("ghost(" in clause for clause in clauses)


def test_hypothesis_space_prunes_reversed_symmetric_comparisons_before_rendering():
    program = Program(
        ["p(1).", "p(2)."],
        [],
        [],
        [],
        [_mode(2, "p", 1, positive=True)],
        [],
        [OperatorDeclaration(2, "neq")],
    )
    clauses = _generate(program, 4, 2).clauses

    assert not any("V0-V1!=0,V0-V1!=0" in clause for clause in clauses)
    assert any("V0-V1!=0" in clause for clause in clauses)


def test_hypothesis_space_prunes_comparison_redundancy_before_rendering():
    program = Program(
        ["p(1).", "p(2)."],
        [],
        [],
        [],
        [_mode(2, "p", 1, positive=True)],
        [],
        [OperatorDeclaration(1, "lt"), OperatorDeclaration(1, "leq"), OperatorDeclaration(1, "neq")],
    )
    clauses = _generate(program, 4, 2).clauses

    assert not any("V0<V1,V0!=V1" in clause for clause in clauses)
    assert not any("V0<V1,V0<=V1" in clause for clause in clauses)
    assert not any("V0<=V1,V1<=V0" in clause for clause in clauses)


def test_hypothesis_space_does_not_generate_equality_comparison():
    program = Program(
        ["p(1)."],
        [],
        [],
        [_mode(1, "target", 1, head=True)],
        [_mode(1, "p", 1, positive=True)],
        [],
        [OperatorDeclaration(1, "eq")],
    )
    clauses = _generate(program, 3, 2).clauses

    assert clauses
    assert not any("==" in clause for clause in clauses)
    assert "target(V0) :- p(V0)." in clauses


def test_hypothesis_space_prunes_leq_neq_when_strict_comparison_exists():
    program = Program(
        ["p(1).", "p(2)."],
        [],
        [],
        [],
        [_mode(2, "p", 1, positive=True)],
        [],
        [
            OperatorDeclaration(1, "lt"),
            OperatorDeclaration(1, "leq"),
            OperatorDeclaration(1, "neq"),
        ],
    )
    clauses = _generate(program, 4, 2).clauses

    assert not any(
        "V0<=V1" in clause and "V0!=V1" in clause for clause in clauses
    )


def test_hypothesis_space_prunes_transitive_comparison_redundancy():
    program = Program(
        ["p(1).", "p(2).", "p(3)."],
        [],
        [],
        [],
        [_mode(3, "p", 1, positive=True)],
        [],
        [OperatorDeclaration(3, "lt"), OperatorDeclaration(3, "neq")],
    )
    clauses = _generate(program, 6, 3).clauses

    assert not any(
        "V0<V1" in clause and "V1<V2" in clause and "V0<V2" in clause
        for clause in clauses
    )
    assert not any(
        "V0<V1" in clause and "V1<V2" in clause and "V0!=V2" in clause
        for clause in clauses
    )


def test_hypothesis_space_prunes_duplicate_arithmetic_inputs_before_rendering():
    program = Program(
        ["q(1,2)."],
        [],
        [],
        [_mode(1, "target", 2, head=True)],
        [_mode(1, "q", 2, positive=True)],
        [],
        [],
        [OperatorDeclaration(2, "add")],
    )
    clauses = _generate(program, 4, 4).clauses

    assert not any(
        "V0+V1=V2" in clause and "V0+V1=V3" in clause for clause in clauses
    )


def test_positive_domain_prunes_impossible_mul_and_div_comparisons():
    program = Program(
        ["q(1,1,1).", "q(2,2,2).", "q(3,3,3)."],
        [],
        [],
        [],
        [_mode(1, "q", 3, positive=True)],
        [],
        [OperatorDeclaration(1, "lt")],
        [OperatorDeclaration(1, "mul"), OperatorDeclaration(1, "div")],
    )
    clauses = _generate(program, 3, 3).clauses

    assert not any(
        "V0*V1=V2" in clause and "V2<V0" in clause for clause in clauses
    )
    assert not any(
        "V0*V1=V2" in clause and "V2<V1" in clause for clause in clauses
    )
    assert not any(
        "V0/V1=V2" in clause and "V0<V2" in clause for clause in clauses
    )


def test_hypothesis_space_prunes_duplicate_aggregate_inputs_before_rendering():
    program = Program(
        ["el(1).", "el(2)."],
        [],
        [],
        [_mode(1, "target", 2, head=True)],
        [],
        [AggregateDeclaration(2, "sum", (("el", 1),), False)],
    )
    clauses = _generate(program, 3, 4).clauses

    assert not any(
        "#sum{V0:el(V0)}=V1" in clause and "#sum{V0:el(V0)}=V2" in clause
        for clause in clauses
    )


def test_count_aggregate_tuple_variables_are_canonicalized():
    program = Program(
        ["edge(a,b).", "edge(b,a)."],
        [],
        [],
        [_mode(1, "target", 1, head=True)],
        [],
        [AggregateDeclaration(1, "count", (("edge", 2),), False)],
    )
    clauses = _generate(program, 2, 4).clauses

    assert clauses
    assert not any(
        int(left) > int(right)
        for clause in clauses
        for left, right in re.findall(r"#count\{V(\d+),V(\d+):", clause)
    )


def test_hypothesis_space_prunes_arithmetic_identities():
    args = copy.deepcopy(CASES["4queens"])
    clauses = HypothesisSpaceGenerator(read_program(args.filename), args).generate().clauses

    assert clauses
    assert not any("V0+V1=V2,V2-V0=V1" in clause for clause in clauses)


def test_linear_canonicalization_merges_equivalent_add_sub_equations():
    program = Program(
        ["q(1,2,3)."],
        [],
        [],
        [],
        [_mode(1, "q", 3, positive=True)],
        [],
        [],
        [OperatorDeclaration(1, "add"), OperatorDeclaration(1, "sub")],
        max_head_literals=0,
    )

    arithmetic = {
        clause
        for clause in _generate(program, 2, 3).clauses
        for match in [re.search(r",V(\d+)\+V(\d+)-V(\d+)=0", clause)]
        if clause.count("=") == 1
        and clause.count("+") == 1
        and match is not None
        and len(set(match.groups())) == 3
    }

    assert arithmetic == {":- q(V0,V1,V2),V0+V1-V2=0."}


def test_nested_constants_expand_and_structured_modes_render(tmp_path):
    task = tmp_path / "structured-generation.txt"
    task.write_text(
        "\n".join(
            (
                "source(box(a,red)).",
                "source(box(a,blue)).",
                "#constant(colour,red).",
                "#constant(colour,blue).",
                "#maxv(1).",
                "#maxbl(1).",
                "#maxhl(1).",
                "#modeh(1,target(box(var(node,output),const(colour)))).",
                "#modeb(1,source(box(var(node,output),const(colour)))).",
            )
        ),
        encoding="utf-8",
    )

    clauses = set(
        HypothesisSpaceGenerator(read_program(str(task)), Arguments())
        .generate()
        .clauses
    )

    assert "target(box(V0,red)) :- source(box(V0,red))." in clauses
    assert "target(box(V0,red)) :- source(box(V0,blue))." in clauses
    assert "target(box(V0,blue)) :- source(box(V0,red))." in clauses
    assert "target(box(V0,blue)) :- source(box(V0,blue))." in clauses


def test_empty_and_singleton_tuples_render_as_asp_tuples(tmp_path):
    task = tmp_path / "tuple-arities.txt"
    task.write_text(
        "\n".join(
            (
                "source((a,),()).",
                "#maxv(1).",
                "#maxbl(1).",
                "#maxhl(1).",
                "#modeh(1,target((var(node,output),),())).",
                "#modeb(1,source((var(node,output),),())).",
            )
        ),
        encoding="utf-8",
    )

    clauses = HypothesisSpaceGenerator(
        read_program(str(task)), Arguments()
    ).generate().clauses

    assert "target((V0,),()) :- source((V0,),())." in clauses


def test_flat_constants_keep_outer_argument_positions(tmp_path):
    task = tmp_path / "flat-constant-position.txt"
    task.write_text(
        "\n".join(
            (
                "source(a,1).",
                "#constant(symbol,a).",
                "#maxv(1).",
                "#maxbl(1).",
                "#maxhl(1).",
                "#modeh(1,target(var(number,output))).",
                "#modeb(1,source(const(symbol),var(number,output))).",
            )
        ),
        encoding="utf-8",
    )

    program = read_program(str(task))
    generator = HypothesisSpaceGenerator(program, Arguments())
    body_mode = next(mode for mode in generator.modes if mode.section == "body")
    facts = hypothesis_space._facts(
        program,
        generator.modes,
        generator.predicate_arg_types,
        generator.max_variables,
        generator.head_slots,
        generator.body_slots,
    )

    assert f"mode_variable_arg({body_mode.id},1)." in facts
    assert "target(V0) :- source(a,V0)." in generator.generate().clauses


def test_nested_constant_requires_declaration(tmp_path):
    task = tmp_path / "missing-nested-constant.txt"
    task.write_text(
        "#modeh(1,target(box(const(colour)))).\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="colour"):
        read_program(str(task))


def test_default_negated_structured_mode_cannot_hide_output(tmp_path):
    task = tmp_path / "negative-structured-output.txt"
    task.write_text(
        "#modeb(1,not source(box(var(node,output)))).\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="cannot produce output"):
        read_program(str(task))


@pytest.mark.parametrize("recall", [1, -1])
def test_linear_canonicalization_normalizes_sub_only_bias(recall):
    program = Program(
        ["q(1,2,3)."],
        [],
        [],
        [],
        [_mode(1, "q", 3, positive=True)],
        [],
        [],
        [OperatorDeclaration(recall, "sub")],
        max_head_literals=0,
    )

    generator = HypothesisSpaceGenerator(program, Arguments())
    arithmetic_modes = [
        mode for mode in generator.modes if isinstance(mode.literal, ArithmeticLiteral)
    ]
    assert len(arithmetic_modes) == 1
    assert arithmetic_modes[0].recall == recall
    assert arithmetic_modes[0].literal.operator == "+"
    assert arithmetic_modes[0].literal.coefficients == (1, 1, -1)
    assert any(
        "V0-V1-V2=0" in clause for clause in generator.generate().clauses
    )


def test_invention_preserves_structured_argument_templates(tmp_path):
    task = tmp_path / "structured-invention.txt"
    task.write_text(
        "#invent(1,helper(box(var(term,input),var(term,output)))).\n",
        encoding="utf-8",
    )

    program = read_program(str(task))
    head_atom = program.language_bias_head[0].template.elements[0]
    body_atom = program.language_bias_body[0].literal.atom

    assert program.invented_predicates == (("helper", 1),)
    assert head_atom == body_atom
    assert head_atom.terms[0].kind == "function"
    assert [binding.direction for binding in head_atom.bindings()] == [
        "input",
        "output",
    ]


@pytest.mark.parametrize(
    ("declarations", "expected_recalls"),
    [
        (
            [OperatorDeclaration(1, "add"), OperatorDeclaration(2, "sub")],
            (3,),
        ),
        (
            [OperatorDeclaration(-1, "add"), OperatorDeclaration(2, "sub")],
            (-1,),
        ),
        (
            [
                OperatorDeclaration(1, "mul"),
                OperatorDeclaration(2, "sub"),
                OperatorDeclaration(1, "div"),
                OperatorDeclaration(1, "add"),
                OperatorDeclaration(1, "mod"),
            ],
            (3, 1, 1, 1),
        ),
    ],
)
def test_additive_modes_share_one_canonical_mode_with_combined_recall(
    declarations, expected_recalls
):
    program = Program(
        ["q(1,2,3)."],
        [],
        [],
        [],
        [_mode(1, "q", 3, positive=True)],
        [],
        [],
        declarations,
        max_head_literals=0,
    )

    generator = HypothesisSpaceGenerator(program, Arguments())
    arithmetic_modes = [
        mode for mode in generator.modes if isinstance(mode.literal, ArithmeticLiteral)
    ]
    assert arithmetic_modes
    assert arithmetic_modes[0].recall == expected_recalls[0]


def test_inverse_comparisons_share_one_mode_with_combined_recall():
    program = Program(
        ["q(1,2)."],
        [],
        [],
        [],
        [_mode(1, "q", 2, positive=True)],
        comparison_modes=[
            OperatorDeclaration(1, "lt"),
            OperatorDeclaration(2, "gt"),
            OperatorDeclaration(3, "leq"),
            OperatorDeclaration(4, "geq"),
        ],
    )

    comparisons = [
        mode
        for mode in HypothesisSpaceGenerator(program, Arguments()).modes
        if isinstance(mode.literal, ComparisonLiteral)
    ]

    assert [(mode.literal.operator, mode.recall) for mode in comparisons] == [
        ("<", 3),
        ("<=", 7),
    ]


def test_linear_canonicalization_reduces_complete_nqueens_systems():
    args = copy.deepcopy(CASES["5queens"])
    clauses = HypothesisSpaceGenerator(read_program(args.filename), args).generate().clauses

    assert len(clauses) == 4805
    assert clauses == tuple(sorted(clauses))
    assert (
        ":- q(V0,V1),q(V2,V3),V0+V1-V2-V3=0,-V1+V3<0."
        in clauses
    )
    assert (
        ":- q(V0,V1),q(V2,V3),V0-V1-V2+V3=0,V1-V3<0."
        in clauses
    )


def test_linear_modes_render_direct_equations_with_bounded_complexity():
    program = Program(
        ["q(1,2,3,4)."],
        [],
        [],
        [],
        [_mode(1, "q", 4, positive=True)],
        [],
        [],
        [OperatorDeclaration(2, "add")],
        max_head_literals=0,
        max_body_literals=3,
        max_variables=5,
    )
    generator = HypothesisSpaceGenerator(program, Arguments())
    assert len(
        [
            mode
            for mode in generator.modes
            if isinstance(mode.literal, ArithmeticLiteral)
        ]
    ) == 1
    assert any("V0+V1-V2-V3=0" in clause for clause in generator.generate().clauses)


def test_linear_mode_complexity_is_capped_by_body_limit():
    program = Program(
        ["q(1,2,3)."],
        [],
        [],
        [],
        [_mode(1, "q", 3, positive=True)],
        [],
        [],
        [OperatorDeclaration(100, "add")],
        max_body_literals=3,
    )

    generator = HypothesisSpaceGenerator(program, Arguments())

    arithmetic_modes = [
        mode for mode in generator.modes if isinstance(mode.literal, ArithmeticLiteral)
    ]
    assert len(arithmetic_modes) == 1
    assert arithmetic_modes[0].recall == 100
    assert arithmetic_modes[0].literal.complexity == 1


def test_direct_linear_equation_can_safely_produce_a_head_variable():
    program = Program(
        ["q(1,2,3)."],
        [],
        [],
        [
            HeadDeclaration(
                1,
                HeadTemplate(
                    "normal",
                    (
                        AtomTemplate(
                            "target",
                            (TermTemplate.variable("numeric", "output"),),
                        ),
                    ),
                ),
            )
        ],
        [_mode(1, "q", 3, positive=True)],
        [],
        [],
        [OperatorDeclaration(2, "add")],
        max_head_literals=1,
        max_body_literals=3,
        max_variables=5,
    )

    clauses = HypothesisSpaceGenerator(program, Arguments()).generate().clauses

    assert "target(V3) :- q(V0,V1,V2),V0+V1=V3." in clauses


def test_linear_canonicalization_eliminates_connected_auxiliary_variables():
    modes = {
        0: _normal_hypothesis_mode(0, 0, "body", "q", 3, 1),
        1: _arithmetic_hypothesis_mode(1, 3, "+"),
        2: _comparison_hypothesis_mode(2, "<"),
    }
    clause = ReifiedClause(
        (),
        (
            ReifiedLiteral("body", 0, 0, (0, 1, 2)),
            ReifiedLiteral("body", 1, 1, (0, 1, 3)),
            ReifiedLiteral("body", 2, 2, (3, 2)),
        ),
    )

    canonical = canonical_arithmetic_clause(clause, modes, 4)

    assert canonical is not None
    assert isinstance(canonical.systems[0].relations[0], LinearConstraint)

    equivalent_modes = {
        **modes,
        3: _arithmetic_hypothesis_mode(3, 3, "-"),
    }
    equivalent = ReifiedClause(
        (),
        (
            ReifiedLiteral("body", 0, 0, (0, 1, 2)),
            ReifiedLiteral("body", 1, 3, (2, 1, 3)),
            ReifiedLiteral("body", 2, 2, (0, 3)),
        ),
    )

    equivalent_system = canonical_arithmetic_clause(equivalent, equivalent_modes, 4)

    assert equivalent_system is not None
    assert equivalent_system.key == canonical.key

    disequality_modes = {
        **modes,
        2: _comparison_hypothesis_mode(2, "!="),
    }
    disequality = canonical_arithmetic_clause(clause, disequality_modes, 4)

    assert disequality is not None
    assert disequality.key != canonical.key


def test_linear_canonicalization_keeps_disconnected_constraints_separate():
    modes = {
        0: _normal_hypothesis_mode(0, 0, "body", "q", 5, 1),
        1: _arithmetic_hypothesis_mode(1, 3, "+"),
        2: _comparison_hypothesis_mode(2, "<"),
        3: _comparison_hypothesis_mode(3, "!="),
    }
    clause = ReifiedClause(
        (),
        (
            ReifiedLiteral("body", 0, 0, (0, 1, 2, 3, 4)),
            ReifiedLiteral("body", 1, 1, (0, 1, 5)),
            ReifiedLiteral("body", 2, 2, (5, 2)),
            ReifiedLiteral("body", 3, 3, (3, 4)),
        ),
    )

    canonical = canonical_arithmetic_clause(clause, modes, 6)

    assert canonical is not None
    assert len(canonical.systems) == 2


def test_linear_canonicalization_preserves_unsafe_output_assignment():
    modes = {
        0: _normal_hypothesis_mode(
            0, 0, "head", "target", 1, 1, head_form=0
        ),
        1: _normal_hypothesis_mode(1, 1, "body", "p", 1, 1),
        2: _arithmetic_hypothesis_mode(2, 3, "+"),
    }
    clause = ReifiedClause(
        (ReifiedLiteral("head", 0, 0, (1,)),),
        (
            ReifiedLiteral("body", 0, 1, (0,)),
            ReifiedLiteral("body", 1, 2, (0, 0, 1)),
        ),
    )

    canonical = canonical_arithmetic_clause(clause, modes, 2)

    assert canonical is not None
    assert isinstance(canonical.systems[0].relations[0], ExpressionConstraint)
    assert canonical.render(modes) == "target(V1) :- p(V0),V0+V0=V1."


def test_linear_canonicalization_preserves_components_with_multiplication():
    modes = {
        0: _normal_hypothesis_mode(0, 0, "body", "q", 4, 1),
        1: _arithmetic_hypothesis_mode(1, 3, "+"),
        2: _arithmetic_hypothesis_mode(2, 3, "*"),
    }
    clause = ReifiedClause(
        (),
        (
            ReifiedLiteral("body", 0, 0, (0, 1, 2, 3)),
            ReifiedLiteral("body", 1, 1, (0, 1, 2)),
            ReifiedLiteral("body", 2, 2, (2, 0, 3)),
        ),
    )

    canonical = canonical_arithmetic_clause(clause, modes, 4)

    assert canonical is not None
    assert len(canonical.systems) == 1
    assert all(
        isinstance(relation, ExpressionConstraint)
        for relation in canonical.systems[0].relations
    )
    assert canonical.render(modes) == ":- q(V0,V1,V2,V3),V2*V0-V3=0,V0+V1-V2=0."


def test_arithmetic_system_inlines_mixed_nonlinear_auxiliaries():
    modes = {
        0: _normal_hypothesis_mode(
            0, 0, "head", "target", 1, 1, head_form=0
        ),
        1: _normal_hypothesis_mode(1, 1, "body", "q", 3, 1),
        2: _arithmetic_hypothesis_mode(2, 3, "+"),
        3: _arithmetic_hypothesis_mode(3, 3, "*"),
    }
    clause = ReifiedClause(
        (ReifiedLiteral("head", 0, 0, (4,)),),
        (
            ReifiedLiteral("body", 0, 1, (0, 1, 2)),
            ReifiedLiteral("body", 1, 2, (0, 1, 3)),
            ReifiedLiteral("body", 2, 3, (3, 2, 4)),
        ),
    )

    canonical = canonical_arithmetic_clause(clause, modes, 5)

    assert canonical is not None
    assert canonical.render(modes) == "target(V4) :- q(V0,V1,V2),(V0+V1)*V2=V4."


def test_arithmetic_expression_key_normalizes_associativity_and_signs():
    x = ArithmeticExpression.var(0)
    y = ArithmeticExpression.var(1)
    z = ArithmeticExpression.var(2)
    left_associative = ArithmeticExpression(
        "+", (ArithmeticExpression("-", (x, y)), z)
    )
    reordered = ArithmeticExpression(
        "-", (ArithmeticExpression("+", (z, x)), y)
    )

    assert left_associative.key == reordered.key
    forward = ExpressionConstraint(ArithmeticExpression("-", (x, y)), "eq")
    reverse = ExpressionConstraint(ArithmeticExpression("-", (y, x)), "eq")
    assert forward.key == reverse.key


def test_arithmetic_system_preserves_multiple_definitions_of_an_auxiliary():
    modes = {
        0: _normal_hypothesis_mode(0, 0, "body", "q", 4, 1),
        1: _arithmetic_hypothesis_mode(1, 3, "+"),
        2: _arithmetic_hypothesis_mode(2, 3, "*"),
        3: _comparison_hypothesis_mode(3, "<"),
    }
    clause = ReifiedClause(
        (),
        (
            ReifiedLiteral("body", 0, 0, (0, 1, 2, 3)),
            ReifiedLiteral("body", 1, 1, (0, 1, 4)),
            ReifiedLiteral("body", 2, 2, (2, 3, 4)),
            ReifiedLiteral("body", 3, 3, (4, 0)),
        ),
    )

    canonical = canonical_arithmetic_clause(clause, modes, 5)

    assert canonical is not None
    rendered = canonical.render(modes)
    assert "(V0+V1)-(V2*V3)=0" in rendered
    assert "(V0+V1)-V0<0" in rendered


def test_arithmetic_system_eliminates_repeated_auxiliary_coefficients():
    modes = {
        0: _normal_hypothesis_mode(0, 0, "body", "q", 2, 1),
        1: _arithmetic_hypothesis_mode(1, 3, "+", 2),
    }
    clause = ReifiedClause(
        (),
        (
            ReifiedLiteral("body", 0, 0, (0, 1)),
            ReifiedLiteral("body", 1, 1, (0, 0, 2)),
            ReifiedLiteral("body", 2, 1, (2, 2, 1)),
        ),
    )

    canonical = canonical_arithmetic_clause(clause, modes, 3)

    assert canonical is not None
    assert canonical.render(modes) == ":- q(V0,V1),4*V0-V1=0."


def test_arithmetic_system_preserves_independent_rows_in_one_component():
    modes = {
        0: _normal_hypothesis_mode(0, 0, "body", "q", 3, 1),
        1: _arithmetic_hypothesis_mode(1, 3, "+", 2),
    }
    clause = ReifiedClause(
        (),
        (
            ReifiedLiteral("body", 0, 0, (0, 1, 2)),
            ReifiedLiteral("body", 1, 1, (0, 1, 2)),
            ReifiedLiteral("body", 2, 1, (0, 2, 1)),
        ),
    )

    canonical = canonical_arithmetic_clause(clause, modes, 3)

    assert canonical is not None
    assert len(canonical.systems) == 1
    assert len(canonical.systems[0].relations) == 2


@pytest.mark.parametrize(("operator", "rendered"), [("/", "V0/V1-V2=0"), ("\\", "V0\\V1-V2=0")])
def test_arithmetic_system_carries_nonzero_domain_guards(operator, rendered):
    modes = {
        0: _normal_hypothesis_mode(0, 0, "body", "q", 3, 1),
        1: _arithmetic_hypothesis_mode(1, 3, operator),
    }
    clause = ReifiedClause(
        (),
        (
            ReifiedLiteral("body", 0, 0, (0, 1, 2)),
            ReifiedLiteral("body", 1, 1, (0, 1, 2)),
        ),
    )

    canonical = canonical_arithmetic_clause(clause, modes, 3)

    assert canonical is not None
    assert canonical.render(modes) == f":- q(V0,V1,V2),{rendered},V1!=0."


def test_arithmetic_system_deduplicates_shared_divisor_guards():
    divisor = ArithmeticExpression.var(1)
    system = ArithmeticSystem(
        (
            ExpressionConstraint(
                ArithmeticExpression(
                    "/", (ArithmeticExpression.var(0), divisor)
                ),
                "eq",
                2,
                guards=(divisor,),
            ),
            ExpressionConstraint(
                ArithmeticExpression(
                    "\\", (ArithmeticExpression.var(3), divisor)
                ),
                "eq",
                4,
                guards=(divisor,),
            ),
        )
    )

    assert len(system.render()) == 3
    assert system.render() == ("V0/V1-V2=0", "V1!=0", "V3\\V1-V4=0")


def test_arithmetic_system_renders_one_guard_per_canonical_expression():
    x, y, z = (
        ArithmeticExpression.var(index) for index in range(3)
    )
    left_nested = ArithmeticExpression(
        "*", (ArithmeticExpression("*", (x, y)), z)
    )
    right_nested = ArithmeticExpression(
        "*", (x, ArithmeticExpression("*", (y, z)))
    )
    system = ArithmeticSystem(
        (
            ExpressionConstraint(x, "eq", 3, guards=(left_nested,)),
            ExpressionConstraint(y, "eq", 4, guards=(right_nested,)),
        )
    )

    assert left_nested.key == right_nested.key
    assert len(system.render()) == 3
    assert system.render() == (
        "V0-V3=0",
        "(V0*V1)*V2!=0",
        "V1-V4=0",
    )


def test_expression_guard_order_is_not_semantic():
    left = ArithmeticExpression.var(0)
    right = ArithmeticExpression.var(1)
    forward = ExpressionConstraint(left, "eq", 2, guards=(left, right))
    reverse = ExpressionConstraint(left, "eq", 2, guards=(right, left))

    assert forward.key == reverse.key
    assert forward.rendered_guards == reverse.rendered_guards


def test_arithmetic_expression_parenthesizes_composite_abs_operands():
    left = ArithmeticExpression(
        "+", (ArithmeticExpression.var(0), ArithmeticExpression.var(1))
    )
    right = ArithmeticExpression(
        "+", (ArithmeticExpression.var(2), ArithmeticExpression.var(3))
    )

    assert ArithmeticExpression("abs", (left, right)).render() == (
        "|(V0+V1)-(V2+V3)|"
    )


def test_division_guard_does_not_consume_another_body_slot():
    program = Program(
        ["q(1,2,3)."],
        [],
        [],
        [],
        [_mode(1, "q", 3, positive=True)],
        [],
        [],
        [OperatorDeclaration(1, "div")],
        max_body_literals=None,
    )

    generator = HypothesisSpaceGenerator(program, Arguments())

    assert generator.body_slots == 2
    guarded = [
        entry
        for entry in generator.generate().entries
        if "/" in entry.text and "!=0" in entry.text
    ]
    assert guarded
    assert all(entry.body_literals <= 2 for entry in guarded)


def test_symbolic_disequality_is_not_rewritten_as_subtraction():
    program = Program(
        ["p(a).", "p(b)."],
        [],
        [],
        [],
        [_mode(2, "p", 1, positive=True, type_name="term")],
        [],
        [OperatorDeclaration(1, "neq")],
    )

    clauses = _generate(program, 3, 2).clauses

    assert ":- p(V0),p(V1),V0!=V1." in clauses
    assert not any("V0-V1!=0" in clause for clause in clauses)


def test_mixed_numeric_system_keeps_cross_type_disequality_symbolic():
    program = Program(
        ["p(a).", "p(b).", "n(1).", "n(2)."],
        [],
        [],
        [],
        [
            _mode(1, "p", 1, positive=True, type_name="person"),
            _mode(2, "n", 1, positive=True),
        ],
        [],
        [OperatorDeclaration(1, "lt"), OperatorDeclaration(1, "neq")],
    )

    clauses = _generate(program, 5, 3).clauses

    target = ":- p(V0),n(V1),n(V2),V0!=V1,V1-V2<0."
    assert target in clauses
    assert not any(
        "p(V0),n(V1),n(V2)" in clause and "V0-V1!=0" in clause
        for clause in clauses
    )


def test_canonicalization_prevents_reversed_add_operands_by_default():
    program_without_zero = Program(
        ["#const n = 2.", "number(1..n).", "q(1,1)."],
        [],
        [],
        [],
        [_mode(1, "q", 2, positive=True)],
        [],
        [],
        [OperatorDeclaration(1, "add")],
    )
    clauses = _generate(program_without_zero, 4, 3).clauses

    assert clauses
    assert not any(
        left > right
        for clause in clauses
        for left, right in re.findall(r"V(\d+)\+V(\d+)=", clause)
    )


def test_canonical_additive_bias_drops_subtraction_zero_equations():
    program_without_zero = Program(
        ["#const n = 2.", "number(1..n).", "q(1,1)."],
        [],
        [],
        [],
        [_mode(1, "q", 2, positive=True)],
        [],
        [],
        [OperatorDeclaration(1, "sub")],
    )
    program_with_zero = Program(
        ["number(0..2).", "q(0,0)."],
        [],
        [],
        [],
        [_mode(1, "q", 2, positive=True)],
        [],
        [],
        [OperatorDeclaration(1, "sub")],
    )
    without_zero = _generate(program_without_zero, 4, 3).clauses
    with_zero = _generate(program_with_zero, 4, 3).clauses

    assert all("=0" in clause for clause in [*without_zero, *with_zero] if "+" in clause)
    assert not any("V0-V0" in clause for clause in [*without_zero, *with_zero])
    assert any("=0" in clause for clause in without_zero)
    assert any("=0" in clause for clause in with_zero)


def test_domain_arithmetic_prune_propagates_zero_and_positive_values():
    program = Program(
        ["#const n = 2.", "number(1..n).", "q(1,1)."],
        [],
        [],
        [],
        [_mode(1, "q", 2, positive=True)],
        [],
        [OperatorDeclaration(1, "lt")],
        [OperatorDeclaration(1, "add"), OperatorDeclaration(1, "sub")],
    )
    clauses = _generate(program, 4, 3).clauses

    assert clauses
    assert ":- q(V0,V0),V1<V0,V0+V0=V1." not in clauses
    assert ":- q(V0,V1),V1<V0,V1+V1=V0." not in clauses


def test_closed_world_properties_prune_symmetric_predicate_orientation():
    program = Program(
        ["edge(1,2).", "edge(2,1)."],
        [],
        [],
        [_mode(1, "target", 2, head=True)],
        [_mode(1, "edge", 2, positive=True)],
    )
    clauses = _generate(program, 2, 2).clauses

    assert "target(V0,V1) :- edge(V0,V1)." in clauses
    assert "target(V0,V1) :- edge(V1,V0)." not in clauses


def test_closed_world_properties_prune_implied_and_mutex_literals():
    program = Program(
        ["p(1).", "q(1).", "q(2).", "r(2)."],
        [],
        [],
        [],
        [
            _mode(1, "p", 1, positive=True),
            _mode(1, "q", 1, positive=True),
            _mode(1, "q", 1, positive=False),
            _mode(1, "r", 1, positive=True),
        ],
    )
    clauses = _generate(program, 2, 1).clauses

    assert ":- p(V0),q(V0)." not in clauses
    assert ":- p(V0),not q(V0)." not in clauses
    assert ":- p(V0),r(V0)." not in clauses


def test_closed_world_properties_prune_functional_dependency():
    program = Program(
        ["parent(a,b).", "parent(c,d)."],
        [],
        [],
        [],
        [_mode(2, "parent", 2, positive=True)],
    )
    clauses = _generate(program, 2, 3).clauses

    assert ":- parent(V0,V1),parent(V0,V2)." not in clauses


def test_closed_world_properties_prune_projection_implication():
    program = Program(
        ["edge(a,b).", "edge(b,c).", "node(a).", "node(b).", "node(c)."],
        [],
        [],
        [],
        [
            _mode(2, "edge", 2, positive=True),
            _mode(1, "node", 1, positive=True),
            _mode(1, "node", 1, positive=False),
        ],
    )
    clauses = _generate(program, 2, 2).clauses

    assert ":- edge(V0,V1),node(V0)." not in clauses
    assert ":- edge(V0,V1),not node(V0)." not in clauses


def test_closed_world_properties_prune_tuple_mutex_permutation():
    program = Program(
        ["father(a,b).", "mother(c,a)."],
        [],
        [],
        [],
        [
            _mode(2, "father", 2, positive=True),
            _mode(2, "mother", 2, positive=True),
        ],
    )
    fragments = hypothesis_space._closed_world_fragments(program)
    properties = hypothesis_space._closed_world_properties(
        fragments,
        hypothesis_space._predicate_arg_types(program, fragments),
        hypothesis_space._closed_body_predicates(program),
    )
    clauses = _generate(program, 2, 2).clauses

    assert ((("father", 2), ("mother", 2), (1, 0))) in properties.tuple_mutex
    assert ":- father(V0,V1),mother(V1,V0)." not in clauses


def test_count_aggregate_full_local_condition_is_canonical():
    program = Program(
        ["p(a,b).", "p(a,c).", "p(d,b).", "p(d,c)."],
        [],
        [],
        [_mode(1, "out", 1, head=True)],
        [],
        [AggregateDeclaration(1, "count", (("p", 2),), True)],
    )
    clauses = _generate(program, 2, 3).clauses

    assert "out(V2) :- #count{V0,V1:p(V0,V1)}=V2." in clauses
    assert "out(V2) :- #count{V0,V1:p(V1,V0)}=V2." not in clauses


def test_aggregate_condition_keeps_inference_and_inherits_declared_normal_type():
    program = Program(
        ["edge(a,b)."],
        [],
        [],
        [],
        [_mode(1, "edge", 2, type_name="node")],
        aggregate_modes=[AggregateDeclaration(1, "count", (("edge", 2),), True)],
    )

    generator = HypothesisSpaceGenerator(program, Arguments())
    aggregate = next(
        mode
        for mode in generator.modes
        if isinstance(mode.literal, AggregateLiteral)
    )

    assert tuple(binding.type for binding in aggregate.bindings[-3:]) == (
        "node",
        "node",
        "numeric",
    )


def test_sum_aggregate_full_local_non_weight_condition_is_canonical():
    program = Program(
        [
            "p(1,3,5).",
            "p(1,3,6).",
            "p(1,4,5).",
            "p(1,4,6).",
            "p(2,3,5).",
            "p(2,3,6).",
            "p(2,4,5).",
            "p(2,4,6).",
        ],
        [],
        [],
        [_mode(1, "out", 1, head=True)],
        [],
        [AggregateDeclaration(1, "sum", (("p", 3),), True)],
    )
    clauses = _generate(program, 2, 4).clauses

    assert "out(V3) :- #sum{V0,V1,V2:p(V0,V1,V2)}=V3." in clauses
    assert "out(V3) :- #sum{V0,V1,V2:p(V0,V2,V1)}=V3." not in clauses
    assert "out(V3) :- #sum{V0,V1,V2:p(V1,V0,V2)}=V3." in clauses


def test_unbalanced_aggregate_prunes_key_determined_discriminator():
    program = Program(
        [
            "val(1).",
            "val(2).",
            "part(a).",
            "part(b).",
            "1 { p(P,V) : part(P) } 1 :- val(V).",
        ],
        [],
        [],
        [_mode(1, "out", 1, head=True)],
        [],
        [AggregateDeclaration(1, "sum", (("p", 2),), True)],
    )
    clauses = _generate(program, 2, 3).clauses

    assert "out(V2) :- #sum{V0:p(V1,V0)}=V2." in clauses
    assert "out(V2) :- #sum{V0,V1:p(V1,V0)}=V2." not in clauses


def test_balanced_aggregate_keeps_key_determined_discriminator():
    program = Program(
        [
            "val(1).",
            "val(2).",
            "part(a).",
            "part(b).",
            "1 { p(P,V) : part(P) } 1 :- val(V).",
        ],
        [],
        [],
        [_mode(1, "out", 1, head=True)],
        [],
        [AggregateDeclaration(1, "sum", (("p", 2),), False)],
    )
    clauses = _generate(program, 2, 3).clauses

    assert "out(V2) :- #sum{V0,V1:p(V1,V0)}=V2." in clauses


def test_closed_world_properties_prune_composite_functional_dependency():
    program = Program(
        [
            "assign(r1,c1,v1).",
            "assign(r1,c2,v2).",
            "assign(r2,c1,v3).",
        ],
        [],
        [],
        [],
        [_mode(2, "assign", 3, positive=True)],
    )
    clauses = _generate(program, 2, 4).clauses

    assert ":- assign(V0,V1,V2),assign(V0,V1,V3)." not in clauses


def test_closed_world_properties_prune_acyclic_body_cycle():
    program = Program(
        ["edge(a,b).", "edge(b,c).", "edge(c,d)."],
        [],
        [],
        [],
        [_mode(3, "edge", 2, positive=True)],
    )
    clauses = _generate(program, 3, 3).clauses

    assert ":- edge(V0,V1),edge(V1,V2),edge(V2,V0)." not in clauses


def test_closed_world_properties_prune_complement_negative_pair():
    program = Program(
        ["p(a).", "q(b).", "safe(a,a).", "safe(b,b)."],
        [],
        [],
        [],
        [
            _mode(1, "p", 1, positive=False),
            _mode(1, "q", 1, positive=False),
            _mode(1, "safe", 2, positive=True),
        ],
    )
    clauses = _generate(program, 3, 2).clauses

    assert ":- not p(V0),not q(V0),safe(V0,V1)." not in clauses


def test_closed_world_properties_infer_generic_atom_relations():
    properties = hypothesis_space._closed_world_properties(
        [
            "p(a).",
            "q(a).",
            "r(b).",
            "color_red(a).",
            "color_green(b).",
            "color_blue(c).",
            "rel(a,b,c).",
            "rel(d,e,f).",
            "before(a,b).",
            "before(b,c).",
            "before(a,c).",
            "le(a,a).",
            "le(a,b).",
            "le(b,b).",
        ]
    )

    assert (("p", 1), ("q", 1)) in properties.equivalent
    assert (("p", 1), 0, ("rel", 3), 1) in properties.disjoint_projection
    assert tuple(sorted((("color_red", 1), ("color_green", 1), ("color_blue", 1)))) in properties.partitions
    assert ((("rel", 3), (0,))) in properties.keys
    assert ("le", 2) not in properties.antisymmetric
    assert ("before", 2) in properties.strict_order
    assert (("before", 2), 0, 1) not in properties.arg_distinct
    assert ("le", 2) in properties.total_order
    assert ("le", 2) not in properties.reflexive


def test_closed_world_extensions_derive_simple_alias_rules():
    properties = hypothesis_space._closed_world_properties(
        [
            "edge(a,b).",
            "node(a).",
            "node(b).",
            "e(X,Y) :- edge(X,Y).",
            "e(Y,X) :- edge(X,Y).",
        ]
    )

    assert ("e", 2) in properties.symmetric
    assert (("e", 2), 0, 1) in properties.arg_distinct


def test_closed_world_extensions_derive_finite_complement_rules():
    properties = hypothesis_space._closed_world_properties(
        [
            "v(a).",
            "v(b).",
            "e(a,b).",
            "e(b,a).",
            "ne(X,Y) :- not e(X,Y), v(X), v(Y).",
        ]
    )

    assert ("ne", 2) in properties.reflexive
    assert ((("ne", 2), ("v", 1), (0,))) in properties.project_implies
    assert ((("ne", 2), ("v", 1), (1,))) in properties.project_implies


def test_closed_world_extensions_do_not_assume_unknown_negative_empty():
    extensions = hypothesis_space._closed_world_extensions(
        ["v(a).", "p(X) :- not q(X), v(X)."]
    )

    assert ("p", 1) not in extensions


def test_rule_defined_inequality_derives_arg_distinct():
    properties = hypothesis_space._closed_world_properties(
        [
            "same_block(C1,C2) :- block(C1,B), block(C2,B), C1 != C2.",
            "same_row((X1,Y),(X2,Y)) :- cell((X1,Y)), cell((X2,Y)), X1 != X2.",
            "parent_child(P,C) :- parent(P,C).",
        ]
    )

    assert (("same_block", 2), 0, 1) in properties.arg_distinct
    assert (("same_row", 2), 0, 1) in properties.arg_distinct
    assert ("same_block", 2) in properties.symmetric
    assert ("same_row", 2) in properties.symmetric
    assert ("parent_child", 2) not in properties.symmetric


def test_closed_world_properties_emit_new_property_facts():
    fragments = [
        "p(a).",
        "q(a).",
        "r(b).",
        "color_red(a).",
        "color_green(b).",
        "color_blue(c).",
        "rel(a,b,c).",
        "rel(d,e,f).",
        "other(a,b,c).",
        "le(a,a).",
        "le(a,b).",
        "le(b,b).",
    ]
    properties = hypothesis_space._closed_world_properties(
        fragments,
        closed_body_predicates={("rel", 3), ("other", 3)},
    )
    ids = {
        ("p", 1): 0,
        ("q", 1): 1,
        ("r", 1): 2,
        ("color_red", 1): 3,
        ("color_green", 1): 4,
        ("color_blue", 1): 5,
        ("rel", 3): 6,
        ("other", 3): 7,
        ("le", 2): 8,
    }
    facts = set(hypothesis_space._closed_world_property_facts(properties, ids))

    assert "equivalent_pred(0,1)." in facts
    assert "disjoint_arg(0,0,6,1)." in facts
    assert any(fact.startswith("tuple_mutex_pred(6,7,") for fact in facts)
    assert not any(fact.startswith("partition_size(") for fact in facts)
    assert "key_pred(6,0)." in facts
    assert "total_order_pred(8)." in facts
    assert "antisymmetric_pred(8)." not in facts
    assert "reflexive_pred(8)." not in facts


def test_partition_subsumes_pairwise_mutex_facts():
    program = Program(
        ["a(1).", "b(2).", "c(3)."],
        [],
        [],
        [],
        [
            _mode(1, "a", 1, positive=True),
            _mode(1, "b", 1, positive=True),
            _mode(1, "c", 1, positive=True),
        ],
    )
    fragments = hypothesis_space._closed_world_fragments(program)
    arg_types = hypothesis_space._predicate_arg_types(program, fragments)
    properties = hypothesis_space._closed_world_properties(
        fragments,
        arg_types,
        hypothesis_space._closed_body_predicates(program),
    )

    assert properties.partitions == frozenset({(("a", 1), ("b", 1), ("c", 1))})
    assert properties.mutex == frozenset()


def test_functional_set_facts_subsumed_by_smaller_dependencies_are_dropped():
    program = Program(
        ["r(1,a,x,z).", "r(1,a,y,z).", "r(1,b,q,z).", "r(2,a,x,w)."],
        [],
        [],
        [],
        [_mode(1, "r", 4, positive=True)],
    )
    fragments = hypothesis_space._closed_world_fragments(program)
    arg_types = hypothesis_space._predicate_arg_types(program, fragments)
    properties = hypothesis_space._closed_world_properties(
        fragments,
        arg_types,
        hypothesis_space._closed_body_predicates(program),
    )

    assert (("r", 4), 0, 3) in properties.functional
    assert (("r", 4), (0, 1), 3) not in properties.functional_set
    assert (("r", 4), (1, 3), 0) not in properties.functional_set


def test_choice_rules_infer_modelwise_keys():
    properties = hypothesis_space._closed_world_properties(
        [
            "#const n = 5.",
            "number(1..n).",
            "1 { q(X,Y) : number(Y) } 1 :- number(X).",
            "1 { q(X,Y) : number(X) } 1 :- number(Y).",
            "1 { x(R,C,N) : val(N) } 1 :- cell(R), cell(C).",
            "3 { in(X) : v(X) } 3.",
        ]
    )

    assert (("q", 2), (0,)) in properties.keys
    assert (("q", 2), (1,)) in properties.keys
    assert (("x", 3), (0, 1)) in properties.keys
    assert not any(predicate == ("in", 1) for predicate, _args in properties.keys)
    assert ("q", 2) not in properties.universal
    assert ((("q", 2), ("number", 1), (1,))) in properties.project_implies
    assert ((("q", 2), ("number", 1), (0,))) in properties.project_implies
    assert ((("in", 1), ("v", 1), (0,))) in properties.project_implies
    assert ((("in", 1), 3)) in properties.cardinality_upper


def test_closed_world_extensions_expand_numeric_ranges():
    extensions = hypothesis_space._closed_world_extensions(
        ["#const n = 3.", "number(1..n).", "pair(1..2,3..4)."]
    )

    assert extensions[("number", 1)] == {("1",), ("2",), ("3",)}
    assert extensions[("pair", 2)] == {
        ("1", "3"),
        ("1", "4"),
        ("2", "3"),
        ("2", "4"),
    }


def test_rule_defined_square_properties_propagate_choice_key():
    properties = hypothesis_space._closed_world_properties(
        [
            "part(a).",
            "val(1).",
            "val(2).",
            "1 { p(P,V) : val(V) } 1 :- part(P).",
            "sq(P,S) :- p(P,V), S = V*V.",
        ]
    )

    assert ((("sq", 2), (0,))) in properties.keys
    assert ((("sq", 2), 0, 1)) not in properties.functional


def test_cardinality_upper_facts_are_emitted():
    properties = hypothesis_space._closed_world_properties(
        ["val(1).", "val(2).", "1 { in(X) : val(X) } 1."]
    )
    facts = set(
        hypothesis_space._closed_world_property_facts(
            properties,
            {
                ("in", 1): 0,
                ("val", 1): 1,
            },
        )
    )

    assert "cardinality_upper_pred(0,1)." in facts


def test_choice_rule_keys_prune_conflicting_positive_literals():
    program = Program(
        [
            "number(1..5).",
            "1 { q(X,Y) : number(Y) } 1 :- number(X).",
            "1 { q(X,Y) : number(X) } 1 :- number(Y).",
        ],
        [],
        [],
        [],
        [_mode(2, "q", 2, positive=True)],
    )
    clauses = _generate(program, 2, 3).clauses

    assert ":- q(V0,V1),q(V0,V2)." not in clauses
    assert ":- q(V0,V1),q(V2,V1)." not in clauses


def test_choice_projection_prunes_redundant_domain_literal():
    program = Program(
        [
            "number(1..5).",
            "1 { q(X,Y) : number(Y) } 1 :- number(X).",
        ],
        [],
        [],
        [],
        [
            _mode(1, "q", 2, positive=True),
            _mode(1, "number", 1, positive=True),
        ],
    )
    clauses = _generate(program, 2, 2).clauses

    assert ":- q(V0,V1),number(V1)." not in clauses


def test_partition_prunes_all_negative_partition_literals():
    program = Program(
        [
            "red(a).",
            "green(b).",
            "blue(c).",
            "node(a).",
            "node(b).",
            "node(c).",
        ],
        [],
        [],
        [],
        [
            _mode(1, "node", 1, positive=True),
            _mode(1, "red", 1, positive=False),
            _mode(1, "green", 1, positive=False),
            _mode(1, "blue", 1, positive=False),
        ],
    )
    clauses = _generate(program, 4, 1).clauses

    assert ":- node(V0),not red(V0),not green(V0)." in clauses
    assert ":- node(V0),not red(V0),not green(V0),not blue(V0)." not in clauses


def test_mutex_complement_and_partition_prune_positive_negative_redundancy():
    program = Program(
        ["p(a).", "q(b).", "safe(a).", "safe(b)."],
        [],
        [],
        [],
        [
            _mode(1, "safe", 1, positive=True),
            _mode(1, "p", 1, positive=True),
            _mode(1, "p", 1, positive=False),
            _mode(1, "q", 1, positive=True),
            _mode(1, "q", 1, positive=False),
        ],
    )
    clauses = _generate(program, 3, 1).clauses

    assert ":- safe(V0),q(V0),not p(V0)." not in clauses
    assert ":- safe(V0),not p(V0),not q(V0)." not in clauses


def test_inverse_and_transitive_negative_closure_prune():
    inverse = Program(
        ["p(a,b).", "q(b,a)."],
        [],
        [],
        [],
        [
            _mode(1, "p", 2, positive=True),
            _mode(1, "q", 2, positive=False),
        ],
    )
    transitive = Program(
        ["p(a,b).", "p(b,c).", "p(a,c)."],
        [],
        [],
        [],
        [
            _mode(2, "p", 2, positive=True),
            _mode(1, "p", 2, positive=False),
        ],
    )

    inverse_clauses = _generate(inverse, 2, 2).clauses
    transitive_clauses = _generate(transitive, 3, 3).clauses

    assert ":- p(V0,V1),not q(V1,V0)." not in inverse_clauses
    assert ":- p(V0,V1),p(V1,V2),not p(V0,V2)." not in transitive_clauses


def test_acyclic_negative_back_edge_prune():
    program = Program(
        ["edge(a,b).", "edge(b,c)."],
        [],
        [],
        [],
        [
            _mode(2, "edge", 2, positive=True),
            _mode(1, "edge", 2, positive=False),
        ],
    )
    clauses = _generate(program, 3, 3).clauses

    assert ":- edge(V0,V1),edge(V1,V2),not edge(V2,V0)." not in clauses


def test_universal_empty_and_complement_facts_are_emitted():
    universal_program = Program(
        ["dom(a).", "dom(b).", "p(a).", "p(b)."],
        [],
        [],
        [],
        [
            _mode(1, "dom", 1, positive=True),
            _mode(1, "p", 1, positive=True),
            _mode(1, "missing", 1, positive=True),
        ],
    )
    domain_program = Program(
        ["left(a).", "right(b)."],
        [],
        [],
        [],
        [
            _mode(1, "left", 1, positive=True),
            _mode(1, "right", 1, positive=True),
        ],
    )
    universal_fragments = hypothesis_space._closed_world_fragments(universal_program)
    domain_fragments = hypothesis_space._closed_world_fragments(domain_program)
    universal_arg_types = hypothesis_space._predicate_arg_types(
        universal_program, universal_fragments
    )
    domain_arg_types = hypothesis_space._predicate_arg_types(
        domain_program, domain_fragments
    )
    universal_properties = hypothesis_space._closed_world_properties(
        universal_fragments,
        universal_arg_types,
        hypothesis_space._closed_body_predicates(universal_program),
    )
    domain_properties = hypothesis_space._closed_world_properties(
        domain_fragments,
        domain_arg_types,
        hypothesis_space._closed_body_predicates(domain_program),
    )
    universal_ids = {
        ("dom", 1): 0,
        ("p", 1): 1,
        ("missing", 1): 2,
    }
    domain_ids = {
        ("left", 1): 2,
        ("right", 1): 3,
    }
    facts = set(
        hypothesis_space._closed_world_property_facts(universal_properties, universal_ids)
    ) | set(hypothesis_space._closed_world_property_facts(domain_properties, domain_ids))

    assert "universal_pred(1)." in facts
    assert "empty_pred(2)." in facts
    assert "complement_pred(2,3)." in facts


def test_universal_binary_predicate_derives_reflexive_property():
    rule_dir = Path(hypothesis_space.__file__).with_name("rules")
    rules = (rule_dir / "properties" / "universal.lp").read_text() + """
universal_pred(1).
mode(body,0,1,2,1).
#show reflexive_pred/1.
"""
    ctl = clingo.Control(["--warn=none"])
    ctl.add("base", [], rules)
    ctl.ground([("base", [])])

    with ctl.solve(yield_=True) as handle:
        symbols = {str(symbol) for model in handle for symbol in model.symbols(shown=True)}

    assert "reflexive_pred(1)" in symbols


def test_empty_predicate_prunes_positive_and_negative_literals():
    program = Program(
        ["safe(a)."],
        [],
        [],
        [],
        [
            _mode(1, "safe", 1, positive=True),
            _mode(1, "missing", 1, positive=True),
            _mode(1, "missing", 1, positive=False),
        ],
    )
    clauses = _generate(program, 2, 1).clauses

    assert not any("missing(" in clause for clause in clauses)


def test_functional_negative_redundancy_with_inequality_prunes():
    program = Program(
        ["parent(a,b).", "parent(c,d).", "child(b).", "child(d)."],
        [],
        [],
        [],
        [
            _mode(1, "parent", 2, positive=True),
            _mode(1, "parent", 2, positive=False),
            _mode(1, "child", 1, positive=True),
        ],
        [],
        [OperatorDeclaration(1, "neq")],
    )
    clauses = _generate(program, 4, 3).clauses

    assert not any(
        "parent(V0,V1)" in clause
        and "not parent(V0,V2)" in clause
        and "child(V2)" in clause
        and "V1!=V2" in clause
        for clause in clauses
    )


def test_functional_negative_redundancy_uses_strict_comparison():
    program = Program(
        ["p(1,1).", "p(2,2).", "value(1).", "value(2)."],
        [],
        [],
        [],
        [
            _mode(1, "p", 2, positive=True),
            _mode(1, "p", 2, positive=False),
            _mode(1, "value", 1, positive=True),
        ],
        [],
        [OperatorDeclaration(1, "lt")],
    )
    clauses = _generate(program, 4, 3).clauses

    assert not any(
        "p(V0,V1)" in clause
        and "not p(V0,V2)" in clause
        and "value(V2)" in clause
        and "V1<V2" in clause
        for clause in clauses
    )


def test_cardinality_upper_prunes_pairwise_distinct_positive_tuples():
    program = Program(
        ["value(a).", "value(b).", "1 { in(X) : value(X) } 1."],
        [],
        [],
        [],
        [_mode(2, "in", 1, positive=True)],
        [],
        [OperatorDeclaration(1, "neq")],
    )
    clauses = _generate(program, 3, 2).clauses

    assert ":- in(V0),in(V1),V0!=V1." not in clauses


def test_empty_join_and_total_order_prune_impossible_bodies():
    empty_join = Program(
        ["p(a).", "q(b).", "safe(a).", "safe(b)."],
        [],
        [],
        [],
        [
            _mode(1, "safe", 1, positive=True),
            _mode(1, "p", 1, positive=True),
            _mode(1, "q", 1, positive=True),
        ],
    )
    order = Program(
        ["le(a,a).", "le(a,b).", "le(b,b).", "pair(a,b)."],
        [],
        [],
        [],
        [
            _mode(1, "pair", 2, positive=True),
            _mode(2, "le", 2, positive=False),
        ],
    )

    empty_clauses = _generate(empty_join, 3, 1).clauses
    order_clauses = _generate(order, 3, 2).clauses

    assert ":- safe(V0),p(V0),q(V0)." not in empty_clauses
    assert ":- pair(V0,V1),not le(V0,V1),not le(V1,V0)." not in order_clauses


def test_reflexive_key_antisymmetric_and_subsumption_prunes():
    reflexive = Program(
        ["le(a,a).", "le(a,b).", "le(b,b).", "node(a).", "node(b)."],
        [],
        [],
        [],
        [
            _mode(1, "node", 1, positive=True),
            _mode(1, "le", 2, positive=True),
            _mode(1, "le", 2, positive=False),
        ],
    )
    key = Program(
        ["rel(a,b,c).", "rel(d,e,f)."],
        [],
        [],
        [],
        [_mode(2, "rel", 3, positive=True)],
    )
    subsumption = Program(
        ["p(a,a).", "p(a,b)."],
        [],
        [],
        [],
        [_mode(2, "p", 2, positive=True)],
    )

    reflexive_clauses = _generate(reflexive, 3, 2).clauses
    key_clauses = _generate(key, 2, 5).clauses
    subsumption_clauses = _generate(subsumption, 2, 2).clauses

    assert ":- node(V0),le(V0,V0)." not in reflexive_clauses
    assert ":- node(V0),not le(V0,V0)." not in reflexive_clauses
    assert ":- le(V0,V1),le(V1,V0)." not in reflexive_clauses
    assert ":- rel(V0,V1,V2),rel(V0,V3,V4)." not in key_clauses
    assert ":- p(V0,V1),p(V0,V0)." not in subsumption_clauses


def test_equivalent_head_body_redundancy_is_pruned():
    program = Program(
        ["p(a).", "q(a)."],
        [],
        [],
        [_mode(1, "p", 1, head=True)],
        [_mode(1, "q", 1, positive=True)],
    )
    clauses = _generate(program, 2, 1).clauses

    assert "p(V0) :- q(V0)." not in clauses


def test_closed_world_properties_apply_to_aggregate_condition_atoms():
    program = Program(
        ["edge(a,b).", "edge(b,a)."],
        [],
        [],
        [_mode(1, "target", 1, head=True)],
        [],
        [AggregateDeclaration(1, "count", (("edge", 2),), True)],
    )
    clauses = _generate(program, 2, 4).clauses

    for clause in clauses:
        for left, right in re.findall(r"edge\(V(\d+),V(\d+)\)", clause):
            assert int(left) <= int(right)


def test_mul_and_abs_operands_are_canonicalized():
    program = Program(
        ["q(1,2)."],
        [],
        [],
        [],
        [_mode(1, "q", 2, positive=True)],
        [],
        [],
        [OperatorDeclaration(1, "mul"), OperatorDeclaration(1, "abs")],
    )
    clauses = _generate(program, 3, 3).clauses

    assert not any(
        left > right
        for clause in clauses
        for left, right in re.findall(r"V(\d+)\*V(\d+)=", clause)
    )
    assert not any(
        left > right
        for clause in clauses
        for left, right in re.findall(r"\|V(\d+)-V(\d+)\|=", clause)
    )


def test_reader_parses_directives_without_regex_space_loss(tmp_path):
    task = tmp_path / "task.txt"
    task.write_text(
        "\n".join(
            [
                "",
                "% comment",
                "edge(1,2).",
                "#pos({ red(1), blue(f(2,3)) }, { green(1) }, { ctx((1,2)) }).",
                "#neg({ bad(1) }, {}).",
                "#modeh(1, red(var(numeric,any))).",
                "#modeb(2, edge(var(numeric,any),var(numeric,any))).",
                "#modeagg(1, sum(edge/2), unbalanced).",
                "#modecmp(2, neq).",
                "#modearith(1, add).",
            ]
        ),
        encoding="utf-8",
    )

    program = read_program(str(task))

    assert program.background == ["edge(1,2)."]
    assert program.positive_examples[0].included == "red(1), blue(f(2,3))"
    assert program.positive_examples[0].excluded == "green(1)"
    assert program.positive_examples[0].context == "ctx((1,2))"
    assert program.negative_examples[0].included == "bad(1)"
    assert program.language_bias_head[0].template.elements[0].name == "red"
    assert program.language_bias_body[0].literal.atom.name == "edge"
    assert program.aggregate_modes == [
        AggregateDeclaration(1, "sum", (("edge", 2),), True)
    ]
    assert program.comparison_modes == [OperatorDeclaration(2, "neq")]
    assert program.arithmetic_modes == [OperatorDeclaration(1, "add")]


def test_reader_parses_complete_head_forms_and_variable_labels(tmp_path):
    task = tmp_path / "heads.txt"
    task.write_text(
        "\n".join(
            (
                "#modeh(1,p(var(node,input,x))).",
                "#modeh(1,p(var(node,input,x));q(var(node,input,x))).",
                "#modeh(1,{p(var(node,input,x));q(var(node,input,y))}).",
                "#modeh(1,1 {p(var(node,input,x));q(var(node,input,x))} 1).",
                "#modeh(1,p(var(node,input,z));q(var(node,output,z))).",
            )
        ),
        encoding="utf-8",
    )

    program = read_program(str(task))

    assert [head.template.kind for head in program.language_bias_head] == [
        "normal",
        "disjunction",
        "choice",
        "choice",
        "disjunction",
    ]
    assert [head.width for head in program.language_bias_head] == [1, 2, 2, 2, 2]
    assert program.language_bias_head[3].template.lower == 1
    assert program.language_bias_head[3].template.upper == 1
    assert program.language_bias_head[1].template.elements[1].terms[0].label == "x"
    assert tuple(
        atom.terms[0].direction
        for atom in program.language_bias_head[4].template.elements
    ) == ("input", "output")


def test_complete_head_forms_are_alternatives_not_implicit_combinations(tmp_path):
    task = tmp_path / "alternatives.txt"
    task.write_text(
        "\n".join(
            (
                "node(1).",
                "#maxhl(2).",
                "#maxbl(1).",
                "#maxv(1).",
                "#modeh(1,p(var(node,input))).",
                "#modeh(1,q(var(node,input))).",
                "#modeb(1,node(var(node,output))).",
            )
        ),
        encoding="utf-8",
    )

    clauses = set(
        HypothesisSpaceGenerator(read_program(str(task)), Arguments())
        .generate()
        .clauses
    )

    assert "p(V0) :- node(V0)." in clauses
    assert "q(V0) :- node(V0)." in clauses
    assert not any("p(V0);q(V0)" in clause for clause in clauses)


@pytest.mark.parametrize(
    ("head", "expected"),
    [
        (
            "p(var(node,input,x));q(var(node,input,x))",
            "p(V0);q(V0) :- node(V0).",
        ),
        (
            "{p(var(node,input,x));q(var(node,input,x))}",
            "{p(V0);q(V0)} :- node(V0).",
        ),
        (
            "1 {p(var(node,input,x));q(var(node,input,x))} 1",
            "1{p(V0);q(V0)}1 :- node(V0).",
        ),
        (
            "-p(var(node,input,x));q(var(node,input,x))",
            "-p(V0);q(V0) :- node(V0).",
        ),
        (
            "{-p(var(node,input,x));q(var(node,input,x))}",
            "{-p(V0);q(V0)} :- node(V0).",
        ),
    ],
)
def test_complete_heads_render_as_declared(tmp_path, head, expected):
    task = tmp_path / "complete.txt"
    task.write_text(
        "\n".join(
            (
                "node(1).",
                "#maxhl(2).",
                "#maxbl(1).",
                "#maxv(1).",
                f"#modeh(1,{head}).",
                "#modeb(1,node(var(node,output))).",
            )
        ),
        encoding="utf-8",
    )

    clauses = HypothesisSpaceGenerator(
        read_program(str(task)), Arguments()
    ).generate().clauses

    assert expected in clauses


def test_strong_negation_is_rendered_in_heads_and_default_negated_bodies(tmp_path):
    task = tmp_path / "strong-generation.txt"
    task.write_text(
        "\n".join(
            (
                "node(a).",
                "node(b).",
                "-blocked(a).",
                "#maxv(1).",
                "#maxbl(2).",
                "#maxhl(1).",
                "#modeh(1,-target(var(node,input))).",
                "#modeb(1,node(var(node,output))).",
                "#modeb(1,not -blocked(var(node,input))).",
            )
        ),
        encoding="utf-8",
    )

    clauses = set(
        HypothesisSpaceGenerator(read_program(str(task)), Arguments())
        .generate()
        .clauses
    )

    assert "-target(V0) :- node(V0),not -blocked(V0)." in clauses


def test_strongly_negated_hypothesis_covers_strongly_negated_example():
    coverage = NormalCoverageSolver(
        ["node(a)."],
        ["0", "--enum-mode=brave"],
        [Example(("-target(a)", ""), True)],
        [Example(("target(a)", ""), False)],
    ).extract_fixed_coverage(("-target(X) :- node(X).",))

    assert coverage.pos_mask == 1
    assert coverage.neg_mask == 0


def test_recursion_uses_signed_predicate_identity(tmp_path):
    matching = tmp_path / "matching.txt"
    matching.write_text(
        "#modeh(1,-p(var(node,input))).\n"
        "#modeb(1,-p(var(node,input))).\n",
        encoding="utf-8",
    )
    opposite = tmp_path / "opposite.txt"
    opposite.write_text(
        "#modeh(1,p(var(node,input))).\n"
        "#modeb(1,-p(var(node,input))).\n",
        encoding="utf-8",
    )

    assert HypothesisSpaceGenerator(
        read_program(str(matching)), Arguments()
    ).capabilities.allow_recursion
    assert not HypothesisSpaceGenerator(
        read_program(str(opposite)), Arguments()
    ).capabilities.allow_recursion


def test_positive_strong_complements_are_pruned_from_same_body_tuple(tmp_path):
    task = tmp_path / "strong-coherence.txt"
    task.write_text(
        "\n".join(
            (
                "node(a).",
                "node(b).",
                "p(a).",
                "-p(b).",
                "#maxv(1).",
                "#maxbl(3).",
                "#maxhl(1).",
                "#modeh(1,target(var(node,input))).",
                "#modeb(1,node(var(node,output))).",
                "#modeb(1,p(var(node,input))).",
                "#modeb(1,-p(var(node,input))).",
            )
        ),
        encoding="utf-8",
    )

    generator = HypothesisSpaceGenerator(read_program(str(task)), Arguments())
    clauses = generator.generate().clauses

    assert any(re.search(r"(?<!-)p\(V0\)", clause) for clause in clauses)
    assert any("-p(V0)" in clause for clause in clauses)
    assert not any(
        re.search(r"(?<!-)p\(V0\)", clause) and "-p(V0)" in clause
        for clause in clauses
    )


def test_structured_shapes_keep_distinct_functors_and_prune_exact_complements(
    tmp_path,
):
    task = tmp_path / "structured-shapes.txt"
    task.write_text(
        "\n".join(
            (
                "node(a).",
                "p(f(a)).",
                "p(g(a)).",
                "-p(g(a)).",
                "#maxv(1).",
                "#maxbl(3).",
                "#maxhl(1).",
                "#modeh(1,target(var(node,input))).",
                "#modeb(1,node(var(node,output))).",
                "#modeb(1,p(f(var(node,input)))).",
                "#modeb(1,p(g(var(node,input)))).",
                "#modeb(1,-p(f(var(node,input)))).",
                "#modeb(1,-p(g(var(node,input)))).",
            )
        ),
        encoding="utf-8",
    )

    clauses = HypothesisSpaceGenerator(
        read_program(str(task)), Arguments()
    ).generate().clauses

    assert any(
        "p(f(V0))" in clause and "-p(g(V0))" in clause
        for clause in clauses
    )
    assert any(
        "p(f(V0))" in clause and "p(g(V0))" in clause
        for clause in clauses
    )
    assert not any(
        re.search(r"(?<!-)p\(f\(V0\)\)", clause) and "-p(f(V0))" in clause
        for clause in clauses
    )


def test_two_default_negated_strong_complements_remain_legal(tmp_path):
    task = tmp_path / "default-strong-complements.txt"
    task.write_text(
        "\n".join(
            (
                "node(a).",
                "#maxv(1).",
                "#maxbl(3).",
                "#maxhl(1).",
                "#modeh(1,p(var(node,input))).",
                "#modeh(1,-p(var(node,input))).",
                "#modeb(1,node(var(node,output))).",
                "#modeb(1,not p(var(node,input))).",
                "#modeb(1,not -p(var(node,input))).",
            )
        ),
        encoding="utf-8",
    )

    clauses = HypothesisSpaceGenerator(
        read_program(str(task)), Arguments()
    ).generate().clauses

    assert ":- node(V0),not p(V0),not -p(V0)." in clauses


def test_strong_negation_is_preserved_in_aggregate_conditions(tmp_path):
    task = tmp_path / "strong-aggregate.txt"
    task.write_text(
        "-value(a).\n#modeagg(1,count(-value/1),balanced).\n",
        encoding="utf-8",
    )

    generator = HypothesisSpaceGenerator(read_program(str(task)), Arguments())
    aggregates = [
        mode.literal
        for mode in generator.modes
        if isinstance(mode.literal, AggregateLiteral)
    ]

    assert aggregates
    assert all(
        aggregate.conditions[0].signature == ("-value", 1)
        for aggregate in aggregates
    )


def test_distinct_head_labels_require_distinct_variables(tmp_path):
    task = tmp_path / "labels.txt"
    task.write_text(
        "\n".join(
            (
                "edge(1,2).",
                "#maxhl(2).",
                "#maxbl(1).",
                "#maxv(2).",
                "#modeh(1,p(var(node,input,x));q(var(node,input,y))).",
                "#modeb(1,edge(var(node,output),var(node,output))).",
            )
        ),
        encoding="utf-8",
    )

    clauses = HypothesisSpaceGenerator(
        read_program(str(task)), Arguments()
    ).generate().clauses

    assert "p(V0);q(V1) :- edge(V0,V1)." in clauses
    assert "p(V0);q(V0) :- edge(V0,V1)." not in clauses


def test_learnable_ground_facts_have_no_empty_rule_body(tmp_path):
    task = tmp_path / "facts.las"
    task.write_text(
        "\n".join(
            (
                "#maxv(1).",
                "#maxbl(1).",
                "#constant(node,a).",
                "#modeh(1,ready(const(node))).",
                "#modeh(1,unsafe(var(node,any))).",
            )
        ),
        encoding="utf-8",
    )

    clauses = HypothesisSpaceGenerator(
        read_program(str(task)), Arguments()
    ).generate().clauses

    assert "ready(a)." in clauses
    assert all(":- ." not in clause for clause in clauses)
    assert all(not clause.startswith("unsafe(") for clause in clauses)


def test_bodyless_complete_heads_keep_their_declared_asp_form(tmp_path):
    task = tmp_path / "bodyless-heads.las"
    task.write_text(
        "\n".join(
            (
                "#maxv(0).",
                "#maxhl(2).",
                "#modeh(1,a;b).",
                "#modeh(1,1 {c;d} 1).",
            )
        ),
        encoding="utf-8",
    )

    clauses = HypothesisSpaceGenerator(
        read_program(str(task)), Arguments()
    ).generate().clauses

    assert "a;b." in clauses
    assert "1{c;d}1." in clauses
    assert ":-." not in clauses


def test_completely_empty_clause_is_not_learnable():
    clauses = HypothesisSpaceGenerator(
        Program([], [], [], [], []), Arguments()
    ).generate().clauses

    assert clauses == ()


def test_maxbl_zero_declares_a_facts_only_rule_space(tmp_path):
    task = tmp_path / "facts-only.las"
    task.write_text(
        "#maxv(0).\n#maxbl(0).\n#modeh(1,ready).\n#modeb(1,source).\n",
        encoding="utf-8",
    )

    clauses = HypothesisSpaceGenerator(
        read_program(str(task)), Arguments()
    ).generate().clauses

    assert clauses == ("ready.",)


def test_positive_head_condition_can_safely_ground_a_bodyless_rule(tmp_path):
    task = tmp_path / "conditional-fact.las"
    task.write_text(
        "\n".join(
            (
                "node(a).",
                "#maxv(1).",
                "#maxbl(1).",
                "#modeh(1,p(var(node,any))).",
                "#modec(1,node(var(node,any))).",
            )
        ),
        encoding="utf-8",
    )

    clauses = HypothesisSpaceGenerator(
        read_program(str(task)), Arguments()
    ).generate().clauses

    assert "p(V0):node(V0)." in clauses


def test_bias_is_multiline_meta_asp_and_disables_implicit_head_identity(tmp_path):
    task = tmp_path / "explicit-bias.las"
    task.write_text(
        """edge(1,2).
#maxhl(2).
#maxbl(1).
#maxv(2).
#modeh(1,p(var(node,input,x));q(var(node,input,x))).
#modeh(1,r(var(node,input,x));s(var(node,input,y))).
#modeb(1,edge(var(node,output),var(node,output))).
#bias("
bias_active.
").
""",
        encoding="utf-8",
    )

    program = read_program(str(task))
    clauses = HypothesisSpaceGenerator(program, Arguments()).generate().clauses

    assert program.bias == ("bias_active.",)
    assert "p(V0);q(V1) :- edge(V0,V1)." in clauses
    assert "r(V0);s(V0) :- edge(V0,V1)." in clauses


def test_bias_meta_rule_can_restore_variable_identity_explicitly(tmp_path):
    task = tmp_path / "identity-metarule.las"
    task.write_text(
        """edge(1,2).
#maxhl(2).
#maxbl(1).
#maxv(2).
#modeh(1,p(var(node,input,x));q(var(node,input,x))).
#modeh(1,r(var(node,input,x));s(var(node,input,y))).
#modeb(1,edge(var(node,output),var(node,output))).
#bias("
bias_same_label_var(F,L,V) :-
    selected_head_form(F),
    head_arg_label(F,M,A,L),
    selected(head,S,M),
    var_at(head,S,A,V).
:- bias_same_label_var(F,L,X), bias_same_label_var(F,L,Y), X != Y.
:- bias_same_label_var(F,L,V), bias_same_label_var(F,R,V), L < R.
").
""",
        encoding="utf-8",
    )

    clauses = HypothesisSpaceGenerator(
        read_program(str(task)), Arguments()
    ).generate().clauses

    assert "p(V0);q(V0) :- edge(V0,V1)." in clauses
    assert "p(V0);q(V1) :- edge(V0,V1)." not in clauses
    assert "r(V0);s(V1) :- edge(V0,V1)." in clauses
    assert "r(V0);s(V0) :- edge(V0,V1)." not in clauses


def test_bias_meta_rule_can_require_a_named_predicate_pattern(tmp_path):
    task = tmp_path / "named-predicate-metarule.las"
    task.write_text(
        '''edge(1).
node(1).
#maxv(1).
#maxbl(1).
#modeh(1,p(var(node,input))).
#modeb(1,edge(var(node,output))).
#modeb(1,node(var(node,output))).
#bias("
bias_uses_edge :-
    selected_atom(body,_,\\"edge\\",1,positive).
:- selected_slot(head,_), not bias_uses_edge.
").
''',
        encoding="utf-8",
    )

    clauses = HypothesisSpaceGenerator(
        read_program(str(task)), Arguments()
    ).generate().clauses

    assert "p(V0) :- edge(V0)." in clauses
    assert "p(V0) :- node(V0)." not in clauses
    assert "p(V0)." not in clauses


def test_reader_rejects_invalid_or_empty_bias(tmp_path):
    for index, declaration in enumerate(("#bias(\"\").", '#bias(\":-\").')):
        task = tmp_path / f"invalid-bias-{index}.las"
        task.write_text(declaration, encoding="utf-8")

        with pytest.raises(ValueError, match="#bias|ASP"):
            read_program(str(task))


def test_bias_cannot_redefine_generator_relations(tmp_path):
    task = tmp_path / "redefined-bias-relation.las"
    task.write_text('#bias("selected(head,0,0).").', encoding="utf-8")

    with pytest.raises(ValueError, match="bias_ namespace"):
        read_program(str(task))


@pytest.mark.parametrize(
    "payload",
    (
        "% comment before the forbidden definition\nselected(head,0,0).",
        "safe_var(0).",
        ":~ selected(body,S,M). [1@1,S,M]",
        "% comment only",
        "#program foo. bias_active.",
    ),
)
def test_bias_rejects_internal_definitions_optimization_and_comments_only(
    tmp_path, payload
):
    task = tmp_path / "invalid-meta-program.las"
    escaped = payload.replace('"', '\\"')
    task.write_text(f'#bias("{escaped}").', encoding="utf-8")

    with pytest.raises(ValueError, match="#bias|bias_ namespace|rules and hard"):
        read_program(str(task))


def test_commented_bias_does_not_enable_explicit_identity(tmp_path):
    task = tmp_path / "commented-bias.las"
    task.write_text('% #bias("enabled.").\n#modeh(1,p).\n', encoding="utf-8")

    assert read_program(str(task)).bias == ()


def test_nested_head_labels_control_flattened_placeholders(tmp_path):
    task = tmp_path / "nested-labels.txt"
    task.write_text(
        "\n".join(
            (
                "edge(1,2).",
                "#maxhl(2).",
                "#maxbl(1).",
                "#maxv(2).",
                "#modeh(1,p(f(var(node,input,x)));q(g(var(node,input,x)))).",
                "#modeb(1,edge(var(node,output),var(node,output))).",
            )
        ),
        encoding="utf-8",
    )

    clauses = HypothesisSpaceGenerator(
        read_program(str(task)), Arguments()
    ).generate().clauses

    assert "p(f(V0));q(g(V0)) :- edge(V0,V1)." in clauses
    assert "p(f(V0));q(g(V1)) :- edge(V0,V1)." not in clauses


@pytest.mark.parametrize(
    "declaration",
    [
        "#modeh(2,p(var(node,input))).",
        "#modeh(1,p(var(node,input,x)):node(var(node,input,x))).",
        "#modeh(1,p(var(node,input,x));q(var(other,input,x))).",
    ],
)
def test_reader_rejects_invalid_complete_head_forms(tmp_path, declaration):
    task = tmp_path / "invalid-head.txt"
    task.write_text(declaration + "\n", encoding="utf-8")

    with pytest.raises(ValueError):
        read_program(str(task))


def test_reader_parses_condition_modes_with_full_atom_syntax(tmp_path):
    task = tmp_path / "condition-mode.las"
    task.write_text(
        "\n".join(
            (
                "#constant(colour,red).",
                "#modec(2,not -blocked(box(var(node,input),const(colour)))).",
            )
        ),
        encoding="utf-8",
    )

    program = read_program(str(task))
    declaration = program.language_bias_condition[0]

    assert declaration.recall == 2
    assert declaration.literal.default_negated
    assert declaration.literal.atom.strong
    assert declaration.literal.atom.terms[0].kind == "function"
    assert program.constants == {"colour": ("red",)}


@pytest.mark.parametrize(
    "declaration",
    (
        "#modeh bad.",
        "#modeb bad.",
        "#modec bad.",
        "#modec(0,node(var(node,input))).",
        "#modec(1,node(var(node,input,label))).",
        "#modec(1,not node(var(node,output))).",
        "#modec(1,node(const(missing))).",
    ),
)
def test_reader_rejects_invalid_condition_modes(tmp_path, declaration):
    task = tmp_path / "invalid-condition-mode.las"
    task.write_text(declaration + "\n", encoding="utf-8")

    with pytest.raises(ValueError):
        read_program(str(task))


def test_condition_modes_generate_head_and_body_conditional_literals(tmp_path):
    task = tmp_path / "conditionals.las"
    task.write_text(
        "\n".join(
            (
                "base(a).",
                "node(a).",
                "#maxv(2).",
                "#maxbl(2).",
                "#maxhl(1).",
                "#modeh(1,target(var(node,input))).",
                "#modeb(1,base(var(node,any))).",
                "#modec(1,node(var(node,any))).",
            )
        ),
        encoding="utf-8",
    )

    clauses = HypothesisSpaceGenerator(
        read_program(str(task)), Arguments()
    ).generate().clauses

    assert "target(V0):node(V0) :- base(V0)." in clauses
    assert "target(V0):node(V1) :- base(V0)." in clauses
    assert "target(V0) :- base(V0):node(V0)." not in clauses


@pytest.mark.parametrize(
    ("head", "expected"),
    (
        (
            "p(var(node,input,x));q(var(node,input,x))",
            "p(V0):node(V1);q(V0) :- base(V0).",
        ),
        (
            "1 {p(var(node,input,x));q(var(node,input,x))} 1",
            "1{p(V0):node(V1);q(V0)}1 :- base(V0).",
        ),
    ),
)
def test_condition_modes_attach_to_disjunction_and_choice_elements(
    tmp_path, head, expected
):
    task = tmp_path / "conditional-head-form.las"
    task.write_text(
        "\n".join(
            (
                "base(a).",
                "node(a).",
                "#maxv(2).",
                "#maxbl(2).",
                "#maxhl(2).",
                f"#modeh(1,{head}).",
                "#modeb(1,base(var(node,any))).",
                "#modec(1,node(var(node,any))).",
            )
        ),
        encoding="utf-8",
    )

    clauses = HypothesisSpaceGenerator(
        read_program(str(task)), Arguments()
    ).generate().clauses

    assert expected in clauses
    control = clingo.Control(["0"])
    control.add("base", [], f"base(a). node(a). {expected}")
    control.ground([("base", [])])


def test_positive_body_conclusion_and_conditions_make_local_variables_safe(tmp_path):
    task = tmp_path / "local-conditionals.las"
    task.write_text(
        "\n".join(
            (
                "p(a).",
                "q(a).",
                "#maxv(2).",
                "#maxbl(2).",
                "#modeh(1,target).",
                "#modeb(1,p(var(node,any))).",
                "#modec(1,q(var(node,any))).",
            )
        ),
        encoding="utf-8",
    )

    clauses = HypothesisSpaceGenerator(
        read_program(str(task)), Arguments()
    ).generate().clauses

    assert "target :- p(V0):q(V0)." in clauses
    assert "target :- p(V0):q(V1)." in clauses


def test_body_conditional_uses_unambiguous_semicolon_separators(tmp_path):
    task = tmp_path / "body-separator.las"
    task.write_text(
        "\n".join(
            (
                "base(a).",
                "p(a).",
                "q(a).",
                "#maxv(2).",
                "#maxbl(3).",
                "#modeh(1,target).",
                "#modeb(1,base(var(node,any))).",
                "#modeb(1,p(var(node,any))).",
                "#modec(1,q(var(node,any))).",
            )
        ),
        encoding="utf-8",
    )

    clauses = HypothesisSpaceGenerator(
        read_program(str(task)), Arguments()
    ).generate().clauses
    clause = "target :- base(V0);p(V1):q(V1)."

    assert clause in clauses
    control = clingo.Control(["0"])
    control.add("base", [], f"base(a). p(a). q(a). {clause}")
    control.ground([("base", [])])


def test_conditional_local_names_can_be_reused_between_scopes(tmp_path):
    task = tmp_path / "local-scopes.las"
    task.write_text(
        "\n".join(
            (
                "p(a).",
                "q(a).",
                "r(b).",
                "s(b).",
                "#maxv(2).",
                "#maxbl(4).",
                "#modeh(1,target).",
                "#modeb(1,p(var(left,any))).",
                "#modeb(1,r(var(right,any))).",
                "#modec(1,q(var(left,any))).",
                "#modec(1,s(var(right,any))).",
            )
        ),
        encoding="utf-8",
    )

    clauses = HypothesisSpaceGenerator(
        read_program(str(task)), Arguments()
    ).generate().clauses

    assert "target :- p(V0):q(V0);r(V0):s(V0)." in clauses


def test_conditional_global_output_requires_an_external_producer(tmp_path):
    def clauses(direction):
        task = tmp_path / f"conditional-output-{direction}.las"
        task.write_text(
            "\n".join(
                (
                    "source(a).",
                    "node(a).",
                    "#maxv(1).",
                    "#maxbl(2).",
                    "#modeh(1,target(var(node,output))).",
                    f"#modeb(1,source(var(node,{direction}))).",
                    "#modec(1,node(var(node,any))).",
                )
            ),
            encoding="utf-8",
        )
        return HypothesisSpaceGenerator(
            read_program(str(task)), Arguments()
        ).generate().clauses

    clause = "target(V0):node(V0) :- source(V0)."

    assert clause in clauses("output")
    assert clause not in clauses("any")


def test_condition_recall_and_body_budget_cover_all_attachments(tmp_path):
    task = tmp_path / "condition-recall.las"
    task.write_text(
        "\n".join(
            (
                "base(a).",
                "node(a).",
                "#maxv(1).",
                "#maxbl(3).",
                "#modeh(1,target(var(node,input))).",
                "#modeb(2,base(var(node,any))).",
                "#modec(1,node(var(node,any))).",
            )
        ),
        encoding="utf-8",
    )

    clauses = HypothesisSpaceGenerator(
        read_program(str(task)), Arguments()
    ).generate().clauses

    assert clauses
    assert all(clause.count(":node(") <= 1 for clause in clauses)
    assert all(
        clause.count("base(") + clause.count(":node(") <= 3
        for clause in clauses
    )


def test_multiple_conditions_preserve_negation_terms_and_dependencies(tmp_path):
    task = tmp_path / "condition-syntax.las"
    task.write_text(
        "\n".join(
            (
                "base(a).",
                "node(box(a,red)).",
                "blocked(a).",
                "#constant(colour,red).",
                "#maxv(2).",
                "#maxbl(3).",
                "#modeh(1,target(var(node,input))).",
                "#modeb(1,base(var(node,any))).",
                "#modec(1,node(box(var(node,any),const(colour)))).",
                "#modec(1,not blocked(var(node,input))).",
            )
        ),
        encoding="utf-8",
    )

    space = HypothesisSpaceGenerator(read_program(str(task)), Arguments()).generate()
    clause = "target(V0):node(box(V0,red)),not blocked(V0) :- base(V0)."
    entry = next(entry for entry in space.entries if entry.text == clause)

    assert entry.heads == frozenset({("target", 1)})
    assert entry.deps == frozenset(
        {("base", 1), ("node", 1), ("blocked", 1)}
    )
    assert entry.body_literals == 3


def test_negative_body_conclusion_can_be_grounded_by_its_condition(tmp_path):
    task = tmp_path / "negative-conclusion.las"
    task.write_text(
        "\n".join(
            (
                "p(a).",
                "q(a).",
                "#maxv(1).",
                "#maxbl(2).",
                "#modeh(1,target).",
                "#modeb(1,not p(var(node,input))).",
                "#modec(1,q(var(node,any))).",
            )
        ),
        encoding="utf-8",
    )

    clauses = HypothesisSpaceGenerator(
        read_program(str(task)), Arguments()
    ).generate().clauses

    assert "target :- not p(V0):q(V0)." in clauses
    assert "target :- not p(V0):q(V1)." not in clauses


def test_unbounded_body_requires_finite_condition_recalls(tmp_path):
    task = tmp_path / "unbounded-conditions.las"
    task.write_text(
        "\n".join(
            (
                "#maxbl(*).",
                "#modeh(1,target).",
                "#modeb(1,p).",
                "#modec(*,q).",
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="finite recalls"):
        HypothesisSpaceGenerator(read_program(str(task)), Arguments())


def test_conditional_literal_ir_renders_variables_in_syntax_order():
    variable = TermTemplate.variable("node", "any")
    literal = ConditionalLiteral(
        AtomLiteral(AtomTemplate("p", (variable,))),
        (
            AtomLiteral(AtomTemplate("q", (variable,))),
            AtomLiteral(AtomTemplate("r", (variable,)), True),
        ),
        (0, 1),
    )

    assert render_literal(literal, (2, 2, 5)) == "p(V2):q(V2),not r(V5)"


def test_reader_rejects_strongly_negated_invention(tmp_path):
    task = tmp_path / "strong-invention.txt"
    task.write_text(
        "#invent(1,-helper(var(person,input))).\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="cannot be strongly negated"):
        read_program(str(task))


def test_complete_head_width_must_fit_maxhl(tmp_path):
    task = tmp_path / "head-width.txt"
    task.write_text(
        "#maxhl(1).\n#modeh(1,p;q).\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="#maxhl"):
        HypothesisSpaceGenerator(read_program(str(task)), Arguments())


def test_language_bias_is_not_generated_when_bias_is_missing():
    program = Program(
        ["a :- b, not c."],
        [],
        [],
        [],
        [],
    )

    assert program.language_bias_head == []
    assert program.language_bias_body == []


def test_language_bias_keeps_explicit_head_without_generating_body():
    program = Program(
        ["coin(c1)."],
        [Example(("heads(c1)", "tails(c1)"), True)],
        [],
        [
            _mode(1, "heads", 1, head=True),
            _mode(1, "tails", 1, head=True),
        ],
        [],
    )

    assert {
        atom.signature
        for head in program.language_bias_head
        for atom in head.template.elements
    } == {
        ("heads", 1),
        ("tails", 1),
    }
    assert program.language_bias_body == []


def test_language_bias_keeps_explicit_body_without_generating_head():
    program = Program(
        ["target(1)."],
        [],
        [],
        [],
        [_mode(1, "target", 1, positive=True)],
    )

    assert program.language_bias_head == []
    assert {
        (
            *mode.literal.atom.signature,
            not mode.literal.default_negated,
        )
        for mode in program.language_bias_body
    } == {("target", 1, True)}


def test_positive_body_singleton_is_available_as_existential_projection():
    program = Program(
        ["edge(1,2)."],
        [],
        [],
        [_mode(1, "target", 1, head=True)],
        [_mode(1, "edge", 2, positive=True)],
    )

    clauses = _generate(program, 2, 2).clauses

    assert "target(V0) :- edge(V0,V1)." in clauses


def test_negative_body_singleton_remains_rejected():
    program = Program(
        ["node(1).", "edge(1,2)."],
        [],
        [],
        [_mode(1, "target", 1, head=True)],
        [
            _mode(1, "node", 1, positive=True),
            _mode(1, "edge", 2, positive=False),
        ],
    )

    clauses = _generate(program, 3, 2).clauses

    assert "target(V0) :- node(V0),not edge(V0,V1)." not in clauses


def test_ast_atom_extraction_handles_choice_rules():
    atoms = {
        (name, arguments)
        for name, arguments, _negative in fragment_atoms(
            "1 { p(P,I) : partition(P) } 1 :- number(I)."
        )
    }

    assert ("p", ("P", "I")) in atoms
    assert ("partition", ("P",)) in atoms
    assert ("number", ("I",)) in atoms


def _benchmark_clauses(name: str) -> set[str]:
    args = copy.deepcopy(CASES[name])
    return set(HypothesisSpaceGenerator(read_program(args.filename), args).generate().clauses)


def test_bundled_benchmarks_use_explicit_non_any_directions():
    for arguments in CASES.values():
        program = read_program(arguments.filename)
        head_modes = [
            atom
            for head in program.language_bias_head
            for atom in head.template.elements
        ]
        body_atoms = [mode.literal.atom for mode in program.language_bias_body]
        for atom in [*head_modes, *body_atoms]:
            assert all(
                argument.kind == "constant" or argument.direction != "any"
                for argument in atom.terms
            ), arguments.filename


def test_constant_colour_benchmark_contains_both_concrete_mode_expansions():
    clauses = _benchmark_clauses("constant_colour")

    assert clauses == {
        "target(V0) :- colour(V0,green).",
        "target(V0) :- colour(V0,red).",
    }


def test_equal_ground_values_do_not_merge_distinct_declared_types():
    program = Program(
        ["left(1).", "right(1)."],
        [],
        [],
        [],
        [
            _mode(1, "left", 1, type_name="node"),
            _mode(1, "right", 1, type_name="numeric"),
        ],
    )

    types = hypothesis_space._predicate_arg_types(
        program, hypothesis_space._closed_world_fragments(program)
    )

    assert types[("left", 1, 0)] == "node"
    assert types[("right", 1, 0)] == "numeric"


def test_coloring_hypothesis_space_contains_target_rules():
    clauses = _benchmark_clauses("coloring")

    assert len(clauses) == 59
    assert "red(V0);green(V0);blue(V0) :- node(V0)." in clauses
    assert ":- e(V0,V1),red(V0),red(V1)." in clauses
    assert ":- e(V0,V1),green(V0),green(V1)." in clauses
    assert ":- e(V0,V1),blue(V0),blue(V1)." in clauses


def test_coin_hypothesis_space_contains_target_rules():
    clauses = _benchmark_clauses("coin")

    assert "heads(V0) :- coin(V0),not tails(V0)." in clauses
    assert "tails(V0) :- coin(V0),not heads(V0)." in clauses


def test_even_odd_hypothesis_space_contains_mutual_recursion():
    clauses = _benchmark_clauses("even_odd")

    assert "even(V1) :- odd(V0),prev(V1,V0)." in clauses
    assert "odd(V1) :- even(V0),prev(V1,V0)." in clauses


def test_grandparent_hypothesis_space_contains_invented_predicate_solution():
    args = copy.deepcopy(CASES["grandparent"])
    program = read_program(args.filename)
    clauses = set(HypothesisSpaceGenerator(program, args).generate().clauses)

    assert program.invented_predicates == (("target_1", 2),)
    assert len(program.positive_examples) == 7
    assert "target(V0,V2) :- target_1(V0,V1),target_1(V1,V2)." in clauses
    assert "target_1(V0,V1) :- mother(V0,V1)." in clauses
    assert "target_1(V0,V1) :- father(V0,V1)." in clauses
    assert not any(
        clause.startswith("target_1(") and "target_1(" in clause.split(" :- ", 1)[1]
        for clause in clauses
    )


def test_latin_square_hypothesis_space_contains_covering_target_program():
    args = copy.deepcopy(CASES["latin_square"])
    program = read_program(args.filename)
    clauses = set(HypothesisSpaceGenerator(program, args).generate().clauses)
    target = (
        "count_row(V0,V3) :- cell(V0),#count{V1:x(V0,V2,V1)}=V3.",
        "count_col(V0,V3) :- cell(V0),#count{V1:x(V2,V0,V1)}=V3.",
        ":- count_row(V0,V1),size(V2),V1-V2!=0.",
        ":- count_col(V0,V1),size(V2),V1-V2!=0.",
    )

    assert program.aggregate_modes == [
        AggregateDeclaration(1, "count", (("x", 3),), True)
    ]
    assert len(program.positive_examples) == 4
    assert len(program.negative_examples) == 20
    assert set(target) <= clauses

    coverage = NormalCoverageSolver(
        program.background,
        ["0", "--enum-mode=brave"],
        program.positive_examples,
        program.negative_examples,
    ).extract_fixed_coverage(target)

    assert coverage.pos_mask == (1 << len(program.positive_examples)) - 1
    assert coverage.neg_mask == 0


def test_magic_square_no_diag_requires_row_and_column_rules():
    args = copy.deepcopy(CASES["magic_square_no_diag"])
    program = read_program(args.filename)

    def example_cells(example):
        return {
            (int(arguments[0]), int(arguments[1])): int(arguments[2])
            for name, arguments, _negative in fragment_atoms(example.included)
            if name == "x"
        }

    def axes_are_equal(cells):
        rows = {
            sum(cells[row, column] for column in (1, 2, 3))
            for row in (1, 2, 3)
        }
        columns = {
            sum(cells[row, column] for row in (1, 2, 3))
            for column in (1, 2, 3)
        }
        return len(rows) == 1, len(columns) == 1

    positive_cells = [example_cells(example) for example in program.positive_examples]
    negative_cells = [example_cells(example) for example in program.negative_examples]
    categories = [axes_are_equal(cells) for cells in negative_cells]
    positions = {(row, column) for row in (1, 2, 3) for column in (1, 2, 3)}
    signatures = [
        tuple(cells[position] for position in sorted(positions))
        for cells in positive_cells + negative_cells
    ]
    target = {
        "sum_row(V0,V3) :- size(V0),#sum{V1:x(V0,V2,V1)}=V3.",
        "sum_col(V0,V3) :- size(V0),#sum{V1:x(V2,V0,V1)}=V3.",
            ":- sum_row(V0,V1),sum_row(V2,V3),V0!=V2,V1-V3!=0.",
            ":- sum_col(V0,V1),sum_col(V2,V3),V0!=V2,V1-V3!=0.",
    }

    assert len(program.positive_examples) == 72
    assert len(program.negative_examples) == 27
    assert all(set(cells) == positions for cells in positive_cells + negative_cells)
    assert all(sorted(cells.values()) == list(range(1, 10)) for cells in positive_cells + negative_cells)
    assert len(set(signatures)) == len(signatures)
    assert categories.count((True, False)) == 9
    assert categories.count((False, True)) == 9
    assert categories.count((False, False)) == 9
    assert program.max_body_literals == 4
    assert program.max_variables == 4
    assert program.max_program_clauses == 6
    assert all(mode.recall == 1 for mode in program.language_bias_head)

    definition_program = copy.deepcopy(program)
    definition_program.max_body_literals = 3
    definition_program.language_bias_body = [
        mode
        for mode in definition_program.language_bias_body
        if mode.literal.atom.name == "size"
    ]
    definition_program.comparison_modes = []
    definition_clauses = set(
        HypothesisSpaceGenerator(definition_program, args).generate().clauses
    )
    constraint_program = copy.deepcopy(program)
    constraint_program.language_bias_body = [
        mode
        for mode in constraint_program.language_bias_body
        if mode.literal.atom.name in {"sum_row", "sum_col"}
    ]
    constraint_program.aggregate_modes = []
    constraint_clauses = set(
        HypothesisSpaceGenerator(constraint_program, args).generate().clauses
    )

    assert {clause for clause in target if "#sum{" in clause} <= definition_clauses
    assert {clause for clause in target if clause.startswith(":-")} <= constraint_clauses

    solver = NormalCoverageSolver(
        program.background,
        ["0", "--enum-mode=brave"],
        program.positive_examples,
        program.negative_examples,
    )
    row_program = (
        "sum_row(R,S) :- size(R),#sum{V:x(R,C,V)}=S.",
        ":- sum_row(R0,S0),sum_row(R1,S1),R0!=R1,S0!=S1.",
    )
    column_program = (
        "sum_col(C,S) :- size(C),#sum{V:x(R,C,V)}=S.",
        ":- sum_col(C0,S0),sum_col(C1,S1),C0!=C1,S0!=S1.",
    )
    full_coverage = solver.extract_fixed_coverage(row_program + column_program)
    row_coverage = solver.extract_fixed_coverage(row_program)
    column_coverage = solver.extract_fixed_coverage(column_program)

    assert full_coverage.pos_mask.bit_count() == 72
    assert full_coverage.neg_mask == 0
    assert row_coverage.neg_mask.bit_count() == 9
    assert column_coverage.neg_mask.bit_count() == 9


def test_fixed_benchmark_definitions_expose_real_target_shapes():
    queens = _benchmark_clauses("8queens")
    subset_double = _benchmark_clauses("subset_sum_double")
    subset_sum = _benchmark_clauses("subset_sum_double_and_sum")
    set_partition = _benchmark_clauses("set_partition_sum")

    assert any(clause.startswith(":- ") and clause.count("q(") == 2 and "+" in clause for clause in queens)
    assert any(clause.startswith(":- ") and clause.count("q(") == 2 and "-" in clause for clause in queens)
    assert "ok(V0) :- s0(V0),s1(V0)." in subset_double
    assert any(
        clause.startswith("ok(") and clause.count("#sum{") >= 2 and "+" in clause
        for clause in subset_sum
    )
    assert any(
        clause.startswith(":- ")
        and clause.count("sum_partition(") >= 2
        and "!=" in clause
        for clause in set_partition
    )


def test_coloring_complete_head_never_generates_partial_disjunctions():
    clauses = _benchmark_clauses("coloring")

    assert all(
        clause.startswith(":-") or clause.partition(" :-")[0].count(";") == 2
        for clause in clauses
    )


def test_unbalanced_aggregate_random_seed_program_is_clingo_safe():
    args = copy.deepcopy(CASES["subset_sum_double_and_prod_unbalanced"])
    program = read_program(args.filename)
    clauses = HypothesisSpaceGenerator(program, args).generate()
    random.seed(1)
    candidate = tuple(
        sorted(random.sample(clauses.clauses, program.max_program_clauses))
    )

    NormalCoverageSolver(
        program.background,
        args.fitness["clingo_arguments"],
        program.positive_examples,
        program.negative_examples,
    ).extract_fixed_coverage(candidate)


def test_linkedness_rejects_disconnected_literal_components():
    program = Program(
        ["p(1).", "p(2).", "q(1).", "q(3).", "r(1).", "r(4)."],
        [],
        [],
        [_mode(1, "target", 1, head=True)],
        [
            _mode(1, "p", 1, positive=True),
            _mode(1, "q", 1, positive=True),
            _mode(1, "r", 1, positive=True),
        ],
    )

    clauses = _generate(program, 4, 2).clauses

    assert "target(V0) :- p(V0),q(V1),r(V1)." not in clauses
    assert "target(V0) :- p(V0),q(V0),r(V0)." in clauses


def test_mode_directions_bind_inputs_and_produce_head_outputs(tmp_path):
    task = tmp_path / "directed.txt"
    task.write_text(
        "\n".join(
            (
                "edge(1,2).",
                "#modeh(1,target(var(term,input),var(term,output))).",
                "#modeb(1,edge(var(term,input),var(term,output))).",
            )
        ),
        encoding="utf-8",
    )
    program = read_program(str(task))

    clauses = _generate(program, 2, 2).clauses

    assert tuple(
        argument.direction
        for argument in program.language_bias_head[0].template.elements[0].terms
    ) == ("input", "output")
    assert "target(V0,V1) :- edge(V0,V1)." in clauses
    assert "target(V0,V1) :- edge(V1,V0)." not in clauses


def test_theta_reduction_rejects_clause_equivalent_to_proper_subclause():
    modes = {
        0: _normal_hypothesis_mode(
            0, 0, "head", "target", 1, 1, head_form=0
        ),
        1: _normal_hypothesis_mode(1, 1, "body", "edge", 2, 2),
        2: _normal_hypothesis_mode(2, 2, "body", "other", 2, 1),
    }
    reducible = ReifiedClause(
        (ReifiedLiteral("head", 0, 0, (0,)),),
        (
            ReifiedLiteral("body", 0, 1, (0, 1)),
            ReifiedLiteral("body", 1, 1, (0, 2)),
        ),
    )
    reduced = ReifiedClause(
        (ReifiedLiteral("head", 0, 0, (0,)),),
        (
            ReifiedLiteral("body", 0, 1, (0, 1)),
            ReifiedLiteral("body", 1, 2, (0, 1)),
        ),
    )

    assert not hypothesis_space._theta_reduced(reducible, modes)
    assert hypothesis_space._theta_reduced(reduced, modes)


def test_reader_parses_aggregate_head_modes_with_optional_recall(tmp_path):
    task = tmp_path / "aggregate-head.las"
    task.write_text(
        "\n".join(
            (
                "#modeha(p(var(node,input))).",
                "#modeha(2,-q(box(var(node,input),const(colour)))).",
                "#constant(colour,red).",
            )
        ),
        encoding="utf-8",
    )

    program = read_program(str(task))

    assert [mode.recall for mode in program.language_bias_aggregate_head] == [-1, 2]
    assert [
        mode.literal.atom.signature for mode in program.language_bias_aggregate_head
    ] == [
        ("p", 1),
        ("-q", 1),
    ]


def test_modeha_generates_nonredundant_cardinality_heads(tmp_path):
    task = tmp_path / "aggregate-head-space.las"
    task.write_text(
        "\n".join(
            (
                "#maxv(0).",
                "#maxbl(1).",
                "#maxhl(2).",
                "seed(a).",
                "seed(b).",
                "#constant(item,a).",
                "#constant(item,b).",
                "#modeha(2,p(const(item))).",
                "#modeb(1,seed(const(item))).",
            )
        ),
        encoding="utf-8",
    )

    clauses = set(
        HypothesisSpaceGenerator(read_program(str(task)), Arguments())
        .generate()
        .clauses
    )

    assert "0{p(a)}1 :- seed(a)." in clauses
    assert "0{p(b)}1 :- seed(a)." in clauses
    assert {
        "0{p(a);p(b)}1 :- seed(a).",
        "1{p(a);p(b)}1 :- seed(a).",
        "1{p(a);p(b)}2 :- seed(a).",
    } <= clauses
    assert not any("0{p(a);p(b)}2" in clause for clause in clauses)
    assert not any("2{p(a);p(b)}2" in clause for clause in clauses)


def test_modeha_recall_and_minhl_bound_generated_width(tmp_path):
    task = tmp_path / "bounded-aggregate-head.las"
    task.write_text(
        "\n".join(
            (
                "#maxv(0).",
                "#maxbl(1).",
                "#minhl(2).",
                "#maxhl(*).",
                "seed(a).",
                "seed(b).",
                "#constant(item,a).",
                "#constant(item,b).",
                "#modeha(2,p(const(item))).",
                "#modeha(1,q(const(item))).",
                "#modeb(1,seed(const(item))).",
            )
        ),
        encoding="utf-8",
    )

    clauses = set(
        HypothesisSpaceGenerator(read_program(str(task)), Arguments())
        .generate()
        .clauses
    )

    assert clauses
    choice_clauses = {clause for clause in clauses if not clause.startswith(":-")}
    assert all(clause.partition(" :-")[0].count(";") >= 1 for clause in choice_clauses)
    assert any("{p(a);p(b);q(a)}" in clause for clause in choice_clauses)
    assert not any("q(a);q(b)" in clause for clause in choice_clauses)


def test_modeha_reuses_one_template_for_distinct_compatible_variables(tmp_path):
    task = tmp_path / "variable-aggregate-head.las"
    task.write_text(
        "\n".join(
            (
                "#maxv(2).",
                "#maxbl(2).",
                "#maxhl(2).",
                "node(a).",
                "node(b).",
                "#modeha(2,p(var(node,input))).",
                "#modeb(2,node(var(node,output))).",
            )
        ),
        encoding="utf-8",
    )

    clauses = set(
        HypothesisSpaceGenerator(read_program(str(task)), Arguments())
        .generate()
        .clauses
    )

    assert "0{p(V0);p(V1)}1 :- node(V0),node(V1)." in clauses
    assert not any("p(V0);p(V0)" in clause for clause in clauses)


def test_unbounded_modeha_requires_finite_maxhl(tmp_path):
    task = tmp_path / "unbounded-aggregate-head.las"
    task.write_text(
        "#maxhl(*).\n#modeha(p(var(node,input))).\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"#maxhl\(\*\).+#modeha"):
        HypothesisSpaceGenerator(read_program(str(task)), Arguments())


def test_ground_modeha_caps_impossible_repeated_elements_before_grounding(tmp_path):
    task = tmp_path / "ground-aggregate-head.las"
    task.write_text(
        "#maxhl(100).\n#modeha(p).\n",
        encoding="utf-8",
    )

    templates = hypothesis_space._aggregate_head_templates(read_program(str(task)))

    assert len(templates) == 1
    assert templates[0].width == 1


def test_bodyless_condition_budget_expands_ground_modeha_capacity(tmp_path):
    task = tmp_path / "ground-conditional-aggregate-head.las"
    task.write_text(
        "#maxbl(1).\n#maxhl(100).\n#modeha(p).\n#modec(1,c).\n",
        encoding="utf-8",
    )

    templates = hypothesis_space._aggregate_head_templates(read_program(str(task)))

    assert len(templates) == 4
    assert {template.width for template in templates} == {1, 2}


def test_modeha_capacity_deduplicates_equal_constant_expansions(tmp_path):
    task = tmp_path / "duplicate-constant-aggregate-head.las"
    task.write_text(
        "\n".join(
            (
                "#maxhl(50).",
                "#constant(left,a).",
                "#constant(right,a).",
                "#modeha(p(const(left))).",
                "#modeha(p(const(right))).",
            )
        ),
        encoding="utf-8",
    )

    templates = hypothesis_space._aggregate_head_templates(read_program(str(task)))

    assert len(templates) == 1
    assert templates[0].width == 1


def test_modeha_elements_accept_generated_conditions(tmp_path):
    task = tmp_path / "conditional-aggregate-head.las"
    task.write_text(
        "\n".join(
            (
                "#maxv(1).",
                "#maxbl(2).",
                "#maxhl(1).",
                "node(a).",
                "allowed(a).",
                "#modeha(1,p(var(node,input))).",
                "#modeb(1,node(var(node,output))).",
                "#modec(1,allowed(var(node,input))).",
            )
        ),
        encoding="utf-8",
    )

    program = read_program(str(task))
    clauses = set(
        HypothesisSpaceGenerator(program, Arguments())
        .generate()
        .clauses
    )

    assert "0{p(V0):allowed(V0)}1 :- node(V0)." in clauses
    control = clingo.Control(["0"])
    control.add("base", [], "\n".join([*program.background, *clauses]))
    control.ground([("base", [])])


@pytest.mark.parametrize(
    "declaration",
    (
        "#modeha(0,p).",
        "#modeha(not p).",
        "#modeha(1,p(var(node,input,x))).",
        "#minhl(2).\n#maxhl(1).\n#modeha(1,p).",
    ),
)
def test_reader_rejects_invalid_aggregate_head_bias(tmp_path, declaration):
    task = tmp_path / "invalid-aggregate-head.las"
    task.write_text(declaration + "\n", encoding="utf-8")

    with pytest.raises(ValueError):
        read_program(str(task))
