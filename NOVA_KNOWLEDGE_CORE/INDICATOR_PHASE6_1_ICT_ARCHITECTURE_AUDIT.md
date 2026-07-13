# NOVA EXECUTION V1 — Phase 6.1: ICT Canonical-Strategy Architecture Audit

**Status:** Audit only. No Pine or Python code changed in this document's production. `indicators/nova_execution_v1.pine` was read-only for this part; the parity correction in Part 1 (separate commit) is the only code change this phase.

**Live-data limitation, stated plainly (Part 3):** the updated local Pine source (Phases 1–6.1) has not been manually deployed to the live TradingView cloud script, by explicit instruction throughout this engagement. Fresh canonical `buySignal`/`sellSignal`/`ictBuySignal` firing counts cannot be measured yet — none of the counts in this document are live telemetry from the current code. The "Recent live alerts?" column above is populated from the historical incident record (`tests/test_strategy_governance_gate.py`'s documented background, referring to an alert that occurred before this engagement) and from static code-path tracing, not from a fresh measurement. Real candidate/pass/fail counts for the current canonical pipeline require deploying this source to the live chart first — a separate, explicit decision, not assumed here.

---

## HEADLINE FINDING

This is not a purely theoretical/architectural question. **ICT already caused a real incident.** From `tests/test_strategy_governance_gate.py`'s own documented background:

> "a live `ICT_OB_FVG_ENTRY` alert from the TradingView indicator executed two real paper trades" — because `main.py`'s public `/webhook` called `execute_signal()` directly with no strategy/instrument check at all, even though `donna_settings.json` had *always* correctly restricted every execution profile to `allowed_strategies=["PROS","ORB"]`.

This has since been fixed: `check_strategy_and_instrument_allowed()` (in `services/execution.py`) is now the single gate both the webhook and `execute_signal()` call against the exact same config — confirmed via `check_strategy_and_instrument_allowed('ICT', ...)` returning `{'allowed': False, 'code': 'STRATEGY_NOT_ALLOWED'}` for every current execution profile (`autonomous_test`, `paper_validation`, `prop_firm`, `live_personal` — all four configured with `allowed_strategies: ['PROS', 'ORB']`, confirmed by reading `data/donna_settings.json` directly). Extensive regression tests (11 tests in that file) lock this in. **ICT cannot reach the broker today, by explicit, tested, defense-in-depth configuration — this was never a gap in the allowlist itself, only in an execution path that used to bypass it.**

What remains open is a **naming/architecture** question, not a live safety gap: the Pine chart, bridge, and Discord-alert layers still treat ICT as if it were a third peer strategy alongside ORB/PROS, which is exactly the ambiguity the user's Phase 3 correction (for RP) already established should not exist unaddressed.

---

## FULL ICT SIGNAL PATH (Pine → Python)

### Pine side (`indicators/nova_execution_v1.pine`)

| Stage | Variable(s) | Trigger | Line(s) |
|---|---|---|---|
| Kill zone timing | `isLondonKZ`/`isNYKZ`/`isLondonClose`/`isKillZone` | Fixed hour windows (London 2-5, NY 7-11, London close 10-12, ET) | 1671–1674 |
| HTF swing levels | `last1hSwingHigh/Low`, `last4hSwingHigh/Low` | `request.security` HTF pivot highs/lows (1h, 4h) | 1682–1699 |
| Dealing range | `dealingRangeHigh/Low/Mid`, `inDealingPremium/Discount` | PDH/PDL or HTF swing fallback, midpoint premium/discount | 1701–1711 |
| Step 1 — HTF liquidity sweep | `sweep1hHigh/Low`, `sweep4hHigh/Low`, `htfSweepHigh/Low`, `sweepHighFresh/LowFresh` | Sweep of 1h/4h swing pivot or PDH/PSH/PWH (or low mirror), fresh within 20 bars | 1726–1754 |
| Step 1b — session gate | `sweepHighGateOK/sweepLowGateOK` | Sweep must not have occurred in Asia/London unless in NY kill zone | ~1756–1780 |
| Step 2 — HTF BOS | `htf5mBullBOS/BearBOS`, `htf15mBullBOS/BearBOS`, `step2BullActive/BearActive` | 5m/15m break of structure, active within 30 bars | ~1820–1850 |
| Step 2b — OB/FVG entry zone | `ictEntryZoneLong/Short` | HTF order block or FVG entry + dealing-range discount/premium alignment | 1851–1852 |
| Step 3 — 79% extension + 1m BOS | `step3LongReady/ShortReady`, `step3LongElite/ShortElite` | 79% Fibonacci extension of the sweep leg + 1-minute BOS, inside kill zone; "Elite" requires *both* conditions simultaneously rather than either | 1867–1871 |
| Step 4 — SMT confirmation | `ictSMTLong/Short` | Step 3 ready + cross-market (ES/NQ) smart-money-technique divergence | 1874–1875 |
| **Final readiness** | `ictLongReady`/`ictShortReady` | `(step3Ready or (BOS+FVG+killzone) or (freshSweep+BOS+OB)) and localBias and not nearOpposingLiquidity` | 1878–1886 |
| **Signal** | `ictBuySignal`/`ictSellSignal` | `ictLongReady/ShortReady and canSmartBuy/Sell` (20-bar cooldown) | 2247–2248 |
| Setup naming | `strategy_family == "ICT"`, `setup_type` ∈ {`ICT_ELITE`, `ICT_SMT_CONFIRMATION`, `ICT_OB_FVG_ENTRY`, `ICT_LIQUIDITY_SWEEP`} | Priority chain over which ICT condition fired | 2257–2276 |
| Composite | `buySignal := orbBuySignal or ictBuySignal or prosBuySignal` (SELL mirror) | **Original, pre-Phase-1, untouched** | 2286–2287 |
| Canonical | `canonicalBuy`/`canonicalSell` | Inherit `ictBuySignal`/`ictSellSignal` via `buySignal`/`sellSignal`, unchanged since Phase 1 | 2386–2387 |
| Chart marker (Phase 2) | `canonicalMarkerStrategyText` | Maps `ICT_ELITE`→"ICT ELITE CONTINUATION", `ICT_SMT_CONFIRMATION`→"ICT SMT CONFIRMATION", `ICT_OB_FVG_ENTRY`→"ICT OB/FVG ENTRY", `ICT_LIQUIDITY_SWEEP`→"ICT LIQUIDITY SWEEP" | 2510–2513 |
| Canonical alert | `alertcondition(canonicalBuyNew/SellNew, "NOVA BUY/SELL", ...)` | Fires for ICT the same as ORB/PROS (Phase 1/2) | 2452–2453 |
| Legacy alertcondition | **None** — only `ORB BUY/SELL` and `PROS BUY/SELL` alertconditions exist; ICT has never had its own dedicated `alertcondition()` entry (documented in the original audit) | 2445 area |
| Webhook JSON | `alert('{"setup_type":"...","strategy_family":"ICT",...}')` for `ictBuySignal`/`ictSellSignal` transitions | Fires independently of the canonical/marker path, straight to the DONNA webhook | 2480–2484 |
| Bridge field | `ICT_STEP` (`_brIctStep`) | 0-6 numeric ladder reflecting how far the 6-step model progressed, **observation only** | 3326, 3403–3404 |
| Score contribution | `buyScore += ictLongReady ? ictWeight : 0`, `ictSMTLong ? 10 : 0` | `ictLongReady`/`ictShortReady` (not the final signal) feed the score model directly | 2058–2065 |
| Other consumers | `freshLongSetup`/`freshShortSetup`, `brainBullAgree`/`brainBearAgree`, `donnaFullICTLong`/`Short`, `donnaTier1/2Bull`/`Bear`, `eliteICTLong`/`Short`, `donnaConfScore` | All consume `ictLongReady`/`ictShortReady` (the readiness variable) or `step3LongElite`/`ShortElite` — **not** `ictBuySignal`/`ictSellSignal` — as inputs to the broader Donna scenario/confidence engine | 2140–2141, 1945–1951, 2900–2901, 2012–2013, 2852 |

### Python side

| Stage | Function/field | Behavior |
|---|---|---|
| Webhook ingestion | `engines/signals.py::normalize_payload()` | `strategy_family = 'ICT' if setup_type.startswith('ICT') else ...` — this is the exact function that turned the live `ICT_OB_FVG_ENTRY` payload into `strategy_family: 'ICT'` in the original incident |
| Discord message templating | `engines/signals.py`, `_ELITE_SETUPS = {'ICT_ELITE', 'ICT_ELITE_SHORT', 'ICT_ELITE_LONG'}` (line 16), used at line 252 | Produces a real, polished message body: *"ELITE ICT setup on {instrument}. Tier 1 — highest conviction HARVEY signal. {regime} regime."* — confirms ICT alerts **do** reach Discord/dashboard delivery, unblocked, informational |
| Discord message templating (dead branch) | `_ICT_SETUPS = {'ICT_BUY', 'ICT_SELL', 'HARVEY_BUY', 'HARVEY_SELL'}` (line 17), used at line 256 | These four literal strings **never match** any current Pine `setup_type` output (`ICT_ELITE`/`ICT_SMT_CONFIRMATION`/`ICT_OB_FVG_ENTRY`/`ICT_LIQUIDITY_SWEEP`) — this branch is dead code for any real, current alert. Legacy naming from the file's own predecessor ("HARVEY V4", per the Pine file's own header comment) |
| Execution governance | `services/execution.py::check_strategy_and_instrument_allowed()` | Rejects `strategy_family == 'ICT'` on every current profile — `STRATEGY_NOT_ALLOWED`, confirmed by 11 passing regression tests including the exact incident scenario |
| Bridge/reasoning parsing | `engines/reasoning.py` | Extracts `ICT_STEP` into `bridge_v2['ict_step']`, used **only** in one debug log line (`f' ict={bridge_v2["ict_step"]}'`) — no branching decision logic anywhere in `reasoning.py` keys off `strategy_family == 'ICT'` or any `setup_type` starting with `ICT_` |

**Adjacent finding (not ICT-specific, noted for awareness only, not touched):** `services/execution.py` documents a separate, already-known Pine-side data-quality bug: `analytics_score` is always `"0"` in real alert payloads because `buyScore`/`sellScore` get reassigned *after* the `alert()` calls fire in the script's execution order, so the webhook JSON captures stale state. Python already works around this (`_derive_signal_grade()` treats `0` as "no data," not "grade D"). This affects ORB/PROS webhook payloads too, not just ICT — flagged here only because it surfaced during this research; **not in scope, not changed.**

---

## PER-SETUP CLASSIFICATION

| Setup | Trigger | Continuation or reversal? | Overlaps PROS? | Context-only? | Can independently create BUY/SELL? | Recent live alerts? | Execution recognizes it? | Belongs under PROS? | Legacy/unused? |
|---|---|---|---|---|---|---|---|---|---|
| `ICT_ELITE` | Step 3 ready + elite (79% ext + 1m BOS simultaneously) + kill zone | Continuation | Conceptually (both are "continuation" plays) but mechanically distinct — HTF-sweep/BOS/OB/79%-extension vs. PROS's displacement/fib-retracement/close-through-reference | No | **Yes** — feeds `ictBuySignal`/`canonicalBuy` today | Same status as any ICT alert: theoretically yes (no execution gate blocks the *alert*, only the *trade*) | **No** — `STRATEGY_NOT_ALLOWED` on every profile | No — genuinely distinct detection mechanism | No — actively computed, feeds the score model and Donna scenario engine extensively |
| `ICT_SMT_CONFIRMATION` | Step 3 ready + cross-market SMT divergence | Continuation (confirmation layer) | No | No | Yes (via `ictBuySignal`) | Same | No | No | No |
| `ICT_OB_FVG_ENTRY` | Step 2 BOS + order block or FVG + dealing-range alignment | Continuation | No | No | Yes (via `ictBuySignal`) | **Yes — this is the exact setup_type from the documented incident** | No | No | No |
| `ICT_LIQUIDITY_SWEEP` | Fresh HTF sweep + BOS, before full step-3 readiness | Reversal-flavored (sweep-then-reverse), feeding into continuation once confirmed | No | No | Yes (via `ictBuySignal`) | Same | No | No | No |

None of the four are context-only in the way RP's Test/Sweep tiers are — each one, when it fires, is a *complete*, already-implemented signal boolean (`ictBuySignal`/`ictSellSignal`) that reaches `canonicalBuy`/`canonicalSell` today, exactly like ORB or PROS. The distinction from RP (Phase 3) is that RP had *no* existing promotion path before Phase 3 built one; ICT has had a full promotion path since before this entire engagement began — it was never absent, just never named as a formally-approved "strategy family" in any of the terminology corrections so far.

---

## RECOMMENDED CLASSIFICATION

**E. INDEPENDENT STRATEGY — NEEDS USER APPROVAL.**

Not A (PROS supporting component) or B (PROS setup subtype) — ICT's detection mechanism (kill-zone timing, HTF swing pivots, dealing-range premium/discount, liquidity-sweep-then-BOS, order-block/FVG entry, 79% extension, cross-market SMT) shares no code with PROS's mechanism (displacement leg, fib retracement zone, rejection, continuation-through-reference-level) — classifying it as a PROS subtype would misrepresent the actual code, the same mistake Phase 3 corrected for RP-as-strategy in the opposite direction.

Not C (context-only intelligence) — unlike RP's Test/Sweep tiers, `ictBuySignal`/`ictSellSignal` are complete, already-promotable signals reaching `canonicalBuy`/`canonicalSell` today; calling that "context-only" would understate what the code actually does.

Not D (legacy path to retire) — the six-step model is not dead or vestigial code; it is actively computed every bar and its readiness variables (`ictLongReady`/`ictShortReady`, `step3LongElite`/`ShortElite`) are genuinely consumed elsewhere (score model, `brainBullAgree`, `donnaFullICTLong`, `eliteICTLong`, confidence scoring) independent of whether `ictBuySignal`/`ictSellSignal` itself ever promotes to canonical. Retiring it outright would remove real, working functionality other engines depend on.

**E is correct because:** the code today behaves exactly like an approved third strategy family (full detection → signal → canonical → marker → alert → webhook), but the user's own stated architecture ("valid strategy families are ORB and PROS only") and the real historical incident both indicate this was never a deliberate design decision — it's an inherited, pre-existing condition nobody has explicitly ratified or corrected.

---

## MIGRATION RISK ASSESSMENT

**Low risk, if done as scoped:** `ictLongReady`/`ictShortReady` (the readiness variables, not the final signal) are what everything *except* `ictBuySignal`/`ictSellSignal` itself actually consumes (score model, `brainBullAgree`, `donnaFullICTLong`, `eliteICTLong`, `donnaConfScore`, `freshLongSetup`/`freshShortSetup`). Removing `ictBuySignal or ictSellSignal` from `buySignal`/`sellSignal`'s composite would **not** touch any of those — they would continue exactly as today. The only things that would stop working are: (1) ICT ever reaching `canonicalBuy`/`canonicalSell`/a chart marker/the canonical alert, and (2) the standalone `alert('...strategy_family":"ICT"...')` JSON webhook calls (2480–2484), which could be left in place (informational, already blocked from execution) or removed separately if the user wants Discord to stop receiving ICT alerts entirely.

**Medium consideration:** the `_ELITE_SETUPS` Discord-templating branch in `engines/signals.py` would keep firing for any ICT webhook alert still sent — a Python-side change, out of scope for the Pine-only work done so far, and not touched here.

---

## SAFEST NEXT STEPS (proposed, not started — awaiting review)

1. **Confirm the classification decision.** Options, mirroring the RP/Phase-3 precedent:
   - **(a) Demote to context/non-canonical** — remove `ictBuySignal`/`ictSellSignal` from `buySignal`/`sellSignal`'s OR-chain (2 words changed: `or ictBuySignal` / `or ictSellSignal` deleted from line 2286/2287) so ICT can never again reach `canonicalBuy`/`canonicalSell`, a marker, or the canonical alert — while every other ICT calculation (`ictLongReady`, scoring, Donna scenario contributions) continues unchanged, since none of those read `ictBuySignal`/`ictSellSignal` directly. Matches "valid strategy families are ORB and PROS only" going forward. Also decide whether to keep or remove the standalone ICT webhook `alert()` calls.
   - **(b) Formally approve ICT as a third strategy family** — update the stated architecture instead of the code, keep everything as-is, and separately decide whether to ever add `'ICT'` to `allowed_strategies` in `donna_settings.json` (a deliberate, explicit execution decision, not a side effect of a Pine change).
   - **(c) Retire/simplify** — only if the user judges the six-step model genuinely obsolete; not recommended given it's actively feeding other engines today.
2. Whichever option is chosen, implement it as its own isolated, reviewed commit — not bundled with anything else, per the established pattern for this engagement.
3. No code has been changed for this part of the report — awaiting your decision before touching `buySignal`/`sellSignal`, the ICT webhook calls, or `donna_settings.json`.
