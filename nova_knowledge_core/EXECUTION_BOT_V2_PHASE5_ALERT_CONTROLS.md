# Execution Bot v2 — Phase 5.1 Alert Controls

## Purpose

Phase 5 added a periodic safety monitor that detects unprotected positions and sends CRITICAL Discord alerts. Phase 5.1 adds governance controls so the monitor can run continuously without spamming Discord during paper validation.

The monitor always runs. Discord delivery is a separate, opt-in layer.

---

## Environment Variables

| Variable | Default | Effect |
|---|---|---|
| `NOVA_EXECUTION_SAFETY_MONITOR_ENABLED` | `true` | Set `false` to pause the entire monitor loop (main.py). Endpoint still works. |
| `NOVA_EXECUTION_SAFETY_DISCORD_ENABLED` | `false` | Set `true` to allow Discord delivery. Default OFF during paper validation. |
| `NOVA_EXECUTION_SAFETY_ALERT_COOLDOWN_SECONDS` | `900` | Seconds between repeat alerts for the same instrument+type (15 minutes). |

---

## Monitor Behavior

Every 60 seconds the safety loop runs `run_execution_safety_check()`.

### Always happens (regardless of Discord setting):
- Fetches broker positions + orders + open journal trades
- Detects unprotected positions (no stop order)
- Writes `nova_execution_safety_status.json`
- Appends to `nova_execution_safety_log.json`
- Logs to stdout

### Only happens when `NOVA_EXECUTION_SAFETY_DISCORD_ENABLED=true` AND alert is not in cooldown:
- Calls `send_safety_discord_alert(alert)`
- Records alert in `nova_execution_safety_alert_registry.json`

### When Discord is disabled:
- Alert is recorded as `SUPPRESSED` with reason `DISCORD_DISABLED` in status dict
- No Discord REST call is made

### When alert is in cooldown:
- Alert is recorded as `SUPPRESSED` with reason `COOLDOWN` in status dict
- No Discord REST call is made

---

## Persistent Cooldown Registry

File: `nova_execution_safety_alert_registry.json`

```json
{
  "SPY__UNPROTECTED_POSITION": {
    "alert_key": "SPY__UNPROTECTED_POSITION",
    "instrument": "SPY",
    "alert_type": "UNPROTECTED_POSITION",
    "last_sent_at": "2026-06-29T15:00:00Z"
  }
}
```

- Loaded at module import time into `_cooldown_state` (in-memory dict)
- Written on every alert send via `_record_alert_sent()`
- Survives process restarts — the registry is the source of truth on startup
- Key format: `{INSTRUMENT}__{ALERT_TYPE}`

### Cooldown logic:

```
in_cooldown = (now - last_sent_at).seconds < cooldown_seconds
```

When Discord is disabled: alert is suppressed but NOT recorded in registry (so when Discord is re-enabled, alerts fire immediately instead of waiting out a stale cooldown).

---

## Status Response Fields (Phase 5.1 additions)

`run_execution_safety_check()` returns these new fields:

| Field | Type | Meaning |
|---|---|---|
| `discord_enabled` | bool | Value of `NOVA_EXECUTION_SAFETY_DISCORD_ENABLED` at check time |
| `cooldown_seconds` | int | Cooldown in effect for this check |
| `alerts_suppressed_by_cooldown` | list[str] | Entries like `'SPY:COOLDOWN'` or `'SPY:DISCORD_DISABLED'` |

---

## API Endpoints

### `GET /api/execution-safety/status`

Returns the latest cached safety status (reads `nova_execution_safety_status.json`). No broker calls.

Compatible with Phase 5. No breaking changes.

---

## main.py Integration

```python
async def execution_safety_loop():
    while True:
        try:
            if not NOVA_EXECUTION_SAFETY_MONITOR_ENABLED:
                await asyncio.sleep(60)
                continue
            run_execution_safety_check()
        except Exception:
            pass
        await asyncio.sleep(60)
```

When `NOVA_EXECUTION_SAFETY_MONITOR_ENABLED=false`: loop still runs (sleeps), endpoint still works, no broker calls are made.

---

## Safety Contract (unchanged from Phase 5)

This module **MUST NEVER**:
- Submit orders
- Cancel orders
- Modify positions
- Call any Alpaca write endpoint

Only `GET` endpoints on Alpaca are permitted. All write methods (`submit_order`, `cancel_order_by_id`, `close_all_positions`) are verified absent by Phase 5 and Phase 5.1 tests.

---

## Test Coverage

**Phase 5 tests** (`tests/test_execution_bot_v2_phase5.py` — 22 tests):
- Basic detection, cooldown, send, no-write verification
- Updated in Phase 5.1 for Discord-gate compatibility (explicit `_discord_enabled=True` where needed)

**Phase 5.1 tests** (`tests/test_execution_bot_v2_phase5_1.py` — 15 tests):
1. Discord disabled suppresses `send_safety_discord_alert`
2. Status file still written when Discord disabled
3. Log still appended when Discord disabled
4. Suppressed list shows `DISCORD_DISABLED` reason
5. Discord enabled sends alert (existing behavior preserved)
6. Cooldown env var respected (900s default)
7. Persistent registry written when alert sent
8. Persistent cooldown survives simulated restart (registry reload)
9. Monitor-enabled field in status (`discord_enabled`)
10. No broker write methods called (Phase 5.1 path)
11. Status field `discord_enabled=true`
12. Status field `discord_enabled=false`
13. Status field `cooldown_seconds`
14. No auto-flatten called
15. No cancel/replace/submit order calls

**Shared test infrastructure** (`tests/conftest.py`):
- `autouse=True` fixture patches broker calls to empty state by default
- Prevents live Alpaca positions from breaking deterministic tests
- Individual tests that need broker state override via their own `with patch(...)` blocks

---

## Operational Notes

### During paper validation:
```
NOVA_EXECUTION_SAFETY_MONITOR_ENABLED=true
NOVA_EXECUTION_SAFETY_DISCORD_ENABLED=false   # monitor runs silently
NOVA_EXECUTION_SAFETY_ALERT_COOLDOWN_SECONDS=900
```

### When ready for live monitoring:
```
NOVA_EXECUTION_SAFETY_DISCORD_ENABLED=true
```

No code changes required. Only env var change needed.

### If Discord floods:
- Increase `NOVA_EXECUTION_SAFETY_ALERT_COOLDOWN_SECONDS` (e.g. 1800 for 30min)
- Or set `NOVA_EXECUTION_SAFETY_DISCORD_ENABLED=false` to pause delivery without stopping detection
