from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from gentians import Arguments
from gentians.rule_generation.rule_space import RuleEntry, RuleSpace


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
        "schemaVersion": 2,
        "dataset": dataset,
        "hypothesisKey": hypothesis_key(arguments),
        "arguments": asdict(arguments),
        "entries": [_entry_payload(entry) for entry in rule_space.entries],
        "metrics": metrics or {},
    }
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")


def read_hypothesis_file(path: Path, arguments: Arguments) -> RuleSpace:
    payload = read_hypothesis_payload(path, arguments)
    return rule_space_from_payload(payload, path)


def rule_space_from_payload(payload: dict[str, object], path: Path) -> RuleSpace:
    entries = payload.get("entries")
    if isinstance(entries, list):
        return RuleSpace([_entry_from_payload(entry) for entry in entries])
    clauses = payload.get("clauses")
    if not isinstance(clauses, list) or not all(isinstance(c, str) for c in clauses):
        raise ValueError(f"Invalid hypothesis space file: {path}")
    return RuleSpace.from_clauses(clauses)


def read_hypothesis_metrics(path: Path, arguments: Arguments) -> dict[str, object]:
    payload = read_hypothesis_payload(path, arguments)
    return metrics_from_payload(payload)


def metrics_from_payload(payload: dict[str, object]) -> dict[str, object]:
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


def _entry_payload(entry: RuleEntry) -> dict[str, object]:
    return {
        "text": entry.text,
        "heads": [list(predicate) for predicate in sorted(entry.heads)],
        "deps": [list(predicate) for predicate in sorted(entry.deps)],
        "body_literals": entry.body_literals,
    }


def _entry_from_payload(value: object) -> RuleEntry:
    if not isinstance(value, dict):
        raise ValueError("Invalid hypothesis rule entry")
    text = value.get("text")
    heads = value.get("heads")
    deps = value.get("deps")
    body_literals = value.get("body_literals")
    if (
        not isinstance(text, str)
        or not isinstance(heads, list)
        or not isinstance(deps, list)
        or not isinstance(body_literals, int)
    ):
        raise ValueError("Invalid hypothesis rule entry")
    return RuleEntry(
        text,
        frozenset(_predicate_from_payload(predicate) for predicate in heads),
        frozenset(_predicate_from_payload(predicate) for predicate in deps),
        body_literals,
    )


def _predicate_from_payload(value: object) -> tuple[str, int]:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not isinstance(value[0], str)
        or not isinstance(value[1], int)
    ):
        raise ValueError("Invalid hypothesis predicate")
    return value[0], value[1]


def safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value)
