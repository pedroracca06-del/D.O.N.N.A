"""
nova_feed.py — NOVA Intelligence Feed

Merges signal_log, execution_trace, computed MR2 state transitions, and the
intelligence event log into a single chronological feed.

Every card is self-contained: all context needed to understand an event is
embedded directly. reasoning_trace_id is a pointer for future drill-down.

Event types:
  SIGNAL       — HEADS_UP | EXECUTION_READY | INVALIDATION | NO_TRADE
  EXECUTION    — EXECUTED | (SKIPPED — moved to GOVERNANCE)
  GOVERNANCE   — BRIDGE_REJECTED | REJECTED | lock state changes
  MR2_CHANGE   — LONGS_BLOCKED | SHORTS_BLOCKED | LONGS_UNBLOCKED |
                 SHORTS_UNBLOCKED | STATE_CHANGE
  INTELLIGENCE — SYNTHESIS_UPDATE | MORNING_BRIEF
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Optional

from core.config import (
    SIGNAL_LOG_FILE       as _SIGNAL_LOG,
    TRACE_FILE            as _EXEC_TRACE,
    INTELLIGENCE_LOG_FILE as _INTEL_LOG,
    REASONING_TRACE_FILE,
    FEED_SYNC_FILE,
    NOVA_INGEST_SECRET,
)

_lock = threading.Lock()


# ── I/O ───────────────────────────────────────────────────────────────────────

def _read_json(path: Path) -> list:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding='utf-8'))
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []


# ── Sort key ──────────────────────────────────────────────────────────────────

def _sort_key(card: dict) -> str:
    """
    Sort key from timestamp_et ("YYYY-MM-DD HH:MM:SS ET").
    Stripping " ET" makes it lexicographically sortable since all entries are ET.
    """
    ts = card.get('timestamp_et', '')
    return ts.replace(' ET', '').strip()


# ── Empty sub-objects (avoids repeating the structure in every normalizer) ────

def _empty_mr2(from_state: str = '') -> dict:
    return {
        'from_state':           from_state,
        'state':                '',
        'score':                None,
        'block_longs':          False,
        'block_shorts':         False,
        'block_reason':         '',
        'block_longs_changed':  False,
        'block_shorts_changed': False,
    }


def _empty_dp() -> dict:
    return {'dominance': '', 'conviction': '', 'bullish': None, 'bearish': None, 'net': None}


def _empty_draw() -> dict:
    return {'name': '', 'category': '', 'tp1_pts': None, 'independent': None}


def _empty_exec() -> dict:
    return {'etf': '', 'qty': None, 'entry_ref': None, 'stop_px': None,
            'target_px': None, 'order_id': '', 'risk_usd': None, 'broker': ''}


# ── Signal log → SIGNAL cards ─────────────────────────────────────────────────

def _normalize_signal(entry: dict) -> dict:
    """
    Normalize one signal_log entry into a feed card.
    Handles both old entries (missing mr2_state / dp fields) and new ones.
    claude_rationale falls back to notes for pre-commit entries.
    """
    setup  = entry.get('setup_type', '') or entry.get('pre_setup', '') or ''
    family = entry.get('strategy_family', '') or (
        setup.split('_')[0].upper() if '_' in setup else ''
    )
    rationale = entry.get('claude_rationale', '') or entry.get('notes', '') or ''

    # subtype = alert_type when the alert fired; 'EVALUATED' when graded but suppressed.
    # pre_signal is kept separately — it's the deterministic pre-classification before Claude.
    alert_type  = entry.get('alert_type', '') or ''
    alert_fired = bool(alert_type)
    subtype     = alert_type if alert_fired else 'EVALUATED'

    return {
        'id':              f'FEED_{entry.get("id", "")}',
        'timestamp_et':    entry.get('timestamp_et', ''),
        'event_type':      'SIGNAL',
        'subtype':         subtype,
        'alert_fired':     alert_fired,
        'pre_signal':      entry.get('pre_signal', ''),

        'symbol':          entry.get('symbol', ''),
        'direction':       entry.get('direction', '') or entry.get('pros_direction', ''),
        'grade':           entry.get('grade', ''),
        'session':         entry.get('session', ''),
        'session_quality': entry.get('session_quality', ''),

        'strategy_family': family,
        'setup_type':      setup,

        # Execution levels — only populated for EXECUTION_READY
        'entry_zone': entry.get('entry_zone', ''),
        'stop':       entry.get('stop', ''),
        'tp1':        entry.get('tp1', ''),
        'rr':         entry.get('rr', ''),

        'pre_rationale':    entry.get('pre_rationale', ''),
        'claude_rationale': rationale,

        'mr2': {
            'from_state':           '',
            'state':                entry.get('mr2_state', ''),
            'score':                entry.get('mr2_score'),
            'block_longs':          bool(entry.get('mr2_block_longs', False)),
            'block_shorts':         bool(entry.get('mr2_block_shorts', False)),
            'block_reason':         entry.get('mr2_block_reason', ''),
            'block_longs_changed':  False,
            'block_shorts_changed': False,
        },

        'dp': {
            'dominance':  entry.get('dp_dominance', ''),
            'conviction': entry.get('dp_conviction', ''),
            'bullish':    entry.get('dp_bullish'),
            'bearish':    entry.get('dp_bearish'),
            'net':        entry.get('dp_net'),
        },

        'draw': {
            'name':        entry.get('draw_name', ''),
            'category':    entry.get('draw_category', ''),
            'tp1_pts':     entry.get('draw_tp1_pts'),
            'independent': entry.get('draw_independent'),
        },

        'rejection_code':   '',
        'rejection_reason': '',
        **_empty_exec(),

        'reasoning_trace_id': entry.get('reasoning_trace_id', ''),
        'screenshot':         entry.get('screenshot', ''),
        'source_id':          entry.get('id', ''),
    }


# ── Execution trace → EXECUTION cards ─────────────────────────────────────────

def _normalize_execution(entry: dict) -> Optional[dict]:
    """Normalize an EXECUTED execution_trace entry."""
    if entry.get('event_type') != 'EXECUTED':
        return None

    # EXECUTED uses 'instrument' (clean) or falls back to 'ticker' (raw like "MES1!")
    symbol = entry.get('instrument', '') or (
        entry.get('ticker', '').replace('1!', '').replace('CME_MINI:', '').replace('CME:', '')
    )
    setup  = entry.get('setup_type', '') or ''
    family = entry.get('family', '') or (setup.split('_')[0].upper() if '_' in setup else '')

    return {
        'id':              f'FEED_{entry.get("id", "")}',
        'timestamp_et':    entry.get('timestamp_et', ''),
        'event_type':      'EXECUTION',
        'subtype':         'EXECUTED',

        'symbol':          symbol,
        'direction':       entry.get('direction', ''),
        'grade':           entry.get('score', ''),
        'session':         entry.get('session', ''),
        'session_quality': '',

        'strategy_family': family,
        'setup_type':      setup,

        'entry_zone': '',
        'stop':       '',
        'tp1':        '',
        'rr':         '',

        'pre_rationale':    '',
        'claude_rationale': '',

        'mr2':  _empty_mr2(),
        'dp':   _empty_dp(),
        'draw': _empty_draw(),

        'rejection_code':   '',
        'rejection_reason': '',

        'etf':       entry.get('etf', ''),
        'qty':       entry.get('qty'),
        'entry_ref': entry.get('entry_ref'),
        'stop_px':   entry.get('stop_px'),
        'target_px': entry.get('target_px'),
        'order_id':  entry.get('order_id', ''),
        'risk_usd':  entry.get('risk_usd'),
        'broker':    entry.get('broker', ''),

        'reasoning_trace_id': '',
        'screenshot':         '',
        'source_id':          entry.get('id', ''),
    }


# ── Execution trace → GOVERNANCE cards ────────────────────────────────────────

def _normalize_governance(entry: dict) -> Optional[dict]:
    """Normalize a REJECTED or BRIDGE_REJECTED execution_trace entry."""
    etype = entry.get('event_type', '')
    if etype not in ('REJECTED', 'BRIDGE_REJECTED'):
        return None

    # BRIDGE_REJECTED uses 'symbol'; REJECTED uses 'instrument' / 'ticker'
    if etype == 'BRIDGE_REJECTED':
        symbol = entry.get('symbol', '')
    else:
        symbol = entry.get('instrument', '') or (
            entry.get('ticker', '').replace('1!', '').replace('CME_MINI:', '')
        )

    setup  = entry.get('setup_type', '') or ''
    family = entry.get('family', '') or (setup.split('_')[0].upper() if '_' in setup else '')
    grade  = entry.get('grade', '') or entry.get('score', '')

    return {
        'id':              f'FEED_{entry.get("id", "")}',
        'timestamp_et':    entry.get('timestamp_et', ''),
        'event_type':      'GOVERNANCE',
        'subtype':         entry.get('rejection_code', etype),

        'symbol':          symbol,
        'direction':       entry.get('direction', ''),
        'grade':           grade,
        'session':         entry.get('session', ''),
        'session_quality': '',

        'strategy_family': family,
        'setup_type':      setup,

        'entry_zone': '',
        'stop':       '',
        'tp1':        '',
        'rr':         '',

        'pre_rationale':    '',
        'claude_rationale': '',

        'mr2':  _empty_mr2(),
        'dp':   _empty_dp(),
        'draw': _empty_draw(),

        'rejection_code':   entry.get('rejection_code', ''),
        'rejection_reason': entry.get('rejection_reason', ''),
        **_empty_exec(),

        'reasoning_trace_id': '',
        'screenshot':         '',
        'source_id':          entry.get('id', ''),
    }


# ── Intelligence log → INTELLIGENCE cards ────────────────────────────────────

def _read_intelligence_log() -> list:
    try:
        if _INTEL_LOG.exists():
            data = json.loads(_INTEL_LOG.read_text(encoding='utf-8'))
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []


def _normalize_intelligence(entry: dict) -> dict:
    """Normalize one intelligence_log entry into a feed card."""
    subtype = entry.get('subtype', 'INTELLIGENCE_UPDATE')

    # Human-readable summary line for the feed
    thesis_state      = entry.get('thesis_state', '')
    thesis_state_prev = entry.get('thesis_state_prev', '')
    thesis            = entry.get('thesis', '')
    confidence        = entry.get('confidence', '')

    if subtype == 'SYNTHESIS_UPDATE':
        summary = (
            f'{thesis_state_prev} -> {thesis_state}: {thesis}'
            if thesis_state_prev else f'{thesis_state}: {thesis}'
        )
    elif subtype == 'MORNING_BRIEF':
        summary = thesis or entry.get('brief_text', '')
    else:
        summary = thesis or ''

    return {
        'id':              f'FEED_INTEL_{entry.get("id", "")}',
        'timestamp_et':    entry.get('timestamp_et', ''),
        'event_type':      'INTELLIGENCE',
        'subtype':         subtype,
        'alert_fired':     False,
        'pre_signal':      '',

        'symbol':          entry.get('symbol', 'MARKET'),
        'direction':       '',
        'grade':           '',
        'session':         entry.get('session', ''),
        'session_quality': '',

        'strategy_family': '',
        'setup_type':      '',

        'entry_zone': '',
        'stop':       '',
        'tp1':        '',
        'rr':         '',

        'pre_rationale':    '',
        'claude_rationale': summary,

        # Full intelligence payload — available for detailed card view
        'intelligence': {
            'thesis_state':         thesis_state,
            'thesis_state_prev':    thesis_state_prev,
            'thesis':               thesis,
            'confidence':           confidence,
            'condition':            entry.get('condition', ''),
            'primary_driver':       entry.get('primary_driver', ''),
            'confirming_evidence':  entry.get('confirming_evidence', []),
            'conflicting_evidence': entry.get('conflicting_evidence', []),
            'bull_score':           entry.get('bull_score'),
            'bear_score':           entry.get('bear_score'),
            'major_conflict':       entry.get('major_conflict', False),
            # Morning brief specific
            'liquidity_draw':       entry.get('liquidity_draw', ''),
            'participation':        entry.get('participation', ''),
            'macro_risk':           entry.get('macro_risk', ''),
            'session_narrative':    entry.get('session_narrative', ''),
            'key_question':         entry.get('key_question', ''),
            'brief_text':           entry.get('brief_text', ''),
        },

        'mr2':  _empty_mr2(),
        'dp':   _empty_dp(),
        'draw': _empty_draw(),

        'rejection_code':   '',
        'rejection_reason': '',
        **_empty_exec(),

        'reasoning_trace_id': '',
        'screenshot':         '',
        'source_id':          entry.get('id', ''),
    }


# ── MR2 state change detection ────────────────────────────────────────────────

def _detect_mr2_changes(signal_entries: list[dict]) -> list[dict]:
    """
    Detect Market Reality state transitions from the signal log.

    Processes entries in chronological order (signal_log is newest-first).
    Only processes entries that have mr2_state populated (new entries post-commit).
    Emits one MR2_CHANGE card per transition — state change or block flag flip.
    Timestamp is the signal_log entry where the new state was first observed.

    Per-symbol tracking: MES and MNQ are evaluated independently.
    """
    # Work oldest-first, only entries with MR2 data
    ordered = [e for e in reversed(signal_entries) if e.get('mr2_state')]

    last_state:  dict[str, str]  = {}
    last_longs:  dict[str, bool] = {}
    last_shorts: dict[str, bool] = {}

    changes: list[dict] = []

    for entry in ordered:
        sym    = entry.get('symbol', '')
        state  = entry.get('mr2_state', '')
        longs  = bool(entry.get('mr2_block_longs', False))
        shorts = bool(entry.get('mr2_block_shorts', False))

        prev_state  = last_state.get(sym)
        prev_longs  = last_longs.get(sym, False)
        prev_shorts = last_shorts.get(sym, False)

        state_changed  = prev_state is not None and state  != prev_state
        longs_changed  = prev_state is not None and longs  != prev_longs
        shorts_changed = prev_state is not None and shorts != prev_shorts

        if state_changed or longs_changed or shorts_changed:
            if   longs  and not prev_longs:  subtype = 'LONGS_BLOCKED'
            elif shorts and not prev_shorts: subtype = 'SHORTS_BLOCKED'
            elif not longs  and prev_longs:  subtype = 'LONGS_UNBLOCKED'
            elif not shorts and prev_shorts: subtype = 'SHORTS_UNBLOCKED'
            else:                            subtype = 'STATE_CHANGE'

            changes.append({
                'id':           f'FEED_MR2_{sym}_{entry.get("id", "")}',
                'timestamp_et': entry.get('timestamp_et', ''),
                'event_type':   'MR2_CHANGE',
                'subtype':      subtype,

                'symbol':          sym,
                'direction':       '',
                'grade':           '',
                'session':         entry.get('session', ''),
                'session_quality': '',

                'strategy_family': '',
                'setup_type':      '',

                'entry_zone': '',
                'stop':       '',
                'tp1':        '',
                'rr':         '',

                'pre_rationale':    '',
                'claude_rationale': '',

                'mr2': {
                    'from_state':           prev_state or '',
                    'state':                state,
                    'score':                entry.get('mr2_score'),
                    'block_longs':          longs,
                    'block_shorts':         shorts,
                    'block_reason':         entry.get('mr2_block_reason', ''),
                    'block_longs_changed':  longs_changed,
                    'block_shorts_changed': shorts_changed,
                },
                'dp':   _empty_dp(),
                'draw': _empty_draw(),

                'rejection_code':   '',
                'rejection_reason': '',
                **_empty_exec(),

                'reasoning_trace_id': '',
                'screenshot':         '',
                'source_id':          entry.get('id', ''),
            })

        last_state[sym]  = state
        last_longs[sym]  = longs
        last_shorts[sym] = shorts

    return changes


# ── Main feed builder ─────────────────────────────────────────────────────────

def build_feed(
    limit:      int            = 50,
    offset:     int            = 0,
    event_type: Optional[str]  = None,
    symbol:     Optional[str]  = None,
    date:       Optional[str]  = None,
    grade:      Optional[str]  = None,
    subtype:    Optional[str]  = None,
    alert_only: bool           = False,
) -> dict:
    """
    Build the merged NOVA intelligence feed.

    Filters (all optional, combinable):
      event_type  — SIGNAL | EXECUTION | GOVERNANCE | MR2_CHANGE
      symbol      — MES | MNQ | ES | NQ
      date        — YYYY-MM-DD (ET date)
      grade       — A | B | C | D
      subtype     — HEADS_UP | EXECUTION_READY | BRIDGE_REJECTED | LONGS_BLOCKED | ...
      alert_only  — when True, only SIGNAL cards where alert_required=True (alert fired)

    Returns:
      feed     — list of feed cards, newest-first, paginated
      total    — total card count after filtering
      has_more — whether more cards exist beyond this page
      stats    — counts by event_type
      meta     — query params echoed back
    """
    with _lock:
        signal_entries = _read_json(_SIGNAL_LOG)
        exec_entries   = _read_json(_EXEC_TRACE)
        intel_entries  = _read_intelligence_log()

    # ── Build cards ────────────────────────────────────────────────────────────
    signal_cards = [_normalize_signal(e) for e in signal_entries]

    exec_cards: list[dict] = []
    for e in exec_entries:
        etype = e.get('event_type', '')
        if etype == 'EXECUTED':
            card = _normalize_execution(e)
        elif etype in ('REJECTED', 'BRIDGE_REJECTED'):
            card = _normalize_governance(e)
        else:
            card = None   # SIGNAL_RECEIVED, VERDICT, REASONING_SNAPSHOT — skip
        if card:
            exec_cards.append(card)

    mr2_cards   = _detect_mr2_changes(signal_entries)
    intel_cards = [_normalize_intelligence(e) for e in intel_entries]

    # ── Merge and sort newest-first ────────────────────────────────────────────
    all_cards: list[dict] = signal_cards + exec_cards + mr2_cards + intel_cards
    all_cards.sort(key=_sort_key, reverse=True)

    # ── Filter ────────────────────────────────────────────────────────────────
    if event_type:
        et = event_type.upper()
        all_cards = [c for c in all_cards if c['event_type'] == et]

    if symbol:
        sym = symbol.upper()
        all_cards = [c for c in all_cards if c['symbol'].upper() == sym]

    if date:
        all_cards = [c for c in all_cards if c['timestamp_et'].startswith(date)]

    if grade:
        g = grade.upper()
        all_cards = [c for c in all_cards if c['grade'].upper() == g]

    if subtype:
        st = subtype.upper()
        all_cards = [c for c in all_cards if c['subtype'].upper() == st]

    if alert_only:
        # Only SIGNAL cards where an alert actually fired (alert_fired=True).
        # Non-SIGNAL cards (EXECUTION, GOVERNANCE, MR2_CHANGE) always pass.
        all_cards = [
            c for c in all_cards
            if c['event_type'] != 'SIGNAL' or c.get('alert_fired', False)
        ]

    # ── Stats ─────────────────────────────────────────────────────────────────
    stats: dict[str, int] = {}
    for c in all_cards:
        k = c['event_type']
        stats[k] = stats.get(k, 0) + 1

    total    = len(all_cards)
    page     = all_cards[offset: offset + limit]
    has_more = (offset + limit) < total

    return {
        'feed':     page,
        'total':    total,
        'has_more': has_more,
        'stats':    stats,
        'meta': {
            'limit':      limit,
            'offset':     offset,
            'event_type': event_type,
            'symbol':     symbol,
            'date':       date,
            'grade':      grade,
            'subtype':    subtype,
            'alert_only': alert_only,
        },
    }


# ── Single card detail ────────────────────────────────────────────────────────

def get_feed_card(source_id: str) -> Optional[dict]:
    """
    Return a single feed card by its source_id (original entry ID, not FEED_ prefixed).

    For SIGNAL cards that have a reasoning_trace_id, the full reasoning snapshot
    is embedded under '_reasoning_detail' for complete audit context.
    """
    with _lock:
        signal_entries = _read_json(_SIGNAL_LOG)
        exec_entries   = _read_json(_EXEC_TRACE)

    # Signal log
    for entry in signal_entries:
        if entry.get('id') == source_id:
            card = _normalize_signal(entry)
            rt_id = entry.get('reasoning_trace_id', '')
            if rt_id:
                try:
                    from services.execution_trace import get_reasoning_trace
                    for rt in get_reasoning_trace(300):
                        if rt.get('id') == rt_id:
                            card['_reasoning_detail'] = rt
                            break
                except Exception:
                    pass
            return card

    # Execution trace
    for entry in exec_entries:
        if entry.get('id') == source_id:
            etype = entry.get('event_type', '')
            if etype == 'EXECUTED':
                return _normalize_execution(entry)
            if etype in ('REJECTED', 'BRIDGE_REJECTED'):
                return _normalize_governance(entry)

    return None


# ── Feed stats ────────────────────────────────────────────────────────────────

def get_feed_stats() -> dict:
    """Summary statistics across the full feed — no pagination."""
    with _lock:
        signal_entries = _read_json(_SIGNAL_LOG)
        exec_entries   = _read_json(_EXEC_TRACE)

    total_signals = len(signal_entries)
    alerts_fired  = sum(1 for e in signal_entries if e.get('alert_type'))
    execution_ready = sum(1 for e in signal_entries if e.get('alert_type') == 'EXECUTION_READY')
    heads_up        = sum(1 for e in signal_entries if e.get('alert_type') == 'HEADS_UP')
    invalidations   = sum(1 for e in signal_entries if e.get('alert_type') == 'INVALIDATION')

    grade_dist: dict[str, int] = {}
    for e in signal_entries:
        g = e.get('grade', '')
        if g:
            grade_dist[g] = grade_dist.get(g, 0) + 1

    family_dist: dict[str, int] = {}
    for e in signal_entries:
        f = e.get('strategy_family', '') or (
            (e.get('setup_type', '') or '').split('_')[0].upper()
        )
        if f:
            family_dist[f] = family_dist.get(f, 0) + 1

    mr2_states: dict[str, int] = {}
    for e in signal_entries:
        s = e.get('mr2_state', '')
        if s:
            mr2_states[s] = mr2_states.get(s, 0) + 1

    dp_dominance: dict[str, int] = {}
    for e in signal_entries:
        d = e.get('dp_dominance', '')
        if d:
            dp_dominance[d] = dp_dominance.get(d, 0) + 1

    draw_cats: dict[str, int] = {}
    for e in signal_entries:
        c = e.get('draw_category', '')
        if c:
            draw_cats[c] = draw_cats.get(c, 0) + 1

    executions = sum(1 for e in exec_entries if e.get('event_type') == 'EXECUTED')
    rejections = sum(1 for e in exec_entries if e.get('event_type') in ('REJECTED', 'BRIDGE_REJECTED'))

    return {
        'signals': {
            'total':           total_signals,
            'alerts_fired':    alerts_fired,
            'execution_ready': execution_ready,
            'heads_up':        heads_up,
            'invalidations':   invalidations,
            'by_grade':        grade_dist,
            'by_family':       family_dist,
        },
        'market_reality': {
            'by_state':     mr2_states,
        },
        'directional_pressure': {
            'by_dominance': dp_dominance,
        },
        'draw_validation': {
            'by_category':  draw_cats,
        },
        'execution': {
            'total_executed':  executions,
            'total_rejected':  rejections,
        },
    }


# ── Ingest (Render-side replica append) ──────────────────────────────────────

_MAX_SIGNAL    = 10_000
_MAX_REASONING = 300
_MAX_EXECUTION = 500


def _sync_ts() -> str:
    try:
        from core.config import now_ny
        return now_ny().strftime('%Y-%m-%d %H:%M:%S ET')
    except Exception:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


def _update_sync_state(signal_id: str = '', reasoning_id: str = '') -> None:
    try:
        state: dict = {}
        if FEED_SYNC_FILE.exists():
            state = json.loads(FEED_SYNC_FILE.read_text(encoding='utf-8'))
        ts = _sync_ts()
        if signal_id:
            state['last_signal_id']        = signal_id
            state['last_signal_ingest_ts'] = ts
        if reasoning_id:
            state['last_reasoning_id']        = reasoning_id
            state['last_reasoning_ingest_ts'] = ts
        state['last_ingest_ts'] = ts
        FEED_SYNC_FILE.write_text(json.dumps(state, indent=2), encoding='utf-8')
    except Exception:
        pass


def ingest_signal(entry: dict) -> str:
    """
    Append one signal_log entry received from the local monitor.
    Deduplicates against the 20 most recent entries.
    Returns the entry ID on success, '' on failure.
    """
    entry_id = entry.get('id', '')
    with _lock:
        try:
            data = _read_json(_SIGNAL_LOG)
            if any(e.get('id') == entry_id for e in data[:20]):
                return entry_id                        # already present
            data.insert(0, entry)
            _SIGNAL_LOG.write_text(
                json.dumps(data[:_MAX_SIGNAL], indent=2, default=str),
                encoding='utf-8',
            )
        except Exception as e:
            print(f'[feed_ingest] signal write error: {e}')
            return ''
    _update_sync_state(signal_id=entry_id)
    return entry_id


def ingest_execution(entry: dict) -> str:
    """
    Append one execution_trace entry received from the local monitor.
    Handles DECISION_CHAIN, BRIDGE_REJECTED, EXECUTED, REJECTED event types.
    Deduplicates against the 20 most recent entries.
    Returns the entry ID on success, '' on failure.
    """
    entry_id = entry.get('id', '')
    with _lock:
        try:
            data = _read_json(_EXEC_TRACE)
            if any(e.get('id') == entry_id for e in data[:20]):
                return entry_id
            data.insert(0, entry)
            _EXEC_TRACE.write_text(
                json.dumps(data[:_MAX_EXECUTION], indent=2, default=str),
                encoding='utf-8',
            )
        except Exception as e:
            print(f'[feed_ingest] execution write error: {e}')
            return ''
    return entry_id


def ingest_reasoning(entry: dict) -> str:
    """
    Append one reasoning_trace entry received from the local monitor.
    Deduplicates against the 20 most recent entries.
    Returns the entry ID on success, '' on failure.
    """
    entry_id = entry.get('id', '')
    with _lock:
        try:
            data = _read_json(REASONING_TRACE_FILE)
            if any(e.get('id') == entry_id for e in data[:20]):
                return entry_id
            data.insert(0, entry)
            REASONING_TRACE_FILE.write_text(
                json.dumps(data[:_MAX_REASONING], indent=2, default=str),
                encoding='utf-8',
            )
        except Exception as e:
            print(f'[feed_ingest] reasoning write error: {e}')
            return ''
    _update_sync_state(reasoning_id=entry_id)
    return entry_id


# ── Feed health ───────────────────────────────────────────────────────────────

def get_feed_health() -> dict:
    """
    Sync health snapshot for GET /api/feed/health.

    Answers immediately: is the feed empty because nothing happened,
    or because sync failed?
    """
    with _lock:
        signals   = _read_json(_SIGNAL_LOG)
        exec_data = _read_json(_EXEC_TRACE)
        reasoning = _read_json(REASONING_TRACE_FILE)

    sync_state: dict = {}
    try:
        if FEED_SYNC_FILE.exists():
            sync_state = json.loads(FEED_SYNC_FILE.read_text(encoding='utf-8'))
    except Exception:
        pass

    newest_signal    = signals[0].get('timestamp_et', '')   if signals   else ''
    newest_reasoning = reasoning[0].get('timestamp_et', '') if reasoning else ''
    exec_total       = sum(1 for e in exec_data if e.get('event_type') == 'EXECUTED')
    gov_total        = sum(1 for e in exec_data if e.get('event_type') in ('REJECTED', 'BRIDGE_REJECTED'))

    return {
        'signal_count':          len(signals),
        'reasoning_count':       len(reasoning),
        'execution_count':       exec_total,
        'governance_count':      gov_total,
        'newest_signal_ts':      newest_signal,
        'newest_reasoning_ts':   newest_reasoning,
        'last_ingest_ts':        sync_state.get('last_ingest_ts', ''),
        'last_signal_ingest_ts': sync_state.get('last_signal_ingest_ts', ''),
        'last_signal_id':        sync_state.get('last_signal_id', ''),
        'feed_populated':        len(signals) > 0,
        'sync_configured':       bool(sync_state),
    }
