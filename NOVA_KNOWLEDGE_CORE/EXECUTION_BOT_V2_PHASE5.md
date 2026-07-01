# Execution Bot v2 — Phase 5: Periodic Safety Monitor + CRITICAL Alerting

## What Was Built

Phase 5 adds a background safety monitor that runs every 60 seconds during market hours (120s off-hours), reads broker/journal state, detects unprotected positions, and sends CRITICAL Discord alerts with a 5-minute per-instrument cooldown.

**Files changed:**
- `services/execution_safety.py` — NEW: full safety monitor module
- `main.py` — import + `execution_safety_loop()` background task + updated endpoint
- `tests/test_execution_bot_v2_phase5.py` — 17 tests
- `nova_knowledge_core/EXECUTION_BOT_V2_PHASE5.md` — this doc

**Test count:** 119/119 total (P1: 19, P2: 31, P3: 31, P4: 21, P5: 17)

---

## How the Periodic Safety Check Works

`run_execution_safety_check()` runs inside `execution_safety_loop()` which fires via `asyncio.create_task()` at startup:

```
execution_safety_loop (main.py)
  └── run_execution_safety_check() [asyncio.to_thread]
        ├── get_execution_safety_status()        # Phase 4 — detect unprotected positions
        ├── get_broker_positions_safe()          # Phase 3 — Alpaca read-only
        ├── get_broker_orders_safe()             # Phase 3 — Alpaca read-only
        ├── get_open_journal_trades_safe()       # Phase 3 — journal OPEN trades
        ├── reconcile_execution_state() × pos   # Phase 3 — per-position reconciliation
        ├── _is_in_cooldown() for each alert     # 5-min dedup per instrument+alert_type
        ├── send_safety_discord_alert()          # Discord embed — if not in cooldown
        ├── _write_safety_status()               # nova_execution_safety_status.json
        └── _append_safety_log()                 # nova_execution_safety_log.json
```

**Loop cadence:**
- Market hours (09:00–16:30 ET weekdays): every 60 seconds
- Off-hours: every 120 seconds

**Status values:**
- `NO_OPEN_POSITIONS` — no broker positions found; nothing to protect
- `ALL_POSITIONS_PROTECTED` — all positions have a stop order
- `UNPROTECTED_POSITIONS_DETECTED` — at least one position has no stop
- `UNKNOWN_BROKER_STATE` — broker reader failed; error captured in `errors[]`

---

## How CRITICAL Alerts Work

When `get_execution_safety_status()` returns one or more `emergency_alerts` (positions with no stop order), Phase 5 sends a Discord embed for each — subject to cooldown.

**Alert flow:**
1. Phase 4 detects unprotected position → builds `emergency_alert` dict (`CRITICAL` severity)
2. Phase 5 checks cooldown for that `instrument + alert_type` pair
3. If NOT in cooldown → `send_safety_discord_alert(alert)` → Discord REST API
4. `_record_alert_sent()` sets the timestamp for this pair
5. Result logged in `alerts_sent` list in the status dict

**Discord channel priority:**
- Uses `DISCORD_CHANNEL_SYSTEM_HEALTH` if set
- Falls back to `DISCORD_CHANNEL_LIVE`
- Returns `{'ok': False, 'error': '...'}` if neither is configured (non-blocking)

**Embed content:**
- Title: `🚨 CRITICAL: UNPROTECTED POSITION DETECTED`
- Body: instrument, side, qty, detected_at, explicit "NO AUTO-ACTION WAS TAKEN"
- Fields: symbol, instrument, side, qty, required action, auto-action = None
- Footer: `NOVA Execution Safety Monitor • Phase 5`

---

## Cooldown Behavior

Cooldown prevents alert spam for the same unprotected position:

```
key = f'{INSTRUMENT}__{ALERT_TYPE}'   # e.g. 'QQQ__UNPROTECTED_POSITION'
```

- Default cooldown: **300 seconds (5 minutes)**
- Scoped per instrument+alert_type pair — QQQ and SPY have independent cooldowns
- State is **in-memory only** — resets on process restart (intentional: no stale suppression across days)
- `cooldown_seconds=0` disables cooldown entirely (useful in tests)
- `clear_cooldown_state()` is exposed for testing; not called from production paths

**Cooldown lifecycle:**
```
First alert (t=0) → send Discord → record timestamp
Check at t+60s    → elapsed=60s < 300s → SUPPRESSED, logged in alerts_suppressed_by_cooldown
Check at t+300s   → elapsed=300s, not < 300s → fires again
```

---

## Files Written

**`data/nova_execution_safety_status.json`** — latest check result, overwritten each cycle:
```json
{
  "checked_at": "2026-06-30T14:00:00Z",
  "status": "UNPROTECTED_POSITIONS_DETECTED",
  "open_positions_count": 1,
  "open_orders_count": 0,
  "open_journal_count": 0,
  "protected_positions": [],
  "unprotected_positions": [{"symbol": "QQQ", "side": "long", "qty": 10.0, ...}],
  "emergency_alerts": [{...}],
  "reconciliations": [{"symbol": "QQQ", "reconciliation_status": "JOURNAL_MISSING", ...}],
  "alerts_sent": [{"instrument": "QQQ", "alert_type": "UNPROTECTED_POSITION", "discord": {"ok": true}}],
  "alerts_suppressed_by_cooldown": [],
  "warnings": [...],
  "errors": []
}
```

**`data/nova_execution_safety_log.json`** — rolling append-only log, capped at 1000 entries. Each entry is the status dict plus `_log_type: "SAFETY_CHECK"`. Oldest entries are dropped when cap is reached.

---

## GET /api/execution-safety/status (Updated)

The endpoint now reads from the status file written by the periodic monitor:

```python
get_latest_safety_status()
```

Priority:
1. Read `nova_execution_safety_status.json` (written by the loop, reflects last cycle)
2. Fall back to live `get_execution_safety_status()` if file missing
3. Return error dict if both fail

This means the endpoint is cheap (file read) rather than triggering a live broker API call on every request.

---

## What Is Still Manual-Only

- **Stopping an unprotected position:** Trader must manually place a stop in the broker UI
- **Reviewing emergency alerts:** Check Discord `#system-health` channel or `/api/execution-safety/status`
- **Acting on reconciliation mismatches:** `JOURNAL_MISSING`, `SIZE_MISMATCH`, etc. are logged but require manual resolution
- **Telegram alerting:** Phase 5 sends to Discord only; Telegram delivery is Phase 6 scope

---

## Why No Auto-Flatten or Auto-Repair Exists

The same constraints from Phase 4 apply:

1. **Ambiguity problem:** Phase 5 detects "no stop order detected NOW." This could mean the stop failed to submit, the stop filled and the journal didn't update, or there's a transient broker API issue. Acting on ambiguous state could cause worse outcomes.

2. **This monitor is a loop, not a trigger:** The safety check runs every 60 seconds. A stop placed 30 seconds ago might not yet appear in broker order state. Auto-flattening based on one cycle's observation is premature.

3. **Prop-firm rules:** Automated order manipulation (including defensive actions) can trigger account reviews at Apex/Topstep. No automated writes run until the reconciliation layer is proven reliable over many observed cycles.

**The design rule: observe, alert, log — let the human decide.**

---

## Phase 6 Scope (What Comes Next)

1. **Prop account state tracking** — `current_balance`, `starting_balance`, `trailing_hwm` auto-updated from Alpaca account endpoint on each safety check cycle
2. **Trailing drawdown HWM gate** — Block new trades when drawdown from HWM exceeds prop-firm rule (Apex/Topstep: $2500 trailing max)
3. **Daily reset logic** — Reset daily P&L, trade count, and HWM at session start; persist state across restarts via state_engine
4. **Consistency rule tracking** — Track daily P&L distribution for prop firms that enforce consistency rules (e.g., no single day > 40% of evaluation profit)
5. **Telegram fallback delivery** — Send CRITICAL alerts to Telegram when Discord fails or is unconfigured

**Phase 6 gate:** Run Phase 5 monitor for at least 5 live market sessions with no false positives before enabling any Phase 6 enforcement gates.
