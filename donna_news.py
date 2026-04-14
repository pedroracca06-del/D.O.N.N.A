from __future__ import annotations

from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import json
import requests
import xml.etree.ElementTree as ET

# ==================================================
# ENV / PATHS
# ==================================================
BASE_DIR = Path(__file__).parent
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

RISK_STATE_FILE = BASE_DIR / "donna_risk_state.json"

NY_TZ = ZoneInfo("America/New_York")
UTC_TZ = ZoneInfo("UTC")

FOREX_FACTORY_XML = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"

# ==================================================
# RED FOLDER FILTERS
# ==================================================
HIGH_IMPACT_KEYWORDS = [
    "cpi",
    "core cpi",
    "ppi",
    "core ppi",
    "nfp",
    "non-farm",
    "powell",
    "fomc",
    "fed",
    "interest rate",
    "rate decision",
    "gdp",
    "retail sales",
    "unemployment",
    "jobless claims",
    "ism",
    "pce",
    "core pce",
    "minutes",
]

# ==================================================
# HELPERS
# ==================================================
def now_ny() -> datetime:
    return datetime.now(NY_TZ)


def now_iso() -> str:
    return datetime.now(UTC_TZ).isoformat()


def load_state() -> dict:
    default_state = {
        "macro_risk": "low",
        "headline_risk": "low",
        "market_news_risk": "low",
        "active_warnings": [],
        "next_event": "",
        "minutes_to_event": None,
        "last_headline": "",
        "last_market_headline": "",
        "last_updated": "",
    }

    try:
        if not RISK_STATE_FILE.exists():
            return default_state

        with open(RISK_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return default_state

        merged = {**default_state, **data}

        if not isinstance(merged.get("active_warnings"), list):
            merged["active_warnings"] = []

        return merged

    except Exception:
        return default_state


def save_state(state: dict) -> None:
    state["last_updated"] = now_iso()

    with open(RISK_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def contains_high_impact(title: str) -> bool:
    text = title.lower()
    return any(word in text for word in HIGH_IMPACT_KEYWORDS)


# ==================================================
# FOREX FACTORY FETCH
# ==================================================
def fetch_calendar_events() -> list[dict]:
    response = requests.get(FOREX_FACTORY_XML, timeout=20)
    response.raise_for_status()

    root = ET.fromstring(response.content)

    events = []

    for item in root.findall("event"):
        try:
            title = (item.findtext("title") or "").strip()
            country = (item.findtext("country") or "").strip()
            impact = (item.findtext("impact") or "").strip().lower()
            date_text = (item.findtext("date") or "").strip()
            time_text = (item.findtext("time") or "").strip()

            if not title or not date_text:
                continue

            # Example date format can vary slightly, so keep robust
            dt_raw = f"{date_text} {time_text}".strip()

            event_dt = parse_event_datetime(dt_raw)
            if not event_dt:
                continue

            events.append({
                "title": title,
                "country": country,
                "impact": impact,
                "datetime": event_dt,
            })

        except Exception:
            continue

    return events


def parse_event_datetime(raw: str):
    formats = [
        "%m-%d-%Y %I:%M%p",
        "%m-%d-%Y %H:%M",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %I:%M%p",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.replace(tzinfo=NY_TZ)
        except Exception:
            pass

    return None

# ==================================================
# EVENT ENGINE
# ==================================================
def get_priority_events(events: list[dict]) -> list[dict]:
    out = []

    for e in events:
        title = e["title"]
        impact = e["impact"]

        if impact == "high" or contains_high_impact(title):
            out.append(e)

    return sorted(out, key=lambda x: x["datetime"])


def find_next_event(events: list[dict]):
    now = now_ny()

    future = [e for e in events if e["datetime"] >= now]

    if not future:
        return None

    return future[0]


def build_macro_state(next_event: dict | None) -> tuple[str, list[str], str, int | None]:
    now = now_ny()

    if not next_event:
        return "low", [], "", None

    event_name = next_event["title"]
    event_time = next_event["datetime"]

    minutes = int((event_time - now).total_seconds() / 60)

    warnings = []

    # Live event window
    if -5 <= minutes <= 5:
        risk = "high"
        warnings.append("Macro event live now — volatility elevated")
        warnings.append(f"{event_name} active")
        return risk, warnings, event_name, 0

    # Immediate pre-event
    if 0 < minutes <= 15:
        risk = "high"
        warnings.append("High-impact event approaching — reduce size")
        warnings.append(f"{event_name} in {minutes}m")
        return risk, warnings, event_name, minutes

    # Pre-event caution
    if 15 < minutes <= 60:
        risk = "medium"
        warnings.append("High-impact macro event approaching")
        warnings.append(f"{event_name} in {minutes}m")
        return risk, warnings, event_name, minutes

    # Post-event cool down
    if -30 <= minutes < -5:
        risk = "medium"
        warnings.append("Post-event volatility window active")
        warnings.append(f"{event_name} recently released")
        return risk, warnings, event_name, 0

    # Normal
    return "low", [], event_name, max(minutes, 0)

# ==================================================
# MAIN CYCLE
# ==================================================
def process_news_guard_cycle() -> None:
    try:
        raw_events = fetch_calendar_events()
        priority_events = get_priority_events(raw_events)
        next_event = find_next_event(priority_events)

        macro_risk, warnings, event_name, mins = build_macro_state(next_event)

        state = load_state()

        # preserve non-macro warnings
        existing = state.get("active_warnings", [])
        keep = [
            w for w in existing
            if not str(w).startswith("MACRO:")
        ]

        macro_warns = [f"MACRO: {w}" for w in warnings]

        state["macro_risk"] = macro_risk
        state["active_warnings"] = keep + macro_warns
        state["next_event"] = event_name
        state["minutes_to_event"] = mins

        save_state(state)

        print(
            "Donna News Guard:",
            macro_risk,
            "|",
            event_name if event_name else "No major event",
            "|",
            mins
        )

    except Exception as e:
        print("Donna News Guard error:", str(e))
