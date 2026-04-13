from __future__ import annotations

from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timedelta, timezone
import os
import time
import requests

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

if not TE_API_KEY:
    raise RuntimeError("Missing TE_API_KEY in .env")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN in .env")

if not TELEGRAM_CHAT_ID:
    raise RuntimeError("Missing TELEGRAM_CHAT_ID in .env")

# =========================
# SETTINGS
# =========================
POLL_SECONDS = 60
LOOKAHEAD_HOURS = 24
ALERT_WINDOWS_MINUTES = [30, 10, 2]

# Keep this tight at first
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

# Prevent duplicate warning spam for same event/window
sent_alerts: set[str] = set()

# =========================
# TELEGRAM
# =========================
def send_telegram_message(text: str) -> dict:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
    }

    response = requests.post(url, json=payload, timeout=20)
    response.raise_for_status()
    return response.json()


# =========================
# ECONOMIC CALENDAR
# =========================
def fetch_us_calendar() -> list[dict]:
    """
    Trading Economics country calendar endpoint.
    Docs example:
    /calendar/country/united%20states?c=YOUR_API_KEY
    """
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

    # TE returns UTC timestamps like 2016-12-02T13:30:00
    # Docs specify Date is UTC.
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

    # Show both UTC and local machine time
    local_time = event_time_utc.astimezone()

    if minutes_left <= 0:
        timing_line = "NOW"
    else:
        timing_line = f"in {minutes_left}m"

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


def process_news_guard() -> None:
    calendar = fetch_us_calendar()
    matches = upcoming_relevant_events(calendar)

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


def main() -> None:
    print("Donna News Guard started.")
    while True:
        try:
            process_news_guard()
        except Exception as e:
            print("Donna News Guard error:", str(e))

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()