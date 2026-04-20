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
MAX_HEADLINES = 15
NEWS_URL = "https://newsapi.org/v2/top-headlines"

TRUSTED_SOURCES = {
    "reuters",
    "associated-press",
    "bloomberg",
    "cnbc",
    "financial-times",
    "the-wall-street-journal",
    "marketwatch",
    "yahoo-finance",
}

seen_titles: set[str] = set()

# ==================================================
# STRICT KEYWORD MAP
# ==================================================
CRITICAL_PHRASES = [
    "strait of hormuz",
    "emergency fed",
    "bank collapse",
    "bank failure",
    "debt default",
    "terror attack",
    "martial law",
    "oil supply disruption",
    "shipping lane closed",
    "missile strike",
    "military strike",
]

CRITICAL_SINGLE_WORDS = [
    "invasion",
    "blockade",
    "nuclear",
]

HIGH_MACRO_POLICY_KEYWORDS = [
    "powell",
    "federal reserve",
    "fomc",
    "rate decision",
    "rate hike",
    "rate cut",
    "inflation",
    "cpi",
    "ppi",
    "pce",
    "jobs report",
    "nonfarm payrolls",
    "tariff",
    "white house",
    "treasury secretary",
    "executive order",
    "opec",
    "sanctions",
]

MEDIUM_MARKET_KEYWORDS = [
    "treasury yields",
    "yield surge",
    "yield spike",
    "big tech",
    "chips",
    "ai spending",
    "ai capex",
    "bank earnings",
    "earnings",
    "guidance",
    "downgrade",
    "upgrade",
    "merger",
    "acquisition",
    "recession",
]

LOW_SIGNAL_TERMS = [
    "opinion",
    "analysis:",
    "what to know",
    "live updates",
    "live coverage",
    "roundup",
    "market recap",
    "watch these stocks",
    "top stocks to watch",
]

BROAD_MARKET_TERMS = [
    "wall street",
    "global markets",
    "stocks fall",
    "stocks rally",
    "markets tumble",
    "markets rise",
    "nasdaq",
    "s&p 500",
    "dow jones",
    "risk-off",
    "risk appetite",
]

URGENCY_TERMS = [
    "unexpected",
    "surge",
    "spike",
    "jumps",
    "slumps",
    "crashes",
    "plunges",
    "shocks",
    "emergency",
]

ROUTINE_FINANCE_TERMS = [
    "record quarter",
    "quarterly profit",
    "quarterly results",
    "revenue beat",
    "analyst expectations",
    "private credit",
    "fund flows",
    "banking and trading",
]

# ==================================================
# HELPERS
# ==================================================
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize(text: str) -> str:
    return " ".join(str(text).lower().split())


def contains_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


def contains_whole_word(text: str, word: str) -> bool:
    parts = text.replace("/", " ").replace("-", " ").replace(",", " ").replace(".", " ").split()
    return word in parts


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
        raise RuntimeError(f"NewsAPI bad response: {data}")

    articles = data.get("articles", [])
    return articles if isinstance(articles, list) else []

# ==================================================
# SOURCE / SCORING
# ==================================================
def source_score(source_id: str, source_name: str) -> int:
    sid = normalize(source_id)
    sname = normalize(source_name)

    if sid in TRUSTED_SOURCES:
        return 3

    if "reuters" in sname or "bloomberg" in sname or "cnbc" in sname:
        return 3

    if "finance" in sname or "market" in sname or "journal" in sname:
        return 2

    return 1


def is_true_critical_shock(title: str, description: str) -> bool:
    text = normalize(f"{title} {description}")

    if contains_any(text, CRITICAL_PHRASES):
        return True

    # Only allow a few single words as critical, and only if broad market/geopolitical context exists
    has_single_critical = any(contains_whole_word(text, w) for w in CRITICAL_SINGLE_WORDS)
    has_broad_context = contains_any(
        text,
        BROAD_MARKET_TERMS + ["oil", "shipping", "military", "iran", "israel", "taiwan", "russia", "china"]
    )

    if has_single_critical and has_broad_context:
        return True

    return False


def classify_lane(title: str, description: str) -> str:
    text = normalize(f"{title} {description}")

    if is_true_critical_shock(title, description):
        return "critical_shock"

    if contains_any(text, HIGH_MACRO_POLICY_KEYWORDS):
        return "high_macro_policy"

    if contains_any(text, MEDIUM_MARKET_KEYWORDS):
        return "medium_market"

    return "background"


def score_headline(title: str, description: str, source_id: str, source_name: str) -> tuple[int, str]:
    text = normalize(f"{title} {description}")
    lane = classify_lane(title, description)
    score = 0

    if lane == "critical_shock":
        score += 9
    elif lane == "high_macro_policy":
        score += 6
    elif lane == "medium_market":
        score += 3

    if contains_any(text, BROAD_MARKET_TERMS):
        score += 3

    if contains_any(text, URGENCY_TERMS):
        score += 2

    if contains_any(text, LOW_SIGNAL_TERMS):
        score -= 4

    if contains_any(text, ROUTINE_FINANCE_TERMS):
        score -= 4

    if lane in {"critical_shock", "high_macro_policy"} and contains_any(text, BROAD_MARKET_TERMS):
        score += 2

    score += source_score(source_id, source_name)

    return score, lane


def map_score_to_risk(score: int, lane: str) -> tuple[str, str]:
    if lane == "critical_shock" and score >= 11:
        return "high", "CRITICAL"

    if lane == "high_macro_policy" and score >= 9:
        return "medium", "HIGH"

    if lane == "medium_market" and score >= 5:
        return "medium", "MEDIUM"

    if score >= 9:
        return "medium", "HIGH"

    if score >= 5:
        return "medium", "MEDIUM"

    return "low", "BACKGROUND"


def build_guidance(title: str, description: str, severity: str, lane: str) -> str:
    text = normalize(f"{title} {description}")

    if severity == "CRITICAL":
        return "Major global market-moving headline detected. Treat conditions as elevated risk."

    if "powell" in text or "federal reserve" in text or "fomc" in text:
        return "Fed communication risk is elevated. Rates-sensitive assets may react."

    if "trump" in text or "tariff" in text or "white house" in text:
        return "Policy communication risk is elevated. Watch indices, USD, and rates."

    if "oil" in text or "hormuz" in text or "opec" in text or "shipping" in text:
        return "Energy and supply-risk headline detected. Watch oil, inflation expectations, and risk sentiment."

    if severity == "HIGH":
        return "High-impact headline detected. Broad market sensitivity is elevated."

    if severity == "MEDIUM":
        return "Relevant market headline detected. Monitor for follow-through, not panic."

    return "Low-priority headline. No strong market warning from this item."

# ==================================================
# MAIN CYCLE
# ==================================================
import time
import requests

NEWSAPI_COOLDOWN_UNTIL = 0.0


def process_headlines_cycle() -> None:
    global NEWSAPI_COOLDOWN_UNTIL

    now = time.time()
    if now < NEWSAPI_COOLDOWN_UNTIL:
        remaining = int((NEWSAPI_COOLDOWN_UNTIL - now) // 60)
        print(f"Donna Headline Guard cooldown active. Skipping cycle for ~{remaining} more min.")
        return

    try:
        articles = fetch_headlines()

        best_score = -999
        best_title = ""
        best_description = ""
        best_source = ""
        best_risk = "low"
        best_severity = "BACKGROUND"
        best_guidance = ""
        best_lane = "background"

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

            score, lane = score_headline(title, description, source_id, source_name)
            risk, severity = map_score_to_risk(score, lane)
            guidance = build_guidance(title, description, severity, lane)

            if score > best_score:
                best_score = score
                best_title = title
                best_description = description
                best_source = source_name or source_id or "Unknown"
                best_risk = risk
                best_severity = severity
                best_guidance = guidance
                best_lane = lane

        state = load_state()

        existing = state.get("active_warnings", [])
        keep = [w for w in existing if not str(w).startswith("HEADLINE:")]

        warnings = []
        if best_severity == "CRITICAL":
            warnings.append("HEADLINE: Critical global headline risk active")
        elif best_severity == "HIGH":
            warnings.append("HEADLINE: High-impact headline risk active")
        elif best_severity == "MEDIUM":
            warnings.append("HEADLINE: Moderate headline pressure active")

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
            best_lane,
            "|",
            best_title if best_title else "No major headline",
        )

    except requests.HTTPError as e:
        status = getattr(e.response, "status_code", None)

        if status == 429:
            NEWSAPI_COOLDOWN_UNTIL = time.time() + 3600
            print("Donna Headline Guard rate-limited by NewsAPI. Cooling down for 60 minutes.")
            return

        print("Donna Headline Guard HTTP error:", str(e))

    except Exception as e:
        print("Donna Headline Guard error:", str(e))
    try:
        articles = fetch_headlines()

        best_score = -999
        best_title = ""
        best_description = ""
        best_source = ""
        best_risk = "low"
        best_severity = "BACKGROUND"
        best_guidance = ""
        best_lane = "background"

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

            score, lane = score_headline(title, description, source_id, source_name)
            risk, severity = map_score_to_risk(score, lane)
            guidance = build_guidance(title, description, severity, lane)

            if score > best_score:
                best_score = score
                best_title = title
                best_description = description
                best_source = source_name or source_id or "Unknown"
                best_risk = risk
                best_severity = severity
                best_guidance = guidance
                best_lane = lane

        state = load_state()

        existing = state.get("active_warnings", [])
        keep = [w for w in existing if not str(w).startswith("HEADLINE:")]

        warnings = []
        if best_severity == "CRITICAL":
            warnings.append("HEADLINE: Critical global headline risk active")
        elif best_severity == "HIGH":
            warnings.append("HEADLINE: High-impact headline risk active")
        elif best_severity == "MEDIUM":
            warnings.append("HEADLINE: Moderate headline pressure active")

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
            best_lane,
            "|",
            best_title if best_title else "No major headline",
        )

    except Exception as e:
        print("Donna Headline Guard error:", str(e))
