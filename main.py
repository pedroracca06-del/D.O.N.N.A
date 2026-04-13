from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
import os
import requests
import json
import re

# =========================
# ENV LOAD
# =========================
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

app = FastAPI(title="Donna Jarvis Core")

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

# =========================
# DONNA SYSTEM PROMPT
# =========================
DONNA_SYSTEM_PROMPT = """
You are Donna, an elite futures execution assistant.

Your tone is cold, sharp, aggressive, and concise.
You sound like a high-level execution desk assistant.
You do not ramble. You do not hedge unnecessarily. You do not sound friendly or chatty.

Your job is to analyze ES/NQ futures alerts and issue a fast execution briefing.

Rules:
- Be decisive.
- Prioritize structure, liquidity, session, market state, context strength, score, and quality.
- If alignment is strong, say TAKE.
- If mixed, say CAUTION.
- If weak, conflicting, or poor quality, say SKIP.
- Keep every section tight.
- No fluff.
- No emojis inside the briefing.
- Do not mention AI.
- Do not restate raw JSON.

Output format exactly:

Verdict: TAKE / CAUTION / SKIP
Confidence: X%
Why: 1 sentence
Risk: 1 short sentence
Execution: 1 short sentence
Summary: 1 hard-hitting line
""".strip()

# =========================
# TELEGRAM
# =========================
def send_telegram_message(text: str) -> dict:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("Telegram credentials missing")
        return {"error": "Telegram bot token or chat id missing"}

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
    }

    try:
        print("Sending Telegram message...")
        response = requests.post(url, json=payload, timeout=15)
        print("Telegram status:", response.status_code)
        print("Telegram response:", response.text)
        return response.json()
    except Exception as e:
        print("Telegram error:", str(e))
        return {"error": str(e)}

# =========================
# HELPERS
# =========================
def safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
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


def pre_verdict_engine(data: dict) -> str:
    score = safe_float(data.get("score", 0))
    quality = str(data.get("quality", "NA")).upper()
    context = str(data.get("context_strength", "")).lower()
    session = str(data.get("session", ""))
    market_state = str(data.get("market_state", "")).lower()
    bias = str(data.get("bias", "")).lower()
    signal = str(data.get("signal", "")).upper()

    points = 0

    # Base score
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

    # Quality
    if quality == "A":
        points += 3
    elif quality == "B":
        points += 2
    elif quality == "C":
        points += 0
    else:
        points -= 1

    # Context
    if context == "strong":
        points += 3
    elif context == "moderate":
        points += 1
    elif context == "light":
        points -= 1

    # Session
    if session in ["NY", "London", "NY_PRE"]:
        points += 2
    elif session == "Asia":
        points -= 1
    else:
        points -= 2

    # Alignment
    aligned = (
        (signal == "LONG" and market_state != "bearish" and bias != "bearish")
        or
        (signal == "SHORT" and market_state != "bullish" and bias != "bullish")
    )

    if aligned:
        points += 2
    else:
        points -= 3

    # Final verdict
    if points >= 10:
        return "TAKE"
    elif points >= 5:
        return "CAUTION"
    else:
        return "SKIP"


def build_precheck(data: dict) -> str:
    signal = data["signal"]
    session = data["session"]
    context_strength = data["context_strength"].lower()
    market_state = data["market_state"].lower()
    bias = data["bias"].lower()
    quality = data["quality"].upper()
    score = safe_float(data["score"])
    signal_priority = data["signal_priority"].lower()

    alignment_good = (
        (signal == "LONG" and market_state != "bearish" and bias != "bearish")
        or
        (signal == "SHORT" and market_state != "bullish" and bias != "bullish")
    )

    strong_session = session in {"London", "NY_PRE", "NY"}
    weak_session = session in {"Asia", "OffHours", "unknown"}

    notes = []

    if quality == "A":
        notes.append("high_quality")
    elif quality == "B":
        notes.append("decent_quality")
    elif quality == "C":
        notes.append("lower_quality")
    else:
        notes.append("unknown_quality")

    if context_strength == "strong":
        notes.append("strong_context")
    elif context_strength == "moderate":
        notes.append("moderate_context")
    else:
        notes.append("light_context")

    if alignment_good:
        notes.append("aligned_state")
    else:
        notes.append("conflicting_state")

    if strong_session:
        notes.append("good_session")
    elif weak_session:
        notes.append("weaker_session")

    if signal_priority in {"continuation", "reversal"}:
        notes.append("strong_signal_family")
    elif signal_priority in {"liquidity", "liquidity_reaction", "fail", "failed_retrace"}:
        notes.append("secondary_signal_family")
    else:
        notes.append("unknown_signal_family")

    if score >= 75:
        notes.append("high_score")
    elif score >= 60:
        notes.append("good_score")
    elif score < 45:
        notes.append("weak_score")

    return ", ".join(notes)


def extract_briefing_fields(raw_reply: str) -> dict:
    if raw_reply is None:
        return {
            "verdict": "UNKNOWN",
            "confidence": "N/A",
            "why": "No response returned from AI.",
            "risk": "Unknown.",
            "execution": "Stand by.",
            "summary": "No valid output.",
        }

    text = str(raw_reply).strip()
    text = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE).strip()
    text = text.replace("```", "").strip()

    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        json_text = json_match.group(0).strip()
        try:
            data = json.loads(json_text)
            return {
                "verdict": str(data.get("verdict", "UNKNOWN")).strip().upper(),
                "confidence": str(data.get("confidence", "N/A")).strip(),
                "why": str(data.get("why", data.get("reason", "No reason provided."))).strip(),
                "risk": str(data.get("risk", "Unknown.")).strip(),
                "execution": str(data.get("execution", "Stand by.")).strip(),
                "summary": str(data.get("summary", "No summary provided.")).strip(),
            }
        except Exception as e:
            print("Primary JSON parse failed:", str(e))

    verdict_match = re.search(r"Verdict:\s*(.+)", text, re.IGNORECASE)
    confidence_match = re.search(r"Confidence:\s*(.+)", text, re.IGNORECASE)
    why_match = re.search(r"Why:\s*(.+)", text, re.IGNORECASE)
    risk_match = re.search(r"Risk:\s*(.+)", text, re.IGNORECASE)
    execution_match = re.search(r"Execution:\s*(.+)", text, re.IGNORECASE)
    summary_match = re.search(r"Summary:\s*(.+)", text, re.IGNORECASE)

    return {
        "verdict": verdict_match.group(1).strip().upper() if verdict_match else "UNKNOWN",
        "confidence": confidence_match.group(1).strip() if confidence_match else "N/A",
        "why": why_match.group(1).strip() if why_match else "No reason provided.",
        "risk": risk_match.group(1).strip() if risk_match else "Unknown.",
        "execution": execution_match.group(1).strip() if execution_match else "Stand by.",
        "summary": summary_match.group(1).strip() if summary_match else text,
    }


def build_user_prompt(data: dict) -> str:
    precheck = build_precheck(data)
    pre_verdict = pre_verdict_engine(data)

    return f"""
Analyze this futures trading alert and return the required execution briefing.

Alert data:
- Ticker: {data["ticker"]}
- Price: {data["price"]}
- Signal: {data["signal"]}
- Timeframe: {data["timeframe"]}
- Session: {data["session"]}
- Setup type: {data["setup_type"]}
- Signal priority: {data["signal_priority"]}
- Context strength: {data["context_strength"]}
- Market state: {data["market_state"]}
- Scenario: {data["scenario"]}
- Fib zone: {data["fib_zone"]}
- Liquidity: {data["liquidity"]}
- Bias: {data["bias"]}
- Score: {data["score"]}
- Quality: {data["quality"]}

Deterministic precheck:
- {precheck}

Deterministic pre-verdict:
- {pre_verdict}

Interpretation goals:
- Reward alignment between signal, bias, market state, and session.
- Be stricter on low-quality, weak-context, Asia, or off-hours alerts.
- If setup is continuation/reversal with strong context and alignment, lean TAKE.
- If mixed, lean CAUTION.
- If conflicting, weak, or poor quality, lean SKIP.
- Execution should be brief and practical.
""".strip()


def format_telegram_message(data: dict, parsed: dict) -> str:
    header = f"DONNA // {data['ticker']} // {data['signal']}"
    meta = f"{data['session']} | TF {data['timeframe']} | Price {data['price']}"

    return f"""{header}
{meta}

Verdict: {parsed['verdict']}
Confidence: {parsed['confidence']}
Why: {parsed['why']}
Risk: {parsed['risk']}
Execution: {parsed['execution']}
Summary: {parsed['summary']}"""


# =========================
# CORE SIGNAL PROCESSOR
# =========================
def process_signal(payload: dict) -> None:
    try:
        print("Processing payload in background:", payload)

        data = normalize_payload(payload)
        print("Normalized payload:", data)

        if data["signal"] == "NONE":
            print("Signal is NONE, skipping.")
            return

        prompt = build_user_prompt(data)
        print("Prompt built successfully.")

        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=DONNA_SYSTEM_PROMPT,
            input=prompt,
            max_output_tokens=220,
        )

        raw_reply = response.output_text
        print("Raw reply repr:", repr(raw_reply))

        parsed = extract_briefing_fields(raw_reply)
        print("Parsed reply:", parsed)

        message = format_telegram_message(data, parsed)
        print("Final Telegram message:", message)

        telegram_result = send_telegram_message(message)
        print("Telegram result:", telegram_result)

    except Exception as e:
        print("Processing error:", str(e))


# =========================
# ROUTES
# =========================
@app.get("/")
async def root():
    return {"status": "Donna is online"}


@app.get("/check-env")
async def check_env():
    return {
        "env_file_exists": env_path.exists(),
        "openai_key_found": bool(os.getenv("OPENAI_API_KEY")),
        "telegram_bot_found": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
        "telegram_chat_found": bool(os.getenv("TELEGRAM_CHAT_ID")),
        "openai_model": OPENAI_MODEL,
    }


@app.get("/test-telegram")
async def test_telegram():
    result = send_telegram_message("DONNA TEST — Telegram path is working")
    return {"result": result}


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        raw_body = await request.body()
        body_text = raw_body.decode("utf-8", errors="ignore").strip()

        print("Raw webhook body:", repr(body_text))

        if not body_text:
            raise HTTPException(status_code=400, detail="Empty webhook body")

        try:
            payload = json.loads(body_text)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON body: {str(e)}")

        print("Received payload:", payload)

        background_tasks.add_task(process_signal, payload)

        return {
            "status": "received",
            "signal": payload.get("signal", "UNKNOWN"),
            "ticker": payload.get("ticker", "UNKNOWN"),
        }

    except HTTPException:
        raise
    except Exception as e:
        print("Webhook error:", str(e))
        raise HTTPException(status_code=500, detail=str(e))
