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
from services.execution import AUTONOMOUS_JOURNAL_SOURCES


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

    # Repair journal splits: an autonomous OPEN entry (DONNA_AUTO or
    # DONNA_AUTO_RECONSTRUCTED) whose EOD close landed as a separate orphaned
    # DONNA_EOD row instead of being linked back to it (pre-existing source-class
    # mismatch in the EOD/outcome matchers, fixed going forward in execution.py).
    merged_eod_closes = _merge_orphaned_eod_closes(journal_trades)
    if merged_eod_closes:
        try:
            save_journal(journal_trades)
            print(f'[audit] Merged {len(merged_eod_closes)} orphaned EOD close(s): {merged_eod_closes}')
        except Exception as e:
            print(f'[audit] journal save error during EOD-close merge: {e}')

    # Regression check: any autonomous OPEN entry that still has an unlinked
    # standalone DONNA_EOD close sitting next to it (should be empty after the
    # merge above — flagged here so any future recurrence is never silent).
    unlinked_eod_closes = find_unlinked_reconstructed_closes(journal_trades)

    result = {
        'clean':                   clean,
        'reconstructed':           len(reconstructed_order_ids),
        'unresolved':              len(unresolved),
        'audit_failures':          len(crit_fails),
        'unresolved_records':      unresolved,
        'reconstructed_order_ids': reconstructed_order_ids,
        'merged_eod_closes':       merged_eod_closes,
        'unlinked_eod_closes':     unlinked_eod_closes,
        'last_run':                _utc_iso(),
    }

    # Summary print
    if unresolved or reconstructed_order_ids or crit_fails or unlinked_eod_closes:
        print(
            f'[audit] ATTENTION -- clean={clean} reconstructed={len(reconstructed_order_ids)} '
            f'unresolved={len(unresolved)} audit_failures={len(crit_fails)} '
            f'unlinked_eod_closes={len(unlinked_eod_closes)}'
        )
        for u in unresolved:
            print(f'[audit] UNRESOLVED: {u}')
        for u in unlinked_eod_closes:
            print(f'[audit] UNLINKED_EOD_CLOSE: {u}')
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


# ── EOD-close split repair ───────────────────────────────────────────────────
#
# Bug class: the EOD-close matcher and check_position_outcomes() used to filter
# strictly on source == 'DONNA_AUTO'. A DONNA_AUTO_RECONSTRUCTED entry (the same
# trade, just recovered by audit.py above) would never match, so its real EOD
# close landed as a brand-new, unlinked 'DONNA_EOD' row instead of updating the
# original entry. Net effect: one real trade shows up as two journal records —
# an OPEN entry that never closes, plus an orphaned close with no order_id.
#
# execution.py now matches on AUTONOMOUS_JOURNAL_SOURCES going forward, so this
# split cannot occur again for new trades. The functions below repair any
# pre-existing split and flag anything they can't safely repair.

def _find_orphan_eod_match(journal_trades: list, open_entry: dict, skip: set[int]) -> int | None:
    """Find the index of a standalone DONNA_EOD row matching open_entry, or None."""
    for j, t in enumerate(journal_trades):
        if j in skip:
            continue
        if (t.get('source') == 'DONNA_EOD'
                and not t.get('order_id')
                and t.get('ticker') == open_entry.get('ticker')
                and t.get('direction') == open_entry.get('direction')
                and t.get('trade_date') == open_entry.get('trade_date')):
            return j
    return None


def _merge_orphaned_eod_closes(journal_trades: list) -> list[dict]:
    """
    Merge any orphaned standalone DONNA_EOD close row into the autonomous OPEN
    entry it actually belongs to (same ticker + direction + trade_date),
    mutating journal_trades in place. Returns a list of merge summaries.
    """
    merged: list[dict] = []
    consumed: set[int] = set()

    open_indices = [
        i for i, t in enumerate(journal_trades)
        if t.get('source') in AUTONOMOUS_JOURNAL_SOURCES
        and str(t.get('outcome', '')).upper() == 'OPEN'
    ]

    for idx in open_indices:
        open_entry = journal_trades[idx]
        match_idx = _find_orphan_eod_match(journal_trades, open_entry, consumed | {idx})
        if match_idx is None:
            continue

        close_row = journal_trades[match_idx]
        try:
            realized_pnl = round(float(close_row.get('realized_pnl') or 0), 2)
        except (TypeError, ValueError):
            realized_pnl = 0.0

        # Recompute exit_price from realized_pnl rather than trusting
        # close_row['exit_price'] directly — the EOD short-position exit-price
        # calc has a known sign bug; entry_price +/- pnl-per-share is reliable.
        exit_price = close_row.get('exit_price')
        try:
            entry_price = float(open_entry.get('entry_price'))
            size        = float(open_entry.get('size') or 1)
            per_share   = realized_pnl / size if size else 0.0
            exit_price  = round(
                entry_price + per_share if str(open_entry.get('direction', '')).upper() == 'LONG'
                else entry_price - per_share,
                4,
            )
        except (TypeError, ValueError, ZeroDivisionError):
            pass

        outcome = 'WIN' if realized_pnl > 0 else ('LOSS' if realized_pnl < 0 else 'BREAKEVEN')
        merge_note = (
            f' | Merged orphaned EOD close (source-class mismatch, separate DONNA_EOD row) '
            f'during journal-split repair on {_utc_iso()}.'
        )

        journal_trades[idx] = {
            **open_entry,
            'exit_price':   exit_price,
            'exit_time':    close_row.get('exit_time') or open_entry.get('exit_time'),
            'realized_pnl': realized_pnl,
            'pnl':          realized_pnl,
            'outcome':      outcome,
            'notes':        (open_entry.get('notes') or '') + merge_note,
            'repaired_at':  _utc_iso(),
        }
        consumed.add(match_idx)
        merged.append({
            'order_id':     open_entry.get('order_id', ''),
            'ticker':       open_entry.get('ticker', ''),
            'trade_date':   open_entry.get('trade_date', ''),
            'realized_pnl': realized_pnl,
            'outcome':      outcome,
        })

    for j in sorted(consumed, reverse=True):
        journal_trades.pop(j)

    return merged


def find_unlinked_reconstructed_closes(journal_trades: list) -> list[dict]:
    """
    Regression check: flag any autonomous OPEN entry (DONNA_AUTO or
    DONNA_AUTO_RECONSTRUCTED) that still has a matching standalone DONNA_EOD
    close row sitting unlinked next to it. Should always return [] after
    _merge_orphaned_eod_closes() runs — a non-empty result means a new variant
    of the split has appeared and needs investigation, not silent data loss.
    """
    flags: list[dict] = []
    open_entries = [
        t for t in journal_trades
        if t.get('source') in AUTONOMOUS_JOURNAL_SOURCES
        and str(t.get('outcome', '')).upper() == 'OPEN'
    ]
    for open_entry in open_entries:
        if _find_orphan_eod_match(journal_trades, open_entry, set()) is not None:
            flags.append({
                'order_id':   open_entry.get('order_id', ''),
                'ticker':     open_entry.get('ticker', ''),
                'trade_date': open_entry.get('trade_date', ''),
                'note': (
                    'OPEN autonomous entry has an unlinked standalone DONNA_EOD '
                    'close row — journal split detected.'
                ),
            })
    return flags
