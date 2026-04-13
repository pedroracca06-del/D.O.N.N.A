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

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

BASE_DIR = Path(__file__).parent
RISK_STATE_FILE = BASE_DIR / "donna_risk_state.json"

# =========================
# SETTINGS
# =========================
WATCHLIST = [
    "NVDA", "AAPL", "MSFT", "AMZN", "META",
    "TSLA", "GOOGL", "SPY", "QQQ"
]

REQUEST_TIMEOUT = 25
MIN_ALERT_SCORE = 6
MAX_ALERTS_PER_CYCLE = 1

HIGH_IMPACT_TERMS = [
    "earnings",
    "guidance",
    "downgrade",
    "upgrade",
    "misses",
    "beats",
    "lawsuit",
    "sec",
    "investigation",
    "bankruptcy",
    "layoffs",
    "ai",
    "chips",
    "forecast",
    "warning",
    "surges",
    "plunges",
]

TOP_WEIGHT_SYMBOLS = {"NVDA", "AAPL", "MSFT", "AMZN", "META", "TSLA", "QQQ"}

seen_urls: set[str] = set()
seen_headlines: set[str] = set()

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
def normalize_headline(text: str) -> str:
    return " ".join(str(text).lower().split())


def score_market_news(symbol: str, headline: str, summary: str = "") -> int:
    text = f"{headline} {summary}".lower()
    score = 0

    for term in HIGH_IMPACT_TERMS:
        if term in text:
            score += 2

    if any(word in text for word in ["federal reserve", "fed", "rates", "yield", "cpi", "inflation"]):
        score += 2

    if any(word in text for word in ["nvda", "nvidia", "apple", "microsoft", "tesla", "amazon", "meta", "google"]):
        score += 2

    if symbol in TOP_WEIGHT_SYMBOLS:
        score += 1

    if any(word in text for word in ["sector update", "market today", "live coverage", "no contest"]):
        score -= 2

    return score


def severity_label(score: int) -> str:
    if score >= 8:
        return "HIGH"
    if score >= 6:
        return "MEDIUM"
    return "LOW"


def build_message(symbol: str, article: dict, score: int) -> str:
    headline = str(article.get("headline", "Unknown")).strip()
    url = str(article.get("url", "")).strip()
    severity = severity_label(score)

    return (
        f"📈 DONNA MARKET GUARD\n\n"
        f"Symbol: {symbol}\n"
        f"Severity: {severity}\n"
        f"Headline: {headline}\n\n"
        f"Donna Guidance: High-conviction company or sector catalyst detected. Expect index reaction.\n\n"
        f"{url}"
    )


def derive_market_risk(best_score: int, best_headline: str) -> tuple[str, list[str], str]:
    warnings: list[str] = []

    if best_score >= 8:
        warnings.append("High-impact company catalyst affecting index flow")
        return "high", warnings, best_headline

    if best_score >= 4:
        warnings.append("Moderate market-moving company news")
        return "medium", warnings, best_headline

    return "low", [], best_headline

# =========================
# MAIN CYCLE
# =========================
def process_finnhub_cycle() -> None:
    candidate_alerts: list[tuple[int, str, dict]] = []
    best_score = 0
    best_headline = ""

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

            normalized = normalize_headline(headline)
            score = score_market_news(symbol, headline, summary)

            if score > best_score:
                best_score = score
                best_headline = headline

            if url in seen_urls or normalized in seen_headlines:
                continue

            if score >= MIN_ALERT_SCORE:
                candidate_alerts.append((score, symbol, article))

    risk, warnings, last_headline = derive_market_risk(best_score, best_headline)
    save_market_state(risk, warnings, last_headline)

    if not candidate_alerts:
        print("Donna Finnhub Guard: nothing strong enough to alert.")
        return

    candidate_alerts.sort(key=lambda x: x[0], reverse=True)

    alerts_sent = 0
    for score, symbol, article in candidate_alerts:
        if alerts_sent >= MAX_ALERTS_PER_CYCLE:
            break

        headline = str(article.get("headline", "")).strip()
        url = str(article.get("url", "")).strip()
        normalized = normalize_headline(headline)

        if url in seen_urls or normalized in seen_headlines:
            continue

        msg = build_message(symbol, article, score)
        result = send_telegram_message(msg)
        print("Finnhub alert sent:", result)

        seen_urls.add(url)
        seen_headlines.add(normalized)
        alerts_sent += 1
