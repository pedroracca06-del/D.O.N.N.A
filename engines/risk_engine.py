"""
DONNA Risk Management Engine — Layer 4
Position sizing, R/R validation, drawdown tracking, session loss limits.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

NY_TZ  = ZoneInfo('America/New_York')

from core.config import RISK_ENGINE_FILE

DEFAULT_STATE: dict = {
    'account_size':     25000.0,
    'risk_pct':         1.0,
    'stop_trading':     False,
    'stop_reason':      '',
    'last_updated':     '',
}


# ── persistence ────────────────────────────────────────────────────────────────

def _read(path: Path, default):
    try:
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return default


def _write(path: Path, data) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def load_re_state() -> dict:
    raw = _read(RISK_ENGINE_FILE, {})
    merged = dict(DEFAULT_STATE)
    if isinstance(raw, dict):
        merged.update(raw)
    return merged


def save_re_state(state: dict) -> None:
    state['last_updated'] = datetime.now(NY_TZ).isoformat()
    _write(RISK_ENGINE_FILE, state)


# ── core calculators ────────────────────────────────────────────────────────────

def compute_position_size(
    account_size: float,
    risk_pct: float,
    entry: float,
    stop: float,
) -> dict:
    """
    Max contracts/shares so that a full stop-out = risk_pct% of account.
    Works for stocks (shares) and futures (points × tick_value = 1 for simplicity).
    """
    try:
        risk_dollars   = float(account_size) * float(risk_pct) / 100.0
        risk_per_unit  = abs(float(entry) - float(stop))
        if risk_per_unit <= 0:
            return {'max_units': 0, 'risk_dollars': round(risk_dollars, 2),
                    'risk_per_unit': 0, 'valid': False, 'note': 'Entry and stop must differ.'}
        max_units = risk_dollars / risk_per_unit
        return {
            'max_units':    round(max_units, 2),
            'risk_dollars': round(risk_dollars, 2),
            'risk_per_unit': round(risk_per_unit, 4),
            'valid':        True,
            'note':         f'Max {max_units:.1f} units · risking ${risk_dollars:.0f}',
        }
    except Exception as exc:
        return {'max_units': 0, 'risk_dollars': 0, 'risk_per_unit': 0,
                'valid': False, 'note': str(exc)}


def compute_rr(
    entry: float,
    stop: float,
    target: float,
    direction: str = 'LONG',
) -> dict:
    """R/R ratio; trade considered valid when ratio >= 1.5."""
    try:
        direction = str(direction).upper()
        risk   = abs(float(entry) - float(stop))
        reward = abs(float(target) - float(entry))
        if risk <= 0:
            return {'rr': 0.0, 'valid': False, 'note': 'Zero-risk trade — check entry/stop.'}
        rr = reward / risk

        # directional sanity
        long_ok  = direction == 'LONG'  and float(target) > float(entry) > float(stop)
        short_ok = direction == 'SHORT' and float(target) < float(entry) < float(stop)
        directional_ok = long_ok or short_ok

        valid = rr >= 1.5 and directional_ok
        note  = (
            f'{rr:.2f}:1 R/R — {"VALID ✓" if valid else "BELOW MINIMUM ✗"}'
            + ('' if directional_ok else ' — Entry/stop/target order incorrect for ' + direction)
        )
        return {
            'rr':       round(rr, 2),
            'risk_pts': round(risk, 4),
            'reward_pts': round(reward, 4),
            'valid':    valid,
            'note':     note,
        }
    except Exception as exc:
        return {'rr': 0.0, 'risk_pts': 0, 'reward_pts': 0, 'valid': False, 'note': str(exc)}


# ── journal analysis helpers ────────────────────────────────────────────────────

def _parse_ts(ts_str: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(ts_str).replace('Z', '+00:00'))
        return dt.astimezone(NY_TZ)
    except Exception:
        return None


def _today_ny() -> datetime:
    return datetime.now(NY_TZ).replace(hour=0, minute=0, second=0, microsecond=0)


def _week_start_ny() -> datetime:
    today = _today_ny()
    # Monday of current week
    return today - timedelta(days=today.weekday())


def _get_today_trades(trades: list) -> list:
    cutoff = _today_ny()
    return [t for t in trades if (dt := _parse_ts(t.get('timestamp',''))) and dt >= cutoff]


def _get_week_trades(trades: list) -> list:
    cutoff = _week_start_ny()
    return [t for t in trades if (dt := _parse_ts(t.get('timestamp',''))) and dt >= cutoff]


def compute_drawdown_status(trades: list, account_size: float = 25000.0) -> dict:
    """
    Analyse daily and weekly P&L from journal.
    Flags breach if daily drawdown > 2% or weekly > 6%.
    """
    acct = float(account_size) if float(account_size) > 0 else 25000.0

    today_trades  = _get_today_trades(trades)
    weekly_trades = _get_week_trades(trades)

    daily_pnl  = sum(float(t.get('pnl', 0)) for t in today_trades)
    weekly_pnl = sum(float(t.get('pnl', 0)) for t in weekly_trades)

    daily_dd_pct  = (-daily_pnl  / acct * 100) if daily_pnl  < 0 else 0.0
    weekly_dd_pct = (-weekly_pnl / acct * 100) if weekly_pnl < 0 else 0.0

    daily_breach  = daily_dd_pct  >= 2.0
    weekly_breach = weekly_dd_pct >= 6.0

    if daily_breach:
        status     = 'DAILY_LIMIT'
        status_note = f'Daily drawdown {daily_dd_pct:.1f}% exceeds 2% limit. Stop trading today.'
    elif weekly_breach:
        status     = 'WEEKLY_LIMIT'
        status_note = f'Weekly drawdown {weekly_dd_pct:.1f}% exceeds 6% limit. No new trades this week.'
    elif daily_dd_pct >= 1.5:
        status     = 'WARNING'
        status_note = f'Approaching daily limit ({daily_dd_pct:.1f}%). Tighten size or pause.'
    else:
        status     = 'OK'
        status_note = 'Drawdown within acceptable limits.'

    return {
        'status':          status,
        'status_note':     status_note,
        'daily_pnl':       round(daily_pnl,  2),
        'weekly_pnl':      round(weekly_pnl, 2),
        'daily_dd_pct':    round(daily_dd_pct,  2),
        'weekly_dd_pct':   round(weekly_dd_pct, 2),
        'daily_breach':    daily_breach,
        'weekly_breach':   weekly_breach,
        'today_trades':    len(today_trades),
        'weekly_trades':   len(weekly_trades),
    }


def compute_session_loss_count(trades: list) -> dict:
    """
    Count consecutive losses at the END of today's trades.
    Triggers STOP_TRADING when streak >= 3.
    """
    today = _get_today_trades(trades)
    # oldest first, count from tail
    streak = 0
    for t in reversed(today):
        if str(t.get('outcome', '')).upper() == 'LOSS':
            streak += 1
        else:
            break

    trigger = streak >= 3
    return {
        'consecutive_losses': streak,
        'stop_triggered':     trigger,
        'note': (
            f'{streak} consecutive loss{"es" if streak != 1 else ""} this session'
            + (' — STOP TRADING rule activated.' if trigger else '.')
        ),
    }


# ── main payload builder ────────────────────────────────────────────────────────

def build_risk_engine_payload(
    trades: list | None       = None,
    account_size: float       = 25000.0,
    risk_pct: float           = 1.0,
    entry: float | None       = None,
    stop: float | None        = None,
    target: float | None      = None,
    direction: str            = 'LONG',
) -> dict:
    """
    Full risk-engine payload used by the /risk-engine-data endpoint
    and injected into build_harvey_payload().
    """
    trades = trades or []

    re_state = load_re_state()
    acct     = float(re_state.get('account_size', account_size))
    r_pct    = float(re_state.get('risk_pct',    risk_pct))

    # Position size
    if entry is not None and stop is not None:
        pos = compute_position_size(acct, r_pct, entry, stop)
    else:
        pos = {'max_units': None, 'risk_dollars': round(acct * r_pct / 100, 2),
               'risk_per_unit': None, 'valid': False, 'note': 'No active trade params.'}

    # R/R
    if entry is not None and stop is not None and target is not None:
        rr = compute_rr(entry, stop, target, direction)
    else:
        rr = {'rr': None, 'valid': False, 'note': 'No trade params — enter entry/stop/target.'}

    # Drawdown
    dd = compute_drawdown_status(trades, acct)

    # Session losses
    sl = compute_session_loss_count(trades)

    # Determine master STOP_TRADING flag — persist when triggered, allow manual reset
    stop_trading = bool(re_state.get('stop_trading', False))
    stop_reason  = str(re_state.get('stop_reason', ''))

    # Auto-trigger: consecutive losses
    if sl['stop_triggered'] and not stop_trading:
        stop_trading = True
        stop_reason  = sl['note']
        re_state['stop_trading'] = True
        re_state['stop_reason']  = stop_reason
        save_re_state(re_state)

    # Auto-trigger: daily or weekly drawdown breach
    if (dd['daily_breach'] or dd['weekly_breach']) and not stop_trading:
        stop_trading = True
        stop_reason  = dd['status_note']
        re_state['stop_trading'] = True
        re_state['stop_reason']  = stop_reason
        save_re_state(re_state)

    return {
        'account_size':        acct,
        'risk_pct':            r_pct,
        'position_size':       pos,
        'rr':                  rr,
        'drawdown':            dd,
        'session_losses':      sl,
        'stop_trading':        stop_trading,
        'stop_reason':         stop_reason,
        'last_updated':        re_state.get('last_updated', ''),
    }


def reset_stop_trading() -> dict:
    """Manually clear the STOP_TRADING flag (e.g., new trading day)."""
    state = load_re_state()
    state['stop_trading'] = False
    state['stop_reason']  = ''
    save_re_state(state)
    return {'status': 'ok', 'stop_trading': False}


def update_re_settings(account_size: float | None = None, risk_pct: float | None = None) -> dict:
    state = load_re_state()
    if account_size is not None:
        state['account_size'] = float(account_size)
    if risk_pct is not None:
        state['risk_pct'] = float(risk_pct)
    save_re_state(state)
    return state
