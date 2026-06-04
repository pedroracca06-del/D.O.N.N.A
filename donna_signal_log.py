"""donna_signal_log.py — NOVA Operational Intelligence Store.

Ring-buffer JSON store that captures every reasoning cycle evaluation —
regardless of whether an alert fired. This is NOVA's operational memory.

Every 60-second cycle that detects a signal (before Claude, during Claude,
and after Claude's decision) is recorded with full context:
  - Instrument + price snapshot
  - Session + session quality
  - PROS state (phase, direction, OTE, quality)
  - ORB state (bias, levels, phase)
  - IB draw + alignment
  - Invalidation flags
  - Deterministic pre-classification
  - Claude's full decision (grade, type, levels, rationale)
  - Macro state (VIX, regime, macro_risk)
  - Screenshot path

No-signal cycles (where deterministic layer found nothing) are NOT logged —
only cycles where a signal was detected and Claude was called.

Capacity: 10,000 entries (~18 months of active daily trading at 3 signals/day).
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Config ───────────────────────────────────────────────────────────────────────

_BASE_DIR   = Path(__file__).parent
_LOG_FILE   = _BASE_DIR / 'data' / 'donna_signal_log.json'
_MAX_ENTRIES = 10_000

_lock = threading.Lock()


# ── I/O helpers ──────────────────────────────────────────────────────────────────

def _load() -> list:
    try:
        if _LOG_FILE.exists():
            data = json.loads(_LOG_FILE.read_text(encoding='utf-8'))
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def _save(entries: list) -> None:
    try:
        _LOG_FILE.write_text(
            json.dumps(entries, indent=2, default=str),
            encoding='utf-8',
        )
    except Exception as e:
        print(f'[signal_log] save error: {e}')


# ── Timezone helper ───────────────────────────────────────────────────────────────

def _now_ny():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo('America/New_York'))
    except Exception:
        return datetime.now(timezone.utc)


# ── Main log function ─────────────────────────────────────────────────────────────

def log_cycle(
    *,
    # Instrument
    symbol:          str,
    price:           Optional[float]  = None,
    high_30:         Optional[float]  = None,
    low_30:          Optional[float]  = None,
    range_30:        Optional[float]  = None,
    change_pct:      str              = '',
    levels:          Optional[list]   = None,

    # Session
    session:         str              = '',
    session_quality: str              = '',

    # NOVA indicator state (from main table)
    nova_cmd:        str              = '',
    nova_state_val:  str              = '',
    nova_score:      str              = '',
    nova_conf:       str              = '',

    # PROS engine
    pros_phase:      str              = '',
    pros_direction:  str              = '',
    pros_signal:     bool             = False,
    pros_strength:   str              = '',
    pros_ote:        str              = '',
    pros_displ:      str              = '',
    pros_retrace:    str              = '',
    pros_cont:       str              = '',
    pros_quality:    str              = '',
    pros_stdv:       str              = '',

    # ORB
    orb_state:       str              = '',
    orb_bias:        str              = '',
    orb_high:        Optional[float]  = None,
    orb_mid:         Optional[float]  = None,
    orb_low:         Optional[float]  = None,
    orb_signal:      bool             = False,
    orb_phase:       str              = '',
    orb_range:       Optional[float]  = None,

    # IB
    ib_high:         Optional[float]  = None,
    ib_low:          Optional[float]  = None,
    ib_draw:         str              = '',
    ib_aligned:      Optional[bool]   = None,
    ib_tight:        bool             = False,

    # Invalidation
    invalidated:     bool             = False,
    inv_reason:      str              = '',

    # Deterministic pre-classification
    pre_signal:      str              = '',
    pre_setup:       str              = '',
    pre_rationale:   str              = '',

    # Claude decision
    claude_called:   bool             = False,
    alert_required:  bool             = False,
    alert_type:      str              = '',
    grade:           str              = '',
    setup_type:      str              = '',
    direction:       str              = '',
    entry_zone:      str              = '',
    stop:            str              = '',
    tp1:             str              = '',
    rr:              str              = '',
    ib_draw_claude:  str              = '',
    daily_bias:      str              = '',
    htf_4h_bias:     str              = '',
    action:          str              = '',
    notes:           str              = '',
    no_alert_reason: str              = '',

    # Macro / market
    macro_risk:      str              = '',
    vix:             Optional[float]  = None,
    regime:          str              = '',
    nq_pct:          Optional[float]  = None,
    es_pct:          Optional[float]  = None,

    # Screenshot
    screenshot:      str              = '',
) -> str:
    """
    Write one signal detection record to the log. Returns the entry ID.
    Thread-safe, non-blocking on failure.
    """
    now_ny = _now_ny()
    entry_id = f'SIG_{now_ny.strftime("%Y%m%d_%H%M%S")}_{uuid.uuid4().hex[:6].upper()}'

    entry = {
        'id':             entry_id,
        'timestamp':      datetime.now(timezone.utc).isoformat(),
        'timestamp_et':   now_ny.strftime('%Y-%m-%d %H:%M:%S ET'),
        'date':           now_ny.strftime('%Y-%m-%d'),

        # Instrument
        'symbol':         symbol,
        'price':          price,
        'high_30':        high_30,
        'low_30':         low_30,
        'range_30':       range_30,
        'change_pct':     change_pct,
        'levels':         (levels or [])[:10],

        # Session
        'session':        session,
        'session_quality': session_quality,

        # NOVA indicator
        'nova_cmd':       nova_cmd,
        'nova_state':     nova_state_val,
        'nova_score':     nova_score,
        'nova_conf':      nova_conf,

        # PROS
        'pros_phase':     pros_phase,
        'pros_direction': pros_direction,
        'pros_signal':    pros_signal,
        'pros_strength':  pros_strength,
        'pros_ote':       pros_ote,
        'pros_displ':     pros_displ,
        'pros_retrace':   pros_retrace,
        'pros_cont':      pros_cont,
        'pros_quality':   pros_quality,
        'pros_stdv':      pros_stdv,

        # ORB
        'orb_state':      orb_state,
        'orb_bias':       orb_bias,
        'orb_high':       orb_high,
        'orb_mid':        orb_mid,
        'orb_low':        orb_low,
        'orb_signal':     orb_signal,
        'orb_phase':      orb_phase,
        'orb_range':      orb_range,

        # IB
        'ib_high':        ib_high,
        'ib_low':         ib_low,
        'ib_draw':        ib_draw,
        'ib_aligned':     ib_aligned,
        'ib_tight':       ib_tight,

        # Invalidation
        'invalidated':    invalidated,
        'inv_reason':     inv_reason,

        # Pre-classification
        'pre_signal':     pre_signal,
        'pre_setup':      pre_setup,
        'pre_rationale':  pre_rationale,

        # Claude
        'claude_called':  claude_called,
        'alert_required': alert_required,
        'alert_type':     alert_type,
        'grade':          grade,
        'setup_type':     setup_type,
        'direction':      direction,
        'entry_zone':     entry_zone,
        'stop':           stop,
        'tp1':            tp1,
        'rr':             rr,
        'ib_draw_claude': ib_draw_claude,
        'daily_bias':     daily_bias,
        'htf_4h_bias':    htf_4h_bias,
        'action':         action,
        'notes':          notes,
        'no_alert_reason': no_alert_reason,

        # Macro
        'macro_risk':     macro_risk,
        'vix':            vix,
        'regime':         regime,
        'nq_pct':         nq_pct,
        'es_pct':         es_pct,

        # Screenshot
        'screenshot':     screenshot,
    }

    with _lock:
        try:
            entries = _load()
            entries.insert(0, entry)          # newest first
            if len(entries) > _MAX_ENTRIES:
                entries = entries[:_MAX_ENTRIES]
            _save(entries)
            print(f'[signal_log] {entry_id}  {symbol}  {pre_signal}  grade={grade or "?"}  alert={alert_type or "none"}')
        except Exception as e:
            print(f'[signal_log] write error: {e}')

    return entry_id


# ── Read API ─────────────────────────────────────────────────────────────────────

def get_recent(n: int = 50) -> list:
    """Return the N most recent signal log entries."""
    with _lock:
        return _load()[:n]


def get_by_symbol(symbol: str, n: int = 50) -> list:
    """Return recent entries for a specific symbol (MES, MNQ, etc.)."""
    sym = symbol.upper().replace('CME_MINI:', '').replace('1!', '')
    with _lock:
        entries = _load()
    return [e for e in entries if e.get('symbol', '').upper() == sym][:n]


def get_by_date(date: str) -> list:
    """Return all entries for a given date (YYYY-MM-DD ET)."""
    with _lock:
        entries = _load()
    return [e for e in entries if e.get('date') == date]


def get_by_grade(grade: str, n: int = 100) -> list:
    """Return recent entries with a specific grade (A, B, C, D)."""
    with _lock:
        entries = _load()
    return [e for e in entries if e.get('grade', '').upper() == grade.upper()][:n]


def get_execution_ready(n: int = 50) -> list:
    """Return recent EXECUTION_READY entries only."""
    with _lock:
        entries = _load()
    return [e for e in entries if e.get('alert_type') == 'EXECUTION_READY'][:n]


def get_stats() -> dict:
    """Summary statistics over the full log."""
    with _lock:
        entries = _load()

    if not entries:
        return {'total': 0}

    grades      = [e.get('grade', '') for e in entries if e.get('grade')]
    alert_types = [e.get('alert_type', '') for e in entries if e.get('alert_type')]
    symbols     = [e.get('symbol', '') for e in entries if e.get('symbol')]
    sessions    = [e.get('session', '') for e in entries if e.get('session')]

    def _counts(lst):
        out = {}
        for v in lst:
            out[v] = out.get(v, 0) + 1
        return dict(sorted(out.items(), key=lambda x: -x[1]))

    return {
        'total':          len(entries),
        'oldest':         entries[-1].get('timestamp_et', '') if entries else '',
        'newest':         entries[0].get('timestamp_et', '')  if entries else '',
        'by_grade':       _counts(grades),
        'by_alert_type':  _counts(alert_types),
        'by_symbol':      _counts(symbols),
        'by_session':     _counts(sessions),
        'execution_ready': sum(1 for e in entries if e.get('alert_type') == 'EXECUTION_READY'),
        'heads_up':        sum(1 for e in entries if e.get('alert_type') == 'HEADS_UP'),
        'invalidations':   sum(1 for e in entries if e.get('invalidated')),
        'grade_a':         sum(1 for e in entries if e.get('grade') == 'A'),
        'grade_b':         sum(1 for e in entries if e.get('grade') == 'B'),
    }
