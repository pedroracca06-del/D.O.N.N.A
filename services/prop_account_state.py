"""prop_account_state.py — Execution Bot v2 Phase 6: Prop account state tracking.

Tracks account balance, high-water mark, trailing drawdown, daily P&L, and
prop rule breach risk. Reads broker account via Alpaca (read-only).

State file: nova_prop_account_state.json (auto-created with zero defaults).
Config inputs (account_size, limits) are loaded from nova_prop_risk_config.json
written by Phase 2; this module ONLY writes the runtime state file.

SAFETY CONTRACT — this module MUST NEVER:
  - Submit orders
  - Cancel orders
  - Modify positions
  - Call any Alpaca write endpoint

Public API:
    load_prop_account_state() -> dict
    save_prop_account_state(state) -> None
    update_prop_account_state_from_broker() -> dict       — main entry
    compute_trailing_drawdown_state(state) -> dict        — pure
    compute_daily_loss_state(state) -> dict               — pure
    compute_total_loss_state(state) -> dict               — pure
    reset_daily_state_if_new_day(state) -> dict           — returns updated state
    get_prop_breach_alerts(state) -> list                 — alert dicts (no I/O)
    check_and_send_prop_alerts(state, cooldown_s) -> dict — send + cooldown
    send_prop_alert_discord(alert, state) -> dict         — Discord only, no broker writes
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

_NY_TZ = ZoneInfo('America/New_York')

# ── Status constants ───────────────────────────────────────────────────────────

PROP_STATE_OK                    = 'PROP_STATE_OK'
PROP_DAILY_LOSS_WARNING          = 'PROP_DAILY_LOSS_WARNING'
PROP_DAILY_LOSS_BREACHED         = 'PROP_DAILY_LOSS_BREACHED'
PROP_TOTAL_LOSS_WARNING          = 'PROP_TOTAL_LOSS_WARNING'
PROP_TOTAL_LOSS_BREACHED         = 'PROP_TOTAL_LOSS_BREACHED'
PROP_TRAILING_DRAWDOWN_WARNING   = 'PROP_TRAILING_DRAWDOWN_WARNING'
PROP_TRAILING_DRAWDOWN_BREACHED  = 'PROP_TRAILING_DRAWDOWN_BREACHED'
UNKNOWN_ACCOUNT_STATE            = 'UNKNOWN_ACCOUNT_STATE'

# Priority (higher = worse; used to pick worst status)
_STATUS_SEVERITY: dict[str, int] = {
    PROP_STATE_OK:                   0,
    PROP_DAILY_LOSS_WARNING:         1,
    PROP_TOTAL_LOSS_WARNING:         2,
    PROP_TRAILING_DRAWDOWN_WARNING:  3,
    PROP_DAILY_LOSS_BREACHED:        4,
    PROP_TOTAL_LOSS_BREACHED:        5,
    PROP_TRAILING_DRAWDOWN_BREACHED: 6,
    UNKNOWN_ACCOUNT_STATE:           7,
}

WARNING_BUFFER_PCT = 0.25   # alert when ≤ 25% of the buffer remains

ALERT_COOLDOWN_SECONDS = 300  # 5 min per alert key

# ── File paths ─────────────────────────────────────────────────────────────────

def _prop_account_state_file() -> Path:
    try:
        from core.config import DATA_DIR
        return DATA_DIR / 'nova_prop_account_state.json'
    except Exception:
        return Path('data') / 'nova_prop_account_state.json'


# ── Default state ──────────────────────────────────────────────────────────────

def _default_state() -> dict:
    return {
        # ── Static configuration (user-editable in the file) ─────────────────
        'prop_firm_name':            '',
        'account_size':              0.0,
        'starting_balance':          0.0,
        'trailing_drawdown_enabled': False,
        'trailing_drawdown_amount':  0.0,
        'trailing_drawdown_floor':   0.0,   # absolute floor level (0 = not configured)
        'trailing_drawdown_type':    'trailing',   # 'trailing' | 'static'
        'max_daily_loss':            0.0,
        'max_total_loss':            0.0,
        # ── Dynamic (updated by update_prop_account_state_from_broker) ────────
        'current_balance':           0.0,
        'previous_balance':          0.0,
        'high_water_mark':           0.0,
        'daily_start_balance':       0.0,
        'daily_pnl':                 0.0,
        'daily_loss_remaining':      None,
        'total_loss_remaining':      None,
        'trailing_drawdown_threshold': None,
        'trailing_drawdown_remaining': None,
        'trailing_drawdown_status':  PROP_STATE_OK,
        'daily_loss_status':         PROP_STATE_OK,
        'total_loss_status':         PROP_STATE_OK,
        'trading_day':               '',
        'trade_count_today':         0,
        'last_updated':              '',
        # ── Overall status ────────────────────────────────────────────────────
        'prop_state_status':         UNKNOWN_ACCOUNT_STATE,
        'broker_account_read':       False,
    }


# ── File I/O ──────────────────────────────────────────────────────────────────

def load_prop_account_state() -> dict:
    """Load state file, merging with defaults so new fields are always present."""
    base = _default_state()
    p = _prop_account_state_file()
    if p.exists():
        try:
            saved = json.loads(p.read_text(encoding='utf-8'))
            if isinstance(saved, dict):
                base.update(saved)
        except Exception:
            pass
    return base


def save_prop_account_state(state: dict) -> None:
    try:
        _prop_account_state_file().write_text(
            json.dumps(state, indent=2), encoding='utf-8'
        )
    except Exception:
        pass


# ── Alpaca account reader (read-only) ─────────────────────────────────────────

def _to_float(raw: dict, key: str, default: float = 0.0) -> float:
    v = raw.get(key)
    if v is None:
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def _get_alpaca_account_safe() -> dict | None:
    """
    Read Alpaca account via the shared client. Returns normalized dict or None.
    SAFETY: calls get_account() only — no write endpoints.
    """
    try:
        from services.execution_reconcile import _get_alpaca_client
        client, err = _get_alpaca_client()
        if client is None:
            return None
        account = client.get_account()
        raw: dict = {}
        for method in ('model_dump', 'dict'):
            try:
                raw = getattr(account, method)()
                break
            except AttributeError:
                pass
        if not raw:
            try:
                raw = vars(account)
            except TypeError:
                pass
        return {
            'equity':          _to_float(raw, 'equity'),
            'last_equity':     _to_float(raw, 'last_equity'),
            'portfolio_value': _to_float(raw, 'portfolio_value'),
            'buying_power':    _to_float(raw, 'buying_power'),
            'raw':             raw,
        }
    except Exception:
        return None


# ── Daily reset ───────────────────────────────────────────────────────────────

def _today_et() -> str:
    return datetime.now(_NY_TZ).strftime('%Y-%m-%d')


def reset_daily_state_if_new_day(state: dict) -> dict:
    """
    If the stored trading_day differs from today (ET), reset daily counters.
    Returns the (possibly updated) state. Does not save — caller saves.
    """
    today = _today_et()
    if state.get('trading_day') == today:
        return state
    state = dict(state)   # shallow copy — don't mutate input
    current = state.get('current_balance', 0.0) or 0.0
    state['daily_start_balance'] = current
    state['daily_pnl']           = 0.0
    state['daily_loss_remaining'] = None
    state['trade_count_today']   = 0
    state['trading_day']         = today
    return state


# ── Pure computation functions ────────────────────────────────────────────────

def compute_trailing_drawdown_state(state: dict) -> dict:
    """
    Pure function. Compute trailing drawdown threshold + remaining + status.

    trailing_drawdown_type='trailing': threshold = hwm - trailing_drawdown_amount
    trailing_drawdown_type='static':   threshold = starting_balance - trailing_drawdown_amount

    Returns dict with: trailing_drawdown_threshold, trailing_drawdown_remaining,
                       trailing_drawdown_status
    """
    enabled   = bool(state.get('trailing_drawdown_enabled'))
    dd_amount = float(state.get('trailing_drawdown_amount') or 0)
    dd_type   = str(state.get('trailing_drawdown_type') or 'trailing').lower()
    hwm       = float(state.get('high_water_mark') or 0)
    start_bal = float(state.get('starting_balance') or 0)
    current   = float(state.get('current_balance') or 0)

    if not enabled or dd_amount <= 0:
        return {
            'trailing_drawdown_threshold': None,
            'trailing_drawdown_remaining': None,
            'trailing_drawdown_status':    PROP_STATE_OK,
        }

    if dd_type == 'static':
        threshold = start_bal - dd_amount
    else:
        threshold = hwm - dd_amount

    remaining = current - threshold

    if remaining <= 0:
        status = PROP_TRAILING_DRAWDOWN_BREACHED
    elif dd_amount > 0 and remaining <= dd_amount * WARNING_BUFFER_PCT:
        status = PROP_TRAILING_DRAWDOWN_WARNING
    else:
        status = PROP_STATE_OK

    return {
        'trailing_drawdown_threshold': round(threshold, 2),
        'trailing_drawdown_remaining': round(remaining, 2),
        'trailing_drawdown_status':    status,
    }


def compute_daily_loss_state(state: dict) -> dict:
    """
    Pure function. Compute daily loss remaining + status.

    daily_pnl is negative when losing.
    daily_loss_remaining = max_daily_loss + daily_pnl
    Positive = room left; zero/negative = breached.
    """
    max_dl  = float(state.get('max_daily_loss') or 0)
    daily_pnl = float(state.get('daily_pnl') or 0)

    if max_dl <= 0:
        return {
            'daily_loss_remaining': None,
            'daily_loss_status':    PROP_STATE_OK,
        }

    remaining = max_dl + daily_pnl   # daily_pnl is negative when losing

    if remaining <= 0:
        status = PROP_DAILY_LOSS_BREACHED
    elif max_dl > 0 and remaining <= max_dl * WARNING_BUFFER_PCT:
        status = PROP_DAILY_LOSS_WARNING
    else:
        status = PROP_STATE_OK

    return {
        'daily_loss_remaining': round(remaining, 2),
        'daily_loss_status':    status,
    }


def compute_total_loss_state(state: dict) -> dict:
    """
    Pure function. Compute total (static max) loss remaining + status.
    Based on max_total_loss and starting_balance (not trailing DD).
    """
    max_tl    = float(state.get('max_total_loss') or 0)
    start_bal = float(state.get('starting_balance') or 0)
    current   = float(state.get('current_balance') or 0)

    if max_tl <= 0 or start_bal <= 0:
        return {
            'total_loss_remaining': None,
            'total_loss_status':    PROP_STATE_OK,
        }

    floor     = start_bal - max_tl
    remaining = current - floor

    if remaining <= 0:
        status = PROP_TOTAL_LOSS_BREACHED
    elif max_tl > 0 and remaining <= max_tl * WARNING_BUFFER_PCT:
        status = PROP_TOTAL_LOSS_WARNING
    else:
        status = PROP_STATE_OK

    return {
        'total_loss_remaining': round(remaining, 2),
        'total_loss_status':    status,
    }


def _worst_status(*statuses: str) -> str:
    """Return the highest-severity status from the given set."""
    return max(statuses, key=lambda s: _STATUS_SEVERITY.get(s, 0))


# ── Main updater ──────────────────────────────────────────────────────────────

def update_prop_account_state_from_broker() -> dict:
    """
    Full prop account state update:
      1. Load saved state
      2. Daily reset if new ET trading day
      3. Read Alpaca account (equity)
      4. Update current_balance, previous_balance, high_water_mark, daily_pnl
      5. Compute trailing drawdown / daily loss / total loss states
      6. Determine worst prop_state_status
      7. Save + return

    SAFETY CONTRACT: calls get_account() (read-only) only.
    """
    state = load_prop_account_state()
    state = reset_daily_state_if_new_day(state)

    broker_read = False
    account = _get_alpaca_account_safe()
    if account is not None:
        current = account.get('equity', 0.0) or 0.0
        state['previous_balance'] = state.get('current_balance', current)
        state['current_balance']  = current

        # HWM: never decreases
        hwm = float(state.get('high_water_mark') or 0)
        if current > hwm:
            state['high_water_mark'] = current

        # Initialise starting_balance from account_size if not set
        if not state.get('starting_balance'):
            state['starting_balance'] = float(state.get('account_size') or current)

        # Initialise daily_start_balance if not set for today
        if not state.get('daily_start_balance'):
            state['daily_start_balance'] = current

        daily_start = float(state.get('daily_start_balance') or current)
        state['daily_pnl'] = round(current - daily_start, 2)
        broker_read = True

    # Compute derived states
    dd_state = compute_trailing_drawdown_state(state)
    dl_state = compute_daily_loss_state(state)
    tl_state = compute_total_loss_state(state)

    state.update(dd_state)
    state.update(dl_state)
    state.update(tl_state)

    # Overall worst status
    individual = [
        dd_state.get('trailing_drawdown_status', PROP_STATE_OK),
        dl_state.get('daily_loss_status',        PROP_STATE_OK),
        tl_state.get('total_loss_status',        PROP_STATE_OK),
    ]
    if broker_read:
        state['prop_state_status'] = _worst_status(*individual)
    else:
        state['prop_state_status'] = UNKNOWN_ACCOUNT_STATE

    state['broker_account_read'] = broker_read
    state['last_updated']        = datetime.now(timezone.utc).isoformat()

    save_prop_account_state(state)
    return state


# ── Prop alert cooldown ───────────────────────────────────────────────────────

_prop_cooldown:      dict[str, str] = {}
_prop_cooldown_lock = threading.Lock()


def _is_prop_in_cooldown(alert_key: str, cooldown_seconds: int = ALERT_COOLDOWN_SECONDS) -> bool:
    if cooldown_seconds <= 0:
        return False
    with _prop_cooldown_lock:
        last_str = _prop_cooldown.get(alert_key)
    if not last_str:
        return False
    try:
        elapsed = (datetime.now(timezone.utc) -
                   datetime.fromisoformat(last_str)).total_seconds()
        return elapsed < cooldown_seconds
    except Exception:
        return False


def _record_prop_alert_sent(alert_key: str) -> None:
    with _prop_cooldown_lock:
        _prop_cooldown[alert_key] = datetime.now(timezone.utc).isoformat()


def clear_prop_cooldown_state() -> None:
    """Reset all prop alert cooldowns (for testing)."""
    with _prop_cooldown_lock:
        _prop_cooldown.clear()


# ── Alert generation ──────────────────────────────────────────────────────────

def get_prop_breach_alerts(state: dict) -> list:
    """
    Return a list of alert dicts for any prop rule at WARNING or BREACHED level.
    Pure function — no I/O, no cooldown check.
    """
    alerts = []
    checks = [
        ('trailing_drawdown', 'trailing_drawdown_status'),
        ('daily_loss',        'daily_loss_status'),
        ('total_loss',        'total_loss_status'),
    ]
    for dim, status_key in checks:
        status = state.get(status_key, PROP_STATE_OK)
        if status == PROP_STATE_OK or not status:
            continue
        severity = 'CRITICAL' if 'BREACHED' in status else 'WARNING'
        alerts.append({
            'alert_type':   status,
            'alert_key':    status,
            'severity':     severity,
            'dimension':    dim,
            'message':      _prop_alert_message(dim, status, state),
        })
    return alerts


def _prop_alert_message(dim: str, status: str, state: dict) -> str:
    current  = state.get('current_balance', '?')
    if dim == 'trailing_drawdown':
        threshold  = state.get('trailing_drawdown_threshold', '?')
        remaining  = state.get('trailing_drawdown_remaining', '?')
        return (
            f'Trailing drawdown {status}: current=${current}, '
            f'threshold=${threshold}, remaining=${remaining}'
        )
    elif dim == 'daily_loss':
        daily_pnl  = state.get('daily_pnl', '?')
        dl_remain  = state.get('daily_loss_remaining', '?')
        max_dl     = state.get('max_daily_loss', '?')
        return (
            f'Daily loss {status}: daily_pnl=${daily_pnl}, '
            f'remaining=${dl_remain} of ${max_dl} limit'
        )
    else:
        tl_remain  = state.get('total_loss_remaining', '?')
        max_tl     = state.get('max_total_loss', '?')
        return (
            f'Total loss {status}: current=${current}, '
            f'remaining=${tl_remain} of ${max_tl} limit'
        )


# ── Discord alert delivery ─────────────────────────────────────────────────────

def send_prop_alert_discord(alert: dict, state: dict) -> dict:
    """
    Send prop rule breach risk embed to Discord.
    WARNING = orange; CRITICAL = red.
    SAFETY: Discord only — no broker writes.
    """
    try:
        import requests as _req
        from core.config import (
            DISCORD_BOT_TOKEN,
            DISCORD_CHANNEL_LIVE,
            DISCORD_CHANNEL_SYSTEM_HEALTH,
        )
        if not DISCORD_BOT_TOKEN:
            return {'ok': False, 'error': 'DISCORD_BOT_TOKEN not configured'}
        channel_id = DISCORD_CHANNEL_SYSTEM_HEALTH or DISCORD_CHANNEL_LIVE
        if not channel_id:
            return {'ok': False, 'error': 'No Discord channel configured'}

        severity   = alert.get('severity', 'WARNING')
        status     = alert.get('alert_type', '')
        color      = 0xFF0000 if severity == 'CRITICAL' else 0xFF8800
        title_icon = '\U0001f6a8' if severity == 'CRITICAL' else '⚠️'

        embed = {
            'title':       f'{title_icon}  PROP ACCOUNT {severity}: {status}',
            'description': alert.get('message', ''),
            'color':       color,
            'fields': [
                {'name': 'Current Balance',   'value': f"${state.get('current_balance', '?')}",  'inline': True},
                {'name': 'High-Water Mark',   'value': f"${state.get('high_water_mark', '?')}",  'inline': True},
                {'name': 'Daily P&L',         'value': f"${state.get('daily_pnl', '?')}",        'inline': True},
                {'name': 'Prop Firm',         'value': str(state.get('prop_firm_name') or 'not configured'), 'inline': True},
                {'name': 'Action Required',   'value': '**MANUAL REVIEW REQUIRED**',             'inline': False},
                {'name': 'Auto-Action',       'value': 'None — alert-only. No trades halted automatically.', 'inline': False},
            ],
            'footer':    {'text': 'NOVA Prop Account Monitor • Phase 6'},
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        r = _req.post(
            f'https://discord.com/api/v10/channels/{channel_id}/messages',
            headers={
                'Authorization': f'Bot {DISCORD_BOT_TOKEN}',
                'Content-Type':  'application/json',
            },
            json={'embeds': [embed]},
            timeout=20,
        )
        if r.status_code in (200, 201):
            return {'ok': True, 'channel_id': channel_id}
        return {'ok': False, 'status': r.status_code, 'error': r.text[:300]}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def check_and_send_prop_alerts(
    state:            dict,
    cooldown_seconds: int = ALERT_COOLDOWN_SECONDS,
) -> dict:
    """
    Evaluate prop state for breach risk, send Discord alerts respecting cooldown.
    Returns {'alerts_sent': [...], 'alerts_suppressed': [...]}.
    SAFETY: Discord only — no broker writes.
    """
    alerts_sent: list[dict] = []
    alerts_suppressed: list[str] = []

    for alert in get_prop_breach_alerts(state):
        key = alert.get('alert_key', '')
        if _is_prop_in_cooldown(key, cooldown_seconds):
            alerts_suppressed.append(key)
            continue
        result = send_prop_alert_discord(alert, state)
        _record_prop_alert_sent(key)
        alerts_sent.append({'alert_key': key, 'discord': result})

    return {'alerts_sent': alerts_sent, 'alerts_suppressed': alerts_suppressed}
