import sys
from collections import OrderedDict, deque
from collections.abc import Sequence
from functools import lru_cache

import clingo
from clingo import ast

from ..clingo_stats import clingo_statistics
from ..language.asp import AspProgram, add_program, clause_predicates
from ..language.ir.example import Example
from ..timing import (
    add,
    current_phase,
    instrumentation,
    metric_enabled,
    net_time,
    record_metric,
)
from .coverage import Coverage
from .prepared import PreparedClauses
from .compiler import CLAUSE_GUARD_PREDICATE, compile_coverage_program, compile_guarded_clauses


class CoverageSolver:
    """Ground and solve each candidate program.

    A candidate gets its own Clingo control unless `prepare` grounded a set of
    clauses that contains it; then it only solves, under assumptions that
    select its clauses in that shared control.
    """

    def __init__(
        self,
        background: AspProgram,
        clingo_arguments: list[str],
        positive_examples: list[Example],
        negative_examples: list[Example],
        *,
        constraint_inheritance: bool = False,
    ) -> None:
        self.background = background
        self.clingo_arguments = clingo_arguments
        self.positive_examples = len(positive_examples)
        self.negative_examples = len(negative_examples)
        self.coverage_program = compile_coverage_program(
            positive_examples, negative_examples
        )
        self.constraint_inheritance = constraint_inheritance
        self._require_exhaustive = constraint_inheritance
        self._examples = (positive_examples, negative_examples)
        # Bounded evidence, not per-clause fitness. Each entry describes a whole
        # program under this solver's fixed background and isolated contexts.
        self._evidence: deque[tuple[frozenset[str], frozenset[str], int]] = deque(maxlen=64)
        self._partial: OrderedDict[int, CoverageSolver] = OrderedDict()
        # Characters of the programs every control adds; metrics only.
        self._static_chars: int | None = None
        self._prepared: PreparedClauses | None = None
        self.inherited_examples = 0
        self.skipped_controls = 0

    def _inherit(self, program: AspProgram) -> Coverage:
        keys = [_rule_key(rule) for rule in program]
        constraints = frozenset(text for constraint, text in keys if constraint)
        headed = frozenset(text for constraint, text in keys if not constraint)
        npos = self.positive_examples
        full = (1 << (npos + self.negative_examples)) - 1
        covered = absent = 0
        for previous_heads, previous_constraints, previous_mask in self._evidence:
            if headed != previous_heads:
                continue
            if previous_constraints <= constraints:
                absent |= full ^ previous_mask
            if constraints <= previous_constraints:
                covered |= previous_mask
        unknown = full & ~(covered | absent)
        self.inherited_examples += (full ^ unknown).bit_count()
        if unknown:
            if unknown == full:
                result = self._extract(program)
                covered |= result.pos_mask | (result.neg_mask << npos)
            else:
                # ponytail: keep at most 32 compiled subsets. Compile on demand;
                # do not retain a Control or grow a cache for every subset.
                selected = [i for i in range(full.bit_length()) if unknown & (1 << i)]
                partial = self._partial.get(unknown)
                if partial is None:
                    positives, negatives = self._examples
                    partial = CoverageSolver(
                        self.background, self.clingo_arguments,
                        [positives[i] for i in selected if i < npos],
                        [negatives[i - npos] for i in selected if i >= npos],
                    )
                    partial._require_exhaustive = True
                    self._partial[unknown] = partial
                    if len(self._partial) > 32:
                        self._partial.popitem(last=False)
                self._partial.move_to_end(unknown)
                result = partial.extract_coverage(program)
                compact = result.pos_mask | (result.neg_mask << partial.positive_examples)
                covered |= sum(1 << original for local, original in enumerate(selected)
                               if compact & (1 << local))
        else:
            self.skipped_controls += 1
        self._evidence.append((headed, constraints, covered))
        return Coverage(covered & ((1 << npos) - 1), covered >> npos)

    def extract_coverage(self, program: AspProgram) -> Coverage:
        if self.constraint_inheritance:
            return self._inherit(program)
        return self._extract(program)

    def prepare(self, clauses: AspProgram) -> None:
        """Ground `clauses` once so candidates made of them only solve.

        Each clause is guarded by a free atom; a candidate assumes the atoms of
        its clauses true and the others false. The stable models match those of
        the candidate alone, so coverage is unchanged. Replaces the previous set.

        Only clauses whose bodies use no head of the given clauses are grounded.
        A guarded head is never a fact, so a body over it would be instantiated
        for every atom any guarded clause might derive; grounding exploded that
        way on aggregate spaces. Candidates using other clauses ground alone.
        """
        self._prepared = None
        clauses = _independent_clauses(clauses)
        guarded = compile_guarded_clauses(clauses) if clauses else None
        if guarded is None:
            return
        ctl = clingo.Control(self.clingo_arguments, logger=_coverage_logger)
        add_program(ctl, self.coverage_program)
        add_program(ctl, self.background)
        add_program(ctl, guarded)
        start = net_time()
        ctl.ground([("base", [])])
        seconds = net_time() - start
        phase = current_phase()
        add(f"{phase}.grounding", seconds)
        literals = []
        for index in range(len(clauses)):
            # The choice rule defines every guard atom.
            atom = ctl.symbolic_atoms[
                clingo.Function(CLAUSE_GUARD_PREDICATE, [clingo.Number(index)])
            ]
            assert atom is not None
            literals.append(atom.literal)
        self._prepared = PreparedClauses(
            ctl,
            {clause: index for index, clause in enumerate(clauses)},
            [-literal for literal in literals],
            clauses,
            (seconds, phase),
        )

    def _extract(self, program: AspProgram) -> Coverage:
        prepared = self._prepared
        if prepared is not None and all(clause in prepared.index for clause in program):
            assumptions = list(prepared.excluded)
            for clause in program:
                position = prepared.index[clause]
                assumptions[position] = -assumptions[position]
            solving_seconds, coverage = self._solve(
                prepared.ctl, self._require_exhaustive, assumptions,
            )
            if prepared.grounding is not None:
                # Statistics describe the ground program only after a solve.
                self._record_grounding(prepared.ctl, prepared.clauses, *prepared.grounding)
                prepared.grounding = None
            self._record_solving(
                prepared.ctl, program, coverage, solving_seconds, current_phase(),
            )
            return coverage
        ctl, grounding_seconds, phase = self._ground(program)
        solving_seconds, coverage = self._solve(ctl, self._require_exhaustive)
        self._record_grounding(ctl, program, grounding_seconds, phase)
        self._record_solving(ctl, program, coverage, solving_seconds, phase)
        return coverage

    def _ground(self, program: AspProgram):
        ctl = clingo.Control(self.clingo_arguments, logger=_coverage_logger)
        add_program(ctl, self.coverage_program)
        add_program(ctl, self.background)
        add_program(ctl, program)
        start = net_time()
        ctl.ground([("base", [])])
        seconds = net_time() - start
        phase = current_phase()
        add(f"{phase}.grounding", seconds)
        return ctl, seconds, phase

    @staticmethod
    def _solve(
        ctl, require_exhaustive: bool = False, assumptions: Sequence[int] = (),
    ) -> tuple[float, Coverage]:
        # Each brave model extends the previous one, so the last model holds
        # every brave consequence. Converting only its symbols is exact.
        if ctl.configuration.solve.enum_mode != "brave":
            raise RuntimeError("Coverage extraction requires brave enumeration")
        last = []
        start = net_time()
        result = ctl.solve(
            assumptions=assumptions,
            on_last=lambda model: last.append(model.symbols(shown=True)),
        )
        seconds = net_time() - start
        if require_exhaustive and not result.exhausted:
            raise RuntimeError("Coverage inheritance requires exhaustive solving")
        pos_mask, neg_mask = _coverage_masks(last[0]) if last else (0, 0)
        add(f"{current_phase()}.solving", seconds)
        return seconds, Coverage(pos_mask, neg_mask)

    def _record_grounding(
        self, ctl, program: AspProgram, seconds: float, phase: str,
    ) -> None:
        if not metric_enabled("clingo"):
            return
        with instrumentation():
            stats = clingo_statistics(ctl)
            if self._static_chars is None:
                self._static_chars = sum(
                    len(str(statement))
                    for statement in (*self.coverage_program, *self.background)
                )
            record_metric(
                "clingo",
                {
                    **self._common(program, phase),
                    "operation_category": "grounding",
                    "seconds": seconds,
                    "input_clauses": len(self.background) + len(program),
                    "program_chars": self._static_chars
                    + sum(len(str(statement)) for statement in program),
                    "positive_examples": self.positive_examples,
                    "negative_examples": self.negative_examples,
                    "stats_atoms": stats["atoms"],
                    "stats_rules": stats["rules"],
                },
            )

    def _record_solving(
        self, ctl, program: AspProgram, coverage: Coverage, seconds: float, phase: str,
    ) -> None:
        if not metric_enabled("clingo"):
            return
        with instrumentation():
            stats = clingo_statistics(ctl)
            record_metric(
                "clingo",
                {
                    **self._common(program, phase),
                    "operation_category": "solving",
                    "seconds": seconds,
                    "models": stats["models"],
                    "covered_positive": coverage.pos_mask.bit_count(),
                    "covered_negative": coverage.neg_mask.bit_count(),
                    "stats_choices": stats["choices"],
                    "stats_conflicts": stats["conflicts"],
                },
            )

    def _common(self, program: AspProgram, phase: str) -> dict[str, object]:
        return {
            "phase_context": phase,
            "program_size": len(program),
            "clingo_arguments": " ".join(self.clingo_arguments),
        }


def _independent_clauses(clauses: AspProgram) -> AspProgram:
    summaries = [clause_predicates(clause) for clause in clauses]
    heads = set().union(*(clause_heads for clause_heads, _deps, _body in summaries))
    return tuple(
        clause
        for clause, (_heads, deps, _body) in zip(clauses, summaries, strict=True)
        if not deps & heads
    )


def _coverage_masks(symbols) -> tuple[int, int]:
    pos_mask = 0
    neg_mask = 0
    for symbol in symbols:
        if len(symbol.arguments) != 1:
            continue
        value = symbol.arguments[0].number
        if symbol.name == "extended_p":
            pos_mask |= 1 << value
        elif symbol.name == "extended_n":
            neg_mask |= 1 << value
    return pos_mask, neg_mask


def _coverage_logger(code, message):
    with instrumentation():
        if code != clingo.MessageCode.AtomUndefined:
            print(message, file=sys.stderr, end="" if message.endswith("\n") else "\n")


def _is_constraint(rule: ast.AST) -> bool:
    return (
        rule.ast_type == ast.ASTType.Rule
        and rule.head.ast_type == ast.ASTType.Literal
        and rule.head.sign == ast.Sign.NoSign
        and rule.head.atom.ast_type == ast.ASTType.BooleanConstant
        and rule.head.atom.value == 0
    )


@lru_cache(maxsize=4096)
def _rule_key(rule: ast.AST) -> tuple[bool, str]:
    # Exact Clingo rendering, not semantic equivalence. Native string-set
    # comparisons avoid repeated Python/C crossings during evidence lookup.
    return _is_constraint(rule), str(rule)
