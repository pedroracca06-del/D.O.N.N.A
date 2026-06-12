"""donna_state.py — read/write functions for all DONNA JSON state files."""
from __future__ import annotations

import json

from core.config import (
    RISK_STATE_FILE, ALERTS_FILE, ASSISTANT_FILE, SETTINGS_FILE,
    MACRO_EVENTS_FILE, JOURNAL_FILE, REJECTIONS_FILE,
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
    if not REJECTIONS_FILE.exists():
        write_json_file(REJECTIONS_FILE, [])


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


# ── Rejection history ─────────────────────────────────────────
def load_rejections() -> list:
    data = read_json_file(REJECTIONS_FILE, [])
    return data if isinstance(data, list) else []


def save_rejections(rejections: list):
    write_json_file(REJECTIONS_FILE, rejections[:200])


# ── Journal ───────────────────────────────────────────────────
def load_journal() -> list:
    data = read_json_file(JOURNAL_FILE, [])
    return data if isinstance(data, list) else []


def save_journal(trades: list):
    write_json_file(JOURNAL_FILE, trades)


def update_trade_thesis_analysis(order_id: str, analysis: dict) -> bool:
    """
    Patch a thesis_analysis block onto a journal entry by order_id.
    Used for manual re-analysis or external callers.
    Returns True if entry was found and updated.
    """
    trades = load_journal()
    for i, t in enumerate(trades):
        if str(t.get('order_id', '')) == order_id:
            trades[i] = {**t, 'thesis_analysis': analysis}
            save_journal(trades)
            return True
    return False


def compute_journal_stats(trades: list) -> dict:
    from datetime import date, timedelta

    empty_daily = {'today': 0.0, 'yesterday': 0.0, 'this_week': 0.0}
    if not trades:
        return {
            'total': 0, 'wins': 0, 'losses': 0, 'breakevens': 0,
            'win_rate': 0.0, 'avg_win': 0.0, 'avg_loss': 0.0,
            'profit_factor': 0.0, 'best_regime': '—', 'worst_regime': '—',
            'by_regime': {}, 'by_session': {}, 'by_strategy_family': {}, 'daily_pnl': empty_daily,
        }

    today_str     = date.today().isoformat()
    yesterday_str = (date.today() - timedelta(days=1)).isoformat()
    week_start    = (date.today() - timedelta(days=date.today().weekday())).isoformat()

    wins, losses, breakevens = 0, 0, 0
    win_pnl, loss_pnl = [], []
    regime_buckets: dict       = {}
    session_buckets: dict      = {}
    setup_type_buckets: dict   = {}
    strategy_family_buckets: dict = {}
    behavioral_freq: dict      = {}
    emotional_buckets: dict    = {}
    behavioral_error_count     = 0
    daily_today = daily_yesterday = daily_week = 0.0

    def _bucket_outcome(bucket, key, outcome):
        if key not in bucket:
            bucket[key] = {'wins': 0, 'losses': 0, 'breakevens': 0, 'pnl': 0.0}
        if outcome == 'WIN':
            bucket[key]['wins'] += 1
        elif outcome == 'LOSS':
            bucket[key]['losses'] += 1
        else:
            bucket[key]['breakevens'] += 1

    for t in trades:
        outcome   = str(t.get('outcome', '')).upper()
        direction = str(t.get('direction', 'LONG')).upper()

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

        # Standard breakdowns
        regime          = str(t.get('active_regime', 'UNKNOWN'))
        session         = str(t.get('session', 'UNKNOWN'))
        setup_type      = str(t.get('setup_type', '')) or 'Untagged'
        strategy_family = str(t.get('strategy_family', 'UNKNOWN'))

        _bucket_outcome(regime_buckets, regime, outcome)
        regime_buckets[regime]['pnl'] += pnl
        _bucket_outcome(session_buckets, session, outcome)
        session_buckets[session]['pnl'] += pnl
        _bucket_outcome(setup_type_buckets, setup_type, outcome)
        setup_type_buckets[setup_type]['pnl'] += pnl
        _bucket_outcome(strategy_family_buckets, strategy_family, outcome)

        # Behavioral tracking
        flags = t.get('behavioral_flags', []) or []
        if flags:
            behavioral_error_count += 1
            for flag in flags:
                behavioral_freq[flag] = behavioral_freq.get(flag, 0) + 1

        # Emotional state correlation
        estate = str(t.get('emotional_state', '') or '').strip().upper()
        if estate:
            _bucket_outcome(emotional_buckets, estate, outcome)
            emotional_buckets[estate]['pnl'] = emotional_buckets[estate].get('pnl', 0.0) + pnl

    total          = len(trades)
    win_rate       = round(wins / total * 100, 1) if total else 0.0
    avg_win        = round(sum(win_pnl) / len(win_pnl), 2) if win_pnl else 0.0
    avg_loss       = round(sum(loss_pnl) / len(loss_pnl), 2) if loss_pnl else 0.0
    total_win_pnl  = sum(win_pnl)
    total_loss_pnl = sum(loss_pnl)
    profit_factor  = round(total_win_pnl / total_loss_pnl, 2) if total_loss_pnl else 0.0
    loss_rate      = round(losses / total * 100, 1) if total else 0.0
    expectancy     = round((win_rate / 100 * avg_win) - (loss_rate / 100 * avg_loss), 2)

    def _enrich(bucket):
        return {
            k: {**v, 'win_rate': round(v['wins'] / (v['wins'] + v['losses'] + v['breakevens']) * 100, 1)
                if (v['wins'] + v['losses'] + v['breakevens']) else 0.0,
                'pnl': round(v.get('pnl', 0.0), 2)}
            for k, v in bucket.items()
        }

    by_regime          = _enrich(regime_buckets)
    by_session         = _enrich(session_buckets)
    by_setup_type      = _enrich(setup_type_buckets)
    by_strategy_family = _enrich(strategy_family_buckets)
    by_emotional_state = _enrich(emotional_buckets)

    best_regime  = max(by_regime, key=lambda k: by_regime[k]['win_rate'],  default='—') if by_regime  else '—'
    worst_regime = min(by_regime, key=lambda k: by_regime[k]['win_rate'],  default='—') if by_regime  else '—'

    # Behavioral frequency sorted by frequency desc
    behavioral_sorted = sorted(behavioral_freq.items(), key=lambda x: x[1], reverse=True)

    return {
        'total': total, 'wins': wins, 'losses': losses, 'breakevens': breakevens,
        'win_rate': win_rate, 'avg_win': avg_win, 'avg_loss': avg_loss,
        'profit_factor': profit_factor, 'expectancy': expectancy,
        'best_regime': best_regime, 'worst_regime': worst_regime,
        'by_regime': by_regime, 'by_session': by_session,
        'by_setup_type': by_setup_type,
        'by_strategy_family': by_strategy_family,
        'by_emotional_state': by_emotional_state,
        'behavioral_error_count': behavioral_error_count,
        'behavioral_frequency': dict(behavioral_sorted),
        'daily_pnl': {
            'today':     round(daily_today, 2),
            'yesterday': round(daily_yesterday, 2),
            'this_week': round(daily_week, 2),
        },
    }
