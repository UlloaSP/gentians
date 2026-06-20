from __future__ import annotations

from pathlib import Path

import pytest


def main() -> int:
    test_file = str(Path(__file__).with_name("benchmarking.py"))
    return pytest.main([test_file, "--benchmark-compare"])


if __name__ == "__main__":
    raise SystemExit(main())
