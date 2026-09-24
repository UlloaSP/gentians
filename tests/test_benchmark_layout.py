from pathlib import Path

from benchmarks.catalog import CASES, DATASETS
from benchmarks.run_experiments import execution_inputs
from gentians.language import parse_file


def test_every_catalog_task_has_separate_background_examples_bias_and_readme():
    directories = {Path(arguments.filename) for arguments in CASES.values()}

    assert directories == {path for path in DATASETS.iterdir() if path.is_dir()}
    for directory in directories:
        assert {path.name for path in directory.iterdir()} == {
            "bk.lp", "exs.lp", "bias.lp", "README.md"
        }
        parse_file(str(directory))


def test_experiment_fingerprint_uses_selected_task_parts_only():
    files = execution_inputs({"datasets": ["coin"], "overrides": {}})["files"]
    coin = DATASETS / "coin"
    unrelated = DATASETS / "alzheimer_amine"

    assert all(str(coin / name) in files for name in ("bk.lp", "exs.lp", "bias.lp"))
    assert str(coin / "README.md") not in files
    assert str(unrelated / "bk.lp") not in files
