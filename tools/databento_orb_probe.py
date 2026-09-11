"""Dry-run/cost probe for future NQ/MNQ ORB historical data requests.

This module never downloads market data. Default mode is pure local JSON.
`--estimate-cost` may call Databento metadata.get_cost only.
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

DATASET = "GLBX.MDP3"
SCHEMA = "ohlcv-1m"
STYPE_IN = "continuous"
ET = ZoneInfo("America/New_York")
SYMBOLS = {"NQ": "NQ.v.0", "MNQ": "MNQ.v.0"}


@dataclass(frozen=True)
class ProbeWindow:
    session_date: str
    start_utc: str
    end_utc: str


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _business_dates(start: date, end: date) -> list[date]:
    if end < start:
        raise ValueError("end date must be on or after start date")
    out: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            out.append(current)
        current += timedelta(days=1)
    return out


def _window_for_day(day: date) -> ProbeWindow:
    start_et = datetime.combine(day, time(8, 0), tzinfo=ET)
    end_et = datetime.combine(day, time(10, 30), tzinfo=ET)
    return ProbeWindow(
        session_date=day.isoformat(),
        start_utc=start_et.astimezone(timezone.utc).isoformat(),
        end_utc=end_et.astimezone(timezone.utc).isoformat(),
    )


def build_probe(start: date, end: date, instruments: tuple[str, ...]) -> dict:
    unknown = [name for name in instruments if name not in SYMBOLS]
    if unknown:
        raise ValueError(f"unsupported instrument(s): {', '.join(unknown)}")
    windows = [_window_for_day(day) for day in _business_dates(start, end)]
    return {
        "mode": "dry_run",
        "dataset": DATASET,
        "schema": SCHEMA,
        "stype_in": STYPE_IN,
        "symbols": [SYMBOLS[name] for name in instruments],
        "windows": [asdict(window) for window in windows],
        "notes": [
            "08:00-10:30 America/New_York only; end is exclusive at provider API level.",
            "Weekends are skipped locally; CME holidays are not removed by this probe.",
            "Continuous symbols use volume-ranked lead contracts and retain unadjusted prices.",
            "This probe contains no historical-data download path.",
        ],
    }


def _estimate_cost(probe: dict) -> dict:
    if not os.getenv("DATABENTO_API_KEY"):
        raise RuntimeError("DATABENTO_API_KEY is required for --estimate-cost")
    try:
        import databento as db
    except ImportError as exc:
        raise RuntimeError("databento package is required for --estimate-cost") from exc

    client = db.Historical()
    total = 0.0
    estimates: list[dict] = []
    for window in probe["windows"]:
        cost = client.metadata.get_cost(
            dataset=probe["dataset"],
            start=window["start_utc"],
            end=window["end_utc"],
            symbols=probe["symbols"],
            schema=probe["schema"],
            stype_in=probe["stype_in"],
        )
        estimates.append({"session_date": window["session_date"], "estimated_usd": float(cost)})
        total += float(cost)
    result = dict(probe)
    result["mode"] = "cost_estimate"
    result["cost_estimates"] = estimates
    result["estimated_total_usd"] = round(total, 6)
    return result


def _instrument_tuple(raw: str) -> tuple[str, ...]:
    if raw == "both":
        return ("NQ", "MNQ")
    return (raw.upper(),)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or cost-estimate bounded ORB historical requests.")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--instrument", choices=("NQ", "MNQ", "both"), default="both")
    parser.add_argument("--estimate-cost", action="store_true")
    args = parser.parse_args(argv)

    probe = build_probe(
        _parse_date(args.start_date),
        _parse_date(args.end_date),
        _instrument_tuple(args.instrument),
    )
    if args.estimate_cost:
        probe = _estimate_cost(probe)
    print(json.dumps(probe, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
