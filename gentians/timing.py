import json
import os
import time
from contextlib import contextmanager
from pathlib import Path


_enabled = bool(os.environ.get("GENTIANS_TIMINGS_PATH"))
_totals: dict[str, float] = {}
_counts: dict[str, int] = {}
_stack: list[str] = []
_ga_rows: list[dict[str, float]] = []


def _write_json_atomic(path: str, rows: list[dict[str, float | int]]) -> None:
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


def add(name: str, seconds: float) -> None:
    if not _enabled:
        return
    _totals[name] = _totals.get(name, 0.0) + seconds
    _counts[name] = _counts.get(name, 0) + 1


@contextmanager
def phase(name: str):
    if not _enabled:
        yield
        return
    _stack.append(name)
    start = time.perf_counter()
    try:
        yield
    finally:
        add(name, time.perf_counter() - start)
        _stack.pop()


def current_phase() -> str:
    return _stack[-1] if _stack else "unclassified"


def record_ga_generation(
    generation: int, scores: list[float], best_so_far: float
) -> None:
    path = os.environ.get("GENTIANS_GA_METRICS_PATH")
    if not path or not scores:
        return
    _ga_rows.append(
        {
            "generation": generation,
            "max_fitness": max(scores),
            "avg_fitness": sum(scores) / len(scores),
            "best_so_far": best_so_far,
        }
    )
    _write_json_atomic(path, _ga_rows)


def export() -> None:
    path = os.environ.get("GENTIANS_TIMINGS_PATH")
    if path:
        rows = [
            {"metric": name, "seconds": seconds, "calls": _counts.get(name, 0)}
            for name, seconds in sorted(_totals.items())
        ]
        Path(path).write_text(json.dumps(rows, indent=2), encoding="utf-8")
    ga_path = os.environ.get("GENTIANS_GA_METRICS_PATH")
    if ga_path:
        _write_json_atomic(ga_path, _ga_rows)
