import json
import sys

from benchmarks.profile_clauses import main


def test_profile_clauses_runs_standalone(monkeypatch, tmp_path):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "profile_clauses.py",
            "--datasets",
            "grandparent",
            "--out-dir",
            str(tmp_path),
        ],
    )

    main()

    payload = json.loads((tmp_path / "grandparent.json").read_text(encoding="utf-8"))
    assert payload["entries"]
    assert payload["metrics"]["timings"]
    assert payload["metrics"]["clingoMetrics"]
