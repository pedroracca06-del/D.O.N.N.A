"""
outcome_linker.py — Read-only outcome linking for MCP decision snapshots.

Links decision snapshots to signal log, execution trace, and journal entries
using stable ID lookup and timestamp/field fuzzy matching.

Observability only — no execution impact of any kind.
"""
from __future__ import annotations
import json as _json
from pathlib import Path

# ── Symbol helpers ─────────────────────────────────────────────────────────────

def normalize_ticker(symbol: str) -> str:
    """CME_MINI:MES1! / MES1! / MES  →  'MES'.  Preserves MES/ES distinction."""
    return (symbol or '').upper().replace('CME_MINI:', '').replace('1!', '').strip()


def _ticker_family(symbol: str) -> str:
    """MES/ES → 'ES',  MNQ/NQ → 'NQ',  else normalize."""
    t = normalize_ticker(symbol)
    if t in ('MES', 'ES'):
        return 'ES'
    if t in ('MNQ', 'NQ'):
        return 'NQ'
    return t


def _setup_family(setup: str) -> str:
    """'PROS_LONG' → 'PROS',  'ORB_EDGE' → 'ORB',  '' → ''."""
    return ((setup or '').split('_')[0] or '').upper()


# ── Timestamp helpers ──────────────────────────────────────────────────────────

def _parse_ts(ts: str) -> float | None:
    """Parse any ISO timestamp (Z or +HH:MM or no TZ) to UTC epoch float."""
    if not ts:
        return None
    try:
        from datetime import datetime, timezone
        t = ts.strip()
        if t.endswith('Z'):
            t = t[:-1] + '+00:00'
        try:
            return datetime.fromisoformat(t).timestamp()
        except ValueError:
            # fallback: strip TZ and assume UTC
            return datetime.fromisoformat(t[:19]).replace(tzinfo=timezone.utc).timestamp()
    except Exception:
        return None


def _ts_date(ts: str) -> str:
    """Return first 10 chars of any timestamp string → 'YYYY-MM-DD'."""
    return (ts or '')[:10]


# ── Data loaders ───────────────────────────────────────────────────────────────

def _load_json_list(path: Path) -> list:
    """Load a JSON list file; return [] on any failure."""
    try:
        if path.exists():
            raw = _json.loads(path.read_text(encoding='utf-8'))
            return raw if isinstance(raw, list) else []
    except Exception:
        pass
    return []


def load_signal_log() -> list:
    from core.config import SIGNAL_LOG_FILE
    return _load_json_list(SIGNAL_LOG_FILE)


def load_journal() -> list:
    from core.config import JOURNAL_FILE
    return _load_json_list(JOURNAL_FILE)


def load_execution_trace() -> list:
    from core.config import TRACE_FILE
    return _load_json_list(TRACE_FILE)


# ── Matching helpers ───────────────────────────────────────────────────────────

_TIME_WINDOW_S = 10 * 60  # 10-minute fuzzy window


def _signal_log_match(snap: dict, signal_log: list) -> tuple[dict | None, str]:
    """Return (best_entry, confidence) from signal log or (None, 'NONE')."""
    snap_ts   = _parse_ts(snap.get('timestamp', ''))
    snap_fam  = _ticker_family(snap.get('symbol', ''))
    snap_sfam = _setup_family(snap.get('setup_type', ''))
    snap_dir  = (snap.get('direction', '') or '').upper()

    best: dict | None = None
    best_score = -1

    for entry in signal_log:
        if not isinstance(entry, dict):
            continue
        # Family match required
        if _ticker_family(entry.get('symbol', '') or entry.get('ticker', '')) != snap_fam:
            continue
        # Direction match required
        if (entry.get('direction', '') or '').upper() != snap_dir:
            continue
        # Time proximity
        entry_ts  = _parse_ts(entry.get('timestamp', ''))
        in_window = bool(snap_ts and entry_ts and abs(snap_ts - entry_ts) <= _TIME_WINDOW_S)
        if not in_window:
            continue
        # Setup family bonus
        fam_match = _setup_family(entry.get('setup_type', '')) == snap_sfam
        score     = 2 + (1 if fam_match else 0)
        if score > best_score:
            best_score = score
            best = entry

    if best is None:
        return None, 'NONE'
    confidence = 'HIGH' if best_score >= 3 else 'MEDIUM'
    return best, confidence


def _journal_match(snap: dict, journal: list) -> dict | None:
    """Match by trade_date + ticker + direction (no time precision in journal)."""
    snap_date = _ts_date(snap.get('timestamp', ''))
    snap_tick = normalize_ticker(snap.get('symbol', ''))
    snap_dir  = (snap.get('direction', '') or '').upper()

    for entry in journal:
        if not isinstance(entry, dict):
            continue
        j_date = entry.get('trade_date', '') or _ts_date(entry.get('timestamp', ''))
        j_tick = normalize_ticker(entry.get('ticker', ''))
        j_dir  = (entry.get('direction', '') or '').upper()
        if j_date == snap_date and j_tick == snap_tick and j_dir == snap_dir:
            return entry
    return None


def _trace_match(snap: dict, trace: list) -> dict | None:
    """Match execution trace by date + ticker + direction."""
    snap_date = _ts_date(snap.get('timestamp', ''))
    snap_tick = normalize_ticker(snap.get('symbol', ''))
    snap_dir  = (snap.get('direction', '') or '').upper()

    for entry in trace:
        if not isinstance(entry, dict):
            continue
        t_tick = normalize_ticker(
            entry.get('instrument', '') or entry.get('ticker', '')
        )
        t_dir  = (entry.get('direction', '') or '').upper()
        t_date = _ts_date(entry.get('timestamp_et', ''))
        if t_date == snap_date and t_tick == snap_tick and t_dir == snap_dir:
            return entry
    return None


# ── Main linking function ──────────────────────────────────────────────────────

def link_snapshot_to_outcome(
    snapshot:   dict,
    signal_log: list | None = None,
    journal:    list | None = None,
    trace:      list | None = None,
) -> dict:
    """Compute outcome link for one decision snapshot.  Pure read — no mutations.

    Returns a link dict with trade_status, outcome, match_confidence,
    match_method, linked_signal_id, linked_trace_id, and outcome fields.
    """
    if signal_log is None:
        signal_log = []
    if journal is None:
        journal = []
    if trace is None:
        trace = []

    snap_signal   = (snapshot.get('signal_type') or '').upper()
    snap_is_ready = bool(snapshot.get('is_execution_ready'))
    snap_is_rej   = bool(snapshot.get('is_rejected'))

    # Try each source in priority order
    sig_entry, sig_conf = _signal_log_match(snapshot, signal_log)
    jour_entry          = _journal_match(snapshot, journal)
    trace_entry         = _trace_match(snapshot, trace)

    # Consolidate match metadata
    if sig_entry:
        linked_signal_id = sig_entry.get('id', '')
        match_method     = 'SIGNAL_TIMESTAMP_FUZZY'
        match_confidence = sig_conf
    elif jour_entry:
        linked_signal_id = ''
        match_method     = 'DATE_TICKER_DIR'
        match_confidence = 'LOW'
    elif trace_entry:
        linked_signal_id = ''
        match_method     = 'TRACE_DATE_SYM'
        match_confidence = 'LOW'
    else:
        linked_signal_id = ''
        match_method     = 'NONE'
        match_confidence = 'NONE'

    linked_trace_id = trace_entry.get('id', '') if trace_entry else ''

    # Outcome from journal (most descriptive)
    j_outcome      = (jour_entry.get('outcome', '')       if jour_entry else '') or ''
    j_close_reason = (jour_entry.get('rejection_code', '') if jour_entry else '') or ''
    j_rej_reason   = (jour_entry.get('rejection_reason', '') if jour_entry else '') or ''

    # Trade status
    if snap_is_rej or snap_signal in ('NO_TRADE', ''):
        trade_status = 'REJECTED_OR_NO_TRADE'
    elif snap_signal == 'HEADS_UP':
        trade_status = 'NOT_TAKEN'
    elif snap_is_ready:
        if trace_entry and trace_entry.get('event_type') in ('EXECUTED', 'FILLED'):
            trade_status = 'TAKEN'
        elif j_outcome in ('WIN', 'LOSS', 'OPEN'):
            trade_status = 'TAKEN'
        else:
            trade_status = 'EXECUTION_READY_NOT_EXECUTED'
    else:
        trade_status = 'NOT_TAKEN'

    # Outcome (only claim if we have evidence)
    if j_outcome in ('WIN', 'LOSS', 'OPEN', 'REJECTED'):
        outcome = j_outcome
    elif trace_entry and trace_entry.get('event_type') == 'REJECTED':
        outcome = 'REJECTED'
    elif match_confidence == 'NONE':
        outcome = 'UNKNOWN'
    else:
        outcome = 'UNKNOWN'

    return {
        'linked_signal_id':  linked_signal_id,
        'linked_trace_id':   linked_trace_id,
        'trade_status':      trade_status,
        'outcome':           outcome,
        'realized_pnl':      None,   # not yet in journal schema
        'r_multiple':        None,   # not yet in journal schema
        'entry_price':       None,
        'exit_price':        None,
        'entry_time':        None,
        'exit_time':         None,
        'close_reason':      j_close_reason,
        'rejection_reason':  j_rej_reason,
        'match_confidence':  match_confidence,
        'match_method':      match_method,
    }


def outcome_summary(snapshot: dict, link: dict) -> dict:
    """Compact outcome record suitable for the /api/mcp-replay/outcomes endpoint."""
    return {
        'decision_id':        snapshot.get('decision_id'),
        'timestamp':          snapshot.get('timestamp'),
        'symbol':             snapshot.get('symbol'),
        'session':            snapshot.get('session'),
        'setup_type':         snapshot.get('setup_type'),
        'signal_type':        snapshot.get('signal_type'),
        'direction':          snapshot.get('direction'),
        'grade':              snapshot.get('grade'),
        'is_execution_ready': snapshot.get('is_execution_ready'),
        'is_rejected':        snapshot.get('is_rejected'),
        'trade_status':       link.get('trade_status', 'UNKNOWN'),
        'outcome':            link.get('outcome', 'UNKNOWN'),
        'realized_pnl':       link.get('realized_pnl'),
        'r_multiple':         link.get('r_multiple'),
        'entry_price':        link.get('entry_price'),
        'exit_price':         link.get('exit_price'),
        'close_reason':       link.get('close_reason', ''),
        'rejection_reason':   link.get('rejection_reason', ''),
        'match_confidence':   link.get('match_confidence', 'NONE'),
        'match_method':       link.get('match_method', 'NONE'),
        'linked_signal_id':   link.get('linked_signal_id', ''),
        'linked_trace_id':    link.get('linked_trace_id', ''),
    }
