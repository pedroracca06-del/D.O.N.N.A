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

BASE_DIR   = Path(__file__).parent
TRACE_FILE = BASE_DIR / 'donna_execution_trace.json'
MAX_TRACE  = 500

_lock = threading.Lock()


# ── I/O helpers ────────────────────────────────────────────────

def _ts_et() -> str:
    try:
        from donna_config import now_ny
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


def get_trace(limit: int = 100) -> list:
    """Return the most recent trace entries (for /execution-trace API endpoint)."""
    try:
        return _load()[:min(limit, MAX_TRACE)]
    except Exception:
        return []
