from tools.orb_dataset_validator import validate_dataset, validate_row


def base_row(**overrides):
    row = {
        "sample_id": "2026-09-01-MNQ-001",
        "session_date": "2026-09-01",
        "timezone": "America/New_York",
        "instrument": "MNQ",
        "source_dataset": "bars.csv",
        "source_hash_or_reference": "sha256:abc",
        "label_method": "deterministic",
        "review_status": "pending",
        "orb_start": "08:00",
        "orb_end": "08:15",
        "orb_high": 100.0,
        "orb_low": 90.0,
        "orb_mid": 95.0,
        "range_points": 10.0,
        "range_complete": True,
        "event_timestamp": "2026-09-01T09:45:00",
        "event_side": "LONG",
        "inside_valid_window": True,
        "after_1030_excluded": False,
    }
    row.update(overrides)
    return row


def codes(issues):
    return {issue.code for issue in issues}

def test_valid_row_passes():
    assert validate_row(base_row()) == []


def test_wrong_instrument_fails():
    assert "INSTRUMENT" in codes(validate_row(base_row(instrument="SPY")))


def test_wrong_orb_window_fails():
    assert "ORB_WINDOW" in codes(validate_row(base_row(orb_start="09:30")))


def test_midpoint_must_match():
    assert "ORB_MID" in codes(validate_row(base_row(orb_mid=94.5)))


def test_post_1030_must_be_excluded():
    issues = validate_row(base_row(event_timestamp="2026-09-01T10:31:00"))
    assert {"CUTOFF", "WINDOW_FLAG"} <= codes(issues)


def test_post_1030_excluded_row_passes_cutoff_checks():
    issues = validate_row(base_row(
        event_timestamp="2026-09-01T10:31:00",
        inside_valid_window=False,
        after_1030_excluded=True,
    ))
    assert "CUTOFF" not in codes(issues)
    assert "WINDOW_FLAG" not in codes(issues)

def test_missing_provenance_fails():
    assert "PROVENANCE" in codes(validate_row(base_row(source_hash_or_reference="")))


def test_bad_label_method_fails():
    assert "LABEL_METHOD" in codes(validate_row(base_row(label_method="model-guessed")))


def test_duplicate_ids_fail_dataset():
    rows = [base_row(), base_row()]
    assert "DUPLICATE_ID" in codes(validate_dataset(rows))


def test_malformed_event_time_fails():
    assert "EVENT_TIME" in codes(validate_row(base_row(event_timestamp="not-a-time")))
