from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Iterable

ALLOWED_INSTRUMENTS = {"NQ", "MNQ"}
EXPECTED_TIMEZONE = "America/New_York"
EXPECTED_ORB_START = "08:00"
EXPECTED_ORB_END = "08:15"
VALIDITY_CUTOFF = time(10, 30)


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    sample_id: str | None
    message: str


def _event_time(value: str) -> time:
    return datetime.fromisoformat(value).time()


def validate_row(row: dict) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    sid = row.get("sample_id")
    if not sid:
        issues.append(ValidationIssue("MISSING_ID", None, "sample_id is required"))
    if row.get("timezone") != EXPECTED_TIMEZONE:
        issues.append(ValidationIssue("TIMEZONE", sid, "timezone must be America/New_York"))
    if row.get("instrument") not in ALLOWED_INSTRUMENTS:
        issues.append(ValidationIssue("INSTRUMENT", sid, "instrument must be NQ or MNQ"))
    if row.get("orb_start") != EXPECTED_ORB_START or row.get("orb_end") != EXPECTED_ORB_END:
        issues.append(ValidationIssue("ORB_WINDOW", sid, "ORB must be 08:00-08:15 ET"))

    high = row.get("orb_high")
    low = row.get("orb_low")
    mid = row.get("orb_mid")
    if high is None or low is None or mid is None:
        issues.append(ValidationIssue("ORB_PRICES", sid, "orb_high/orb_low/orb_mid are required"))
    else:
        if high < low:
            issues.append(ValidationIssue("ORB_ORDER", sid, "orb_high must be >= orb_low"))
        expected_mid = (high + low) / 2.0
        if abs(mid - expected_mid) > 1e-9:
            issues.append(ValidationIssue("ORB_MID", sid, "orb_mid must equal midpoint"))

    if not row.get("source_hash_or_reference"):
        issues.append(ValidationIssue("PROVENANCE", sid, "source reference/hash is required"))
    if row.get("label_method") not in {"deterministic", "human-confirmed"}:
        issues.append(ValidationIssue("LABEL_METHOD", sid, "invalid label method"))

    event_ts = row.get("event_timestamp")
    if event_ts:
        try:
            after_cutoff = _event_time(event_ts) > VALIDITY_CUTOFF
        except ValueError:
            issues.append(ValidationIssue("EVENT_TIME", sid, "event_timestamp must be ISO-8601"))
        else:
            if after_cutoff and not row.get("after_1030_excluded"):
                issues.append(ValidationIssue("CUTOFF", sid, "post-10:30 event must be excluded"))
            if after_cutoff and row.get("inside_valid_window"):
                issues.append(ValidationIssue("WINDOW_FLAG", sid, "post-10:30 event cannot be valid"))
    return issues

def validate_dataset(rows: Iterable[dict]) -> list[ValidationIssue]:
    rows = list(rows)
    issues: list[ValidationIssue] = []
    seen: set[str] = set()
    for row in rows:
        sid = row.get("sample_id")
        if sid and sid in seen:
            issues.append(ValidationIssue("DUPLICATE_ID", sid, "sample_id must be unique"))
        if sid:
            seen.add(sid)
        issues.extend(validate_row(row))
    return issues
