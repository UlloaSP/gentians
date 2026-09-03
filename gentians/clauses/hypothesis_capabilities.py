from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HypothesisCapabilities:
    has_numeric_evidence: bool
    allow_numeric_comparison: bool
    allow_equality_comparison: bool
    allow_arithmetic: bool
    allow_aggregates: bool
    allow_recursion: bool
