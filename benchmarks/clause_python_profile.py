"""Optional, separate cProfile pass for the Python side of clause generation."""

import cProfile
import json
import os
import platform
import pstats
from dataclasses import asdict
from pathlib import Path

import clingo

from gentians import timing
from gentians.clauses import generate_clause_space
from gentians.clauses.canonicalization.arithmetic_system import ArithmeticSystem
from gentians.clauses.canonicalization.canonical_clause import CanonicalArithmeticClause
from gentians.clauses.clause import Clause
from gentians.clauses.reified_clause import ReifiedClause
from gentians.clauses.reified_literal import ReifiedLiteral


BUCKET_LABELS = {
    "decode": "Decode (own code and literal probes)",
    "construction": "Clause construction (own code)",
    "canonicalization": "Canonicalization (own code)",
    "hash_dedup": "Keys/hash/dedup (visible calls)",
    "append_storage": "Append/order/storage (visible calls)",
    "canonical_storage": "Canonical dedup/storage (mixed own time)",
    "final_storage": "Final ClauseSpace dedup/storage (mixed own time)",
    "symbol": "clingo.Symbol access/conversion",
    "ast_text": "Clingo AST-to-text conversion",
    "bindings": "Other Clingo AST/CFFI access",
    "other": "Preparation/orchestration/other",
    "grounding": "Native Clingo grounding",
    "solving": "Native Clingo solving",
}


def profile_stats(profiler: cProfile.Profile) -> pstats.Stats:
    """Retain code identities that standard cProfile labels can overwrite.

    Generated dataclass methods share '<string>:2(__init__)'. Give clause
    methods their class names and disambiguate any remaining collisions.
    """
    methods = {}
    for cls in (Clause, ReifiedClause, ReifiedLiteral, CanonicalArithmeticClause, ArithmeticSystem):
        for name in ("__init__", "__hash__", "__eq__"):
            code = getattr(getattr(cls, name, None), "__code__", None)
            if code is not None:
                methods[id(code)] = f"{cls.__name__}.{name}"
    entries = profiler.getstats()
    labels = {}
    stats = pstats.Stats()
    for entry in entries:
        code = entry.code
        label = ("~", 0, code) if isinstance(code, str) else (
            code.co_filename, code.co_firstlineno, methods.get(id(code), code.co_name),
        )
        if label in stats.stats:
            label = (*label[:2], f"{label[2]} [definition {len(labels)}]")
        labels[id(code)] = label
        stats.stats[label] = (
            entry.callcount - entry.reccallcount, entry.callcount,
            entry.inlinetime, entry.totaltime, {},
        )
    for entry in entries:
        caller = labels[id(entry.code)]
        for subentry in entry.calls or ():
            callers = stats.stats[labels[id(subentry.code)]][4]
            callers[caller] = (
                subentry.callcount, subentry.callcount - subentry.reccallcount,
                subentry.inlinetime, subentry.totaltime,
            )
    stats.get_top_level_stats()
    return stats


def function_bucket(filename: str, name: str) -> str:
    """Classify function self time, never its overlapping cumulative time.

    Implicit dict assignments, tuple hashing, etc. remain in the enclosing
    function's self time. cProfile cannot split those source-level operations.
    """
    source = filename.replace("\\", "/")
    method = name.rsplit(".", 1)[-1]
    if "clingo_control_ground" in name:
        return "grounding"
    if "clingo_control_solve" in name:
        return "solving"
    if source.endswith("/clingo/symbol.py") or "_clingo.clingo_symbol_" in name:
        return "symbol"
    if (
        source.endswith("/clingo/ast.py") and name in {"__str__", "__repr__"}
        or "_clingo.clingo_ast_to_string" in name
    ):
        return "ast_text"
    if method in {"__hash__", "__eq__"} or name == "<built-in method builtins.hash>" or (
        name == "key" and "/clauses/canonicalization/" in source
    ) or name in {
        "<method 'get' of 'dict' objects>",
        "<method 'setdefault' of 'dict' objects>",
        "<method 'add' of 'set' objects>",
    }:
        return "hash_dedup"
    if name in {
        "<method 'append' of 'list' objects>",
        "<method 'extend' of 'list' objects>",
        "<method 'sort' of 'list' objects>",
        "<built-in method builtins.sorted>",
    }:
        return "append_storage"
    if name in {
        "Clause.__init__", "ReifiedClause.__init__", "ReifiedLiteral.__init__",
        "CanonicalArithmeticClause.__init__", "ArithmeticSystem.__init__",
    } or source.endswith("/clingo/ast.py") and name == "Rule":
        return "construction"
    if source.endswith("/clauses/decoder.py") and name != "_model_literal_index":
        return "decode"
    if source.endswith("/clauses/clause_space.py"):
        return "final_storage"
    if source.endswith("/clauses/canonicalization/clauses.py"):
        return "construction" if name == "_clause_from_reified" else "canonical_storage"
    if source.endswith("/clauses/reified_clause.py") or (
        "/clauses/canonicalization/" in source and name in {"instantiate", "render"}
    ):
        return "construction"
    if "/clauses/canonicalization/" in source:
        return "canonicalization"
    if "/clingo/" in source or "_clingo." in name or "_cffi_backend." in name:
        return "bindings"
    return "other"


def summarize_profile(stats: pstats.Stats) -> dict:
    buckets = {
        name: {"bucket": name, "label": label, "selfSeconds": 0.0, "calls": 0}
        for name, label in BUCKET_LABELS.items()
    }
    functions = []
    decode_calls = 0
    for (filename, line, name), (primitive, calls, own, cumulative, _callers) in stats.stats.items():
        bucket = function_bucket(filename, name)
        buckets[bucket]["selfSeconds"] += own
        buckets[bucket]["calls"] += calls
        functions.append({
            "file": filename, "line": line, "function": name, "bucket": bucket,
            "primitiveCalls": primitive, "calls": calls,
            "selfSeconds": own, "cumulativeSeconds": cumulative,
        })
        if filename.replace("\\", "/").endswith("/clauses/decoder.py") and name == "_clause_from_model":
            decode_calls += calls
    total = sum(row["selfSeconds"] for row in buckets.values())
    python = total - buckets["grounding"]["selfSeconds"] - buckets["solving"]["selfSeconds"]
    return {
        "schemaVersion": 1,
        "functionSelfSeconds": total,
        "pythonAndBindingsSelfSeconds": python,
        "decodeCalls": decode_calls,
        "buckets": list(buckets.values()),
        "functions": sorted(functions, key=lambda row: (
            -row["selfSeconds"], row["file"], row["line"], row["function"],
        )),
    }


def profile_clause_python(task, arguments, expected_space, expected_models, path: Path) -> dict:
    """Profile the same complete space separately, without the regular timers.

    Keep the first pass's throughput independent of cProfile overhead. Verify
    that all model callbacks were captured, including with parallel Clingo.
    """
    profiler = cProfile.Profile()
    old_enabled = timing.is_enabled()
    old_clingo_path = os.environ.pop("GENTIANS_CLINGO_METRICS_PATH", None)
    try:
        timing.set_enabled(False)
        space = profiler.runcall(generate_clause_space, task, arguments)
    finally:
        timing.set_enabled(old_enabled)
        if old_clingo_path is not None:
            os.environ["GENTIANS_CLINGO_METRICS_PATH"] = old_clingo_path

    path.parent.mkdir(parents=True, exist_ok=True)
    stats = profile_stats(profiler)
    stats.dump_stats(str(path))
    summary = summarize_profile(stats)
    if space.entries != expected_space.entries:
        raise RuntimeError("cProfile pass produced a different ClauseSpace")
    if expected_models is not None and summary["decodeCalls"] != expected_models:
        raise RuntimeError(
            f"cProfile captured {summary['decodeCalls']} of {expected_models} model callbacks; "
            f"inspect {path} before interpreting the breakdown"
        )
    summary.update({
        "protocol": "Separate second generation pass; cProfile overhead included; caches may be warm.",
        "python": platform.python_version(), "clingo": clingo.__version__,
        "platform": platform.platform(), "arguments": asdict(arguments),
        "clauses": len(space), "expectedModels": expected_models,
    })
    path.with_suffix(".json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def print_python_profile(summary: dict, path: Path) -> None:
    python = summary["pythonAndBindingsSelfSeconds"]
    print("  Python cProfile (separate pass; profiler overhead included):")
    print(f"    Captured decode calls: {summary['decodeCalls']:,}")
    print("    Function self-time buckets; subcalls belong to their own buckets:")
    for row in summary["buckets"]:
        if row["bucket"] in {"grounding", "solving"}:
            continue
        share = f" ({100 * row['selfSeconds'] / python:.1f}%)" if python else ""
        print(f"      {row['label']}: {row['selfSeconds']:.3f}s{share}; {row['calls']:,} calls")
    print("    Implicit hashing/assignment stays in the enclosing function's bucket.")
    print("    These times do not decompose or rescale the first pass's Python seconds.")
    print("    Hot functions (self seconds | cumulative seconds | calls):")
    hotspots = [row for row in summary["functions"] if row["bucket"] not in {"grounding", "solving"}]
    for row in hotspots[:15]:
        print(
            f"      {row['selfSeconds']:.3f} | {row['cumulativeSeconds']:.3f} | {row['calls']:,} "
            f"{row['file']}:{row['line']}({row['function']})"
        )
    print("    Cumulative times overlap; use self times when adding costs.")
    print(f"    Full profile: {path}")
    print(f"    Function details + environment: {path.with_suffix('.json')}")
