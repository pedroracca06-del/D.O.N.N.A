from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
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
        "text": text,
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
    except Exception:
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
        "quality": str(payload.get("quality", "NA")).upper(),
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
        "model": OPENAI_MODEL,
    }


@app.get("/test-telegram")
async def test_telegram():
    return send_telegram_message("DONNA TEST MESSAGE")


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
*{
    margin:0;
    padding:0;
    box-sizing:border-box;
}

body{
    font-family: Inter, Arial, sans-serif;
    background: radial-gradient(circle at top right,#182030 0%,#0b0f14 45%,#05070a 100%);
    color:#ffffff;
    padding:24px;
}

.wrapper{
    max-width:1300px;
    margin:auto;
}

.topbar{
    display:flex;
    justify-content:space-between;
    align-items:center;
    margin-bottom:22px;
    gap:20px;
    flex-wrap:wrap;
}

.brand h1{
    font-size:34px;
    letter-spacing:2px;
    font-weight:800;
}

.brand p{
    color:#8ea0bd;
    margin-top:4px;
    font-size:14px;
}

.status-pill{
    padding:10px 16px;
    border-radius:999px;
    background:rgba(0,255,140,.08);
    border:1px solid rgba(0,255,140,.35);
    color:#7fffb6;
    font-size:14px;
    font-weight:700;
}

.grid{
    display:grid;
    grid-template-columns:repeat(auto-fit,minmax(240px,1fr));
    gap:16px;
    margin-bottom:18px;
}

.card{
    background:rgba(18,25,35,.88);
    border:1px solid rgba(255,255,255,.05);
    border-radius:18px;
    padding:18px;
    box-shadow:0 10px 30px rgba(0,0,0,.35);
}

.label{
    font-size:13px;
    color:#8ea0bd;
    margin-bottom:10px;
    text-transform:uppercase;
    letter-spacing:1px;
}

.value{
    font-size:28px;
    font-weight:800;
}

.low{color:#4dff9a;}
.medium{color:#ffd24d;}
.high{color:#ff5f6d;}

.section{
    margin-top:14px;
}

.big-card{
    background:rgba(18,25,35,.92);
    border:1px solid rgba(255,255,255,.05);
    border-radius:18px;
    padding:20px;
    margin-top:16px;
    box-shadow:0 10px 30px rgba(0,0,0,.35);
}

.feed-item{
    padding:10px 0;
    border-bottom:1px solid rgba(255,255,255,.05);
    color:#d9e2ef;
    font-size:15px;
}

.feed-item:last-child{
    border-bottom:none;
}

.small{
    color:#8ea0bd;
    font-size:13px;
    margin-top:6px;
}

.footer{
    margin-top:20px;
    color:#6f819d;
    font-size:13px;
}

.glow{
    box-shadow:0 0 0 1px rgba(80,160,255,.08),0 0 24px rgba(80,160,255,.08);
}

@media(max-width:700px){
    body{padding:14px;}
    .brand h1{font-size:26px;}
    .value{font-size:24px;}
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
        <div class="status-pill" id="status">ONLINE</div>
    </div>

    <div class="grid">

        <div class="card glow">
            <div class="label">Macro Risk</div>
            <div class="value" id="macro_risk">-</div>
        </div>

        <div class="card glow">
            <div class="label">Headline Risk</div>
            <div class="value" id="headline_risk">-</div>
        </div>

        <div class="card glow">
            <div class="label">Market Risk</div>
            <div class="value" id="market_news_risk">-</div>
        </div>

        <div class="card glow">
            <div class="label">Next Event</div>
            <div class="value" id="next_event">-</div>
            <div class="small" id="minutes_to_event"></div>
        </div>

    </div>

    <div class="big-card">
        <div class="label">Active Warnings</div>
        <div id="warnings"></div>
    </div>

    <div class="big-card">
        <div class="label">Latest Headlines</div>
        <div class="feed-item">
            <strong>News Feed:</strong>
            <span id="last_headline">-</span>
        </div>
        <div class="feed-item">
            <strong>Market Feed:</strong>
            <span id="last_market_headline">-</span>
        </div>
    </div>

    <div class="footer">
        Last Updated: <span id="last_updated">-</span>
    </div>

</div>

<script>
function riskClass(v){
    const x = String(v).toLowerCase();
    if(x.includes("high")) return "high";
    if(x.includes("medium")) return "medium";
    return "low";
}

function applyRisk(id,val){
    const el = document.getElementById(id);
    el.className = "value " + riskClass(val);
    el.innerText = String(val).toUpperCase();
}

async function refreshDashboard(){
    try{
        const res = await fetch('/dashboard-data');
        const data = await res.json();

        document.getElementById('status').innerText = data.status.toUpperCase();

        applyRisk('macro_risk', data.macro_risk);
        applyRisk('headline_risk', data.headline_risk);
        applyRisk('market_news_risk', data.market_news_risk);

        document.getElementById('next_event').innerText =
            data.next_event ? data.next_event : "NONE";

        document.getElementById('minutes_to_event').innerText =
            data.minutes_to_event !== null
            ? data.minutes_to_event + " minutes remaining"
            : "";

        const warnBox = document.getElementById('warnings');

        if(data.active_warnings && data.active_warnings.length){
            warnBox.innerHTML = data.active_warnings
                .map(x => '<div class="feed-item">' + x + '</div>')
                .join('');
        } else {
            warnBox.innerHTML = '<div class="feed-item">No active warnings</div>';
        }

        document.getElementById('last_headline').innerText =
            data.last_headline || "No recent headline";

        document.getElementById('last_market_headline').innerText =
            data.last_market_headline || "No recent market headline";

        document.getElementById('last_updated').innerText =
            data.last_updated || "-";

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
