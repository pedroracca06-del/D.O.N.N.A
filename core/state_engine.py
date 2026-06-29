"""
DONNA State Engine — centralized live execution state authority.
Single source of truth for all execution state. No business logic; pure state ownership.

Future migration: replace JSON persistence with Redis or Postgres by swapping
_save() and _load() methods only. All other code stays identical.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ── Timezone helpers ───────────────────────────────────────────

try:
    from zoneinfo import ZoneInfo as _ZI
    _NY_TZ = _ZI('America/New_York')
except ImportError:
    try:
        import pytz as _pytz  # type: ignore[import]
        _NY_TZ = _pytz.timezone('America/New_York')
    except ImportError:
        _NY_TZ = timezone.utc  # type: ignore[assignment]


def _now_ny() -> datetime:
    return datetime.now(tz=_NY_TZ)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


# ── Schema ─────────────────────────────────────────────────────

from core.config import STATE_ENGINE_FILE as _STATE_FILE

_DEFAULT_STATE: dict = {
    'market_regime':         'UNKNOWN',
    'macro_risk':            'low',
    'session_state':         'OFF_HOURS',
    'daily_trade_count':     0,
    'first_trade_outcome':   None,
    'size_reduction_active': False,
    'daily_loss_trade_hit':  False,
    'cumulative_risk_today': 0.0,
    'daily_pnl':             0.0,
    'open_positions':        [],
    'execution_lock':        False,
    'trade_permission':      True,
    'eod_lock':              False,
    'macro_lock':            False,
    'red_folder_lock':       False,
    'asia_trade_taken':      False,
    'last_signal_id':        None,
    'last_execution_time':   None,
    'risk_lockouts':         [],
    'state_date':            None,
    'last_updated':          None,
    'active_thesis':         'NEUTRAL',
    'thesis_set_at':         None,
    'thesis_direction':      None,
    'last_spy_execution':    None,
    'last_qqq_execution':    None,
    'spy_cooldown_until':    None,
    'qqq_cooldown_until':    None,
    'blocked_signals_today': [],
}

# Fields reset to their defaults each new ET calendar day
_DAILY_RESET_FIELDS: dict = {
    'daily_trade_count':     0,
    'first_trade_outcome':   None,
    'size_reduction_active': False,
    'daily_loss_trade_hit':  False,
    'cumulative_risk_today': 0.0,
    'daily_pnl':             0.0,
    'eod_lock':              False,
    'red_folder_lock':       False,
    'asia_trade_taken':      False,
    'risk_lockouts':         [],
    'open_positions':        [],
    'active_thesis':         'NEUTRAL',
    'thesis_set_at':         None,
    'thesis_direction':      None,
    'last_signal_id':        None,
    'last_execution_time':   None,
    'blocked_signals_today': [],
    'spy_cooldown_until':    None,
    'qqq_cooldown_until':    None,
    'last_spy_execution':    None,
    'last_qqq_execution':    None,
    # EOD disables this at 3:30 PM — must restore at the start of each new day
    # so yesterday's EOD lock never bleeds into the next trading session.
    'trade_permission':      True,
}


class DonnaStateEngine:
    """
    Thread-safe, file-backed state store for DONNA's live execution layer.
    Instantiate once (use the module-level `state` singleton below).
    All public methods are safe to call from any thread — they never raise.
    """

    def __init__(self) -> None:
        self._lock  = threading.Lock()
        self._state: dict = {}
        self._load()

    # ── Persistence ────────────────────────────────────────────

    def _load(self) -> None:
        """Load state from disk, falling back to defaults on any failure."""
        try:
            if _STATE_FILE.exists():
                raw = json.loads(_STATE_FILE.read_text(encoding='utf-8'))
                if isinstance(raw, dict):
                    merged = dict(_DEFAULT_STATE)
                    merged.update(raw)
                    self._state = merged
                    self._maybe_reset_daily_unlocked()
                    return
        except Exception as exc:
            print(f'[state_engine] _load error: {exc}')
        self._state = dict(_DEFAULT_STATE)
        self._state['state_date'] = _now_ny().strftime('%Y-%m-%d')
        self._save_unlocked()

    def _save_unlocked(self) -> None:
        """Write current state to disk. Caller must hold self._lock."""
        try:
            self._state['last_updated'] = _utc_now_iso()
            _STATE_FILE.write_text(
                json.dumps(self._state, indent=2, default=str),
                encoding='utf-8',
            )
        except Exception as exc:
            print(f'[state_engine] _save error: {exc}')

    # ── Daily reset ────────────────────────────────────────────

    def _maybe_reset_daily_unlocked(self) -> None:
        """Reset daily fields if state_date is not today ET. Caller must hold lock."""
        today_str = _now_ny().strftime('%Y-%m-%d')
        if self._state.get('state_date') != today_str:
            self._do_reset_unlocked(today_str)

    def _do_reset_unlocked(self, today_str: str | None = None) -> None:
        """Apply the daily field reset. Caller must hold lock."""
        if today_str is None:
            today_str = _now_ny().strftime('%Y-%m-%d')
        self._state.update(_DAILY_RESET_FIELDS)
        self._state['state_date'] = today_str
        self._save_unlocked()
        print(f'[state_engine] Daily reset — state_date={today_str}')

    # ── Getters ────────────────────────────────────────────────

    def get_state(self) -> dict:
        """Return a shallow copy of the full state dict."""
        with self._lock:
            self._maybe_reset_daily_unlocked()
            return dict(self._state)

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value of a single state field."""
        with self._lock:
            self._maybe_reset_daily_unlocked()
            return self._state.get(key, default)

    def can_execute(self) -> bool:
        """True only when all execution gates are open."""
        return self.block_reason() is None

    def block_reason(self) -> str | None:
        """Return a human-readable reason string if execution is blocked, else None."""
        with self._lock:
            self._maybe_reset_daily_unlocked()
            s = self._state
            _ny = _now_ny()
            _h, _m = _ny.hour, _ny.minute
            # NOVA_ALL_SESSIONS=true bypasses the NY-only time gate for testing.
            # Remove or unset this env var when moving to production NY-session-only mode.
            _all_sessions = os.getenv('NOVA_ALL_SESSIONS', '').strip().lower() == 'true'
            if not _all_sessions:
                if _h < 9 or (_h == 9 and _m < 30) or _h >= 16:
                    return f'outside NY session hours — {_ny.strftime("%H:%M")} ET (window: 09:30–16:00)'
            if s.get('execution_lock', False):
                return 'execution_lock is set'
            if not bool(s.get('trade_permission', True)):
                return 'trade_permission disabled'
            if s.get('eod_lock', False) and not _all_sessions:
                return 'eod_lock is set'
            if s.get('macro_lock', False):
                return 'macro_lock is set'
            if s.get('red_folder_lock', False):
                return 'red_folder_lock is set'
            return None

    def get_trade_count(self) -> int:
        """Return today's trade count."""
        with self._lock:
            self._maybe_reset_daily_unlocked()
            return int(self._state.get('daily_trade_count', 0))

    def get_session(self) -> str:
        """Return the current session_state label."""
        with self._lock:
            self._maybe_reset_daily_unlocked()
            return str(self._state.get('session_state', 'OFF_HOURS'))

    def get_open_positions(self) -> list:
        """Return a copy of the open_positions list."""
        with self._lock:
            self._maybe_reset_daily_unlocked()
            return list(self._state.get('open_positions', []))

    # ── Setters ────────────────────────────────────────────────

    def set(self, key: str, value: Any) -> None:
        """Update a single field and persist immediately."""
        with self._lock:
            try:
                self._maybe_reset_daily_unlocked()
                self._state[key] = value
                self._save_unlocked()
            except Exception as exc:
                print(f'[state_engine] set({key}) error: {exc}')

    def set_many(self, updates: dict) -> None:
        """Update multiple fields in a single atomic write."""
        with self._lock:
            try:
                self._maybe_reset_daily_unlocked()
                self._state.update(updates)
                self._save_unlocked()
            except Exception as exc:
                print(f'[state_engine] set_many error: {exc}')

    def add_lockout(self, reason: str) -> None:
        """Append a timestamped lockout reason to risk_lockouts."""
        with self._lock:
            try:
                self._maybe_reset_daily_unlocked()
                lockouts = list(self._state.get('risk_lockouts', []))
                lockouts.append({'reason': reason, 'timestamp': _utc_now_iso()})
                self._state['risk_lockouts'] = lockouts
                self._save_unlocked()
            except Exception as exc:
                print(f'[state_engine] add_lockout error: {exc}')

    def clear_lockouts(self) -> None:
        """Empty the risk_lockouts list."""
        with self._lock:
            try:
                self._maybe_reset_daily_unlocked()
                self._state['risk_lockouts'] = []
                self._save_unlocked()
            except Exception as exc:
                print(f'[state_engine] clear_lockouts error: {exc}')

    def add_position(self, position: dict) -> None:
        """Append a position dict to open_positions."""
        with self._lock:
            try:
                self._maybe_reset_daily_unlocked()
                positions = list(self._state.get('open_positions', []))
                positions.append(position)
                self._state['open_positions'] = positions
                self._save_unlocked()
            except Exception as exc:
                print(f'[state_engine] add_position error: {exc}')

    def remove_position(self, symbol: str) -> None:
        """Remove all positions matching symbol from open_positions."""
        with self._lock:
            try:
                self._maybe_reset_daily_unlocked()
                sym_upper = str(symbol).upper()
                self._state['open_positions'] = [
                    p for p in self._state.get('open_positions', [])
                    if str(p.get('symbol', '')).upper() != sym_upper
                ]
                self._save_unlocked()
            except Exception as exc:
                print(f'[state_engine] remove_position error: {exc}')

    def increment_trade_count(self) -> int:
        """Increment daily_trade_count by 1 and return the new value."""
        with self._lock:
            try:
                self._maybe_reset_daily_unlocked()
                new_val = int(self._state.get('daily_trade_count', 0)) + 1
                self._state['daily_trade_count'] = new_val
                self._save_unlocked()
                return new_val
            except Exception as exc:
                print(f'[state_engine] increment_trade_count error: {exc}')
                return 0

    def record_execution(self, signal_id: str | None, risk_amount: float) -> None:
        """Record a completed trade: updates signal ID, timestamp, and cumulative risk."""
        with self._lock:
            try:
                self._maybe_reset_daily_unlocked()
                self._state['last_signal_id']       = signal_id
                self._state['last_execution_time']  = _utc_now_iso()
                self._state['cumulative_risk_today'] = (
                    float(self._state.get('cumulative_risk_today', 0.0))
                    + float(risk_amount)
                )
                self._save_unlocked()
            except Exception as exc:
                print(f'[state_engine] record_execution error: {exc}')

    def reset_daily(self) -> None:
        """Force an immediate daily reset of all daily-scoped fields."""
        with self._lock:
            try:
                self._do_reset_unlocked()
            except Exception as exc:
                print(f'[state_engine] reset_daily error: {exc}')

    # ── Thesis ─────────────────────────────────────────────────

    def set_thesis(self, thesis: str, direction: str | None) -> None:
        """Set active thesis, direction, and timestamp."""
        with self._lock:
            try:
                self._maybe_reset_daily_unlocked()
                self._state['active_thesis']    = thesis
                self._state['thesis_direction'] = direction
                self._state['thesis_set_at']    = _utc_now_iso()
                self._save_unlocked()
            except Exception as exc:
                print(f'[state_engine] set_thesis error: {exc}')

    def get_thesis(self) -> dict:
        """Return active_thesis, thesis_direction, thesis_set_at."""
        with self._lock:
            self._maybe_reset_daily_unlocked()
            return {
                'active_thesis':    self._state.get('active_thesis', 'NEUTRAL'),
                'thesis_direction': self._state.get('thesis_direction'),
                'thesis_set_at':    self._state.get('thesis_set_at'),
            }

    # ── Cooldowns ──────────────────────────────────────────────

    def set_cooldown(self, symbol: str, minutes: int = 30) -> None:
        """Set spy_cooldown_until or qqq_cooldown_until to now + minutes UTC."""
        key = 'spy_cooldown_until' if symbol.upper() == 'SPY' else 'qqq_cooldown_until'
        until = (
            datetime.now(timezone.utc) + timedelta(minutes=minutes)
        ).strftime('%Y-%m-%dT%H:%M:%SZ')
        with self._lock:
            try:
                self._maybe_reset_daily_unlocked()
                self._state[key] = until
                self._save_unlocked()
            except Exception as exc:
                print(f'[state_engine] set_cooldown error: {exc}')

    def is_on_cooldown(self, symbol: str) -> bool:
        """Return True if the symbol's cooldown timestamp is still in the future."""
        key = 'spy_cooldown_until' if symbol.upper() == 'SPY' else 'qqq_cooldown_until'
        with self._lock:
            self._maybe_reset_daily_unlocked()
            until_str = self._state.get(key)
        if not until_str:
            return False
        try:
            until_dt = datetime.strptime(until_str, '%Y-%m-%dT%H:%M:%SZ').replace(
                tzinfo=timezone.utc
            )
            return datetime.now(timezone.utc) < until_dt
        except Exception:
            return False


# ── Singleton ──────────────────────────────────────────────────
state = DonnaStateEngine()
