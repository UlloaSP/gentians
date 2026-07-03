import json
import os
import queue
import threading
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
_write_queue: "queue.Queue[tuple[str | None, dict[str, Any] | threading.Event] | None]" = queue.Queue()
_writer_thread: threading.Thread | None = None
_writer_lock = threading.Lock()
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
    _start_writer()
    _write_queue.put((path, row))


def _start_writer() -> None:
    global _writer_thread
    if _writer_thread is not None:
        return
    with _writer_lock:
        if _writer_thread is None:
            _writer_thread = threading.Thread(target=_writer_loop, daemon=True)
            _writer_thread.start()


def _writer_loop() -> None:
    handles: dict[str, Any] = {}
    try:
        while True:
            item = _write_queue.get()
            try:
                if item is None:
                    return
                path, row = item
                if path is None:
                    for handle in handles.values():
                        handle.flush()
                    assert isinstance(row, threading.Event)
                    row.set()
                    continue
                assert isinstance(row, dict)
                handle = handles.get(path)
                if handle is None:
                    target = Path(path)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    handle = target.open("a", encoding="utf-8")
                    handles[path] = handle
                handle.write(json.dumps(row, sort_keys=True) + "\n")
            finally:
                _write_queue.task_done()
    finally:
        for handle in handles.values():
            handle.flush()
            handle.close()


def _flush_async_writes() -> None:
    global _writer_thread
    if _writer_thread is None:
        return
    flushed = threading.Event()
    _write_queue.put((None, flushed))
    flushed.wait()
    _write_queue.join()
    _write_queue.put(None)
    _write_queue.join()
    _writer_thread.join()
    _writer_thread = None


def add(name: str, seconds: float) -> None:
    if not _enabled:
        return
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
    _event_counter += 1
    parent = _stack[-1] if _stack else None
    event = {
        "event_id": _event_counter,
        "parent_id": parent["event_id"] if parent else None,
        "phase": name,
        "depth": len(_stack),
        "started_perf": time.perf_counter(),
        "started_wall": time.time(),
        "child_seconds": 0.0,
    }
    _stack.append(event)
    start = time.perf_counter()
    try:
        yield
    finally:
        ended = time.perf_counter()
        seconds = ended - start
        self_seconds = max(seconds - float(event["child_seconds"]), 0.0)
        add(name, seconds)
        add(f"{name}.self", self_seconds)
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
            "self_seconds": self_seconds,
        }
        _append_jsonl(os.environ.get("GENTIANS_TIMING_EVENTS_PATH"), row)
        _stack.pop()
        if _stack:
            _stack[-1]["child_seconds"] += seconds


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
    if not path:
        return
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
    global _ga_dirty
    scores = [float(getattr(element, "score", 0.0)) for element in population]
    row = {
        "generation": generation,
        "global_generation": generation,
        "max_fitness": max(scores),
        "avg_fitness": sum(scores) / len(scores),
        "best_so_far": best_so_far,
    }
    signatures = [getattr(element, "signature", None) for element in population]
    valid_signatures = [signature for signature in signatures if signature is not None]
    sizes = [len(getattr(element, "program", [])) for element in population]
    invalid = sum(
        1 for element in population if getattr(element, "score", 0.0) == float("-inf")
    )
    row.update(
        {
            "population_size": len(population),
            "unique_signatures": len(set(valid_signatures)),
            "diversity": len(set(valid_signatures)) / len(population),
            "invalid_count": invalid,
            "invalid_rate": invalid / len(population),
            "mean_program_size": sum(sizes) / len(sizes) if sizes else 0.0,
        }
    )
    _ga_rows.append(row)
    _ga_dirty = True


def export() -> None:
    _flush_async_writes()
    _flush_timings()
    ga_path = os.environ.get("GENTIANS_GA_METRICS_PATH")
    global _ga_dirty
    if ga_path and _ga_dirty:
        _write_json_atomic(ga_path, _ga_rows)
        _ga_dirty = False


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
