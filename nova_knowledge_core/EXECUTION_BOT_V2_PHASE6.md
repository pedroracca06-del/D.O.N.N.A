# Execution Bot v2 — Phase 6: Prop Account State Tracking

## What Was Built

Phase 6 adds automated prop account state tracking. On every safety check cycle the
system reads the Alpaca account balance, updates the high-water mark, computes
trailing drawdown / daily loss / total loss states, and sends Discord alerts when
any rule approaches or exceeds its limit.

**This phase is state tracking and alerting only.**
No trades are placed, no orders are cancelled or modified, no positions are flattened.

**Files changed:**
- `services/prop_account_state.py` — NEW: full prop account state module + Phase 5.1 alert controls
- `services/execution_safety.py` — Phase 6 block wired into `run_execution_safety_check()`
- `main.py` — `GET /api/prop-account/state` endpoint
- `tests/test_execution_bot_v2_phase6.py` — 27 tests (19 core + 5 Phase 5.1 integration + 3 endpoint/isolation)
- `nova_knowledge_core/EXECUTION_BOT_V2_PHASE6.md` — this doc

**Test count:** 146/146 total (P1: 19, P2: 31, P3: 31, P4: 21, P5: 17, P6: 27)

---

## State File: `nova_prop_account_state.json`

Auto-created on first run with zero defaults. Written on every update cycle.

```json
{
  "prop_firm_name":              "Apex",
  "account_size":                50000.0,
  "starting_balance":            50000.0,
  "current_balance":             51200.0,
  "previous_balance":            50800.0,
  "high_water_mark":             51200.0,
  "trailing_drawdown_enabled":   true,
  "trailing_drawdown_amount":    2500.0,
  "trailing_drawdown_floor":     0.0,
  "trailing_drawdown_type":      "trailing",
  "max_daily_loss":              500.0,
  "max_total_loss":              2500.0,
  "daily_start_balance":         50400.0,
  "daily_pnl":                   800.0,
  "daily_loss_remaining":        1300.0,
  "total_loss_remaining":        3700.0,
  "trailing_drawdown_threshold": 48700.0,
  "trailing_drawdown_remaining": 2500.0,
  "trailing_drawdown_status":    "PROP_STATE_OK",
  "daily_loss_status":           "PROP_STATE_OK",
  "total_loss_status":           "PROP_STATE_OK",
  "trading_day":                 "2026-07-01",
  "trade_count_today":           2,
  "last_updated":                "2026-07-01T14:00:00Z",
  "prop_state_status":           "PROP_STATE_OK",
  "broker_account_read":         true
}
```

**Static configuration fields** (user-editable in the file):

| Field | Purpose |
|---|---|
| `prop_firm_name` | Display name (e.g., "Apex", "Topstep") |
| `account_size` | Account tier size |
| `starting_balance` | Balance when evaluation started |
| `trailing_drawdown_enabled` | Enable trailing drawdown monitoring |
| `trailing_drawdown_amount` | Max drawdown from HWM (e.g., 2500 for Apex 50k) |
| `trailing_drawdown_floor` | Absolute floor if it locks (0 = not configured) |
| `trailing_drawdown_type` | `'trailing'` (moves with HWM) or `'static'` (fixed from start) |
| `max_daily_loss` | Daily loss limit in dollars |
| `max_total_loss` | Total loss limit (static; different from trailing DD) |

---

## How Trailing Drawdown Works

Two types, controlled by `trailing_drawdown_type`:

```
trailing (default — Apex / Topstep):
  threshold = high_water_mark - trailing_drawdown_amount
  → threshold moves UP as profits accumulate

static:
  threshold = starting_balance - trailing_drawdown_amount
  → threshold never changes
```

**High-water mark rule:** HWM increases whenever `current_balance > hwm`. It NEVER decreases.

**Warning threshold:** Fires when `remaining ≤ 25% of trailing_drawdown_amount`.
Example: $2,500 DD limit → WARNING fires when remaining ≤ $625.

**Breach threshold:** `remaining ≤ 0` → BREACHED.

---

## Status Constants

```python
PROP_STATE_OK                    # no issues
PROP_DAILY_LOSS_WARNING          # ≤25% of daily limit remains
PROP_DAILY_LOSS_BREACHED         # daily limit exceeded
PROP_TOTAL_LOSS_WARNING          # ≤25% of total limit remains
PROP_TOTAL_LOSS_BREACHED         # total limit exceeded
PROP_TRAILING_DRAWDOWN_WARNING   # ≤25% of trailing DD buffer remains
PROP_TRAILING_DRAWDOWN_BREACHED  # trailing drawdown limit breached
UNKNOWN_ACCOUNT_STATE            # broker read failed; no live data
```

**Worst-wins priority (highest first):**
`UNKNOWN` > `TRAILING_DD_BREACHED` > `TOTAL_LOSS_BREACHED` > `DAILY_LOSS_BREACHED` >
`TRAILING_DD_WARNING` > `TOTAL_LOSS_WARNING` > `DAILY_LOSS_WARNING` > `OK`

The `prop_state_status` field always reflects the worst active status.

---

## Daily Reset Logic

On every `update_prop_account_state_from_broker()` call:

1. Load state from file
2. Compare `trading_day` (stored) to today (ET timezone)
3. If different → reset: `daily_pnl = 0`, `trade_count_today = 0`, `daily_start_balance = current_balance`
4. Set `trading_day = today_ET`

Daily reset does NOT touch HWM — that carries across days (prop firms track HWM globally, not per-day).

---

## Phase 5.1 Alert Controls Integration

Prop alerts obey the same Phase 5.1 env vars as the safety monitor:

| Variable | Default | Effect on prop alerts |
|---|---|---|
| `NOVA_EXECUTION_SAFETY_DISCORD_ENABLED` | `false` | `false` → Discord suppressed; state/log still written |
| `NOVA_EXECUTION_SAFETY_ALERT_COOLDOWN_SECONDS` | `900` | Seconds between repeat alerts per key |

### Suppression reasons in `alerts_suppressed`:
- `PROP_TRAILING_DRAWDOWN_WARNING:COOLDOWN` — within cooldown window
- `PROP_TRAILING_DRAWDOWN_WARNING:DISCORD_DISABLED` — Discord off

When Discord is disabled: alert is NOT recorded in the cooldown registry (so when re-enabled, alerts fire immediately instead of waiting out a stale cooldown).

### Persistent cooldown registry

File: `nova_prop_alert_registry.json`

```json
{
  "PROP_TRAILING_DRAWDOWN_WARNING": {
    "alert_key": "PROP_TRAILING_DRAWDOWN_WARNING",
    "last_sent_at": "2026-07-06T14:00:00Z"
  }
}
```

Loaded at module import time into `_prop_cooldown` (in-memory dict). Survives process restarts.

---

## Integration with Phase 5 Safety Loop

Phase 6 runs as a non-blocking block inside `run_execution_safety_check()`:

```
run_execution_safety_check()
  ├── Phase 5.1: Discord gate + persistent cooldown registry
  ├── Phase 5: broker reconciliation + UNPROTECTED_POSITION alerts
  └── Phase 6 (non-blocking try/except):
        ├── update_prop_account_state_from_broker()   ← reads Alpaca account (read-only)
        ├── populate prop_account_summary in status dict
        └── check_and_send_prop_alerts()              ← respects DISCORD_ENABLED + cooldown
```

If Phase 6 raises any exception, the error is captured in `warnings[]` and the rest
of the safety check is unaffected. `prop_account_summary: {}` is always present in
the status dict.

**Cooldown:** Prop alerts use a separate cooldown dict (`_prop_cooldown`) backed by
`nova_prop_alert_registry.json`. Persists across restarts. Uses
`NOVA_EXECUTION_SAFETY_ALERT_COOLDOWN_SECONDS` env var (default 900s).

---

## Prop Alert Discord Embeds

Alert level → color:
- `WARNING`: orange (`0xFF8800`)
- `CRITICAL` (BREACHED): red (`0xFF0000`)

Example CRITICAL embed:
```
🚨  PROP ACCOUNT CRITICAL: PROP_TRAILING_DRAWDOWN_BREACHED

Trailing drawdown PROP_TRAILING_DRAWDOWN_BREACHED: current=$49000,
threshold=$49500, remaining=$-500

Fields:
  Current Balance   $49000
  High-Water Mark   $52000
  Daily P&L         $-800
  Prop Firm         Apex
  Action Required   MANUAL REVIEW REQUIRED
  Auto-Action       None — alert-only. No trades halted automatically.

Footer: NOVA Prop Account Monitor • Phase 6
```

Channel priority: `DISCORD_CHANNEL_SYSTEM_HEALTH` → `DISCORD_CHANNEL_LIVE`.

---

## GET /api/prop-account/state

New read-only endpoint that returns the latest prop account state.

**Priority:**
1. Call `update_prop_account_state_from_broker()` (live Alpaca read + file write)
2. If that fails → fall back to `load_prop_account_state()` (last saved file)
3. If both fail → `{'prop_state_status': 'UNKNOWN_ACCOUNT_STATE', 'error': '...'}`

**What it never does:** place orders, cancel orders, modify positions.

---

## What Remains Manual

- **Acting on a breach:** Trader must manually reduce or close positions
- **Setting limits:** Edit `nova_prop_account_state.json` directly to configure
  `trailing_drawdown_amount`, `max_daily_loss`, `max_total_loss`, etc.
- **Enforcement:** Phase 7 will add dry-run prop enforcement trial (gate new trades
  when HWM drawdown is breached) — not implemented here

---

## Phase 7 Preview: Dry-Run Prop Enforcement

Phase 7 scope (NOT yet implemented):

1. **Enforcement gate** — When `trailing_drawdown_status == PROP_TRAILING_DRAWDOWN_BREACHED`
   and `NOVA_PROP_GATES_ENABLED=true`, block new entry signals
2. **Dry-run trial** — Run gate in dry-run mode first (log-only); compare signal outcomes
   over 10+ sessions to confirm accuracy before enabling
3. **Readiness checklist** before enabling:
   - Phase 5 monitor running for 5+ live sessions with no false positives
   - Phase 6 HWM values verified accurate against broker portal
   - `trailing_drawdown_amount` confirmed correct for your account tier
   - Dry-run gate tested for at least 3 sessions
   - User explicitly sets `NOVA_PROP_GATES_ENABLED=true`

**Phase 7 gate:** Do not enable enforcement until all items above are confirmed.

---

## Safety Contract

This module MUST NEVER:
- Submit orders
- Cancel orders
- Modify positions
- Call any Alpaca write endpoint (`submit_order`, `cancel_order_by_id`, `close_all_positions`, etc.)

The only external call made is `client.get_account()` (read-only).
Discord embeds are outbound-only notifications.
