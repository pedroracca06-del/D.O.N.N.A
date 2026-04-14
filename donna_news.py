from __future__ import annotations

from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
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
MACRO_CACHE_FILE = BASE_DIR / "donna_macro_cache.json"

NY_TZ = ZoneInfo("America/New_York")
UTC_TZ = ZoneInfo("UTC")

FOREX_FACTORY_XML = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"

# ==================================================
# SETTINGS
# ==================================================
CACHE_HOURS = 6
REQUEST_TIMEOUT = 20

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
# TIME HELPERS
# ==================================================
def now_ny() -> datetime:
    return datetime.now(NY_TZ)


def now_utc() -> datetime:
    return datetime.now(UTC_TZ)


def now_iso_utc() -> str:
    return now_utc().isoformat()


def now_iso_ny() -> str:
    return now_ny().isoformat()


def current_day_name() -> str:
    return now_ny().strftime("%A")


def current_time_label() -> str:
    return now_ny().strftime("%Y-%m-%d %I:%M:%S %p %Z")


def get_market_session_label(dt: datetime | None = None) -> str:
    dt = dt or now_ny()
    minutes = dt.hour * 60 + dt.minute

    # NY-based rough global session model
    # Asia: 19:00 - 03:00
    # London: 03:00 - 09:30
    # NY Cash: 09:30 - 16:00
    # Off hours: everything else

    if minutes >= 19 * 60 or minutes < 3 * 60:
        return "ASIA"
    if 3 * 60 <= minutes < 9 * 60 + 30:
        return "LONDON"
    if 9 * 60 + 30 <= minutes < 16 * 60:
        return "NEW_YORK_CASH"
    return "OFF_HOURS"


def describe_event_phase(minutes_to_event: int | None) -> str:
    if minutes_to_event is None:
        return "NO_EVENT"

    if -5 <= minutes_to_event <= 5:
        return "LIVE"
    if 0 < minutes_to_event <= 15:
        return "IMMINENT"
    if 15 < minutes_to_event <= 60:
        return "APPROACHING"
    if 60 < minutes_to_event <= 24 * 60:
        return "LATER_TODAY_OR_SOON"
    if -30 <= minutes_to_event < -5:
        return "POST_EVENT_COOLDOWN"
    if minutes_to_event < -30:
        return "PASSED"
    return "SCHEDULED"

# ==================================================
# STATE
# ==================================================
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
        "headline_severity": "",
        "headline_guidance": "",
        "headline_source": "",
        "last_market_symbol": "",
        "last_market_severity": "",
        "last_market_guidance": "",
        "last_market_url": "",
        "donna_time_utc": "",
        "donna_time_ny": "",
        "donna_day": "",
        "donna_session": "",
        "event_phase": "",
        "event_time_ny": "",
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
    state["last_updated"] = now_iso_utc()
    state["donna_time_utc"] = now_iso_utc()
    state["donna_time_ny"] = now_iso_ny()
    state["donna_day"] = current_day_name()
    state["donna_session"] = get_market_session_label()

    with open(RISK_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

# ==================================================
# CACHE
# ==================================================
def load_macro_cache() -> dict:
    default_cache = {
        "fetched_at": "",
        "events": [],
    }

    try:
        if not MACRO_CACHE_FILE.exists():
            return default_cache

        with open(MACRO_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return default_cache

        return {**default_cache, **data}
    except Exception:
        return default_cache


def save_macro_cache(events: list[dict]) -> None:
    payload = {
        "fetched_at": now_iso_utc(),
        "events": events,
    }

    with open(MACRO_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def cache_is_fresh(cache: dict) -> bool:
    fetched_at = str(cache.get("fetched_at", "")).strip()
    if not fetched_at:
        return False

    try:
        dt = datetime.fromisoformat(fetched_at)
    except Exception:
        return False

    return now_utc() - dt < timedelta(hours=CACHE_HOURS)

# ==================================================
# FILTER HELPERS
# ==================================================
def contains_high_impact(title: str) -> bool:
    text = title.lower()
    return any(word in text for word in HIGH_IMPACT_KEYWORDS)


def normalize_title(title: str) -> str:
    return " ".join(str(title).lower().split())

# ==================================================
# FOREX FACTORY FETCH
# ==================================================
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


def fetch_calendar_events_from_source() -> list[dict]:
    response = requests.get(FOREX_FACTORY_XML, timeout=REQUEST_TIMEOUT)
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

            dt_raw = f"{date_text} {time_text}".strip()
            event_dt = parse_event_datetime(dt_raw)

            if not event_dt:
                continue

            events.append({
                "title": title,
                "country": country,
                "impact": impact,
                "datetime": event_dt.isoformat(),
            })

        except Exception:
            continue

    return events


def fetch_calendar_events() -> list[dict]:
    cache = load_macro_cache()

    if cache_is_fresh(cache):
        return cache.get("events", [])

    try:
        events = fetch_calendar_events_from_source()
        save_macro_cache(events)
        return events
    except Exception as e:
        if cache.get("events"):
            print("Donna News Guard using cached macro calendar due to fetch error:", str(e))
            return cache.get("events", [])
        raise

# ==================================================
# EVENT ENGINE
# ==================================================
def get_priority_events(events: list[dict]) -> list[dict]:
    out = []

    for e in events:
        title = str(e.get("title", ""))
        impact = str(e.get("impact", "")).lower()
        dt_raw = str(e.get("datetime", "")).strip()

        if not dt_raw:
            continue

        try:
            event_dt = datetime.fromisoformat(dt_raw)
        except Exception:
            continue

        if impact == "high" or contains_high_impact(title):
            out.append({
                "title": title,
                "country": str(e.get("country", "")),
                "impact": impact,
                "datetime": event_dt,
            })

    return sorted(out, key=lambda x: x["datetime"])


def find_relevant_event(events: list[dict]):
    now = now_ny()

    if not events:
        return None

    # Prefer events within the nearby actionable window
    window_start = now - timedelta(minutes=30)
    window_end = now + timedelta(hours=24)

    relevant = [
        e for e in events
        if window_start <= e["datetime"] <= window_end
    ]

    if relevant:
        return sorted(
            relevant,
            key=lambda x: abs((x["datetime"] - now).total_seconds())
        )[0]

    future = [e for e in events if e["datetime"] >= now]
    return future[0] if future else None


def build_macro_state(next_event: dict | None) -> tuple[str, list[str], str, int | None, str]:
    now = now_ny()

    if not next_event:
        return "low", [], "", None, ""

    event_name = next_event["title"]
    event_time = next_event["datetime"]
    event_time_label = event_time.strftime("%Y-%m-%d %I:%M %p %Z")
    minutes = int((event_time - now).total_seconds() / 60)

    warnings = []

    if -5 <= minutes <= 5:
        risk = "high"
        warnings.append("Macro event live now — volatility elevated")
        warnings.append(f"{event_name} active")
        return risk, warnings, event_name, 0, event_time_label

    if 0 < minutes <= 15:
        risk = "high"
        warnings.append("High-impact event approaching — reduce size")
        warnings.append(f"{event_name} in {minutes}m")
        return risk, warnings, event_name, minutes, event_time_label

    if 15 < minutes <= 60:
        risk = "medium"
        warnings.append("High-impact macro event approaching")
        warnings.append(f"{event_name} in {minutes}m")
        return risk, warnings, event_name, minutes, event_time_label

    if -30 <= minutes < -5:
        risk = "medium"
        warnings.append("Post-event volatility window active")
        warnings.append(f"{event_name} recently released")
        return risk, warnings, event_name, 0, event_time_label

    return "low", [], event_name, max(minutes, 0), event_time_label

# ==================================================
# MAIN CYCLE
# ==================================================
def process_news_guard_cycle() -> None:
    try:
        raw_events = fetch_calendar_events()
        priority_events = get_priority_events(raw_events)
        next_event = find_relevant_event(priority_events)

        macro_risk, warnings, event_name, mins, event_time_label = build_macro_state(next_event)
        event_phase = describe_event_phase(mins)

        state = load_state()

        existing = state.get("active_warnings", [])
        keep = [w for w in existing if not str(w).startswith("MACRO:")]
        macro_warns = [f"MACRO: {w}" for w in warnings]

        state["macro_risk"] = macro_risk
        state["active_warnings"] = keep + macro_warns
        state["next_event"] = event_name
        state["minutes_to_event"] = mins
        state["event_phase"] = event_phase
        state["event_time_ny"] = event_time_label

        save_state(state)

        print(
            "Donna News Guard:",
            macro_risk,
            "|",
            event_name if event_name else "No major event",
            "|",
            mins,
            "|",
            event_phase,
            "|",
            current_time_label(),
        )

    except Exception as e:
        print("Donna News Guard error:", str(e))
