from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Response
from fastapi.responses import HTMLResponse
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import asyncio
import os
import json
import re
import requests

from donna_news import process_news_guard_cycle
from donna_headlines import process_headlines_cycle
from donna_finnhub import process_finnhub_cycle

# ==================================================
# ENV
# ==================================================
BASE_DIR = Path(__file__).parent
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_ALERT_MODE = os.getenv("TELEGRAM_ALERT_MODE", "all").lower()

if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY")
if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")
if not TELEGRAM_CHAT_ID:
    raise RuntimeError("Missing TELEGRAM_CHAT_ID")

client = OpenAI(api_key=OPENAI_API_KEY)
app = FastAPI(title="DONNA MASTER CORE RECOVERY")

# ==================================================
# FILES
# ==================================================
RISK_STATE_FILE = BASE_DIR / "donna_risk_state.json"
ALERTS_FILE = BASE_DIR / "donna_alert_history.json"
ASSISTANT_FILE = BASE_DIR / "donna_assistant_state.json"

# ==================================================
# TIME
# ==================================================
NY_TZ = ZoneInfo("America/New_York")
UTC_TZ = ZoneInfo("UTC")

def local_now_ny() -> datetime:
    return datetime.now(NY_TZ)

def local_now_utc() -> datetime:
    return datetime.now(UTC_TZ)

def local_day_name() -> str:
    return local_now_ny().strftime("%A")

def local_session_label(dt: datetime | None = None) -> str:
    dt = dt or local_now_ny()
    minutes = dt.hour * 60 + dt.minute

    if minutes >= 19 * 60 or minutes < 3 * 60:
        return "ASIA"
    if 3 * 60 <= minutes < 9 * 60 + 30:
        return "LONDON"
    if 9 * 60 + 30 <= minutes < 16 * 60:
        return "NEW_YORK_CASH"
    return "OFF_HOURS"

# ==================================================
# LOOP TIMERS
# ==================================================
NEWS_POLL_SECONDS = 900
HEADLINE_POLL_SECONDS = 900
FINNHUB_POLL_SECONDS = 600

# ==================================================
# SYSTEM PROMPTS
# ==================================================
DONNA_SYSTEM_PROMPT = """
You are Donna, an elite futures execution assistant.

Tone:
Cold. Sharp. Precise. Professional.

Job:
Analyze ES/NQ futures alerts and return a decisive execution briefing.

Rules:
- Consider setup quality, score, market state, bias, session, liquidity, and live risk conditions.
- Respect the fusion-adjusted verdict guidance.
- Respect confidence guidance.
- High risk conditions should reduce confidence or downgrade verdicts.
- Keep responses tight.
- No fluff.
- No emojis.
- No AI disclaimers.

Format exactly:

Verdict: TAKE / CAUTION / SKIP
Confidence: X%
Why: 1 sentence
Risk: 1 short sentence
Execution: 1 short sentence
Summary: 1 hard-hitting line
""".strip()

DONNA_ASSISTANT_PROMPT = """
You are Donna, the command center AI assistant inside a live trading and intelligence dashboard.

Tone:
Cold. Sharp. Helpful. Professional. Brief.

Core job:
Interpret timing, risk, session context, headlines, market catalysts, and assistant state for a futures trader.

You can do two things:
1. Answer questions about the current system state.
2. Trigger one assistant action if the user clearly asks for it.

You must return ONLY valid JSON in this exact shape:
{
  "action": "none | set_focus | add_task | add_reminder | clear_tasks | clear_reminders",
  "value": "string value or empty string",
  "reply": "short direct response to the user"
}

Reasoning rules:
- Treat time and event proximity as highly important.
- If a high-impact event is LIVE, IMMINENT, or within a dangerous window, say so directly.
- If the user asks whether it is safe or dangerous to trade, judge using:
  - macro_risk
  - headline_risk
  - market_news_risk
  - minutes_to_event
  - event_phase
  - donna_session
- If event_phase is LIVE, reply as if volatility is active now.
- If event_phase is IMMINENT, reply as if the user should reduce size and avoid random entries.
- If event_phase is APPROACHING, reply as if caution is increasing.
- If event_phase is POST_EVENT_COOLDOWN, reply as if conditions may still be unstable.
- If the user asks "what matters right now", prioritize:
  1. live/imminent macro event timing
  2. critical headline risk
  3. major market catalyst risk
  4. session context
- If the user asks how long until something, use minutes_to_event and event_time_ny.
- If the user asks what session we are in, use donna_session.
- If the user asks what time it is, use donna_time_ny and donna_time_utc.
- If the user asks for a state readout, synthesize rather than dumping raw fields.
- Be decisive. Do not sound vague unless the data is actually missing.

Action rules:
- If the user is asking a question, use action = "none".
- If the user clearly wants a focus/task/reminder action, choose the correct action.
- For clear actions, value can be empty string.
- Never return markdown.
- Never return extra text outside JSON.
""".strip()

# ==================================================
# TELEGRAM
# ==================================================
def send_telegram_message(text: str) -> dict:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
    }

    try:
        response = requests.post(url, json=payload, timeout=20)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def should_send_trade_to_telegram(parsed: dict) -> bool:
    if TELEGRAM_ALERT_MODE == "off":
        return False
    if TELEGRAM_ALERT_MODE == "all":
        return True

    verdict = str(parsed.get("verdict", "")).upper()
    confidence_raw = str(parsed.get("confidence", "0")).replace("%", "").strip()

    try:
        confidence_num = float(confidence_raw)
    except Exception:
        confidence_num = 0.0

    if TELEGRAM_ALERT_MODE == "critical":
        return verdict == "TAKE" or confidence_num >= 80

    return True

# ==================================================
# HELPERS
# ==================================================
def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def normalize_payload(payload: dict) -> dict:
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

def parse_json_loose(text: str, fallback: dict) -> dict:
    if not text:
        return fallback

    text = text.strip()

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

# ==================================================
# STATE LOAD / SAVE
# ==================================================
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
        "headline_severity": "",
        "headline_guidance": "",
        "headline_source": "",
        "last_market_symbol": "",
        "last_market_severity": "",
        "last_market_guidance": "",
        "last_market_url": "",
        "donna_time_utc": "",
        "donna_time_ny": "",
        "donna_day": "",
        "donna_session": "",
        "event_phase": "",
        "event_time_ny": "",
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

def load_alert_history() -> list:
    try:
        if not ALERTS_FILE.exists():
            return []

        with open(ALERTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data if isinstance(data, list) else []
    except Exception:
        return []

def save_alert_history(alerts: list) -> None:
    with open(ALERTS_FILE, "w", encoding="utf-8") as f:
        json.dump(alerts, f, indent=2)

def add_alert_to_history(data: dict, parsed: dict) -> None:
    alerts = load_alert_history()

    entry = {
        "ticker": data.get("ticker", "UNKNOWN"),
        "signal": data.get("signal", "UNKNOWN"),
        "session": data.get("session", "unknown"),
        "timeframe": data.get("timeframe", "unknown"),
        "price": data.get("price", "0"),
        "verdict": parsed.get("verdict", "UNKNOWN"),
        "confidence": parsed.get("confidence", "N/A"),
        "summary": parsed.get("summary", ""),
        "timestamp": utc_now_iso(),
    }

    alerts.insert(0, entry)
    alerts = alerts[:30]
    save_alert_history(alerts)

def load_assistant_state() -> dict:
    default_state = {
        "daily_focus": "Build Donna into a true command center.",
        "tasks": [
            "Review dashboard",
            "Check active alerts",
            "Handle top work priority",
            "Study and improve execution",
        ],
        "reminders": [
            "Watch next macro event",
            "Review Donna warnings",
            "Stay focused and avoid low-quality trades",
        ],
        "last_updated": utc_now_iso(),
    }

    try:
        if not ASSISTANT_FILE.exists():
            return default_state

        with open(ASSISTANT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return default_state

        merged = {**default_state, **data}

        if not isinstance(merged.get("tasks"), list):
            merged["tasks"] = default_state["tasks"]

        if not isinstance(merged.get("reminders"), list):
            merged["reminders"] = default_state["reminders"]

        return merged
    except Exception:
        return default_state

def save_assistant_state(state: dict) -> None:
    state["last_updated"] = utc_now_iso()
    with open(ASSISTANT_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

# ==================================================
# VERDICT ENGINE
# ==================================================
def pre_verdict_engine(data: dict) -> str:
    score = safe_float(data["score"])
    quality = data["quality"]
    context = data["context_strength"].lower()
    session = data["session"]
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

    if session in ["NY", "NY_PRE", "London"]:
        points += 2
    elif session == "Asia":
        points -= 1

    aligned = (
        (signal == "LONG" and market_state != "bearish" and bias != "bearish")
        or
        (signal == "SHORT" and market_state != "bullish" and bias != "bullish")
    )

    if aligned:
        points += 2
    else:
        points -= 3

    if points >= 10:
        return "TAKE"
    elif points >= 5:
        return "CAUTION"
    return "SKIP"

def apply_fusion_overlay(base_verdict: str, risk: dict, data: dict) -> str:
    macro = str(risk.get("macro_risk", "low")).lower()
    headline = str(risk.get("headline_risk", "low")).lower()
    market = str(risk.get("market_news_risk", "low")).lower()

    ticker = str(data.get("ticker", "")).upper()

    is_nq = "NQ" in ticker or "MNQ" in ticker or "NASDAQ" in ticker
    is_es = "ES" in ticker or "MES" in ticker or "SPX" in ticker or "SPY" in ticker

    if is_nq:
        if macro == "high":
            return "SKIP"
        if market == "high" and base_verdict == "TAKE":
            return "CAUTION"
        if macro == "medium" and base_verdict == "TAKE":
            return "CAUTION"
        if headline == "high":
            return "CAUTION" if base_verdict == "TAKE" else "SKIP"

    if is_es:
        if macro == "high":
            return "SKIP"
        if macro == "medium" and base_verdict == "TAKE":
            return "CAUTION"
        if headline == "high" and base_verdict == "TAKE":
            return "CAUTION"

    high_count = sum(x == "high" for x in [macro, headline, market])

    if base_verdict == "TAKE" and high_count >= 1:
        return "CAUTION"

    if base_verdict == "CAUTION" and high_count >= 2:
        return "SKIP"

    return base_verdict

def confidence_bias(risk: dict, data: dict) -> str:
    macro = str(risk.get("macro_risk", "low")).lower()
    headline = str(risk.get("headline_risk", "low")).lower()
    market = str(risk.get("market_news_risk", "low")).lower()
    ticker = str(data.get("ticker", "")).upper()

    penalty = 0

    if macro == "high":
        penalty += 25
    elif macro == "medium":
        penalty += 12

    if headline == "high":
        penalty += 18
    elif headline == "medium":
        penalty += 8

    if market == "high":
        penalty += 15
    elif market == "medium":
        penalty += 6

    if ("NQ" in ticker or "MNQ" in ticker) and market in ["medium", "high"]:
        penalty += 5

    if ("ES" in ticker or "MES" in ticker) and macro in ["medium", "high"]:
        penalty += 5

    if penalty >= 30:
        return "Strongly reduce confidence."
    elif penalty >= 15:
        return "Reduce confidence."
    elif penalty > 0:
        return "Slightly reduce confidence."
    return "Normal confidence."

# ==================================================
# PARSER
# ==================================================
def extract_fields(text: str) -> dict:
    if not text:
        return {
            "verdict": "UNKNOWN",
            "confidence": "N/A",
            "why": "No response.",
            "risk": "Unknown.",
            "execution": "Stand by.",
            "summary": "No summary.",
        }

    def grab(label, default):
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

# ==================================================
# PROMPT BUILDERS
# ==================================================
def build_prompt(data: dict) -> str:
    risk = load_risk_state()
    base_verdict = pre_verdict_engine(data)
    fusion = apply_fusion_overlay(base_verdict, risk, data)
    confidence_note = confidence_bias(risk, data)

    warnings = ", ".join(risk["active_warnings"]) if risk["active_warnings"] else "none"

    return f"""
Analyze this futures trading alert.

Alert:
Ticker: {data["ticker"]}
Price: {data["price"]}
Signal: {data["signal"]}
Timeframe: {data["timeframe"]}
Session: {data["session"]}
Setup: {data["setup_type"]}
Priority: {data["signal_priority"]}
Context: {data["context_strength"]}
Market State: {data["market_state"]}
Scenario: {data["scenario"]}
Fib Zone: {data["fib_zone"]}
Liquidity: {data["liquidity"]}
Bias: {data["bias"]}
Score: {data["score"]}
Quality: {data["quality"]}

Risk Layer:
Macro Risk: {risk["macro_risk"]}
Headline Risk: {risk["headline_risk"]}
Market News Risk: {risk["market_news_risk"]}
Warnings: {warnings}
Next Event: {risk["next_event"]}
Minutes To Event: {risk["minutes_to_event"]}
Event Phase: {risk.get("event_phase", "")}
Donna Session: {risk.get("donna_session", "")}
Last Headline: {risk["last_headline"]}
Headline Severity: {risk.get("headline_severity", "")}
Headline Guidance: {risk.get("headline_guidance", "")}
Last Market Headline: {risk["last_market_headline"]}
Market Symbol: {risk.get("last_market_symbol", "")}
Market Severity: {risk.get("last_market_severity", "")}
Market Guidance: {risk.get("last_market_guidance", "")}

Deterministic Verdict: {base_verdict}
Fusion Verdict: {fusion}
Confidence Guidance: {confidence_note}
""".strip()

def build_market_driver_engine():
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

    # ==========================================
    # AI / TECH LEADERSHIP
    # ==========================================
    if any(x in market_text for x in [
        "nvidia", "microsoft", "apple", "amazon",
        "meta", "google", "tesla", "ai"
    ]):
        dominant_driver = "AI / Mega-Cap Leadership"
        regime = "Risk-On Trend"
        confidence = "High"
        summary = "Large-cap leadership is supporting index strength."

    # ==========================================
    # MACRO EVENT PRESSURE
    # ==========================================
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

    # ==========================================
    # HEADLINE SHOCK
    # ==========================================
    if headline == "high":
        dominant_driver = "Headline Shock"
        regime = "Reactive Conditions"
        confidence = "High"
        summary = "Breaking headlines are driving price reaction."

    # ==========================================
    # MARKET NEWS / EARNINGS
    # ==========================================
    if market == "high" and dominant_driver == "Balanced Conditions":
        dominant_driver = "Company / Earnings Catalyst"
        regime = "Catalyst Driven"
        confidence = "Medium"
        summary = "Company-specific catalysts are influencing index direction."

    # ==========================================
    # EVENT PHASE LOGIC
    # ==========================================
    if event_phase == "LIVE":
        threat = "Live Macro Release"
        regime = "Volatility Expansion"

    elif event_phase == "IMMINENT":
        threat = next_event or "Event Imminent"

    elif event_phase == "POST_EVENT_COOLDOWN":
        secondary_driver = "Post-Event Repricing"

    # ==========================================
    # SESSION LOGIC
    # ==========================================
    if session == "ASIA" and confidence == "Low":
        regime = "Thin Liquidity"

    elif session == "LONDON" and confidence == "Low":
        regime = "Expansion Window"

    elif session == "NEW_YORK_CASH" and confidence == "Low":
        regime = "Primary Volume Session"

    # ==========================================
    # SECONDARY DRIVER DETECTION
    # ==========================================
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
        "market_summary": summary
    }

def summarize_system_context() -> str:
    risk = load_risk_state()
    alerts = load_alert_history()[:5]
    assistant = load_assistant_state()

    donna_time_ny = risk.get("donna_time_ny") or local_now_ny().isoformat()
    donna_time_utc = risk.get("donna_time_utc") or local_now_utc().isoformat()
    donna_day = risk.get("donna_day") or local_day_name()
    donna_session = risk.get("donna_session") or local_session_label()

    alerts_text = []
    for a in alerts:
        alerts_text.append(
            f"{a.get('ticker', 'UNK')} {a.get('signal', '')} {a.get('verdict', '')} "
            f"{a.get('confidence', '')} @ {a.get('price', '')}"
        )

    return f"""
Current Donna state:

Time Engine:
- Donna Time NY: {donna_time_ny}
- Donna Time UTC: {donna_time_utc}
- Donna Day: {donna_day}
- Donna Session: {donna_session}

Macro Timing:
- Next Event: {risk.get("next_event", "none")}
- Event Time NY: {risk.get("event_time_ny", "unknown")}
- Minutes To Event: {risk.get("minutes_to_event", "unknown")}
- Event Phase: {risk.get("event_phase", "unknown")}
- Macro Risk: {risk.get("macro_risk", "low")}

Headline / News Layer:
- Headline Risk: {risk.get("headline_risk", "low")}
- Last Headline: {risk.get("last_headline", "none")}
- Headline Severity: {risk.get("headline_severity", "none")}
- Headline Guidance: {risk.get("headline_guidance", "none")}
- Headline Source: {risk.get("headline_source", "none")}

Market Catalyst Layer:
- Market News Risk: {risk.get("market_news_risk", "low")}
- Last Market Headline: {risk.get("last_market_headline", "none")}
- Market Symbol: {risk.get("last_market_symbol", "none")}
- Market Severity: {risk.get("last_market_severity", "none")}
- Market Guidance: {risk.get("last_market_guidance", "none")}

Warnings:
- Active Warnings: {", ".join(risk.get("active_warnings", [])) if risk.get("active_warnings") else "none"}

Assistant State:
- Daily Focus: {assistant.get("daily_focus", "")}
- Tasks: {assistant.get("tasks", [])}
- Reminders: {assistant.get("reminders", [])}

Recent Alerts:
- {" | ".join(alerts_text) if alerts_text else "No recent alerts"}
""".strip()

# ==================================================
# FORMATTERS / ACTIONS
# ==================================================
def format_message(data: dict, result: dict) -> str:
    return f"""DONNA // {data['ticker']} // {data['signal']}
{data['session']} | TF {data['timeframe']} | Price {data['price']}

Verdict: {result['verdict']}
Confidence: {result['confidence']}
Why: {result['why']}
Risk: {result['risk']}
Execution: {result['execution']}
Summary: {result['summary']}"""

def apply_assistant_action(action: str, value: str) -> dict:
    state = load_assistant_state()

    action = str(action or "none").strip().lower()
    value = str(value or "").strip()

    if action == "set_focus" and value:
        state["daily_focus"] = value
        save_assistant_state(state)
    elif action == "add_task" and value:
        state["tasks"].append(value)
        state["tasks"] = state["tasks"][:20]
        save_assistant_state(state)
    elif action == "add_reminder" and value:
        state["reminders"].append(value)
        state["reminders"] = state["reminders"][:20]
        save_assistant_state(state)
    elif action == "clear_tasks":
        state["tasks"] = []
        save_assistant_state(state)
    elif action == "clear_reminders":
        state["reminders"] = []
        save_assistant_state(state)

    return state

# ==================================================
# SIGNAL PROCESSOR
# ==================================================
def process_signal(payload: dict):
    try:
        data = normalize_payload(payload)

        if data["signal"] == "NONE":
            return

        prompt = build_prompt(data)

        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=DONNA_SYSTEM_PROMPT,
            input=prompt,
            max_output_tokens=220,
        )

        raw = response.output_text
        parsed = extract_fields(raw)

        add_alert_to_history(data, parsed)

        msg = format_message(data, parsed)

        if should_send_trade_to_telegram(parsed):
            send_telegram_message(msg)

    except Exception as e:
        print("Signal error:", str(e))

# ==================================================
# LOOPS
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
            print("Headline loop error:", str(e))
        await asyncio.sleep(HEADLINE_POLL_SECONDS)

async def finnhub_loop():
    while True:
        try:
            await asyncio.to_thread(process_finnhub_cycle)
        except Exception as e:
            print("Finnhub loop error:", str(e))
        await asyncio.sleep(FINNHUB_POLL_SECONDS)

# ==================================================
# STARTUP
# ==================================================
@app.on_event("startup")
async def startup():
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
async def root():
    return {"status": "Donna is online"}

@app.head("/")
async def root_head():
    return Response(status_code=200)

# ==================================================
# ROUTES - DATA
# ==================================================
@app.get("/risk-state")
async def risk_state():
    return load_risk_state()

@app.get("/alerts-data")
async def alerts_data():
    return {"alerts": load_alert_history()}

@app.get("/assistant-data")
async def assistant_data():
    return load_assistant_state()

@app.get("/dashboard-data")
async def dashboard_data():
    state = load_risk_state()
    alerts = load_alert_history()
    assistant = load_assistant_state()
    driver = build_market_driver_engine()

    return {
        "status": "online",
        "macro_risk": state.get("macro_risk", "low"),
        "headline_risk": state.get("headline_risk", "low"),
        "market_news_risk": state.get("market_news_risk", "low"),
        "active_warnings": state.get("active_warnings", []),
        "next_event": state.get("next_event", ""),
        "minutes_to_event": state.get("minutes_to_event", None),
        "last_headline": state.get("last_headline", ""),
        "last_market_headline": state.get("last_market_headline", ""),
        "last_updated": state.get("last_updated", ""),
        "headline_severity": state.get("headline_severity", ""),
        "headline_guidance": state.get("headline_guidance", ""),
        "headline_source": state.get("headline_source", ""),
        "last_market_symbol": state.get("last_market_symbol", ""),
        "last_market_severity": state.get("last_market_severity", ""),
        "last_market_guidance": state.get("last_market_guidance", ""),
        "last_market_url": state.get("last_market_url", ""),
        "donna_time_utc": state.get("donna_time_utc") or local_now_utc().isoformat(),
        "donna_time_ny": state.get("donna_time_ny") or local_now_ny().isoformat(),
        "donna_day": state.get("donna_day") or local_day_name(),
        "donna_session": state.get("donna_session") or local_session_label(),
        "event_phase": state.get("event_phase", ""),
        "event_time_ny": state.get("event_time_ny", ""),
        "alerts": alerts[:10],
        "assistant": assistant,
        **driver
    }

@app.get("/check-env")
async def check_env():
    return {
        "openai_key_found": bool(OPENAI_API_KEY),
        "telegram_found": bool(TELEGRAM_BOT_TOKEN),
        "newsapi_found": bool(os.getenv("NEWSAPI_KEY")),
        "finnhub_found": bool(os.getenv("FINNHUB_API_KEY")),
        "risk_file_exists": RISK_STATE_FILE.exists(),
        "alerts_file_exists": ALERTS_FILE.exists(),
        "assistant_file_exists": ASSISTANT_FILE.exists(),
        "telegram_alert_mode": TELEGRAM_ALERT_MODE,
        "model": OPENAI_MODEL,
    }

@app.get("/test-telegram")
async def test_telegram():
    return send_telegram_message("DONNA TEST MESSAGE")

# ==================================================
# ROUTES - ASSISTANT ACTIONS
# ==================================================
@app.post("/assistant/set-focus")
async def assistant_set_focus(request: Request):
    body = await request.json()
    value = str(body.get("daily_focus", "")).strip()

    if not value:
        raise HTTPException(status_code=400, detail="daily_focus is required")

    state = load_assistant_state()
    state["daily_focus"] = value
    save_assistant_state(state)

    return {"status": "ok", "assistant": state}

@app.post("/assistant/add-task")
async def assistant_add_task(request: Request):
    body = await request.json()
    value = str(body.get("task", "")).strip()

    if not value:
        raise HTTPException(status_code=400, detail="task is required")

    state = load_assistant_state()
    state["tasks"].append(value)
    state["tasks"] = state["tasks"][:20]
    save_assistant_state(state)

    return {"status": "ok", "assistant": state}

@app.post("/assistant/add-reminder")
async def assistant_add_reminder(request: Request):
    body = await request.json()
    value = str(body.get("reminder", "")).strip()

    if not value:
        raise HTTPException(status_code=400, detail="reminder is required")

    state = load_assistant_state()
    state["reminders"].append(value)
    state["reminders"] = state["reminders"][:20]
    save_assistant_state(state)

    return {"status": "ok", "assistant": state}

@app.post("/assistant/delete-task")
async def assistant_delete_task(request: Request):
    body = await request.json()
    index = body.get("index", None)

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
async def assistant_delete_reminder(request: Request):
    body = await request.json()
    index = body.get("index", None)

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
async def assistant_clear_tasks():
    state = load_assistant_state()
    state["tasks"] = []
    save_assistant_state(state)
    return {"status": "ok", "assistant": state}

@app.post("/assistant/clear-reminders")
async def assistant_clear_reminders():
    state = load_assistant_state()
    state["reminders"] = []
    save_assistant_state(state)
    return {"status": "ok", "assistant": state}

@app.post("/assistant/chat")
async def assistant_chat(request: Request):
    body = await request.json()
    message = str(body.get("message", "")).strip()

    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    context = summarize_system_context()

    fallback = {
        "action": "none",
        "value": "",
        "reply": "State check complete. No action taken.",
    }

    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=DONNA_ASSISTANT_PROMPT,
            input=f"User message:\n{message}\n\nSystem context:\n{context}",
            max_output_tokens=220,
        )

        parsed = parse_json_loose(response.output_text, fallback)

        action = str(parsed.get("action", "none")).strip().lower()
        value = str(parsed.get("value", "")).strip()
        reply = str(parsed.get("reply", "")).strip()

        risk = load_risk_state()

        if not reply:
            event_phase = str(risk.get("event_phase", "")).upper()
            minutes_to_event = risk.get("minutes_to_event", None)
            donna_session = str(risk.get("donna_session", "unknown"))

            if event_phase == "LIVE":
                reply = "Macro event is live. Volatility is active now. Stand down until reaction becomes clear."
            elif event_phase == "IMMINENT":
                reply = f"High-impact event is close. {minutes_to_event} minutes remaining. Reduce size and avoid random entries."
            elif event_phase == "APPROACHING":
                reply = f"Event risk is building. {minutes_to_event} minutes to the next macro event. Stay selective."
            elif event_phase == "POST_EVENT_COOLDOWN":
                reply = "Recent macro release is still affecting conditions. Treat this as a cooldown volatility window."
            else:
                reply = f"Donna time check complete. Session: {donna_session}. No direct action taken."

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
# DASHBOARD
# ==================================================
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>D.O.N.N.A Recovery</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;}
:root{
    --bg:#060912;
    --bg2:#0b1220;
    --bg3:#101a2d;
    --panel:rgba(15,23,38,.82);
    --panel2:rgba(18,28,46,.96);
    --line:rgba(255,255,255,.07);
    --text:#eef4ff;
    --muted:#8ea4c5;
    --low:#4dffab;
    --medium:#ffd24f;
    --high:#ff637d;
    --blue:#4f8cff;
    --blue2:#2b5fd9;
    --chip:rgba(255,255,255,.04);
    --shadow:0 14px 40px rgba(0,0,0,.34);
    --radius:22px;
}
html,body{min-height:100%;}
body{
    font-family:Inter,Arial,sans-serif;
    color:var(--text);
    background:
        radial-gradient(circle at top right, rgba(79,140,255,.18), transparent 25%),
        radial-gradient(circle at 15% 85%, rgba(77,255,171,.08), transparent 20%),
        linear-gradient(180deg,var(--bg2) 0%,var(--bg) 100%);
    padding:20px;
}
.wrapper{max-width:1540px;margin:0 auto;}
.topbar{
    display:flex;
    justify-content:space-between;
    align-items:flex-start;
    gap:18px;
    flex-wrap:wrap;
    margin-bottom:16px;
}
.brand h1{font-size:42px;line-height:1;letter-spacing:4px;font-weight:900;}
.brand p{margin-top:8px;color:var(--muted);font-size:14px;letter-spacing:.4px;}
.top-right{display:flex;flex-direction:column;align-items:flex-end;gap:12px;}
.status-strip{
    display:flex;align-items:center;gap:12px;padding:10px 16px;border-radius:999px;
    background:rgba(77,255,171,.08);border:1px solid rgba(77,255,171,.22);box-shadow:var(--shadow);
}
.pulse-dot{
    width:11px;height:11px;border-radius:50%;background:var(--low);
    box-shadow:0 0 16px rgba(77,255,171,.8);animation:pulse 1.6s infinite;
}
@keyframes pulse{
    0%{transform:scale(.9);opacity:.9;}
    70%{transform:scale(1.22);opacity:.35;}
    100%{transform:scale(.95);opacity:.9;}
}
.status-text{font-weight:800;font-size:13px;letter-spacing:.8px;color:#a5ffc8;}
.navbar{display:flex;gap:10px;flex-wrap:wrap;}
.nav-btn{
    border:none;cursor:pointer;border-radius:14px;padding:12px 16px;font-weight:800;font-size:13px;
    color:#d6e4fb;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.06);transition:.18s ease;
}
.nav-btn:hover{background:rgba(255,255,255,.08);}
.nav-btn.active{background:linear-gradient(135deg,var(--blue),var(--blue2));color:white;box-shadow:var(--shadow);}
.live-strip{
    display:grid;grid-template-columns:220px 1fr 220px;gap:12px;align-items:center;margin-bottom:16px;
}
.live-pill{
    background:linear-gradient(135deg, rgba(255,99,125,.16), rgba(255,99,125,.08));
    border:1px solid rgba(255,99,125,.22);border-radius:16px;padding:14px 16px;
    font-size:12px;font-weight:900;letter-spacing:1.4px;text-transform:uppercase;color:#ffc0cc;
}
.ticker{
    position:relative;overflow:hidden;border-radius:16px;background:rgba(255,255,255,.04);
    border:1px solid rgba(255,255,255,.07);min-height:52px;display:flex;align-items:center;box-shadow:var(--shadow);
}
.ticker-track{
    display:inline-flex;white-space:nowrap;padding-left:100%;animation:tickerMove 24s linear infinite;will-change:transform;
}
@keyframes tickerMove{
    0%{transform:translateX(0);}
    100%{transform:translateX(-100%);}
}
.ticker-item{padding-right:50px;font-size:14px;color:#dce8fb;}
.ticker-strong{font-weight:800;color:#ffffff;}
.session-chip{
    background:linear-gradient(135deg, rgba(79,140,255,.16), rgba(79,140,255,.08));
    border:1px solid rgba(79,140,255,.22);border-radius:16px;padding:14px 16px;text-align:center;box-shadow:var(--shadow);
}
.session-chip .top{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:1.2px;}
.session-chip .val{margin-top:5px;font-size:16px;font-weight:900;}
.hero{display:grid;grid-template-columns:1.45fr 1fr;gap:16px;margin-bottom:18px;}
.panel,.stat-card{
    background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
    padding:20px;box-shadow:var(--shadow);backdrop-filter:blur(10px);
}
.panel{background:var(--panel2);}
.hero-title{font-size:12px;text-transform:uppercase;letter-spacing:1.8px;color:var(--muted);margin-bottom:14px;}
.hero-headline{font-size:34px;font-weight:900;line-height:1.08;margin-bottom:12px;}
.hero-sub{color:var(--muted);line-height:1.55;font-size:15px;}
.hero-side{display:grid;gap:14px;}
.hero-focus{font-size:20px;font-weight:800;line-height:1.35;}
.hero-mini{display:grid;grid-template-columns:1fr 1fr;gap:12px;}
.mini-card{
    background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:16px;padding:14px;
}
.mini-label{font-size:11px;text-transform:uppercase;letter-spacing:1.2px;color:var(--muted);}
.mini-value{margin-top:6px;font-size:16px;font-weight:900;}
.stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:18px;}
.label{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:1.6px;margin-bottom:14px;}
.value{font-size:40px;font-weight:900;line-height:1;}
.value.low{color:var(--low);}
.value.medium{color:var(--medium);}
.value.high{color:var(--high);}
.value.event{font-size:24px;color:#fff;line-height:1.15;}
.sub{margin-top:10px;color:var(--muted);font-size:14px;}
.section{display:none;}
.section.active{display:block;}
.grid-2{display:grid;grid-template-columns:1.3fr 1fr;gap:16px;}
.grid-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;}
.section-title{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:1.6px;margin-bottom:14px;}
.feed-item{padding:13px 0;border-bottom:1px solid rgba(255,255,255,.06);color:#e9f1fe;font-size:15px;line-height:1.45;}
.feed-item:last-child{border-bottom:none;padding-bottom:0;}
.feed-label{color:white;font-weight:800;}
.badge{
    display:inline-flex;align-items:center;gap:8px;padding:8px 12px;border-radius:999px;font-size:12px;font-weight:800;
    background:var(--chip);border:1px solid rgba(255,255,255,.06);margin:0 8px 8px 0;color:#deebff;
}
.badge.high{color:#ffc0cc;border-color:rgba(255,99,125,.25);background:rgba(255,99,125,.09);}
.badge.medium{color:#ffe08c;border-color:rgba(255,210,79,.25);background:rgba(255,210,79,.09);}
.badge.low{color:#baffdc;border-color:rgba(77,255,171,.25);background:rgba(77,255,171,.09);}
.alert-box{padding:14px 0;border-bottom:1px solid rgba(255,255,255,.06);}
.alert-box:last-child{border-bottom:none;}
.alert-top{
    display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;font-weight:800;color:#f2f7ff;
}
.alert-meta{margin-top:7px;color:var(--muted);font-size:13px;}
.alert-summary{margin-top:7px;color:#d8e5f8;line-height:1.45;font-size:14px;}
.kv{display:flex;justify-content:space-between;gap:12px;padding:13px 0;border-bottom:1px solid rgba(255,255,255,.06);font-size:14px;}
.kv:last-child{border-bottom:none;}
.kv-label{color:#dce7f9;}
.kv-value{color:var(--muted);text-align:right;}
.input,.textarea{
    width:100%;border-radius:14px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.04);
    color:white;outline:none;padding:13px 14px;margin-top:10px;font-size:14px;
}
.textarea{min-height:110px;resize:vertical;}
.btn-row{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px;}
.btn{
    padding:11px 15px;border:none;border-radius:13px;cursor:pointer;font-weight:800;font-size:13px;
    color:white;background:#1f3c67;transition:.18s ease;
}
.btn:hover{transform:translateY(-1px);}
.btn.primary{background:linear-gradient(135deg,var(--blue),var(--blue2));}
.btn.secondary{background:#253754;}
.btn.ghost{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);}
.item-row{
    display:flex;justify-content:space-between;gap:12px;align-items:center;padding:12px 0;border-bottom:1px solid rgba(255,255,255,.06);
}
.item-row:last-child{border-bottom:none;}
.item-text{flex:1;color:#e6eefb;font-size:14px;line-height:1.45;}
.item-actions{display:flex;gap:8px;flex-shrink:0;}
.quick-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px;}
.quick-chip{
    padding:10px 12px;border-radius:12px;border:1px solid rgba(255,255,255,.07);background:rgba(255,255,255,.04);
    color:#deebff;cursor:pointer;font-size:13px;font-weight:700;
}
.quick-chip:hover{background:rgba(255,255,255,.07);}
.chat-shell{display:flex;flex-direction:column;gap:12px;}
.chat-output{
    min-height:240px;max-height:500px;overflow:auto;border-radius:18px;background:rgba(0,0,0,.18);
    border:1px solid rgba(255,255,255,.06);padding:14px;
}
.chat-msg{margin-bottom:12px;padding:12px 13px;border-radius:14px;line-height:1.5;font-size:14px;}
.chat-msg.user{background:rgba(79,140,255,.13);border:1px solid rgba(79,140,255,.2);}
.chat-msg.assistant{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.06);}
.chat-role{display:block;font-size:11px;text-transform:uppercase;letter-spacing:1.1px;color:var(--muted);margin-bottom:6px;}
.console-card{min-height:190px;}
.console-head{font-size:20px;font-weight:900;color:#f4f8ff;line-height:1.2;}
.console-note{margin-top:10px;color:var(--muted);line-height:1.55;font-size:14px;}
.link-out{display:inline-block;margin-top:10px;color:#9ec2ff;text-decoration:none;font-size:13px;font-weight:700;}
.news-feature{position:relative;overflow:hidden;}
.news-feature:before{
    content:"";position:absolute;inset:0;background:linear-gradient(135deg, rgba(79,140,255,.08), transparent 45%);pointer-events:none;
}
.breaking-tag{
    display:inline-flex;align-items:center;gap:8px;padding:8px 12px;border-radius:999px;background:rgba(255,99,125,.12);
    border:1px solid rgba(255,99,125,.25);color:#ffc0cc;font-size:11px;font-weight:900;text-transform:uppercase;letter-spacing:1.2px;margin-bottom:14px;
}
.breaking-dot{width:8px;height:8px;border-radius:50%;background:var(--high);box-shadow:0 0 14px rgba(255,99,125,.8);}
.footer{margin-top:18px;display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap;color:var(--muted);font-size:13px;}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;}
@media(max-width:1180px){
    .hero{grid-template-columns:1fr;}
    .live-strip{grid-template-columns:1fr;}
    .stat-grid{grid-template-columns:repeat(2,1fr);}
    .grid-2,.grid-3{grid-template-columns:1fr;}
}
@media(max-width:760px){
    body{padding:14px;}
    .brand h1{font-size:30px;}
    .hero-headline{font-size:26px;}
    .stat-grid{grid-template-columns:1fr;}
    .item-row{flex-direction:column;align-items:flex-start;}
    .item-actions{width:100%;}
}
</style>
</head>
<body>
<div class="wrapper">

    <div class="topbar">
        <div class="brand">
            <h1>D.O.N.N.A</h1>
            <p>Dynamic Operational Neural Network Assistant // Recovery Build</p>
        </div>

        <div class="top-right">
            <div class="status-strip">
                <div class="pulse-dot"></div>
                <div class="status-text" id="status_text">ONLINE</div>
            </div>

            <div class="navbar">
                <button class="nav-btn active" onclick="showSection('dashboard', this)">Dashboard</button>
                <button class="nav-btn" onclick="showSection('trading', this)">Trading</button>
                <button class="nav-btn" onclick="showSection('news', this)">News</button>
                <button class="nav-btn" onclick="showSection('assistant', this)">Assistant</button>
            </div>
        </div>
    </div>

    <div class="live-strip">
        <div class="live-pill">Live Intelligence</div>
        <div class="ticker">
            <div class="ticker-track" id="ticker_track">
                <div class="ticker-item"><span class="ticker-strong">Donna</span> loading live intelligence...</div>
            </div>
        </div>
        <div class="session-chip">
            <div class="top">Current Session</div>
            <div class="val" id="session_chip_val">-</div>
        </div>
    </div>

    <div class="hero">
        <div class="panel">
            <div class="hero-title">Donna Overview</div>
            <div class="hero-headline" id="hero_headline">System online. Monitoring macro, global headlines, market catalysts, and alerts.</div>
            <div class="hero-sub" id="hero_sub">
                Donna is running as the command center for trading intelligence, event risk, headline pressure, and operator support.
            </div>
        </div>        <div class="panel hero-side">
            <div>
                <div class="hero-title">Daily Focus</div>
                <div class="hero-focus" id="daily_focus_hero">Loading...</div>
            </div>

            <div class="hero-mini">
                <div class="mini-card">
                    <div class="mini-label">Donna Time</div>
                    <div class="mini-value mono" id="donna_time_ny">-</div>
                </div>
                <div class="mini-card">
                    <div class="mini-label">Event Phase</div>
                    <div class="mini-value" id="event_phase">-</div>
                </div>
            </div>

            <div>
                <div class="hero-title">Next Event Window</div>
                <div style="font-size:18px;font-weight:800;" id="next_event_hero">Loading...</div>
                <div class="sub" id="next_event_hero_sub">Waiting for data...</div>
            </div>
        </div>
    </div>

    <div class="stat-grid">
        <div class="stat-card">
            <div class="label">Macro Risk</div>
            <div class="value" id="macro_risk">-</div>
            <div class="sub">Red-folder and macro event pressure</div>
        </div>

        <div class="stat-card">
            <div class="label">Headline Risk</div>
            <div class="value" id="headline_risk">-</div>
            <div class="sub">Global market-moving headline pressure</div>
        </div>

        <div class="stat-card">
            <div class="label">Market Risk</div>
            <div class="value" id="market_news_risk">-</div>
            <div class="sub">Company and sector catalyst pressure</div>
        </div>

        <div class="stat-card">
            <div class="label">Next Event</div>
            <div class="value event" id="next_event">-</div>
            <div class="sub" id="minutes_to_event">No timed event loaded</div>
        </div>
    </div>

    <div class="section active" id="section-dashboard">
        <div class="grid-2">
            <div>
                <div class="panel">
                    <div class="section-title">Active Warnings</div>
                    <div id="warnings"></div>
                </div>

                <div class="panel" style="margin-top:16px;">
                    <div class="section-title">Donna Internal Clock</div>
                    <div class="kv"><div class="kv-label">New York Time</div><div class="kv-value mono" id="donna_time_ny_panel">-</div></div>
                    <div class="kv"><div class="kv-label">UTC Time</div><div class="kv-value mono" id="donna_time_utc">-</div></div>
                    <div class="kv"><div class="kv-label">Day</div><div class="kv-value" id="donna_day">-</div></div>
                    <div class="kv"><div class="kv-label">Session</div><div class="kv-value" id="donna_session">-</div></div>
                    <div class="kv"><div class="kv-label">Event Phase</div><div class="kv-value" id="event_phase_panel">-</div></div>
                    <div class="kv"><div class="kv-label">Event Time NY</div><div class="kv-value" id="event_time_ny">-</div></div>
                </div>
            </div>

            <div>
                <div class="panel">
                    <div class="section-title">Recent Donna Alerts</div>
                    <div id="alerts_feed_dashboard">
                        <div class="feed-item">No alerts yet</div>
                    </div>
                </div>

            <div class="panel" style="margin-top:16px;">
                <div class="section-title">Market Driver Engine</div>

                <div class="kv">
                    <div class="kv-label">Dominant Driver</div>
                    <div class="kv-value" id="dominant_driver">-</div>
                </div>

                <div class="kv">
                    <div class="kv-label">Secondary Driver</div>
                    <div class="kv-value" id="secondary_driver">-</div>
                </div>

                <div class="kv">
                    <div class="kv-label">Regime</div>
                    <div class="kv-value" id="market_regime">-</div>
                </div>

                <div class="kv">
                    <div class="kv-label">Threat</div>
                    <div class="kv-value" id="market_threat">-</div>
                </div>

                <div class="kv">
                    <div class="kv-label">Confidence</div>
                    <div class="kv-value" id="market_confidence">-</div>
                </div>

                <div class="sub" id="market_summary" style="margin-top:14px;">
                    No driver summary available.
                </div>
            </div>

                <div class="panel" style="margin-top:16px;">
                    <div class="section-title">Risk Radar</div>
                    <div class="kv"><div class="kv-label">Headline Severity</div><div class="kv-value" id="headline_severity_dash">-</div></div>
                    <div class="kv"><div class="kv-label">Market Severity</div><div class="kv-value" id="market_severity_dash">-</div></div>
                    <div class="kv"><div class="kv-label">Last Updated</div><div class="kv-value mono" id="last_updated">-</div></div>
                </div>
            </div>
        </div>
    </div>

    <div class="section" id="section-trading">
        <div class="grid-2">
            <div>
                <div class="panel">
                    <div class="section-title">Trade Alert Feed</div>
                    <div id="alerts_feed_trading">
                        <div class="feed-item">No alerts yet</div>
                    </div>
                </div>
            </div>

            <div>
                <div class="panel">
                    <div class="section-title">Trading Command Snapshot</div>
                    <div class="kv"><div class="kv-label">Telegram Mode</div><div class="kv-value" id="telegram_mode">-</div></div>
                    <div class="kv"><div class="kv-label">Latest Signal Count</div><div class="kv-value" id="alert_count">-</div></div>
                    <div class="kv"><div class="kv-label">Macro Risk Bias</div><div class="kv-value" id="macro_bias_trading">-</div></div>
                    <div class="kv"><div class="kv-label">Headline Risk Bias</div><div class="kv-value" id="headline_bias_trading">-</div></div>
                    <div class="kv"><div class="kv-label">Market Risk Bias</div><div class="kv-value" id="market_bias_trading">-</div></div>
                </div>
            </div>
        </div>
    </div>

    <div class="section" id="section-news">
        <div class="grid-3">
            <div class="panel news-feature console-card">
                <div class="breaking-tag"><span class="breaking-dot"></span> Breaking</div>
                <div class="section-title">Top Story</div>
                <div class="console-head" id="headline_title">No major headline detected</div>
                <div class="console-note" id="headline_note">Headline guidance unavailable.</div>
                <div class="sub" id="headline_source">Source: -</div>
            </div>

            <div class="panel console-card">
                <div class="section-title">Macro Countdown</div>
                <div class="console-head" id="news_macro_title">No major event loaded</div>
                <div class="console-note" id="news_macro_note">Donna is monitoring upcoming macro volatility windows.</div>
                <div class="kv"><div class="kv-label">Phase</div><div class="kv-value" id="event_phase_news">-</div></div>
                <div class="kv"><div class="kv-label">Event Time</div><div class="kv-value" id="event_time_news">-</div></div>
                <div class="kv"><div class="kv-label">Session</div><div class="kv-value" id="session_news">-</div></div>
            </div>

            <div class="panel console-card">
                <div class="section-title">Market Catalyst</div>
                <div class="console-head" id="market_title">No major market catalyst detected</div>
                <div class="console-note" id="market_note">Market guidance unavailable.</div>
                <div class="kv"><div class="kv-label">Severity</div><div class="kv-value" id="market_severity_news">-</div></div>
                <div class="kv"><div class="kv-label">Symbol</div><div class="kv-value" id="market_symbol_news">-</div></div>
                <a class="link-out" id="market_link" href="#" target="_blank" rel="noopener noreferrer" style="display:none;">Open source</a>
            </div>
        </div>

        <div class="grid-2" style="margin-top:16px;">
            <div>
                <div class="panel">
                    <div class="section-title">Donna Briefing</div>
                    <div id="warning_pressure_news"></div>
                    <div class="feed-item"><span class="feed-label">Latest Headline:</span> <span id="last_headline">No recent headline</span></div>
                    <div class="feed-item"><span class="feed-label">Latest Market Story:</span> <span id="last_market_headline">No recent market headline</span></div>
                </div>
            </div>

            <div>
                <div class="panel">
                    <div class="section-title">Live Risk Radar</div>
                    <div class="kv"><div class="kv-label">Macro Risk</div><div class="kv-value" id="macro_news">-</div></div>
                    <div class="kv"><div class="kv-label">Headline Risk</div><div class="kv-value" id="headline_news">-</div></div>
                    <div class="kv"><div class="kv-label">Market Risk</div><div class="kv-value" id="market_news">-</div></div>
                    <div class="kv"><div class="kv-label">Headline Severity</div><div class="kv-value" id="headline_severity_news">-</div></div>
                    <div class="kv"><div class="kv-label">Market Severity</div><div class="kv-value" id="market_severity_news_2">-</div></div>
                </div>
            </div>
        </div>
    </div>

    <div class="section" id="section-assistant">
        <div class="grid-2">
            <div>
                <div class="panel">
                    <div class="section-title">Donna AI Assistant</div>

                    <div class="chat-shell">
                        <div class="chat-output" id="chat_output">
                            <div class="chat-msg assistant">
                                <span class="chat-role">Donna</span>
                                Donna online. Ask for risk, time, session, event timing, news, alerts, or give a command.
                            </div>
                        </div>

                        <textarea class="textarea" id="chat_input" placeholder="Ask Donna something or give a command..."></textarea>

                        <div class="btn-row">
                            <button class="btn primary" onclick="sendDonnaChat()">Send to Donna</button>
                            <button class="btn ghost" onclick="quickAsk('What is the current risk environment?')">Risk Summary</button>
                            <button class="btn ghost" onclick="quickAsk('What time is it and what session are we in?')">Time Check</button>
                            <button class="btn ghost" onclick="quickAsk('Is this a dangerous time to trade?')">Danger Check</button>
                        </div>

                        <div class="quick-actions">
                            <button class="quick-chip" onclick="quickAsk('What matters right now?')">What Matters</button>
                            <button class="quick-chip" onclick="quickAsk('How long until the next event?')">Time To Event</button>
                            <button class="quick-chip" onclick="quickAsk('Are we near a red-folder event?')">Red Folder Check</button>
                            <button class="quick-chip" onclick="quickAsk('Summarize the latest headline risk.')">Headline Risk</button>
                            <button class="quick-chip" onclick="quickAsk('Summarize the latest market catalyst.')">Market Catalyst</button>
                            <button class="quick-chip" onclick="quickAsk('Set my focus to execution and discipline.')">Set Focus</button>
                            <button class="quick-chip" onclick="quickAsk('Add task review top alerts.')">Add Task</button>
                            <button class="quick-chip" onclick="quickAsk('Add reminder review next macro event.')">Add Reminder</button>
                        </div>
                    </div>
                </div>
            </div>

            <div>
                <div class="panel">
                    <div class="section-title">Assistant Control Panel</div>

                    <div class="assistant-item">
                        <strong>Daily Focus</strong>
                        <div class="sub" id="daily_focus">Loading...</div>
                        <input class="input" id="focus_input" placeholder="Set daily focus..." />
                        <div class="btn-row">
                            <button class="btn primary" onclick="saveFocus()">Save Focus</button>
                        </div>
                    </div>

                    <div style="height:14px;"></div>

                    <div class="assistant-item">
                        <strong>Tasks</strong>
                        <div id="tasks_list" class="sub">Loading...</div>
                        <input class="input" id="task_input" placeholder="Add task..." />
                        <div class="btn-row">
                            <button class="btn secondary" onclick="addTask()">Add Task</button>
                            <button class="btn ghost" onclick="clearTasks()">Clear All</button>
                        </div>
                    </div>

                    <div style="height:14px;"></div>

                    <div class="assistant-item">
                        <strong>Reminders</strong>
                        <div id="reminders_list" class="sub">Loading...</div>
                        <input class="input" id="reminder_input" placeholder="Add reminder..." />
                        <div class="btn-row">
                            <button class="btn secondary" onclick="addReminder()">Add Reminder</button>
                            <button class="btn ghost" onclick="clearReminders()">Clear All</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="footer">
        <div>D.O.N.N.A Recovery</div>
        <div>Dashboard primary / news terminal / assistant layer active</div>
    </div>
</div>

<script>
function riskClass(v){
    const x = String(v || '').toLowerCase();
    if (x.includes('high')) return 'high';
    if (x.includes('medium')) return 'medium';
    return 'low';
}

function applyRisk(id, val){
    const el = document.getElementById(id);
    el.className = 'value ' + riskClass(val);
    el.innerText = String(val || '-').toUpperCase();
}

function escapeHtml(value){
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function showSection(sectionName, btn){
    document.querySelectorAll('.section').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
    document.getElementById('section-' + sectionName).classList.add('active');
    btn.classList.add('active');
}

function addChatMessage(role, text){
    const output = document.getElementById('chat_output');
    const div = document.createElement('div');
    div.className = 'chat-msg ' + role;
    div.innerHTML = `
        <span class="chat-role">${role === 'user' ? 'You' : 'Donna'}</span>
        ${escapeHtml(text)}
    `;
    output.appendChild(div);
    output.scrollTop = output.scrollHeight;
}

function formatTimeText(mins){
    if (mins === null || mins === undefined) return 'No timed event loaded';
    if (mins === 0) return 'Live or immediate event window';
    return mins + ' minutes remaining';
}

function setText(id, value, fallback='-'){
    const el = document.getElementById(id);
    if (el) el.innerText = value || fallback;
}

function buildTicker(data){
    const warnings = (data.active_warnings || []).slice(0,4);
    const items = [];

    items.push(`<div class="ticker-item"><span class="ticker-strong">Macro:</span> ${escapeHtml(String(data.macro_risk || '-').toUpperCase())}</div>`);
    items.push(`<div class="ticker-item"><span class="ticker-strong">Headline:</span> ${escapeHtml(String(data.headline_risk || '-').toUpperCase())}</div>`);
    items.push(`<div class="ticker-item"><span class="ticker-strong">Market:</span> ${escapeHtml(String(data.market_news_risk || '-').toUpperCase())}</div>`);
    items.push(`<div class="ticker-item"><span class="ticker-strong">Next:</span> ${escapeHtml(data.next_event || 'No event loaded')}</div>`);

    warnings.forEach(w => {
        items.push(`<div class="ticker-item"><span class="ticker-strong">Warning:</span> ${escapeHtml(w)}</div>`);
    });

    if (data.last_headline){
        items.push(`<div class="ticker-item"><span class="ticker-strong">Headline:</span> ${escapeHtml(data.last_headline)}</div>`);
    }

    if (data.last_market_headline){
        items.push(`<div class="ticker-item"><span class="ticker-strong">Market Story:</span> ${escapeHtml(data.last_market_headline)}</div>`);
    }

    document.getElementById('ticker_track').innerHTML = items.join('');
}

async function saveFocus(){
    const value = document.getElementById('focus_input').value.trim();
    if(!value) return;

    await fetch('/assistant/set-focus', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({daily_focus:value})
    });

    document.getElementById('focus_input').value = '';
    refreshDashboard();
}

async function addTask(){
    const value = document.getElementById('task_input').value.trim();
    if(!value) return;

    await fetch('/assistant/add-task', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({task:value})
    });

    document.getElementById('task_input').value = '';
    refreshDashboard();
}

async function addReminder(){
    const value = document.getElementById('reminder_input').value.trim();
    if(!value) return;

    await fetch('/assistant/add-reminder', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({reminder:value})
    });

    document.getElementById('reminder_input').value = '';
    refreshDashboard();
}

async function deleteTask(index){
    await fetch('/assistant/delete-task', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({index:index})
    });
    refreshDashboard();
}

async function deleteReminder(index){
    await fetch('/assistant/delete-reminder', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({index:index})
    });
    refreshDashboard();
}

async function clearTasks(){
    await fetch('/assistant/clear-tasks', {method:'POST'});
    refreshDashboard();
}

async function clearReminders(){
    await fetch('/assistant/clear-reminders', {method:'POST'});
    refreshDashboard();
}

async function quickAsk(text){
    document.getElementById('chat_input').value = text;
    await sendDonnaChat();
}

async function sendDonnaChat(){
    const input = document.getElementById('chat_input');
    const message = input.value.trim();
    if(!message) return;

    addChatMessage('user', message);
    input.value = '';

    try{
        const res = await fetch('/assistant/chat', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({message})
        });

        const data = await res.json();
        addChatMessage('assistant', data.reply || 'Command complete.');
        refreshDashboard();
    }catch(err){
        addChatMessage('assistant', 'Assistant route error.');
        console.log(err);
    }
}

function renderWarnings(warnings, targetId){
    const box = document.getElementById(targetId);
    if (warnings && warnings.length){
        box.innerHTML = warnings.map(x => {
            const low = String(x).toLowerCase();
            const cls = low.includes('high') || low.includes('critical')
                ? 'high'
                : low.includes('medium')
                    ? 'medium'
                    : 'low';
            return '<span class="badge ' + cls + '">' + escapeHtml(x) + '</span>';
        }).join('');
    } else {
        box.innerHTML = '<span class="badge low">No active warnings</span>';
    }
}

function renderAlerts(alerts, targetId){
    const box = document.getElementById(targetId);

    if (!alerts || !alerts.length){
        box.innerHTML = '<div class="feed-item">No alerts yet</div>';
        return;
    }

    box.innerHTML = alerts.map(a => `
        <div class="alert-box">
            <div class="alert-top">
                <span>${escapeHtml(a.ticker)} | ${escapeHtml(a.signal)} | ${escapeHtml(a.verdict)}</span>
                <span>${escapeHtml(a.confidence)}</span>
            </div>
            <div class="alert-meta">
                TF: ${escapeHtml(a.timeframe)} | Session: ${escapeHtml(a.session)} | Price: ${escapeHtml(a.price)}
            </div>
            <div class="alert-summary">
                ${escapeHtml(a.summary || '')}
            </div>
            <div class="alert-meta mono">
                ${escapeHtml(a.timestamp || '')}
            </div>
        </div>
    `).join('');
}

function renderTasks(tasks){
    const box = document.getElementById('tasks_list');

    if (!tasks || !tasks.length){
        box.innerHTML = '<div class="feed-item">No tasks</div>';
        return;
    }

    box.innerHTML = tasks.map((x, i) => `
        <div class="item-row">
            <div class="item-text">${escapeHtml(x)}</div>
            <div class="item-actions">
                <button class="btn ghost" onclick="deleteTask(${i})">Delete</button>
            </div>
        </div>
    `).join('');
}

function renderReminders(reminders){
    const box = document.getElementById('reminders_list');

    if (!reminders || !reminders.length){
        box.innerHTML = '<div class="feed-item">No reminders</div>';
        return;
    }

    box.innerHTML = reminders.map((x, i) => `
        <div class="item-row">
            <div class="item-text">${escapeHtml(x)}</div>
            <div class="item-actions">
                <button class="btn ghost" onclick="deleteReminder(${i})">Delete</button>
            </div>
        </div>
    `).join('');
}

async function refreshDashboard(){
    try{
        const res = await fetch('/dashboard-data');
        const data = await res.json();

        const status = String(data.status || 'online').toUpperCase();
        const assistant = data.assistant || {};
        const alerts = data.alerts || [];

        setText('status_text', status);
        applyRisk('macro_risk', data.macro_risk);
        applyRisk('headline_risk', data.headline_risk);
        applyRisk('market_news_risk', data.market_news_risk);

        const nextEvent = data.next_event || 'NONE';
        const mins = data.minutes_to_event;

        setText('next_event', nextEvent);
        setText('next_event_hero', nextEvent);
        setText('next_event_hero_sub', formatTimeText(mins));
        setText('minutes_to_event', formatTimeText(mins));

        setText('daily_focus', assistant.daily_focus || 'No focus set');
        setText('daily_focus_hero', assistant.daily_focus || 'No focus set');

        setText('donna_time_ny', data.donna_time_ny || '-');
        setText('donna_time_ny_panel', data.donna_time_ny || '-');
        setText('donna_time_utc', data.donna_time_utc || '-');
        setText('donna_day', data.donna_day || '-');
        setText('donna_session', data.donna_session || '-');
        setText('event_phase', data.event_phase || '-');
        setText('event_phase_panel', data.event_phase || '-');
        setText('event_time_ny', data.event_time_ny || '-');
        setText('session_chip_val', data.donna_session || '-');

        const heroHead = `System online. ${String(data.macro_risk || 'low').toUpperCase()} macro risk, ${String(data.headline_risk || 'low').toUpperCase()} headline risk, ${String(data.market_news_risk || 'low').toUpperCase()} market risk.`;
        setText('hero_headline', heroHead);

        const hasWarnings = data.active_warnings && data.active_warnings.length;
        const heroSub = hasWarnings
            ? 'Active warnings are live. Donna is monitoring macro timing, headline shock, market catalyst pressure, and session context.'
            : 'No major live warning pressure. Donna is monitoring time, events, signals, and operator state.';
        setText('hero_sub', heroSub);

        renderWarnings(data.active_warnings || [], 'warnings');
        renderWarnings(data.active_warnings || [], 'warning_pressure_news');
        renderAlerts(alerts, 'alerts_feed_dashboard');
        renderAlerts(alerts, 'alerts_feed_trading');
        renderTasks(assistant.tasks || []);
        renderReminders(assistant.reminders || []);

        setText('telegram_mode', 'LIVE');
        setText('alert_count', String(alerts.length || 0));
        setText('macro_bias_trading', String(data.macro_risk || '-').toUpperCase());
        setText('headline_bias_trading', String(data.headline_risk || '-').toUpperCase());
        setText('market_bias_trading', String(data.market_news_risk || '-').toUpperCase());

        setText('headline_severity_dash', data.headline_severity || '-');
        setText('market_severity_dash', data.last_market_severity || '-');

        setText('dominant_driver', data.dominant_driver || '-');
        setText('secondary_driver', data.secondary_driver || '-');
        setText('market_regime', data.market_regime || '-');
        setText('market_threat', data.market_threat || '-');
        setText('market_confidence', data.market_confidence || '-');
        setText('market_summary', data.market_summary || 'No driver summary available.');
        setText('last_updated', data.last_updated || '-');

        setText('headline_title', data.last_headline || 'No major headline detected');
        setText('headline_note', data.headline_guidance || 'Headline guidance unavailable.');
        setText('headline_source', 'Source: ' + (data.headline_source || '-'));

        setText('market_title', data.last_market_headline || 'No major market catalyst detected');
        setText('market_note', data.last_market_guidance || 'Market guidance unavailable.');
        setText('market_severity_news', data.last_market_severity || '-');
        setText('market_severity_news_2', data.last_market_severity || '-');
        setText('market_symbol_news', data.last_market_symbol || '-');

        setText('last_headline', data.last_headline || 'No recent headline');
        setText('last_market_headline', data.last_market_headline || 'No recent market headline');

        setText('macro_news', String(data.macro_risk || '-').toUpperCase());
        setText('headline_news', String(data.headline_risk || '-').toUpperCase());
        setText('market_news', String(data.market_news_risk || '-').toUpperCase());
        setText('headline_severity_news', data.headline_severity || '-');

        const macroTitle = data.next_event || 'No major event loaded';
        let macroNote = 'Donna is monitoring upcoming macro volatility windows.';
        if (data.event_phase === 'LIVE'){
            macroNote = 'Macro event live. Volatility sensitivity elevated.';
        } else if (data.event_phase === 'IMMINENT'){
            macroNote = 'High-impact event is imminent. Reduce size and avoid random entries.';
        } else if (data.event_phase === 'APPROACHING'){
            macroNote = `${mins} minutes to next major event.`;
        } else if (data.event_phase === 'POST_EVENT_COOLDOWN'){
            macroNote = 'Recent event released. Cooldown volatility window is still active.';
        } else if (mins !== null && mins !== undefined){
            macroNote = `${mins} minutes to next major event.`;
        }
        setText('news_macro_title', macroTitle);
        setText('news_macro_note', macroNote);
        setText('event_phase_news', data.event_phase || '-');
        setText('event_time_news', data.event_time_ny || '-');
        setText('session_news', data.donna_session || '-');

        const marketLink = document.getElementById('market_link');
        if (data.last_market_url){
            marketLink.style.display = 'inline-block';
            marketLink.href = data.last_market_url;
        } else {
            marketLink.style.display = 'none';
            marketLink.href = '#';
        }

        buildTicker(data);

    }catch(err){
        console.log(err);
    }
}

document.getElementById('chat_input').addEventListener('keydown', async function(e){
    if(e.key === 'Enter' && !e.shiftKey){
        e.preventDefault();
        await sendDonnaChat();
    }
});

refreshDashboard();
setInterval(refreshDashboard, 15000);
</script>
</body>
</html>
"""
# ==================================================
# WEBHOOK
# ==================================================
@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.body()
        text = body.decode("utf-8").strip()

        if not text:
            raise HTTPException(status_code=400, detail="Empty body")

        payload = json.loads(text)
        background_tasks.add_task(process_signal, payload)

        return {
            "status": "received",
            "ticker": payload.get("ticker", "UNKNOWN"),
            "signal": payload.get("signal", "UNKNOWN"),
        }

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
