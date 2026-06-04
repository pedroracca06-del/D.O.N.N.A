"""donna_config.py — constants, env vars, file paths, time helpers, cache, Anthropic client."""
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import json
import os
import re
import requests

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / '.env')

# ── Timezone ──────────────────────────────────────────────────
NY_TZ  = ZoneInfo('America/New_York')
UTC_TZ = ZoneInfo('UTC')

# ── File paths ────────────────────────────────────────────────
DATA_DIR           = BASE_DIR / 'data'
DATA_DIR.mkdir(exist_ok=True)

RISK_STATE_FILE    = DATA_DIR / 'donna_risk_state.json'
ALERTS_FILE        = DATA_DIR / 'donna_alert_history.json'
ASSISTANT_FILE     = DATA_DIR / 'donna_assistant_state.json'
SETTINGS_FILE      = DATA_DIR / 'donna_settings.json'
MACRO_EVENTS_FILE  = DATA_DIR / 'donna_macro_events.json'
MORNING_BRIEF_FILE = DATA_DIR / 'donna_morning_brief_state.json'
JOURNAL_FILE       = DATA_DIR / 'donna_journal.json'
REJECTIONS_FILE    = DATA_DIR / 'donna_rejections.json'
TRACE_FILE         = DATA_DIR / 'donna_execution_trace.json'

# ── API keys ──────────────────────────────────────────────────
ANTHROPIC_API_KEY       = os.getenv('ANTHROPIC_API_KEY', '').strip()
ANTHROPIC_MODEL         = os.getenv('ANTHROPIC_MODEL', 'claude-haiku-4-5-20251001').strip()
ANTHROPIC_ASSISTANT_MODEL = os.getenv('ANTHROPIC_ASSISTANT_MODEL', 'claude-sonnet-4-6').strip()
TELEGRAM_BOT_TOKEN       = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
TELEGRAM_CHAT_ID         = os.getenv('TELEGRAM_CHAT_ID', '').strip()
TELEGRAM_ALERT_MODE      = os.getenv('TELEGRAM_ALERT_MODE', 'critical').strip().lower()

# ── Discord (bot token + channel IDs) ────────────────────────
# One token, all channels. Add channel IDs as channels are created.
# All alerts fall back to DISCORD_CHANNEL_LIVE if specific channel not set.
DISCORD_BOT_TOKEN              = os.getenv('DISCORD_BOT_TOKEN', '').strip()
DISCORD_CHANNEL_LIVE           = os.getenv('DISCORD_CHANNEL_LIVE', '').strip()           # #nova-live  (primary, all alerts initially)
DISCORD_CHANNEL_HEADS_UP       = os.getenv('DISCORD_CHANNEL_HEADS_UP', '').strip()       # #heads-up
DISCORD_CHANNEL_MORNING_BRIEF  = os.getenv('DISCORD_CHANNEL_MORNING_BRIEF', '').strip()  # #morning-brief
DISCORD_CHANNEL_EXECUTION      = os.getenv('DISCORD_CHANNEL_EXECUTION', '').strip()      # #execution
DISCORD_CHANNEL_INVALIDATION   = os.getenv('DISCORD_CHANNEL_INVALIDATION', '').strip()   # #live-alerts (invalidations)
DISCORD_CHANNEL_NO_TRADE       = os.getenv('DISCORD_CHANNEL_NO_TRADE', '').strip()       # #macro-risk
DISCORD_CHANNEL_MACRO          = os.getenv('DISCORD_CHANNEL_MACRO', '').strip()          # #macro-risk
DISCORD_CHANNEL_LOGS           = os.getenv('DISCORD_CHANNEL_LOGS', '').strip()           # #logs
DISCORD_CHANNEL_SYSTEM_HEALTH  = os.getenv('DISCORD_CHANNEL_SYSTEM_HEALTH', '').strip()  # #system-health

# ── Alert engine ──────────────────────────────────────────────
ALERT_SCREENSHOT       = os.getenv('ALERT_SCREENSHOT', 'true').strip().lower() == 'true'
ALERT_COOLDOWN_MINUTES = int(os.getenv('ALERT_COOLDOWN_MINUTES', '15'))
ALERT_DAILY_MAX        = int(os.getenv('ALERT_DAILY_MAX', '20'))
ALERT_STATE_FILE       = DATA_DIR / 'donna_alert_state.json'

FINNHUB_API_KEY         = os.getenv('FINNHUB_API_KEY', '').strip()
FMP_API_KEY             = os.getenv('FMP_API_KEY', '').strip()
ALPHA_VANTAGE_API_KEY   = os.getenv('ALPHA_VANTAGE_API_KEY', '').strip()
FOREX_FACTORY_NOTES_URL = os.getenv('FOREX_FACTORY_NOTES_URL', '').strip()

# ── Anthropic client ──────────────────────────────────────────
try:
    from anthropic import Anthropic
    client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
except Exception:
    Anthropic = None  # type: ignore
    client = None

# ── In-memory cache ───────────────────────────────────────────
CACHE: dict = {}

# ── Default state values ──────────────────────────────────────
DEFAULT_RISK_STATE = {
    'macro_risk': 'medium',
    'headline_risk': 'medium',
    'market_news_risk': 'medium',
    'active_warnings': ['Macro timing matters today', 'Leadership concentration is elevated'],
    'next_event': '10:00 ET Data / Fed Window',
    'minutes_to_event': 45,
    'last_headline': 'Mega-cap leadership remains the main driver of Nasdaq strength.',
    'last_market_headline': 'Semis and mega-cap tech continue to control index direction.',
    'headline_guidance': 'Respect event timing and avoid treating a major NY session expansion like noise.',
    'headline_severity': 'MEDIUM',
    'last_market_guidance': 'Leadership names are doing most of the lifting. Watch NVDA, MSFT, AMZN, AMD.',
    'last_market_severity': 'HIGH',
    'event_phase': 'APPROACHING',
    'market_snapshot': {
        'SPX':               {'last': 7022.95, 'chg': 55.57,   'pct': 0.80},
        'NASDAQ':            {'last': 24016.01,'chg': 376.93,  'pct': 1.60},
        'DJIA':              {'last': 48463.72,'chg': -72.27,  'pct': -0.15},
        'VIX':               {'last': 18.17,   'chg': -0.19,   'pct': -1.03},
        'US10Y':             {'last': 4.281,   'chg': 0.025,   'pct': 0.59},
        'DXY':               {'last': 103.84,  'chg': -0.14,   'pct': -0.13},
        'NQ':                {'last': 0,       'chg': 0,       'pct': 0},
        'ES':                {'last': 0,       'chg': 0,       'pct': 0},
        'OIL':               {'last': 0,       'chg': 0,       'pct': 0},
        'GOLD':              {'last': 0,       'chg': 0,       'pct': 0},
        'SILVER':            {'last': 0,       'chg': 0,       'pct': 0},
        'NQ_SESSION_POINTS': 393.0,
        'ES_SESSION_POINTS': 49.5,
    },
}

DEFAULT_ASSISTANT_STATE = {
    'daily_focus': 'Trade what matters. Ignore noise.',
    'tasks': ['Review morning edge', 'Check likely market movers', 'Respect macro timing'],
    'reminders': ['Do not force trades into event windows', 'Leadership names deserve first attention'],
}

DEFAULT_SETTINGS = {
    'theme_mode': 'premium_dark',
    'layout_density': 'balanced',
    'telegram_alert_mode': TELEGRAM_ALERT_MODE or 'critical',
}

DEFAULT_MACRO_EVENTS = {
    'source': 'empty',
    'events': [],
    'note': 'Populate with actual scheduled events via ForexFactory/manual entry. No events = no red-folder block.',
}

# ── Time helpers ──────────────────────────────────────────────
def now_ny() -> datetime:
    return datetime.now(NY_TZ)


def now_utc() -> datetime:
    return datetime.now(UTC_TZ)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def day_name() -> str:
    return now_ny().strftime('%A')


def session_label(dt=None) -> str:
    dt = dt or now_ny()
    m = dt.hour * 60 + dt.minute
    if m >= 19 * 60 or m < 3 * 60:
        return 'ASIA'
    if 3 * 60 <= m < 9 * 60 + 30:
        return 'LONDON'
    if 9 * 60 + 30 <= m < 16 * 60:
        return 'NEW_YORK_CASH'
    return 'OFF_HOURS'


# ── Numeric helpers ───────────────────────────────────────────
def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


# ── Cache helpers ─────────────────────────────────────────────
def cache_get(key):
    v = CACHE.get(key)
    if not v:
        return None
    if datetime.now(timezone.utc).timestamp() > v['expires_at']:
        return None
    return v['value']


def cache_set(key, value, ttl):
    CACHE[key] = {'value': value, 'expires_at': datetime.now(timezone.utc).timestamp() + ttl}


# ── Telegram ──────────────────────────────────────────────────
def send_telegram_message(text: str) -> dict:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return {'ok': False, 'error': 'Telegram not configured'}
    try:
        r = requests.post(
            f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',
            json={'chat_id': TELEGRAM_CHAT_ID, 'text': text},
            timeout=20,
        )
        return r.json()
    except Exception as e:
        return {'ok': False, 'error': str(e)}


# ── HTTP helper ───────────────────────────────────────────────
def _requests_get_json(url, params=None):
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()
