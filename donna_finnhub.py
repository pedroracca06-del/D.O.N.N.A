from __future__ import annotations

from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timedelta, timezone
import os
import json
import requests

# =========================
# ENV
# =========================
BASE_DIR = Path(__file__).parent
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RISK_STATE_FILE = BASE_DIR / "donna_risk_state.json"

# =========================
# SETTINGS
# =========================
WATCHLIST = ["NVDA", "AAPL", "MSFT", "AMZN", "META", "TSLA", "GOOGL", "SPY", "QQQ"]
REQUEST_TIMEOUT = 25
MIN_ALERT_SCORE = 7
MAX_ALERTS_PER_CYCLE = 1

seen_urls: set[str] = set()
seen_titles: set[str] = set()

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
# STATE
# =========================
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def load_risk_state() -> dict:
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


def save_market_state(risk: str, warnings: list[str], last_headline: str) -> None:
    state = load_risk_state()

    non_market = [
        w for w in state.get("active_warnings", [])
        if not str(w).startswith("MARKET:")
    ]

    market_warnings = [f"MARKET: {w}" for w in warnings]

    state["market_news_risk"] = risk
    state["active_warnings"] = non_market + market_warnings
    state["last_market_headline"] = last_headline
    state["last_updated"] = now_utc().isoformat()

    with open(RISK_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

# =========================
# FINNHUB
# =========================
def fetch_company_news(symbol: str) -> list[dict]:
    if not FINNHUB_API_KEY:
        raise RuntimeError("Missing FINNHUB_API_KEY")

    today = now_utc().date()
    from_date = today - timedelta(days=2)

    url = "https://finnhub.io/api/v1/company-news"
    params = {
        "symbol": symbol,
        "from": from_date.isoformat(),
        "to": today.isoformat(),
        "token": FINNHUB_API_KEY,
    }

    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    data = response.json()
    return data if isinstance(data, list) else []

# =========================
# SCORING
# =========================
def normalize_title(title: str) -> str:
    return " ".join(title.lower().split())


def score_article(symbol: str, headline: str, summary: str) -> int:
    text = f"{headline} {summary}".lower()
    score = 0

    strong_terms = [
        "earnings", "guidance", "downgrade", "upgrade", "warning",
        "forecast", "beats", "misses", "lawsuit", "investigation",
        "sec", "layoffs", "bankruptcy", "plunges", "surges"
    ]

    weak_terms = [
        "sector update", "market today", "live coverage", "no contest"
    ]

    mega_names = [
        "nvidia", "nvda", "apple", "aapl", "microsoft", "msft",
        "amazon", "amzn", "meta", "tesla", "google", "googl"
    ]

    macro_terms = ["fed", "rates", "yield", "inflation", "cpi"]

    for term in strong_terms:
        if term in text:
            score += 2

    for term in mega_names:
        if term in text:
            score += 2

    for term in macro_terms:
        if term in text:
            score += 1

    for term in weak_terms:
        if term in text:
            score -= 3

    if symbol in {"NVDA", "AAPL", "MSFT", "AMZN", "META", "TSLA", "QQQ"}:
        score += 1

    return score


def build_message(symbol: str, headline: str, url: str, score: int) -> str:
    severity = "HIGH" if score >= 9 else "MEDIUM"

    return (
        f"📈 DONNA MARKET GUARD\n\n"
        f"Symbol: {symbol}\n"
        f"Severity: {severity}\n"
        f"Headline: {headline}\n\n"
        f"Donna Guidance: High-conviction market catalyst detected. Expect index reaction.\n\n"
        f"{url}"
    )

# =========================
# MAIN CYCLE
# =========================
def process_finnhub_cycle() -> None:
    best_score = 0
    best_headline = ""
    best_alert = None

    for symbol in WATCHLIST:
        try:
            news = fetch_company_news(symbol)
        except Exception as e:
            print("Finnhub fetch error:", symbol, str(e))
            continue

        for article in news[:5]:
            headline = str(article.get("headline", "")).strip()
            summary = str(article.get("summary", "")).strip()
            url = str(article.get("url", "")).strip()

            if not headline or not url:
                continue

            norm_title = normalize_title(headline)
            score = score_article(symbol, headline, summary)

            if score > best_score:
                best_score = score
                best_headline = headline

            if url in seen_urls or norm_title in seen_titles:
                continue

            if score >= MIN_ALERT_SCORE:
                if best_alert is None or score > best_alert[0]:
                    best_alert = (score, symbol, headline, url, norm_title)

    if best_score >= 8:
        risk = "high"
        warnings = ["High-impact company catalyst affecting index flow"]
    elif best_score >= 4:
        risk = "medium"
        warnings = ["Moderate market-moving company news"]
    else:
        risk = "low"
        warnings = []

    save_market_state(risk, warnings, best_headline)

    if best_alert is None:
        print("Donna Finnhub Guard: nothing strong enough to alert.")
        return

    score, symbol, headline, url, norm_title = best_alert
    msg = build_message(symbol, headline, url, score)
    result = send_telegram_message(msg)
    print("Finnhub alert sent:", result)

    seen_urls.add(url)
    seen_titles.add(norm_title)
