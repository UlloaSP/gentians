import sys
from collections import OrderedDict, deque
from functools import lru_cache

import clingo
from clingo import ast

from ..clingo_stats import clingo_stat, ground_stats
from ..language.asp import AspProgram, add_program
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
from .compiler import compile_coverage_program


class CoverageSolver:
    """Create, ground, and solve one Clingo control per candidate."""

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
        self.inherited_examples = 0
        self.skipped_controls = 0
        self._positive_ceilings: OrderedDict[tuple[str, ...], int] = OrderedDict()
        self._positive_solver: CoverageSolver | None = None

    def positive_ceiling(self, program: AspProgram, coverage: Coverage) -> int:
        """Exact positive coverage after removing only learned constraints."""
        if coverage.pos_mask.bit_count() == self.positive_examples:
            return coverage.pos_mask
        headed = tuple(rule for rule in program if not _rule_key(rule)[0])
        if len(headed) == len(program):
            return coverage.pos_mask
        key = tuple(sorted(_rule_key(rule)[1] for rule in headed))
        if key not in self._positive_ceilings:
            if self._positive_solver is None:
                self._positive_solver = CoverageSolver(
                    self.background, self.clingo_arguments, self._examples[0], [],
                )
                self._positive_solver._require_exhaustive = True
            # The empty headed program is a valid diagnostic query, not an
            # admissible empty genome. BK/context constraints remain untouched.
            self._positive_ceilings[key] = self._positive_solver.extract_coverage(headed).pos_mask
            if len(self._positive_ceilings) > 64:
                self._positive_ceilings.popitem(last=False)
        self._positive_ceilings.move_to_end(key)
        return self._positive_ceilings[key]

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

    def _extract(self, program: AspProgram) -> Coverage:
        ctl, grounding_seconds, phase = self._ground(program)
        solving_seconds, coverage = self._solve(ctl, self._require_exhaustive)
        self._record(
            ctl,
            program,
            coverage,
            grounding_seconds,
            solving_seconds,
            phase,
        )
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
    def _solve(ctl, require_exhaustive: bool = False) -> tuple[float, Coverage]:
        if require_exhaustive and ctl.configuration.solve.enum_mode != "brave":
            raise RuntimeError("Coverage inheritance requires brave enumeration")
        seconds = 0.0
        pos_mask = 0
        neg_mask = 0
        start = net_time()
        with ctl.solve(yield_=True) as handle:
            seconds += net_time() - start
            iterator = iter(handle)
            while True:
                start = net_time()
                try:
                    model = next(iterator)
                except StopIteration:
                    seconds += net_time() - start
                    break
                seconds += net_time() - start
                positive, negative = _coverage_masks(model.symbols(shown=True))
                pos_mask |= positive
                neg_mask |= negative
            if require_exhaustive and not handle.get().exhausted:
                raise RuntimeError("Coverage inheritance requires exhaustive solving")
            start = net_time()
        seconds += net_time() - start
        add(f"{current_phase()}.solving", seconds)
        return seconds, Coverage(pos_mask, neg_mask)

    def _record(
        self,
        ctl,
        program: AspProgram,
        coverage: Coverage,
        grounding_seconds: float,
        solving_seconds: float,
        phase: str,
    ) -> None:
        if not metric_enabled("clingo"):
            return
        with instrumentation():
            stats = ctl.statistics
            grounded = ground_stats(stats)
            common = {
                "phase_context": phase,
                "program_size": len(program),
                "clingo_arguments": " ".join(self.clingo_arguments),
            }
            record_metric(
                "clingo",
                {
                    **common,
                    "operation_category": "grounding",
                    "seconds": grounding_seconds,
                    "input_clauses": len(self.background) + len(program),
                    "program_chars": sum(
                        len(str(statement)) for statement in self.coverage_program
                    )
                    + sum(len(str(statement)) for statement in self.background)
                    + sum(len(str(statement)) for statement in program),
                    "positive_examples": self.positive_examples,
                    "negative_examples": self.negative_examples,
                    "stats_atoms": grounded["atoms"],
                    "stats_rules": grounded["rules"],
                },
            )
            record_metric(
                "clingo",
                {
                    **common,
                    "operation_category": "solving",
                    "seconds": solving_seconds,
                    "models": clingo_stat(stats, "summary", "models", "enumerated"),
                    "covered_positive": coverage.pos_mask.bit_count(),
                    "covered_negative": coverage.neg_mask.bit_count(),
                    "stats_choices": clingo_stat(
                        stats, "solving", "solvers", "choices"
                    ),
                    "stats_conflicts": clingo_stat(
                        stats, "solving", "solvers", "conflicts"
                    ),
                },
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
