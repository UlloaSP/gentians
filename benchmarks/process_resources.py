"""Worker-process resource snapshots, retained even after an external timeout."""

import ctypes
import json
import os
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from gentians.timing import current_phase, last_search_progress


def peak_rss_bytes() -> int:
    """OS high-water resident memory for this worker, excluding its launcher."""
    if os.name == "nt":
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                *[(name, ctypes.c_size_t) for name in (
                    "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                    "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                    "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage",
                )],
            ]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD,
        ]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(
            kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb,
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return counters.PeakWorkingSetSize
    import resource

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


@contextmanager
def record_process_resources(path: Path):
    """Sample every 200 ms; final=False identifies a censored timeout snapshot."""
    stop = threading.Event()
    started = time.perf_counter()

    def write(final: bool) -> None:
        snapshot = {
            "pid": os.getpid(), "peak_rss_bytes": peak_rss_bytes(),
            "cpu_seconds": time.process_time(),
            "sample_elapsed_seconds": time.perf_counter() - started,
            "final": final,
            "search_progress": last_search_progress(),
            "sampling_phase": current_phase(),
        }
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(snapshot), encoding="utf-8")
        for attempt in range(20):
            try:
                temporary.replace(path)
                return
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.05)

    def sample() -> None:
        while not stop.wait(0.2):
            write(False)

    write(False)
    thread = threading.Thread(target=sample, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join()
        write(True)
