# Trading Subsystem Archive Manifest

Date: 2026-07-16
Status: **This implementation is archived. It is NOT approved for production use.**
Rollback to this point does not mean the legacy system is approved for use — see `TRADING_SUBSYSTEM_DISABLEMENT.md` for the current server-side kill switch that stays in force regardless of which branch is checked out.

---

## Archive coordinates

| | |
|---|---|
| Source branch | `indicator/canonical-signal-phase1` |
| Source commit | `c8a62a94441b609695fc28b78cec570d8329806a` |
| Archive branch | `archive/legacy-trading-subsystem` → `c8a62a9` |
| Annotated tag | `nova-legacy-trading-subsystem-final` → `c8a62a9` |
| Retirement working branch | `retirement/disable-legacy-trading` (branched from `c8a62a9`, carries the disablement work) |
| Deployment state at archive time | Render deploys `main` @ `800d757` (2026-07-10). The archived commit `c8a62a9` was ahead of `main` on the indicator branch and had not been deployed. |

The archive branch and tag are not merged into any active branch and will not be. All historical commits reachable from `c8a62a9` remain reachable through either ref indefinitely.

---

## Intentionally excluded uncommitted files

At the moment of archiving, the working tree on `indicator/canonical-signal-phase1` had uncommitted state that is **not** part of this archive point and was **not** carried into the retirement branch's commits:

- `main.py` — in-progress Phase 8 dry-run-trial wiring (stashed as `phase8-dry-run-trial-wip`, restored to the working tree after the retirement commits landed; still uncommitted, still Pedro's active work, untouched by this retirement)
- `mcp/tradingview` submodule pointer bump (1 commit ahead of the committed pointer) — submodule housekeeping, unrelated
- `services/prop_dry_run_trial.py`, `tests/test_execution_bot_v2_phase8.py` — untracked Phase 8 files
- 28 untracked `data/*.json` / `data/_check_*` / `data/_dash_*` runtime-state and scratch files
- `nova_knowledge_core/INDICATOR_DASHBOARD_READABILITY_SCOPE.md`, `MONDAY_VALIDATION_PLAN.md`, `PROS_EVAN_INVESTING/draw_validation.md` — untracked in-progress docs

None of these are execution-critical to the archived implementation — they are separate in-progress work that happened to be sitting in the working tree. They remain on disk on the working branch, untouched, for Pedro to commit, discard, or continue separately.

---

## Complete subsystem inventory (as of `c8a62a9`)

### Core reasoning / signal pipeline
`engines/reasoning.py`, `engines/signals.py`, `engines/risk_engine.py`, `engines/native_shadow.py`, `engines/outcome_linker.py`, `engines/post_trade_review.py`, `delivery/signal_log.py`, `monitor.py`

### Execution Bot v2
`services/execution.py`, `services/execution_bridge.py`, `services/execution_trace.py`, `services/execution_request.py`, `services/execution_reconcile.py`, `services/execution_safety.py`, `services/prop_account_state.py`, `services/prop_risk.py`, `services/prop_readiness.py`, `services/audit.py`

### TradingView indicator / bridge
`indicators/nova_execution_v1.pine`, `mcp/tradingview/` (submodule)

### Dashboard trading surfaces (embedded in shared files, not standalone)
`H.A.R.V.E.Y`, `EXECUTION`, `NOVA REPLAY` tabs in `ui/html.py` (lines ~1487–1494 nav bar); `build_harvey_payload()` in `engines/engines.py`

### Alert delivery (shared mechanism, strategy-specific alert types)
`delivery/alert_engine.py` (`HEADS_UP` / `EXECUTION_READY` / `INVALIDATION` / `NO_TRADE`), `delivery/macro_discord.py` (largely retained — not strategy-signal-based)

### Tests
`tests/test_execution_bot_v2_phase1.py` through `phase8`, `tests/test_strategy_governance_gate.py`, `tests/test_cancel_orders_guard.py`, `tests/test_grade_trades_cooldown_governance.py`, `tests/test_eod_exit_price_sign.py`, `tests/test_manual_close_sync.py`, `tests/test_native_shadow.py`, `tests/test_replay_dashboard.py`, `tests/test_mcp_health.py`, `tests/test_mcp_snapshots.py`, `tests/test_phase_b_parser.py` through `phase_i`, `tests/test_phase_6_3_canonical_bridge.py`, `tests/test_execution_import_hardening.py`

### Runtime data (archived, not deleted)
`data/nova_execution_registry.json`, `nova_execution_safety_*.json`, `nova_execution_trace_v2.json`, `nova_prop_*.json`, `donna_execution_trace.json`, `donna_signal_log.json`

Full classification detail (RETAIN / ARCHIVE / DISABLE / REMOVE_FROM_UI / SHARED / UNKNOWN per file) is in `nova_knowledge_core/TRADING_SUBSYSTEM_RETIREMENT_AUDIT.md` — that document is the audit; this manifest is the point-in-time archive record.

---

## Known failures / known incidents (from existing project memory and docs)

- `project_indicator_signal_rejection_audit` — signal/rejection audit found RP-vs-RAP naming confusion and an intentional-but-confusing ORB/ES gate; 6-phase remediation plan was mid-flight when retirement was ordered.
- `project_execution_bot_v2_audit` (2026-06-30) — prop-firm readiness audit found 10 critical gaps (no exec_request_id, no dedup persistence, no stale check, no trailing drawdown, no prop config) that were being incrementally patched through Phase 8 at the time of retirement.
- `feedback_uuid_normalization` — Alpaca SDK `model_dump()` returns `uuid.UUID`; required `_json_safe()` fix in normalize_position_record/normalize_order_record (commit `7f38402`).
- `feedback_test_broker_isolation` — Phase 1/2 tests needed a `conftest.py` autouse fixture patching the broker to empty state; live positions previously broke them.
- `project_execution_trace_v2_orphaned` — `data/nova_execution_trace_v2.json` exists but is never wired to the file the app actually reads/writes (`donna_execution_trace.json`); a known dangling artifact, not an active bug.
- `project_draw_validation` (Jun 2026) — PROS framework discovery that draw independence (not just field completion) is required for a valid setup; documented but never enforced before retirement.
- The root cause named by Pedro for ordering this retirement: after months of incremental patching, he could no longer confidently determine why a given signal fired, which strategy family generated it, whether an execution failure originated in the bot or the strategy, or whether inherited ICT/IB/PROS concepts belonged in the system at all.

---

## Restoration instructions

If a future need arises to inspect or resurrect any part of this implementation:

```
git fetch                              # if working from a clone
git checkout archive/legacy-trading-subsystem
# or, to pin to the exact archived state without creating a local branch:
git checkout nova-legacy-trading-subsystem-final
```

To compare the archived state against the current (post-retirement) state of any file:

```
git diff nova-legacy-trading-subsystem-final -- <path>
```

To cherry-pick a specific historical fix out of the archive into a future rebuild (only after explicit review — do not bulk-restore):

```
git log nova-legacy-trading-subsystem-final -- <path>     # find the commit
git show <commit>                                          # inspect it
git cherry-pick <commit>                                    # only onto a branch Pedro has approved for this
```

**Do not merge `archive/legacy-trading-subsystem` into any active branch.** It exists only as a preserved reference point. Any future rebuild (`rebuild/trading-core-v1` per the retirement brief) starts from a blank specification and must not import or copy old strategy logic by default.

---

## Explicit status

This archive captures a system that Pedro determined was unreliable enough to warrant a full controlled reset. **Archiving it here is a preservation action, not an endorsement.** Nothing in this archive is approved for production trading, paper or live, until a future rebuild is independently designed, documented, tested, and explicitly approved stage-by-stage per the retirement brief's 8-stage rebuild plan.
