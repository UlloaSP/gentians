import json
import os
import time
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import Any, Callable, TypeVar


_enabled = bool(os.environ.get("GENTIANS_TIMINGS_PATH"))
_totals: dict[str, float] = {}
_counts: dict[str, int] = {}
_stack: list[dict[str, Any]] = []
_ga_rows: list[dict[str, float]] = []
_event_counter = 0
_outer_iteration = 0
_global_generation_offset = 0
_F = TypeVar("_F", bound=Callable)


def _write_json_atomic(path: str, rows: list[dict[str, object]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(f"{target.suffix}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    for _ in range(20):
        try:
            tmp.replace(target)
            return
        except PermissionError:
            time.sleep(0.05)
    try:
        tmp.unlink()
    except OSError:
        pass


def _append_jsonl(path: str | None, row: dict[str, Any]) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
        f.flush()


def add(name: str, seconds: float) -> None:
    if not _enabled:
        return
    _totals[name] = _totals.get(name, 0.0) + seconds
    _counts[name] = _counts.get(name, 0) + 1
    _flush_timings()


@contextmanager
def phase(name: str):
    if not _enabled:
        yield
        return
    global _event_counter
    _event_counter += 1
    parent = _stack[-1] if _stack else None
    event = {
        "event_id": _event_counter,
        "parent_id": parent["event_id"] if parent else None,
        "phase": name,
        "depth": len(_stack),
        "started_perf": time.perf_counter(),
        "started_wall": time.time(),
    }
    _stack.append(event)
    start = time.perf_counter()
    try:
        yield
    finally:
        ended = time.perf_counter()
        seconds = ended - start
        add(name, seconds)
        row = {
            "event_id": event["event_id"],
            "parent_id": event["parent_id"],
            "phase": name,
            "depth": event["depth"],
            "started_perf": event["started_perf"],
            "ended_perf": ended,
            "started_wall": event["started_wall"],
            "ended_wall": time.time(),
            "seconds": seconds,
        }
        _append_jsonl(os.environ.get("GENTIANS_TIMING_EVENTS_PATH"), row)
        _stack.pop()


def profile_phase(name: str):
    def decorator(func: _F) -> _F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            with phase(name):
                return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def current_phase() -> str:
    return _stack[-1]["phase"] if _stack else "unclassified"


def current_event_id() -> int | None:
    return _stack[-1]["event_id"] if _stack else None


def record_metric(kind: str, row: dict[str, Any]) -> None:
    env_paths = {
        "candidate": "GENTIANS_CANDIDATE_METRICS_PATH",
        "operator": "GENTIANS_OPERATOR_METRICS_PATH",
        "quality": "GENTIANS_QUALITY_METRICS_PATH",
        "clingo": "GENTIANS_CLINGO_METRICS_PATH",
    }
    path = os.environ.get(env_paths[kind])
    enriched = {
        "phase": current_phase(),
        "event_id": current_event_id(),
        "wall_time": time.time(),
        **row,
    }
    _append_jsonl(path, enriched)


def set_outer_iteration(outer_iteration: int, iterations_genetic: int) -> None:
    global _outer_iteration, _global_generation_offset
    _outer_iteration = outer_iteration
    _global_generation_offset = outer_iteration * (iterations_genetic + 1)


def record_ga_generation(
    generation: int, scores: list[float], best_so_far: float
) -> None:
    path = os.environ.get("GENTIANS_GA_METRICS_PATH")
    if not path or not scores:
        return
    _ga_rows.append(
        {
            "outer_iteration": _outer_iteration,
            "generation": generation,
            "global_generation": _global_generation_offset + generation,
            "max_fitness": max(scores),
            "avg_fitness": sum(scores) / len(scores),
            "best_so_far": best_so_far,
        }
    )
    _write_json_atomic(path, _ga_rows)


def export() -> None:
    _flush_timings()
    ga_path = os.environ.get("GENTIANS_GA_METRICS_PATH")
    if ga_path:
        _write_json_atomic(ga_path, _ga_rows)


def _flush_timings() -> None:
    path = os.environ.get("GENTIANS_TIMINGS_PATH")
    if not path:
        return
    rows = [
        {"metric": name, "seconds": seconds, "calls": _counts.get(name, 0)}
        for name, seconds in sorted(_totals.items())
    ]
    _write_json_atomic(path, rows)
