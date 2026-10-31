import random
from importlib import import_module
from types import SimpleNamespace

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "rng(seed): replay every search of the test from a fixed RNG")


@pytest.fixture(autouse=True)
def fixed_search_rng(request, monkeypatch):
    """Inject the RNG: production searches always draw a fresh one."""
    marker = request.node.get_closest_marker("rng")
    if marker is None:
        return
    fixed = SimpleNamespace(Random=lambda: random.Random(marker.args[0]))
    for name in ("steady_state_genetic", "incremental_clause_genetic"):
        monkeypatch.setattr(import_module(f"gentians.algorithms.{name}"), "random", fixed)
