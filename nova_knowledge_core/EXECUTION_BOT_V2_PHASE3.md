# EXECUTION BOT V2 — PHASE 3 IMPLEMENTATION NOTE

**Date:** 2026-06-30  
**Status:** COMPLETE — 31/31 Phase 3 tests + 81/81 total (P1+P2+P3) passing  
**Constraint:** Read-only. No broker writes. No live enforcement changes. No strategy changes.

---

## What Was Built

Phase 3 adds pre-trade open-position conflict detection, read-only broker state inspection,
and a journal/broker reconciliation scaffold. Every execution attempt now knows whether a
position already exists for the same instrument, whether that position is protected by orders,
and whether the broker and journal are consistent.

### New Files

**`services/execution_reconcile.py`**  
Read-only broker state reader and reconciliation engine. Safety contract: never calls any
Alpaca write endpoint (no submit_order, no cancel_order_by_id, no close_all_positions).

Public API:
- `get_broker_positions_safe() -> list` — Alpaca positions, normalized, [] on failure
- `get_broker_orders_safe() -> list` — open Alpaca orders, normalized, [] on failure
- `get_open_journal_trades_safe() -> list` — OPEN journal entries, [] on failure
- `normalize_position_record(pos) -> dict` — Alpaca Position object → standard dict
- `normalize_order_record(order) -> dict` — Alpaca Order object → standard dict
- `check_open_position_conflict(symbol, direction, routed_etf, broker_positions) -> dict`
- `detect_protective_orders(routed_etf, broker_positions, broker_orders) -> dict`
- `reconcile_execution_state(execution_request, broker_positions, broker_orders, journal_trades) -> dict`

**`tests/test_execution_bot_v2_phase3.py`**  
31 tests — all passing.

### Modified Files

**`services/execution_request.py`**

New Phase 3 status constants:
```python
STATUS_REJECTED_OPEN_POSITION    = 'REJECTED_OPEN_POSITION'
# Reconciliation statuses (reconciliation_status field, not final_status):
STATUS_RECON_SYNCED              = 'SYNCED'
STATUS_RECON_RECONCILED          = 'RECONCILED'
STATUS_RECON_BROKER_MISSING      = 'BROKER_POSITION_MISSING'
STATUS_RECON_JOURNAL_MISSING     = 'JOURNAL_MISSING'
STATUS_RECON_SIZE_MISMATCH       = 'SIZE_MISMATCH'
STATUS_RECON_DIRECTION_MISMATCH  = 'DIRECTION_MISMATCH'
STATUS_RECON_UNPROTECTED         = 'UNPROTECTED_POSITION'
STATUS_RECON_UNKNOWN             = 'UNKNOWN_BROKER_STATE'
STATUS_RECON_INSUFFICIENT        = 'INSUFFICIENT_DATA'
```

Phase 3 wired inside `_validate_and_record_impl()` after Phase 2 gates:
1. `get_broker_positions_safe()` — read all open Alpaca positions (read-only)
2. `get_broker_orders_safe()` — read all open orders (read-only)
3. `get_open_journal_trades_safe()` — read open journal entries
4. `check_open_position_conflict()` — gate: any position for routed_etf = conflict
5. `detect_protective_orders()` — check stop/target/bracket on existing position
6. `reconcile_execution_state()` — pre-trade broker/journal comparison

New fields in every `validate_and_record()` return dict:
```python
'open_position_check':          dict     # conflict gate result
'broker_positions_count':       int      # total broker positions read
'broker_orders_count':          int      # total open orders read
'journal_open_trades_count':    int      # total OPEN journal entries
'reconciliation_status':        str|None # SYNCED / UNPROTECTED_POSITION / etc.
'protective_stop_found':        bool|None
'protective_target_found':      bool|None
'unprotected_position_warning': bool     # True if position exists with no stop
'reconciliation_warnings':      list
'reconciliation_errors':        list
```

**Final status priority (full chain):**
```
REJECTED_BAD_PAYLOAD > REJECTED_DUPLICATE > REJECTED_STALE
  > prop gate rejection (Phase 2)
  > REJECTED_OPEN_POSITION (Phase 3, when enforced)
  > DRY_RUN_VALIDATED | RECEIVED
```

---

## How Open-Position Detection Works

1. The signal's `symbol` (e.g. MNQ) is mapped to its routed ETF (QQQ) via `_symbol_to_etf()`
2. `check_open_position_conflict()` checks if any broker position has `symbol == 'QQQ'`
3. **Any** open position for that ETF is a conflict — direction does not matter
4. If conflict detected:
   - `rejection_code = 'REJECTED_OPEN_POSITION'`
   - In dry-run: becomes `final_status` (blocked)
   - In live + `NOVA_PROP_GATES_ENABLED=true`: blocked
   - In live + `NOVA_PROP_GATES_ENABLED=false` (default): logged only, `RECEIVED` returned

---

## How Reconciliation Works

`reconcile_execution_state()` is a PRE-TRADE check that compares the current broker state
with the NOVA journal to detect discrepancies before a new trade is attempted.

**Inputs:**
- `broker_positions` — what Alpaca says is open
- `broker_orders` — what open orders exist for the instrument
- `journal_trades` — NOVA journal entries with `outcome='OPEN'`

**Matching:** Broker position matched by `symbol == routed_etf`. Journal trade matched by
`ticker == routed_etf` and `outcome == 'OPEN'`.

**Status priority (highest → lowest):**

| Status | Condition |
|---|---|
| `DIRECTION_MISMATCH` | Broker side ≠ journal direction |
| `SIZE_MISMATCH` | Qty differs by > 5% |
| `UNPROTECTED_POSITION` | Broker position exists but no stop order |
| `JOURNAL_MISSING` | Broker has position, journal has nothing |
| `BROKER_POSITION_MISSING` | Journal says OPEN, broker has no position |
| `SYNCED` | Broker + journal agree; position is protected |
| `INSUFFICIENT_DATA` | Both broker and journal are empty |

Reconciliation status goes into the `reconciliation_status` field of the req dict.  
It does **not** affect `final_status` unless it triggers `REJECTED_OPEN_POSITION` through
the conflict gate.

---

## Protective Order Detection

`detect_protective_orders(routed_etf, broker_positions, broker_orders)`:

For a LONG position: looks for `side=sell` orders for that symbol.  
For a SHORT position: looks for `side=buy` orders for that symbol.

- `stop_found` = True if `type` is `stop`, `stop_limit`, or `trailing_stop`
- `target_found` = True if `type` is `limit`
- `bracket_detected` = True if any order has `order_class` in `bracket`, `oco`
  — bracket means both stop AND target are confirmed

`unprotected = not stop_found` — only the stop matters for the unprotected flag.

---

## What Is Enforced in Dry-Run

| Feature | Dry-Run | Live (NOVA_PROP_GATES_ENABLED=false) |
|---|---|---|
| Phase 1: dedup | Blocks | Logs only |
| Phase 1: stale signal | Blocks | Logs only |
| Phase 2: prop gates | Blocks | Logs only |
| Phase 3: open position conflict | Blocks | Logs only |
| Phase 3: unprotected position | Warning only | Warning only |
| Phase 3: reconciliation status | Logged | Logged |

---

## What Is Only Logged in Live Mode

With `NOVA_PROP_GATES_ENABLED=false` (default):
- `open_position_check.conflict = True` is recorded in trace_v2 and req dict
- `unprotected_position_warning = True` is recorded
- `reconciliation_status` (SYNCED, MISMATCH, etc.) is recorded
- `final_status` remains `RECEIVED` — broker path continues

To enable live enforcement: `NOVA_PROP_GATES_ENABLED=true`

---

## Why We Are Not Ready for Prop Live Yet

1. **`decision_id` is not wired** — reasoning snapshot ID doesn't flow to bridge (Phase 1 known gap)
2. **`current_balance` is manually set** — max_total_loss gate reads from config file, not live from Alpaca
3. **No trailing drawdown gate** — Phase 4 scope
4. **No protective order confirmation post-fill** — we detect protective orders on existing positions but don't verify they were placed correctly after a fill
5. **No broker reconciliation loop** — reconciliation runs once at pre-trade time; no periodic re-check
6. **No UNPROTECTED_POSITION alerting** — detected and logged, but no Discord/Telegram alert sent

---

## Phase 4 Scope (After Phase 3)

Phase 4 should focus on post-trade lifecycle tracking:

1. **Protective order confirmation after fill** — after broker fill confirmed, re-check that
   stop and target orders were placed; alert if missing
2. **UNPROTECTED_POSITION alerting** — if detection fires, send priority Discord alert
3. **Broker order lifecycle tracking** — SUBMITTED_TO_BROKER → BROKER_ACCEPTED →
   ENTRY_FILLED → PROTECTIVE_ORDERS_PLACED → EXIT_FILLED state machine
4. **Periodic reconciliation loop** — re-check broker/journal alignment every N minutes during session
5. **RECONCILED terminal status** — mark trace_v2 entry as RECONCILED when position closes cleanly
6. **Trailing drawdown gate** — HWM tracking + `trailing_drawdown_amount` gate

---

## Environment Variables

| Variable | Default | Effect |
|---|---|---|
| `NOVA_EXECUTION_DRY_RUN` | `false` | Phase 1+2+3 result is final; broker never called |
| `NOVA_PROP_GATES_ENABLED` | `false` | Phase 2+3 gates enforce in live mode |
| `NOVA_MAX_SIGNAL_AGE_SECONDS` | `120` | Stale signal threshold |
| `ALPACA_API_KEY` | — | Required for broker reads |
| `ALPACA_SECRET_KEY` | — | Required for broker reads |
