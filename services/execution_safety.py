"""execution_safety.py — Execution Bot v2 Phase 5 + 5.1: Periodic safety monitor.

Periodic read-only scan of broker/journal state. Detects unprotected positions,
sends CRITICAL Discord alerts (when enabled), writes a snapshot status file and a
rolling log.

SAFETY CONTRACT — this module MUST NEVER:
  - Submit orders
  - Cancel orders
  - Modify positions
  - Call any Alpaca write endpoint

Phase 5.1 alert controls (read from core.config / env vars):
  NOVA_EXECUTION_SAFETY_MONITOR_ENABLED  — if false, loop skips run (still sleeps)
  NOVA_EXECUTION_SAFETY_DISCORD_ENABLED  — if false, alerts are logged but not sent to Discord
  NOVA_EXECUTION_SAFETY_ALERT_COOLDOWN_SECONDS — repeat-alert cooldown (default 900)

Cooldown is dual-layer:
  - In-memory: fast check within the same process lifetime
  - File-backed: nova_execution_safety_alert_registry.json — survives restarts

Public API:
    run_execution_safety_check(cooldown_seconds) -> dict
    get_latest_safety_status() -> dict
    send_safety_discord_alert(alert) -> dict
    get_cooldown_state() -> dict
    clear_cooldown_state() -> None
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────────

SAFETY_LOG_MAX         = 1000
ALERT_COOLDOWN_SECONDS = 300      # legacy default; env var overrides at runtime


# ── File paths ─────────────────────────────────────────────────────────────────

def _safety_status_file() -> Path:
    try:
        from core.config import DATA_DIR
        return DATA_DIR / 'nova_execution_safety_status.json'
    except Exception:
        return Path('data') / 'nova_execution_safety_status.json'


def _safety_log_file() -> Path:
    try:
        from core.config import DATA_DIR
        return DATA_DIR / 'nova_execution_safety_log.json'
    except Exception:
        return Path('data') / 'nova_execution_safety_log.json'


def _alert_registry_file() -> Path:
    try:
        from core.config import DATA_DIR
        return DATA_DIR / 'nova_execution_safety_alert_registry.json'
    except Exception:
        return Path('data') / 'nova_execution_safety_alert_registry.json'


# ── Persistent alert registry ─────────────────────────────────────────────────

def _load_alert_registry() -> dict:
    """Load persistent cooldown registry from file. Returns {key: entry_dict}."""
    p = _alert_registry_file()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_alert_registry_entry(
    key:        str,
    instrument: str,
    alert_type: str,
    sent_at:    str,
) -> None:
    """Persist a single alert record to the registry (survives restart)."""
    try:
        registry = _load_alert_registry()
        registry[key] = {
            'alert_key':    key,
            'instrument':   instrument,
            'alert_type':   alert_type,
            'last_sent_at': sent_at,
        }
        _alert_registry_file().write_text(
            json.dumps(registry, indent=2), encoding='utf-8'
        )
    except Exception:
        pass


# ── Alert cooldown (in-memory + file-backed) ──────────────────────────────────

_cooldown_state: dict[str, str] = {}   # {key: iso_timestamp_of_last_alert}
_cooldown_lock  = threading.Lock()

# Pre-populate from persistent registry so cooldowns survive restarts
try:
    for _rk, _re in _load_alert_registry().items():
        if _re.get('last_sent_at'):
            _cooldown_state[_rk] = _re['last_sent_at']
except Exception:
    pass


def _cooldown_key(instrument: str, alert_type: str) -> str:
    return f'{instrument.upper()}__{alert_type.upper()}'


def _is_in_cooldown(
    instrument:       str,
    alert_type:       str,
    cooldown_seconds: int = ALERT_COOLDOWN_SECONDS,
) -> bool:
    """Return True if this pair fired an alert within cooldown_seconds."""
    if cooldown_seconds <= 0:
        return False
    key = _cooldown_key(instrument, alert_type)
    with _cooldown_lock:
        last_str = _cooldown_state.get(key)
    if not last_str:
        return False
    try:
        last    = datetime.fromisoformat(last_str)
        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        return elapsed < cooldown_seconds
    except Exception:
        return False


def _record_alert_sent(instrument: str, alert_type: str) -> None:
    """Record that an alert was sent — updates both in-memory and file registry."""
    key     = _cooldown_key(instrument, alert_type)
    sent_at = datetime.now(timezone.utc).isoformat()
    with _cooldown_lock:
        _cooldown_state[key] = sent_at
    _save_alert_registry_entry(key, instrument, alert_type, sent_at)


def get_cooldown_state() -> dict:
    """Return a copy of the current in-memory cooldown state."""
    with _cooldown_lock:
        return dict(_cooldown_state)


def clear_cooldown_state() -> None:
    """Reset all in-memory cooldowns (used in testing; not called from production)."""
    with _cooldown_lock:
        _cooldown_state.clear()


# ── Env-var helpers ────────────────────────────────────────────────────────────

def _discord_enabled() -> bool:
    try:
        from core.config import NOVA_EXECUTION_SAFETY_DISCORD_ENABLED
        return bool(NOVA_EXECUTION_SAFETY_DISCORD_ENABLED)
    except Exception:
        return False   # default OFF


def _env_cooldown_seconds() -> int:
    try:
        from core.config import NOVA_EXECUTION_SAFETY_ALERT_COOLDOWN_SECONDS
        return int(NOVA_EXECUTION_SAFETY_ALERT_COOLDOWN_SECONDS)
    except Exception:
        return 900


# ── Discord CRITICAL alert delivery ───────────────────────────────────────────

def send_safety_discord_alert(alert: dict) -> dict:
    """
    Send a CRITICAL unprotected-position embed to Discord.

    Prefers DISCORD_CHANNEL_SYSTEM_HEALTH; falls back to DISCORD_CHANNEL_LIVE.
    Sends a raw embed — does NOT use the AlertData / deliver_alert path.

    SAFETY: this is the only outbound network call in this module.
    No broker writes. No order changes.
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

        instrument = str(alert.get('instrument', '?')).upper()
        side       = str(alert.get('side', '?')).upper()
        qty        = alert.get('qty', '?')
        detected   = alert.get('detected_at', '?')

        embed = {
            'title':       '\U0001f6a8  CRITICAL: UNPROTECTED POSITION DETECTED',
            'description': (
                f'**{instrument} {side} — {qty} units has NO STOP ORDER**\n\n'
                f'Detected at: `{detected}`\n\n'
                f'⚠️ **NO AUTO-ACTION WAS TAKEN.**\n'
                f'Position remains open. Manual review required immediately.'
            ),
            'color': 0xFF0000,
            'fields': [
                {'name': 'Symbol',          'value': str(alert.get('symbol', '?')), 'inline': True},
                {'name': 'Instrument',      'value': instrument,                    'inline': True},
                {'name': 'Side',            'value': side,                          'inline': True},
                {'name': 'Qty',             'value': str(qty),                      'inline': True},
                {'name': 'Required Action', 'value': '**MANUAL REVIEW REQUIRED**',  'inline': False},
                {
                    'name':  'Auto-Action Taken',
                    'value': 'None — alert-only. No flatten, no stop submitted, no cancel.',
                    'inline': False,
                },
            ],
            'footer':    {'text': 'NOVA Execution Safety Monitor • Phase 5'},
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


# ── File I/O ──────────────────────────────────────────────────────────────────

def _write_safety_status(status: dict) -> None:
    try:
        _safety_status_file().write_text(json.dumps(status, indent=2), encoding='utf-8')
    except Exception:
        pass


def _append_safety_log(entry: dict) -> None:
    p = _safety_log_file()
    try:
        entries: list = []
        if p.exists():
            try:
                entries = json.loads(p.read_text(encoding='utf-8'))
                if not isinstance(entries, list):
                    entries = []
            except Exception:
                entries = []
        entries.append(entry)
        if len(entries) > SAFETY_LOG_MAX:
            entries = entries[-SAFETY_LOG_MAX:]
        p.write_text(json.dumps(entries, indent=2), encoding='utf-8')
    except Exception:
        pass


def get_latest_safety_status() -> dict:
    """
    Return the most recent safety status from the cached file.
    Falls back to a live computation if the file is missing.
    Never raises.
    """
    p = _safety_status_file()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            pass
    try:
        from services.execution_reconcile import get_execution_safety_status
        return get_execution_safety_status()
    except Exception as e:
        return {
            'checked_at':              None,
            'status':                  'UNKNOWN_BROKER_STATE',
            'open_positions_count':    0,
            'open_orders_count':       0,
            'open_journal_count':      0,
            'protected_positions':     [],
            'unprotected_positions':   [],
            'emergency_alerts':        [],
            'reconciliations':         [],
            'alerts_sent':             [],
            'alerts_suppressed_by_cooldown': [],
            'warnings':                [],
            'errors':                  [f'Could not compute live status: {e}'],
        }


# ── Main safety check ─────────────────────────────────────────────────────────

def run_execution_safety_check(
    cooldown_seconds: int | None = None,
) -> dict:
    """
    Full periodic safety check:
      1. Fetch broker positions + orders + open journal trades
      2. Detect unprotected positions (Phase 4 get_execution_safety_status)
      3. Reconcile each position against journal (Phase 3 reconcile_execution_state)
      4. [Phase 5.1] If Discord enabled and not in cooldown: send CRITICAL alert
         If Discord disabled: record DISCORD_DISABLED suppression; no send
      5. [Phase 6] Update prop account state
      6. Write nova_execution_safety_status.json
      7. Append to nova_execution_safety_log.json

    cooldown_seconds: override the env-var default (used in tests).

    Returns structured status dict.
    SAFETY CONTRACT: read-only. Never modifies broker state.
    """
    if cooldown_seconds is None:
        cooldown_seconds = _env_cooldown_seconds()

    discord_on = _discord_enabled()

    checked_at             = datetime.now(timezone.utc).isoformat()
    warnings:  list[str]  = []
    errors:    list[str]  = []
    alerts_sent:       list[dict] = []
    alerts_suppressed: list[str]  = []
    reconciliations:   list[dict] = []
    prop_account_summary: dict    = {}

    try:
        from services.execution_reconcile import (
            get_execution_safety_status,
            get_broker_positions_safe,
            get_broker_orders_safe,
            get_open_journal_trades_safe,
            reconcile_execution_state,
        )

        # 1. Primary safety snapshot
        safety           = get_execution_safety_status()
        broker_positions = get_broker_positions_safe()
        broker_orders    = get_broker_orders_safe()
        journal_trades   = get_open_journal_trades_safe()

        # 2. Reconcile each broker position against journal
        for pos in broker_positions:
            symbol     = str(pos.get('symbol', '')).upper()
            pos_side   = (pos.get('side') or '').lower()
            recon_req  = {
                'symbol':    symbol,
                'direction': 'LONG' if pos_side == 'long' else 'SHORT',
                'qty':       pos.get('qty'),
            }
            try:
                recon = reconcile_execution_state(
                    execution_request = recon_req,
                    broker_positions  = broker_positions,
                    broker_orders     = broker_orders,
                    journal_trades    = journal_trades,
                )
                reconciliations.append({
                    'symbol':                  symbol,
                    'reconciliation_status':   recon.get('reconciliation_status'),
                    'reason':                  recon.get('reason'),
                    'protective_stop_found':   recon.get('protective_stop_found'),
                    'protective_target_found': recon.get('protective_target_found'),
                })
                if recon.get('warnings'):
                    warnings.extend(recon['warnings'])
                if recon.get('errors'):
                    errors.extend(recon['errors'])
            except Exception as _re:
                warnings.append(f'Reconciliation error for {symbol}: {_re}')

        # 3. Alert routing (Phase 5.1 controls)
        for alert in safety.get('emergency_alerts', []):
            instrument = str(alert.get('instrument', '')).upper()
            alert_type = str(alert.get('alert_type', 'UNPROTECTED_POSITION')).upper()

            # Cooldown check (applies regardless of Discord setting)
            if _is_in_cooldown(instrument, alert_type, cooldown_seconds):
                alerts_suppressed.append(f'{instrument}:COOLDOWN')
                warnings.append(f'Alert suppressed by cooldown: {instrument} {alert_type}')
                continue

            if not discord_on:
                # Monitor still running; Discord delivery is OFF by config
                alerts_suppressed.append(f'{instrument}:DISCORD_DISABLED')
                warnings.append(
                    f'Discord disabled — alert NOT sent for {instrument} {alert_type}. '
                    f'Set NOVA_EXECUTION_SAFETY_DISCORD_ENABLED=true to enable.'
                )
                continue

            # Discord enabled → send
            send_result = send_safety_discord_alert(alert)
            _record_alert_sent(instrument, alert_type)
            alerts_sent.append({
                'instrument': instrument,
                'alert_type': alert_type,
                'discord':    send_result,
            })
            if not send_result.get('ok'):
                warnings.append(
                    f'Discord alert failed for {instrument}: {send_result.get("error")}'
                )

        # Phase 6: Prop account state + trailing drawdown monitoring (non-blocking)
        try:
            from services.prop_account_state import (
                update_prop_account_state_from_broker,
                check_and_send_prop_alerts,
            )
            prop_state = update_prop_account_state_from_broker()
            prop_account_summary = {
                'current_balance':             prop_state.get('current_balance'),
                'starting_balance':            prop_state.get('starting_balance'),
                'high_water_mark':             prop_state.get('high_water_mark'),
                'trailing_drawdown_threshold': prop_state.get('trailing_drawdown_threshold'),
                'trailing_drawdown_remaining': prop_state.get('trailing_drawdown_remaining'),
                'daily_pnl':                   prop_state.get('daily_pnl'),
                'daily_loss_remaining':        prop_state.get('daily_loss_remaining'),
                'total_loss_remaining':        prop_state.get('total_loss_remaining'),
                'prop_state_status':           prop_state.get('prop_state_status'),
                'broker_account_read':         prop_state.get('broker_account_read', False),
            }
            prop_result = check_and_send_prop_alerts(prop_state, cooldown_seconds)
            if prop_result.get('alerts_sent'):
                alerts_sent.extend(prop_result['alerts_sent'])
            if prop_result.get('alerts_suppressed'):
                alerts_suppressed.extend(prop_result['alerts_suppressed'])
        except Exception as _p6_err:
            warnings.append(f'Prop account state error (non-blocking): {_p6_err}')

        # Merge
        warnings = list(safety.get('warnings', [])) + warnings
        errors   = list(safety.get('errors', []))   + errors

        status = {
            'checked_at':                  checked_at,
            'status':                      safety.get('status'),
            'open_positions_count':        safety.get('open_positions_count', 0),
            'open_orders_count':           safety.get('open_orders_count', 0),
            'open_journal_count':          safety.get('open_journal_count', 0),
            'protected_positions':         safety.get('protected_positions', []),
            'unprotected_positions':       safety.get('unprotected_positions', []),
            'emergency_alerts':            safety.get('emergency_alerts', []),
            'reconciliations':             reconciliations,
            'alerts_sent':                 alerts_sent,
            'alerts_suppressed_by_cooldown': alerts_suppressed,
            'warnings':                    warnings,
            'errors':                      errors,
            'prop_account_summary':        prop_account_summary,
            'discord_enabled':             discord_on,
            'cooldown_seconds':            cooldown_seconds,
        }

    except Exception as e:
        errors.append(str(e))
        status = {
            'checked_at':                  checked_at,
            'status':                      'UNKNOWN_BROKER_STATE',
            'open_positions_count':        0,
            'open_orders_count':           0,
            'open_journal_count':          0,
            'protected_positions':         [],
            'unprotected_positions':       [],
            'emergency_alerts':            [],
            'reconciliations':             [],
            'alerts_sent':                 [],
            'alerts_suppressed_by_cooldown': [],
            'warnings':                    warnings,
            'errors':                      errors,
            'prop_account_summary':        {},
            'discord_enabled':             discord_on,
            'cooldown_seconds':            cooldown_seconds,
        }

    _write_safety_status(status)
    _append_safety_log({**status, '_log_type': 'SAFETY_CHECK'})
    return status
