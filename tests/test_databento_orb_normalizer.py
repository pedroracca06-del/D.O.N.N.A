import csv
from datetime import datetime, timedelta, timezone

import pytest

from tools.databento_orb_normalizer import OrbNormalizationError, normalize_csv
from tools.orb_dataset_validator import validate_dataset


def _write_csv(path, *, symbol="NQU6", count=15):
    fields = ["ts_event", "open", "high", "low", "close", "volume", "symbol"]
    start = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for i in range(count):
            px = 25000.0 + i
            writer.writerow({
                "ts_event": (start + timedelta(minutes=i)).isoformat(),
                "open": px, "high": px + 2, "low": px - 1,
                "close": px + 1, "volume": 100 + i, "symbol": symbol,
            })


def test_complete_databento_window_normalizes_and_validates(tmp_path):
    path = tmp_path / "bars.csv"
    _write_csv(path)
    rows = normalize_csv(path)
    assert len(rows) == 1
    assert rows[0]["sample_id"] == "NQ-2026-09-08"
    assert rows[0]["orb_high"] == 25016.0
    assert rows[0]["orb_low"] == 24999.0
    assert validate_dataset(rows) == []


def test_incomplete_orb_window_fails_closed(tmp_path):
    path = tmp_path / "bars.csv"
    _write_csv(path, count=14)
    with pytest.raises(OrbNormalizationError, match="incomplete ORB bars"):
        normalize_csv(path)


def test_unsupported_symbol_is_rejected(tmp_path):
    path = tmp_path / "bars.csv"
    _write_csv(path, symbol="ESU6")
    with pytest.raises(OrbNormalizationError, match="unsupported symbol"):
        normalize_csv(path)


def test_source_provenance_is_content_hash(tmp_path):
    path = tmp_path / "bars.csv"
    _write_csv(path, symbol="MNQU6")
    row = normalize_csv(path)[0]
    assert row["sample_id"] == "MNQ-2026-09-08"
    assert row["source_hash_or_reference"].startswith("sha256:")
    assert len(row["source_hash_or_reference"].split(":", 1)[1]) == 64
