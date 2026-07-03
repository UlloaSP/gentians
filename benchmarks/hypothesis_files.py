from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from gentians import Arguments
from gentians.rule_generation.rule_space import RuleSpace


HYPOTHESIS_FIELDS = (
    "filename",
    "max_variables",
    "max_depth",
    "disjunctive_head_length",
    "max_candidate_clauses",
    "unbalanced_aggregates",
    "hypothesis_space",
    "aggregates",
    "comparison_operators",
    "arithmetic_operators",
    "predicate_invention",
    "automatic_language_bias",
)


def hypothesis_path(directory: Path, dataset: str) -> Path:
    return directory / f"{safe_filename(dataset)}.json"


def write_hypothesis_file(
    path: Path,
    dataset: str,
    arguments: Arguments,
    rule_space: RuleSpace,
    metrics: dict[str, object] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schemaVersion": 1,
        "dataset": dataset,
        "hypothesisKey": hypothesis_key(arguments),
        "arguments": asdict(arguments),
        "clauses": rule_space.clauses,
        "metrics": metrics or {},
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def read_hypothesis_file(path: Path, arguments: Arguments) -> RuleSpace:
    payload = read_hypothesis_payload(path, arguments)
    clauses = payload.get("clauses")
    if not isinstance(clauses, list) or not all(isinstance(c, str) for c in clauses):
        raise ValueError(f"Invalid hypothesis space file: {path}")
    return RuleSpace.from_clauses(clauses)


def read_hypothesis_metrics(path: Path, arguments: Arguments) -> dict[str, object]:
    payload = read_hypothesis_payload(path, arguments)
    metrics = payload.get("metrics", {})
    return metrics if isinstance(metrics, dict) else {}


def read_hypothesis_payload(path: Path, arguments: Arguments) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"Hypothesis space not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid hypothesis space file: {path}")
    expected = hypothesis_key(arguments)
    actual = payload.get("hypothesisKey")
    if actual != expected:
        raise ValueError(f"Hypothesis space does not match current arguments: {path}")
    return payload


def hypothesis_key(arguments: Arguments) -> dict[str, object]:
    values = asdict(arguments)
    return {field: values[field] for field in HYPOTHESIS_FIELDS}


def safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value)
