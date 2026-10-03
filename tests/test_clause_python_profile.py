import cProfile
import os
import pstats
from types import SimpleNamespace

import pytest

from benchmarks import clause_python_profile
from gentians import timing
from gentians.arguments import Arguments
from gentians.clauses import generate_clause_space
from gentians.clauses.canonicalization.canonical_clause import CanonicalArithmeticClause
from gentians.clauses.reified_clause import ReifiedClause
from gentians.clauses.reified_literal import ReifiedLiteral
from gentians.language import parse_text


def test_profile_keeps_distinct_generated_constructors_and_all_self_time(tmp_path):
    def construct():
        for _ in range(10):
            literal = ReifiedLiteral("head", 0, 1, ())
            clause = ReifiedClause((literal,), ())
            CanonicalArithmeticClause(clause.head, clause.body, ())

    profiler = cProfile.Profile()
    profiler.runcall(construct)
    stats = clause_python_profile.profile_stats(profiler)
    path = tmp_path / "constructors.prof"
    stats.dump_stats(str(path))
    restored = pstats.Stats(str(path))

    assert sum(row[2] for row in restored.stats.values()) == pytest.approx(
        sum(entry.inlinetime for entry in profiler.getstats())
    )
    for cls in (ReifiedLiteral, ReifiedClause, CanonicalArithmeticClause):
        rows = [row for key, row in restored.stats.items() if key[2] == f"{cls.__name__}.__init__"]
        assert len(rows) == 1
        assert rows[0][1] == 10
    assert any(row[4] for row in restored.stats.values())


def test_function_self_times_partition_without_double_counting_callees():
    stats = SimpleNamespace(stats={
        ("/gentians/clauses/decoder.py", 69, "_clause_from_model"): (5, 5, 1.0, 12.0, {}),
        ("/gentians/clauses/canonicalization/arithmetic.py", 32, "canonical_arithmetic_clause"):
            (5, 5, 2.0, 8.0, {}),
        ("/gentians/clauses/canonicalization/clauses.py", 24, "add"): (5, 5, 3.0, 20.0, {}),
        ("/gentians/clauses/clause_space.py", 9, "__init__"): (1, 1, 4.0, 6.0, {}),
        ("/clingo/symbol.py", 100, "arguments"): (7, 7, 0.5, 1.0, {}),
        ("~", 0, "<built-in method _clingo.clingo_control_ground>"): (1, 1, 10.0, 10.0, {}),
        ("~", 0, "<built-in method _clingo.clingo_control_solve>"): (1, 1, 20.0, 50.0, {}),
    })

    summary = clause_python_profile.summarize_profile(stats)

    assert summary["functionSelfSeconds"] == 40.5
    assert summary["pythonAndBindingsSelfSeconds"] == 10.5
    assert summary["decodeCalls"] == 5
    assert sum(row["selfSeconds"] for row in summary["buckets"]) == 40.5
    assert sum(row["selfSeconds"] for row in summary["functions"]) == 40.5
    assert sum(row["cumulativeSeconds"] for row in summary["functions"]) > 40.5


def test_metadata_construction_keeps_its_profile_bucket_after_helper_change():
    source = "/gentians/clauses/canonicalization/clauses.py"
    assert clause_python_profile.function_bucket(source, "_clause_metadata") == "construction"
    assert clause_python_profile.function_bucket(source, "finish") == "canonical_storage"


def test_python_profile_preserves_arithmetic_space_and_captures_every_model(tmp_path):
    task = parse_text(
        "d(1..3). #maxv(3). #maxbl(3). #maxhl(1). "
        "#modeh(1,p(var(numeric,input))). "
        "#modeb(3,d(var(numeric,output))). "
        "#modeb(1,var(numeric)+var(numeric)=var(numeric))."
    )
    arguments = Arguments()
    expected = generate_clause_space(task, arguments)

    summary = clause_python_profile.profile_clause_python(
        task, arguments, expected, None, tmp_path / "arithmetic.prof",
    )

    assert summary["clauses"] == len(expected)
    assert summary["decodeCalls"] >= len(expected)
    assert any(row["bucket"] == "canonicalization" and row["calls"] for row in summary["buckets"])
    assert sum(row["selfSeconds"] for row in summary["buckets"]) == pytest.approx(
        sum(row["selfSeconds"] for row in summary["functions"])
    )


def test_python_profile_rejects_missing_callback_coverage(tmp_path):
    task = parse_text("#maxv(0). #maxbl(0). #modeh(1,p).")
    arguments = Arguments()
    expected = generate_clause_space(task, arguments)

    with pytest.raises(RuntimeError, match="model callbacks"):
        clause_python_profile.profile_clause_python(
            task, arguments, expected, 999, tmp_path / "incomplete.prof",
        )
    assert (tmp_path / "incomplete.prof").exists()
    assert not (tmp_path / "incomplete.json").exists()


def test_python_profile_rejects_a_changed_clause_space(tmp_path):
    task = parse_text("#maxv(0). #maxbl(0). #modeh(1,p).")
    different = generate_clause_space(parse_text("#maxv(0). #maxbl(0)."), Arguments())

    with pytest.raises(RuntimeError, match="different ClauseSpace"):
        clause_python_profile.profile_clause_python(
            task, Arguments(), different, None, tmp_path / "changed.prof",
        )


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("clingo_path", [None, "original.jsonl"])
def test_python_profile_restores_instrumentation_after_failure(monkeypatch, enabled, clingo_path, tmp_path):
    previous_enabled = timing.is_enabled()
    if clingo_path is None:
        monkeypatch.delenv("GENTIANS_CLINGO_METRICS_PATH", raising=False)
    else:
        monkeypatch.setenv("GENTIANS_CLINGO_METRICS_PATH", clingo_path)

    def fail(task, arguments):
        assert not timing.is_enabled()
        assert not timing.metric_enabled("clingo")
        raise RuntimeError("generation failed")

    monkeypatch.setattr(clause_python_profile, "generate_clause_space", fail)
    try:
        timing.set_enabled(enabled)
        with pytest.raises(RuntimeError, match="generation failed"):
            clause_python_profile.profile_clause_python(None, None, None, None, tmp_path / "failed.prof")
        assert timing.is_enabled() is enabled
        assert os.environ.get("GENTIANS_CLINGO_METRICS_PATH") == clingo_path
    finally:
        timing.set_enabled(previous_enabled)
