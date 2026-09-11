from __future__ import annotations

from datetime import date
import json
import sys
import types

import pytest

from tools import databento_orb_probe as probe


def test_dry_run_uses_bounded_current_orb_window_and_continuous_symbols():
    result = probe.build_probe(date(2026, 9, 8), date(2026, 9, 8), ("NQ", "MNQ"))
    assert result["mode"] == "dry_run"
    assert result["dataset"] == "GLBX.MDP3"
    assert result["schema"] == "ohlcv-1m"
    assert result["stype_in"] == "continuous"
    assert result["symbols"] == ["NQ.v.0", "MNQ.v.0"]
    assert result["windows"] == [{
        "session_date": "2026-09-08",
        "start_utc": "2026-09-08T12:00:00+00:00",
        "end_utc": "2026-09-08T14:30:00+00:00",
    }]


def test_dst_conversion_and_weekend_skip_are_deterministic():
    result = probe.build_probe(date(2026, 1, 2), date(2026, 1, 5), ("NQ",))
    assert [w["session_date"] for w in result["windows"]] == ["2026-01-02", "2026-01-05"]
    assert result["windows"][0]["start_utc"] == "2026-01-02T13:00:00+00:00"
    assert result["windows"][0]["end_utc"] == "2026-01-02T15:30:00+00:00"


def test_invalid_range_and_instrument_fail_locally():
    with pytest.raises(ValueError, match="end date"):
        probe.build_probe(date(2026, 9, 9), date(2026, 9, 8), ("NQ",))
    with pytest.raises(ValueError, match="unsupported instrument"):
        probe.build_probe(date(2026, 9, 8), date(2026, 9, 8), ("ES",))


def test_source_contains_no_download_call():
    source = probe.__file__
    text = open(source, encoding="utf-8").read()
    assert "timeseries.get_range" not in text
    assert "batch.submit_job" not in text


def test_estimate_cost_requires_key(monkeypatch):
    monkeypatch.delenv("DATABENTO_API_KEY", raising=False)
    payload = probe.build_probe(date(2026, 9, 8), date(2026, 9, 8), ("NQ",))
    with pytest.raises(RuntimeError, match="DATABENTO_API_KEY"):
        probe._estimate_cost(payload)


def test_estimate_cost_uses_metadata_only(monkeypatch):
    calls = []
    class FakeMetadata:
        def get_cost(self, **kwargs):
            calls.append(kwargs)
            return 0.125
    class FakeHistorical:
        def __init__(self):
            self.metadata = FakeMetadata()
    monkeypatch.setenv("DATABENTO_API_KEY", "db-test")
    monkeypatch.setitem(sys.modules, "databento", types.SimpleNamespace(Historical=FakeHistorical))
    payload = probe.build_probe(date(2026, 9, 8), date(2026, 9, 9), ("NQ", "MNQ"))
    result = probe._estimate_cost(payload)
    assert result["mode"] == "cost_estimate"
    assert result["estimated_total_usd"] == 0.25
    assert len(calls) == 2
    assert all(call["schema"] == "ohlcv-1m" for call in calls)
    assert all(call["stype_in"] == "continuous" for call in calls)
