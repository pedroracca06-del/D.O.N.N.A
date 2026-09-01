# Execution Bot v2 — Phase 7: Prop Readiness Validation

## What Phase 7 Validates

Phase 7 is not a new trading feature. It is the validation and readiness layer that must
be completed before any live prop account capital is exposed to the execution bot.

**Phase 7 validates:**
- All infrastructure layers (Phases 1–6) are functioning as a cohesive system
- Prop risk config is present and correctly calibrated for your specific firm
- Account state tracking is live and accurate (HWM, trailing drawdown, daily P&L)
- Safety monitor is running, detecting positions, and reconciling against journal
- Execution pipeline produces correct dry-run results with no duplicate IDs, stale signals,
  or broker/journal mismatches across 5+ live market sessions

**Files changed:**
- `services/prop_readiness.py` — NEW: readiness evaluation engine
- `main.py` — `GET /api/prop-readiness/status` endpoint added
- `tests/test_execution_bot_v2_phase7.py` — 17 tests
- `nova_knowledge_core/PROP_ACCOUNT_READINESS_CHECKLIST.md` — full go/no-go checklist
- `nova_knowledge_core/EXECUTION_BOT_V2_PHASE7.md` — this doc

**Test count:** 163/163 total (P1: 19, P2: 31, P3: 31, P4: 21, P5: 17, P6: 27, P7: 17)

---

## Readiness Report: `nova_prop_readiness_report.json`

Written on every call to `GET /api/prop-readiness/status` or `write_prop_readiness_report()`.

```json
{
  "checked_at":            "2026-07-06T14:00:00Z",
  "readiness_status":      "READY_FOR_DRY_RUN",
  "blockers":              [],
  "warnings":              [
    "NOVA_EXECUTION_SAFETY_DISCORD_ENABLED=false: Discord alerts suppressed."
  ],
  "recommended_next_action": "System is ready for dry-run validation. Run 5 live market sessions...",
  "prop_firm":             "Apex",
  "prop_config_present":   true,
  "account_state_summary": {
    "prop_state_status":           "PROP_STATE_OK",
    "current_balance":             50000.0,
    "high_water_mark":             50000.0,
    "daily_pnl":                   0.0,
    "trailing_drawdown_remaining": 2500.0,
    "daily_loss_remaining":        500.0,
    "broker_account_read":         true,
    "last_updated":                "2026-07-06T14:00:00Z"
  },
  "latest_safety_status": {
    "status":               "NO_OPEN_POSITIONS",
    "checked_at":           "2026-07-06T13:58:00Z",
    "open_positions_count": 0,
    "unprotected_count":    0,
    "discord_enabled":      false
  },
  "execution_trace_summary": {
    "trace_file_exists": true,
    "entry_count":       12,
    "latest_status":     "DRY_RUN_VALIDATED",
    "latest_at":         "2026-07-06T13:45:00Z"
  },
  "discord_configured":     false,
  "dry_run_enabled":        true,
  "auto_execute_enabled":   false,
  "prop_gates_enforcing":   false,
  "safety_monitor_enabled": true
}
```

---

## Readiness Status Values

| Status | Meaning |
|---|---|
| `READY_FOR_DRY_RUN` | No blockers. All required infrastructure is in place. Proceed to 5-session dry-run trial. |
| `NOT_READY` | One or more blockers must be resolved before dry-run validation can begin. |

**Blockers** (must fix; cause `NOT_READY`):
- `NOVA_AUTO_EXECUTE=true` with `NOVA_EXECUTION_DRY_RUN=false` — live execution without dry-run safety
- Prop risk config missing or `prop_firm_name=NONE`

**Warnings** (informational; do not block `READY_FOR_DRY_RUN`):
- `NOVA_EXECUTION_DRY_RUN=false` when `NOVA_AUTO_EXECUTE=false` — execution off, set dry-run before trial
- `NOVA_PROP_GATES_ENABLED=true` — gates enforcing before validation complete
- Safety monitor never run or status is stale (>30 min)
- Prop account state not updated or stale (>2 hr)
- Discord disabled — alerts suppressed
- `broker_account_read=false` — balance not yet populated from broker
- Execution trace empty — no signals through pipeline yet

---

## Dry-Run Trial Plan

### Minimum Trial Requirements

Before any live prop capital deployment, complete a 5-session dry-run trial.

**Session = one full market day from open to close (9:30 AM–4:00 PM ET)**

| Requirement | Value |
|---|---|
| Minimum sessions | 5 live market sessions |
| Required env | `NOVA_EXECUTION_DRY_RUN=true` |
| Prop gates | `NOVA_PROP_GATES_ENABLED=false` (observe-only) |
| Discord | Disabled is acceptable; enable to test alert delivery |
| Safety monitor | Must be running throughout |
| Prop account state | Must update each session |

### Per-Session Pass Criteria

Every session must complete with:

- [ ] No duplicate `exec_request_id` in `nova_execution_trace_v2.json`
- [ ] No stale signal executions (all signals received within staleness window)
- [ ] No broker/journal reconciliation mismatches
- [ ] No unprotected-position alerts
- [ ] No unexpected order actions (no cancel, replace, or submit calls)
- [ ] All executed signals have both `tp1` and `stop` populated
- [ ] All executed signals have a grade of A or B (or as configured)
- [ ] `dry_run: true` present on every trace entry
- [ ] Prop account state `last_updated` reflects same-day update

### Post-Trial Verification

After all 5 sessions pass:

1. **Verify HWM accuracy** — compare `high_water_mark` in `nova_prop_account_state.json`
   against the Alpaca account equity shown in broker portal
2. **Verify limit calibration** — confirm `trailing_drawdown_amount`, `max_daily_loss`,
   and `max_total_loss` match your firm's published rules for your account tier
3. **Verify gate decision log** — review `nova_execution_trace_v2.json` gate results
   across all 5 sessions; no `FAIL` entries should appear on valid signals
4. **Review the prop account state file** — confirm daily resets fired correctly each morning
5. **Run `GET /api/prop-readiness/status`** — must return `READY_FOR_DRY_RUN` with no blockers

---

## Go / No-Go Criteria

### Go — Approved for Live Prop Deployment

All of the following must be true:

- `GET /api/prop-readiness/status` returns `READY_FOR_DRY_RUN`
- 5 dry-run sessions completed with all per-session pass criteria met
- `high_water_mark` verified accurate against broker portal
- `trailing_drawdown_amount` confirmed correct for your account tier
- `max_daily_loss` and `max_total_loss` confirmed match firm's published rules
- Zero unprotected-position alerts across all 5 sessions
- Zero journal/broker mismatches
- Zero duplicate execution requests
- Zero stale signal executions
- User explicitly sets `NOVA_PROP_GATES_ENABLED=true`
- User explicitly changes `NOVA_EXECUTION_DRY_RUN=false` after reviewing the above

### No-Go — Stay in Dry-Run or Paper Mode

Any of the following means do not advance to live prop:

- Any session produced a duplicate `exec_request_id`
- Any session produced an unprotected position
- Any session produced a broker/journal mismatch
- `nova_prop_account_state.json` shows `broker_account_read=false`
- HWM values are zero or do not match broker portal
- Any gate decision log shows unexpected `FAIL` on a valid signal

---

## Why We Are Not Live Trading a Prop Account Yet

As of Phase 7, the execution bot is in **paper validation mode**. The reasons:

1. **Phases 1–6 have never run in real market conditions** — dry-run validation has not yet
   been performed. Phase 7 is the validation gate before that trial begins.

2. **Account state tracking is new** — `nova_prop_account_state.json` needs to be verified
   accurate against the broker portal across multiple sessions before we trust it.

3. **Prop risk config has not been reviewed against your firm's actual rules** — limits
   must be calibrated to match the specific account tier (e.g., Apex 50k trailing drawdown
   amount differs from a 100k account).

4. **Gate 3b (TP1 + SL required) was just added** — signals without defined targets now
   reject before reaching the broker. This needs to be validated across real NOVA reasoning
   cycles to confirm the constraint fires correctly.

5. **`NOVA_PROP_GATES_ENABLED=false` by design** — prop gates are observe-only until the
   dry-run trial confirms they produce correct decisions without false positives.

6. **No auto-flatten** — a prop account violation would require manual intervention. Until
   the trader is comfortable with the manual emergency process and has practiced it, live
   prop is premature.

---

## Phase 8 Preview: Prop Gate Enforcement Trial

Phase 8 scope (NOT yet implemented):

1. Enable `NOVA_PROP_GATES_ENABLED=true` in a controlled dry-run session
2. Verify prop gates block new entries when drawdown threshold is approaching
3. Confirm no false positives across 3+ gated sessions
4. Add prop enforcement event to `nova_execution_trace_v2.json` with gate reason
5. Update `nova_knowledge_core/EXECUTION_BOT_V2_PHASE8.md`

**Phase 8 gate:** Do not begin until:
- Phase 7 dry-run trial complete (5 sessions, all criteria met)
- User explicitly approves `NOVA_PROP_GATES_ENABLED=true`

---

## Safety Contract

Phase 7 and all readiness validation MUST NEVER:
- Submit orders
- Cancel orders
- Modify positions
- Call any Alpaca write endpoint

The only external calls in `services/prop_readiness.py`:
- `load_prop_config()` — reads `nova_prop_risk_config.json`
- `load_prop_account_state()` — reads `nova_prop_account_state.json`
- `get_latest_safety_status()` — reads `nova_execution_safety_status.json`
- Execution trace file read — reads `nova_execution_trace_v2.json`

All read-only. No broker writes. No order actions.
