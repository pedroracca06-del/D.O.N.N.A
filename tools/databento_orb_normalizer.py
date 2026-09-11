from __future__ import annotations

import csv
import hashlib
from collections import defaultdict
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
ORB_START = time(8, 0)
ORB_END = time(8, 15)


class OrbNormalizationError(ValueError):
    pass


def _instrument(symbol: str) -> str:
    value = symbol.upper().strip()
    if value.startswith("MNQ"):
        return "MNQ"
    if value.startswith("NQ"):
        return "NQ"
    raise OrbNormalizationError(f"unsupported symbol: {symbol}")


def _parse_ts(value: str) -> datetime:
    ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if ts.tzinfo is None:
        raise OrbNormalizationError("ts_event must include timezone/UTC offset")
    return ts.astimezone(ET)


def normalize_csv(path: str | Path) -> list[dict]:
    source = Path(path)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    with source.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        required = {"ts_event", "open", "high", "low", "close", "volume", "symbol"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            missing = sorted(required - set(reader.fieldnames or []))
            raise OrbNormalizationError(f"missing columns: {', '.join(missing)}")
        for row in reader:
            ts_et = _parse_ts(row["ts_event"])
            t = ts_et.time().replace(tzinfo=None)
            if ORB_START <= t < ORB_END:
                inst = _instrument(row["symbol"])
                row["_ts_et"] = ts_et
                groups[(inst, ts_et.date().isoformat())].append(row)

    output: list[dict] = []
    for (inst, session_date), rows in sorted(groups.items()):
        minutes = {r["_ts_et"].strftime("%H:%M") for r in rows}
        expected = {f"08:{m:02d}" for m in range(15)}
        if minutes != expected or len(rows) != 15:
            raise OrbNormalizationError(
                f"{inst} {session_date} incomplete ORB bars: expected 15 unique minutes, got {len(rows)}"
            )
        high = max(float(r["high"]) for r in rows)
        low = min(float(r["low"]) for r in rows)
        output.append({
            "sample_id": f"{inst}-{session_date}",
            "instrument": inst,
            "timezone": "America/New_York",
            "orb_start": "08:00",
            "orb_end": "08:15",
            "orb_high": high,
            "orb_low": low,
            "orb_mid": (high + low) / 2.0,
            "event_timestamp": f"{session_date}T08:15:00",
            "inside_valid_window": True,
            "after_1030_excluded": False,
            "label_method": "deterministic",
            "source_hash_or_reference": f"sha256:{source_hash}",
        })
    return output
