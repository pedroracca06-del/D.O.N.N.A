"""donna_alert_engine.py — NOVA Phase 2E: Operational Alert Delivery System.

Primary delivery: Discord (bot token + channel IDs).
Secondary delivery: Telegram (fallback, text-only).

Architecture:
  TradingView → webhook → NOVA backend → governance → screenshot → Discord

Alert types:
  HEADS_UP        — setup forming before confirmation
  EXECUTION_READY — setup confirmed, ready to trade
  INVALIDATION    — setup invalidated, stand aside
  NO_TRADE        — session or behavioral block active
  SESSION_BRIEF   — morning/session intelligence brief

Channel routing (all fall back to DISCORD_CHANNEL_LIVE):
  HEADS_UP        → DISCORD_CHANNEL_HEADS_UP
  EXECUTION_READY → DISCORD_CHANNEL_EXECUTION
  INVALIDATION    → DISCORD_CHANNEL_INVALIDATION (or #live-alerts)
  NO_TRADE        → DISCORD_CHANNEL_NO_TRADE (or #macro-risk)
  SESSION_BRIEF   → DISCORD_CHANNEL_MORNING_BRIEF
"""
from __future__ import annotations

import json
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

# ── Config ─────────────────────────────────────────────────────────────────────

_BASE_DIR   = Path(__file__).parent
_MCP_DIR    = _BASE_DIR / 'mcp' / 'tradingview'
_SS_DIR     = _MCP_DIR / 'screenshots'
_STATE_FILE = _BASE_DIR / 'data' / 'donna_alert_state.json'
_DISCORD_API = 'https://discord.com/api/v10'

try:
    from donna_config import (
        DISCORD_BOT_TOKEN,
        DISCORD_CHANNEL_LIVE,
        DISCORD_CHANNEL_HEADS_UP,
        DISCORD_CHANNEL_MORNING_BRIEF,
        DISCORD_CHANNEL_EXECUTION,
        DISCORD_CHANNEL_INVALIDATION,
        DISCORD_CHANNEL_NO_TRADE,
        TELEGRAM_BOT_TOKEN,
        TELEGRAM_CHAT_ID,
        ALERT_SCREENSHOT,
        ALERT_COOLDOWN_MINUTES,
        ALERT_DAILY_MAX,
        now_ny,
    )
except ImportError:
    DISCORD_BOT_TOKEN             = ''
    DISCORD_CHANNEL_LIVE          = ''
    DISCORD_CHANNEL_HEADS_UP      = ''
    DISCORD_CHANNEL_MORNING_BRIEF = ''
    DISCORD_CHANNEL_EXECUTION     = ''
    DISCORD_CHANNEL_INVALIDATION  = ''
    DISCORD_CHANNEL_NO_TRADE      = ''
    TELEGRAM_BOT_TOKEN            = ''
    TELEGRAM_CHAT_ID              = ''
    ALERT_SCREENSHOT              = True
    ALERT_COOLDOWN_MINUTES        = 15
    ALERT_DAILY_MAX               = 20
    def now_ny():
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo('America/New_York'))

# ── Alert type constants ───────────────────────────────────────────────────────

HEADS_UP        = 'HEADS_UP'
EXECUTION_READY = 'EXECUTION_READY'
INVALIDATION    = 'INVALIDATION'
NO_TRADE        = 'NO_TRADE'
SESSION_BRIEF   = 'SESSION_BRIEF'

# Discord embed colors
_COLORS = {
    HEADS_UP:        0x00C851,   # green   — forming
    EXECUTION_READY: 0x0080FF,   # blue    — ready
    INVALIDATION:    0xFF4444,   # red     — broken
    NO_TRADE:        0xFFBB33,   # amber   — caution
    SESSION_BRIEF:   0x9B59B6,   # purple  — brief
}

# Cooldown per type (minutes)
_COOLDOWNS = {
    HEADS_UP:        15,
    EXECUTION_READY: 30,
    INVALIDATION:    5,
    NO_TRADE:        20,
    SESSION_BRIEF:   120,
}

# Channel routing: alert type → env var channel ID → fallback to LIVE
_CHANNEL_MAP = {
    HEADS_UP:        lambda: DISCORD_CHANNEL_HEADS_UP      or DISCORD_CHANNEL_LIVE,
    EXECUTION_READY: lambda: DISCORD_CHANNEL_EXECUTION     or DISCORD_CHANNEL_LIVE,
    INVALIDATION:    lambda: DISCORD_CHANNEL_INVALIDATION  or DISCORD_CHANNEL_LIVE,
    NO_TRADE:        lambda: DISCORD_CHANNEL_NO_TRADE      or DISCORD_CHANNEL_LIVE,
    SESSION_BRIEF:   lambda: DISCORD_CHANNEL_MORNING_BRIEF or DISCORD_CHANNEL_LIVE,
}

# ── Data model ─────────────────────────────────────────────────────────────────

@dataclass
class AlertData:
    alert_type:       str
    symbol:           str
    setup_type:       str          # "PROS_LONG" | "ORB_E1_SHORT" | etc.
    direction:        str          # "LONG" | "SHORT" | "N/A"
    priority:         str = 'standard'

    # Market context
    session:          str = 'NY_OPEN'
    session_quality:  str = '?'
    ib_draw:          str = '?'
    daily_bias:       str = '?'
    htf_4h_bias:      str = '?'
    grade:            str = '?'

    # Price levels (execution alerts)
    entry_zone:       str = ''
    stop:             str = ''
    tp1:              str = ''
    rr:               str = ''

    # Heads-up specifics
    timeframe:        str = ''        # "30M PROS"
    time_to_close:    str = ''        # "3 min to close"
    watch_time:       str = ''        # "Watch for confirmation at 10:00 AM ET"

    # Invalidation / no-trade
    reason:           str = ''
    action:           str = ''

    # Free notes
    notes:            str = ''

    @property
    def signal_key(self) -> str:
        return f'{self.symbol}_{self.setup_type}_{self.direction}'.upper()


# ── Embed formatting ────────────────────────────────────────────────────────────

def _bias_icon(val: str) -> str:
    v = val.upper()
    if any(x in v for x in ('BULL', 'LONG', 'HIGH', 'UP', 'GREEN')):
        return '🟢'
    if any(x in v for x in ('BEAR', 'SHORT', 'LOW', 'DOWN', 'RED')):
        return '🔴'
    if v in ('A',):
        return '🟢'
    if v in ('B',):
        return '🟡'
    if v in ('C', 'D'):
        return '🔴'
    return '🟡'


def _field(name: str, value: str, inline: bool = True) -> dict:
    return {'name': name, 'value': value or '—', 'inline': inline}


def _spacer() -> dict:
    return {'name': '​', 'value': '​', 'inline': False}


def _build_heads_up_embed(d: AlertData) -> dict:
    title = f'🟢  HEADS UP — {d.symbol} {d.direction} FORMING'

    desc_parts = []
    if d.timeframe:
        line = d.timeframe
        if d.time_to_close:
            line += f' — {d.time_to_close}'
        desc_parts.append(line)
    description = '\n'.join(desc_parts)

    fields = [
        _field('Daily',            f'{_bias_icon(d.daily_bias)} {d.daily_bias}'),
        _field('4H',               f'{_bias_icon(d.htf_4h_bias)} {d.htf_4h_bias}'),
        _field('IB Draw',          f'{_bias_icon(d.ib_draw)} {d.ib_draw}'),
        _field('Session Quality',  f'{_bias_icon(d.session_quality)} {d.session_quality}'),
    ]
    if d.grade and d.grade != '?':
        fields.append(_field('Setup Grade', f'{_bias_icon(d.grade)} {d.grade}'))
    fields.append(_field('Session', d.session))
    if d.watch_time:
        fields.append(_spacer())
        fields.append(_field('⏱', d.watch_time, inline=False))
    if d.notes:
        fields.append(_field('Note', d.notes, inline=False))

    return {'title': title, 'description': description, 'fields': fields,
            'color': _COLORS[HEADS_UP]}


def _build_execution_embed(d: AlertData) -> dict:
    title = f'⚡  {d.setup_type.replace("_", " ")} READY — {d.symbol}'
    description = ''

    fields = []
    if d.entry_zone:
        fields.append(_field('Entry Zone', d.entry_zone, inline=False))
    if d.stop:
        fields.append(_field('Stop', d.stop, inline=False))
    if d.tp1:
        fields.append(_field('TP1', f'{d.tp1}  ·  IB level — hold if volume strong', inline=False))
    if d.rr:
        fields.append(_field('R:R', f'{d.rr}  →  hold for 3–4:1 if momentum intact', inline=False))
    fields.append(_spacer())
    fields.append(_field('Grade',    f'{_bias_icon(d.grade)} {d.grade}'))
    fields.append(_field('Session',  d.session))
    fields.append(_field('IB Draw',  f'{_bias_icon(d.ib_draw)} {d.ib_draw}'))
    fields.append(_field('Quality',  f'{_bias_icon(d.session_quality)} {d.session_quality}'))
    if d.notes:
        fields.append(_spacer())
        fields.append(_field('Note', d.notes, inline=False))

    return {'title': title, 'description': description, 'fields': fields,
            'color': _COLORS[EXECUTION_READY]}


def _build_invalidation_embed(d: AlertData) -> dict:
    title = f'🔴  SETUP INVALIDATED — {d.symbol} {d.direction}'
    description = d.reason or ''

    action = d.action or 'Stand aside. No re-entry until a fresh setup forms.'
    fields = [_field('Action', action, inline=False)]
    if d.setup_type and d.setup_type != '?':
        was = d.setup_type.replace('_', ' ')
        if d.grade and d.grade != '?':
            was += f'  ·  Grade {d.grade}'
        fields.append(_field('Setup was', was, inline=False))
    if d.notes:
        fields.append(_field('Note', d.notes, inline=False))

    return {'title': title, 'description': description, 'fields': fields,
            'color': _COLORS[INVALIDATION]}


def _build_no_trade_embed(d: AlertData) -> dict:
    sym   = d.symbol if d.symbol and d.symbol not in ('N/A', '?', '') else 'SESSION'
    title = f'⛔  NO TRADE — {sym}'
    description = d.reason or ''

    fields = []
    if d.session_quality and d.session_quality != '?':
        fields.append(_field('Session Quality', f'{_bias_icon(d.session_quality)} {d.session_quality}'))
    if d.session:
        fields.append(_field('Session', d.session))
    action = d.action or 'Stand aside. Wait for next valid session.'
    fields.append(_spacer())
    fields.append(_field('Action', action, inline=False))
    if d.notes:
        fields.append(_field('Note', d.notes, inline=False))

    return {'title': title, 'description': description, 'fields': fields,
            'color': _COLORS[NO_TRADE]}


def _build_brief_embed(d: AlertData) -> dict:
    title = f'📋  NOVA MORNING BRIEF — {d.symbol}'
    description = d.notes or ''
    fields = []
    if d.session_quality and d.session_quality != '?':
        fields.append(_field('Session Quality', f'{_bias_icon(d.session_quality)} {d.session_quality}'))
    if d.ib_draw and d.ib_draw != '?':
        fields.append(_field('IB Draw', f'{_bias_icon(d.ib_draw)} {d.ib_draw}'))
    if d.daily_bias and d.daily_bias != '?':
        fields.append(_field('Daily Bias', f'{_bias_icon(d.daily_bias)} {d.daily_bias}'))
    return {'title': title, 'description': description, 'fields': fields,
            'color': _COLORS[SESSION_BRIEF]}


_EMBED_BUILDERS = {
    HEADS_UP:        _build_heads_up_embed,
    EXECUTION_READY: _build_execution_embed,
    INVALIDATION:    _build_invalidation_embed,
    NO_TRADE:        _build_no_trade_embed,
    SESSION_BRIEF:   _build_brief_embed,
}


def build_embed(d: AlertData) -> dict:
    builder = _EMBED_BUILDERS.get(d.alert_type, _build_no_trade_embed)
    embed = builder(d)
    embed['footer'] = {'text': f'NOVA  ·  {now_ny().strftime("%H:%M ET")}  ·  {d.symbol}'}
    embed['timestamp'] = datetime.now(timezone.utc).isoformat()
    return embed


def embed_to_text(embed: dict) -> str:
    """Convert a Discord embed to flat text (Telegram fallback)."""
    lines = [embed.get('title', '')]
    if embed.get('description'):
        lines.append(embed['description'])
    lines.append('')
    for f in embed.get('fields', []):
        name  = f.get('name', '')
        value = f.get('value', '')
        if name == '​':
            continue
        if name:
            lines.append(f'{name}: {value}')
        else:
            lines.append(value)
    return '\n'.join(lines).strip()


# ── Anti-spam governance ────────────────────────────────────────────────────────

_gov_lock = threading.Lock()


def _load_alert_state() -> dict:
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text())
        except Exception:
            pass
    return {'signals': {}, 'daily_total': 0, 'daily_date': '', 'suppressed_today': 0}


def _save_alert_state(state: dict) -> None:
    try:
        _STATE_FILE.write_text(json.dumps(state, indent=2))
    except Exception:
        pass


def _today_et() -> str:
    return now_ny().strftime('%Y-%m-%d')


def _reset_daily_if_needed(state: dict) -> dict:
    today = _today_et()
    if state.get('daily_date') != today:
        state.update({'daily_total': 0, 'suppressed_today': 0,
                      'daily_date': today, 'signals': {}})
    return state


def can_deliver(signal_key: str, alert_type: str) -> tuple[bool, str]:
    with _gov_lock:
        state = _reset_daily_if_needed(_load_alert_state())

        if state['daily_total'] >= ALERT_DAILY_MAX:
            return False, f'Daily cap reached ({ALERT_DAILY_MAX})'

        sig = state['signals'].get(signal_key, {})
        last_time_str = sig.get('last_delivery_time', '')
        if last_time_str and sig.get('last_type') == alert_type:
            try:
                last_time = datetime.fromisoformat(last_time_str)
                cooldown  = _COOLDOWNS.get(alert_type, ALERT_COOLDOWN_MINUTES)
                elapsed   = (datetime.now(timezone.utc) - last_time).total_seconds() / 60
                if elapsed < cooldown:
                    remaining = int(cooldown - elapsed)
                    return False, f'Cooldown active ({remaining}min remaining)'
            except Exception:
                pass

        return True, 'ok'


def record_delivery(signal_key: str, alert_type: str) -> None:
    with _gov_lock:
        state = _reset_daily_if_needed(_load_alert_state())
        state['signals'][signal_key] = {
            'last_type':          alert_type,
            'last_delivery_time': datetime.now(timezone.utc).isoformat(),
        }
        state['daily_total'] += 1
        _save_alert_state(state)


def record_suppression() -> None:
    with _gov_lock:
        state = _reset_daily_if_needed(_load_alert_state())
        state['suppressed_today'] = state.get('suppressed_today', 0) + 1
        _save_alert_state(state)


def clear_signal(signal_key: str) -> None:
    """Remove signal from governance (e.g. after invalidation — fresh start next setup)."""
    with _gov_lock:
        state = _load_alert_state()
        state['signals'].pop(signal_key, None)
        _save_alert_state(state)


# ── Screenshot pipeline ─────────────────────────────────────────────────────────

def capture_screenshot() -> Optional[Path]:
    """Capture TradingView chart via MCP CLI. Returns path or None."""
    if not ALERT_SCREENSHOT:
        return None
    try:
        result = subprocess.run(
            ['node', 'src/cli/index.js', 'screenshot', '--region', 'chart'],
            cwd=str(_MCP_DIR),
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            try:
                data     = json.loads(result.stdout.strip())
                path_str = data.get('file_path') or data.get('path') or data.get('file') or data.get('screenshot')
                if path_str:
                    p = Path(path_str)
                    if not p.is_absolute():
                        p = _MCP_DIR / path_str
                    if p.exists():
                        return p
            except Exception:
                pass
        # Fallback: most recent screenshot
        if _SS_DIR.exists():
            shots = sorted(_SS_DIR.glob('*.png'), key=lambda f: f.stat().st_mtime, reverse=True)
            if shots:
                return shots[0]
    except Exception:
        pass
    return None


# ── Discord delivery (bot token + REST API) ─────────────────────────────────────

def _discord_headers() -> dict:
    return {'Authorization': f'Bot {DISCORD_BOT_TOKEN}'}


def _resolve_channel(alert_type: str) -> str:
    resolver = _CHANNEL_MAP.get(alert_type, lambda: DISCORD_CHANNEL_LIVE)
    return resolver()


def send_discord(data: AlertData, photo: Optional[Path] = None) -> dict:
    """Deliver a rich embed to the appropriate Discord channel via bot REST API."""
    if not DISCORD_BOT_TOKEN:
        return {'ok': False, 'error': 'DISCORD_BOT_TOKEN not configured'}

    channel_id = _resolve_channel(data.alert_type)
    if not channel_id:
        return {'ok': False, 'error': 'No Discord channel configured — set DISCORD_CHANNEL_LIVE in .env'}

    url   = f'{_DISCORD_API}/channels/{channel_id}/messages'
    embed = build_embed(data)

    try:
        if photo and photo.exists():
            embed['image'] = {'url': 'attachment://chart.png'}
            payload = json.dumps({'embeds': [embed]})
            with open(photo, 'rb') as f:
                r = requests.post(
                    url,
                    headers=_discord_headers(),
                    data={'payload_json': payload},
                    files={'files[0]': ('chart.png', f, 'image/png')},
                    timeout=20,
                )
        else:
            r = requests.post(
                url,
                headers={**_discord_headers(), 'Content-Type': 'application/json'},
                json={'embeds': [embed]},
                timeout=20,
            )

        if r.status_code in (200, 201):
            return {'ok': True, 'channel_id': channel_id}
        return {'ok': False, 'status': r.status_code, 'error': r.text[:300]}

    except Exception as e:
        return {'ok': False, 'error': str(e)}


# ── Telegram delivery (secondary / fallback) ────────────────────────────────────

def send_telegram(data: AlertData, photo: Optional[Path] = None) -> dict:
    """Deliver alert to Telegram as flat text (photo if available)."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return {'ok': False, 'error': 'Telegram not configured'}

    embed = build_embed(data)
    text  = embed_to_text(embed)

    try:
        if photo and photo.exists():
            caption = text[:1024]
            with open(photo, 'rb') as f:
                r = requests.post(
                    f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto',
                    data={'chat_id': TELEGRAM_CHAT_ID, 'caption': caption},
                    files={'photo': ('chart.png', f, 'image/png')},
                    timeout=20,
                )
            # Send overflow text if caption was truncated
            if len(text) > 1024:
                requests.post(
                    f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',
                    json={'chat_id': TELEGRAM_CHAT_ID, 'text': text[1024:]},
                    timeout=20,
                )
        else:
            r = requests.post(
                f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',
                json={'chat_id': TELEGRAM_CHAT_ID, 'text': text},
                timeout=20,
            )
        return r.json()
    except Exception as e:
        return {'ok': False, 'error': str(e)}


# ── Main entry point ────────────────────────────────────────────────────────────

def deliver_alert(data: AlertData, with_screenshot: bool = True) -> dict:
    """
    Deliver a NOVA alert. Discord is primary; Telegram is secondary.

    1. Governance check (cooldown, daily cap, dedup)
    2. Screenshot capture
    3. Discord delivery (primary)
    4. Telegram delivery (secondary, does not block on Discord failure)
    5. Record delivery / suppression
    """
    allowed, reason = can_deliver(data.signal_key, data.alert_type)
    if not allowed:
        record_suppression()
        return {'delivered': False, 'suppressed': True, 'reason': reason}

    photo = capture_screenshot() if (with_screenshot and ALERT_SCREENSHOT) else None

    discord_result  = send_discord(data, photo)
    telegram_result = send_telegram(data, photo)

    any_ok = discord_result.get('ok') or telegram_result.get('ok')
    if any_ok:
        record_delivery(data.signal_key, data.alert_type)
        if data.alert_type == INVALIDATION:
            clear_signal(data.signal_key)

    return {
        'delivered': any_ok,
        'discord':   discord_result,
        'telegram':  telegram_result,
        'photo':     str(photo) if photo else None,
    }


# ── Setup monitor (background forming-alert engine) ────────────────────────────

def _in_trading_window() -> bool:
    now = now_ny()
    minutes = now.hour * 60 + now.minute
    return 9 * 60 + 30 <= minutes <= 11 * 60


def _read_chart_state() -> Optional[dict]:
    try:
        r = subprocess.run(
            ['node', 'src/cli/index.js', 'state'],
            cwd=str(_MCP_DIR), capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            return json.loads(r.stdout)
    except Exception:
        pass
    return None


def _read_ohlcv(count: int = 30) -> Optional[dict]:
    try:
        r = subprocess.run(
            ['node', 'src/cli/index.js', 'ohlcv', '--count', str(count), '--summary'],
            cwd=str(_MCP_DIR), capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            return json.loads(r.stdout)
    except Exception:
        pass
    return None


def check_forming_setups() -> list[AlertData]:
    """
    Poll chart via NOVA reasoning engine. Returns AlertData for any forming setups.
    Delegates to donna_nova_reasoning.run_reasoning_cycle() for full Claude evaluation.
    """
    try:
        from donna_nova_reasoning import run_reasoning_cycle
        return run_reasoning_cycle()
    except Exception:
        pass
    # Fallback: basic MCP check without Claude
    if not _in_trading_window():
        return []
    chart = _read_chart_state()
    if not chart or not chart.get('success'):
        return []
    return []


_monitor_running = False
_monitor_thread: Optional[threading.Thread] = None


def start_setup_monitor(interval_seconds: int = 60) -> None:
    """Start background setup monitor. Polls chart and delivers heads-up alerts."""
    global _monitor_running, _monitor_thread
    if _monitor_running:
        return

    def _loop():
        global _monitor_running
        _monitor_running = True
        while _monitor_running:
            try:
                for alert_data in check_forming_setups():
                    deliver_alert(alert_data, with_screenshot=True)
            except Exception:
                pass
            time.sleep(interval_seconds)

    _monitor_thread = threading.Thread(target=_loop, daemon=True, name='nova-setup-monitor')
    _monitor_thread.start()


def stop_setup_monitor() -> None:
    global _monitor_running
    _monitor_running = False


# ── Status ─────────────────────────────────────────────────────────────────────

def get_alert_status() -> dict:
    state = _reset_daily_if_needed(_load_alert_state())
    channel_live = DISCORD_CHANNEL_LIVE
    return {
        'daily_total':          state.get('daily_total', 0),
        'daily_max':            ALERT_DAILY_MAX,
        'suppressed_today':     state.get('suppressed_today', 0),
        'active_signals':       len(state.get('signals', {})),
        'monitor_running':      _monitor_running,
        'discord_configured':   bool(DISCORD_BOT_TOKEN and channel_live),
        'discord_channel_live': channel_live or 'not set',
        'telegram_configured':  bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
        'screenshot_enabled':   ALERT_SCREENSHOT,
    }
