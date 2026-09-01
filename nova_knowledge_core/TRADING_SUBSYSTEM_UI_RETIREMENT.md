# Trading Subsystem UI Retirement (Phase 3)

Date: 2026-07-16
Status: **The legacy trading subsystem is gone from active navigation.** This is UI retirement, not data destruction or code deletion — every historical file, backend route, and archived implementation described here remains on disk and reachable by direct API call. Nothing in this phase re-enables or reactivates anything; see `TRADING_SUBSYSTEM_DISABLEMENT.md` for the server-side kill switch this phase builds on.

Scope: `ui/html.py` (the single shared `DASHBOARD_HTML` template) and one additive field on `main.py`'s `/check-env`. No other backend behavior changed.

---

## Active navigation — before / after

**Before:** Dashboard · Alerts · Journal · News · Assistant · H.A.R.V.E.Y · EXECUTION · NOVA REPLAY (8 tabs)

**After:** Dashboard · Journal · News · Assistant · Settings (5 tabs)

The four active product pillars (Journal, Market/News, NOVA AI Assistant, Settings) are all present. Dashboard (Overview) remains as a fifth tab because every card on it is sourced from retained data (see below).

---

## Tabs removed

| Tab | Why |
|---|---|
| H.A.R.V.E.Y | Retired strategy-grading UI (verdict, bias score, ORB/PROS/Draws sub-tabs, Market Reality sub-tab). Nav button, `page-harvey` div, and all sub-tab HTML deleted. |
| EXECUTION | Retired execution-bot control panel. Nav button and `page-execution` div deleted. |
| NOVA REPLAY | Retired decision-replay UI. Nav button and `page-replay` div deleted. `tests/test_replay_dashboard.py` (which asserts on that JS block) now self-skips via `pytestmark = pytest.mark.skipif(...)` rather than being deleted — it stays as a historical record of what the tab looked like, and `test_ui_retirement.py` takes over proving the tab is gone. |
| Alerts | See "Alerts" section below — removed for a different reason than the other three. |

## Tabs retained

Dashboard (Overview), Journal, News, Assistant — unchanged in this phase except for nav-bar position. Plus one new tab: **Settings**.

---

## Overview (Dashboard) cards

**Audited, no changes needed in this phase** — a prior pass (already committed/in-flight before this session started) had already stripped every Harvey/execution-sourced card:

- Removed previously: EXECUTION status badge, EXECUTION reason line, RED FOLDER badge, HARVEY SNAPSHOT panel (verdict/confidence/regime/bias score/last signal).
- Retained (all confirmed sourced from macro/market intelligence, none from the retired subsystem): Hero regime + macro tone, Macro Risk badge, Session badge, Market Driver panel, Primary Catalyst panel, 5-symbol Market Board (NQ/ES/VIX/DXY/GOLD), Macro Radar (economic calendar), "NOVA Says" tone panel — all driven by `/dashboard-data`, `/state-engine`, and Grok intelligence, none by Harvey/ORB/PROS/broker state.

No fake zeros or stale placeholders were introduced — every remaining Overview element renders from a live, retained data source.

---

## Alerts behavior

**The Alerts tab was removed from active navigation entirely** — not filtered, not shown empty.

Investigation before editing found that `/api/feed` (the tab's only data source, in `services/feed.py`) merges exactly four event types: `SIGNAL`, `EXECUTION`, `GOVERNANCE`, `MR2_CHANGE` — all originating from the retired reasoning/execution pipeline. There is no economic-event or breaking-news event type flowing into this feed; that data exists in a separate system (`services/headlines.py`, `delivery/macro_discord.py`, `donna_macro_events.json`) that currently only pushes to Discord, not to any UI feed. Filtering the existing feed down to "reliable" categories would have left the tab empty essentially always, which the retirement brief explicitly forbids ("do not display fake zeros or stale values merely to fill space").

Decision (confirmed with Pedro before implementation): remove the tab now; rebuild it later against a real economic/news event source if wanted. Nothing about the backend was touched — `/api/feed`, `/api/feed/card/{id}`, `/api/feed/stats`, `/api/feed/health`, and `/api/feed/ingest` all remain registered and functional; only the frontend calls into them were stopped (see next section).

---

## Retired frontend polling stopped

Three boot-time calls were removed from the end of the `<script>` block:

| Removed | What it did |
|---|---|
| `initFeedNotifications();` | Requested/managed browser notification permission for the Alerts tab. |
| `setInterval(refreshFeed, 30000);` | Polled `/api/feed` + `/api/feed/stats` every 30s regardless of active tab. |
| `connectSSE();` | Opened a persistent `EventSource` to `/stream`, which the `/webhook` handler pushes to on every incoming TradingView signal (`harvey_verdict`, `ict_step`, `kill_zone`, etc.). It drove `maybeSendNotif()` — an **audio ping** (Web Audio oscillator, no permission required) plus an optional browser popup for `EXECUTION_READY` or Grade A/B signals — with no visible card behind it once the Alerts tab was gone. This was the clearest remaining case of "implying the retired subsystem is operational": incoming legacy strategy signals would have kept audibly announcing themselves with no UI page to explain what was making the sound. |

The tab-switch click handler's `if (btn.dataset.page === 'alerts') { ... refreshFeed(); }` branch was removed and replaced with `if (btn.dataset.page === 'settings') { refreshSettings(); }`.

**Known limitation:** the JS *function bodies* for the feed/SSE subsystem (`refreshFeed`, `connectSSE`, `maybeSendNotif`, `setFdCat`/`setFdDate`/`setFdSym`, `loadMoreFeed`, `fdExecution`, etc. — roughly 400 lines) and the dead `refreshScenarios`/`renderScenarios` scenario-engine JS (whose HTML page was already gone before this phase) were left in place, unreachable, rather than deleted. They have zero remaining call sites (verified: `grep` for every call-site of each function shows only internal self-references within the dead subsystem, never a boot-time or click-handler invocation) and are inert. Full removal was deferred to avoid a larger, riskier edit to a shared 4200-line file for code that is already provably unreachable — a candidate for a future dedicated cleanup pass, not a safety concern.

---

## Retired route behavior

No backend routes were deleted or given new "RETIRED" response bodies in this phase. Every route exclusively tied to the retired subsystem (`/api/governance`, `/api/execution-state`, `/harvey-data`, `/execution/close`, `/execution/close-all`, `/execution/cancel-orders`, `/execution/macro-lock`, `/execution/red-folder-lock`, `/execution/trade-permission`, `/execution/settings`, `/close-all`, plus the Phase 8 `/api/prop-*` routes) was already unreachable from the frontend before this phase started — a full audit of every `fetch(...)` call in `DASHBOARD_HTML` (`tests/test_ui_retirement.py::test_no_frontend_fetch_targets_a_broker_write_route` makes this permanent) confirmed none of them target a broker-write path. Per the retirement brief's option 1 ("stop calling them from the frontend and leave them archived but unreachable"), no route-level change was needed or made. None of these routes start background work on their own — they are request/response only.

The `/api/mcp-replay/*` routes (decisions, fingerprints, similar, outcomes, similar-with-outcomes, post-trade-reviews, shadow) remain fully registered and functional — only their UI tab is gone, not the data or the API.

---

## NOVA Assistant terminology changes

**None were needed.** Audit of `services/assistant.py`'s system prompt and action dispatch, and of the Assistant page HTML/quick-commands in `DASHBOARD_HTML`, found:

- The system prompt already identifies the assistant as "NOVA, an elite market intelligence assistant" — no Harvey identity, no claim of live execution or active trading.
- `apply_assistant_action()` only supports `{none, set_focus, add_task, add_reminder, clear_tasks, clear_reminders}` — no broker-write action exists for the LLM to invoke even if it wanted to.
- No "Harvey", "H.A.R.V.E.Y", "auto execute", "live trading", or "active trading bot" strings appear anywhere in `services/assistant.py` or the Assistant page markup.

This was almost certainly already correct from earlier work; this phase only confirmed it and added `test_broker_and_auto_execute_controls_absent` / the Harvey-mention tests as a permanent guard.

---

## New: Settings tab

No Settings tab existed anywhere in the UI before this phase, despite being one of the four required active pillars. Rather than build a fake or partially-wired settings editor, the new tab is deliberately minimal and **entirely read-only, entirely real**:

- **Trading Subsystem status** — reads the actual `NOVA_TRADING_SUBSYSTEM_ENABLED` value (new field added to `/check-env`) and displays `RETIRED · DISABLED` (or `ENABLED`, honestly, if the flag is ever flipped) plus a plain-language explanation.
- **Integrations** — Anthropic/Telegram/Finnhub/FMP/Discord-Macro connection status, from the existing `/check-env` endpoint.
- **System** — chat/fast model names and server time (ET), from `/check-env` and `/system-health`.

No editable controls were added. `donna_settings.json`'s `theme_mode`/`layout_density` keys were considered but rejected for this phase: there is no existing client-side mechanism that reads or applies them (verified — no `data-theme`/theme-switch JS exists anywhere in the codebase), so exposing them as togglable would have been a non-functional control. `telegram_alert_mode` was also rejected as an editable field: it is loaded once from an environment variable at process startup (`core/config.py`), not read dynamically from the settings file, so a JSON-patch "save" would silently do nothing until a restart — the retirement brief's "no fake zeros or stale values" principle applies equally to fake controls.

---

## Preserved historical systems

Nothing was deleted. Confirmed still intact and reachable:

- **Journal** — `/journal/data`, `/journal/add`, `/journal/delete`, `/journal/signals` all unchanged; the in-Journal "Evaluations" sub-tab (historical NOVA signal evaluations) and Trade Detail modal (execution trace, governance-at-execution, PROS phase) are untouched — these are historical/read-only displays within the retained Journal pillar, not live strategy controls.
- **NOVA Replay backend** — decisions, fingerprints, similarity, outcome-linking, post-trade reviews all still served; only the nav tab is gone.
- **Signal/execution/governance logs** — `donna_signal_log.json`, `donna_execution_trace.json`, and related files are untouched; `/api/feed*` still serves them for anyone hitting the API directly.
- **Phase 8 prop-firm dry-run trial work** — `services/prop_dry_run_trial.py`, its `/api/prop-dry-run-trial/status` route, and its background tracking tick in `execution_safety_loop()` were not touched by this phase (confirmed via `git diff --stat` before editing — see Git Discipline below).

---

## Known limitations

1. Alerts has no active replacement yet — see "Alerts behavior" above. Rebuilding it against a real economic/news event source is future work, not started here.
2. ~400 lines of now-unreachable feed/SSE JS (and a smaller amount of pre-existing dead scenario-engine JS) remain in `ui/html.py`, uncalled. Confirmed inert; candidate for a future cleanup pass.
3. Orphaned CSS-only selectors (`.harvey-btn`, `.orb-*`, `.hv-orb-badge`, etc.) remain in the stylesheet with no matching HTML element. Invisible to users; not a safety or branding concern, just unused CSS.
4. Settings is intentionally minimal (status/integrations/system info only). No user-editable preferences were added in this phase.

## Future clean-rebuild boundary

This phase does not start, plan, or scope a clean trading-core rebuild. The archived implementation remains at `archive/legacy-trading-subsystem` / tag `nova-legacy-trading-subsystem-final`, not approved for production use. Any future rebuild — of Alerts against a real news/economic feed, of a genuine strategy engine, or of anything else described as "future work" above — requires a separate, explicitly-approved design pass, per the retirement brief.

---

## Tests

`tests/test_ui_retirement.py` — 23 tests (18 required assertions plus a few parametrized/supporting cases), all passing:

1–4. Active navigation contains Journal, Market(News), NOVA(Assistant), Settings.
5–10. H.A.R.V.E.Y, EXECUTION tab, NOVA REPLAY, Alerts, legacy strategy sub-tab controls, and broker/auto-execute control phrasing are all absent (with a companion test proving every remaining "H.A.R.V.E.Y" string is either a dead CSS comment or this document's own retirement disclosure — never live branding).
11. Retired boot-time polling (`initFeedNotifications`, `connectSSE`, `refreshFeed` interval) does not start.
12–14. Journal, Market, and NOVA Assistant routes remain registered on the FastAPI app.
15. `main.py` imports cleanly (full app startup) with trading disabled.
16. No `fetch()` call in the dashboard HTML targets a broker-write route (static allowlist check against every known execution/governance/harvey endpoint).
17. Historical Journal access and the full NOVA Replay backend route set remain registered/importable.
18. No Pine-write function names appear in the dashboard HTML (static proxy); manual `git diff` confirmed no changes to `indicators/` or the TradingView submodule pointer beyond what pre-existed this session (see Git Discipline).

### Full suite result

**465 passed, 7 failed, 13 skipped.**

The 13 skips are all `tests/test_replay_dashboard.py` self-skipping now that the Replay tab is gone (by design, see "Tabs removed" above).

Of the 7 failures, **none are caused by this work** (nothing in `services/execution.py`, `services/execution_bridge.py`, or any governance/gate test file was touched):

- **2 pre-existing, date-sensitive** (already known before this phase, documented in `TRADING_SUBSYSTEM_DISABLEMENT.md`): `test_journal_repair.py::test_stats_are_correct_after_merge_not_double_counted`, `test_open_trade_pnl_exclusion.py::test_mixed_open_and_closed_journal_only_counts_closed` — both assert a hardcoded `daily_pnl.this_week` value against fixture dates that have aged out of "this week."
- **5 newly-observed, time-of-day-sensitive** (not previously documented — discovered during this session's full-suite run, reproduced in isolation, confirmed unrelated): `test_strategy_governance_gate.py::test_execute_signal_rejects_ict_before_reaching_alpaca`, `test_strategy_governance_gate.py::test_gc_is_rejected_before_alpaca_by_the_etf_routing_step`, `test_strategy_governance_gate.py::test_execute_signal_rejects_disallowed_market_via_new_gate_before_alpaca`, `test_grade_trades_cooldown_governance.py::test_execute_signal_rejects_over_daily_limit_before_alpaca`, `test_grade_trades_cooldown_governance.py::test_execute_signal_rejects_low_grade_before_alpaca`. The suite ran at 20:00 ET; `services/execution.py`'s session-hours gate now blocks with `STATE_GATE_BLOCKED` ("outside NY session hours — window: 09:30–16:00") before these tests' target gate is ever reached, so the assertion on the *specific* rejection code fails. Reproduced in isolation (`pytest tests/test_strategy_governance_gate.py tests/test_grade_trades_cooldown_governance.py`) with identical results, independent of the rest of the suite. This is pre-existing test/gate-ordering behavior in code this phase never touched — flagged here as new information for Pedro, not attributed to Phase 3.

---

## Git discipline

Before editing: `git status` showed pre-existing modifications to `main.py`, `mcp/tradingview` (submodule pointer), `tests/test_replay_dashboard.py`, and `ui/html.py` already in the working tree, plus a set of untracked Phase 8 (prop dry-run trial) files and runtime `data/*.json` files — all pre-existing from before this session, confirmed unrelated to trading-subsystem retirement (the `main.py` diff was 100% Phase 8 dry-run-trial wiring; the `ui/html.py` and `test_replay_dashboard.py` diffs were prior-session Phase 3 work already in progress, reused and completed here rather than redone). None of the pre-existing untracked files were staged by this work. `indicators/` (Pine Script) and the TradingView submodule were not touched further by this phase.
