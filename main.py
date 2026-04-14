from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timezone
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
ALERTS_FILE = BASE_DIR / "donna_alert_history.json"
ASSISTANT_FILE = BASE_DIR / "donna_assistant_state.json"

# ==================================================
# LOOP TIMERS
# ==================================================
NEWS_POLL_SECONDS = 60
HEADLINE_POLL_SECONDS = 900
FINNHUB_POLL_SECONDS = 600

# ==================================================
# TELEGRAM MODE
# all = send every trade alert
# critical = only strong alerts
# off = dashboard only
# ==================================================
TELEGRAM_ALERT_MODE = os.getenv("TELEGRAM_ALERT_MODE", "all").lower()

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
Last Headline: {risk["last_headline"]}
Last Market Headline: {risk["last_market_headline"]}

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
    asyncio.create_task(news_loop())
    asyncio.create_task(headline_loop())
    asyncio.create_task(finnhub_loop())

# ==================================================
# ROUTES - DATA
# ==================================================
@app.get("/")
async def root():
    return {"status": "Donna is online"}


@app.get("/risk-state")
async def risk_state():
    return load_risk_state()


@app.get("/alerts-data")
async def alerts_data():
    return {"alerts": load_alert_history()}


@app.get("/assistant-data")
async def assistant_data():
    return load_assistant_state()


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

# ==================================================
# ROUTES - DASHBOARD
# ==================================================
@app.get("/dashboard-data")
async def dashboard_data():
    state = load_risk_state()
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
    }


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>D.O.N.N.A Command Center</title>

<style>
*{margin:0;padding:0;box-sizing:border-box;}
:root{
    --bg:#060a10;
    --bg2:#0b1220;
    --panel:rgba(14,21,34,.82);
    --panel-2:rgba(18,27,42,.92);
    --line:rgba(255,255,255,.06);
    --text:#f2f6fc;
    --muted:#8ca0bf;
    --low:#47ff9c;
    --medium:#ffd24d;
    --high:#ff5e74;
    --glow:0 0 30px rgba(89,167,255,.08);
}
body{
    font-family: Inter, Arial, sans-serif;
    background:
        radial-gradient(circle at top right, rgba(46,113,255,.16), transparent 25%),
        radial-gradient(circle at bottom left, rgba(0,255,153,.08), transparent 20%),
        linear-gradient(180deg, var(--bg2) 0%, var(--bg) 100%);
    color:var(--text);
    padding:24px;
}
.wrapper{max-width:1380px;margin:0 auto;}
.topbar{
    display:flex;justify-content:space-between;align-items:center;gap:18px;flex-wrap:wrap;margin-bottom:22px;
}
.brand h1{font-size:38px;letter-spacing:4px;font-weight:900;}
.brand p{margin-top:6px;color:var(--muted);font-size:14px;letter-spacing:.4px;}
.status-wrap{display:flex;align-items:center;gap:12px;}
.pulse-dot{
    width:12px;height:12px;border-radius:50%;background:var(--low);
    box-shadow:0 0 18px rgba(71,255,156,.85);animation:pulse 1.6s infinite;
}
@keyframes pulse{
    0%{transform:scale(.9);opacity:.9;}
    70%{transform:scale(1.25);opacity:.35;}
    100%{transform:scale(.95);opacity:.9;}
}
.status-pill{
    padding:10px 18px;border-radius:999px;background:rgba(71,255,156,.08);
    border:1px solid rgba(71,255,156,.28);color:#9cffc7;font-size:14px;font-weight:800;letter-spacing:.6px;
}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:18px;}
.card,.panel{
    background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:20px;
    box-shadow:var(--glow);backdrop-filter:blur(10px);
}
.panel{background:var(--panel-2);}
.label{
    font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:1.6px;margin-bottom:14px;
}
.value{font-size:40px;font-weight:900;line-height:1;}
.value.low{color:var(--low);}
.value.medium{color:var(--medium);}
.value.high{color:var(--high);}
.value.event{font-size:26px;color:#ffffff;}
.sub{margin-top:10px;color:var(--muted);font-size:14px;}
.layout{display:grid;grid-template-columns:1.65fr .95fr;gap:16px;align-items:start;}
.section-title{
    font-size:13px;color:var(--muted);text-transform:uppercase;letter-spacing:1.6px;margin-bottom:14px;
}
.feed-item{
    padding:12px 0;border-bottom:1px solid rgba(255,255,255,.06);color:#e6edf7;font-size:15px;line-height:1.45;
}
.feed-item:last-child{border-bottom:none;padding-bottom:0;}
.feed-label{color:#ffffff;font-weight:700;}
.warning-badge{
    display:inline-block;padding:7px 11px;border-radius:999px;font-size:12px;font-weight:700;
    margin:0 8px 8px 0;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.03);color:#d8e4f7;
}
.assistant-box{display:flex;flex-direction:column;gap:12px;}
.assistant-item{
    padding:14px;border-radius:14px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.05);
    color:#dde6f3;font-size:14px;line-height:1.45;
}
.history-row{
    display:flex;justify-content:space-between;gap:12px;padding:12px 0;border-bottom:1px solid rgba(255,255,255,.06);font-size:14px;
}
.history-row:last-child{border-bottom:none;}
.history-label{color:#dfe8f5;}
.history-value{color:var(--muted);text-align:right;}
.alert-box{padding:12px 0;border-bottom:1px solid rgba(255,255,255,.06);}
.alert-box:last-child{border-bottom:none;}
.alert-top{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;font-weight:700;color:#eef4fd;}
.alert-meta{margin-top:6px;color:var(--muted);font-size:13px;}
.alert-summary{margin-top:6px;color:#d8e4f4;font-size:14px;line-height:1.4;}
.small{color:var(--muted);font-size:13px;margin-top:6px;}
.input{
    width:100%;padding:12px 14px;border-radius:12px;border:1px solid rgba(255,255,255,.08);
    background:rgba(255,255,255,.04);color:white;outline:none;margin-top:10px;
}
.btn-row{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px;}
.btn{
    padding:10px 14px;border:none;border-radius:12px;cursor:pointer;font-weight:700;
    background:#1d3557;color:white;
}
.btn.secondary{background:#243b55;}
.item-row{
    display:flex;
    justify-content:space-between;
    gap:10px;
    align-items:center;
    padding:12px 0;
    border-bottom:1px solid rgba(255,255,255,.06);
}
.item-row:last-child{border-bottom:none;}
.item-text{
    color:#e6edf7;
    font-size:14px;
    line-height:1.4;
    flex:1;
}
.item-actions{
    display:flex;
    gap:8px;
    flex-shrink:0;
}
.footer{
    margin-top:16px;display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap;color:var(--muted);font-size:13px;
}
@media(max-width:1100px){
    .grid{grid-template-columns:repeat(2,1fr);}
    .layout{grid-template-columns:1fr;}
}
@media(max-width:680px){
    body{padding:14px;}
    .brand h1{font-size:28px;}
    .grid{grid-template-columns:1fr;}
    .value{font-size:34px;}
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
            <p>Dynamic Operational Neural Network Assistant</p>
        </div>

        <div class="status-wrap">
            <div class="pulse-dot"></div>
            <div class="status-pill" id="status">ONLINE</div>
        </div>
    </div>

    <div class="grid">
        <div class="card">
            <div class="label">Macro Risk</div>
            <div class="value" id="macro_risk">-</div>
            <div class="sub">Scheduled event pressure</div>
        </div>

        <div class="card">
            <div class="label">Headline Risk</div>
            <div class="value" id="headline_risk">-</div>
            <div class="sub">Breaking macro / geopolitical flow</div>
        </div>

        <div class="card">
            <div class="label">Market Risk</div>
            <div class="value" id="market_news_risk">-</div>
            <div class="sub">Company / sector catalyst pressure</div>
        </div>

        <div class="card">
            <div class="label">Next Event</div>
            <div class="value event" id="next_event">-</div>
            <div class="sub" id="minutes_to_event"></div>
        </div>
    </div>

    <div class="layout">
        <div>
            <div class="panel">
                <div class="section-title">Active Warnings</div>
                <div id="warnings"></div>
            </div>

            <div class="panel" style="margin-top:16px;">
                <div class="section-title">Live Intelligence Feed</div>

                <div class="feed-item">
                    <span class="feed-label">News Feed:</span>
                    <span id="last_headline">No recent headline</span>
                </div>

                <div class="feed-item">
                    <span class="feed-label">Market Feed:</span>
                    <span id="last_market_headline">No recent market headline</span>
                </div>
            </div>

            <div class="panel" style="margin-top:16px;">
                <div class="section-title">Recent Donna Alerts</div>
                <div id="alerts_feed">
                    <div class="feed-item">No alerts yet</div>
                </div>
            </div>
        </div>

        <div>
            <div class="panel">
                <div class="section-title">Assistant Panel</div>

                <div class="assistant-box">
                    <div class="assistant-item">
                        <strong>Daily Focus</strong>
                        <div class="small" id="daily_focus">Loading...</div>
                        <input class="input" id="focus_input" placeholder="Set daily focus..." />
                        <div class="btn-row">
                            <button class="btn" onclick="saveFocus()">Save Focus</button>
                        </div>
                    </div>

                    <div class="assistant-item">
                        <strong>Today's Tasks</strong>
                        <div id="tasks_list" class="small">Loading...</div>
                        <input class="input" id="task_input" placeholder="Add task..." />
                        <div class="btn-row">
                            <button class="btn secondary" onclick="addTask()">Add Task</button>
                            <button class="btn" onclick="clearTasks()">Clear All</button>
                        </div>
                    </div>

                    <div class="assistant-item">
                        <strong>Reminders</strong>
                        <div id="reminders_list" class="small">Loading...</div>
                        <input class="input" id="reminder_input" placeholder="Add reminder..." />
                        <div class="btn-row">
                            <button class="btn secondary" onclick="addReminder()">Add Reminder</button>
                            <button class="btn" onclick="clearReminders()">Clear All</button>
                        </div>
                    </div>
                </div>
            </div>

            <div class="panel" style="margin-top:16px;">
                <div class="section-title">System Snapshot</div>

                <div class="history-row">
                    <div class="history-label">Status</div>
                    <div class="history-value" id="status_2">ONLINE</div>
                </div>

                <div class="history-row">
                    <div class="history-label">Next Event</div>
                    <div class="history-value" id="next_event_2">-</div>
                </div>

                <div class="history-row">
                    <div class="history-label">Minutes Remaining</div>
                    <div class="history-value" id="minutes_to_event_2">-</div>
                </div>

                <div class="history-row">
                    <div class="history-label">Last Updated</div>
                    <div class="history-value" id="last_updated">-</div>
                </div>
            </div>
        </div>
    </div>

    <div class="footer">
        <div>D.O.N.N.A Interface</div>
        <div>Dashboard Primary / Telegram Secondary</div>
    </div>
</div>

<script>
function riskClass(v){
    const x = String(v).toLowerCase();
    if (x.includes("high")) return "high";
    if (x.includes("medium")) return "medium";
    return "low";
}

function applyRisk(id, val){
    const el = document.getElementById(id);
    el.className = "value " + riskClass(val);
    el.innerText = String(val).toUpperCase();
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
    await fetch('/assistant/clear-tasks', {
        method:'POST'
    });

    refreshDashboard();
}

async function clearReminders(){
    await fetch('/assistant/clear-reminders', {
        method:'POST'
    });

    refreshDashboard();
}

async function refreshDashboard(){
    try{
        const res = await fetch('/dashboard-data');
        const data = await res.json();

        const status = (data.status || "online").toUpperCase();
        document.getElementById('status').innerText = status;
        document.getElementById('status_2').innerText = status;

        applyRisk('macro_risk', data.macro_risk);
        applyRisk('headline_risk', data.headline_risk);
        applyRisk('market_news_risk', data.market_news_risk);

        const nextEvent = data.next_event || "NONE";
        document.getElementById('next_event').innerText = nextEvent;
        document.getElementById('next_event_2').innerText = nextEvent;

        const mins = data.minutes_to_event;
        document.getElementById('minutes_to_event').innerText =
            mins !== null ? mins + " minutes remaining" : "No timed event loaded";
        document.getElementById('minutes_to_event_2').innerText =
            mins !== null ? mins : "-";

        const warnBox = document.getElementById('warnings');
        if (data.active_warnings && data.active_warnings.length){
            warnBox.innerHTML = data.active_warnings
                .map(x => '<span class="warning-badge">' + x + '</span>')
                .join('');
        } else {
            warnBox.innerHTML = '<span class="warning-badge">No active warnings</span>';
        }

        document.getElementById('last_headline').innerText =
            data.last_headline || "No recent headline";

        document.getElementById('last_market_headline').innerText =
            data.last_market_headline || "No recent market headline";

        document.getElementById('last_updated').innerText =
            data.last_updated || "-";

        const alertsRes = await fetch('/alerts-data');
        const alertsJson = await alertsRes.json();
        const alerts = alertsJson.alerts || [];

        const alertsFeed = document.getElementById('alerts_feed');

        if (alerts.length) {
            alertsFeed.innerHTML = alerts.map(a => `
                <div class="alert-box">
                    <div class="alert-top">
                        <span>${a.ticker} | ${a.signal} | ${a.verdict}</span>
                        <span>${a.confidence}</span>
                    </div>
                    <div class="alert-meta">
                        TF: ${a.timeframe} | Session: ${a.session} | Price: ${a.price}
                    </div>
                    <div class="alert-summary">
                        ${a.summary || ""}
                    </div>
                    <div class="alert-meta">
                        ${a.timestamp}
                    </div>
                </div>
            `).join('');
        } else {
            alertsFeed.innerHTML = '<div class="feed-item">No alerts yet</div>';
        }

        const assistantRes = await fetch('/assistant-data');
        const assistant = await assistantRes.json();

        document.getElementById('daily_focus').innerText =
            assistant.daily_focus || "No focus set";

        document.getElementById('tasks_list').innerHTML =
            assistant.tasks && assistant.tasks.length
                ? assistant.tasks.map((x, i) => `
                    <div class="item-row">
                        <div class="item-text">${x}</div>
                        <div class="item-actions">
                            <button class="btn secondary" onclick="deleteTask(${i})">Delete</button>
                        </div>
                    </div>
                `).join('')
                : '<div class="feed-item">No tasks</div>';

        document.getElementById('reminders_list').innerHTML =
            assistant.reminders && assistant.reminders.length
                ? assistant.reminders.map((x, i) => `
                    <div class="item-row">
                        <div class="item-text">${x}</div>
                        <div class="item-actions">
                            <button class="btn secondary" onclick="deleteReminder(${i})">Delete</button>
                        </div>
                    </div>
                `).join('')
                : '<div class="feed-item">No reminders</div>';

    } catch(err){
        console.log(err);
    }
}

refreshDashboard();
setInterval(refreshDashboard, 5000);
</script>
</body>
</html>
"""


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
