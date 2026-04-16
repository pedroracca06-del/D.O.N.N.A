from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import HTMLResponse
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any
import asyncio
import os
import json
import re
import requests

# ==================================================
# OPTIONAL EXTERNAL WORKERS
# ==================================================
# Donna should still boot even if one worker is missing.
try:
    from donna_news import process_news_guard_cycle
except Exception:
    def process_news_guard_cycle():
        return None

try:
    from donna_headlines import process_headlines_cycle
except Exception:
    def process_headlines_cycle():
        return None

try:
    from donna_finnhub import process_finnhub_cycle
except Exception:
    def process_finnhub_cycle():
        return None


# ==================================================
# APP / ENV
# ==================================================
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
TELEGRAM_ALERT_MODE = os.getenv("TELEGRAM_ALERT_MODE", "all").strip().lower()

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
app = FastAPI(title="DONNA Premium Core", version="1.0")


# ==================================================
# FILES / PERSISTENCE
# ==================================================
RISK_STATE_FILE = BASE_DIR / "donna_risk_state.json"
ALERTS_FILE = BASE_DIR / "donna_alert_history.json"
ASSISTANT_FILE = BASE_DIR / "donna_assistant_state.json"
SETTINGS_FILE = BASE_DIR / "donna_settings.json"


# ==================================================
# TIME
# ==================================================
NY_TZ = ZoneInfo("America/New_York")
UTC_TZ = ZoneInfo("UTC")


def now_ny() -> datetime:
    return datetime.now(NY_TZ)


def now_utc() -> datetime:
    return datetime.now(UTC_TZ)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_day() -> str:
    return now_ny().strftime("%A")


def current_session(dt: datetime | None = None) -> str:
    dt = dt or now_ny()
    minutes = dt.hour * 60 + dt.minute
    if minutes >= 19 * 60 or minutes < 3 * 60:
        return "ASIA"
    if 3 * 60 <= minutes < 9 * 60 + 30:
        return "LONDON"
    if 9 * 60 + 30 <= minutes < 16 * 60:
        return "NEW_YORK_CASH"
    return "OFF_HOURS"


# ==================================================
# POLL TIMERS
# ==================================================
NEWS_POLL_SECONDS = 900
HEADLINE_POLL_SECONDS = 900
FINNHUB_POLL_SECONDS = 600


# ==================================================
# PROMPTS
# ==================================================
DONNA_SIGNAL_PROMPT = """
You are Donna, an elite trading intelligence assistant.

Return plain text in exactly this format:
Verdict: TAKE | CAUTION | SKIP
Confidence: XX%
Why: short explanation
Risk: short risk summary
Execution: short execution note
Summary: one concise final line

Rules:
- Be decisive.
- Keep it short.
- No markdown.
- No JSON.
""".strip()

DONNA_ASSISTANT_PROMPT = """
You are Donna, the command center assistant inside a live market dashboard.

Tone:
Sharp. Premium. Concise. Operator energy.

You must return ONLY valid JSON in this exact shape:
{
  "action": "none | set_focus | add_task | add_reminder | clear_tasks | clear_reminders",
  "value": "string or empty string",
  "reply": "short direct response"
}

Rules:
- Use system state to answer what matters now, what can move the market, and whether risk is elevated.
- If the user asks for tasks/reminders/focus changes, choose the correct action.
- Never output markdown.
- Never output any text outside the JSON.
""".strip()


# ==================================================
# DEFAULT STATE BUILDERS
# ==================================================
def default_risk_state() -> dict[str, Any]:
    return {
        "macro_risk": "low",
        "headline_risk": "low",
        "market_news_risk": "low",
        "active_warnings": [],
        "next_event": "",
        "minutes_to_event": None,
        "event_phase": "",
        "event_time_ny": "",
        "last_headline": "",
        "headline_severity": "",
        "headline_guidance": "",
        "headline_source": "",
        "last_market_headline": "",
        "last_market_symbol": "",
        "last_market_severity": "",
        "last_market_guidance": "",
        "last_market_url": "",
        "donna_time_ny": now_ny().isoformat(),
        "donna_time_utc": now_utc().isoformat(),
        "donna_day": current_day(),
        "donna_session": current_session(),
        "last_updated": utc_now_iso(),
    }


def default_assistant_state() -> dict[str, Any]:
    return {
        "daily_focus": "Build Donna into a true command center.",
        "tasks": [
            "Review what matters now",
            "Check the likely market movers",
            "Stay selective around macro events",
        ],
        "reminders": [
            "Watch the next macro event window",
            "Do not overtrade low-quality conditions",
        ],
        "last_updated": utc_now_iso(),
    }


def default_settings() -> dict[str, Any]:
    return {
        "premium_theme": "donna_dark",
        "market_watchlist": ["NQ", "ES", "SPX", "NVDA", "MSFT", "TSLA"],
        "telegram_alert_mode": TELEGRAM_ALERT_MODE or "all",
        "last_updated": utc_now_iso(),
    }


# ==================================================
# FILE HELPERS
# ==================================================
def load_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception:
        return default


def save_json(path: Path, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_risk_state() -> dict[str, Any]:
    state = load_json(RISK_STATE_FILE, default_risk_state())
    if not isinstance(state, dict):
        state = default_risk_state()
    merged = {**default_risk_state(), **state}
    merged["donna_time_ny"] = now_ny().isoformat()
    merged["donna_time_utc"] = now_utc().isoformat()
    merged["donna_day"] = current_day()
    merged["donna_session"] = current_session()
    if not isinstance(merged.get("active_warnings"), list):
        merged["active_warnings"] = []
    return merged


def save_risk_state(state: dict[str, Any]) -> None:
    state = {**default_risk_state(), **state}
    state["donna_time_ny"] = now_ny().isoformat()
    state["donna_time_utc"] = now_utc().isoformat()
    state["donna_day"] = current_day()
    state["donna_session"] = current_session()
    state["last_updated"] = utc_now_iso()
    save_json(RISK_STATE_FILE, state)


def load_alert_history() -> list[dict[str, Any]]:
    data = load_json(ALERTS_FILE, [])
    return data if isinstance(data, list) else []


def save_alert_history(alerts: list[dict[str, Any]]) -> None:
    save_json(ALERTS_FILE, alerts)


def load_assistant_state() -> dict[str, Any]:
    state = load_json(ASSISTANT_FILE, default_assistant_state())
    if not isinstance(state, dict):
        state = default_assistant_state()
    merged = {**default_assistant_state(), **state}
    if not isinstance(merged.get("tasks"), list):
        merged["tasks"] = default_assistant_state()["tasks"]
    if not isinstance(merged.get("reminders"), list):
        merged["reminders"] = default_assistant_state()["reminders"]
    return merged


def save_assistant_state(state: dict[str, Any]) -> None:
    state = {**default_assistant_state(), **state}
    state["last_updated"] = utc_now_iso()
    save_json(ASSISTANT_FILE, state)


def load_settings() -> dict[str, Any]:
    settings = load_json(SETTINGS_FILE, default_settings())
    return settings if isinstance(settings, dict) else default_settings()


def save_settings(settings: dict[str, Any]) -> None:
    settings = {**default_settings(), **settings}
    settings["last_updated"] = utc_now_iso()
    save_json(SETTINGS_FILE, settings)


# ==================================================
# GENERIC HELPERS
# ==================================================
def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def parse_json_loose(text: str, fallback: dict[str, Any]) -> dict[str, Any]:
    if not text:
        return fallback
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    return fallback


def extract_fields(text: str) -> dict[str, str]:
    if not text:
        return {
            "verdict": "UNKNOWN",
            "confidence": "N/A",
            "why": "No response.",
            "risk": "Unknown.",
            "execution": "Stand by.",
            "summary": "No summary.",
        }

    def grab(label: str, default: str) -> str:
        m = re.search(rf"{label}:\s*(.+)", text, re.IGNORECASE)
        return m.group(1).strip() if m else default

    return {
        "verdict": grab("Verdict", "UNKNOWN").upper(),
        "confidence": grab("Confidence", "N/A"),
        "why": grab("Why", "No reason."),
        "risk": grab("Risk", "Unknown."),
        "execution": grab("Execution", "Stand by."),
        "summary": grab("Summary", text.strip()),
    }


def normalize_payload(payload: dict[str, Any]) -> dict[str, str]:
    return {
        "ticker": str(payload.get("ticker", "UNKNOWN")),
        "price": str(payload.get("price", "0")),
        "signal": str(payload.get("signal", "NONE")).upper(),
        "timeframe": str(payload.get("timeframe", "unknown")),
        "session": str(payload.get("session", "unknown")),
        "setup_type": str(payload.get("setup_type", "unknown")),
        "signal_priority": str(payload.get("signal_priority", "unknown")),
        "context_strength": str(payload.get("context_strength", "unknown")),
        "market_state": str(payload.get("market_state", "neutral")),
        "scenario": str(payload.get("scenario", "none")),
        "fib_zone": str(payload.get("fib_zone", "none")),
        "liquidity": str(payload.get("liquidity", "unknown")),
        "bias": str(payload.get("bias", "neutral")),
        "score": str(payload.get("score", "0")),
        "quality": str(payload.get("quality", "NA")).upper(),
    }


def add_alert_to_history(data: dict[str, str], parsed: dict[str, str]) -> None:
    alerts = load_alert_history()
    alerts.insert(0, {
        "ticker": data.get("ticker", "UNKNOWN"),
        "signal": data.get("signal", "UNKNOWN"),
        "session": data.get("session", "unknown"),
        "timeframe": data.get("timeframe", "unknown"),
        "price": data.get("price", "0"),
        "verdict": parsed.get("verdict", "UNKNOWN"),
        "confidence": parsed.get("confidence", "N/A"),
        "summary": parsed.get("summary", ""),
        "timestamp": utc_now_iso(),
    })
    save_alert_history(alerts[:50])


# ==================================================
# TELEGRAM
# ==================================================
def send_telegram_message(text: str) -> dict[str, Any]:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return {"ok": False, "error": "Telegram not configured"}
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=20,
        )
        return response.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}


def should_send_trade_to_telegram(parsed: dict[str, Any]) -> bool:
    mode = (load_settings().get("telegram_alert_mode") or TELEGRAM_ALERT_MODE or "all").lower()
    if mode == "off":
        return False
    if mode == "all":
        return True
    verdict = str(parsed.get("verdict", "")).upper()
    confidence_raw = str(parsed.get("confidence", "0")).replace("%", "").strip()
    try:
        confidence_num = float(confidence_raw)
    except Exception:
        confidence_num = 0.0
    if mode == "critical":
        return verdict == "TAKE" or confidence_num >= 80
    return True


# ==================================================
# CORE INTELLIGENCE ENGINES
# ==================================================
def pre_verdict_engine(data: dict[str, str]) -> str:
    score = safe_float(data["score"])
    quality = data["quality"]
    context = data["context_strength"].lower()
    session = data["session"].upper()
    market_state = data["market_state"].lower()
    bias = data["bias"].lower()
    signal = data["signal"]
    points = 0

    if score >= 80:
        points += 4
    elif score >= 70:
        points += 3
    elif score >= 60:
        points += 2
    elif score >= 50:
        points += 1
    else:
        points -= 2

    if quality == "A":
        points += 3
    elif quality == "B":
        points += 2
    elif quality == "C":
        points += 0
    else:
        points -= 1

    if context == "strong":
        points += 3
    elif context == "moderate":
        points += 1
    else:
        points -= 1

    if session in {"NY", "NY_PRE", "LONDON", "NEW_YORK_CASH"}:
        points += 2
    elif session == "ASIA":
        points -= 1

    aligned = (
        (signal == "LONG" and market_state != "bearish" and bias != "bearish")
        or
        (signal == "SHORT" and market_state != "bullish" and bias != "bullish")
    )

    points += 2 if aligned else -3

    if points >= 10:
        return "TAKE"
    if points >= 5:
        return "CAUTION"
    return "SKIP"


def apply_fusion_overlay(base_verdict: str, risk: dict[str, Any], data: dict[str, str]) -> str:
    macro = str(risk.get("macro_risk", "low")).lower()
    headline = str(risk.get("headline_risk", "low")).lower()
    market = str(risk.get("market_news_risk", "low")).lower()
    ticker = str(data.get("ticker", "")).upper()

    is_nq = any(x in ticker for x in ["NQ", "MNQ", "QQQ", "NASDAQ"])
    is_es = any(x in ticker for x in ["ES", "MES", "SPX", "SPY", "S&P"])

    if is_nq:
        if macro == "high":
            return "SKIP"
        if (market == "high" or macro == "medium" or headline == "high") and base_verdict == "TAKE":
            return "CAUTION"

    if is_es:
        if macro == "high":
            return "SKIP"
        if (macro == "medium" or headline == "high") and base_verdict == "TAKE":
            return "CAUTION"

    high_count = sum(x == "high" for x in [macro, headline, market])
    if base_verdict == "TAKE" and high_count >= 1:
        return "CAUTION"
    if base_verdict == "CAUTION" and high_count >= 2:
        return "SKIP"
    return base_verdict


def confidence_bias(risk: dict[str, Any], data: dict[str, str]) -> str:
    macro = str(risk.get("macro_risk", "low")).lower()
    headline = str(risk.get("headline_risk", "low")).lower()
    market = str(risk.get("market_news_risk", "low")).lower()
    ticker = str(data.get("ticker", "")).upper()
    penalty = 0
    penalty += 25 if macro == "high" else 12 if macro == "medium" else 0
    penalty += 18 if headline == "high" else 8 if headline == "medium" else 0
    penalty += 15 if market == "high" else 6 if market == "medium" else 0
    if any(x in ticker for x in ["NQ", "MNQ", "QQQ"]) and market in {"medium", "high"}:
        penalty += 5
    if any(x in ticker for x in ["ES", "MES", "SPX", "SPY"]) and macro in {"medium", "high"}:
        penalty += 5
    if penalty >= 30:
        return "Strongly reduce confidence."
    if penalty >= 15:
        return "Reduce confidence."
    if penalty > 0:
        return "Slightly reduce confidence."
    return "Normal confidence."


def build_market_driver_engine() -> dict[str, str]:
    state = load_risk_state()
    macro = str(state.get("macro_risk", "low")).lower()
    headline = str(state.get("headline_risk", "low")).lower()
    market = str(state.get("market_news_risk", "low")).lower()
    next_event = str(state.get("next_event", ""))
    event_phase = str(state.get("event_phase", ""))
    session = str(state.get("donna_session", "OFF_HOURS"))
    headline_text = str(state.get("last_headline", "")).lower()
    market_text = str(state.get("last_market_headline", "")).lower()

    dominant_driver = "Balanced Conditions"
    secondary_driver = "No clear secondary force"
    regime = "Neutral"
    threat = "None"
    confidence = "Low"
    summary = "No strong market driver currently detected."

    if any(x in market_text for x in ["nvidia", "microsoft", "apple", "amazon", "meta", "google", "tesla", "ai"]):
        dominant_driver = "AI / Mega-Cap Leadership"
        regime = "Risk-On Trend"
        confidence = "High"
        summary = "Large-cap leadership is supporting index strength."

    if macro == "high":
        dominant_driver = "Macro Event Risk"
        regime = "High Volatility"
        threat = next_event or "Upcoming Event"
        confidence = "High"
        summary = "Macro timing is dominating market behavior."
    elif macro == "medium" and regime == "Neutral":
        dominant_driver = "Macro Positioning"
        regime = "Cautious Trend"
        confidence = "Medium"
        summary = "Markets are positioning around upcoming macro risk."

    if headline == "high":
        dominant_driver = "Headline Shock"
        regime = "Reactive Conditions"
        confidence = "High"
        summary = "Breaking headlines are driving price reaction."

    if market == "high" and dominant_driver == "Balanced Conditions":
        dominant_driver = "Company / Earnings Catalyst"
        regime = "Catalyst Driven"
        confidence = "Medium"
        summary = "Company-specific catalysts are influencing index direction."

    if event_phase == "LIVE":
        threat = "Live Macro Release"
        regime = "Volatility Expansion"
    elif event_phase == "IMMINENT":
        threat = next_event or "Event Imminent"
    elif event_phase == "POST_EVENT_COOLDOWN":
        secondary_driver = "Post-Event Repricing"

    if session == "ASIA" and confidence == "Low":
        regime = "Thin Liquidity"
    elif session == "LONDON" and confidence == "Low":
        regime = "Expansion Window"
    elif session == "NEW_YORK_CASH" and confidence == "Low":
        regime = "Primary Volume Session"

    if "yield" in headline_text or "rates" in headline_text:
        secondary_driver = "Rates Sensitivity"
    elif "oil" in headline_text:
        secondary_driver = "Energy Pressure"
    elif "war" in headline_text or "iran" in headline_text:
        secondary_driver = "Geopolitical Risk"
    elif "fed" in headline_text or "powell" in headline_text:
        secondary_driver = "Federal Reserve Guidance"

    return {
        "dominant_driver": dominant_driver,
        "secondary_driver": secondary_driver,
        "market_regime": regime,
        "market_threat": threat,
        "market_confidence": confidence,
        "market_summary": summary,
    }


def build_market_movers_intelligence() -> dict[str, list[dict[str, str]]]:
    risk = load_risk_state()
    market_text = str(risk.get("last_market_headline", "")).lower()
    headline_text = str(risk.get("last_headline", "")).lower()

    leaders = [
        {"ticker": "NVDA", "company": "NVIDIA", "impact": "Very High", "index": "NQ / QQQ / SPX", "catalyst": "AI leadership / guidance", "why": "Can drag or lift the entire Nasdaq tone."},
        {"ticker": "MSFT", "company": "Microsoft", "impact": "Very High", "index": "NQ / SPX", "catalyst": "Cloud / AI capex", "why": "Mega-cap stabilizer and leadership name."},
        {"ticker": "AAPL", "company": "Apple", "impact": "Very High", "index": "NQ / SPX", "catalyst": "Consumer demand / product cycle", "why": "Huge index weight and sentiment anchor."},
        {"ticker": "AMZN", "company": "Amazon", "impact": "High", "index": "NQ / SPX", "catalyst": "Cloud / retail demand", "why": "Major broad-market and tech sentiment driver."},
        {"ticker": "META", "company": "Meta", "impact": "High", "index": "NQ / SPX", "catalyst": "Ad spend / AI spend", "why": "Momentum leadership name in mega-cap risk-on conditions."},
    ]

    threats = [
        {"ticker": "TSLA", "company": "Tesla", "impact": "High", "index": "NQ / QQQ", "catalyst": "Headlines / deliveries / margin pressure", "why": "High-beta sentiment mover that can distort intraday tone."},
        {"ticker": "JPM", "company": "JPMorgan", "impact": "Medium / High", "index": "SPX / DJIA", "catalyst": "Banks / credit tone", "why": "Can signal broad risk appetite through financials."},
        {"ticker": "XOM", "company": "Exxon", "impact": "Medium", "index": "SPX", "catalyst": "Energy / oil shocks", "why": "Matters more when crude and geopolitics are active."},
    ]

    next_to_watch = [
        {"ticker": "AVGO", "company": "Broadcom", "impact": "High", "index": "NQ / QQQ", "catalyst": "Semis / AI infrastructure", "why": "Broad semiconductor sympathy mover."},
        {"ticker": "AMD", "company": "AMD", "impact": "High", "index": "NQ / QQQ", "catalyst": "AI chip positioning", "why": "Can reinforce or weaken semiconductor leadership."},
        {"ticker": "GOOGL", "company": "Alphabet", "impact": "High", "index": "NQ / SPX", "catalyst": "AI / search / ads", "why": "Large weight and sentiment signal for mega-cap tech."},
    ]

    if "oil" in headline_text or "iran" in headline_text or "war" in headline_text:
        next_to_watch.insert(0, {"ticker": "CVX", "company": "Chevron", "impact": "Medium", "index": "SPX", "catalyst": "Energy / geopolitical premium", "why": "Energy leaders matter more during geopolitical or crude spikes."})

    if "bank" in market_text or "credit" in headline_text or "yield" in headline_text:
        next_to_watch.insert(0, {"ticker": "GS", "company": "Goldman Sachs", "impact": "Medium", "index": "SPX / DJIA", "catalyst": "Rates / risk appetite", "why": "Financial tone can spill into the broad market quickly."})

    return {
        "leaders": leaders[:5],
        "threats": threats[:5],
        "next_to_watch": next_to_watch[:5],
    }


def build_market_pulse() -> list[dict[str, str]]:
    # Premium snapshot layer. Replace with live feed values later without changing the UI contract.
    return [
        {"symbol": "NASDAQ", "price": "24,016.01", "change": "+376.93", "pct": "+1.60%", "dir": "up"},
        {"symbol": "S&P 500", "price": "7,022.95", "change": "+55.57", "pct": "+0.80%", "dir": "up"},
        {"symbol": "DJIA", "price": "48,463.72", "change": "-72.27", "pct": "-0.15%", "dir": "down"},
        {"symbol": "VIX", "price": "18.17", "change": "-0.19", "pct": "-1.03%", "dir": "down"},
        {"symbol": "US 10Y", "price": "4.281", "change": "+0.025", "pct": "+0.59%", "dir": "up"},
        {"symbol": "OIL", "price": "91.13", "change": "-0.15", "pct": "-0.16%", "dir": "down"},
    ]


def build_session_significance() -> dict[str, str]:
    # This is the first pass significance engine. Later it can be replaced by live session math
    # without changing the UI contract.
    nq_points = 393
    nq_pct = 1.66
    es_points = 56
    es_pct = 0.80
    near_high = True
    label = "Major NY Session Expansion"
    severity = "high"

    summary = (
        f"NQ expanded roughly {nq_points} points and ES added about {es_points} points during the New York session. "
        "That is significant index expansion, not routine noise. "
        + ("Price pushed toward major highs, which makes leadership and follow-through more important." if near_high else "The move was meaningful even without a fresh high push.")
    )

    return {
        "label": label,
        "severity": severity,
        "nq_points": str(nq_points),
        "nq_pct": f"{nq_pct:.2f}%",
        "es_points": str(es_points),
        "es_pct": f"{es_pct:.2f}%",
        "summary": summary,
    }


def build_top_bottom_movers() -> dict[str, list[dict[str, str]]]:
    return {
        "top": [
            {"ticker": "NVDA", "price": "942.18", "change": "+18.21", "pct": "+1.97%", "why": "AI leadership remains the cleanest index support name."},
            {"ticker": "META", "price": "612.40", "change": "+9.84", "pct": "+1.63%", "why": "Momentum and mega-cap participation improved risk tone."},
            {"ticker": "AVGO", "price": "1,742.11", "change": "+24.17", "pct": "+1.41%", "why": "Semi sympathy keeps pressure on NQ shorts."},
            {"ticker": "MSFT", "price": "488.91", "change": "+5.47", "pct": "+1.13%", "why": "Large-cap stability reinforced broad index strength."},
            {"ticker": "AMZN", "price": "201.76", "change": "+1.96", "pct": "+0.98%", "why": "Consumer and cloud beta helped risk-on tone."},
        ],
        "bottom": [
            {"ticker": "TSLA", "price": "171.44", "change": "-2.63", "pct": "-1.51%", "why": "High-beta weakness without broad market damage is still worth tracking."},
            {"ticker": "UNH", "price": "487.22", "change": "-4.85", "pct": "-0.99%", "why": "Defensive lag can matter more if the tape loses momentum."},
            {"ticker": "XOM", "price": "116.54", "change": "-0.72", "pct": "-0.61%", "why": "Energy cooled slightly despite elevated crude levels."},
            {"ticker": "JPM", "price": "241.63", "change": "-1.02", "pct": "-0.42%", "why": "Banks lagging means breadth is not as clean as headline index strength."},
            {"ticker": "PFE", "price": "27.84", "change": "-0.11", "pct": "-0.39%", "why": "Low-impact downside, but useful as a defensive tone tell."},
        ],
    }


def summarize_system_context() -> str:
    risk = load_risk_state()
    alerts = load_alert_history()[:5]
    assistant = load_assistant_state()
    driver = build_market_driver_engine()
    movers = build_market_movers_intelligence()
    mover_names = ", ".join(x["ticker"] for x in movers["leaders"][:3])
    alert_text = " | ".join(
        f"{a.get('ticker')} {a.get('signal')} {a.get('verdict')} {a.get('confidence')}"
        for a in alerts
    ) or "No recent alerts"

    return f"""
Time:
- NY: {risk.get('donna_time_ny')}
- Session: {risk.get('donna_session')}
- Day: {risk.get('donna_day')}

Risk:
- Macro: {risk.get('macro_risk')}
- Headline: {risk.get('headline_risk')}
- Market News: {risk.get('market_news_risk')}
- Next Event: {risk.get('next_event')}
- Minutes To Event: {risk.get('minutes_to_event')}
- Event Phase: {risk.get('event_phase')}

Driver Engine:
- Dominant Driver: {driver.get('dominant_driver')}
- Secondary Driver: {driver.get('secondary_driver')}
- Regime: {driver.get('market_regime')}
- Threat: {driver.get('market_threat')}
- Confidence: {driver.get('market_confidence')}
- Summary: {driver.get('market_summary')}

Market Movers:
- Leaders: {mover_names}

Assistant State:
- Focus: {assistant.get('daily_focus')}
- Tasks: {assistant.get('tasks')}
- Reminders: {assistant.get('reminders')}

Recent Alerts:
- {alert_text}
""".strip()


# ==================================================
# SIGNAL / ALERT PROCESSOR
# ==================================================
def build_signal_prompt(data: dict[str, str]) -> str:
    risk = load_risk_state()
    base_verdict = pre_verdict_engine(data)
    fusion = apply_fusion_overlay(base_verdict, risk, data)
    confidence_note = confidence_bias(risk, data)
    warnings = ", ".join(risk.get("active_warnings", [])) or "none"

    return f"""
Analyze this futures trading alert.

Alert:
Ticker: {data['ticker']}
Price: {data['price']}
Signal: {data['signal']}
Timeframe: {data['timeframe']}
Session: {data['session']}
Setup: {data['setup_type']}
Priority: {data['signal_priority']}
Context: {data['context_strength']}
Market State: {data['market_state']}
Scenario: {data['scenario']}
Fib Zone: {data['fib_zone']}
Liquidity: {data['liquidity']}
Bias: {data['bias']}
Score: {data['score']}
Quality: {data['quality']}

Risk Layer:
Macro Risk: {risk['macro_risk']}
Headline Risk: {risk['headline_risk']}
Market News Risk: {risk['market_news_risk']}
Warnings: {warnings}
Next Event: {risk['next_event']}
Minutes To Event: {risk['minutes_to_event']}
Event Phase: {risk['event_phase']}
Driver Summary: {build_market_driver_engine()['market_summary']}

Deterministic Verdict: {base_verdict}
Fusion Verdict: {fusion}
Confidence Guidance: {confidence_note}
""".strip()


def format_telegram_alert(data: dict[str, str], parsed: dict[str, str]) -> str:
    return (
        f"DONNA // {data['ticker']} // {data['signal']}\n"
        f"{data['session']} | TF {data['timeframe']} | Price {data['price']}\n\n"
        f"Verdict: {parsed['verdict']}\n"
        f"Confidence: {parsed['confidence']}\n"
        f"Why: {parsed['why']}\n"
        f"Risk: {parsed['risk']}\n"
        f"Execution: {parsed['execution']}\n"
        f"Summary: {parsed['summary']}"
    )


def process_signal(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        data = normalize_payload(payload)
        if data["signal"] == "NONE":
            return {"status": "ignored", "reason": "signal NONE"}

        if client:
            response = client.responses.create(
                model=OPENAI_MODEL,
                instructions=DONNA_SIGNAL_PROMPT,
                input=build_signal_prompt(data),
                max_output_tokens=220,
            )
            parsed = extract_fields(response.output_text)
        else:
            parsed = {
                "verdict": apply_fusion_overlay(pre_verdict_engine(data), load_risk_state(), data),
                "confidence": "65%",
                "why": "OpenAI unavailable. Using fallback engine.",
                "risk": confidence_bias(load_risk_state(), data),
                "execution": "Wait for confirmation before acting.",
                "summary": "Donna fallback engine processed this signal.",
            }

        add_alert_to_history(data, parsed)
        telegram_result = None
        if should_send_trade_to_telegram(parsed):
            telegram_result = send_telegram_message(format_telegram_alert(data, parsed))

        return {
            "status": "ok",
            "data": data,
            "parsed": parsed,
            "telegram": telegram_result,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ==================================================
# ASSISTANT ACTIONS
# ==================================================
def apply_assistant_action(action: str, value: str) -> dict[str, Any]:
    state = load_assistant_state()
    action = (action or "none").strip().lower()
    value = (value or "").strip()

    if action == "set_focus" and value:
        state["daily_focus"] = value
    elif action == "add_task" and value:
        state["tasks"].append(value)
        state["tasks"] = state["tasks"][:30]
    elif action == "add_reminder" and value:
        state["reminders"].append(value)
        state["reminders"] = state["reminders"][:30]
    elif action == "clear_tasks":
        state["tasks"] = []
    elif action == "clear_reminders":
        state["reminders"] = []

    save_assistant_state(state)
    return state


# ==================================================
# DASHBOARD DATA BUILDER
# ==================================================
def build_dashboard_payload() -> dict[str, Any]:
    risk = load_risk_state()
    assistant = load_assistant_state()
    settings = load_settings()
    alerts = load_alert_history()[:12]
    drivers = build_market_driver_engine()
    movers = build_market_movers_intelligence()
    pulse = build_market_pulse()
    session_sig = build_session_significance()
    top_bottom = build_top_bottom_movers()

    # Pass 1 wording upgrade: make Donna acknowledge when the session was truly meaningful.
    driver_summary = drivers.get("market_summary", "")
    if session_sig["severity"] == "high":
        driver_summary = session_sig["summary"]
        drivers["market_regime"] = "Trend Expansion"
        if drivers.get("market_confidence", "Low") == "Low":
            drivers["market_confidence"] = "Medium / High"

    return {
        "status": "online",
        "risk": risk,
        "assistant": assistant,
        "settings": settings,
        "alerts": alerts,
        "market_pulse": pulse,
        "market_movers": movers,
        "session_significance": session_sig,
        "top_bottom_movers": top_bottom,
        **drivers,
        "market_summary": driver_summary,
    }


# ==================================================
# STARTUP / BACKGROUND LOOPS
# ==================================================
async def news_loop():
    while True:
        try:
            await asyncio.to_thread(process_news_guard_cycle)
        except Exception as e:
            print("Donna News loop error:", str(e))
        await asyncio.sleep(NEWS_POLL_SECONDS)


async def headline_loop():
    while True:
        try:
            await asyncio.to_thread(process_headlines_cycle)
        except Exception as e:
            print("Donna Headlines loop error:", str(e))
        await asyncio.sleep(HEADLINE_POLL_SECONDS)


async def finnhub_loop():
    while True:
        try:
            await asyncio.to_thread(process_finnhub_cycle)
        except Exception as e:
            print("Donna Finnhub loop error:", str(e))
        await asyncio.sleep(FINNHUB_POLL_SECONDS)


@app.on_event("startup")
async def startup() -> None:
    if not RISK_STATE_FILE.exists():
        save_risk_state(default_risk_state())
    if not ALERTS_FILE.exists():
        save_alert_history([])
    if not ASSISTANT_FILE.exists():
        save_assistant_state(default_assistant_state())
    if not SETTINGS_FILE.exists():
        save_settings(default_settings())

    try:
        await asyncio.to_thread(process_news_guard_cycle)
    except Exception as e:
        print("Startup news init error:", str(e))
    try:
        await asyncio.to_thread(process_headlines_cycle)
    except Exception as e:
        print("Startup headlines init error:", str(e))
    try:
        await asyncio.to_thread(process_finnhub_cycle)
    except Exception as e:
        print("Startup finnhub init error:", str(e))

    asyncio.create_task(news_loop())
    asyncio.create_task(headline_loop())
    asyncio.create_task(finnhub_loop())


# ==================================================
# ROUTES - BASIC
# ==================================================
@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "Donna is online"}


@app.head("/")
async def root_head() -> Response:
    return Response(status_code=200)


@app.get("/check-env")
async def check_env() -> dict[str, Any]:
    return {
        "openai_key_found": bool(OPENAI_API_KEY),
        "telegram_found": bool(TELEGRAM_BOT_TOKEN),
        "risk_file_exists": RISK_STATE_FILE.exists(),
        "alerts_file_exists": ALERTS_FILE.exists(),
        "assistant_file_exists": ASSISTANT_FILE.exists(),
        "settings_file_exists": SETTINGS_FILE.exists(),
        "model": OPENAI_MODEL,
        "telegram_alert_mode": load_settings().get("telegram_alert_mode", TELEGRAM_ALERT_MODE),
    }


@app.get("/test-telegram")
async def test_telegram() -> dict[str, Any]:
    return send_telegram_message("DONNA TEST MESSAGE")


# ==================================================
# ROUTES - DATA
# ==================================================
@app.get("/risk-state")
async def risk_state() -> dict[str, Any]:
    return load_risk_state()


@app.get("/alerts-data")
async def alerts_data() -> dict[str, Any]:
    return {"alerts": load_alert_history()}


@app.get("/assistant-data")
async def assistant_data() -> dict[str, Any]:
    return load_assistant_state()


@app.get("/dashboard-data")
async def dashboard_data() -> dict[str, Any]:
    return build_dashboard_payload()


# ==================================================
# ROUTES - WEBHOOK / ALERTS
# ==================================================
@app.post("/webhook")
async def webhook(request: Request) -> dict[str, Any]:
    try:
        body = await request.body()
        text = body.decode("utf-8", errors="ignore").strip()
        if not text:
            raise HTTPException(status_code=400, detail="Empty body")
        try:
            payload = json.loads(text)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Webhook body is not valid JSON. Received: {text[:200]}")
        result = process_signal(payload)
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("error", "Signal processing failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================================================
# ROUTES - ASSISTANT CONTROL
# ==================================================
@app.post("/assistant/set-focus")
async def assistant_set_focus(request: Request) -> dict[str, Any]:
    body = await request.json()
    value = str(body.get("daily_focus", "")).strip()
    if not value:
        raise HTTPException(status_code=400, detail="daily_focus is required")
    state = load_assistant_state()
    state["daily_focus"] = value
    save_assistant_state(state)
    return {"status": "ok", "assistant": state}


@app.post("/assistant/add-task")
async def assistant_add_task(request: Request) -> dict[str, Any]:
    body = await request.json()
    value = str(body.get("task", "")).strip()
    if not value:
        raise HTTPException(status_code=400, detail="task is required")
    state = load_assistant_state()
    state["tasks"].append(value)
    state["tasks"] = state["tasks"][:30]
    save_assistant_state(state)
    return {"status": "ok", "assistant": state}


@app.post("/assistant/add-reminder")
async def assistant_add_reminder(request: Request) -> dict[str, Any]:
    body = await request.json()
    value = str(body.get("reminder", "")).strip()
    if not value:
        raise HTTPException(status_code=400, detail="reminder is required")
    state = load_assistant_state()
    state["reminders"].append(value)
    state["reminders"] = state["reminders"][:30]
    save_assistant_state(state)
    return {"status": "ok", "assistant": state}


@app.post("/assistant/delete-task")
async def assistant_delete_task(request: Request) -> dict[str, Any]:
    body = await request.json()
    index = body.get("index")
    if index is None:
        raise HTTPException(status_code=400, detail="index is required")
    state = load_assistant_state()
    try:
        index = int(index)
    except Exception:
        raise HTTPException(status_code=400, detail="index must be integer")
    if index < 0 or index >= len(state["tasks"]):
        raise HTTPException(status_code=400, detail="invalid task index")
    state["tasks"].pop(index)
    save_assistant_state(state)
    return {"status": "ok", "assistant": state}


@app.post("/assistant/delete-reminder")
async def assistant_delete_reminder(request: Request) -> dict[str, Any]:
    body = await request.json()
    index = body.get("index")
    if index is None:
        raise HTTPException(status_code=400, detail="index is required")
    state = load_assistant_state()
    try:
        index = int(index)
    except Exception:
        raise HTTPException(status_code=400, detail="index must be integer")
    if index < 0 or index >= len(state["reminders"]):
        raise HTTPException(status_code=400, detail="invalid reminder index")
    state["reminders"].pop(index)
    save_assistant_state(state)
    return {"status": "ok", "assistant": state}


@app.post("/assistant/clear-tasks")
async def assistant_clear_tasks() -> dict[str, Any]:
    state = load_assistant_state()
    state["tasks"] = []
    save_assistant_state(state)
    return {"status": "ok", "assistant": state}


@app.post("/assistant/clear-reminders")
async def assistant_clear_reminders() -> dict[str, Any]:
    state = load_assistant_state()
    state["reminders"] = []
    save_assistant_state(state)
    return {"status": "ok", "assistant": state}


@app.post("/assistant/chat")
async def assistant_chat(request: Request) -> dict[str, Any]:
    body = await request.json()
    message = str(body.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    fallback = {
        "action": "none",
        "value": "",
        "reply": "State check complete. No action taken.",
    }

    if not client:
        return {
            "status": "ok",
            "action": "none",
            "value": "",
            "reply": "OpenAI is not configured. Donna assistant is in fallback mode.",
            "assistant": load_assistant_state(),
            "risk": load_risk_state(),
            "alerts": load_alert_history()[:10],
        }

    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=DONNA_ASSISTANT_PROMPT,
            input=f"User message:\n{message}\n\nSystem context:\n{summarize_system_context()}",
            max_output_tokens=220,
        )
        parsed = parse_json_loose(response.output_text, fallback)
        action = str(parsed.get("action", "none")).strip().lower()
        value = str(parsed.get("value", "")).strip()
        reply = str(parsed.get("reply", "")).strip() or fallback["reply"]
        updated_state = apply_assistant_action(action, value)
        return {
            "status": "ok",
            "action": action,
            "value": value,
            "reply": reply,
            "assistant": updated_state,
            "risk": load_risk_state(),
            "alerts": load_alert_history()[:10],
        }
    except Exception as e:
        return {
            "status": "error",
            "action": "none",
            "value": "",
            "reply": f"Assistant error: {str(e)}",
            "assistant": load_assistant_state(),
            "risk": load_risk_state(),
            "alerts": load_alert_history()[:10],
        }


# ==================================================
# HTML FRONTEND
# ==================================================
DASHBOARD_HTML = r'''
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>D.O.N.N.A Premium Core</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#050b16;
  --bg2:#0a1426;
  --panel:#0f1d34;
  --panel2:#132641;
  --line:rgba(255,255,255,.08);
  --text:#eef4ff;
  --muted:#8ea4c5;
  --blue:#4f84ff;
  --blue2:#2b62e7;
  --green:#48ffb2;
  --yellow:#ffd454;
  --red:#ff657e;
  --shadow:0 18px 46px rgba(0,0,0,.34);
  --radius:22px;
}
html,body{min-height:100%}
body{
  font-family:Inter,Arial,sans-serif;color:var(--text);
  background:
    radial-gradient(circle at 100% 0%, rgba(79,132,255,.16), transparent 28%),
    radial-gradient(circle at 0% 100%, rgba(72,255,178,.08), transparent 24%),
    linear-gradient(180deg,var(--bg2),var(--bg));
  padding:22px;
}
.wrap{max-width:1540px;margin:0 auto}
.topbar{display:flex;justify-content:space-between;align-items:flex-start;gap:18px;flex-wrap:wrap;margin-bottom:16px}
.brand h1{font-size:46px;line-height:1;letter-spacing:4px;font-weight:900}
.brand p{margin-top:8px;color:var(--muted);font-size:13px;letter-spacing:.4px}
.top-right{display:flex;flex-direction:column;gap:12px;align-items:flex-end}
.online{display:flex;align-items:center;gap:10px;padding:10px 16px;border-radius:999px;background:rgba(72,255,178,.08);border:1px solid rgba(72,255,178,.24);color:#baffdc;font-weight:900;font-size:13px}
.dot{width:10px;height:10px;border-radius:50%;background:var(--green);box-shadow:0 0 14px rgba(72,255,178,.8)}
.navbar{display:flex;gap:10px;flex-wrap:wrap}
.nav-btn{border:none;cursor:pointer;border-radius:14px;padding:12px 16px;font-weight:800;font-size:13px;color:#d6e4fb;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.06)}
.nav-btn.active{background:linear-gradient(135deg,var(--blue),var(--blue2));box-shadow:var(--shadow);color:white}
.live-strip{display:grid;grid-template-columns:220px 1fr 220px;gap:12px;align-items:center;margin-bottom:16px}
.live-pill,.tape,.session-chip{border-radius:16px;border:1px solid var(--line);box-shadow:var(--shadow)}
.live-pill{padding:14px 16px;background:rgba(255,101,126,.08);border-color:rgba(255,101,126,.22);color:#ffc0cb;font-size:12px;font-weight:900;letter-spacing:1.4px;text-transform:uppercase}
.tape{padding:14px 18px;background:rgba(255,255,255,.04);display:flex;gap:30px;overflow:hidden;white-space:nowrap;font-size:13px;color:#e5eefc}
.tape b{color:#fff}
.session-chip{padding:14px 16px;background:rgba(79,132,255,.08);border-color:rgba(79,132,255,.2);text-align:center}
.session-chip .top{color:var(--muted);font-size:11px;letter-spacing:1.2px;text-transform:uppercase}
.session-chip .val{margin-top:5px;font-size:16px;font-weight:900}
.hero{display:grid;grid-template-columns:1.45fr 1fr;gap:16px;margin-bottom:16px}
.panel,.card{background:linear-gradient(180deg, rgba(19,38,65,.94), rgba(15,29,52,.98));border:1px solid var(--line);border-radius:var(--radius);padding:22px;box-shadow:var(--shadow)}
.kicker{font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--muted);margin-bottom:12px}
.hero-title{font-size:30px;font-weight:900;line-height:1.08}
.hero-sub{margin-top:12px;color:var(--muted);font-size:15px;line-height:1.55}
.mini-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:16px 0}
.mini{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:16px;padding:14px}
.mini-label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:1.2px}
.mini-value{margin-top:7px;font-weight:900;line-height:1.3}
.stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:16px}
.stat-card .label{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:1.6px;margin-bottom:12px}
.stat-card .value{font-size:38px;font-weight:900;line-height:1;text-transform:uppercase}
.stat-card .sub{margin-top:10px;color:var(--muted);font-size:14px}
.low{color:var(--green)}.medium{color:var(--yellow)}.high{color:var(--red)}.neutral{color:#dce9ff}
.page{display:none}.page.active{display:block}
.grid-2{display:grid;grid-template-columns:1.2fr .9fr;gap:16px}.grid-3{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.section-title{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:1.6px;margin-bottom:14px}
.row{display:flex;justify-content:space-between;gap:12px;padding:14px 0;border-bottom:1px solid rgba(255,255,255,.07)}
.row:last-child{border-bottom:none}
.row-label{color:#deebff}.row-value{color:var(--muted);text-align:right}
.badges{display:flex;gap:10px;flex-wrap:wrap}.badge{padding:8px 12px;border-radius:999px;font-size:12px;font-weight:800;background:rgba(255,101,126,.08);border:1px solid rgba(255,101,126,.22);color:#ffc0cb}
.feed-item{padding:14px 0;border-bottom:1px solid rgba(255,255,255,.07);font-size:14px;line-height:1.5}.feed-item:last-child{border-bottom:none}
.table{width:100%;border-collapse:collapse}.table th{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:1.4px;text-align:left;padding:0 0 12px;border-bottom:1px solid rgba(255,255,255,.08)}.table td{padding:12px 0;border-bottom:1px solid rgba(255,255,255,.06);font-size:14px}.table tr:last-child td{border-bottom:none}
.up{color:var(--green)}.down{color:var(--red)}.flat{color:#dbe7fa}
.seg{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px}.seg button{border:none;cursor:pointer;padding:10px 13px;border-radius:12px;background:rgba(255,255,255,.05);color:#edf4ff;border:1px solid rgba(255,255,255,.06);font-weight:800}.seg button.active{background:rgba(255,255,255,.12)}
.input,.textarea,.chat-output{user-select:text}.input,.textarea{width:100%;border-radius:14px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.04);color:white;outline:none;padding:13px 14px;font-size:14px}
.textarea{min-height:110px;resize:vertical}
.btn-row{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}.btn{padding:11px 15px;border:none;border-radius:13px;cursor:pointer;font-weight:800;font-size:13px;color:white;background:#1f3c67}.btn.primary{background:linear-gradient(135deg,var(--blue),var(--blue2))}.btn.ghost{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08)}
.item-row{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:12px 0;border-bottom:1px solid rgba(255,255,255,.06)}.item-row:last-child{border-bottom:none}
.item-text{flex:1;color:#e6eefb;font-size:14px;line-height:1.45}
.chat-output{min-height:240px;max-height:500px;overflow:auto;border-radius:18px;background:rgba(0,0,0,.18);border:1px solid rgba(255,255,255,.06);padding:14px}
.chat-msg{margin-bottom:12px;padding:12px 13px;border-radius:14px;line-height:1.5;font-size:14px}.chat-msg.user{background:rgba(79,132,255,.13);border:1px solid rgba(79,132,255,.2)}.chat-msg.assistant{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.06)}.chat-role{display:block;font-size:11px;text-transform:uppercase;letter-spacing:1.1px;color:var(--muted);margin-bottom:6px}
.footer{margin-top:16px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;color:var(--muted);font-size:12px}.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
@media(max-width:1180px){.hero,.grid-2,.grid-3,.stat-grid,.live-strip{grid-template-columns:1fr}}
@media(max-width:760px){body{padding:14px}.brand h1{font-size:34px}.hero-title{font-size:24px}}
</style>
</head>
<body>
<div class="wrap">
  <div class="topbar">
    <div class="brand">
      <h1>D.O.N.N.A</h1>
      <p>Dynamic Operational Neural Network Assistant // Premium Core</p>
    </div>
    <div class="top-right">
      <div class="online"><span class="dot"></span>ONLINE</div>
      <div class="navbar">
        <button class="nav-btn active" data-page="dashboard">Dashboard</button>
        <button class="nav-btn" data-page="trading">Trading</button>
        <button class="nav-btn" data-page="news">News</button>
        <button class="nav-btn" data-page="assistant">Assistant</button>
      </div>
    </div>
  </div>

  <div class="live-strip">
    <div class="live-pill">Live Intelligence</div>
    <div class="tape" id="tape"></div>
    <div class="session-chip"><div class="top">Current Session</div><div class="val" id="sessionVal">-</div></div>
  </div>

  <div class="hero">
    <div class="panel">
      <div class="kicker">Donna Overview</div>
      <div class="hero-title" id="heroTitle">System online. Loading command center view.</div>
      <div class="hero-sub" id="heroSub">Donna is preparing market context, catalysts, and driver analysis.</div>
    </div>
    <div class="panel">
      <div class="kicker">Daily Focus</div>
      <div style="font-size:19px;font-weight:900;line-height:1.35" id="focusHero">Loading...</div>
      <div class="mini-grid">
        <div class="mini"><div class="mini-label">Donna Time</div><div class="mini-value mono" id="nyTime">-</div></div>
        <div class="mini"><div class="mini-label">Event Phase</div><div class="mini-value" id="eventPhase">-</div></div>
      </div>
      <div class="kicker">Next Event Window</div>
      <div style="font-size:18px;font-weight:900" id="nextEventHero">-</div>
      <div class="hero-sub" id="nextEventSub">-</div>
    </div>
  </div>

  <div class="stat-grid">
    <div class="card stat-card"><div class="label">Macro Risk</div><div class="value neutral" id="macroRisk">-</div><div class="sub">Macro event pressure and red-folder timing</div></div>
    <div class="card stat-card"><div class="label">Headline Risk</div><div class="value neutral" id="headlineRisk">-</div><div class="sub">Market-moving headline pressure</div></div>
    <div class="card stat-card"><div class="label">Market Risk</div><div class="value neutral" id="marketRisk">-</div><div class="sub">Company and catalyst sensitivity</div></div>
    <div class="card stat-card"><div class="label">Next Event</div><div class="value neutral" style="font-size:20px;line-height:1.15;text-transform:none" id="nextEventCard">-</div><div class="sub" id="nextEventMinutes">No timed event loaded</div></div>
  </div>

  <div class="page active" id="page-dashboard">
    <div class="grid-2">
      <div>
        <div class="panel">
          <div class="section-title">Active Warnings</div>
          <div class="badges" id="warnings"></div>
        </div>
        <div class="panel" style="margin-top:16px">
          <div class="section-title">Market Pulse</div>
          <table class="table"><thead><tr><th>Symbol</th><th>Last</th><th>Chg</th><th>%Chg</th></tr></thead><tbody id="pulseDashboard"></tbody></table>
        </div>
        <div class="panel" style="margin-top:16px">
          <div class="section-title">Session Significance</div>
          <div class="feed-item"><b>Label:</b> <span id="sessionSigLabel">-</span></div>
          <div class="feed-item"><b>NQ Move:</b> <span id="sessionSigNq">-</span></div>
          <div class="feed-item"><b>ES Move:</b> <span id="sessionSigEs">-</span></div>
          <div class="feed-item"><b>Donna Read:</b> <span id="sessionSigSummary">-</span></div>
        </div>
        <div class="panel" style="margin-top:16px">
          <div class="section-title">Donna Internal Clock</div>
          <div class="row"><div class="row-label">New York Time</div><div class="row-value mono" id="clockNY">-</div></div>
          <div class="row"><div class="row-label">UTC Time</div><div class="row-value mono" id="clockUTC">-</div></div>
          <div class="row"><div class="row-label">Day</div><div class="row-value" id="clockDay">-</div></div>
          <div class="row"><div class="row-label">Session</div><div class="row-value" id="clockSession">-</div></div>
          <div class="row"><div class="row-label">Event Phase</div><div class="row-value" id="clockPhase">-</div></div>
        </div>
      </div>
      <div>
        <div class="panel">
          <div class="section-title">Market Driver Engine</div>
          <div class="row"><div class="row-label">Dominant Driver</div><div class="row-value" id="driverMain">-</div></div>
          <div class="row"><div class="row-label">Secondary Driver</div><div class="row-value" id="driverSecondary">-</div></div>
          <div class="row"><div class="row-label">Regime</div><div class="row-value" id="driverRegime">-</div></div>
          <div class="row"><div class="row-label">Threat</div><div class="row-value" id="driverThreat">-</div></div>
          <div class="row"><div class="row-label">Confidence</div><div class="row-value" id="driverConfidence">-</div></div>
          <div class="hero-sub" id="driverSummary">-</div>
        </div>
        <div class="panel" style="margin-top:16px">
          <div class="section-title">Likely Market Movers</div>
          <table class="table"><thead><tr><th>Ticker</th><th>Impact</th><th>Why</th></tr></thead><tbody id="leadersTable"></tbody></table>
        </div>
        <div class="panel" style="margin-top:16px">
          <div class="section-title">Top Stories</div>
          <div class="feed-item"><b>Headline:</b> <span id="topHeadline">-</span></div>
          <div class="feed-item"><b>Guidance:</b> <span id="topHeadlineGuidance">-</span></div>
          <div class="feed-item"><b>Market Story:</b> <span id="topMarketHeadline">-</span></div>
          <div class="feed-item"><b>Market Guidance:</b> <span id="topMarketGuidance">-</span></div>
        </div>
      </div>
    </div>
  </div>

  <div class="page" id="page-trading">
    <div class="grid-2">
      <div>
        <div class="panel">
          <div class="section-title">Trading Intelligence</div>
          <div class="feed-item"><b>What Matters Right Now:</b> <span id="tradeSummary">-</span></div>
          <div class="feed-item"><b>Primary Driver:</b> <span id="tradeDriver">-</span></div>
          <div class="feed-item"><b>Threat:</b> <span id="tradeThreat">-</span></div>
          <div class="feed-item"><b>Regime:</b> <span id="tradeRegime">-</span></div>
          <div class="feed-item"><b>Macro Window:</b> <span id="tradeEvent">-</span></div>
          <div class="feed-item"><b>Risk Read:</b> <span id="tradeRiskRead">-</span></div>
        </div>
        <div class="panel" style="margin-top:16px">
          <div class="section-title">Recent Alerts</div>
          <div id="recentAlerts"></div>
        </div>
      </div>
      <div>
        <div class="panel">
          <div class="section-title">Market Pulse</div>
          <table class="table"><thead><tr><th>Symbol</th><th>Last</th><th>Chg</th><th>%Chg</th></tr></thead><tbody id="pulseTrading"></tbody></table>
        </div>
        <div class="panel" style="margin-top:16px">
          <div class="section-title">Top Movers</div>
          <table class="table"><thead><tr><th>Ticker</th><th>Price</th><th>%Chg</th><th>Why</th></tr></thead><tbody id="topMoversTable"></tbody></table>
        </div>
        <div class="panel" style="margin-top:16px">
          <div class="section-title">Bottom Movers</div>
          <table class="table"><thead><tr><th>Ticker</th><th>Price</th><th>%Chg</th><th>Why</th></tr></thead><tbody id="bottomMoversTable"></tbody></table>
        </div>
        <div class="panel" style="margin-top:16px">
          <div class="section-title">Threat Names</div>
          <table class="table"><thead><tr><th>Ticker</th><th>Impact</th><th>Why</th></tr></thead><tbody id="threatsTable"></tbody></table>
        </div>
        <div class="panel" style="margin-top:16px">
          <div class="section-title">Next To Watch</div>
          <table class="table"><thead><tr><th>Ticker</th><th>Catalyst</th><th>Why</th></tr></thead><tbody id="watchTable"></tbody></table>
        </div>
      </div>
    </div>
  </div>

  <div class="page" id="page-news">
    <div class="grid-3">
      <div class="panel">
        <div class="section-title">Top Story</div>
        <div style="font-size:24px;font-weight:900;line-height:1.2" id="newsTopStory">-</div>
        <div class="hero-sub" id="newsTopNote">-</div>
      </div>
      <div class="panel">
        <div class="section-title">Macro Watch</div>
        <div class="feed-item"><b>Next Event:</b> <span id="newsEvent">-</span></div>
        <div class="feed-item"><b>Minutes To Event:</b> <span id="newsMinutes">-</span></div>
        <div class="feed-item"><b>Phase:</b> <span id="newsPhase">-</span></div>
        <div class="feed-item"><b>Session:</b> <span id="newsSession">-</span></div>
      </div>
      <div class="panel">
        <div class="section-title">Catalyst Watch</div>
        <div class="feed-item"><b>Market Story:</b> <span id="newsMarketStory">-</span></div>
        <div class="feed-item"><b>Symbol:</b> <span id="newsMarketSymbol">-</span></div>
        <div class="feed-item"><b>Severity:</b> <span id="newsMarketSeverity">-</span></div>
      </div>
    </div>
    <div class="grid-2" style="margin-top:16px">
      <div class="panel">
        <div class="section-title">Leaders</div>
        <table class="table"><thead><tr><th>Ticker</th><th>Index</th><th>Why It Matters</th></tr></thead><tbody id="leadersNews"></tbody></table>
      </div>
      <div class="panel">
        <div class="section-title">Donna News Read</div>
        <div class="feed-item"><b>Dominant Driver:</b> <span id="newsDriver">-</span></div>
        <div class="feed-item"><b>Secondary Driver:</b> <span id="newsSecondary">-</span></div>
        <div class="feed-item"><b>Regime:</b> <span id="newsRegime">-</span></div>
        <div class="feed-item"><b>Threat:</b> <span id="newsThreat">-</span></div>
        <div class="feed-item"><b>Confidence:</b> <span id="newsConfidence">-</span></div>
        <div class="hero-sub" id="newsSummary">-</div>
      </div>
    </div>
  </div>

  <div class="page" id="page-assistant">
    <div class="grid-2">
      <div class="panel">
        <div class="section-title">Donna AI Assistant</div>
        <div class="chat-output" id="chatOutput">
          <div class="chat-msg assistant"><span class="chat-role">Donna</span>Donna online. Ask what matters now, what companies can move the market, or give me a task.</div>
        </div>
        <textarea class="textarea" id="chatInput" placeholder="Ask Donna something..."></textarea>
        <div class="btn-row">
          <button class="btn primary" id="sendChatBtn">Send</button>
          <button class="btn ghost" id="quickRiskBtn">Risk Summary</button>
          <button class="btn ghost" id="quickMoverBtn">Likely Movers</button>
          <button class="btn ghost" id="quickDangerBtn">Danger Check</button>
        </div>
      </div>
      <div class="panel">
        <div class="section-title">Assistant State</div>
        <div class="kicker">Daily Focus</div>
        <input class="input" id="focusInput" placeholder="Set Donna daily focus">
        <div class="btn-row"><button class="btn primary" id="setFocusBtn">Set Focus</button></div>

        <div class="kicker" style="margin-top:18px">Tasks</div>
        <input class="input" id="taskInput" placeholder="Add task">
        <div class="btn-row"><button class="btn" id="addTaskBtn">Add Task</button><button class="btn ghost" id="clearTasksBtn">Clear Tasks</button></div>
        <div id="tasksList" style="margin-top:12px"></div>

        <div class="kicker" style="margin-top:18px">Reminders</div>
        <input class="input" id="reminderInput" placeholder="Add reminder">
        <div class="btn-row"><button class="btn" id="addReminderBtn">Add Reminder</button><button class="btn ghost" id="clearRemindersBtn">Clear Reminders</button></div>
        <div id="remindersList" style="margin-top:12px"></div>
      </div>
    </div>
  </div>

  <div class="footer"><div>Donna Premium Core</div><div class="mono" id="footerUpdated">last update: -</div></div>
</div>

<script>
let dashboardState = null;

function byId(id){ return document.getElementById(id); }
function esc(s){ return String(s ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;'); }

function setPage(page){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active'));
  byId('page-' + page).classList.add('active');
  document.querySelector(`.nav-btn[data-page="${page}"]`).classList.add('active');
}

document.querySelectorAll('.nav-btn').forEach(btn=>btn.addEventListener('click',()=>setPage(btn.dataset.page)));

function riskClass(v){
  const x = String(v || '').toLowerCase();
  if(x === 'high') return 'high';
  if(x === 'medium') return 'medium';
  return 'low';
}

async function api(url, options={}){
  const res = await fetch(url, { headers:{'Content-Type':'application/json'}, ...options });
  const data = await res.json().catch(()=>({}));
  if(!res.ok) throw new Error(data.detail || data.reply || 'Request failed');
  return data;
}

function renderPulse(rows, targetId){
  const body = byId(targetId);
  if(!body) return;
  body.innerHTML = (rows || []).map(r => `
    <tr>
      <td>${esc(r.symbol)}</td>
      <td>${esc(r.price)}</td>
      <td class="${esc(r.dir || 'flat')}">${esc(r.change)}</td>
      <td class="${esc(r.dir || "flat")}">${esc(r.pct)}</td>
    </tr>
  `).join('') || '<tr><td colspan="4">No pulse data</td></tr>';
}

function renderMoverTable(rows, targetId, mode){
  const body = byId(targetId);
  if(!body) return;
  body.innerHTML = (rows || []).map(r => {
    if(mode === 'leaders-news') return `<tr><td>${esc(r.ticker)}</td><td>${esc(r.index)}</td><td>${esc(r.why)}</td></tr>`;
    if(mode === 'watch') return `<tr><td>${esc(r.ticker)}</td><td>${esc(r.catalyst)}</td><td>${esc(r.why)}</td></tr>`;
    return `<tr><td>${esc(r.ticker)}</td><td>${esc(r.impact)}</td><td>${esc(r.why)}</td></tr>`;
  }).join('') || '<tr><td colspan="3">No data</td></tr>';
}

function renderAlerts(alerts){
  const target = byId('recentAlerts');
  if(!alerts || !alerts.length){
    target.innerHTML = '<div class="feed-item">No alerts yet</div>';
    return;
  }
  target.innerHTML = alerts.map(a => `
    <div class="feed-item">
      <b>${esc(a.ticker)} ${esc(a.signal)}</b> // ${esc(a.verdict)} // ${esc(a.confidence)}<br>
      ${esc(a.session)} | TF ${esc(a.timeframe)} | Price ${esc(a.price)}<br>
      ${esc(a.summary || 'No summary')}
    </div>
  `).join('');
}


function renderMoveTable(rows, targetId){
  const body = byId(targetId);
  if(!body) return;
  body.innerHTML = (rows || []).map(r => `
    <tr>
      <td>${esc(r.ticker)}</td>
      <td>${esc(r.price)}</td>
      <td class="${String(r.pct || '').trim().startsWith('-') ? 'down' : 'up'}">${esc(r.pct)}</td>
      <td>${esc(r.why)}</td>
    </tr>
  `).join('') || '<tr><td colspan="4">No data</td></tr>';
}

function renderWarnings(warnings){
  const target = byId('warnings');
  if(!warnings || !warnings.length){
    target.innerHTML = '<span class="badge">No active warnings</span>';
    return;
  }
  target.innerHTML = warnings.map(w=>`<span class="badge">${esc(w)}</span>`).join('');
}

function renderStateLists(items, targetId, deleteRoute){
  const target = byId(targetId);
  if(!items || !items.length){
    target.innerHTML = '<div class="feed-item">None</div>';
    return;
  }
  target.innerHTML = items.map((item, idx)=>`
    <div class="item-row">
      <div class="item-text">${esc(item)}</div>
      <button class="btn ghost" onclick="deleteIndexedItem('${deleteRoute}', ${idx})">Delete</button>
    </div>
  `).join('');
}

function addChatMessage(role, text){
  const wrap = byId('chatOutput');
  const div = document.createElement('div');
  div.className = 'chat-msg ' + (role === 'user' ? 'user' : 'assistant');
  div.innerHTML = `<span class="chat-role">${role === 'user' ? 'You' : 'Donna'}</span>${esc(text)}`;
  wrap.appendChild(div);
  wrap.scrollTop = wrap.scrollHeight;
}

async function sendDonnaChat(message=null){
  const input = byId('chatInput');
  const text = message || input.value.trim();
  if(!text) return;
  addChatMessage('user', text);
  if(!message) input.value = '';
  try{
    const data = await api('/assistant/chat', { method:'POST', body:JSON.stringify({message:text}) });
    addChatMessage('assistant', data.reply || 'No response.');
    await refreshDashboard();
  }catch(err){
    addChatMessage('assistant', 'Assistant error: ' + err.message);
  }
}

async function deleteIndexedItem(route, index){
  try{
    await api(route, { method:'POST', body:JSON.stringify({index}) });
    await refreshDashboard();
  }catch(err){ alert(err.message); }
}

async function setFocus(){
  const value = byId('focusInput').value.trim();
  if(!value) return;
  await api('/assistant/set-focus', { method:'POST', body:JSON.stringify({daily_focus:value}) });
  byId('focusInput').value = '';
  await refreshDashboard();
}

async function addTask(){
  const value = byId('taskInput').value.trim();
  if(!value) return;
  await api('/assistant/add-task', { method:'POST', body:JSON.stringify({task:value}) });
  byId('taskInput').value = '';
  await refreshDashboard();
}

async function addReminder(){
  const value = byId('reminderInput').value.trim();
  if(!value) return;
  await api('/assistant/add-reminder', { method:'POST', body:JSON.stringify({reminder:value}) });
  byId('reminderInput').value = '';
  await refreshDashboard();
}

async function clearTasks(){
  await api('/assistant/clear-tasks', { method:'POST' });
  await refreshDashboard();
}

async function clearReminders(){
  await api('/assistant/clear-reminders', { method:'POST' });
  await refreshDashboard();
}

function bindAssistant(){
  byId('sendChatBtn').addEventListener('click', ()=>sendDonnaChat());
  byId('quickRiskBtn').addEventListener('click', ()=>sendDonnaChat('What is the current risk environment?'));
  byId('quickMoverBtn').addEventListener('click', ()=>sendDonnaChat('What companies are most likely to move the market next?'));
  byId('quickDangerBtn').addEventListener('click', ()=>sendDonnaChat('Is this a dangerous time to trade?'));
  byId('setFocusBtn').addEventListener('click', setFocus);
  byId('addTaskBtn').addEventListener('click', addTask);
  byId('addReminderBtn').addEventListener('click', addReminder);
  byId('clearTasksBtn').addEventListener('click', clearTasks);
  byId('clearRemindersBtn').addEventListener('click', clearReminders);
  byId('chatInput').addEventListener('keydown', (e)=>{
    if(e.key === 'Enter' && !e.shiftKey){ e.preventDefault(); sendDonnaChat(); }
  });
}

function render(payload){
  dashboardState = payload;
  const risk = payload.risk || {};
  const assistant = payload.assistant || {};
  const movers = payload.market_movers || {};
  const sessionSig = payload.session_significance || {};
  const topBottom = payload.top_bottom_movers || {};

  byId('sessionVal').textContent = risk.donna_session || '-';
  byId('heroTitle').textContent = `${payload.dominant_driver || 'Balanced Conditions'} is leading current conditions.`;
  byId('heroSub').textContent = payload.market_summary || '-';
  byId('focusHero').textContent = assistant.daily_focus || 'No focus set.';
  byId('nyTime').textContent = risk.donna_time_ny || '-';
  byId('eventPhase').textContent = risk.event_phase || '-';
  byId('nextEventHero').textContent = risk.next_event || 'No event loaded';
  byId('nextEventSub').textContent = risk.minutes_to_event != null ? `${risk.minutes_to_event} minutes to event` : 'No timed event loaded';
  byId('nextEventCard').textContent = risk.next_event || 'None';
  byId('nextEventMinutes').textContent = risk.minutes_to_event != null ? `${risk.minutes_to_event} minutes remaining` : 'No timed event loaded';

  const macro = byId('macroRisk'); macro.textContent = String(risk.macro_risk || '-').toUpperCase(); macro.className = 'value ' + riskClass(risk.macro_risk);
  const head = byId('headlineRisk'); head.textContent = String(risk.headline_risk || '-').toUpperCase(); head.className = 'value ' + riskClass(risk.headline_risk);
  const market = byId('marketRisk'); market.textContent = String(risk.market_news_risk || '-').toUpperCase(); market.className = 'value ' + riskClass(risk.market_news_risk);

  byId('clockNY').textContent = risk.donna_time_ny || '-';
  byId('clockUTC').textContent = risk.donna_time_utc || '-';
  byId('clockDay').textContent = risk.donna_day || '-';
  byId('clockSession').textContent = risk.donna_session || '-';
  byId('clockPhase').textContent = risk.event_phase || '-';

  byId('driverMain').textContent = payload.dominant_driver || '-';
  byId('driverSecondary').textContent = payload.secondary_driver || '-';
  byId('driverRegime').textContent = payload.market_regime || '-';
  byId('driverThreat').textContent = payload.market_threat || '-';
  byId('driverConfidence').textContent = payload.market_confidence || '-';
  byId('driverSummary').textContent = payload.market_summary || '-';

  byId('topHeadline').textContent = risk.last_headline || 'No recent headline';
  byId('topHeadlineGuidance').textContent = risk.headline_guidance || 'No headline guidance';
  byId('topMarketHeadline').textContent = risk.last_market_headline || 'No recent market story';
  byId('topMarketGuidance').textContent = risk.last_market_guidance || 'No market guidance';

  byId('tradeSummary').textContent = sessionSig.summary || payload.market_summary || '-';
  byId('tradeDriver').textContent = payload.dominant_driver || '-';
  byId('tradeThreat').textContent = payload.market_threat || '-';
  byId('tradeRegime').textContent = payload.market_regime || '-';
  byId('tradeEvent').textContent = risk.next_event || 'No event loaded';
  byId('tradeRiskRead').textContent = `Macro ${String(risk.macro_risk || '-').toUpperCase()} / Headline ${String(risk.headline_risk || '-').toUpperCase()} / Market ${String(risk.market_news_risk || '-').toUpperCase()}`;

  byId('newsTopStory').textContent = risk.last_headline || 'No major headline detected';
  byId('newsTopNote').textContent = risk.headline_guidance || 'No headline guidance available.';
  byId('newsEvent').textContent = risk.next_event || 'No event loaded';
  byId('newsMinutes').textContent = risk.minutes_to_event != null ? String(risk.minutes_to_event) : '-';
  byId('newsPhase').textContent = risk.event_phase || '-';
  byId('newsSession').textContent = risk.donna_session || '-';
  byId('newsMarketStory').textContent = risk.last_market_headline || 'No market story detected';
  byId('newsMarketSymbol').textContent = risk.last_market_symbol || '-';
  byId('newsMarketSeverity').textContent = risk.last_market_severity || '-';
  byId('newsDriver').textContent = payload.dominant_driver || '-';
  byId('newsSecondary').textContent = payload.secondary_driver || '-';
  byId('newsRegime').textContent = payload.market_regime || '-';
  byId('newsThreat').textContent = payload.market_threat || '-';
  byId('newsConfidence').textContent = payload.market_confidence || '-';
  byId('newsSummary').textContent = payload.market_summary || '-';

  byId('sessionSigLabel').textContent = sessionSig.label || '-';
  byId('sessionSigNq').textContent = sessionSig.nq_points ? `${sessionSig.nq_points} pts / ${sessionSig.nq_pct}` : '-';
  byId('sessionSigEs').textContent = sessionSig.es_points ? `${sessionSig.es_points} pts / ${sessionSig.es_pct}` : '-';
  byId('sessionSigSummary').textContent = sessionSig.summary || '-';

  renderWarnings(risk.active_warnings || []);
  renderPulse(payload.market_pulse || [], 'pulseDashboard');
  renderPulse(payload.market_pulse || [], 'pulseTrading');
  renderMoverTable(movers.leaders || [], 'leadersTable', 'leaders');
  renderMoveTable(topBottom.top || [], 'topMoversTable');
  renderMoveTable(topBottom.bottom || [], 'bottomMoversTable');
  renderMoverTable(movers.threats || [], 'threatsTable', 'threats');
  renderMoverTable(movers.next_to_watch || [], 'watchTable', 'watch');
  renderMoverTable(movers.leaders || [], 'leadersNews', 'leaders-news');
  renderAlerts(payload.alerts || []);
  renderStateLists(assistant.tasks || [], 'tasksList', '/assistant/delete-task');
  renderStateLists(assistant.reminders || [], 'remindersList', '/assistant/delete-reminder');

  byId('tape').innerHTML = `
    <div class="tape-track">
      <span><b>Macro:</b> ${esc(String(risk.macro_risk || '-').toUpperCase())}</span>
      <span><b>Headline:</b> ${esc(String(risk.headline_risk || '-').toUpperCase())}</span>
      <span><b>Market:</b> ${esc(String(risk.market_news_risk || '-').toUpperCase())}</span>
      <span><b>Driver:</b> ${esc(payload.dominant_driver || '-')}</span>
      <span><b>Threat:</b> ${esc(payload.market_threat || '-')}</span>
      <span><b>Event:</b> ${esc(risk.next_event || 'None')}</span>
      <span><b>Session:</b> ${esc(risk.donna_session || '-')}</span>
      <span><b>Top Headline:</b> ${esc(risk.last_headline || 'No recent headline')}</span>
      <span><b>NQ NY Move:</b> ${esc(sessionSig.nq_points || '-')} pts</span>
      <span><b>ES NY Move:</b> ${esc(sessionSig.es_points || '-')} pts</span>
    </div>
  `;

  byId('footerUpdated').textContent = 'last update: ' + (risk.last_updated || new Date().toISOString());
}

async function refreshDashboard(){
  try{
    const payload = await api('/dashboard-data');
    render(payload);
  }catch(err){
    console.error(err);
    byId('heroTitle').textContent = 'Donna connection issue.';
    byId('heroSub').textContent = err.message;
  }
}

bindAssistant();
refreshDashboard();
setInterval(refreshDashboard, 15000);
</script>
</body>
</html>
'''


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    return HTMLResponse(content=DASHBOARD_HTML)
