# EXECUTION BOT V2 — PHASE 1 IMPLEMENTATION NOTE

**Date:** 2026-06-30  
**Status:** COMPLETE — 19/19 tests passing  
**Constraint:** Read-only parallel layer. No broker changes. No execution behavior changes. No prop drawdown gates.

---

## What Was Built

Phase 1 establishes the execution request backbone: every execution attempt is now traceable, deduplicated, freshness-checked, and dry-run validatable before any prop-firm gate work begins.

### New Files

**`services/execution_request.py`**  
Core Phase 1 module. Public API:
- `validate_and_record(**kwargs) -> dict` — call once per execution attempt
- `build_execution_request_id(symbol, direction, setup_type, ...) -> str` — deterministic EXREQ ID
- `is_dry_run() -> bool` — reads `NOVA_EXECUTION_DRY_RUN` env var at call time
- `get_registry_stats() -> dict` — summary for /api endpoints
- `get_trace_v2_recent(limit) -> list` — last N trace_v2 entries

**`data/nova_execution_registry.json`** (auto-created)  
Persistent dedup registry. Survives process restarts. Format:
```json
{
  "version": "1",
  "records": [
    {
      "execution_request_id": "EXREQ_20260630_143000_AB12CD34",
      "decision_id": "...",
      "signal_id": "...",
      "symbol": "MNQ",
      "direction": "LONG",
      "setup_type": "PROS_LONG",
      "created_at": "2026-06-30T14:30:00Z",
      "status": "DRY_RUN_VALIDATED"
    }
  ]
}
```

**`data/nova_execution_trace_v2.json`** (auto-created)  
Append-only trace for every execution attempt. Max 5000 entries (oldest rotated).  
Every record includes `execution_request_id`, `final_status`, `duplicate_check`, `stale_check`, `broker_called: false`.

**`tests/test_execution_bot_v2_phase1.py`**  
19 tests — all passing.

### Modified Files

**`delivery/alert_engine.py`** — Added two optional fields to `AlertData`:
```python
decision_id: str = ''           # reasoning snapshot id; empty until wired
signal_generated_at: str = ''   # ISO UTC timestamp when signal was created
```

**`engines/reasoning.py`** — `_build_alert_from_decision()` now sets `signal_generated_at = utc_now_iso()` when building any AlertData. No behavior change to signal classification or grading.

**`services/execution_bridge.py`** — `route_to_execution()` now calls `validate_and_record()` at the very top, before any gate:
- Always runs (observability in live mode)
- In `NOVA_EXECUTION_DRY_RUN=true` mode: returns Phase 1 result immediately, broker never called
- In live mode: logs result and continues to existing gate chain unchanged
- Phase 1 exceptions are caught with try-except; never block the live path
- All return dicts now include `execution_request` field

---

## What Is NOT Yet Active

| Feature | Status |
|---|---|
| `decision_id` populated from reasoning snapshot | NOT wired — reasoning fires snapshots async after AlertData is built; decision_id is empty until a separate wiring pass |
| Duplicate rejection blocking live trades | NOT enforced in live mode — registry is built, dedup is logged, but live path runs regardless |
| Stale signal blocking live trades | NOT enforced in live mode — stale check fires and logs, but live path runs regardless |
| prop_risk_config | NOT built yet (Phase 2) |
| Prop daily loss gate | NOT built yet (Phase 2) |
| Trailing drawdown gate | NOT built yet (Phase 2+) |
| Protective order verification | NOT built yet (Phase 3) |
| Broker reconciliation | NOT built yet (Phase 4) |

---

## Execution Request ID Format

```
EXREQ_YYYYMMDD_HHMMSS_HASH8

Where HASH8 = SHA256(decision_id|signal_id|symbol|direction|setup_type|signal_generated_at)[:8].upper()
```

Same signal fields within the same second always produce the same ID — deterministic for dedup and idempotent retries.

---

## Phase 1 Status Codes

| Status | Meaning |
|---|---|
| `RECEIVED` | All checks passed; live mode (caller continues to broker) |
| `DRY_RUN_VALIDATED` | All checks passed; dry-run mode (caller must NOT call broker) |
| `REJECTED_BAD_PAYLOAD` | Missing required fields (symbol, direction, setup_type) |
| `REJECTED_DUPLICATE` | Matched existing registry record by execution_request_id, decision_id, or signal_id |
| `REJECTED_STALE` | Signal age > `NOVA_MAX_SIGNAL_AGE_SECONDS` (default 120s) |
| `FAILED` | Unexpected exception in Phase 1 module itself |

---

## How to Run Dry-Run Validation

```bash
# Enable dry-run mode
NOVA_EXECUTION_DRY_RUN=true

# Run the monitor as normal — alerts will generate execution_requests
# but no broker calls will be placed.
python monitor.py

# Check trace_v2
cat data/nova_execution_trace_v2.json | python -m json.tool | head -100

# Check registry
cat data/nova_execution_registry.json | python -m json.tool
```

In dry-run mode, `route_to_execution()` returns:
```python
{
    'status': 'DRY_RUN_VALIDATED',   # or rejection status
    'code': 'DRY_RUN_VALIDATED',
    'execution_request': { ... full Phase 1 record ... },
    'chain_id': '',
}
```

The existing execution trace (`nova_execution_trace.json`) is NOT written in dry-run mode — only `nova_execution_trace_v2.json` is.

---

## Missing Signal Timestamp (current state)

Currently, `decision_id` is not populated in AlertData. `signal_generated_at` IS populated (set to `utc_now_iso()` in `_build_alert_from_decision()`).

A missing `signal_generated_at` (e.g. from webhook path) produces:
- Warning: `MISSING_SIGNAL_TIMESTAMP — signal age cannot be validated`
- Status: `DRY_RUN_VALIDATED` (not rejected — Phase 1 warns, does not block)

---

## Environment Variables

| Variable | Default | Effect |
|---|---|---|
| `NOVA_EXECUTION_DRY_RUN` | `false` | `true` = Phase 1 is final; broker never called |
| `NOVA_MAX_SIGNAL_AGE_SECONDS` | `120` | Signals older than this are `REJECTED_STALE` |

---

## Phase 2 Scope (not yet started)

Phase 2 will add prop-firm risk gates:
1. `prop_risk_config` schema + persistence (`donna_settings.json` or `donna_prop_config.json`)
2. Max contracts per symbol gate
3. Max trades per day gate (reads from prop config, not hardcoded)
4. Daily loss gate (replaces hardcoded `_LOSS_LIMIT_USD = -1000.0`)
5. Open position conflict gate (reads from prop config allowed_symbols / allowed_sessions)

Phase 2 enforcement gates will be ACTIVE in dry-run mode only until validated.  
Live enforcement requires clean dry-run run first.

## Phase 3 Scope (after Phase 2)

1. Trailing drawdown tracking (HWM + trailing_drawdown_amount)
2. Protective order confirmation after broker fill
3. UNPROTECTED_POSITION detection and alert

## Phase 4 Scope (after Phase 3)

1. Periodic broker↔state-engine reconciliation
2. Journal↔Alpaca open position reconciliation
3. RECONCILED status in trace_v2
4. Daily EOD reconciliation report
