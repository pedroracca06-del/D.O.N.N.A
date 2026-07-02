# Execution Bot v2 — Phase 6: Prop Account State Tracking

## Purpose

Phase 6 adds a read-only prop account state layer that tracks balance, high-water mark, trailing drawdown, and daily P&L from the Alpaca account. It monitors prop firm risk rules and sends alerts when a rule nears breach.

Phase 6 integrates with Phase 5.1 alert controls — Discord delivery obeys `NOVA_EXECUTION_SAFETY_DISCORD_ENABLED` and cooldown obeys `NOVA_EXECUTION_SAFETY_ALERT_COOLDOWN_SECONDS`.

---

## Safety Contract

This module **MUST NEVER**:
- Submit orders
- Cancel orders
- Modify positions
- Call any Alpaca write endpoint

Only `get_account()` (a read endpoint) is permitted. All write methods are verified absent by Phase 6 tests.

---

## State File

`nova_prop_account_state.json` — auto-created with zero defaults on first run.

```json
{
  "prop_firm_name":              "Apex",
  "account_size":                50000.0,
  "starting_balance":            50000.0,
  "trailing_drawdown_enabled":   true,
  "trailing_drawdown_amount":    2500.0,
  "trailing_drawdown_type":      "trailing",
  "max_daily_loss":              500.0,
  "max_total_loss":              2500.0,
  "current_balance":             50125.0,
  "high_water_mark":             52000.0,
  "daily_pnl":                   125.0,
  "trailing_drawdown_threshold": 49500.0,
  "trailing_drawdown_remaining": 625.0,
  "trailing_drawdown_status":    "PROP_TRAILING_DRAWDOWN_WARNING",
  "daily_loss_status":           "PROP_STATE_OK",
  "total_loss_status":           "PROP_STATE_OK",
  "prop_state_status":           "PROP_TRAILING_DRAWDOWN_WARNING",
  "broker_account_read":         true,
  "last_updated":                "2026-07-02T14:00:00Z"
}
```

Static configuration fields (firm name, limits) are user-editable directly in the file. Dynamic fields are overwritten on each `update_prop_account_state_from_broker()` call.

---

## Status Constants

| Constant | Meaning |
|---|---|
| `PROP_STATE_OK` | No rule breached or near-breach |
| `PROP_DAILY_LOSS_WARNING` | Daily loss ≤ 25% buffer remaining |
| `PROP_DAILY_LOSS_BREACHED` | Daily loss limit hit or exceeded |
| `PROP_TOTAL_LOSS_WARNING` | Total loss ≤ 25% buffer remaining |
| `PROP_TOTAL_LOSS_BREACHED` | Total loss limit hit or exceeded |
| `PROP_TRAILING_DRAWDOWN_WARNING` | Trailing drawdown ≤ 25% buffer remaining |
| `PROP_TRAILING_DRAWDOWN_BREACHED` | Trailing drawdown hit or exceeded |
| `UNKNOWN_ACCOUNT_STATE` | Broker read failed or no state yet |

`prop_state_status` = worst status across all three dimensions.

---

## Trailing Drawdown Types

| Type | Threshold Formula |
|---|---|
| `trailing` | `high_water_mark - trailing_drawdown_amount` |
| `static` | `starting_balance - trailing_drawdown_amount` |

For `trailing` type, HWM updates as balance rises (never decreases). Threshold moves up with HWM.
For `static` type, threshold is fixed from the starting balance.

---

## Alert Controls (Phase 5.1 Integration)

Prop alerts obey the same Phase 5.1 env vars as the safety monitor:

| Variable | Default | Effect on prop alerts |
|---|---|---|
| `NOVA_EXECUTION_SAFETY_DISCORD_ENABLED` | `false` | `false` → alerts logged/suppressed only, Discord not called |
| `NOVA_EXECUTION_SAFETY_ALERT_COOLDOWN_SECONDS` | `900` | Seconds between repeat alerts per alert key |

### Always happens (regardless of Discord setting):
- Prop state computed and saved to `nova_prop_account_state.json`
- Safety status includes `prop_account_summary`

### Only happens when `NOVA_EXECUTION_SAFETY_DISCORD_ENABLED=true` AND not in cooldown:
- `send_prop_alert_discord()` called
- Alert key recorded in `nova_prop_alert_registry.json`

### Suppression reasons in `alerts_suppressed`:
- `PROP_TRAILING_DRAWDOWN_WARNING:COOLDOWN` — within cooldown window
- `PROP_TRAILING_DRAWDOWN_WARNING:DISCORD_DISABLED` — Discord off

When Discord is disabled: NOT recorded in cooldown registry (so when re-enabled, alerts fire immediately).

---

## Persistent Alert Registry

File: `nova_prop_alert_registry.json`

```json
{
  "PROP_TRAILING_DRAWDOWN_WARNING": {
    "alert_key": "PROP_TRAILING_DRAWDOWN_WARNING",
    "last_sent_at": "2026-07-02T14:00:00Z"
  }
}
```

- Loaded at module import time into `_prop_cooldown` (in-memory dict)
- Written on every Discord alert send via `_record_prop_alert_sent()`
- Survives process restarts

---

## Public API

```python
load_prop_account_state() -> dict
save_prop_account_state(state: dict) -> None
get_latest_prop_account_state() -> dict          # file-first, live fallback, never raises
update_prop_account_state_from_broker() -> dict  # main entry: live read + save
compute_trailing_drawdown_state(state) -> dict   # pure function
compute_daily_loss_state(state) -> dict          # pure function
compute_total_loss_state(state) -> dict          # pure function
reset_daily_state_if_new_day(state) -> dict      # returns updated state
get_prop_breach_alerts(state) -> list            # alert dicts, no I/O
check_and_send_prop_alerts(state, cooldown_s) -> dict  # respects Phase 5.1 controls
send_prop_alert_discord(alert, state) -> dict    # Discord only, no broker writes
clear_prop_cooldown_state() -> None              # for testing
```

---

## execution_safety.py Integration

`run_execution_safety_check()` calls `update_prop_account_state_from_broker()` and
`check_and_send_prop_alerts()` on each cycle, then adds `prop_account_summary` to
the returned status dict:

```python
status['prop_account_summary'] = {
    'prop_state_status':           state['prop_state_status'],
    'current_balance':             state['current_balance'],
    'high_water_mark':             state['high_water_mark'],
    'starting_balance':            state.get('starting_balance', 0.0),
    'daily_pnl':                   state.get('daily_pnl', 0.0),
    'daily_loss_remaining':        state.get('daily_loss_remaining'),
    'total_loss_remaining':        state.get('total_loss_remaining'),
    'trailing_drawdown_remaining': state.get('trailing_drawdown_remaining'),
    'broker_account_read':         state.get('broker_account_read', False),
    'prop_alerts_sent':            prop_alerts.get('alerts_sent', []),
    'prop_alerts_suppressed':      prop_alerts.get('alerts_suppressed', []),
}
```

---

## API Endpoints

### `GET /api/prop-account/state`

Returns the latest prop account state (reads `nova_prop_account_state.json`, no broker call).

### `GET /api/execution-safety/status`

Includes `prop_account_summary` key with current balance, HWM, loss remaining, and alert activity.

---

## main.py Integration

The safety loop already calls `run_execution_safety_check()` which includes Phase 6:

```python
async def execution_safety_loop():
    while True:
        try:
            if not NOVA_EXECUTION_SAFETY_MONITOR_ENABLED:
                await asyncio.sleep(60)
                continue
            run_execution_safety_check()   # ← includes prop account update
        except Exception:
            pass
        await asyncio.sleep(60)
```

No separate loop needed for Phase 6.

---

## Test Coverage

**Phase 6 tests** (`tests/test_execution_bot_v2_phase6.py` — 27 tests):

| # | Test | Focus |
|---|---|---|
| 01 | `test_default_state_loads_safely` | State init |
| 02 | `test_missing_state_file_does_not_crash` | File safety |
| 03 | `test_state_saves_and_loads_round_trip` | Persistence |
| 04 | `test_daily_reset_on_new_trading_day` | Daily reset |
| 04b | `test_no_daily_reset_when_same_day` | Same-day guard |
| 05 | `test_hwm_updates_when_balance_increases` | HWM update |
| 06 | `test_hwm_never_decreases` | HWM invariant |
| 07 | `test_trailing_drawdown_threshold_trailing` | Trailing type |
| 07b | `test_trailing_drawdown_threshold_static` | Static type |
| 08 | `test_trailing_drawdown_warning_at_25pct` | WARNING threshold |
| 09 | `test_trailing_drawdown_breached` | BREACHED |
| 10 | `test_daily_loss_warning` | Daily loss warning |
| 11 | `test_daily_loss_breached` | Daily loss breached |
| 12 | `test_total_loss_warning` | Total loss warning |
| 13 | `test_total_loss_breached` | Total loss breached |
| 14 | `test_broker_read_failure_gives_unknown_state` | Failure safety |
| 15 | `test_safety_status_includes_prop_summary` | Integration |
| 16 | `test_no_broker_write_methods_called_in_prop_update` | Safety contract |
| 17 | `test_prop_warning_alert_sent_when_near_breach` | Alert send |
| 18 | `test_get_latest_prop_account_state_from_file` | File-first |
| 18b | `test_get_latest_prop_account_state_live_fallback` | Live fallback |
| 19 | `test_strategy_logic_unchanged_by_prop_update` | Strategy isolation |
| 20 | `test_prop_discord_disabled_suppresses_alert` | Phase 5.1 gate |
| 21 | `test_prop_suppressed_reason_discord_disabled` | Suppression reason |
| 22 | `test_prop_suppressed_reason_cooldown` | Cooldown reason |
| 23 | `test_prop_registry_written_when_alert_sent` | Registry persistence |
| 24 | `test_prop_persistent_cooldown_survives_reload` | Restart survival |

---

## Operational Notes

### During paper validation:

```
NOVA_EXECUTION_SAFETY_DISCORD_ENABLED=false   # prop alerts run silently
NOVA_EXECUTION_SAFETY_MONITOR_ENABLED=true
NOVA_EXECUTION_SAFETY_ALERT_COOLDOWN_SECONDS=900
```

### When ready to monitor prop risk on Discord:

```
NOVA_EXECUTION_SAFETY_DISCORD_ENABLED=true
```

No code changes required.

### Configuring prop limits (edit `nova_prop_account_state.json`):

```json
{
  "prop_firm_name":            "Apex",
  "account_size":              50000.0,
  "starting_balance":          50000.0,
  "trailing_drawdown_enabled": true,
  "trailing_drawdown_amount":  2500.0,
  "trailing_drawdown_type":    "trailing",
  "max_daily_loss":            500.0,
  "max_total_loss":            2500.0
}
```

Static fields are preserved across broker reads. Dynamic fields are overwritten.

### NOVA_PROP_GATES_ENABLED:

Phase 6 is **observation only**. Setting `NOVA_PROP_GATES_ENABLED=true` is blocked until dry-run execution validation is complete. Alerts fire but no execution gates are enforced.
