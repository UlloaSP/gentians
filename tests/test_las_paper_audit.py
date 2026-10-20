import subprocess
import sys

import pytest

from tools.validate_las_papers import audit, progress_rows, run_bounded


def test_parse_audit_records_each_failure_and_continues(tmp_path, capsys):
    bad, good = tmp_path / "bad.las", tmp_path / "good.las"
    bad.write_text("#constant(t,a).", encoding="utf-8")
    good.write_text("#modeh(h). #pos(e,{h},{}).", encoding="utf-8")
    rows = audit("fastlas2", [bad, good], parse_only=True)
    assert [row["status"] for row in rows] == ["error", "ok"]
    assert rows[1]["examples"] == 1
    assert "unsupported FastLAS directive" in rows[0]["error"]
    assert len(capsys.readouterr().out.splitlines()) == 2


def test_partial_last_progress_line_does_not_erase_completed_windows():
    assert progress_rows('{"status":"ok","window":1}\n{"window":') == [{"status": "ok", "window": 1}]


def test_timeout_kills_worker_descendants(tmp_path):
    marker = tmp_path / "escaped-worker.txt"
    child = f"import time; from pathlib import Path; time.sleep(3); Path({str(marker)!r}).write_text('escaped')"
    parent = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child!r}]); time.sleep(30)"
    with pytest.raises(subprocess.TimeoutExpired):
        run_bounded([sys.executable, "-c", parent], timeout=1)
    assert not marker.exists()
