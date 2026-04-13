from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
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

if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY")
if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")
if not TELEGRAM_CHAT_ID:
    raise RuntimeError("Missing TELEGRAM_CHAT_ID")

client = OpenAI(api_key=OPENAI_API_KEY)
app = FastAPI(title="DONNA MASTER CORE")

# ==================================================
# FILES
# ==================================================
RISK_STATE_FILE = BASE_DIR / "donna_risk_state.json"

# ==================================================
# LOOP TIMERS
# ==================================================
NEWS_POLL_SECONDS = 60
HEADLINE_POLL_SECONDS = 900
FINNHUB_POLL_SECONDS = 600

# ==================================================
# SYSTEM PROMPT
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

# ==================================================
# TELEGRAM
# ==================================================
def send_telegram_message(text: str) -> dict:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    }

    try:
        response = requests.post(url, json=payload, timeout=20)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

# ==================================================
# HELPERS
# ==================================================
def safe_float(value, default=0.0):
    try:
        return float(value)
    except:
        return default


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
        "quality": str(payload.get("quality", "NA")).upper()
    }


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
        "last_updated": ""
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

    except:
        return default_state

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

    # NQ = tech + macro sensitive
    if is_nq:
        if macro == "high":
            return "SKIP"
        if market == "high" and base_verdict == "TAKE":
            return "CAUTION"
        if macro == "medium" and base_verdict == "TAKE":
            return "CAUTION"
        if headline == "high":
            return "CAUTION" if base_verdict == "TAKE" else "SKIP"

    # ES = macro first
    if is_es:
        if macro == "high":
            return "SKIP"
        if macro == "medium" and base_verdict == "TAKE":
            return "CAUTION"
        if headline == "high" and base_verdict == "TAKE":
            return "CAUTION"

    # General fallback
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
            "summary": "No summary."
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
        "summary": grab("Summary", text.strip())
    }

# ==================================================
# PROMPT BUILDER
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

Deterministic Verdict: {base_verdict}
Fusion Verdict: {fusion}
Confidence Guidance: {confidence_note}
""".strip()

# ==================================================
# FORMATTER
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
            max_output_tokens=220
        )

        raw = response.output_text
        parsed = extract_fields(raw)

        msg = format_message(data, parsed)
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
    asyncio.create_task(news_loop())
    asyncio.create_task(headline_loop())
    asyncio.create_task(finnhub_loop())

# ==================================================
# ROUTES
# ==================================================
@app.get("/")
async def root():
    return {"status": "Donna is online"}


@app.get("/risk-state")
async def risk_state():
    return load_risk_state()


@app.get("/check-env")
async def check_env():
    return {
        "openai_key_found": bool(OPENAI_API_KEY),
        "telegram_found": bool(TELEGRAM_BOT_TOKEN),
        "newsapi_found": bool(os.getenv("NEWSAPI_KEY")),
        "finnhub_found": bool(os.getenv("FINNHUB_API_KEY")),
        "risk_file_exists": RISK_STATE_FILE.exists(),
        "model": OPENAI_MODEL
    }


@app.get("/test-telegram")
async def test_telegram():
    return send_telegram_message("DONNA TEST MESSAGE")


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
            "signal": payload.get("signal", "UNKNOWN")
        }

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
