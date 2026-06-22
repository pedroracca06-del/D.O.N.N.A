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
from typing import Optional

from core.config import SIGNAL_LOG_FILE as _LOG_FILE

# ── Config ───────────────────────────────────────────────────────────────────────

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
    orb_state:        str              = '',
    orb_bias:         str              = '',
    orb_high:         Optional[float]  = None,
    orb_mid:          Optional[float]  = None,
    orb_low:          Optional[float]  = None,
    orb_signal:       bool             = False,
    orb_phase:        str              = '',
    orb_range:        Optional[float]  = None,
    orb_entry_type:   str              = '',
    orb_entry_quality: str             = '',

    # IB
    ib_high:         Optional[float]  = None,
    ib_low:          Optional[float]  = None,
    ib_draw:         str              = '',
    ib_aligned:      Optional[bool]   = None,
    ib_tight:        bool             = False,
    ib_source:       str              = 'pros_table',

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

    # Draw Validation telemetry (logged only — not enforced)
    draw_name:       str              = '',
    draw_category:   str              = '',   # STRONG / CONDITIONAL / CIRCULAR
    draw_tp1_pts:    Optional[float]  = None,
    draw_independent: Optional[bool]  = None,

    # Strategy metadata (stored explicitly — avoids parsing setup_type in UI/query layer)
    strategy_family:  str             = '',

    # Claude rationale text (notes field from decision; combine with pre_rationale for full context)
    claude_rationale: str             = '',

    # Market Reality snapshot at signal time (self-contained — no external lookup needed months later)
    mr2_state:        str             = '',
    mr2_score:        Optional[int]   = None,
    mr2_block_longs:  bool            = False,
    mr2_block_shorts: bool            = False,
    mr2_block_reason: str             = '',

    # Directional Pressure snapshot at signal time
    dp_dominance:     str             = '',
    dp_conviction:    str             = '',
    dp_bullish:       Optional[float] = None,
    dp_bearish:       Optional[float] = None,
    dp_net:           Optional[float] = None,

    # Cross-reference to donna_reasoning_trace.json for full intelligence audit
    reasoning_trace_id: str           = '',

    # Screenshot
    screenshot:      str              = '',

    # Session development telemetry — for PROS maturity audit
    # ny_open_minutes: minutes since 9:30 ET at signal time; None outside NY sessions
    # ib_window_closed: True when IB window has passed (10:30 ET)
    # ib_maturity: derived label — UNCLEAR / FORMING / MATURE / CLOSED_NO_DRAW
    ny_open_minutes:  Optional[int]   = None,
    ib_window_closed: bool            = False,
) -> dict:
    """
    Write one signal detection record to the log.
    Returns the full entry dict (caller can use entry['id'] for the ID).
    Thread-safe, non-blocking on failure — returns {} on error.
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
        'orb_state':        orb_state,
        'orb_bias':         orb_bias,
        'orb_high':         orb_high,
        'orb_mid':          orb_mid,
        'orb_low':          orb_low,
        'orb_signal':       orb_signal,
        'orb_phase':        orb_phase,
        'orb_range':        orb_range,
        'orb_entry_type':   orb_entry_type,
        'orb_entry_quality': orb_entry_quality,

        # IB
        'ib_high':        ib_high,
        'ib_low':         ib_low,
        'ib_draw':        ib_draw,
        'ib_aligned':     ib_aligned,
        'ib_tight':       ib_tight,
        'ib_source':      ib_source,

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

        # Draw Validation telemetry
        'draw_name':       draw_name,
        'draw_category':   draw_category,
        'draw_tp1_pts':    draw_tp1_pts,
        'draw_independent': draw_independent,

        # Strategy metadata
        'strategy_family':  strategy_family,

        # Rationale (Claude's assessment; read alongside pre_rationale for full reasoning context)
        'claude_rationale': claude_rationale,

        # Market Reality snapshot at signal time
        'mr2_state':        mr2_state,
        'mr2_score':        mr2_score,
        'mr2_block_longs':  mr2_block_longs,
        'mr2_block_shorts': mr2_block_shorts,
        'mr2_block_reason': mr2_block_reason,

        # Directional Pressure snapshot at signal time
        'dp_dominance':     dp_dominance,
        'dp_conviction':    dp_conviction,
        'dp_bullish':       dp_bullish,
        'dp_bearish':       dp_bearish,
        'dp_net':           dp_net,

        # Cross-reference to donna_reasoning_trace.json (full intelligence audit trail)
        'reasoning_trace_id': reasoning_trace_id,

        # Screenshot
        'screenshot':     screenshot,

        # Session development telemetry
        'ny_open_minutes':  ny_open_minutes,
        'ib_window_closed': ib_window_closed,
        'ib_maturity': (
            'MATURE'         if ib_window_closed and ib_draw not in ('', 'UNCLEAR') else
            'CLOSED_NO_DRAW' if ib_window_closed and ib_draw in ('', 'UNCLEAR')    else
            'FORMING'        if not ib_window_closed and ib_draw not in ('', 'UNCLEAR') else
            'UNCLEAR'
        ),
    }

    with _lock:
        try:
            entries = _load()

            # --- Direction churn telemetry ---
            # Find the most recent prior entry for the same symbol on the same date.
            # Used to detect direction flips and IB draw flips at write time so each
            # entry is self-contained — no post-hoc join required for analysis.
            _prev = next(
                (e for e in entries
                 if e.get('symbol') == symbol
                 and e.get('date') == entry['date']
                 and e.get('pros_direction', '') != ''),
                None,
            )
            _prev_dir = _prev.get('pros_direction', '') if _prev else ''
            _prev_ib  = _prev.get('ib_draw', '')        if _prev else ''
            _this_dir = pros_direction
            _this_ib  = ib_draw

            _dir_flip = bool(_prev_dir and _this_dir and _prev_dir != _this_dir)
            _ib_flip  = bool(_prev_ib  and _this_ib  and _prev_ib  != _this_ib)

            # Minutes since most recent prior direction flip for this symbol today.
            # 0.0 if this entry IS the flip; None if no prior flip exists.
            _mins_since_flip: float | None = None
            if _dir_flip:
                _mins_since_flip = 0.0
            else:
                _last_flip = next(
                    (e for e in entries
                     if e.get('symbol') == symbol
                     and e.get('date') == entry['date']
                     and e.get('direction_flip')),
                    None,
                )
                if _last_flip:
                    try:
                        _t0 = datetime.fromisoformat(_last_flip['timestamp'])
                        _t1 = datetime.fromisoformat(entry['timestamp'])
                        _mins_since_flip = round((_t1 - _t0).total_seconds() / 60, 1)
                    except Exception:
                        pass

            entry['direction_flip']       = _dir_flip
            entry['ib_draw_flip']         = _ib_flip
            entry['prev_direction']       = _prev_dir
            entry['prev_ib_draw']         = _prev_ib
            entry['mins_since_last_flip'] = _mins_since_flip

            entries.insert(0, entry)          # newest first
            if len(entries) > _MAX_ENTRIES:
                entries = entries[:_MAX_ENTRIES]
            _save(entries)
            _flip_tag = ' FLIP' if _dir_flip else ''
            print(f'[signal_log] {entry_id}  {symbol}  {pre_signal}  grade={grade or "?"}  alert={alert_type or "none"}{_flip_tag}')
        except Exception as e:
            print(f'[signal_log] write error: {e}')
            return {}

    return entry


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


def get_ny_open_pros(n: int = 500) -> list:
    """All NY_OPEN PROS signals for session development analysis."""
    with _lock:
        entries = _load()
    return [
        e for e in entries
        if e.get('session') == 'NY_OPEN' and e.get('pros_signal')
    ][:n]


def get_direction_churn(n: int = 500) -> dict:
    """
    Direction churn analysis for alert volume investigation.

    For each direction flip in NY sessions, captures:
      - Whether the IB draw also flipped (IB-driven) or stayed (interpretation-only)
      - How long the new direction held before the next flip
      - Session age at flip time
      - Rapid flip-back rate (flips reversed within 2 minutes)

    The IB-driven vs direction-only split is the primary signal for:
      "Is this real market structure change or indicator interpretation instability?"
    """
    with _lock:
        entries = _load()

    ny_sessions = {'NY_OPEN', 'NY_AM', 'NY_PM'}

    # Collect all flip events
    flip_events: list[dict] = []
    symbols = sorted({e.get('symbol', '') for e in entries if e.get('symbol')})
    dates   = sorted({e.get('date', '')   for e in entries if e.get('date')})

    for sym in symbols:
        for date in dates:
            day = sorted(
                [e for e in entries
                 if e.get('symbol') == sym
                 and e.get('date') == date
                 and e.get('session') in ny_sessions],
                key=lambda x: x.get('timestamp', ''),
            )
            if not day:
                continue

            for i, e in enumerate(day):
                if not e.get('direction_flip'):
                    continue

                # Duration until the next flip for this symbol+date
                next_flip = next(
                    (e2 for e2 in day[i + 1:] if e2.get('direction_flip')),
                    None,
                )
                if next_flip:
                    try:
                        t0 = datetime.fromisoformat(e['timestamp'])
                        t1 = datetime.fromisoformat(next_flip['timestamp'])
                        held_mins = round((t1 - t0).total_seconds() / 60, 1)
                    except Exception:
                        held_mins = None
                else:
                    held_mins = None  # direction held until end of observed window

                flip_events.append({
                    'symbol':                    sym,
                    'date':                      date,
                    'timestamp_et':              e.get('timestamp_et', ''),
                    'session':                   e.get('session', ''),
                    'ny_open_minutes':           e.get('ny_open_minutes'),
                    'from_direction':            e.get('prev_direction', ''),
                    'to_direction':              e.get('pros_direction', ''),
                    'ib_draw_also_flipped':      e.get('ib_draw_flip', False),
                    'ib_draw_before':            e.get('prev_ib_draw', ''),
                    'ib_draw_after':             e.get('ib_draw', ''),
                    'ib_maturity_at_flip':       e.get('ib_maturity', ''),
                    'ib_window_closed_at_flip':  e.get('ib_window_closed', False),
                    'phase_at_flip':             e.get('pros_phase', ''),
                    'grade_at_flip':             e.get('grade', ''),
                    'alert_type_at_flip':        e.get('alert_type', ''),
                    'held_until_next_flip_mins': held_mins,
                })

    flip_events = flip_events[:n]

    # Summary statistics
    total = len(flip_events)
    ib_driven   = [f for f in flip_events if f['ib_draw_also_flipped']]
    dir_only    = [f for f in flip_events if not f['ib_draw_also_flipped']]
    rapid_backs = [f for f in flip_events
                   if f['held_until_next_flip_mins'] is not None
                   and f['held_until_next_flip_mins'] < 2.0]
    early_flips = [f for f in flip_events
                   if f['ny_open_minutes'] is not None
                   and f['ny_open_minutes'] < 30]

    def _by_symbol(lst):
        out: dict[str, int] = {}
        for f in lst:
            out[f['symbol']] = out.get(f['symbol'], 0) + 1
        return out

    held_values = [f['held_until_next_flip_mins'] for f in flip_events
                   if f['held_until_next_flip_mins'] is not None]
    avg_held = round(sum(held_values) / len(held_values), 1) if held_values else None

    return {
        'total_flips':              total,
        'ib_driven_flips':          len(ib_driven),
        'direction_only_flips':     len(dir_only),
        'rapid_flip_backs_lt2min':  len(rapid_backs),
        'early_session_flips_lt30': len(early_flips),
        'avg_held_mins':            avg_held,
        'by_symbol':                _by_symbol(flip_events),
        # Classification: IB-driven flips correlate with real market structure change;
        # direction-only flips (IB draw unchanged) are the primary instability signal.
        'instability_ratio': round(len(dir_only) / total, 2) if total else None,
        'flips': sorted(flip_events, key=lambda x: (x['date'], x['timestamp_et'])),
    }


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
