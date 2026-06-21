"""
services/audit.py -- Execution audit + ghost trade reconciliation.

Runs at startup (called from main.py lifespan) and on demand via GET /audit/execution.

What it does:
  1. Reads execution_trace for all PRE_ORDER_INTENT records.
  2. For each, checks whether a matching EXECUTED record exists (by intent_id or order_id).
  3. Reads the journal for all order_ids.
  4. For any EXECUTED trace record with no matching journal entry:
     reconstructs a minimal journal entry from trace data and writes it.
  5. Returns a structured audit report: clean / reconstructed / unresolved counts.

Definitions:
  CLEAN         — PRE_ORDER_INTENT + EXECUTED + journal entry all present.
  RECONSTRUCTED — EXECUTED in trace but journal entry missing; repaired here.
  UNRESOLVED    — PRE_ORDER_INTENT present but no EXECUTED record found.
                  This means the order may not have filled, or the process
                  crashed between submit_order() and the EXECUTED write.
                  These are flagged but NOT reconstructed — requires manual review.
  AUDIT_FAILURE — CRITICAL_AUDIT_FAILURE events logged explicitly.

What cannot be guaranteed:
  If the Python process hard-crashes between submit_order() returning and the
  PRE_ORDER_INTENT write completing, no record of the order exists anywhere in
  NOVA's files. This window is ~5ms. In that scenario only Alpaca's own
  order history can surface the trade. The reconciliation cannot close this gap —
  it can only detect and repair gaps that left at least a partial trace.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from core.config import TRACE_FILE, DATA_DIR
from core.state import load_journal, save_journal


# ── I/O ───────────────────────────────────────────────────────────────────────

def _read_trace() -> list[dict]:
    try:
        if TRACE_FILE.exists():
            data = json.loads(TRACE_FILE.read_text(encoding='utf-8'))
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Core reconciliation ───────────────────────────────────────────────────────

def reconcile_execution_audit() -> dict:
    """
    Full execution audit pass.

    Returns:
        {
          'clean':         int,   # fully auditable trades
          'reconstructed': int,   # journal entries rebuilt from trace
          'unresolved':    int,   # PRE_ORDER_INTENT with no EXECUTED record
          'audit_failures':int,   # explicit CRITICAL_AUDIT_FAILURE events
          'unresolved_ids': [...], # intent_ids/order_ids needing manual review
          'reconstructed_order_ids': [...],
          'last_run': '...',
        }
    """
    trace = _read_trace()

    # Index by event type
    intents:    dict[str, dict] = {}   # intent_id -> record
    submitted:  dict[str, dict] = {}   # intent_id -> record
    executed:   dict[str, dict] = {}   # order_id  -> record
    crit_fails: list[dict]       = []

    for entry in trace:
        etype = entry.get('event_type', '')
        if etype == 'PRE_ORDER_INTENT':
            eid = entry.get('id', '')
            if eid:
                intents[eid] = entry
        elif etype == 'POST_ORDER_SUBMITTED':
            iid = entry.get('intent_id', '')
            if iid:
                submitted[iid] = entry
        elif etype == 'EXECUTED':
            oid = entry.get('order_id', '')
            if oid:
                executed[oid] = entry
        elif etype == 'CRITICAL_AUDIT_FAILURE':
            crit_fails.append(entry)

    # Build a set of order_ids from all EXECUTED records
    executed_order_ids = set(executed.keys())

    # Build a set of order_ids already in the journal
    try:
        journal_trades = load_journal()
    except Exception:
        journal_trades = []
    journal_order_ids = {str(t.get('order_id', '')) for t in journal_trades if t.get('order_id')}

    # Classify every PRE_ORDER_INTENT
    clean         = 0
    unresolved    = []
    reconstructed_order_ids = []

    for intent_id, intent in intents.items():
        # Find the matching EXECUTED record by checking if any submitted entry
        # links this intent to a known order_id
        sub = submitted.get(intent_id)
        order_id = ''
        if sub:
            order_id = str(sub.get('order_id', ''))

        if not order_id:
            # Also scan executed records for a matching signal_id as fallback
            sig_id = intent.get('signal_id', '')
            if sig_id:
                for oid, ex in executed.items():
                    if ex.get('signal_id', '') == sig_id:
                        order_id = oid
                        break

        if not order_id or order_id not in executed_order_ids:
            # PRE_ORDER_INTENT exists but no EXECUTED record found
            unresolved.append({
                'intent_id':  intent_id,
                'order_id':   order_id or '?',
                'etf':        intent.get('etf', '?'),
                'direction':  intent.get('direction', '?'),
                'timestamp':  intent.get('timestamp_et', '?'),
                'note': (
                    'PRE_ORDER_INTENT present with no matching EXECUTED record. '
                    'Check Alpaca order history manually.'
                ),
            })
            continue

        # EXECUTED exists — check journal
        if order_id not in journal_order_ids:
            # Reconstruct journal entry from trace data
            ex = executed[order_id]
            _reconstruct_journal_entry(ex, intent, journal_trades)
            reconstructed_order_ids.append(order_id)
        else:
            clean += 1

    # Persist journal if anything was reconstructed
    if reconstructed_order_ids:
        try:
            save_journal(journal_trades)
            print(
                f'[audit] Reconstructed {len(reconstructed_order_ids)} missing journal '
                f'entries: {reconstructed_order_ids}'
            )
        except Exception as e:
            print(f'[audit] journal save error during reconstruction: {e}')

    result = {
        'clean':                   clean,
        'reconstructed':           len(reconstructed_order_ids),
        'unresolved':              len(unresolved),
        'audit_failures':          len(crit_fails),
        'unresolved_records':      unresolved,
        'reconstructed_order_ids': reconstructed_order_ids,
        'last_run':                _utc_iso(),
    }

    # Summary print
    if unresolved or reconstructed_order_ids or crit_fails:
        print(
            f'[audit] ATTENTION -- clean={clean} reconstructed={len(reconstructed_order_ids)} '
            f'unresolved={len(unresolved)} audit_failures={len(crit_fails)}'
        )
        for u in unresolved:
            print(f'[audit] UNRESOLVED: {u}')
    else:
        print(f'[audit] All {clean} trade(s) fully auditable. No gaps detected.')

    return result


def _reconstruct_journal_entry(
    executed_record: dict,
    intent_record: dict,
    journal_trades: list,
) -> None:
    """
    Write a minimal reconstructed journal entry from trace data.
    Appended in-place to journal_trades (caller handles save).
    Marked source='DONNA_AUTO_RECONSTRUCTED' so it is distinguishable.
    """
    order_id  = str(executed_record.get('order_id', ''))
    etf       = executed_record.get('etf', '') or intent_record.get('etf', '')
    direction = (executed_record.get('direction', '') or intent_record.get('direction', '')).upper()
    qty       = executed_record.get('shares', 0) or intent_record.get('qty', 0)
    entry_ref = executed_record.get('entry_ref', 0) or intent_record.get('entry_ref', 0)
    stop_px   = executed_record.get('stop_price', 0) or intent_record.get('stop_px', 0)
    tgt_px    = executed_record.get('target_price', 0) or intent_record.get('target_px', 0)
    setup     = executed_record.get('setup_type', '') or intent_record.get('setup_type', '')
    session   = executed_record.get('session', '') or intent_record.get('session', '')
    ts_et     = executed_record.get('timestamp_et', '') or intent_record.get('timestamp_et', '')

    trade_date = ''
    try:
        trade_date = ts_et.split(' ')[0]
    except Exception:
        pass

    entry = {
        'source':           'DONNA_AUTO_RECONSTRUCTED',
        'order_id':         order_id,
        'ticker':           etf,
        'instrument':       intent_record.get('instrument', ''),
        'direction':        direction,
        'trade_date':       trade_date,
        'time':             ts_et,
        'entry_price':      entry_ref,
        'stop_price':       stop_px,
        'target_price':     tgt_px,
        'exit_price':       None,
        'exit_time':        None,
        'size':             qty,
        'setup_type':       setup,
        'strategy_family':  intent_record.get('family', ''),
        'tier':             intent_record.get('risk_tier', ''),
        'confidence':       intent_record.get('confidence', ''),
        'regime':           'UNKNOWN',
        'active_regime':    'UNKNOWN',
        'session':          session,
        'harvey_verdict':   'TAKE',
        'broker_mode':      'ALPACA_ETF',
        'realized_pnl':     None,
        'pnl':              None,
        'outcome':          'OPEN',
        'context_snapshot': {},
        'thesis_analysis':  None,
        'notes': (
            f'RECONSTRUCTED by audit.py from execution_trace. '
            f'Original journal write failed. Intent ID: {intent_record.get("id", "?")}. '
            f'Verify entry/stop/target against Alpaca order history.'
        ),
        'timestamp': _utc_iso(),
    }
    journal_trades.append(entry)
