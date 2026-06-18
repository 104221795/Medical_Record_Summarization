from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_optional_local_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the full suite independent of developer-only model settings."""

    monkeypatch.setenv("RUN_REAL_BASELINES", "0")
    monkeypatch.setenv("RAG_RUN_REAL_BASELINES", "0")
    monkeypatch.setenv("MLFLOW_ALLOW_FILE_STORE", "true")
