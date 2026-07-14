# NOVA EXECUTION V1 — Phase 6.3: Canonical Bridge Cutover Audit and Safe Parser Migration

**Status:** Parser/reasoning migration implemented, additive only. Python files changed: `engines/reasoning.py`, `delivery/signal_log.py`, `tests/test_phase_6_3_canonical_bridge.py`. **No Pine file changed this phase** — the CANON_* fields it parses were already emitted by `indicators/nova_execution_v1.pine` since Phase 1/6.2. No execution/broker file touched. Live TradingView cloud script untouched.

---

## PART 1 — LEGACY BRIDGE CONSUMER MAP

Full-codebase trace (Pine dashboard/bridge, Python parser, reasoning engine, alerts, execution bridge, replay/snapshot, tests, dashboard UI):

### `CMD` / `SYS_STATE` (legacy, from `donnaCommand`/`donnaScenario`) — heavily actionable

| Consumer | Field | Behavior | Actionable? | BRIDGE_VER-aware? |
|---|---|---|---|---|
| `engines/reasoning.py:374-378` (`_parse_nova_tables_impl`) | `d.get('CMD')`, `d.get('SYS_STATE')` | Populates `parsed['main']['CMD']`/`['STATE']` | Enables all downstream actionable use | No |
| `engines/reasoning.py` `_evaluate_price_structure` | `main_state.get('CMD')` | `cmd_up` contributes to `bias_long`/`bias_short` → OTE-zone `direction` | **Yes** | No |
| `engines/reasoning.py` `_evaluate_pros_phase` | `main_state.get('CMD')` | `cmd_up` is "unconditionally authoritative" for PROS `direction`, overriding DISPL | **Yes** | No |
| `engines/reasoning.py` `_evaluate_ib_alignment` | `main_state.get('CMD')` | Infers IB `draw` when the PROS table doesn't disambiguate (`draw_source='CMD'`) | **Yes** | No |
| `engines/reasoning.py` `_check_invalidation_signals` | `main_state.get('STATE')` | Keyword-scans for INVALID/BROKEN/FAILED/VIOLATED → `invalidated=True` | **Yes** | No |
| `engines/reasoning.py` `_build_evaluation_prompt` | `json.dumps(main_state)` | Whole dict dumped into the Claude prompt | Informational input to an actionable decision | No |
| `engines/reasoning.py::_evaluate_single_chart` | `main_state.get('CMD')`/`.get('STATE')` | Logged as `nova_cmd`/`nova_state_val` via `log_cycle()` | Indirectly actionable (see execution_bridge below) | No |
| `delivery/signal_log.py` | `nova_cmd`, `nova_state_val` params | Persisted verbatim in `donna_signal_log.json` | Feeds execution_bridge's context lookup | No |
| **`services/execution_bridge.py::_check_directional_alignment`** | `ctx.get('nova_state')`, `ctx.get('nova_cmd')` (from the signal-log entry) | Gate 6b `DIRECTIONAL_CONTEXT` — a **conflict/veto check** that can block an otherwise-approved EXECUTION_READY ORB/PROS trade if the broader market-context text disagrees | **Yes — most actionable consumer, and it lives in execution-layer code** | No |
| `services/execution_trace.py:472` | `main_st.get('CMD')` | Stored in `pine_summary` for `donna_reasoning_trace.json` | Diagnostic/replay only | No |
| `main.py` `/journal/analyze` | `s.get('nova_cmd')` | Formats a post-trade-review Claude prompt block | Informational, not a live trade path | No |
| `ui/html.py` (signal feed, journal timeline) | `s.nova_cmd` | Renders a colored chip in the dashboard | Purely display, to a human | No |
| Various `tests/test_phase_b_parser.py`, `test_mcp_health.py`, `test_mcp_snapshots.py`, `test_phase_d/f/g/h/i_*.py` | `main_state['CMD']`, raw rows | Parser/snapshot correctness assertions | Test-only | Several test version gating explicitly |

**Migration risk for `services/execution_bridge.py`: HIGH, and explicitly out of scope.** This file sits in the execution layer, between reasoning and the broker. The user's instruction for this phase is "do not change execution or broker logic" — `_check_directional_alignment` is a **conflict/veto** gate on a signal whose direction and strategy already came from the webhook payload (ORB/PROS-sourced, per Phase 6.1/6.2's confirmed governance), not the *source* of the trade signal. It is reported here per Part 1's instruction to map every consumer, but **not touched or migrated** in Part 3/4 — a dedicated, separately-scoped execution-layer phase would be needed to migrate it, if ever desired.

### `BRIDGE_VER` / `bridge_ver` / `bridge_v2` / `bridge_meta` — strictly observational

| Consumer | Behavior | Actionable? |
|---|---|---|
| `engines/reasoning.py::_parse_nova_tables_impl` | Computes `bridge_ver`, `v2_detected`, builds `bridge_v2`/`bridge_meta` | No — docstring states "Observation only" |
| `engines/reasoning.py::compute_mcp_health` | 0-100 health/confidence score, HEALTHY/DEGRADED/BROKEN | No — explicitly "does NOT gate execution" |
| `engines/reasoning.py::_build_mcp_snapshot` | Replay/audit snapshot, capped rolling JSON file | Diagnostic/replay only |
| `main.py` `/api/mcp-health`, `ui/html.py` `refreshMcpHealth` | Serves/renders health JSON | Informational dashboard display |
| `tests/test_mcp_health.py`, `test_mcp_snapshots.py`, `test_phase_b_parser.py`, `test_phase_d/e_*.py` | Assert presence/absence/values | Test-only |

### `CANON_*` fields (before this phase)

Confirmed via full-repo grep: **zero Python consumers existed.** `_V2_KEYS` capped at `DRAW_TARGET`/`DRAW_DIR` (Pine row 33); rows 34-42 (`CANON_STATE` through `CANON_SELL`) were emitted by `indicators/nova_execution_v1.pine` since Phase 1 but never read by any Python file — consistent with the original audit's own finding ("confirmed zero existing references... no compatibility risk"). This phase closes that gap, additively.

**Important naming note found during this audit:** the actual Pine bridge key is `CANON_STRAT`, not `CANON_STRATEGY` as referenced in the task instructions — confirmed by reading `indicators/nova_execution_v1.pine` directly (`table.cell(novaBridge, 0, 36, "CANON_STRAT", ...)`). The parser matches the real key (`CANON_STRAT`) while the Python-side field is named `canonical_strategy` for clarity, matching the requested schema.

---

## PART 2 — CANONICAL SCHEMA (source of truth)

| Field | Type | Allowed values | Meaning |
|---|---|---|---|
| `canonical_state` | `str \| None` | `WAIT`, `HEADS_UP`, `LOCKED`, `EXECUTION_READY` | Pine's `canonicalSignalState` — overall readiness |
| `canonical_direction` | `str \| None` | `LONG`, `SHORT`, `NONE` | Pine's `canonicalDirection` |
| `canonical_strategy` | `str \| None` | `ORB`, `PROS`, `NONE` | Pine's `canonicalStrategy` — **ICT can never appear**, structurally guaranteed (Phase 6.2) and re-validated here |
| `canonical_setup` | `str \| None` | An ORB/PROS `setup_type` value, or `NONE` | Pine's `canonicalSetup` |
| `canonical_grade` | `str \| None` | `A`/`B`/`C`/`D`/`NA` | Pine's `canonicalGrade` |
| `canonical_liquidity_source` | `str \| None` | e.g. `PDH`, `ASIA HIGH`, `NONE` | Pine's `canonicalLiquiditySource` |
| `canonical_interaction` | `str \| None` | e.g. `MID_REJECT`, `NONE` | Pine's `canonicalInteraction` |
| `canonical_buy` | `bool \| None` | — | Pine's `canonicalBuy` |
| `canonical_sell` | `bool \| None` | — | Pine's `canonicalSell` |
| `canonical_available` | `bool` | — | `True` iff `BRIDGE_VER >= 3` |
| `canonical_degraded` | `bool` | — | `True` iff v3 detected but malformed (see validation below) |
| `canonical_warnings` | `list[str]` | — | Human-readable reasons for degradation |

**Validation performed on every v3 parse:**
- `canonical_buy` and `canonical_sell` cannot both be `True` (flags degraded).
- `canonical_strategy` must be `ORB`, `PROS`, or `NONE` — anything else (including `ICT`) flags degraded.
- `canonical_state`/`canonical_direction` must be one of their allowed values.
- `canonical_buy=True` requires `canonical_direction == 'LONG'`; `canonical_sell=True` requires `SHORT`.
- `canonical_state == 'EXECUTION_READY'` requires `canonical_direction` to be `LONG` or `SHORT`.
- Any missing `CANON_*` field on a v3 chart flags degraded (logged, not silently ignored).

**Malformed data is never treated as a valid trade** — degraded parses return `canonical_direction`/`canonical_buy`/`canonical_sell` as `None` from `derive_actionable_signal()`, not a guessed default.

---

## PART 3 — PYTHON PARSER MIGRATION (`engines/reasoning.py`)

New code, entirely additive, added at the end of the existing `NOVA BRIDGE` branch of `_parse_nova_tables_impl` (before its `return parsed`):

- `_parse_canonical_v3(d, bridge_ver, main_cmd, main_sys_state) -> (canonical, canonical_mismatch)` — builds the schema above plus mismatch telemetry (Part 5).
- `derive_actionable_signal(nova_state) -> dict` — the "what should Python act on" contract: returns canonical-sourced fields when `canonical_available and not canonical_degraded`, otherwise returns an all-`None` dict with `source='legacy_unavailable'` or `source='degraded'`. **It does not fall back to reading CMD/SYS_STATE itself** — see Part 4.
- `parsed['canonical']` and `parsed['canonical_mismatch']` are new top-level keys on `parse_nova_tables()`'s return value.

**Backward compatibility, verified:**
- BRIDGE_VER 1/2: `canonical_available=False`, `canonical_mismatch=None`, `derive_actionable_signal()` returns `source='legacy_unavailable'`. `parsed['main']`/`['pros']`/`['orb']`/`['bridge_v2']`/`['bridge_meta']` are all populated exactly as before this phase — confirmed via the full existing regression suite (128 tests across `test_phase_b_parser.py`, `test_mcp_health.py`, `test_mcp_snapshots.py`, `test_phase_d/e/f/g/h/i_*.py`, `test_strategy_governance_gate.py`, `test_grade_trades_cooldown_governance.py`), all still passing unchanged.
- Nothing in `_V2_KEYS`, `compute_mcp_health`, or the legacy three-table fallback path was modified.

---

## PART 4 — REASONING CUTOVER

**Design decision, stated explicitly:** `_evaluate_price_structure`, `_evaluate_pros_phase`, `_evaluate_ib_alignment`, `_check_invalidation_signals`, and `_classify_signal` were **not modified**. These are deeply nuanced, live-tested functions that blend CMD text with IB draw, PROS displacement text, session context, and multi-branch phase logic — rewriting their internals to "prefer canonical" would risk exactly the kind of qualification-logic change the instruction explicitly forbids ("do not change actual ORB or PROS qualification logic"), and there is no way to verify such a rewrite is behavior-preserving without live production data, which does not yet exist for BRIDGE_VER 3 (see Part 3 of this document / the live-data limitation, restated below).

Instead, `derive_actionable_signal()` is a **new, additive, pure function** that implements the requested contract exactly:
- `BRIDGE_VER >= 3` and valid → `actionable_direction`/`actionable_strategy`/`actionable_setup`/`actionable_state`/`actionable_buy`/`actionable_sell` all come from `canonical_*` fields, never from CMD/SYS_STATE.
- Otherwise → every `actionable_*` field is `None` (it does not silently reconstruct an answer from legacy fields — that remains the existing evaluators' job, untouched).

`_evaluate_single_chart` now also writes the canonical fields (`canonical_state`, `canonical_direction`, `canonical_strategy`, `canonical_setup`, `canonical_grade`, `canonical_buy`, `canonical_sell`) and legacy fields (`legacy_cmd`, `legacy_sys_state`, `legacy_canonical_mismatch`, `mismatch_reason`) to `delivery/signal_log.py::log_cycle()` — **additively, alongside** the existing `nova_cmd`/`nova_state`/`alert_type`/`direction`/`setup_type`/`grade` fields, which are **completely unchanged** and continue to be what actually drives `alert_required`, Discord delivery, and the existing execution path today.

**What this means concretely:** as of this phase, the canonical fields are fully parsed, validated, logged, and available — but the live alert-routing/execution decision still flows through the existing `_classify_signal` pipeline, exactly as before. Flipping the *live* decision over to prefer `derive_actionable_signal()`'s output is the natural next step once (a) BRIDGE_VER 3 is actually deployed to the live chart, and (b) the Pine canonical vocabulary (`WAIT`/`HEADS_UP`/`LOCKED`/`EXECUTION_READY`) is explicitly reconciled against the existing `alert_type` vocabulary (`None`/`HEADS_UP`/`EXECUTION_READY`/`INVALIDATION`/`NO_TRADE` — `LOCKED` has no direct existing equivalent and needs an explicit design decision, not an assumed mapping). See Rollout Plan below.

---

## PART 5 — MISMATCH TELEMETRY

`_parse_canonical_v3` computes `canonical_mismatch` whenever `BRIDGE_VER >= 3` and the canonical parse is not degraded:

```python
{
    'legacy_canonical_mismatch': bool,   # True if any disagreement found
    'legacy_cmd':                str,    # raw CMD text
    'legacy_sys_state':          str,    # raw SYS_STATE text
    'canonical_state':           str | None,
    'canonical_direction':       str | None,
    'canonical_strategy':        str | None,
    'mismatch_reason':           str,    # human-readable, semicolon-joined
}
```

Mismatch conditions checked: (1) legacy `CMD` says `BUY`/`SELL` while `canonical_state != 'EXECUTION_READY'`; (2) legacy direction (derived from `CMD`) disagrees with `canonical_direction` when both are non-`NONE`; (3) legacy `SYS_STATE` mentions `ICT` while `canonical_strategy` is `ORB`/`PROS` (the exact scenario documented in Phase 6.2 — `eliteICTLong`/`eliteICTShort` driving `donnaCommand`/`donnaScenario` independently of the canonical path). **Legacy values never win** — a mismatch is logged, not resolved in legacy's favor; `derive_actionable_signal()` always prefers canonical when available, regardless of what legacy says.

Mismatches are both printed (`[nova-bridge-v3] legacy/canonical mismatch: ...`) and persisted per-cycle via the new `log_cycle()` fields, so they're queryable historically, not just visible in real-time logs.

---

## PART 6 — TEST MATRIX

New file: `tests/test_phase_6_3_canonical_bridge.py`, 10 tests, all passing:

| # | Test | Verifies |
|---|---|---|
| 1 | `test_bridge_v3_orb_buy_parses_correctly` | Clean ORB BUY v3 payload parses with correct canonical + actionable fields |
| 2 | `test_bridge_v3_pros_sell_parses_correctly` | Clean PROS SELL v3 payload parses correctly |
| 3 | `test_canonical_wait_legacy_ict_buy_no_actionable_signal` | Legacy CMD=BUY/SYS_STATE=ICT + canonical=WAIT → no actionable BUY, mismatch logged with reason |
| 4 | `test_canonical_none_legacy_elite_cont_no_trade_signal` | Legacy SYS_STATE="ELITE CONT LONG" + canonical=NONE → no actionable direction/strategy |
| 5 | `test_canonical_buy_and_sell_both_true_is_degraded` | Malformed dual-true payload → degraded, `actionable_direction is None` |
| 6 | `test_canonical_strategy_ict_rejected` | `CANON_STRAT=ICT` → degraded, rejected, `actionable_strategy is None` |
| 7 | `test_bridge_v2_unchanged_no_canonical` | v2 chart: `canonical_available=False`, `canonical_mismatch=None`, legacy `main`/`pros`/`orb` parsing byte-identical |
| 8 | `test_missing_canonical_fields_degraded_safely` | Missing `CANON_GRADE`/`CANON_LIQ_SRC` → degraded with named-field warnings, safe `None` actionable output |
| 9 | `test_log_cycle_keeps_canonical_and_legacy_fields_separate` | `log_cycle()` entry has distinct `canonical_*` and `legacy_*` keys, never merged; existing `nova_cmd`/`nova_state` fields unaffected |
| 10 | `test_no_execution_or_broker_import_in_this_file` | AST-verified: this test file imports no `services.execution*` module |

**Full regression run (existing suites, unmodified):** `test_phase_b_parser.py` (12/12), `test_mcp_health.py` (11/11), `test_mcp_snapshots.py` (10/10), `test_phase_d_decision_snapshot.py` (14/14), `test_phase_e_replay_query.py` (17/17), `test_phase_f_fingerprint.py` (14/14), `test_phase_g_similarity.py` (15/15), `test_phase_h_outcome_linking.py` (16/16), `test_phase_i_post_trade_review.py` (19/19), `test_strategy_governance_gate.py` (16/16), `test_grade_trades_cooldown_governance.py` (15/15) — **all still passing, zero regressions.**

---

## LIVE-DATA LIMITATION (restated)

As with Phase 6.1: the live TradingView cloud script has not been updated with any of Phases 1-6.3's Pine work. `BRIDGE_VER` on the live chart is currently 1 or 2, meaning `canonical_available` will be `False` and every new code path in this phase is presently **dormant** in production — confirmed dormant, not merely assumed, since `derive_actionable_signal()` explicitly returns `source='legacy_unavailable'` whenever `bridge_ver < 3`. Real BRIDGE_VER-3 mismatch telemetry can only be observed after a separate, explicit decision to deploy the current Pine source to the live chart.

---

## ROLLOUT PLAN

1. (Already done, this phase) Ship the additive parser/reasoning/log-schema changes — zero behavior change while the live chart stays on BRIDGE_VER 1/2.
2. Deploy the current local Pine source to the live chart (separate, explicit decision — not assumed or performed here).
3. Observe `canonical_mismatch` telemetry in `donna_signal_log.json` for a defined validation window, comparing canonical vs. legacy agreement rate in real conditions.
4. Design and get explicit approval for the `canonical_state` → `alert_type` vocabulary mapping (specifically how `LOCKED` should be represented in the existing `alert_type` enum).
5. Only then, in a separately-scoped phase, wire `derive_actionable_signal()`'s output into `_classify_signal`'s actual return value (or the call site that consumes it) as the authoritative source for BRIDGE_VER-3 charts — with its own dedicated regression tests proving ORB/PROS behavior is unchanged for BRIDGE_VER 1/2 and correctly canonical-driven for BRIDGE_VER 3.
6. `services/execution_bridge.py`'s `DIRECTIONAL_CONTEXT` gate is a separate, execution-layer concern — any change there requires its own dedicated, explicitly-scoped phase, not bundled with the reasoning-layer cutover above.

## ROLLBACK PLAN

Every change in this phase is additive:
- `engines/reasoning.py`: `parsed['canonical']`/`parsed['canonical_mismatch']` are new dict keys; removing the `_parse_canonical_v3` call and the two new functions fully reverts to pre-Phase-6.3 behavior with no other code path affected.
- `delivery/signal_log.py`: the new `log_cycle()` parameters all default to empty/`None` and are purely additive dict keys in the persisted entry; omitting them entirely is backward compatible (existing readers of `donna_signal_log.json` that don't know about these keys are unaffected).
- No existing function signature was changed in a breaking way (no existing parameter removed or repositioned; all new parameters are keyword-only with defaults).
- If reverted, simply `git revert` this phase's commit — nothing downstream depends on the new fields yet (confirmed: they are not read anywhere outside this phase's own new test file).
