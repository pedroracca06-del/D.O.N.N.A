# Execution Bot v2 — Phase 4: Protective Order Confirmation + Emergency Alerting

## What Was Built

Phase 4 adds post-submit/post-fill protective order confirmation scaffolding and structured emergency alerting for unprotected positions. Three new functions in `services/execution_reconcile.py`, 10 new trace_v2 fields, and a new API endpoint.

**Files changed:**
- `services/execution_reconcile.py` — three new Phase 4 functions
- `services/execution_request.py` — Phase 4 block wired, 10 new trace_v2 fields, shared broker state pattern
- `main.py` — `GET /api/execution-safety/status` endpoint
- `tests/test_execution_bot_v2_phase4.py` — 21 tests

**Test count:** 102/102 total (P1: 19, P2: 31, P3: 31, P4: 21)

---

## How Protective Confirmation Works

`confirm_protective_orders_after_submit(execution_request, broker_orders, broker_positions)` is called inside `_validate_and_record_impl()` after Phase 3 using the same broker state (no second API call). It:

1. Routes the signal's symbol to the ETF: MNQ/NQ → QQQ, MES/ES → SPY
2. Looks for an open position in `broker_positions` for that ETF
3. Checks `broker_orders` for protective orders (stop-loss, take-profit, bracket/OCO)
4. Returns a status and optional emergency alert

**Status table:**

| Status | Condition | `unprotected_position` |
|---|---|---|
| `INSUFFICIENT_DATA` | No position, no pending entry order | false |
| `ENTRY_NOT_FILLED` | Pending entry order found, position not yet open | false |
| `UNPROTECTED_POSITION` | Position found, no orders at all | **true** |
| `STOP_MISSING` | Position + target order only (no stop) | **true** |
| `TARGET_MISSING` | Position + stop order only (no target) | false |
| `PROTECTIVE_ORDERS_CONFIRMED` | Position + stop + target | false |

**Critical rule:** The stop order is the load-bearing protection. No stop = unprotected, regardless of target. A position with a target but no stop is `STOP_MISSING` and fires an emergency alert. A position with a stop but no target is `TARGET_MISSING` and does NOT fire an emergency alert.

**Bracket/OCO detection:** If any order for the position's ETF has `order_class == 'bracket'` or `'oco'`, both stop and target are treated as confirmed. This handles single bracket orders submitted at entry.

**Shared broker state:** Phase 3 fetches broker positions and orders once. Phase 4 reuses the same lists via `_shared_broker_positions` and `_shared_broker_orders` — no second Alpaca API call.

---

## What Emergency Alerting Does

`build_unprotected_position_alert(...)` returns a structured dict when a position has no stop order:

```python
{
    'alert_type':           'UNPROTECTED_POSITION',
    'severity':             'CRITICAL',
    'symbol':               'MNQ',        # futures symbol
    'instrument':           'QQQ',        # routed ETF
    'qty':                  10.0,
    'side':                 'long',
    'detected_at':          '2026-06-30T...',
    'execution_request_id': 'EXREQ_...',
    'decision_id':          None,
    'broker_position':      {...},         # full position dict
    'broker_orders_seen':   [...],         # all orders at detection time
    'message':              'CRITICAL: QQQ long position of 10.0 units has NO stop order...',
    'recommended_action':   'MANUAL_REVIEW_REQUIRED',
}
```

The alert object is:
- Written to `emergency_alert` in the trace_v2 entry
- Added to `validation_warnings` as `EMERGENCY UNPROTECTED_POSITION: ...`
- Included in the `GET /api/execution-safety/status` response
- **Never sent automatically** — no Discord push, no order submission

---

## What Is Still Manual-Only

- **Reviewing emergency alerts:** The trader must check `/api/execution-safety/status` or read trace_v2
- **Adding a missing stop:** Must be placed manually in the broker UI or via a future Phase 5 action
- **Flattening an unprotected position:** No auto-flatten logic exists or is planned for Phase 4
- **Discord notification:** Emergency alerts live in the trace and API response only; routing to Discord is Phase 5

---

## Why No Auto-Flatten or Auto-Repair Exists Yet

NOVA does not auto-flatten or auto-submit missing stops for three reasons:

1. **Signal ambiguity:** By the time Phase 4 runs, NOVA cannot distinguish "position opened but stop not yet submitted" from "stop submission failed." Automated action on ambiguous state would cause worse outcomes than doing nothing.

2. **Phase ordering:** Phase 4 runs as a *pre-trade* validation layer, not a post-fill monitor. It observes broker state at signal time, not continuously after order submission. A proper post-fill monitor (periodic reconciliation loop) is Phase 5 scope.

3. **Prop-firm rules:** Unsolicited cancel/replace activity can trigger account reviews at some prop firms. No automated order manipulation runs until the reconciliation loop is validated end-to-end in dry-run.

The design choice: **observe and alert** first, **act** only after the observation layer is proven reliable.

---

## New trace_v2 Fields (Phase 4)

All 10 fields are present on every `validate_and_record()` call:

| Field | Type | Description |
|---|---|---|
| `protective_confirmation_status` | str or None | PROTECTIVE_ORDERS_CONFIRMED / TARGET_MISSING / STOP_MISSING / UNPROTECTED_POSITION / INSUFFICIENT_DATA / ENTRY_NOT_FILLED |
| `entry_order_found` | bool or None | Pending entry order detected in broker |
| `entry_filled` | bool or None | Position found = fill confirmed (for market orders) |
| `position_found` | bool or None | ETF position exists in broker |
| `stop_order_found` | bool or None | Protective stop-loss order detected |
| `target_order_found` | bool or None | Take-profit limit order detected |
| `bracket_or_oco_detected` | bool or None | Bracket/OCO order class detected (implies both) |
| `emergency_alert` | dict or None | Full alert object if position is unprotected |
| `emergency_alert_type` | str or None | 'UNPROTECTED_POSITION' when alert fired |
| `emergency_alert_severity` | str or None | 'CRITICAL' when alert fired |

---

## GET /api/execution-safety/status

Read-only endpoint that checks all current broker positions for protection:

```json
{
  "status": "UNPROTECTED_POSITIONS_DETECTED",
  "open_positions_count": 1,
  "open_orders_count": 0,
  "open_journal_count": 0,
  "protected_positions": [],
  "unprotected_positions": [{"symbol": "QQQ", "side": "long", "qty": 10.0, ...}],
  "emergency_alerts": [{"alert_type": "UNPROTECTED_POSITION", "severity": "CRITICAL", ...}],
  "warnings": ["CRITICAL: QQQ position is UNPROTECTED"],
  "errors": []
}
```

**Overall status values:**
- `NO_OPEN_POSITIONS` — no broker positions found
- `ALL_POSITIONS_PROTECTED` — all positions have stop orders
- `UNPROTECTED_POSITIONS_DETECTED` — at least one position missing a stop

This endpoint never modifies broker state. Safe to poll.

---

## Enforcement Rules (Same as Phase 2+3)

Phase 4 is **observation-only** in all modes:

| Mode | Behavior |
|---|---|
| Live, `NOVA_PROP_GATES_ENABLED=false` | Phase 4 runs, logs, appends to warnings. Does NOT block. `final_status=RECEIVED` |
| Dry-run (`NOVA_EXECUTION_DRY_RUN=true`) | Phase 4 runs. Broker never called. `final_status=DRY_RUN_VALIDATED` |
| Live, `NOVA_PROP_GATES_ENABLED=true` | Phase 2+3 gates can block. Phase 4 still observation-only. |

Emergency alerts appear in the trace and warnings in all modes but do not change `final_status`.

---

## Phase 5 Scope (What Comes Next)

1. **Periodic reconciliation loop** — background task (60–120s) that calls `get_execution_safety_status()` and pushes CRITICAL alerts to Discord automatically
2. **Post-fill protective order verification** — explicit wait after submit, retry on ENTRY_NOT_FILLED, escalate after N retries
3. **Trailing drawdown HWM gate** — prop-firm trailing drawdown tracking (Apex/Topstep rules)
4. **Reconciled terminal status** — mark trace entries RECONCILED once position is closed and journal matches
5. **Discord emergency delivery** — route `UNPROTECTED_POSITION` alerts to a dedicated alert channel with position details

**Hard constraint for Phase 5 start:** Phase 4 emergency alerts must be observed on at least 5 real (or dry-run simulated) execution cycles before any automated action is wired.
