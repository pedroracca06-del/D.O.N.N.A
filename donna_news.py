from __future__ import annotations

from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timezone
import os
import requests
import json

# =========================
# ENV LOAD
# =========================
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# =========================
# FILE PATHS
# =========================
BASE_DIR = Path(__file__).parent
MACRO_FILE = BASE_DIR / "donna_macro_calendar.json"
RISK_STATE_FILE = BASE_DIR / "donna_risk_state.json"

# Prevent duplicate alerts
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
# HELPERS
# =========================
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_utc(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def load_macro_calendar() -> list[dict]:
    if not MACRO_FILE.exists():
        return []

    with open(MACRO_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    events = data.get("events", [])
    return events if isinstance(events, list) else []


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


def save_macro_state(risk: str, warnings: list[str], next_event: str, minutes_left: int | None) -> None:
    state = load_risk_state()

    non_macro = [
        w for w in state.get("active_warnings", [])
        if not str(w).startswith("MACRO:")
    ]

    macro_warnings = [f"MACRO: {w}" for w in warnings]

    state["macro_risk"] = risk
    state["active_warnings"] = non_macro + macro_warnings
    state["next_event"] = next_event
    state["minutes_to_event"] = minutes_left
    state["last_updated"] = now_utc().isoformat()

    with open(RISK_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

# =========================
# CORE LOGIC
# =========================
def upcoming_events() -> list[tuple[dict, datetime, int]]:
    current = now_utc()
    matches = []

    for event in load_macro_calendar():
        dt = parse_utc(str(event.get("datetime_utc", "")))
        if not dt:
            continue

        minutes_left = int((dt - current).total_seconds() // 60)

        if minutes_left < 0:
            continue

        matches.append((event, dt, minutes_left))

    matches.sort(key=lambda x: x[1])
    return matches


def derive_macro_risk(events: list[tuple[dict, datetime, int]]) -> tuple[str, list[str], str, int | None]:
    if not events:
        return "low", [], "", None

    event, _, minutes_left = events[0]

    name = str(event.get("name", "Unknown Event"))
    importance = str(event.get("importance", "low")).lower()

    warnings = []

    if importance == "high":
        if minutes_left <= 15:
            warnings.append(f"{name} within {minutes_left}m")
            return "high", warnings, name, minutes_left
        if minutes_left <= 60:
            warnings.append(f"{name} within {minutes_left}m")
            return "medium", warnings, name, minutes_left

    if importance == "medium":
        if minutes_left <= 30:
            warnings.append(f"{name} within {minutes_left}m")
            return "medium", warnings, name, minutes_left

    warnings.append(f"Upcoming event: {name}")
    return "low", warnings, name, minutes_left


def build_alert_key(name: str, minutes: int) -> str:
    return f"{name}|{minutes}"


def format_event_message(event: dict, minutes_left: int) -> str:
    name = str(event.get("name", "Unknown Event"))
    category = str(event.get("category", "general"))
    importance = str(event.get("importance", "low")).upper()

    timing = "NOW" if minutes_left <= 0 else f"in {minutes_left}m"

    return (
        f"⚠️ DONNA NEWS GUARD\n\n"
        f"Event: {name}\n"
        f"Category: {category}\n"
        f"Importance: {importance}\n"
        f"Timing: {timing}\n\n"
        f"Donna Guidance: Major macro event near market. Expect volatility and lower setup reliability."
    )


def process_news_guard_cycle() -> None:
    events = upcoming_events()

    risk, warnings, next_event, minutes_left = derive_macro_risk(events)
    save_macro_state(risk, warnings, next_event, minutes_left)

    if not events:
        print("Donna News Guard: no upcoming events.")
        return

    event, _, mins = events[0]
    name = str(event.get("name", "Unknown Event"))
    windows = event.get("warning_minutes", [])

    if not isinstance(windows, list):
        windows = []

    for window in windows:
        try:
            window = int(window)
        except Exception:
            continue

        if mins <= window and mins >= max(0, window - 1):
            key = build_alert_key(name, window)

            if key in sent_alerts:
                continue

            msg = format_event_message(event, mins)
            result = send_telegram_message(msg)
            print("Macro alert sent:", result)

            sent_alerts.add(key)
