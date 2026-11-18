"""Test-wide configuration overrides."""

from __future__ import annotations

import pytest

from app.deps import settings as deps_settings


@pytest.fixture(autouse=True)
def disable_shared_access_code(monkeypatch):
    """Unit/API tests exercise the open-access behaviour by default."""
    monkeypatch.setattr(deps_settings, "app_access_code", "")
