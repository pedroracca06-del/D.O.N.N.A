# EXECUTION BOT V2 — PROP-FIRM READINESS AUDIT

**Date:** 2026-06-30  
**Status:** READ-ONLY AUDIT. No execution changes. No broker changes. No new gates.  
**Purpose:** Full audit of the current NOVA execution system from decision to broker order to journal/outcome, to identify every gap before prop-firm deployment.

---

## 1. CURRENT EXECUTION FLOW

```
[Monitor / Webhook]
        │
        ▼
engines/reasoning.py          → Reads chart state via MCP
                                 → Fires AlertData (HEADS_UP / EXECUTION_READY / etc.)
                                 → Fires _fire_decision_snapshot() (async, daemon thread)
        │
        ▼
delivery/alert_engine.py      → Governance: cooldown, daily cap
                                 → Discord embed + screenshot
                                 → EXECUTION_READY signals forwarded to execution_bridge
        │
        ▼
services/execution_bridge.py  → Gate 1:  NOVA_AUTO_EXECUTE env var
                                 → Gate 2:  paper mode check
                                 → Gate 3:  alert_type == EXECUTION_READY only
                                 → Gate 4:  grade A/B only
                                 → Gate 5:  valid direction (LONG/SHORT)
                                 → Gate 6:  symbol routing (MES/ES→SPY, MNQ/NQ→QQQ)
                                 → Gate 7:  directional context check
                                 → Gate 8:  market reality check
                                 → Gate 9:  kill switch
                                 → Gate 10: instrument filter
                                 → Gate 11: strategy filter
                                 → Gate 12: duplicate signal (in-process set)
                                 → Gate 13: position governance (3-layer)
                                 Cooldown check (per-instrument)
                                 → route_to_execution(alert) → execute_signal()
        │
        ▼
services/execution.py         → Rule 0:  state engine gate (can_execute())
   execute_signal()              → Rule 0.5: execution governance (strategy/instrument/grade)
                                 → VERDICT must be TAKE
                                 → daily_loss_trade_hit check
                                 → session trade limit check
                                 → session boundary → close stale positions
                                 → live Alpaca position + pending order conflict check
                                 → cooldown check
                                 → thesis conflict check (60-min flip window)
                                 → Rule 1: red folder (±30 min HIGH event)
                                 → Rule 3: daily loss limit (Alpaca P&L query)
                                 → Rule 5: position sizing
                                 → _execute_alpaca_etf()
        │
        ▼
services/execution.py         → Fetch live ETF price
   _execute_alpaca_etf()         → Compute qty = floor(equity × RISK_PCT / stop_dist), capped
                                 → log_pre_order_intent() → PRE_ORDER_INTENT trace record
                                 → api.submit_order() — bracket (market + stop + limit)
                                 → log_post_order_submitted() → POST_ORDER_SUBMITTED trace
                                 → state engine: increment trade count, add_position, set cooldown, set thesis
                                 → backup write to donna_risk_state.json
                                 → _journal_log_trade() → OPEN journal entry
                                 → log_trade_execution() → EXECUTED trace record
                                 → Telegram notification
        │
        ▼
[Background: check_position_outcomes()]
                                 → Polls Alpaca for filled orders
                                 → Matches to OPEN NOVA_AUTO journal entries by order_id
                                 → Updates exit_price, realized_pnl, outcome
                                 → thesis_analysis populated post-close
```

---

## 2. SOURCE-OF-TRUTH MAP

| State | Primary Authority | Backup | Gap |
|---|---|---|---|
| Daily trade count | `state_engine.json` (DonnaStateEngine) | `donna_risk_state.json` | Dual-write, possible drift |
| Session trade count | `donna_risk_state.json` session_trade_counts | None | No cross-check |
| Daily P&L | Alpaca REST `get_account().equity - last_equity` | None | Alpaca latency; not persisted locally |
| Loss limit hit | `donna_risk_state.json` daily_loss_limit_hit + state_engine | Both written | Redundant, OK |
| Open positions | `state_engine.json` open_positions list | Alpaca REST (live check) | State engine can lag real broker state |
| Cooldown | `state_engine.json` spy/qqq_cooldown_until | None | Resets on process restart |
| Active thesis | `state_engine.json` active_thesis / thesis_direction | None | Resets on process restart |
| Signal dedup | `_seen_signal_ids` in-process set (execution_bridge.py) | None | **Resets on process restart** |
| Execution request | No concept exists | — | **MISSING** |
| Decision_id chain | No concept exists | — | **MISSING** |
| Prop-firm balance | No concept exists | — | **MISSING** |
| Trailing drawdown | No concept exists | — | **MISSING** |
| Execution trace | `donna_execution_trace.json` (ring buffer, 500) | None | No decision_id link |

---

## 3. CURRENT SAFETY CHECKS (what exists)

### In execution_bridge.py
- `NOVA_AUTO_EXECUTE` env var gate (hard off switch)
- Paper mode enforcement
- Alert type filter (EXECUTION_READY only)
- Grade filter (A/B only)
- Direction validation
- Instrument routing validation
- Kill switch check
- In-process duplicate signal dedup (`_seen_signal_ids` set)
- 3-layer position governance: per-instrument cap + global cap (2) + correlated exposure guard

### In execute_signal() — execution.py
- State engine gate (`can_execute()`) — checks eod_lock, macro_lock, red_folder_lock, trade_permission
- Execution governance check (strategy allowlist, instrument allowlist, grade floor, daily trade count)
- VERDICT != TAKE filter
- daily_loss_trade_hit (first-trade-loss rule)
- Session trade limit (`_SESSION_MAX_TRADES`, default 5)
- Session boundary auto-close of stale positions
- Live Alpaca position conflict check (direct broker query)
- Pending order conflict check (direct broker query)
- Per-instrument cooldown check
- Thesis conflict check (60-min flip window)
- Red folder window (±30 min HIGH macro events)
- Daily loss limit (Alpaca P&L query against `_LOSS_LIMIT_USD = -1000.0`)

### In _execute_alpaca_etf()
- Market clock check (api.get_clock().is_open)
- PRE_ORDER_INTENT trace written before submit_order
- CRITICAL_AUDIT_FAILURE trace if journal write fails
- CRITICAL_AUDIT_FAILURE trace if execution trace write fails
- Bracket order: entry (market) + take-profit (limit) + stop-loss (stop)

---

## 4. MISSING SAFETY CHECKS (gaps)

### Q1. Is there an execution_request_id tying the full lifecycle?
**No.** There is no atomic identifier for a single execution attempt. The signal_id, trace _new_id(), and order_id are three separate namespaces with no common key. If an order is placed but the post-order trace fails, there is no way to cross-reference the pre-order intent record with the Alpaca order.

### Q2. Is the signal_id linked to the decision_id from reasoning?
**No.** `signal_id` in execution_bridge.py = `NOVA_{key}_{signal}_{uuid4.hex[:8].upper()}` — UUID generated at bridge entry. The decision snapshot in `donna_mcp_snapshots.json` uses its own `id` field. No field joins them.

### Q3. Is dedup persistent across restarts?
**No.** `_seen_signal_ids: set[str]` is in-process only. On monitor restart (e.g., crash, daily restart via Task Scheduler), the set is empty. A signal that fired just before the restart could re-fire immediately after.

### Q4. Is there a stale signal check?
**No.** No timestamp comparison between when the signal was generated and when it reaches execute_signal(). A webhook could carry a 20-minute-old signal; the system would trade it as current.

### Q5. Is `_LOSS_LIMIT_USD` prop-firm configurable?
**No.** Hardcoded to `-1000.0` in execution.py. No env var. No prop_risk_config. No connection to account size. For a $50K Apex/Topstep account with a $2K daily loss cap, this is incorrect.

### Q6. Does the state engine track prop-firm balance fields?
**No.** `DonnaStateEngine` has no `starting_balance`, `current_balance`, `trailing_high_watermark`, `max_daily_loss_prop`, `max_total_loss_prop`, or `trailing_drawdown_amount`. Without these, the system cannot enforce prop-firm daily loss, max loss, or trailing drawdown rules.

### Q7. Is trailing drawdown tracked anywhere?
**No.** No trailing HWM field exists in state_engine, risk_state, or any other file. Prop firms with trailing drawdown rules (Apex, Topstep) would be violated invisibly.

### Q8. Does the execution trace link to decision_id?
**No.** `execution_trace.py` `_new_id()` = `f'{int(time.time() * 1000)}-{random.randint(100, 999)}'`. No `decision_id` field in any trace entry type (SIGNAL_RECEIVED, VERDICT, REJECTED, EXECUTED, PRE_ORDER_INTENT, POST_ORDER_SUBMITTED, CRITICAL_AUDIT_FAILURE, BRIDGE_REJECTED, DECISION_CHAIN, REASONING_SNAPSHOT).

### Q9. Is the bracket order verified to have filled?
**No fill confirmation gate.** After `api.submit_order()`, execution returns success if the order was accepted by Alpaca. Whether the entry leg fills, whether the bracket legs attach, and whether the stop is actually active is checked lazily by `check_position_outcomes()` on the next poll cycle, not at order time.

### Q10. Is there a protective order verification step?
**No.** After `api.submit_order()`, no check confirms the bracket stop leg is live. If Alpaca accepts the order but the stop leg fails to attach (edge case on paper API), the position is UNPROTECTED. No `UNPROTECTED_POSITION` trace status exists.

### Q11. Is there reconciliation between state engine and Alpaca?
**Partial.** `execute_signal()` does a live Alpaca position check before each order (correct). But `state_engine.open_positions` is only updated by NOVA itself; positions opened outside NOVA (manual dashboard trades, Alpaca dashboard) would not appear in state engine. No periodic reconciliation loop exists.

### Q12. Is there a minimum trading days enforcement?
**No.** Prop firms (e.g. Apex) require minimum 5–10 trading days on the evaluation. NOVA has no `min_trading_days` counter or enforcement.

### Q13. Is there a consistency rule enforcement?
**No.** Some prop firms cap single-day profit as a % of total profit (e.g. no single day > 40% of target). NOVA has no `consistency_rule_enabled` or `daily_profit_cap` enforcement.

### Q14. Is flatten_before_close enforced as a safety gate?
**Partial.** `close_all_positions_eod()` runs at 3:45 PM ET via main.py background loop. But if the Render deployment is down, or if the local monitor is the only active process and crashes, the EOD flatten may not execute.

### Q15. Is news trading blocked?
**Partial.** Red folder governance covers HIGH-importance economic calendar events (±30 min). Ad-hoc breaking news is partially handled via macro_risk state from the news feed, but no explicit `news_trading_allowed = false` gate exists at broker level.

### Q16. Is there a max_contracts_per_symbol check?
**Partial.** Position governance in execution_bridge.py enforces a global cap of 2 concurrent positions. Per-symbol ETF share cap exists (SPY 200, QQQ 150) but these are sizing caps, not contract count caps in a prop-firm sense.

### Q17. What happens on a duplicate webhook delivery?
**Partial protection.** Dedup in execution_bridge.py uses `_seen_signal_ids`. But this is in-process only. If TradingView webhook delivers the same alert twice within 1 second (common on fast moves), the dedup key is `{instrument}:{signal}:{setup_type}:{grade}` — not timestamp-based — so it would catch the second delivery only if the first signal_id is still in the set (which it is, within the same process lifetime).

---

## 5. PROP FIRM RULE GAPS (by firm type)

### APEX TRADER FUNDING (most common prop firm)
| Rule | NOVA Status | Gap |
|---|---|---|
| Daily loss limit (e.g. $1K on $50K) | Hardcoded $-1000 | Not tied to account size / prop config |
| Max trailing drawdown | NOT TRACKED | **Critical gap** |
| Min trading days (e.g. 10 days) | Not counted | Missing field |
| Consistency rule (no day > 40% of target) | Not enforced | Missing |
| Flatten before close | EOD close exists | Cloud-only reliability risk |
| Max contracts per symbol | Sizing cap only | Not contract-count gated |
| No news trading | Red folder only | Not explicit |

### TOPSTEP / MYFOREXFUNDS (similar structure)
| Rule | NOVA Status | Gap |
|---|---|---|
| Daily loss limit | Hardcoded | Not configurable |
| Max loss (absolute) | Not tracked | **Critical gap** |
| Trailing drawdown | Not tracked | **Critical gap** |
| Min trading days | Not tracked | Missing |

---

## 6. DUPLICATE / STALE / CONTRACT / RECONCILIATION RISKS

### Duplicate signal risk
- **Level:** MEDIUM-HIGH
- In-process dedup clears on restart. Monitor restarts daily at 9:15 AM ET via Task Scheduler. If a signal fires at 9:14:55 and the monitor restarts at 9:15:00, the same signal could fire again on startup.
- Dedup key does not include timestamp, so the same signal type on the same day is treated as new on restart.
- **Proposed fix:** persistent dedup log in state_engine.json with (instrument:signal:setup_type:grade:date) key.

### Stale signal risk
- **Level:** HIGH
- No signal age check. Webhook payloads can arrive late (TradingView network delay, Render queue). A PROS signal that printed at 09:35 but arrives at 09:55 would be executed as if current.
- Reasoning cycle snapshots have `timestamp_et` but this is never compared to signal arrival time in the execution path.
- **Proposed fix:** `signal_generated_at` field on every signal; reject if `now() - signal_generated_at > MAX_SIGNAL_AGE_SECONDS` (e.g. 300s).

### Contract/position count risk
- **Level:** LOW-MEDIUM**
- ETF share caps are hardcoded constants. No dynamic cap tied to prop-firm contract rules.
- No position-count-per-symbol gate at execution.py level (bridge has global cap of 2).

### Daily drawdown risk
- **Level:** HIGH
- `_LOSS_LIMIT_USD = -1000.0` is hardcoded. If prop account daily loss limit is $800, the system would continue trading past the prop limit until it hit NOVA's $1000 floor.
- P&L source is Alpaca `get_account().pnl_today` — correct but adds one network call per potential trade.

### Trailing drawdown risk
- **Level:** CRITICAL**
- No tracking whatsoever. A prop firm with trailing drawdown (e.g. Apex: starting balance is HWM, drawdown trails as profits increase) would be violated without any warning.

### Protective order risk
- **Level:** MEDIUM**
- Bracket order placed atomically. If Alpaca accepts the parent market order but the stop leg silently fails (platform issue), no check catches it.
- `_cancel_pending_orders_for_symbol()` is used before closing positions — correct. But no verification that bracket legs survived order submission.

### Reconciliation risk
- **Level:** MEDIUM**
- `check_position_outcomes()` matches by `order_id` (bracket parent). If an order_id is wrong or the leg matching fails, a closed trade remains OPEN in the journal.
- Journal read-modify-write has no process-wide lock (documented in `project_journal_write_lock_backlog.md`).
- No periodic broker↔journal reconciliation run (e.g. daily summary comparison).

---

## 7. EXECUTION FLOW RISK MAP (per-stage)

```
Stage                    | Risk Level | Key Risk
─────────────────────────┼────────────┼──────────────────────────────────────────
Signal generation         | LOW        | Deterministic NOVA reasoning
Bridge gate chain         | LOW        | 13 gates, well-tested
Dedup check               | MEDIUM     | Not persistent across restarts
Stale signal check        | HIGH       | Completely absent
execute_signal() gates    | LOW-MEDIUM | Thorough, but loss limit hardcoded
Prop balance check        | CRITICAL   | Absent — no trailing drawdown, no max loss
Broker order submission   | LOW        | Bracket order, pre/post trace
Protective order verify   | MEDIUM     | No confirmation fill check
State engine update       | LOW        | Thread-safe, file-backed
Journal write             | MEDIUM     | Write-lock absent, audit failure surfaced
Outcome reconciliation    | MEDIUM     | Lazy poll, no forced reconciliation
EOD flatten               | MEDIUM     | Cloud-dependent; crash risk
```

---

## 8. EXECUTION BOT V2 — PROPOSED ARCHITECTURE

Execution Bot v2 introduces three new concepts:

1. **execution_request_id** — An atomic UUID generated the moment a signal enters the execution path. Ties every downstream record (trace entries, journal entry, Alpaca order_id, dedup log) to one root ID.

2. **prop_risk_config** — A configurable JSON record (stored in `donna_settings.json` or a dedicated `donna_prop_config.json`) that defines all prop-firm rules. Execution gates read from this config, not from hardcoded constants.

3. **Dry-run validation mode** — Full gate chain executed, decisions logged, but `api.submit_order()` is never called. Produces complete trace and journal entries marked `dry_run=true`. Clean dry-run run is required before any live prop trading.

---

## 9. PROPOSED: execution_request SCHEMA

```python
execution_request = {
    # Identity chain
    "execution_request_id": str,    # UUID4 — generated at bridge entry
    "decision_id": str,             # from reasoning snapshot (mcp_snapshots.json)
    "signal_id": str,               # NOVA_{key}_{signal}_{hex8}
    "source": str,                  # "BRIDGE" | "WEBHOOK" | "MANUAL"

    # Signal payload
    "instrument": str,              # "MNQ" | "MES" | "NQ" | "ES"
    "routed_etf": str,              # "QQQ" | "SPY"
    "direction": str,               # "LONG" | "SHORT"
    "setup_type": str,              # "PROS_LONG" | "ORB_E1_SHORT" | etc.
    "grade": str,                   # "A" | "B"
    "session": str,                 # session label at receipt time
    "signal_generated_at": str,     # ISO UTC — when NOVA generated the signal
    "signal_received_at": str,      # ISO UTC — when bridge received it
    "signal_age_seconds": float,    # signal_received_at - signal_generated_at

    # Status lifecycle
    "status": str,                  # See Section 10
    "rejection_reason": str | None,
    "rejection_code": str | None,

    # Broker result
    "order_id": str | None,
    "entry_ref": float | None,
    "stop_px": float | None,
    "target_px": float | None,
    "qty": int | None,
    "risk_usd": float | None,

    # Prop-firm context snapshot at execution time
    "prop_context": {
        "current_balance": float,
        "starting_balance": float,
        "trailing_hwm": float,
        "daily_pnl_at_entry": float,
        "daily_loss_remaining": float,
        "trailing_drawdown_remaining": float,
        "trades_today": int,
    },

    # Dry-run flag
    "dry_run": bool,

    # Timestamps
    "created_at": str,
    "updated_at": str,
}
```

---

## 10. PROPOSED: STATUS LIFECYCLE

Every execution_request moves through exactly one terminal status:

```
RECEIVED
    │
    ├─ REJECTED_BAD_PAYLOAD        ← missing required fields
    ├─ REJECTED_STALE              ← signal_age_seconds > MAX_SIGNAL_AGE
    ├─ REJECTED_DUPLICATE          ← matches persistent dedup log
    ├─ REJECTED_SESSION            ← outside allowed session / state gate
    ├─ REJECTED_NEWS_WINDOW        ← red folder / news trading blocked
    ├─ REJECTED_MAX_TRADES         ← daily or session trade limit
    ├─ REJECTED_MAX_CONTRACTS      ← position count gate
    ├─ REJECTED_OPEN_POSITION      ← existing same-direction position
    ├─ REJECTED_PROP_DAILY_LOSS    ← daily loss limit (prop config)
    ├─ REJECTED_PROP_MAX_LOSS      ← max total loss (prop config)
    ├─ REJECTED_PROP_TRAILING_DRAWDOWN ← trailing drawdown limit
    │
VALIDATED
    │
SUBMITTED_TO_BROKER
    │
    ├─ BROKER_ACCEPTED
    │       │
    │   ENTRY_FILLED
    │       │
    │       ├─ PROTECTIVE_ORDERS_PLACED    ← stop + target confirmed live
    │       │       │
    │       │   EXIT_FILLED
    │       │       │
    │       │   JOURNALED
    │       │       │
    │       │   RECONCILED                 ← broker P&L matches journal
    │       │
    │       └─ UNPROTECTED_POSITION        ← stop leg not confirmed
    │
    └─ FAILED                              ← broker rejected, timeout, error
```

---

## 11. PROPOSED: prop_risk_config SCHEMA

```python
prop_risk_config = {
    "prop_firm_name": str,              # "APEX" | "TOPSTEP" | "MYFOREXFUNDS" | "NONE"
    "account_size": float,              # e.g. 50000.0
    "starting_balance": float,          # account equity at challenge start
    "current_balance": float,           # updated after each close
    "max_daily_loss": float,            # e.g. 1000.0 (positive value, subtracted from balance)
    "max_total_loss": float,            # e.g. 2500.0 (absolute drawdown from starting)
    "trailing_drawdown_enabled": bool,
    "trailing_drawdown_amount": float,  # e.g. 2000.0
    "trailing_drawdown_type": str,      # "FIXED_FROM_START" | "TRAILS_WITH_PROFIT"
    "min_trading_days": int,            # e.g. 10
    "max_contracts_total": int,         # concurrent contract cap
    "max_contracts_per_symbol": int,    # per-instrument cap
    "max_trades_per_day": int,          # overrides NOVA_SESSION_MAX_TRADES
    "allowed_symbols": list[str],       # ["MES", "MNQ", "ES", "NQ"]
    "allowed_sessions": list[str],      # ["NY_OPEN", "NY_AM", "NY_PM"]
    "flatten_before_close": bool,       # enforce EOD close
    "news_trading_allowed": bool,       # if False, red folder always blocks
    "consistency_rule_enabled": bool,   # single-day profit cap
    "daily_profit_cap_if_any": float | None,  # e.g. 0.4 = no day > 40% of target
}
```

---

## 12. PROPOSED: execution_trace_v2 ENTRY SCHEMA

```python
trace_entry_v2 = {
    "id": str,                          # _new_id() — keeps existing format
    "execution_request_id": str,        # NEW — links all entries for one execution attempt
    "decision_id": str,                 # NEW — links to reasoning snapshot
    "signal_id": str,                   # existing
    "type": str,                        # existing log types + UNPROTECTED_POSITION
    "timestamp": str,                   # ISO UTC
    "dry_run": bool,                    # NEW
    # ... all existing fields preserved
}
```

---

## 13. PROPOSED TESTS (Execution Bot v2)

| Test | What it verifies |
|---|---|
| `test_execution_request_id_generated` | execution_request_id created on bridge entry, UUID4 format |
| `test_decision_id_chain` | decision_id from snapshot flows into execution_request |
| `test_stale_signal_rejection` | signal with signal_age_seconds > MAX blocked with REJECTED_STALE |
| `test_fresh_signal_passes_age_check` | signal within age window passes |
| `test_dedup_persistent_across_restart` | duplicate key in state engine → REJECTED_DUPLICATE even after "restart" |
| `test_dedup_different_signals_pass` | different signal key passes dedup |
| `test_prop_daily_loss_blocks` | prop_risk_config daily loss → REJECTED_PROP_DAILY_LOSS |
| `test_prop_max_loss_blocks` | current_balance - max_total_loss breach → REJECTED_PROP_MAX_LOSS |
| `test_trailing_drawdown_blocks` | trailing HWM - trailing_drawdown_amount breach → REJECTED_PROP_TRAILING_DRAWDOWN |
| `test_trailing_hwm_updates_after_win` | HWM advances when current_balance exceeds prior HWM |
| `test_trailing_hwm_does_not_retreat` | HWM never decreases |
| `test_dry_run_no_broker_call` | dry_run=True → api.submit_order never called |
| `test_dry_run_full_trace_written` | dry_run=True → all trace entries written, marked dry_run=true |
| `test_unprotected_position_status` | bracket leg confirmation failure → UNPROTECTED_POSITION status |
| `test_protected_position_status` | bracket legs confirmed → PROTECTIVE_ORDERS_PLACED status |
| `test_execution_request_in_trace` | every trace entry for an execution has execution_request_id |
| `test_min_trading_days_blocks` | trades_today_count < min_trading_days enforcement |
| `test_consistency_rule_blocks` | daily_pnl > daily_profit_cap → blocked |
| `test_allowed_sessions_filter` | session not in allowed_sessions → REJECTED_SESSION |
| `test_max_trades_per_day_prop` | prop max_trades_per_day overrides NOVA default |

---

## 14. FILES LIKELY TO CHANGE IN V2

| File | Change |
|---|---|
| `services/execution_bridge.py` | Add execution_request_id generation; persistent dedup log; stale signal check; prop_risk_config gate; decision_id extraction; status lifecycle tracking |
| `services/execution.py` | Remove hardcoded `_LOSS_LIMIT_USD`; read from prop_risk_config; add trailing drawdown gate; add dry_run mode (skip api.submit_order); prop balance update after close |
| `services/execution_trace.py` | Add `execution_request_id` and `decision_id` fields to all entry types; add UNPROTECTED_POSITION log type; add PROTECTIVE_ORDERS_PLACED log type; add RECONCILED log type |
| `core/state_engine.py` | Add prop-firm fields: `current_balance`, `starting_balance`, `trailing_hwm`, `max_daily_loss_prop`, `max_total_loss_prop`, `trailing_drawdown_amount`; persistent dedup log; `trading_days_count` counter |
| `donna_settings.json` (or new `donna_prop_config.json`) | Add `prop_risk_config` block |
| `engines/reasoning.py` | Ensure `decision_id` is stable and passed through to signal payload so bridge can read it |
| `tests/test_execution_bot_v2.py` | New file — all tests from Section 13 |

---

## 15. PHASED ROLLOUT PLAN

**Constraint:** No live prop trading until dry-run execution validation is clean.

### Phase 1: Identity + Protection (First Implementation)
**Goal:** Every execution attempt gets an ID. Dedup and stale signal are permanent.

1. **execution_request_id / decision_id chain**
   - Generate UUID4 at bridge entry
   - Pass decision_id from reasoning snapshot (if available) through bridge
   - Include execution_request_id in every trace entry and journal entry
   - Zero behavior change to gates or broker path

2. **Persistent duplicate protection**
   - Replace `_seen_signal_ids` (in-process) with a state engine dedup log
   - Key: `{instrument}:{signal}:{setup_type}:{grade}:{date_et}`
   - Persisted to `donna_state_engine.json`
   - Daily reset on new ET day (same as trade count)

3. **Stale signal protection**
   - Add `signal_generated_at` to every AlertData / signal payload
   - Add `MAX_SIGNAL_AGE_SECONDS` constant (default: 300s / 5 min)
   - Reject with REJECTED_STALE if signal_age_seconds > MAX
   - Log age in every trace entry

4. **prop_risk_config skeleton**
   - Add `prop_risk_config` block to `donna_settings.json`
   - Schema from Section 11 with all fields present (no enforcement yet)
   - Read-only in execution path — logged in execution_request but not gated

5. **Dry-run validation mode**
   - Add `DRY_RUN_EXECUTION` env var (default: false)
   - When true: full gate chain runs, all trace/journal written, `api.submit_order()` skipped
   - All trace and journal entries marked `dry_run: true`
   - Dry-run pass count tracked; required before live prop trading

### Phase 2: Prop Risk Gates
**Goal:** prop_risk_config is enforced, not just logged.

- Prop daily loss gate (replaces hardcoded `_LOSS_LIMIT_USD`)
- Prop max total loss gate (new)
- Trailing drawdown gate + HWM tracking (new)
- Minimum trading days counter (new)
- Consistency rule enforcement (if enabled)
- `current_balance` update after each close

### Phase 3: Protective Order Verification
**Goal:** Every open position is confirmed protected.

- After submit_order, verify bracket legs exist via Alpaca orders API
- Log PROTECTIVE_ORDERS_PLACED or UNPROTECTED_POSITION
- Alert on UNPROTECTED_POSITION (Telegram + Discord critical channel)

### Phase 4: Reconciliation
**Goal:** State engine matches broker reality at all times.

- Periodic (hourly) broker↔state-engine reconciliation
- Journal reconciliation: compare journal OPEN entries to Alpaca open positions
- Daily EOD reconciliation report
- RECONCILED trace status after journal matches broker close

---

## 16. QUESTIONS ANSWERED (27/27)

| # | Question | Answer |
|---|---|---|
| Q1 | What is the current execution flow? | Section 1 |
| Q2 | What is the source-of-truth for each state? | Section 2 |
| Q3 | What safety checks currently exist? | Section 3 |
| Q4 | What safety checks are missing? | Section 4 |
| Q5 | Is there an execution_request_id? | No — Section 4 Q1 |
| Q6 | Is signal_id linked to decision_id? | No — Section 4 Q2 |
| Q7 | Is dedup persistent? | No — Section 4 Q3 |
| Q8 | Is there a stale signal check? | No — Section 4 Q4 |
| Q9 | Is _LOSS_LIMIT_USD prop configurable? | No — Section 4 Q5 |
| Q10 | Does state engine track prop balance? | No — Section 4 Q6 |
| Q11 | Is trailing drawdown tracked? | No — Section 4 Q7 |
| Q12 | Does execution trace link decision_id? | No — Section 4 Q8 |
| Q13 | Is bracket fill confirmed? | No — Section 4 Q9 |
| Q14 | Is protective order verified? | No — Section 4 Q10 |
| Q15 | Is there broker↔state reconciliation? | Partial — Section 4 Q11 |
| Q16 | Is min trading days enforced? | No — Section 4 Q12 |
| Q17 | Is consistency rule enforced? | No — Section 4 Q13 |
| Q18 | Is flatten-before-close safe? | Partial — Section 4 Q14 |
| Q19 | Is news trading explicitly blocked? | Partial — Section 4 Q15 |
| Q20 | Is max_contracts_per_symbol gated? | Partial — Section 4 Q16 |
| Q21 | What happens on duplicate webhook? | Partial — Section 4 Q17 |
| Q22 | What are the prop firm rule gaps? | Section 5 |
| Q23 | What are duplicate/stale/contract/reconciliation risks? | Section 6 |
| Q24 | What is the execution flow risk by stage? | Section 7 |
| Q25 | What is the proposed v2 architecture? | Section 8 |
| Q26 | What schemas does v2 require? | Sections 9, 11, 12 |
| Q27 | What is the phased rollout? | Section 15 |

---

## 17. BROKER MODE REFERENCE (current)

```
BROKER_MODE = "ALPACA_ETF"

Routing:
  MES / ES  → SPY shares
  MNQ / NQ  → QQQ shares

ETF sizing constants (hardcoded):
  SPY: stop=$10.00, target=$20.00, cap=200 shares
  QQQ: stop=$15.00, target=$30.00, cap=150 shares

Risk per trade: floor(equity × RISK_PCT / stop_dist), capped
  NOVA_RISK_PCT_PER_TRADE = 1.0% (env var)
  _LOSS_LIMIT_USD = -1000.0 (HARDCODED — not prop configurable)
  _SESSION_MAX_TRADES = 5 (env: NOVA_SESSION_MAX_TRADES)
  NOVA_AUTO_EXECUTE = false (env var, must be true to reach broker)
```

---

*This document is read-only. No execution changes have been made.*  
*Next step: decide and implement Phase 1 from Section 15.*
