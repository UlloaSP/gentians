import json
import sys

from benchmarks.profile_hypothesis import main


def test_profile_hypothesis_runs_standalone(monkeypatch, tmp_path):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "profile_hypothesis.py",
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
