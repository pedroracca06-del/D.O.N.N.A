"""donna_state.py — read/write functions for all DONNA JSON state files."""
from __future__ import annotations

import json

from donna_config import (
    RISK_STATE_FILE, ALERTS_FILE, ASSISTANT_FILE, SETTINGS_FILE,
    MACRO_EVENTS_FILE, JOURNAL_FILE,
    DEFAULT_RISK_STATE, DEFAULT_ASSISTANT_STATE, DEFAULT_SETTINGS, DEFAULT_MACRO_EVENTS,
    now_ny, now_utc, utc_now_iso, day_name, session_label,
)


# ── Generic JSON I/O ──────────────────────────────────────────
def read_json_file(path, default):
    try:
        if not path.exists():
            return default
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def write_json_file(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


# ── Bootstrap ─────────────────────────────────────────────────
def ensure_files():
    if not RISK_STATE_FILE.exists():
        write_json_file(RISK_STATE_FILE, DEFAULT_RISK_STATE)
    if not ALERTS_FILE.exists():
        write_json_file(ALERTS_FILE, [])
    if not ASSISTANT_FILE.exists():
        write_json_file(ASSISTANT_FILE, DEFAULT_ASSISTANT_STATE)
    if not SETTINGS_FILE.exists():
        write_json_file(SETTINGS_FILE, DEFAULT_SETTINGS)
    if not MACRO_EVENTS_FILE.exists():
        write_json_file(MACRO_EVENTS_FILE, DEFAULT_MACRO_EVENTS)
    if not JOURNAL_FILE.exists():
        write_json_file(JOURNAL_FILE, [])


# ── Risk state ────────────────────────────────────────────────
def load_risk_state() -> dict:
    data = read_json_file(RISK_STATE_FILE, DEFAULT_RISK_STATE)
    if not isinstance(data, dict):
        data = dict(DEFAULT_RISK_STATE)
    merged = dict(DEFAULT_RISK_STATE)
    merged.update(data)
    merged['donna_time_utc'] = now_utc().isoformat()
    merged['donna_time_ny']  = now_ny().isoformat()
    merged['donna_day']      = day_name()
    merged['donna_session']  = session_label()
    merged['last_updated']   = utc_now_iso()
    merged.setdefault('event_time_ny', now_ny().replace(minute=0, second=0, microsecond=0).isoformat())
    return merged


def save_risk_state(state: dict):
    s = dict(state)
    s['last_updated'] = utc_now_iso()
    write_json_file(RISK_STATE_FILE, s)


# ── Alert history ─────────────────────────────────────────────
def load_alert_history() -> list:
    data = read_json_file(ALERTS_FILE, [])
    return data if isinstance(data, list) else []


def save_alert_history(alerts: list):
    write_json_file(ALERTS_FILE, alerts[:50])


# ── Assistant state ───────────────────────────────────────────
def load_assistant_state() -> dict:
    data = read_json_file(ASSISTANT_FILE, DEFAULT_ASSISTANT_STATE)
    if not isinstance(data, dict):
        data = dict(DEFAULT_ASSISTANT_STATE)
    merged = dict(DEFAULT_ASSISTANT_STATE)
    merged.update(data)
    if not isinstance(merged.get('tasks'), list):
        merged['tasks'] = list(DEFAULT_ASSISTANT_STATE['tasks'])
    if not isinstance(merged.get('reminders'), list):
        merged['reminders'] = list(DEFAULT_ASSISTANT_STATE['reminders'])
    merged['last_updated'] = utc_now_iso()
    return merged


def save_assistant_state(state: dict):
    s = dict(state)
    s['last_updated'] = utc_now_iso()
    write_json_file(ASSISTANT_FILE, s)


# ── Settings ──────────────────────────────────────────────────
def load_settings() -> dict:
    data = read_json_file(SETTINGS_FILE, DEFAULT_SETTINGS)
    if not isinstance(data, dict):
        data = dict(DEFAULT_SETTINGS)
    merged = dict(DEFAULT_SETTINGS)
    merged.update(data)
    merged['last_updated'] = utc_now_iso()
    return merged


# ── Macro events ──────────────────────────────────────────────
def load_macro_events() -> dict:
    data = read_json_file(MACRO_EVENTS_FILE, DEFAULT_MACRO_EVENTS)
    if not isinstance(data, dict):
        data = dict(DEFAULT_MACRO_EVENTS)
    if not isinstance(data.get('events'), list):
        data['events'] = list(DEFAULT_MACRO_EVENTS['events'])
    return data


# ── Journal ───────────────────────────────────────────────────
def load_journal() -> list:
    data = read_json_file(JOURNAL_FILE, [])
    return data if isinstance(data, list) else []


def save_journal(trades: list):
    write_json_file(JOURNAL_FILE, trades)


def compute_journal_stats(trades: list) -> dict:
    from datetime import date, timedelta

    empty_daily = {'today': 0.0, 'yesterday': 0.0, 'this_week': 0.0}
    if not trades:
        return {
            'total': 0, 'wins': 0, 'losses': 0, 'breakevens': 0,
            'win_rate': 0.0, 'avg_win': 0.0, 'avg_loss': 0.0,
            'profit_factor': 0.0, 'best_regime': '—', 'worst_regime': '—',
            'by_regime': {}, 'by_session': {}, 'daily_pnl': empty_daily,
        }

    today_str     = date.today().isoformat()
    yesterday_str = (date.today() - timedelta(days=1)).isoformat()
    week_start    = (date.today() - timedelta(days=date.today().weekday())).isoformat()

    wins, losses, breakevens = 0, 0, 0
    win_pnl, loss_pnl = [], []
    regime_buckets: dict = {}
    session_buckets: dict = {}
    daily_today = daily_yesterday = daily_week = 0.0

    for t in trades:
        outcome   = str(t.get('outcome', '')).upper()
        direction = str(t.get('direction', 'LONG')).upper()

        # P&L priority: realized_pnl if present, else calculate from entry/exit/size
        realized = t.get('realized_pnl')
        if realized is not None:
            try:
                pnl = float(realized)
            except (TypeError, ValueError):
                pnl = 0.0
        else:
            try:
                entry = float(t.get('entry_price') or 0)
                exit_ = float(t.get('exit_price') or 0)
                size  = float(t.get('size') or 1)
            except Exception:
                entry, exit_, size = 0.0, 0.0, 1.0
            pnl = (exit_ - entry) * size if direction == 'LONG' else (entry - exit_) * size

        if outcome == 'WIN':
            wins += 1
            win_pnl.append(pnl)
        elif outcome == 'LOSS':
            losses += 1
            loss_pnl.append(abs(pnl))
        else:
            breakevens += 1

        trade_date = str(t.get('trade_date', ''))
        if trade_date == today_str:
            daily_today += pnl
        elif trade_date == yesterday_str:
            daily_yesterday += pnl
        if trade_date >= week_start:
            daily_week += pnl

        regime  = str(t.get('active_regime', 'UNKNOWN'))
        session = str(t.get('session', 'UNKNOWN'))

        for bucket, key in [(regime_buckets, regime), (session_buckets, session)]:
            if key not in bucket:
                bucket[key] = {'wins': 0, 'losses': 0, 'breakevens': 0}
            if outcome == 'WIN':
                bucket[key]['wins'] += 1
            elif outcome == 'LOSS':
                bucket[key]['losses'] += 1
            else:
                bucket[key]['breakevens'] += 1

    total         = len(trades)
    win_rate      = round(wins / total * 100, 1) if total else 0.0
    avg_win       = round(sum(win_pnl) / len(win_pnl), 2) if win_pnl else 0.0
    avg_loss      = round(sum(loss_pnl) / len(loss_pnl), 2) if loss_pnl else 0.0
    total_win_pnl  = sum(win_pnl)
    total_loss_pnl = sum(loss_pnl)
    profit_factor  = round(total_win_pnl / total_loss_pnl, 2) if total_loss_pnl else 0.0

    def regime_wr(b):
        t_ = b['wins'] + b['losses'] + b['breakevens']
        return round(b['wins'] / t_ * 100, 1) if t_ else 0.0

    by_regime  = {k: {**v, 'win_rate': regime_wr(v)} for k, v in regime_buckets.items()}
    by_session = {k: {**v, 'win_rate': regime_wr(v)} for k, v in session_buckets.items()}

    best_regime  = max(by_regime,  key=lambda k: by_regime[k]['win_rate'],  default='—') if by_regime  else '—'
    worst_regime = min(by_regime,  key=lambda k: by_regime[k]['win_rate'],  default='—') if by_regime  else '—'

    return {
        'total': total, 'wins': wins, 'losses': losses, 'breakevens': breakevens,
        'win_rate': win_rate, 'avg_win': avg_win, 'avg_loss': avg_loss,
        'profit_factor': profit_factor, 'best_regime': best_regime, 'worst_regime': worst_regime,
        'by_regime': by_regime, 'by_session': by_session,
        'daily_pnl': {
            'today':     round(daily_today, 2),
            'yesterday': round(daily_yesterday, 2),
            'this_week': round(daily_week, 2),
        },
    }
