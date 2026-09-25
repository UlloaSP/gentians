import json
import sys
from pathlib import Path

from benchmarks import profile_clauses
from benchmarks.profile_clauses import main
from gentians.clauses import ClauseSpace


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


def test_profile_clauses_loads_all_alzheimer_tasks(monkeypatch, tmp_path):
    seen = []

    def capture(task, arguments):
        seen.append((arguments.filename, len(task.positive_examples)))
        return ClauseSpace(()), {"timings": [], "clingoMetrics": []}

    monkeypatch.setattr(profile_clauses, "build_profiled_clause_space", capture)
    monkeypatch.setattr(
        sys, "argv",
        ["profile_clauses.py", "--datasets", "alzheimer", "--out-dir", str(tmp_path)],
    )

    main()

    assert [(Path(filename).name, count) for filename, count in seen] == [
        ("alzheimer_acetyl", 530),
        ("alzheimer_amine", 274),
        ("alzheimer_mem", 256),
        ("alzheimer_toxic", 354),
    ]
    assert {path.stem for path in tmp_path.glob("*.json")} == {
        "alzheimer_acetyl", "alzheimer_amine", "alzheimer_mem", "alzheimer_toxic"
    }
