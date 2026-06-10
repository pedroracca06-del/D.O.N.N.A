"""
engines/market_memory.py

Persistent intra-session structural memory.

Architecture principle:
  Pine events fire once — market structure persists.
  This module tracks what the market has DONE this session, not just
  what it is doing right now. Structural evidence (OTE defenses, continuation
  persistence, reclaim failures) accumulates across evaluation cycles and
  feeds Claude's interpretation without re-triggering Pine.

State is session-scoped (cleared on session boundary).
Persists to data/donna_market_memory.json between poll cycles.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from core.config import DATA_DIR, now_ny

_MEMORY_FILE = DATA_DIR / 'donna_market_memory.json'
_MAX_EVENTS  = 200   # ring-buffer cap per symbol


# ── Persistence ───────────────────────────────────────────────────────────────

def _load() -> dict:
    try:
        return json.loads(_MEMORY_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _save(data: dict) -> None:
    try:
        _MEMORY_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')
    except Exception:
        pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _et_str() -> str:
    return now_ny().strftime('%H:%M:%S')


def _et_date() -> str:
    return now_ny().strftime('%Y-%m-%d')


def _minutes_since(start_hms: str | None) -> float:
    """Elapsed minutes since a HH:MM:SS string (same calendar day)."""
    if not start_hms:
        return 0.0
    try:
        now = now_ny()
        h, m, s = start_hms.split(':')
        start_mins = int(h) * 60 + int(m) + int(s) / 60
        now_mins   = now.hour * 60 + now.minute + now.second / 60
        return max(0.0, now_mins - start_mins)
    except Exception:
        return 0.0


def _get_or_init(data: dict, symbol: str, session: str, date: str) -> dict:
    """Return symbol block, resetting it if session or date has changed."""
    sym = data.get(symbol, {})
    if sym.get('session') != session or sym.get('session_date') != date:
        sym = {
            'session':      session,
            'session_date': date,
            'last_eval':    {},
            'events':       [],
        }
    data[symbol] = sym
    return sym


def _append(sym: dict, event: dict) -> None:
    events = sym.setdefault('events', [])
    events.append(event)
    if len(events) > _MAX_EVENTS:
        sym['events'] = events[-_MAX_EVENTS:]


# ── Tally ─────────────────────────────────────────────────────────────────────

def _tally(events: list, direction: str) -> dict:
    """
    Compute per-direction summary from the event list.
    O(n) over events per symbol — fine for session-scoped data (~200 events max).
    """
    d             = direction.upper()
    ote_touches   = 0
    ote_holds     = 0
    ote_conts     = 0
    ote_failures  = 0
    cont_starts   = 0
    cont_active   = False
    cont_start_et = None
    reclaim_fails = 0
    reclaim_succ  = 0

    for e in events:
        if e.get('dir', '').upper() != d:
            continue
        t = e.get('t', '')
        if   t == 'OTE_TOUCH':      ote_touches  += 1
        elif t == 'OTE_HOLD':       ote_holds    += 1
        elif t == 'OTE_CONT':       ote_conts    += 1
        elif t == 'OTE_FAIL':       ote_failures += 1
        elif t == 'CONT_OPEN':
            cont_starts  += 1
            cont_start_et = e.get('et')
            cont_active   = True
        elif t == 'CONT_CLOSE':
            cont_active   = False
            cont_start_et = None
        elif t == 'RECLAIM_FAIL':   reclaim_fails += 1
        elif t == 'RECLAIM_SUCCESS':reclaim_succ  += 1

    cont_minutes = _minutes_since(cont_start_et) if cont_active and cont_start_et else 0.0

    return {
        'ote_touches':   ote_touches,
        'ote_holds':     ote_holds,
        'ote_conts':     ote_conts,
        'ote_failures':  ote_failures,
        'cont_starts':   cont_starts,
        'cont_active':   cont_active,
        'cont_minutes':  round(cont_minutes, 1),
        'reclaim_fails': reclaim_fails,
        'reclaim_succ':  reclaim_succ,
    }


# ── Public API ────────────────────────────────────────────────────────────────

def update(
    symbol:         str,
    session_ctx:    dict,
    price_ote_eval: dict,
    pros_eval:      dict,
    chart_ctx:      dict,
) -> None:
    """
    Called every evaluation cycle. Compares current state against the previous
    cycle snapshot and records structural transition events. Must be called
    after all deterministic evaluators run, before Claude evaluation.

    Events recorded:
      OTE_TOUCH  — price just entered OTE zone
      OTE_HOLD   — price still inside OTE zone (persistence bar)
      OTE_CONT   — price exited OTE zone toward bias (bullish/bearish continuation)
      OTE_FAIL   — price exited OTE zone against bias (structural failure)
      CONT_OPEN  — Pine/sticky CONT became CONFIRMED this cycle
      CONT_CLOSE — CONT was CONFIRMED, now it is not
    """
    session = session_ctx.get('session', 'UNKNOWN')
    date    = _et_date()
    et      = _et_str()

    data = _load()
    sym  = _get_or_init(data, symbol, session, date)
    prev = sym.get('last_eval', {})

    price = None
    try:
        price = float(chart_ctx.get('price') or 0) or None
    except (TypeError, ValueError):
        pass

    # ── Current OTE state ─────────────────────────────────────────────────────
    in_ote  = price_ote_eval.get('has_ote', False)
    ote_dir = price_ote_eval.get('direction') if in_ote else None
    fib_pct = price_ote_eval.get('fib_pct', 0.0)

    # ── Current CONT state (from pros_eval) ───────────────────────────────────
    # cont_quality == 'STRONG' means Pine or sticky logic has CONFIRMED continuation.
    # direction from pros_eval is 'LONG', 'SHORT', or 'N/A'.
    cont_quality = pros_eval.get('cont_quality', 'UNKNOWN')
    pros_dir     = pros_eval.get('direction', 'N/A').upper()
    cont_long    = cont_quality == 'STRONG' and pros_dir == 'LONG'
    cont_short   = cont_quality == 'STRONG' and pros_dir == 'SHORT'

    prev_in_ote     = prev.get('in_ote', False)
    prev_ote_dir    = prev.get('ote_dir')
    prev_price      = prev.get('price')
    prev_cont_long  = prev.get('cont_long', False)
    prev_cont_short = prev.get('cont_short', False)

    # ── OTE transition detection ──────────────────────────────────────────────
    if in_ote and not prev_in_ote:
        # Just entered OTE zone
        _append(sym, {'t': 'OTE_TOUCH', 'dir': ote_dir, 'price': price,
                       'fib': round(fib_pct, 3), 'et': et})

    elif in_ote and prev_in_ote and ote_dir == prev_ote_dir:
        # Still inside OTE zone — structural persistence bar
        _append(sym, {'t': 'OTE_HOLD', 'dir': ote_dir, 'price': price,
                       'fib': round(fib_pct, 3), 'et': et})

    elif not in_ote and prev_in_ote and prev_ote_dir and price and prev_price:
        # Exited OTE zone — determine resolution direction
        bullish_exit = price > prev_price
        if prev_ote_dir == 'LONG':
            evt = 'OTE_CONT' if bullish_exit else 'OTE_FAIL'
        else:
            evt = 'OTE_CONT' if not bullish_exit else 'OTE_FAIL'
        _append(sym, {'t': evt, 'dir': prev_ote_dir, 'price': price, 'et': et})

    # ── CONT transition detection ─────────────────────────────────────────────
    if cont_long and not prev_cont_long:
        _append(sym, {'t': 'CONT_OPEN',  'dir': 'LONG',  'et': et})
    elif not cont_long and prev_cont_long:
        _append(sym, {'t': 'CONT_CLOSE', 'dir': 'LONG',  'et': et})

    if cont_short and not prev_cont_short:
        _append(sym, {'t': 'CONT_OPEN',  'dir': 'SHORT', 'et': et})
    elif not cont_short and prev_cont_short:
        _append(sym, {'t': 'CONT_CLOSE', 'dir': 'SHORT', 'et': et})

    # ── Snapshot this cycle ───────────────────────────────────────────────────
    sym['last_eval'] = {
        'in_ote':      in_ote,
        'ote_dir':     ote_dir,
        'cont_long':   cont_long,
        'cont_short':  cont_short,
        'price':       price,
        'et':          et,
    }

    _save(data)


def record_reclaim(symbol: str, session_ctx: dict, direction: str, success: bool) -> None:
    """
    Manually record a reclaim attempt (called when execution bridge detects
    a level reclaim event from the signal stream).
    """
    session = session_ctx.get('session', 'UNKNOWN')
    date    = _et_date()
    data    = _load()
    sym     = _get_or_init(data, symbol, session, date)
    _append(sym, {
        't':   'RECLAIM_SUCCESS' if success else 'RECLAIM_FAIL',
        'dir': direction.upper(),
        'et':  _et_str(),
    })
    _save(data)


def get_summary(symbol: str) -> dict:
    """Return structured per-direction summary for this session."""
    data   = _load()
    sym    = data.get(symbol, {})
    events = sym.get('events', [])
    return {
        'session':     sym.get('session'),
        'session_date':sym.get('session_date'),
        'long':        _tally(events, 'LONG'),
        'short':       _tally(events, 'SHORT'),
        'event_count': len(events),
    }


def format_for_prompt(symbol: str) -> str:
    """
    Compact structural narrative for Claude prompt injection.
    Describes what the market has DONE this session — structural evidence
    that persists beyond individual Pine trigger cycles.

    Example output:
      MARKET MEMORY [MES | NY_AM]:
        LONG: OTE touched 3×, defended 2×, continued 1× | continuation active 18min
        SHORT: no structure this session
    """
    summary = get_summary(symbol)
    session = summary.get('session')
    if not session:
        return f'MARKET MEMORY [{symbol}]: no session data'

    lines = [f'MARKET MEMORY [{symbol} | {session}]:']

    for direction in ('LONG', 'SHORT'):
        t = summary[direction.lower()]
        parts: list[str] = []

        if t['ote_touches'] > 0:
            touch_str = f'OTE touched {t["ote_touches"]}×'
            if t['ote_holds'] > 0:
                touch_str += f', defended {t["ote_holds"]}×'
            if t['ote_conts'] > 0:
                touch_str += f', continued {t["ote_conts"]}×'
            if t['ote_failures'] > 0:
                touch_str += f', failed {t["ote_failures"]}×'
            parts.append(touch_str)

        if t['cont_active']:
            parts.append(f'continuation active {t["cont_minutes"]:.0f}min')
        elif t['cont_starts'] > 0:
            parts.append(f'continuation confirmed {t["cont_starts"]}× (now closed)')

        if t['reclaim_fails'] > 0:
            parts.append(f'reclaim failed {t["reclaim_fails"]}×')

        if parts:
            lines.append(f'  {direction}: {" | ".join(parts)}')
        else:
            lines.append(f'  {direction}: no structure this session')

    return '\n'.join(lines)
