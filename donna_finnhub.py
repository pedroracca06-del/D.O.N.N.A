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

WATCHLIST = [
    "NVDA", "AAPL", "MSFT", "AMZN", "META",
    "TSLA", "GOOGL", "SPY", "QQQ"
]

seen_news: set[str] = set()

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
        "token": FINNHUB_API_KEY
    }

    response = requests.get(url, params=params, timeout=25)
    response.raise_for_status()

    data = response.json()
    return data if isinstance(data, list) else []

# =========================
# SCORING
# =========================
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
]


def score_market_news(headline: str, summary: str = "") -> int:
    text = f"{headline} {summary}".lower()
    score = 0

    for term in HIGH_IMPACT_TERMS:
        if term in text:
            score += 2

    if any(word in text for word in ["nvda", "apple", "microsoft", "tesla"]):
        score += 2

    return score


def severity_label(score: int) -> str:
    if score >= 6:
        return "HIGH"
    if score >= 3:
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
        f"Donna Guidance: Market-moving catalyst detected. Expect reaction in index flow.\n\n"
        f"{url}"
    )

# =========================
# MAIN CYCLE
# =========================
def process_finnhub_cycle() -> None:
    best_score = 0
    best_headline = ""
    warnings = []

    for symbol in WATCHLIST:
        try:
            news = fetch_company_news(symbol)
        except Exception as e:
            print("Finnhub fetch error:", symbol, str(e))
            continue

        for article in news[:3]:
            headline = str(article.get("headline", "")).strip()
            summary = str(article.get("summary", "")).strip()
            url = str(article.get("url", "")).strip()

            if not headline or not url:
                continue

            uid = f"{symbol}|{url}"
            score = score_market_news(headline, summary)

            if score > best_score:
                best_score = score
                best_headline = headline

            if score >= 5 and uid not in seen_news:
                msg = build_message(symbol, article, score)
                result = send_telegram_message(msg)
                print("Finnhub alert sent:", result)
                seen_news.add(uid)

    if best_score >= 6:
        warnings.append("High-impact company catalyst affecting market")
        risk = "high"
    elif best_score >= 3:
        warnings.append("Moderate market-moving company news")
        risk = "medium"
    else:
        risk = "low"

    save_market_state(risk, warnings, best_headline)
