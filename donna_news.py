from __future__ import annotations

from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timedelta, timezone
import os
import requests
import json

# =========================
# ENV LOAD
# =========================
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

TE_API_KEY = os.getenv("TE_API_KEY")
TE_BASE_URL = "https://api.tradingeconomics.com"
TE_COUNTRY = "united%20states"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RISK_STATE_FILE = Path(__file__).parent / "donna_risk_state.json"

# =========================
# SETTINGS
# =========================
LOOKAHEAD_HOURS = 24
ALERT_WINDOWS_MINUTES = [30, 10, 2]

WATCHLIST_KEYWORDS = [
    "Consumer Price Index",
    "Core Consumer Prices",
    "Inflation Rate",
    "Producer Prices",
    "Non Farm Payrolls",
    "Unemployment Rate",
    "FOMC",
    "Fed",
    "Interest Rate Decision",
    "Retail Sales",
    "GDP",
    "Initial Jobless Claims",
    "Jerome Powell",
    "Powell",
]

sent_alerts: set[str] = set()


# =========================
# TELEGRAM
# =========================
def send_telegram_message(text: str) -> dict:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return {"error": "Missing Telegram credentials"}

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
    }

    response = requests.post(url, json=payload, timeout=20)
    response.raise_for_status()
    return response.json()


# =========================
# RISK STATE
# =========================
def load_risk_state() -> dict:
    default_state = {
        "macro_risk": "low",
        "headline_risk": "low",
        "active_warnings": [],
        "next_event": "",
        "minutes_to_event": None,
        "last_headline": "",
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


def save_risk_state_macro(macro_risk: str, active_warnings: list[str], next_event: str, minutes_to_event: int | None) -> None:
    state = load_risk_state()

    headline_warnings = [
        w for w in state.get("active_warnings", [])
        if not str(w).startswith("MACRO:")
    ]

    macro_prefixed = [f"MACRO: {w}" for w in active_warnings]

    state["macro_risk"] = macro_risk
    state["active_warnings"] = headline_warnings + macro_prefixed
    state["next_event"] = next_event
    state["minutes_to_event"] = minutes_to_event
    state["last_updated"] = datetime.now(timezone.utc).isoformat()

    with open(RISK_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


# =========================
# ECONOMIC CALENDAR
# =========================
def fetch_us_calendar() -> list[dict]:
    if not TE_API_KEY:
        raise RuntimeError("Missing TE_API_KEY")

    url = f"{TE_BASE_URL}/calendar/country/{TE_COUNTRY}?c={TE_API_KEY}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()

    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected calendar response: {data}")

    return data


def parse_utc_datetime(value: str) -> datetime | None:
    if not value:
        return None

    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def is_watched_event(event_name: str, category: str) -> bool:
    haystack = f"{event_name} {category}".lower()
    return any(keyword.lower() in haystack for keyword in WATCHLIST_KEYWORDS)


def severity_label(importance: int) -> str:
    if importance >= 3:
        return "HIGH"
    if importance == 2:
        return "MEDIUM"
    return "LOW"


def build_event_key(calendar_id: str, event_time: datetime, minutes_left: int) -> str:
    return f"{calendar_id}|{event_time.isoformat()}|{minutes_left}"


def format_event_message(event: dict, event_time_utc: datetime, minutes_left: int) -> str:
    event_name = str(event.get("Event", "Unknown Event"))
    category = str(event.get("Category", "Unknown Category"))
    importance = int(event.get("Importance", 0) or 0)
    reference = str(event.get("Reference", ""))
    source = str(event.get("Source", ""))

    local_time = event_time_utc.astimezone()

    timing_line = "NOW" if minutes_left <= 0 else f"in {minutes_left}m"

    return (
        f"⚠️ DONNA NEWS GUARD\n\n"
        f"Event: {event_name}\n"
        f"Category: {category}\n"
        f"Severity: {severity_label(importance)}\n"
        f"Timing: {timing_line}\n"
        f"UTC: {event_time_utc.strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"Local: {local_time.strftime('%Y-%m-%d %I:%M %p')}\n"
        f"Reference: {reference or 'N/A'}\n"
        f"Source: {source or 'N/A'}\n\n"
        f"Donna Guidance: High-impact macro risk near market. Be careful with new trades."
    )


def upcoming_relevant_events(calendar: list[dict]) -> list[tuple[dict, datetime, int]]:
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc + timedelta(hours=LOOKAHEAD_HOURS)

    matches: list[tuple[dict, datetime, int]] = []

    for event in calendar:
        country = str(event.get("Country", ""))
        if country.lower() != "united states":
            continue

        importance = int(event.get("Importance", 0) or 0)
        if importance < 3:
            continue

        event_name = str(event.get("Event", ""))
        category = str(event.get("Category", ""))

        if not is_watched_event(event_name, category):
            continue

        event_time = parse_utc_datetime(str(event.get("Date", "")))
        if not event_time:
            continue

        if event_time < now_utc or event_time > cutoff:
            continue

        minutes_left = int((event_time - now_utc).total_seconds() // 60)
        matches.append((event, event_time, minutes_left))

    matches.sort(key=lambda x: x[1])
    return matches


def derive_macro_risk(matches: list[tuple[dict, datetime, int]]) -> tuple[str, list[str], str, int | None]:
    if not matches:
        return "low", [], "", None

    event, _, minutes_left = matches[0]
    event_name = str(event.get("Event", "Unknown Event"))

    warnings: list[str] = []

    if minutes_left <= 15:
        warnings.append(f"{event_name} within {minutes_left}m")
        return "high", warnings, event_name, minutes_left

    if minutes_left <= 60:
        warnings.append(f"{event_name} within {minutes_left}m")
        return "medium", warnings, event_name, minutes_left

    warnings.append(f"High-impact event later today: {event_name}")
    return "low", warnings, event_name, minutes_left


def process_news_guard_cycle() -> None:
    calendar = fetch_us_calendar()
    matches = upcoming_relevant_events(calendar)

    macro_risk, warnings, next_event, minutes_to_event = derive_macro_risk(matches)
    save_risk_state_macro(macro_risk, warnings, next_event, minutes_to_event)

    if not matches:
        print("Donna News Guard: no relevant high-impact US events in window.")
        return

    for event, event_time, minutes_left in matches:
        calendar_id = str(event.get("CalendarID", "no_id"))

        for window in ALERT_WINDOWS_MINUTES:
            if minutes_left <= window and minutes_left >= max(0, window - 1):
                key = build_event_key(calendar_id, event_time, window)
                if key in sent_alerts:
                    continue

                message = format_event_message(event, event_time, minutes_left)
                result = send_telegram_message(message)
                print("News alert sent:", result)
                sent_alerts.add(key)
