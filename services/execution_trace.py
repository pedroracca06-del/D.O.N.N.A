"""donna_execution_trace.py — structured execution pipeline trace log.

Ring-buffer JSON log (donna_execution_trace.json, max 500 entries).
Never raises — all public methods fail silently so they never block
the main execution pipeline.

Three helpers, called from three places:
  log_execution_event()  — webhook entry + verdict stage
  log_trade_rejection()  — every rejection inside execute_signal()
  log_trade_execution()  — confirmed broker order
"""
from __future__ import annotations

import json
import random
import threading
import time
from pathlib import Path

BASE_DIR        = Path(__file__).parent.parent
TRACE_FILE      = BASE_DIR / 'data' / 'donna_execution_trace.json'
REASONING_FILE  = BASE_DIR / 'data' / 'donna_reasoning_trace.json'
MAX_TRACE       = 500
MAX_REASONING   = 300

_lock = threading.Lock()


# ── I/O helpers ────────────────────────────────────────────────

def _ts_et() -> str:
    try:
        from core.config import now_ny
        return now_ny().strftime('%Y-%m-%d %H:%M:%S ET')
    except Exception:
        return ''


def _new_id() -> str:
    return f'{int(time.time() * 1000)}-{random.randint(100, 999)}'


def _load() -> list:
    try:
        if TRACE_FILE.exists():
            raw = json.loads(TRACE_FILE.read_text(encoding='utf-8'))
            return raw if isinstance(raw, list) else []
    except Exception:
        pass
    return []


def _save(entries: list) -> None:
    try:
        TRACE_FILE.write_text(
            json.dumps(entries, indent=2, default=str), encoding='utf-8'
        )
    except Exception as e:
        print(f'[trace] save error: {e}')


def _append(entry: dict) -> None:
    try:
        with _lock:
            entries = _load()
            entries.insert(0, entry)
            _save(entries[:MAX_TRACE])
    except Exception as e:
        print(f'[trace] append error: {e}')


# ── Public API ─────────────────────────────────────────────────

def log_execution_event(
    event_type: str,
    data: dict,
    context: dict | None = None,
) -> None:
    """
    Log a pipeline stage event.

    event_type: SIGNAL_RECEIVED | VERDICT | ERROR
    data:       normalized signal fields (family, setup_type, ticker, etc.)
    context:    extra key/value pairs for this stage
    """
    try:
        entry: dict = {
            'id':           _new_id(),
            'event_type':   event_type,
            'timestamp_et': _ts_et(),
            'family':       data.get('strategy_family', ''),
            'setup_type':   data.get('setup_type', ''),
            'ticker':       data.get('ticker', ''),
            'instrument':   data.get('instrument', ''),
            'direction':    str(data.get('signal', '')).upper(),
            'session':      data.get('session', ''),
            'score':        data.get('score', ''),
        }
        if context:
            entry.update(context)
        _append(entry)
    except Exception as e:
        print(f'[trace] log_execution_event error: {e}')


def log_trade_rejection(
    code: str,
    reason: str,
    data: dict,
    parsed: dict,
    gates: dict | None = None,
) -> None:
    """
    Log a rejected trade with full gate state snapshot.

    code:   rejection code (e.g. VERDICT_NOT_TAKE, COOLDOWN_ACTIVE)
    reason: human-readable rejection reason
    data:   normalized signal fields
    parsed: verdict + confidence from process_signal()
    gates:  full snapshot of every execution gate at rejection time
    """
    try:
        entry: dict = {
            'id':               _new_id(),
            'event_type':       'REJECTED',
            'timestamp_et':     _ts_et(),
            'rejection_code':   code,
            'rejection_reason': reason,
            'family':           data.get('strategy_family', ''),
            'setup_type':       data.get('setup_type', ''),
            'ticker':           data.get('ticker', ''),
            'instrument':       data.get('instrument', ''),
            'direction':        str(data.get('signal', '')).upper(),
            'session':          data.get('session', ''),
            'score':            data.get('score', ''),
            'verdict':          parsed.get('verdict', ''),
            'confidence':       parsed.get('confidence', ''),
            'gates':            gates or {},
        }
        _append(entry)
    except Exception as e:
        print(f'[trace] log_trade_rejection error: {e}')


def log_trade_execution(
    data: dict,
    parsed: dict,
    result: dict,
) -> None:
    """
    Log a confirmed broker execution.

    data:   normalized signal fields
    parsed: verdict + confidence
    result: broker response dict (etf, qty, entry_ref, stop_px, etc.)
    """
    try:
        entry: dict = {
            'id':           _new_id(),
            'event_type':   'EXECUTED',
            'timestamp_et': _ts_et(),
            'family':       data.get('strategy_family', ''),
            'setup_type':   data.get('setup_type', ''),
            'ticker':       data.get('ticker', ''),
            'instrument':   data.get('instrument', ''),
            'direction':    str(data.get('signal', '')).upper(),
            'session':      data.get('session', ''),
            'score':        data.get('score', ''),
            'verdict':      parsed.get('verdict', ''),
            'confidence':   parsed.get('confidence', ''),
            'broker':       result.get('broker_mode', ''),
            'etf':          result.get('etf', result.get('ticker', '')),
            'qty':          result.get('shares', 0),
            'entry_ref':    result.get('entry_ref', 0),
            'stop_px':      result.get('stop_price', 0),
            'target_px':    result.get('target_price', 0),
            'order_id':     result.get('order_id', ''),
            'risk_usd':     result.get('risk_usd', 0),
        }
        _append(entry)
    except Exception as e:
        print(f'[trace] log_trade_execution error: {e}')


def log_bridge_rejection(
    code: str,
    reason: str,
    symbol: str,
    direction: str,
    setup_type: str,
    grade: str,
    session: str,
    governance_snapshot: dict | None = None,
) -> None:
    """
    Log a pre-execution bridge-level rejection with full governance snapshot.
    Called for test-mode gate failures before execute_signal() is reached.
    """
    try:
        entry: dict = {
            'id':                 _new_id(),
            'event_type':         'BRIDGE_REJECTED',
            'timestamp_et':       _ts_et(),
            'rejection_code':     code,
            'rejection_reason':   reason,
            'symbol':             symbol,
            'direction':          direction,
            'setup_type':         setup_type,
            'grade':              grade,
            'session':            session,
            'governance_snapshot': governance_snapshot or {},
        }
        _append(entry)
    except Exception as e:
        print(f'[trace] log_bridge_rejection error: {e}')


def get_trace(limit: int = 100) -> list:
    """Return the most recent trace entries (for /execution-trace API endpoint)."""
    try:
        return _load()[:min(limit, MAX_TRACE)]
    except Exception:
        return []


# ── Reasoning snapshot ─────────────────────────────────────────────────────────

def _load_reasoning() -> list:
    try:
        if REASONING_FILE.exists():
            raw = json.loads(REASONING_FILE.read_text(encoding='utf-8'))
            return raw if isinstance(raw, list) else []
    except Exception:
        pass
    return []


def _save_reasoning(entries: list) -> None:
    try:
        REASONING_FILE.write_text(
            json.dumps(entries, indent=2, default=str), encoding='utf-8'
        )
    except Exception as e:
        print(f'[trace] reasoning save error: {e}')


def log_reasoning_snapshot(
    symbol:          str,
    session_ctx:     dict,
    chart_ctx:       dict,
    pine_state:      dict,
    pros_eval:       dict,
    ib_eval:         dict,
    price_ote_eval:  dict,
    dir_pressure:    dict,
    mem_summary:     dict,
    pre_signal:      str,
    claude_decision: dict,
) -> None:
    """
    Full intelligence context snapshot captured at every Claude reasoning decision.

    Answers: "Why did NOVA think this?" / "Why was this blocked?" /
             "What differentiated good from bad trades?"

    Stored in donna_reasoning_trace.json (separate from execution trace).
    Each entry is self-contained — reconstructable without any other state.

    Called from reasoning.py after evaluate_with_claude() returns, before
    AlertData is built.
    """
    try:
        # ── Pine state summary (key fields only, not full raw table) ──────────
        main_st = pine_state.get('main', {})
        pros_st = pine_state.get('pros', {})
        pine_summary = {
            'CMD':     main_st.get('CMD', ''),
            'DISPL':   main_st.get('DISPL', ''),
            'PROS':    main_st.get('PROS', ''),
            'OTE':     pros_st.get('OTE',  ''),
            'CONT':    pros_st.get('CONT', ''),
            'RETRACE': pros_st.get('RETRACE', ''),
            'IB_H':    pros_st.get('IB H', ''),
            'IB_L':    pros_st.get('IB L', ''),
        }

        # ── Price context ─────────────────────────────────────────────────────
        ohlcv = chart_ctx.get('ohlcv', {})
        price_summary = {
            'price':    chart_ctx.get('price'),
            'high_30':  ohlcv.get('high_30'),
            'low_30':   ohlcv.get('low_30'),
            'range_30': ohlcv.get('range_30'),
        }

        # ── Directional pressure (scores only, skip verbose sources) ──────────
        dp_summary = {
            'bullish':       dir_pressure.get('bullish', 0),
            'bearish':       dir_pressure.get('bearish', 0),
            'net':           dir_pressure.get('net', 0),
            'dominance':     dir_pressure.get('dominance', ''),
            'conviction':    dir_pressure.get('conviction', ''),
            'disagreements': dir_pressure.get('disagreements', []),
        }

        # ── Market memory summary ─────────────────────────────────────────────
        mem = {
            'long':  mem_summary.get('long',  {}),
            'short': mem_summary.get('short', {}),
        }

        # ── Claude decision summary ───────────────────────────────────────────
        claude_summary = {
            'alert_required':  claude_decision.get('alert_required', False),
            'alert_type':      claude_decision.get('alert_type', ''),
            'grade':           claude_decision.get('grade', ''),
            'no_alert_reason': claude_decision.get('no_alert_reason', ''),
            'entry_zone':      claude_decision.get('entry_zone', ''),
            'stop':            claude_decision.get('stop', ''),
            'tp1':             claude_decision.get('tp1', ''),
            'rr':              claude_decision.get('rr', ''),
            'watch_time':      claude_decision.get('watch_time', ''),
            'reasoning':       (
                claude_decision.get('reasoning') or
                claude_decision.get('confidence') or
                claude_decision.get('analysis') or ''
            ),
        }

        entry: dict = {
            'id':             _new_id(),
            'event_type':     'REASONING_SNAPSHOT',
            'timestamp_et':   _ts_et(),
            'symbol':         symbol,

            # Session context
            'session':        session_ctx.get('session', ''),
            'session_quality':session_ctx.get('session_quality', ''),
            'time_et':        session_ctx.get('time_et', ''),
            'daily_trades':   session_ctx.get('daily_trades', 0),
            'daily_loss_hit': session_ctx.get('daily_loss_hit', False),

            # Intelligence layers
            'pine':           pine_summary,
            'price':          price_summary,
            'pros_eval': {
                'phase':        pros_eval.get('phase', ''),
                'direction':    pros_eval.get('direction', ''),
                'cont_quality': pros_eval.get('cont_quality', ''),
                'ote_status':   pros_eval.get('ote_status', ''),
                'has_signal':   pros_eval.get('has_signal', False),
            },
            'ib_eval': {
                'draw':    ib_eval.get('draw', ''),
                'aligned': ib_eval.get('aligned', False),
                'ib_high': ib_eval.get('ib_high'),
                'ib_low':  ib_eval.get('ib_low'),
            },
            'price_ote': {
                'has_ote':   price_ote_eval.get('has_ote', False),
                'direction': price_ote_eval.get('direction', ''),
                'fib_pct':   price_ote_eval.get('fib_pct', 0),
                'clean_ote': price_ote_eval.get('clean_ote', False),
                'ib_aligned':price_ote_eval.get('ib_aligned', False),
                'ote_lo':    price_ote_eval.get('ote_lo'),
                'ote_hi':    price_ote_eval.get('ote_hi'),
                'reason':    price_ote_eval.get('reason', ''),
            },
            'dir_pressure':  dp_summary,
            'market_memory': mem,

            # Decision
            'pre_signal':    pre_signal,
            'claude':        claude_summary,
        }

        with _lock:
            entries = _load_reasoning()
            entries.insert(0, entry)
            _save_reasoning(entries[:MAX_REASONING])

    except Exception as e:
        print(f'[trace] log_reasoning_snapshot error: {e}')


def get_reasoning_trace(limit: int = 50) -> list:
    """Return the most recent reasoning snapshots."""
    try:
        return _load_reasoning()[:min(limit, MAX_REASONING)]
    except Exception:
        return []
