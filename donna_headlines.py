from __future__ import annotations

from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timedelta, timezone
import os
import time
import requests

print("HEADLINES FILE LOADED")

# =========================
# ENV LOAD
# =========================
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not NEWSAPI_KEY:
    raise RuntimeError("Missing NEWSAPI_KEY in .env")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN in .env")

if not TELEGRAM_CHAT_ID:
    raise RuntimeError("Missing TELEGRAM_CHAT_ID in .env")

# =========================
# SETTINGS
# =========================
POLL_SECONDS = 900          # 15 minutes
PAGE_SIZE = 20
MIN_SEVERITY_TO_ALERT = 3
REQUEST_TIMEOUT = 25

seen_urls: set[str] = set()

# Broad macro / geopolitical / policy scan
NEWS_QUERY = (
    '("Trump" OR "Donald Trump" OR "White House" OR tariff OR sanctions '
    'OR Iran OR Israel OR missile OR airstrike OR war OR ceasefire OR oil '
    'OR "Federal Reserve" OR Fed OR FOMC OR Powell OR "Jerome Powell" '
    'OR "rate decision" OR China OR "trade war")'
)

HIGH_RISK_TERMS = [
    "airstrike",
    "missile",
    "attack",
    "war",
    "emergency",
    "tariff",
    "sanctions",
    "fed",
    "fomc",
    "powell",
    "military",
    "oil",
    "retaliation",
]

HEADERS = {
    "X-Api-Key": NEWSAPI_KEY,
    "User-Agent": "DonnaHeadlineGuard/1.0",
}

# =========================
# TELEGRAM
# =========================
def send_telegram_message(text: str) -> dict:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
    }

    response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()

# =========================
# NEWSAPI
# =========================
def fetch_newsapi_headlines() -> list[dict]:
    """
    NewsAPI Everything endpoint:
    - boolean / phrase search in q
    - sort by publishedAt
    - english only
    """
    base_url = "https://newsapi.org/v2/everything"

    now_utc = datetime.now(timezone.utc)
    from_utc = now_utc - timedelta(hours=6)

    params = {
        "q": NEWS_QUERY,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": PAGE_SIZE,
        "from": from_utc.isoformat().replace("+00:00", "Z"),
    }

    response = requests.get(base_url, headers=HEADERS, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    body = response.text.strip()
    if not body:
        raise RuntimeError("NEWSAPI_EMPTY_RESPONSE")

    data = response.json()

    if data.get("status") != "ok":
        raise RuntimeError(f"NEWSAPI_BAD_STATUS: {data}")

    articles = data.get("articles", [])
    if not isinstance(articles, list):
        return []

    return articles

# =========================
# SCORING
# =========================
def classify_theme(text: str) -> str:
    t = text.lower()

    if any(term in t for term in ["trump", "donald trump", "white house", "tariff", "sanctions"]):
        return "TRUMP / POLICY"
    if any(term in t for term in ["iran", "israel", "airstrike", "missile", "ceasefire", "war", "retaliation"]):
        return "GEOPOLITICS"
    if any(term in t for term in ["fed", "fomc", "powell", "federal reserve", "rate decision"]):
        return "FED / RATES"
    if any(term in t for term in ["china", "trade war"]):
        return "CHINA / TRADE"
    if "oil" in t:
        return "OIL / ENERGY"

    return "GENERAL RISK"


def score_headline(title: str, description: str = "", source_name: str = "") -> int:
    text = f"{title} {description} {source_name}".lower()
    score = 0

    if any(term in text for term in ["iran", "israel", "war", "missile", "airstrike", "retaliation"]):
        score += 3

    if any(term in text for term in ["trump", "white house", "tariff", "sanctions"]):
        score += 2

    if any(term in text for term in ["fed", "fomc", "powell", "federal reserve", "rate decision"]):
        score += 3

    if "oil" in text:
        score += 1

    for term in HIGH_RISK_TERMS:
        if term in text:
            score += 1

    return score


def severity_label(score: int) -> str:
    if score >= 6:
        return "HIGH"
    if score >= 3:
        return "MEDIUM"
    return "LOW"


def build_message(article: dict, score: int) -> str:
    source_name = str(article.get("source", {}).get("name", "Unknown source")).strip()
    title = str(article.get("title", "Unknown headline")).strip()
    description = str(article.get("description", "")).strip()
    url = str(article.get("url", "")).strip()
    published_at = str(article.get("publishedAt", "")).strip()

    theme = classify_theme(f"{title} {description}")
    severity = severity_label(score)

    guidance = (
        "Headline risk is elevated. Expect fast repricing, liquidity sweeps, and unstable continuation quality."
        if severity == "HIGH"
        else "Potential market-moving headline. Trade with caution until direction stabilizes."
    )

    return (
        f"⚠️ DONNA HEADLINE GUARD\n\n"
        f"Severity: {severity}\n"
        f"Theme: {theme}\n"
        f"Headline: {title}\n"
        f"Source: {source_name}\n"
        f"Published: {published_at or 'N/A'}\n\n"
        f"Donna Guidance: {guidance}\n\n"
        f"{url}"
    )

# =========================
# MAIN PROCESS
# =========================
def process_headlines() -> None:
    print("Checking headlines...")
    articles = fetch_newsapi_headlines()

    if not articles:
        print("Donna Headline Guard: no matching headlines.")
        return

    sent_count = 0

    for article in articles:
        title = str(article.get("title", "")).strip()
        description = str(article.get("description", "")).strip()
        url = str(article.get("url", "")).strip()
        source_name = str(article.get("source", {}).get("name", "")).strip()

        if not title or not url:
            continue

        if url in seen_urls:
            continue

        score = score_headline(title, description, source_name)
        if score < MIN_SEVERITY_TO_ALERT:
            continue

        message = build_message(article, score)
        result = send_telegram_message(message)
        print("Headline alert sent:", result)

        seen_urls.add(url)
        sent_count += 1

    if sent_count == 0:
        print("Donna Headline Guard: nothing severe enough to alert.")


def main() -> None:
    print("Donna Headline Guard started.")
    while True:
        try:
            process_headlines()
            time.sleep(POLL_SECONDS)

        except Exception as e:
            msg = str(e)
            print("Donna Headline Guard error:", msg)

            if "429" in msg:
                print("NewsAPI rate limited. Sleeping 30 minutes...")
                time.sleep(1800)
            else:
                print("Generic headline guard error. Sleeping 15 minutes...")
                time.sleep(900)


if __name__ == "__main__":
    main()
    