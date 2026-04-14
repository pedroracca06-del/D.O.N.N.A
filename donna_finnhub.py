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

RISK_STATE_FILE = BASE_DIR / "donna_risk_state.json"

# =========================
# SETTINGS
# =========================
WATCHLIST = ["NVDA", "AAPL", "MSFT", "AMZN", "META", "TSLA", "GOOGL", "SPY", "QQQ"]
REQUEST_TIMEOUT = 25
MIN_ALERT_SCORE = 8

SYMBOL_ALIASES = {
    "NVDA": ["nvda", "nvidia"],
    "AAPL": ["aapl", "apple"],
    "MSFT": ["msft", "microsoft"],
    "AMZN": ["amzn", "amazon"],
    "META": ["meta", "facebook"],
    "TSLA": ["tsla", "tesla"],
    "GOOGL": ["googl", "google", "alphabet"],
    "SPY": ["spy", "s&p", "sp500", "s&p 500", "stocks", "stock market", "dow", "nasdaq"],
    "QQQ": ["qqq", "nasdaq", "tech stocks", "big tech"],
}

MEGA_CAPS = {"NVDA", "AAPL", "MSFT", "AMZN", "META", "TSLA", "GOOGL"}

seen_urls: set[str] = set()
seen_titles: set[str] = set()

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
        "last_market_symbol": "",
        "last_market_severity": "",
        "last_market_guidance": "",
        "last_market_url": "",
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


def save_market_state(
    risk: str,
    warnings: list[str],
    last_headline: str,
    symbol: str = "",
    severity: str = "",
    guidance: str = "",
    url: str = "",
) -> None:
    state = load_risk_state()

    non_market = [
        w for w in state.get("active_warnings", [])
        if not str(w).startswith("MARKET:")
    ]

    market_warnings = [f"MARKET: {w}" for w in warnings]

    state["market_news_risk"] = risk
    state["active_warnings"] = non_market + market_warnings
    state["last_market_headline"] = last_headline
    state["last_market_symbol"] = symbol
    state["last_market_severity"] = severity
    state["last_market_guidance"] = guidance
    state["last_market_url"] = url
    state["last_updated"] = now_utc().isoformat()

    with open(RISK_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

# =========================
# FINNHUB FETCH
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
# SCORING / FILTERING
# =========================
def normalize_title(title: str) -> str:
    return " ".join(title.lower().split())


def contains_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


def symbol_is_relevant(symbol: str, headline: str, summary: str) -> bool:
    text = f"{headline} {summary}".lower()
    aliases = SYMBOL_ALIASES.get(symbol, [])
    return contains_any(text, aliases)


def is_broad_market_story(headline: str, summary: str) -> bool:
    text = f"{headline} {summary}".lower()
    broad_terms = [
        "stock market",
        "stocks",
        "market today",
        "dow",
        "nasdaq",
        "s&p 500",
        "s&p",
        "qqq",
        "spy",
        "big tech",
        "sector update",
        "index",
        "futures",
        "bond yields",
        "treasury yields",
    ]
    return contains_any(text, broad_terms)


def classify_story(symbol: str, headline: str, summary: str) -> str:
    text = f"{headline} {summary}".lower()

    macro_terms = ["fed", "rates", "yield", "inflation", "cpi", "powell", "fomc", "jobs report"]
    earnings_terms = ["earnings", "guidance", "forecast", "beats", "misses", "revenue", "profit"]
    legal_terms = ["lawsuit", "investigation", "antitrust", "sec", "ftc", "department of justice", "regulator"]
    deal_terms = ["acquisition", "merger", "deal", "buyout", "takeover"]
    ai_terms = ["ai", "artificial intelligence", "chips", "semiconductor", "cloud", "aws", "azure"]
    weak_terms = ["sector update", "market today", "live coverage", "today's movers"]

    if contains_any(text, macro_terms):
        return "broad_macro"
    if contains_any(text, earnings_terms):
        return "earnings"
    if contains_any(text, legal_terms):
        return "regulatory"
    if contains_any(text, deal_terms):
        return "deal"
    if contains_any(text, ai_terms):
        return "strategic"
    if contains_any(text, weak_terms):
        return "weak_roundup"
    if symbol in MEGA_CAPS:
        return "single_stock_megacap"
    return "single_stock"


def score_article(symbol: str, headline: str, summary: str) -> int:
    text = f"{headline} {summary}".lower()
    score = 0

    relevant = symbol_is_relevant(symbol, headline, summary)
    broad_market = is_broad_market_story(headline, summary)
    story_type = classify_story(symbol, headline, summary)

    if relevant:
        score += 3

    if symbol in MEGA_CAPS:
        score += 1

    if story_type == "broad_macro":
        score += 4
    elif story_type == "earnings":
        score += 4
    elif story_type == "regulatory":
        score += 3
    elif story_type == "deal":
        score += 2
    elif story_type == "strategic":
        score += 2
    elif story_type == "single_stock_megacap":
        score += 1
    elif story_type == "weak_roundup":
        score -= 4

    if broad_market:
        score += 2

    weak_isolated_terms = [
        "expands",
        "launches",
        "partnership",
        "collaboration",
        "new feature",
        "pilot program",
        "consumer rollout",
    ]
    if contains_any(text, weak_isolated_terms) and not broad_market:
        score -= 2

    if "globalstar" in text and not broad_market:
        score -= 2

    return score


def build_guidance(symbol: str, headline: str, summary: str, score: int) -> tuple[str, str]:
    broad_market = is_broad_market_story(headline, summary)
    story_type = classify_story(symbol, headline, summary)

    if score >= 11:
        severity = "HIGH"
    elif score >= 8:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    if broad_market or story_type == "broad_macro":
        guidance = "Broad market catalyst detected. Elevated index sensitivity."
    elif symbol in MEGA_CAPS and story_type in {"earnings", "regulatory", "strategic"}:
        guidance = "Major company catalyst detected. Monitor for tech/index spillover."
    elif symbol in MEGA_CAPS:
        guidance = "Company-specific catalyst detected. Monitor for limited spillover."
    else:
        guidance = "Isolated company headline. Broad index reaction not confirmed."

    return severity, guidance

# =========================
# MAIN CYCLE
# =========================
def process_finnhub_cycle() -> None:
    best_score = 0
    best_headline = ""
    best_symbol = ""
    best_guidance = ""
    best_severity = ""
    best_url = ""
    best_warnings: list[str] = []

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

            if url in seen_urls or norm_title in seen_titles:
                continue

            relevant_to_symbol = symbol_is_relevant(symbol, headline, summary)
            broad_market = is_broad_market_story(headline, summary)

            if not relevant_to_symbol and not broad_market:
                continue

            score = score_article(symbol, headline, summary)

            if score > best_score:
                severity, guidance = build_guidance(symbol, headline, summary, score)

                best_score = score
                best_headline = headline
                best_symbol = symbol
                best_guidance = guidance
                best_severity = severity
                best_url = url

                if broad_market:
                    best_warnings = ["Broad market catalyst is raising market-news pressure"]
                elif symbol in MEGA_CAPS and score >= MIN_ALERT_SCORE:
                    best_warnings = [f"{symbol} catalyst may create limited tech/index spillover"]
                else:
                    best_warnings = [f"{symbol} company-specific headline detected"]

                if score >= MIN_ALERT_SCORE:
                    seen_urls.add(url)
                    seen_titles.add(norm_title)

    if best_score >= 11:
        risk = "high"
    elif best_score >= 8:
        risk = "medium"
    else:
        risk = "low"
        best_warnings = []

    save_market_state(
        risk=risk,
        warnings=best_warnings,
        last_headline=best_headline,
        symbol=best_symbol,
        severity=best_severity,
        guidance=best_guidance,
        url=best_url,
    )

    if best_score >= MIN_ALERT_SCORE:
        print("Donna Finnhub Guard updated Donna-only market state:", best_symbol, best_severity, best_headline)
    else:
        print("Donna Finnhub Guard: no Donna-only market item strong enough this cycle.")
