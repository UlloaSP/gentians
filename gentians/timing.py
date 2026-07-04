import atexit
import json
import multiprocessing as mp
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
_timings_dirty = False
_ga_dirty = False
_writer_queue: mp.Queue | None = None
_writer_process: mp.Process | None = None
_F = TypeVar("_F", bound=Callable)
_METRIC_ENV_PATHS = {
    "candidate": "GENTIANS_CANDIDATE_METRICS_PATH",
    "operator": "GENTIANS_OPERATOR_METRICS_PATH",
    "quality": "GENTIANS_QUALITY_METRICS_PATH",
    "clingo": "GENTIANS_CLINGO_METRICS_PATH",
}


def _write_json_atomic_direct(path: str, rows: list[dict[str, object]]) -> None:
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


def _append_jsonl_direct(path: str, row: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def _writer_loop(queue: mp.Queue) -> None:
    while True:
        task = queue.get()
        if task is None:
            return
        kind, path, payload = task
        if kind == "jsonl":
            _append_jsonl_direct(path, payload)
        elif kind == "json":
            _write_json_atomic_direct(path, payload)


def _writer() -> mp.Queue | None:
    global _writer_queue, _writer_process
    if _writer_process is not None and _writer_process.is_alive():
        return _writer_queue
    try:
        queue: mp.Queue = mp.Queue()
        process = mp.Process(target=_writer_loop, args=(queue,), daemon=True)
        process.start()
    except (OSError, RuntimeError):
        return None
    _writer_queue = queue
    _writer_process = process
    return queue


def _close_writer() -> None:
    global _writer_queue, _writer_process
    queue = _writer_queue
    process = _writer_process
    if queue is not None:
        queue.put(None)
        queue.close()
        queue.join_thread()
    if process is not None:
        process.join()
    _writer_queue = None
    _writer_process = None


def _write_json_atomic(path: str, rows: list[dict[str, object]]) -> None:
    queue = _writer()
    if queue is None:
        _write_json_atomic_direct(path, rows)
        return
    queue.put(("json", path, rows))


def _append_jsonl(path: str | None, row: dict[str, Any]) -> None:
    if not path:
        return
    queue = _writer()
    if queue is None:
        _append_jsonl_direct(path, row)
        return
    queue.put(("jsonl", path, row))


def append_jsonl(path: str | None, rows: list[dict[str, object]]) -> None:
    for row in rows:
        _append_jsonl(path, row)


def reset() -> None:
    global _event_counter, _timings_dirty, _ga_dirty
    _close_writer()
    _totals.clear()
    _counts.clear()
    _stack.clear()
    _ga_rows.clear()
    _event_counter = 0
    _timings_dirty = False
    _ga_dirty = False


def set_enabled(enabled: bool) -> None:
    global _enabled
    _enabled = enabled


def merge_timings(rows: list[dict[str, object]]) -> None:
    global _timings_dirty
    for row in rows:
        metric = row.get("metric")
        if not isinstance(metric, str):
            continue
        _totals[metric] = _totals.get(metric, 0.0) + float(row.get("seconds", 0.0))
        _counts[metric] = _counts.get(metric, 0) + int(row.get("calls", 0))
        _timings_dirty = True


def add(name: str, seconds: float) -> None:
    if not _enabled:
        return
    if _stack and not _stack[-1]["instrumenting"]:
        event = _stack[-1]
        event["instrumenting"] = True
        start = time.perf_counter()
        try:
            _record_total(name, seconds)
        finally:
            event["instrumentation_seconds"] += time.perf_counter() - start
            event["instrumenting"] = False
        return
    _record_total(name, seconds)


def _record_total(name: str, seconds: float) -> None:
    global _timings_dirty
    _totals[name] = _totals.get(name, 0.0) + seconds
    _counts[name] = _counts.get(name, 0) + 1
    _timings_dirty = True


@contextmanager
def phase(name: str):
    if not _enabled:
        yield
        return
    global _event_counter
    parent = _stack[-1] if _stack else None
    setup_start = time.perf_counter() if parent else 0.0
    _event_counter += 1
    event = {
        "event_id": _event_counter,
        "parent_id": parent["event_id"] if parent else None,
        "phase": name,
        "depth": len(_stack),
        "started_perf": time.perf_counter(),
        "started_wall": time.time(),
        "child_seconds": 0.0,
        "instrumentation_seconds": 0.0,
        "instrumenting": False,
    }
    _stack.append(event)
    start = time.perf_counter()
    if parent:
        parent["instrumentation_seconds"] += time.perf_counter() - setup_start
    try:
        yield
    finally:
        ended = time.perf_counter()
        raw_seconds = ended - start
        instrumentation_seconds = float(event["instrumentation_seconds"])
        seconds = max(raw_seconds - instrumentation_seconds, 0.0)
        self_seconds = max(seconds - float(event["child_seconds"]), 0.0)
        _record_total(name, seconds)
        _record_total(f"{name}.self", self_seconds)
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
            "raw_seconds": raw_seconds,
            "self_seconds": self_seconds,
            "instrumentation_seconds": instrumentation_seconds,
        }
        parent_event = _stack[-2] if len(_stack) > 1 else None
        finalize_start = time.perf_counter() if parent_event else 0.0
        _append_jsonl(os.environ.get("GENTIANS_TIMING_EVENTS_PATH"), row)
        finalize_overhead = (
            time.perf_counter() - finalize_start if parent_event else 0.0
        )
        _stack.pop()
        if parent_event:
            parent_event["child_seconds"] += seconds
            parent_event["instrumentation_seconds"] += (
                instrumentation_seconds + finalize_overhead
            )


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


@contextmanager
def instrumentation():
    if not _enabled or not _stack:
        yield
        return
    event = _stack[-1]
    if event["instrumenting"]:
        yield
        return
    event["instrumenting"] = True
    start = time.perf_counter()
    try:
        yield
    finally:
        event["instrumentation_seconds"] += time.perf_counter() - start
        event["instrumenting"] = False


def metric_enabled(kind: str) -> bool:
    return bool(os.environ.get(_METRIC_ENV_PATHS[kind]))


def record_metric(kind: str, row: dict[str, Any]) -> None:
    path = os.environ.get(_METRIC_ENV_PATHS[kind])
    if not path:
        return
    with instrumentation():
        enriched = {
            "phase": current_phase(),
            "event_id": current_event_id(),
            "wall_time": time.time(),
            **row,
        }
        _append_jsonl(path, enriched)


def record_ga_generation(
    generation: int,
    best_so_far: float,
    population: list[object],
) -> None:
    path = os.environ.get("GENTIANS_GA_METRICS_PATH")
    if not path or not population:
        return
    with instrumentation():
        global _ga_dirty
        score_total = 0.0
        max_fitness = float("-inf")
        signatures = set()
        invalid = 0
        size_total = 0
        for element in population:
            score = float(getattr(element, "score", 0.0))
            score_total += score
            max_fitness = max(max_fitness, score)
            program = getattr(element, "program", None)
            if program is not None:
                signatures.add(program)
            size_total += len(getattr(element, "program", []))
            if score == float("-inf"):
                invalid += 1
        population_size = len(population)
        unique_signatures = len(signatures)
        _ga_rows.append(
            {
                "generation": generation,
                "global_generation": generation,
                "max_fitness": max_fitness,
                "avg_fitness": score_total / population_size,
                "best_so_far": best_so_far,
                "population_size": population_size,
                "unique_signatures": unique_signatures,
                "diversity": unique_signatures / population_size,
                "invalid_count": invalid,
                "invalid_rate": invalid / population_size,
                "mean_program_size": size_total / population_size,
            }
        )
        _ga_dirty = True


def export() -> None:
    _flush_timings()
    ga_path = os.environ.get("GENTIANS_GA_METRICS_PATH")
    global _ga_dirty
    if ga_path and _ga_dirty:
        _write_json_atomic(ga_path, _ga_rows)
        _ga_dirty = False
    _close_writer()


def _flush_timings() -> None:
    global _timings_dirty
    path = os.environ.get("GENTIANS_TIMINGS_PATH")
    if not path or not _timings_dirty:
        return
    rows = [
        {"metric": name, "seconds": seconds, "calls": _counts.get(name, 0)}
        for name, seconds in sorted(_totals.items())
    ]
    _write_json_atomic(path, rows)
    _timings_dirty = False


atexit.register(_close_writer)
