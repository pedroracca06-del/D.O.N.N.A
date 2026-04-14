from __future__ import annotations

from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timezone
import os
import json
import requests

# ==================================================
# ENV / PATHS
# ==================================================
BASE_DIR = Path(__file__).parent
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")

RISK_STATE_FILE = BASE_DIR / "donna_risk_state.json"

# ==================================================
# SETTINGS
# ==================================================
REQUEST_TIMEOUT = 20
MAX_HEADLINES = 12

NEWS_URL = "https://newsapi.org/v2/top-headlines"

TRUSTED_SOURCES = {
    "reuters",
    "associated-press",
    "bloomberg",
    "cnbc",
    "financial-times",
    "the-wall-street-journal",
    "business-insider",
    "marketwatch",
    "yahoo-finance",
}

seen_titles: set[str] = set()

# ==================================================
# KEYWORD MAP
# ==================================================
CRITICAL_KEYWORDS = [
    "war",
    "missile",
    "attack",
    "strike",
    "invasion",
    "nuclear",
    "sanction",
    "blockade",
    "shipping lane",
    "strait",
    "hormuz",
    "terror",
    "emergency fed",
    "bank collapse",
    "default",
]

HIGH_KEYWORDS = [
    "powell",
    "fomc",
    "federal reserve",
    "rate cut",
    "rate hike",
    "inflation",
    "cpi",
    "ppi",
    "jobs report",
    "yield surge",
    "treasury yields",
    "tariff",
    "trump",
    "white house",
    "treasury secretary",
    "oil jumps",
    "opec",
]

MEDIUM_KEYWORDS = [
    "earnings",
    "guidance",
    "downgrade",
    "upgrade",
    "ai spending",
    "chips",
    "big tech",
    "merger",
    "acquisition",
    "recession",
]

# ==================================================
# HELPERS
# ==================================================
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def normalize(text: str) -> str:
    return " ".join(str(text).lower().split())


def contains_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)

# ==================================================
# FETCH
# ==================================================
def fetch_headlines() -> list[dict]:
    if not NEWSAPI_KEY:
        raise RuntimeError("Missing NEWSAPI_KEY")

    params = {
        "language": "en",
        "pageSize": MAX_HEADLINES,
        "apiKey": NEWSAPI_KEY,
        "category": "business",
    }

    response = requests.get(NEWS_URL, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    data = response.json()

    if data.get("status") != "ok":
        raise RuntimeError("NewsAPI bad response")

    return data.get("articles", [])

# ==================================================
# SCORING
# ==================================================
def source_score(source_id: str, source_name: str) -> int:
    source_id = normalize(source_id)
    source_name = normalize(source_name)

    if source_id in TRUSTED_SOURCES:
        return 3

    if "reuters" in source_name or "bloomberg" in source_name or "cnbc" in source_name:
        return 3

    if "finance" in source_name or "market" in source_name:
        return 2

    return 1


def headline_score(title: str, description: str) -> tuple[int, str]:
    text = normalize(f"{title} {description}")
    score = 0
    lane = "background"

    if contains_any(text, CRITICAL_KEYWORDS):
        score += 8
        lane = "critical"

    if contains_any(text, HIGH_KEYWORDS):
        score += 5
        lane = "high" if lane != "critical" else lane

    if contains_any(text, MEDIUM_KEYWORDS):
        score += 2
        if lane == "background":
            lane = "medium"

    # Broad market phrases
    broad_terms = [
        "stocks fall",
        "stocks rally",
        "markets tumble",
        "markets rise",
        "nasdaq",
        "s&p 500",
        "dow jones",
        "wall street",
        "global markets",
    ]

    if contains_any(text, broad_terms):
        score += 3

    # Surprise / urgency words
    urgency_terms = [
        "unexpected",
        "surge",
        "plunge",
        "shocks",
        "crashes",
        "jumps",
        "slumps",
        "emergency",
    ]

    if contains_any(text, urgency_terms):
        score += 2

    return score, lane


def classify(score: int) -> tuple[str, str]:
    if score >= 11:
        return "high", "CRITICAL"
    if score >= 8:
        return "medium", "HIGH"
    if score >= 5:
        return "medium", "MEDIUM"
    return "low", "BACKGROUND"


def build_guidance(severity: str, title: str) -> str:
    text = normalize(title)

    if severity == "CRITICAL":
        return "Major global market-moving headline detected. Elevated volatility risk."

    if "powell" in text or "federal reserve" in text or "fomc" in text:
        return "Fed communication risk elevated. Rates-sensitive assets may react."

    if "trump" in text or "tariff" in text or "white house" in text:
        return "Policy communication risk elevated. Watch indices and USD."

    if "oil" in text or "hormuz" in text or "opec" in text:
        return "Energy headline detected. Watch oil, inflation expectations, risk sentiment."

    if severity == "HIGH":
        return "High-impact headline detected. Broad market sensitivity elevated."

    if severity == "MEDIUM":
        return "Relevant headline detected. Monitor for follow-through."

    return "Low-priority headline. Background monitoring only."

# ==================================================
# MAIN CYCLE
# ==================================================
def process_headlines_cycle() -> None:
    try:
        articles = fetch_headlines()

        best_score = 0
        best_title = ""
        best_source = ""
        best_risk = "low"
        best_severity = "BACKGROUND"
        best_guidance = ""

        for article in articles:
            title = str(article.get("title", "")).strip()
            description = str(article.get("description", "")).strip()

            source = article.get("source", {}) or {}
            source_id = str(source.get("id", "")).strip()
            source_name = str(source.get("name", "")).strip()

            if not title:
                continue

            norm_title = normalize(title)

            if norm_title in seen_titles:
                continue

            base_score, lane = headline_score(title, description)
            trust = source_score(source_id, source_name)

            total = base_score + trust

            if total > best_score:
                risk, severity = classify(total)

                best_score = total
                best_title = title
                best_source = source_name or source_id
                best_risk = risk
                best_severity = severity
                best_guidance = build_guidance(severity, title)

        state = load_state()

        # keep non-headline warnings
        existing = state.get("active_warnings", [])
        keep = [w for w in existing if not str(w).startswith("HEADLINE:")]

        warnings = []
        if best_score >= 8:
            warnings.append(f"HEADLINE: {best_severity} news risk active")

        state["headline_risk"] = best_risk
        state["active_warnings"] = keep + warnings
        state["last_headline"] = best_title
        state["headline_severity"] = best_severity
        state["headline_guidance"] = best_guidance
        state["headline_source"] = best_source

        save_state(state)

        if best_title:
            seen_titles.add(normalize(best_title))

        print(
            "Donna Headlines:",
            best_severity,
            "|",
            best_title if best_title else "No major headline"
        )

    except Exception as e:
        print("Donna Headline Guard error:", str(e))
