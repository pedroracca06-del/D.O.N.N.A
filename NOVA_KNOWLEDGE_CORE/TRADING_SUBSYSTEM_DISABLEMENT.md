# Trading Subsystem Disablement

Date: 2026-07-16
Status: **The trading/execution subsystem is disabled by server-side default.** This document describes the kill switch, what it guards, and how to reason about it. It does not describe or endorse re-enabling the legacy system — see the explicit statement at the end.

---

## Authoritative flag

```
NOVA_TRADING_SUBSYSTEM_ENABLED
```

- **Default: `false`** (missing, empty, or any non-`'true'` value all resolve to disabled).
- Defined once in `core/config.py`, read directly inside every broker-write function in `services/execution.py`, and read dynamically (via `os.getenv`, matching the existing `_auto_execute_enabled()` pattern) inside `services/execution_bridge.py`'s `route_to_execution()`.
- **Independent of `NOVA_AUTO_EXECUTE`.** `NOVA_AUTO_EXECUTE=true` alone cannot place, modify, cancel, or close a trade while `NOVA_TRADING_SUBSYSTEM_ENABLED` is false — proven by `tests/test_trading_subsystem_disablement.py::test_auto_execute_true_alone_cannot_bypass_retirement_flag`.
- This is a server-side enforcement, not a UI preference. It cannot be worked around by calling a function directly, bypassing the frontend, or hitting a route with a raw HTTP client.

To re-enable (only with Pedro's explicit approval and a separate deployment change, per the retirement brief): set `NOVA_TRADING_SUBSYSTEM_ENABLED=true` in the environment (`.env` locally, Render env vars in the cloud) and restart.

---

## Guarded write paths (the chokepoint)

Both production entry points converge on `services/execution.py`, which is the single place every broker-writing call is guarded:

```
Path A (Render, always running):
  main.py POST /webhook -> process_signal() -> check_execution_governance()
    -> execute_signal()  [GUARDED]

Path B (local, only when monitor.py is running):
  monitor.py main() -> engines.reasoning.run_reasoning_cycle()
    -> services.execution_bridge.route_to_execution()  [GUARDED, Gate 0]
    -> execute_signal()  [GUARDED]
```

Guarded functions in `services/execution.py` (each returns `{'status': 'TRADING_SUBSYSTEM_DISABLED', ...}` immediately, before touching `_client()` / Alpaca, when the flag is false):

| Function | What it does when enabled |
|---|---|
| `execute_signal()` | Opens a new position (order submission, stop/target bracket creation) |
| `close_position(symbol)` | Closes one position (manual EXECUTION tab button) |
| `close_all_positions()` | Closes every open position (manual EXECUTION tab button) |
| `close_all_positions_eod()` | Force-flattens at 3:45pm ET (scheduled safety sweep) and the manual `/close-all` trigger |
| `cancel_all_orders()` | Cancels open (non-protective) orders |
| `close_qqq_positions()` | Emergency QQQ-only close (not currently wired to any route, guarded anyway for defense-in-depth) |

Guarded in `services/execution_bridge.py`:

- `route_to_execution()` — **Gate 0**, checked before Phase 1 execution-request validation and before the existing `NOVA_AUTO_EXECUTE` Gate 1. When disabled, no execution request is even recorded (`services.execution_request.validate_and_record` is never called).

Guarded in `main.py`:

- `GET /close-all` — the underlying `close_all_positions_eod()` returns a bare `int` (positions closed), so this route explicitly checks the flag first and returns a structured `{'status': 'TRADING_SUBSYSTEM_DISABLED', 'positions_closed': 0}` rather than a possibly-misleading `{'status': 'ok', 'positions_closed': 0}`.
- Every other execution route (`/execution/close`, `/execution/close-all`, `/execution/cancel-orders`, the `/webhook` execution step) needed **no route-level change** — they call the already-guarded `services/execution.py` functions directly and inherit the block automatically. This was a deliberate choice: guarding at the lowest reliable broker-write boundary means the routes can't drift out of sync with the guard.

**Not guarded (deliberately — these are reads, not writes):** `get_account()`, `get_positions()`, `sync_positions_from_alpaca()`, `reconcile_positions_from_alpaca()`, `check_position_outcomes()`, `has_open_journal_match()`. These still run so the EXECUTION tab and journal reconciliation can show accurate broker state during the retirement — no code path resulting from a read can place or modify an order.

---

## Startup-script change

`scripts/start_trading_session.ps1` (triggered by Task Scheduler at 09:15 ET Mon–Fri) previously did `$env:NOVA_AUTO_EXECUTE = 'true'` on every launch. It now:

- Never sets `NOVA_AUTO_EXECUTE`.
- Explicitly sets `$env:NOVA_TRADING_SUBSYSTEM_ENABLED = 'false'`.
- No longer launches `monitor.py` (step 3 removed — see below).
- Still launches TradingView in CDP mode (harmless with no consumer reading it) and the `uvicorn` feed server (Journal / Market / Assistant / finnhub / headlines — all retained).

**Manual Task Scheduler action:** none required for safety — the script is now inert with respect to trading regardless of when or how it fires. Pedro may still want to disable or retime the scheduled task if TradingView + the feed server are no longer needed every trading morning, but that's a convenience decision, not a safety one.

---

## monitor.py behavior

`monitor.py`'s only purpose is the retired reasoning → alert → execution pipeline. `main()` now checks `NOVA_TRADING_SUBSYSTEM_ENABLED` as its very first action:

- **If false (default):** logs `TRADING_SUBSYSTEM_DISABLED`, logs that it's exiting cleanly, and returns immediately — before importing `engines.reasoning`, `delivery.alert_engine`, or `services.execution_bridge`, before connecting to TradingView/CDP, and before initializing any broker client.
- **If true:** runs exactly as before (unchanged behavior) — but every broker write it could trigger downstream is still independently guarded in `services/execution.py` and `services/execution_bridge.py`.

No CDP/TradingView automation, chart writes, or live-script touches were made or are made by this change — `monitor.py` simply never gets far enough to open a CDP connection when disabled.

---

## Webhook behavior

`POST /webhook` (main.py) is unchanged at the route level. It still accepts and logs every incoming TradingView signal (`process_signal()`, `SIGNAL_RECEIVED` trace event) — nothing about inbound signal visibility was removed. The execution step (`execute_signal()`) now always returns `{'status': 'TRADING_SUBSYSTEM_DISABLED', ...}` while the flag is false, so:

- No order is submitted.
- The auto-journal block (`if execution.get('status') == 'executed'`) never fires, since `'TRADING_SUBSYSTEM_DISABLED' != 'executed'` — no fabricated "executed" journal entry is created.
- The webhook's HTTP response still returns `200` with the full signal-processing result plus the disabled execution status, so TradingView-side alerting/logging is unaffected.

---

## Broker initialization behavior

`_client()` in `services/execution.py` (the only place a `TradingClient` is constructed) is untouched — it's still called by read-only functions (`get_account`, `get_positions`, etc.) so those keep working. Every write-capable function now returns before reaching `_client()` at all when disabled, confirmed by `mock_client.assert_not_called()` in every relevant test.

---

## Tests

`tests/test_trading_subsystem_disablement.py` — 15 tests, all passing:

1. `execute_signal` blocked by default, and proven to proceed past the guard when the flag is explicitly enabled (proves it's a real switch).
2. `route_to_execution` blocked by default; no execution request recorded.
3. Webhook's execution call (`execute_signal`) blocked by default.
4. `monitor.py main()` exits cleanly, logging `TRADING_SUBSYSTEM_DISABLED`, in a real subprocess.
5. `scripts/start_trading_session.ps1` no longer force-sets `NOVA_AUTO_EXECUTE=true`, explicitly sets the retirement flag off, and no longer launches `monitor.py`.
6–8. `close_position`, `close_all_positions`, `cancel_all_orders`, `close_qqq_positions`, `close_all_positions_eod` all blocked by default (cancel/replace, close/flatten, and stop/target creation, the last via the same `execute_signal` gate as #1).
9. Missing/absent env var defaults safely to disabled, verified in a clean subprocess.
10. `NOVA_AUTO_EXECUTE=true` alone cannot bypass the retirement flag, for both the direct `execute_signal` path and the bridge's Gate 0.
11. `core.state`, `services.finnhub`, `services.news`, `services.headlines`, `services.assistant`, `engines.analytics`, `engines.thesis_analysis` all still import cleanly.
12. `main.py` imports cleanly (full app startup) with the subsystem disabled.

`tests/conftest.py` gained one new autouse fixture, `_trading_subsystem_enabled_for_existing_tests`, which defaults the flag to `True` for the in-process pytest environment only. This exists because dozens of pre-existing tests (`test_cancel_orders_guard.py`, `test_strategy_governance_gate.py`, `test_manual_close_sync.py`, `test_grade_trades_cooldown_governance.py`, `test_execution_bot_v2_phase1.py`, etc.) call the now-guarded functions directly and assert on their real business-logic results (bracket protection, governance gates, cooldowns, Phase 1 request validation) — none of that logic was touched, and none of those tests were weakened. The new retirement tests explicitly override the flag back to `False` within their own test body, or run in a subprocess with a deliberately clean environment the fixture never reaches, so the production-default safety contract is still independently proven.

Full suite result: **460 passed, 2 failed, 0 touched by this change.** The 2 failures (`test_journal_repair.py::test_stats_are_correct_after_merge_not_double_counted`, `test_open_trade_pnl_exclusion.py::test_mixed_open_and_closed_journal_only_counts_closed`) are pre-existing and unrelated — both assert a hardcoded `daily_pnl.this_week` value against fixture trade dates in late June 2026, which is no longer "this week" relative to today's date (2026-07-16). `core/state.py`, where `compute_journal_stats()` lives, was not modified by this retirement work.

---

## Rollback process

Rollback here means reverting the *disablement commits* on `retirement/disable-legacy-trading`, not restoring the archived legacy implementation to production use.

```
git log retirement/disable-legacy-trading   # find the disablement commits
git revert <commit>                          # revert just the disablement change, keeping everything else
```

**Rolling back this disablement does not mean the legacy trading system is approved for use.** The legacy implementation remains archived at `archive/legacy-trading-subsystem` / tag `nova-legacy-trading-subsystem-final` and is not approved for production trading — paper or live — until a future rebuild is independently designed, documented, tested, and explicitly approved stage-by-stage, per the retirement brief.
