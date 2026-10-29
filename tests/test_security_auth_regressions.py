"""Security regression tests for NOVA private routes.

These tests define the expected boundary: private journal/state reads and
mutations must reject requests without authentication. The purge endpoint must
fail closed when its shared secret is missing.

The tests intentionally do not call production services or use real journal
files. They are expected to fail against the currently inspected route
handlers until the corresponding authentication protections are implemented.
"""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

import core.config
import main


def test_journal_data_rejects_unauthenticated_request():
    response = TestClient(main.app).get("/journal/data")

    assert response.status_code == 401


def test_state_engine_rejects_unauthenticated_request():
    response = TestClient(main.app).get("/state-engine")

    assert response.status_code == 401


def test_journal_reset_rejects_unauthenticated_request_without_writing(monkeypatch):
    original_trades = [
        {"ticker": "MNQ", "trade_mode": "PAPER", "realized_pnl": -10}
    ]
    saved = []
    monkeypatch.setattr(main, "load_journal", lambda: list(original_trades))
    monkeypatch.setattr(main, "save_journal", lambda value: saved.append(value))

    response = TestClient(main.app).post(
        "/journal/reset", json={"confirmation": "RESET_ALL_TRADES"}
    )

    assert response.status_code == 401
    assert saved == []


def test_test_purge_fails_closed_when_shared_secret_is_unset(
    monkeypatch, tmp_path
):
    """An empty header must not authenticate when the configured secret is empty."""
    intelligence_log = tmp_path / "intelligence.jsonl"
    signal_log = tmp_path / "signals.jsonl"
    trace_log = tmp_path / "trace.jsonl"
    sentinel = json.dumps({"id": "keep-me", "kind": "sentinel"}) + "\n"
    for path in (intelligence_log, signal_log, trace_log):
        path.write_text(sentinel, encoding="utf-8")

    monkeypatch.setattr(core.config, "NOVA_INGEST_SECRET", "")
    monkeypatch.setattr(core.config, "INTELLIGENCE_LOG_FILE", intelligence_log)
    monkeypatch.setattr(core.config, "SIGNAL_LOG_FILE", signal_log)
    monkeypatch.setattr(core.config, "TRACE_FILE", trace_log)

    response = TestClient(main.app).post(
        "/api/test/purge",
        headers={"X-Nova-Ingest-Secret": ""},
        json={"ids": ["keep-me"]},
    )

    assert response.status_code == 503
    for path in (intelligence_log, signal_log, trace_log):
        assert path.read_text(encoding="utf-8") == sentinel
