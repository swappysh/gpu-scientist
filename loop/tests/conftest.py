"""Tests run offline on synthetic step-shaped series, never the real pack."""

import pytest

from pacific_hack import harness


@pytest.fixture(autouse=True)
def synthetic_data(monkeypatch):
    monkeypatch.setenv(harness.DATA_ENV, "synthetic")
