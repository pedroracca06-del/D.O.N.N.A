# Trading Subsystem Retirement — Phase 0 Safety Audit

Date: 2026-07-16
Branch at time of audit: `indicator/canonical-signal-phase1` (HEAD `c8a62a9`)
Status: **AUDIT ONLY — no code changed.** Awaiting Pedro's approval before Phase 1.

---

## 1. Git state

**Current branch:** `indicator/canonical-signal-phase1`
**Base:** `main` (`origin/main` @ `800d757`, 2026-07-10)
**Local branches:** only two exist — `indicator/canonical-signal-phase1` and `main`. No separate historical "execution-only" or "indicator-only" branches to track; all trading-subsystem work lives on commits within these two branches.

**Pre-existing modified/untracked files at audit start:**

Modified (not staged):
- `main.py`
- `mcp/tradingview` (submodule pointer bump, 1 commit ahead — Node MCP server, not app code)

Untracked:
- `data/_check_ec_js.js`, `data/_check_js.js`, `data/_check_live_js.js` — scratch JS extracted from dashboard for review (not wired into the app)
- `data/_dash_live.html`, `data/_dash_post_fix.html` — scratch dashboard HTML snapshots
- 25 runtime state JSON files under `data/` (all gitignored except `donna_settings.json`; expected — auto-generated)
- `nova_knowledge_core/INDICATOR_DASHBOARD_READABILITY_SCOPE.md`, `MONDAY_VALIDATION_PLAN.md`, `PROS_EVAN_INVESTING/draw_validation.md` — in-progress docs
- `services/prop_dry_run_trial.py` — Phase 8 prop dry-run module (referenced by `main.py`, not yet committed)
- `tests/test_execution_bot_v2_phase8.py` — matching test file

None of this untracked/modified state will be touched by the audit itself. It reflects work in progress on the current branch and should be preserved until Pedro decides what to do with it.

**Commit volume:** 450 commits total on this branch; ~249 match trading-subsystem keywords (ORB/PROS/ICT/indicator/canonical/execution/harvey/market reality/bridge/alert) — i.e., roughly 55% of all history is trading-subsystem work. This confirms the scale of what's being retired; a full commit-by-commit list is impractical to hand-classify and isn't necessary — the tag/branch archive in Phase 1 preserves all of them reachable, which is what matters.

---

## 2. Trading subsystem file inventory

### Core reasoning / signal pipeline (ARCHIVE + DISABLE)
| File | Role |
|---|---|
| `engines/reasoning.py` | Chart reading, PROS/ORB/IB evaluators, Claude setup grading |
| `engines/signals.py` | TradingView webhook signal parser (`process_signal`) |
| `engines/risk_engine.py` | Position sizing / drawdown for trade signals |
| `engines/native_shadow.py` | Python-native IB/ORB/PROS shadow engine |
| `engines/outcome_linker.py`, `engines/post_trade_review.py` | MCP replay outcome linking / narrative review |
| `delivery/signal_log.py` | Structured log of every NOVA evaluation cycle |
| `monitor.py` | Local session monitor — MCP chart polling, reasoning cycle, Discord dispatch |

### Execution Bot v2 (ARCHIVE + DISABLE)
| File | Role |
|---|---|
| `services/execution.py` | Alpaca broker client — `submit_order`, `close_position`, `close_all_positions`, `cancel_all_orders`, `execute_signal` (**the single broker-writing chokepoint** — both the webhook path and the local monitor path funnel through this) |
| `services/execution_bridge.py` | Local governance/gate chain (`NOVA_AUTO_EXECUTE` master switch, gates 1–11), calls `execute_signal()` |
| `services/execution_trace.py` | Audit ring-buffer of execution events |
| `services/execution_request.py`, `services/execution_reconcile.py`, `services/execution_safety.py` | Request backbone, reconciliation, periodic safety monitor |
| `services/prop_account_state.py`, `services/prop_risk.py`, `services/prop_readiness.py`, `services/prop_dry_run_trial.py` | Prop-firm account state, risk gates, readiness scoring, dry-run trial |
| `core/state_engine.py` | Daily trade count, locks (`eod_lock`, `trade_permission`), risk regime — **SHARED, see §4** |
| `services/audit.py` | Execution audit reconciliation (ghost-trade gap repair) |

### TradingView indicator / bridge (ARCHIVE)
| File | Role |
|---|---|
| `indicators/nova_execution_v1.pine` | The Pine Script indicator itself (canonical signal state, ICT context, RP/rejection logic) |
| `mcp/tradingview/` (submodule) | Node MCP server — CDP chart reads, screenshot capture |

### Dashboard trading surfaces (REMOVE_FROM_UI, file is SHARED — see §4)
| File | Role |
|---|---|
| `ui/html.py` | Single ~4200-line file containing **every** dashboard tab — Dashboard, Alerts, Journal, News, Assistant, `H.A.R.V.E.Y`, `EXECUTION`, `NOVA REPLAY` — all in one HTML/JS blob. Nav tabs found at lines 1487–1494. |
| `engines/engines.py` | `build_harvey_payload()` (Harvey tab, retiring) lives alongside `build_dashboard_payload`, `get_live_*` market functions (retained) — **SHARED, see §4** |

### Alert delivery (SHARED — see §4)
| File | Role |
|---|---|
| `delivery/alert_engine.py` | `HEADS_UP` / `EXECUTION_READY` / `INVALIDATION` / `NO_TRADE` alert types + Discord embed delivery + anti-spam governance. Strategy-signal alert types retire; the delivery mechanism itself may be reusable for general platform notifications — needs a decision, not a default. |
| `delivery/macro_discord.py` | Macro calendar / VIX / breaking-news Discord alerts — **not** strategy-signal-based, looks closer to RETAIN (feeds Market/News), confirm with Pedro. |

### Data files (ARCHIVE, do not delete)
`data/nova_execution_registry.json`, `nova_execution_safety_*.json`, `nova_execution_trace_v2.json`, `nova_prop_*.json`, `donna_signal_log.json` (if present), `donna_execution_trace.json` (per CLAUDE.md — note: `data/nova_execution_trace_v2.json` is currently orphaned/unwired per existing memory, see `project_execution_trace_v2_orphaned`).

---

## 3. RETAIN — working features, protect completely

| File | Feature |
|---|---|
| `core/state.py` | Generic JSON read/write, journal load/save/stats — used by everything, no execution-specific logic |
| `services/finnhub.py`, `services/news.py`, `services/headlines.py` | Market/News feed |
| `services/assistant.py` | NOVA Assistant — chat, tasks/reminders/focus (`apply_assistant_action` has **no** trade-placing action — confirmed safe) |
| Journal endpoints in `main.py` (`/journal/*`) | Trade journal CRUD, screenshots, AI analysis |
| `engines/analytics.py`, `engines/thesis_analysis.py` | Journal analytics, thesis/execution classification |
| `health/health.py` | System health checks (general) — **SHARED**, also contains an `NOVA_AUTO_EXECUTE` gate check, see §4 |
| `core/config.py` | Constants, env vars, Anthropic client — generic |

---

## 4. SHARED files — require surgical editing, not wholesale removal

This is the section that most needs Pedro's judgment before Phase 1 proceeds — these are load-bearing for RETAIN features and cannot simply be archived with the rest of the subsystem.

1. **`engines/market_reality.py` and its whole intelligence-engine family** — `market_reality_v2.py`, `cross_market.py`, `market_structure.py`, `participation.py`, `liquidity.py`, `synthesis.py`, `session_memory.py`, `momentum.py`, `directional_pressure.py`, `market_memory.py`, `morning_brief.py`.
   **Confirmed by direct import inspection:** `services/assistant.py` imports `format_reality_for_assistant`, `format_for_assistant` from *every one* of these modules to build Assistant chat context. **If these are archived as part of "Harvey / Market Reality" retirement, the NOVA Assistant breaks.**
   The retirement brief names "Harvey / Market Reality **trading tab**" for retirement — that is the *dashboard tab* built by `build_harvey_payload()` in `engines/engines.py`, which is a different thing from this *intelligence-engine module family* that fee both the reasoning prompt (retiring) and the Assistant (retained). Recommend classifying the tab as ARCHIVE and this module family as **RETAIN**, but flagging explicitly since the naming overlap ("Market Reality") is exactly the kind of ambiguity Pedro's brief warns about. **Do not resolve this unilaterally — needs an explicit yes/no per module before Phase 4.**

2. **`engines/engines.py`** — `build_harvey_payload()` (retiring) sits in the same file as `build_dashboard_payload`, `build_scenario_engine`, `get_live_major_indexes`, `get_live_market_data`, `get_live_movers`, `get_live_calendar`, `get_live_earnings`, `get_live_news`, `send_morning_brief` (retained, Market/News feed). The webhook handler in `main.py` also calls `build_harvey_payload()` to populate `harvey_verdict` in the auto-logged journal entry — so even the disable step touches this file. Needs function-level removal, not file deletion.

3. **`ui/html.py`** — one file, all tabs. Retiring `H.A.R.V.E.Y`, `EXECUTION`, `NOVA REPLAY` tabs means deleting specific HTML blocks + JS handlers out of this file while leaving Dashboard/Alerts/Journal/News/Assistant intact. High risk of collateral breakage given the file's size (~4200 lines) and the `Python Triple-String JS Quoting` failure mode already on record in memory (`\'` in this file has caused dashboard-freezing bugs before) — edits here need care and a manual smoke-test in browser, not just a diff review.

4. **`core/state_engine.py`** — `trade_permission`, `eod_lock`, daily trade count, risk regime. Used by execution gates (retiring) but the "risk regime" concept may also feed dashboard/Market displays — needs a read to confirm scope before deciding RETAIN vs DISABLE vs SHARED-trim.

5. **`health/health.py`** — general system health checks (API keys, file state) plus an explicit `NOVA_AUTO_EXECUTE` block (lines ~539–547) that currently reports FAIL if execution isn't armed. Under the new default (`TRADING_SUBSYSTEM_ENABLED=false`), this check's semantics flip — a "FAIL" today should become an expected/healthy state. Needs updating, not removal.

6. **`delivery/alert_engine.py`** — delivery mechanism (Discord routing, cooldowns, embed builder) is generic; the four alert *type* constants (`HEADS_UP`, `EXECUTION_READY`, `INVALIDATION`, `NO_TRADE`) are strategy-signal-specific. If any general/system notifications should keep using Discord delivery post-retirement, this file's plumbing is reusable — but that's a product decision, not something to assume.

7. **`main.py` webhook handler (`/webhook`, lines 2506–2628)** — currently the single internet-facing execution entry point. Disabling it fully removes TradingView's ability to reach NOVA at all, including for any future non-execution use (e.g., logging signals for observation only). Confirm with Pedro whether `/webhook` should be disabled outright or degraded to "receive and log, never execute."

8. **`tests/conftest.py`** — shared pytest fixtures; per existing memory (`feedback_test_broker_isolation`), it patches the broker to empty state for other tests. Needs review once execution tests are archived so the fixture doesn't dangle.

---

## 5. Active trading write paths (must all reach `TRADING_SUBSYSTEM_ENABLED=false`)

Both paths converge on `services/execution.py: execute_signal()` → Alpaca `submit_order` / `close_position` / `close_all_positions` / `cancel_all_orders`. That makes `execute_signal()` (and the four broker calls it wraps) the single correct enforcement point for a server-side kill switch — confirmed by a comment in `services/execution.py` itself: *"the one function every order-placing path (webhook, execution_bridge.py, anything future) calls before routing to a broker."*

**Path A — cloud (Render), always running:**
`main.py /webhook` → `process_signal()` → `check_execution_governance()` → `execute_signal()` → Alpaca.
Gated today only by `NOVA_AUTO_EXECUTE` env var (checked inside governance/execute_signal) — currently defaults to `false` unless explicitly set.

**Path B — local, only when `monitor.py` is running:**
`monitor.py main()` → `engines/reasoning.run_reasoning_cycle()` → `delivery/alert_engine.deliver_alert()` (Discord) + `services/execution_bridge.route_to_execution()` → `execute_signal()` → Alpaca.
`scripts/start_trading_session.ps1` line 35 **explicitly sets `$env:NOVA_AUTO_EXECUTE = 'true'`** every time the session launcher runs — and that launcher is wired to **Task Scheduler at 09:15 ET, Mon–Fri** (per existing memory `project_monday_trading_setup` and the script header comment). This is the most important live finding: **the auto-execute switch is armed automatically every trading morning**, not just available. Any disablement plan must either edit this script or introduce a switch that overrides it.

**Other broker-touching background loops (main.py startup, lines 494–532):**
- `position_outcomes_loop()` — read + reconcile Alpaca positions, update journal (read-mostly, but calls `sync_positions_from_alpaca`/`reconcile_positions_from_alpaca` which can write state)
- `eod_close_loop()` — **force-closes all open positions at 15:45 ET** and disables trade permission at 15:30 ET — this is a safety net, not a signal-driven path, and retiring it without a replacement could leave a stray position unmanaged if something else ever opens one
- `execution_safety_loop()` — explicitly documented as **read-only, never modifies broker state** — lower risk, mostly monitoring/alerting
- `services/audit.py: reconcile_execution_audit()` — runs once at startup, repairs "ghost trade gaps" — read/repair, not signal-driven

None of these currently run unless `_EXECUTION_AVAILABLE` (import succeeded) and, for the signal-driven paths, `NOVA_AUTO_EXECUTE=true`.

---

## 6. UI pages tied to the failed subsystem

From `ui/html.py` nav bar (lines 1487–1494), the tab bar is: `Dashboard | Alerts | Journal | News | Assistant | H.A.R.V.E.Y | EXECUTION | NOVA REPLAY`.

- **`H.A.R.V.E.Y`** (data-page="harvey") — REMOVE_FROM_UI
- **`EXECUTION`** (data-page="execution") — REMOVE_FROM_UI (governance/audit sub-tabs live here too, `['execution','governance','audit']` at line 6145)
- **`NOVA REPLAY`** (data-page="replay") — REMOVE_FROM_UI (MCP replay / decision snapshot viewer)
- **`Dashboard`** — needs inspection; if its cards pull from Harvey/execution state it will need simplification rather than a straight keep (per Pedro's brief: "If the current Overview depends heavily on the retired trading subsystem, simplify it rather than displaying broken cards"). Not yet audited line-by-line — flagging as follow-up before Phase 3.
- **`Alerts`** — per brief, may stay if scoped to general platform/news/system notifications only; today it's fed by `donna_alert_history` which mixes strategy signals and other notices — needs a filter, not a blanket keep.
- **`Journal`, `News`, `Assistant`** — RETAIN as-is.

---

## 7. Shared-file risk summary (short list for quick reference)

| File | Risk if archived wholesale |
|---|---|
| `engines/market_reality.py` + 9 sibling engines | Breaks NOVA Assistant chat context |
| `engines/engines.py` | Breaks Market/News dashboard payload + webhook auto-journal harvey_verdict field |
| `ui/html.py` | Single file for all tabs — risk of breaking Journal/News/Assistant UI while removing Harvey/Execution/Replay |
| `core/state_engine.py` | Locks/regime may be read by non-execution code — unconfirmed, needs a read |
| `health/health.py` | `NOVA_AUTO_EXECUTE` health check semantics invert under the new default |
| `delivery/alert_engine.py` | Delivery plumbing may be wanted for general notifications post-retirement |
| `main.py /webhook` | Sole TradingView ingestion point — disabling removes all inbound signal visibility, even for passive logging |
| `tests/conftest.py` | Shared fixture patches broker state for all tests |

---

## 8. Unknowns needing investigation before Phase 1–4 proceed

- Whether `core/state_engine.py`'s "risk regime" is consumed by anything outside execution/Harvey.
- Whether the `Dashboard` (default) tab's cards depend on Harvey/execution payloads enough to need simplification.
- Whether `Alerts` tab history needs filtering (strategy signals vs general notices) or a clean split.
- Whether `data/nova_execution_trace_v2.json` (currently orphaned per existing memory) should be archived alongside the rest or just left as dead data.
- Scope of "historical execution traces needed for incident analysis" the brief says must not be deleted — which specific files count (candidates: `donna_execution_trace.json`, `nova_execution_safety_log.json`, `nova_execution_safety_alert_registry.json`).

---

## 9. Proposed archive/tag plan (not yet executed)

- Tag: `nova-legacy-trading-subsystem-final` on current HEAD (`c8a62a9`) — **after** the untracked/modified files listed in §1 are committed or explicitly set aside (a tag can't capture uncommitted work).
- Branch: `archive/legacy-trading-subsystem` from the same point.
- Manifest export: branch, tag, commit hash, file inventory (this document), known failures (link `project_indicator_signal_rejection_audit`, `project_execution_bot_v2_audit` from memory), deployment state (Render `main` @ `800d757`).
- No merge of the archive branch back into any active branch.

## 10. Proposed disablement plan (not yet executed)

- Introduce `TRADING_SUBSYSTEM_ENABLED` (default `false`) checked inside `execute_signal()` in `services/execution.py` — the confirmed single chokepoint — so it backstops both Path A and Path B regardless of `NOVA_AUTO_EXECUTE`.
- Update `scripts/start_trading_session.ps1` to stop forcing `NOVA_AUTO_EXECUTE=true` on every scheduled launch.
- Add a test asserting `submit_order`/`close_position`/`close_all_positions`/`cancel_all_orders` raise or no-op when `TRADING_SUBSYSTEM_ENABLED=false`, replacing/extending the existing broker-isolation fixture in `tests/conftest.py`.
- Decide fate of `eod_close_loop()`'s safety-net force-close — likely should stay enabled even with the subsystem otherwise disabled, in case a stray position exists from before the switch flipped.

---

## 11. Regression-test plan for RETAIN features (to run after any Phase 2+ change)

- **Journal:** `/journal/add`, `/journal/data`, `/journal/screenshot`, `/journal/trade-detail`, `/journal/analyze`, `/journal/delete` — create/read/update, screenshot retrieval, AI analysis (credits permitting), persistence across restart. Existing tests: `test_journal_repair.py`, `test_open_trade_pnl_exclusion.py`, `test_nova_review.py`.
- **Market/News:** `/market-data`, `/calendar`, `/earnings`, `/major-indexes`, `/movers`, news/headline loops — confirm no dependency on `engines/reasoning.py` or the indicator.
- **NOVA Assistant:** `/assistant/chat`, `/assistant-data`, task/reminder/focus endpoints — confirm chat still has Market Reality context (pending §4.1 resolution) and confirm `apply_assistant_action` still has no execution-capable action.
- **General:** app startup (all `asyncio.create_task` loops still start cleanly with execution loops removed/gated), navigation, `/system-health`, `/check-env`.

---

## 12. Files expected to change in the retirement (once approved)

ARCHIVE (move, don't delete): `engines/reasoning.py`, `engines/signals.py`, `engines/risk_engine.py`, `engines/native_shadow.py`, `engines/outcome_linker.py`, `engines/post_trade_review.py`, `delivery/signal_log.py`, `monitor.py`, `services/execution*.py` (all), `services/prop_*.py`, `services/audit.py`, `indicators/nova_execution_v1.pine`, associated `tests/test_execution_bot_v2_phase*.py`, `tests/test_phase_*.py` (MCP replay), `tests/test_strategy_governance_gate.py`, `tests/test_cancel_orders_guard.py`, `tests/test_grade_trades_cooldown_governance.py`, `tests/test_eod_exit_price_sign.py`, `tests/test_manual_close_sync.py`, `tests/test_native_shadow.py`, `tests/test_replay_dashboard.py`, `tests/test_mcp_health.py`, `tests/test_mcp_snapshots.py`, `tests/test_execution_import_hardening.py`.

EDIT (surgical, in place): `main.py` (startup loops, webhook handler, `/execution/*` and `/api/mcp-*` routes, `/harvey-data`), `ui/html.py` (remove 3 tabs), `engines/engines.py` (remove `build_harvey_payload`), `health/health.py` (flip `NOVA_AUTO_EXECUTE` semantics), `scripts/start_trading_session.ps1` (stop forcing auto-execute), `core/state_engine.py` (scope TBD), `delivery/alert_engine.py` (scope TBD), `tests/conftest.py` (scope TBD).

UNTOUCHED: `core/state.py`, `core/config.py`, `services/finnhub.py`, `services/news.py`, `services/headlines.py`, `services/assistant.py`, `engines/analytics.py`, `engines/thesis_analysis.py`, `engines/market_reality*.py` + siblings (pending §4.1 confirmation), all Journal endpoints.

---

## 13. Risks and blockers

1. **§4.1 is the biggest blocker** — the intelligence-engine family shares a name ("Market Reality") with a tab being retired but is structurally load-bearing for the Assistant. Needs an explicit decision before any archive/delete touches `engines/market_reality*.py` or siblings.
2. **`scripts/start_trading_session.ps1` auto-arms execution every trading morning via Task Scheduler.** A server-side `TRADING_SUBSYSTEM_ENABLED=false` flag is required — an env-var-only gate that the launcher itself sets is not sufficient, since the launcher is exactly what needs to change.
3. **`ui/html.py`'s size and prior fragility** (documented triple-quote JS escaping incidents) makes tab removal riskier than it looks; needs a manual browser smoke-test per Pedro's own standing rule for frontend changes, not just a code review.
4. **Uncommitted work on the current branch** (§1) should be resolved (committed or explicitly shelved) before tagging, or the archive tag won't reflect the true current state.
5. **`data/nova_execution_trace_v2.json` orphan** — already flagged in memory as unwired; low risk, but worth resolving so the archive manifest doesn't have to guess whether it's "historical execution trace needed for incident analysis" or dead weight.
6. No separate execution-only or indicator-only git branches exist — everything is on `indicator/canonical-signal-phase1` / `main`, which simplifies the tag/branch plan (one archive point, not several to reconcile).

---

**Stopping here per Phase 0 instructions. No code has been changed. Awaiting Pedro's review and explicit approval before Phase 1 (tag/branch/manifest).**
