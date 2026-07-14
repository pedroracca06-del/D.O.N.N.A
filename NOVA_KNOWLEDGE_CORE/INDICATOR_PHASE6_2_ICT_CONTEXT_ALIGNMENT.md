# NOVA EXECUTION V1 — Phase 6.2: ICT Aligned as Context-Only Intelligence

**Status:** Implemented. `indicators/nova_execution_v1.pine` only. Verified with TradingView's stateless server-side compile-check endpoint only — no CDP/live-chart interaction, live cloud script untouched.

## Why ICT was removed from canonical trade promotion

Per the Phase 6.1 audit and the user's decision: **ICT is not an approved NOVA strategy family. The approved families are ORB and PROS only.** ICT already caused a real, documented incident before this engagement (a live `ICT_OB_FVG_ENTRY` alert executed two real paper trades because the webhook path used to bypass execution governance — since fixed at the execution layer). This phase closes the remaining gap: the Pine/chart layer still treated ICT as a peer of ORB/PROS, which this phase corrects, without deleting any of ICT's underlying intelligence.

## `buySignal`/`sellSignal` — before and after

```pine
// before (original, pre-Phase-1, unchanged until this phase):
buySignal  := orbBuySignal  or ictBuySignal  or prosBuySignal
sellSignal := orbSellSignal or ictSellSignal or prosSellSignal

// after (Phase 6.2):
buySignal  := orbBuySignal  or prosBuySignal
sellSignal := orbSellSignal or prosSellSignal
```

`ictBuySignal`/`ictSellSignal` and everything upstream of them (`ictLongReady`/`ictShortReady`, the full 6-step model, `step3LongElite`/`ShortElite`, `ictSMTLong`/`Short`, kill-zone/HTF-sweep/BOS/OB-FVG/dealing-range calculations) are **completely unchanged** — they still compute every bar. Only their promotion into `buySignal`/`sellSignal` was removed.

## Proof that `canonicalStrategy`/`canonicalSetup` can never return ICT (no additional code change needed)

```pine
canonicalStrategy = (canonicalBuy or canonicalSell) ? strategy_family : "NONE"
canonicalBuy  = buySignal  and not canonicalSignalConflict   // buySignal now excludes ICT
canonicalSell = sellSignal and not canonicalSignalConflict

strategy_family =
     prosBuySignal or prosSellSignal                      ? "PROS" :   // checked FIRST
     orbBuySignal or orbSellSignal                        ? "ORB"  :   // checked SECOND
     ictBuySignal and (step3LongElite or step3ShortElite) ? "ICT"  :   // only reachable after PROS/ORB both fail
     ...
```

Whenever `canonicalBuy`/`canonicalSell` is true, it is because `orbBuySignal` or `prosBuySignal` fired (the only two remaining OR-branches). `strategy_family`'s own ternary checks the PROS branch first, the ORB branch second, and only reaches the ICT branch after **both** have failed — but if `orbBuySignal`/`prosBuySignal` is what made `canonicalBuy` true, one of those two branches will already have matched. **This is a structural guarantee, not a coincidence of current values**: `canonicalStrategy` cannot return `"ICT"` for as long as `strategy_family` keeps PROS/ORB ahead of ICT in its own priority chain (unchanged, original code). Same logic applies identically to `canonicalSetup`/`setup_type`. No edit to `strategy_family`, `setup_type`, `canonicalStrategy`, or `canonicalSetup` was necessary or made — verified via `git diff`, zero lines in that block changed.

`canonicalStrategy` now only ever returns `"ORB"`, `"PROS"`, or `"NONE"`, exactly as required. `canonicalSetup` only ever returns an ORB or PROS setup value, or `"NONE"`.

## Phase 2 markers

Unaffected by construction — they read `canonicalBuy`/`canonicalSell`/`canonicalBuyNew`/`canonicalSellNew`, all of which now structurally exclude ICT. No marker code was touched. `canonicalMarkerStrategyText`'s four ICT-mapping branches (`ICT_ELITE`→"ICT ELITE CONTINUATION", etc.) are now **unreachable** (since `canonicalSetup` can never equal those values) but were left in place rather than deleted — harmless dead branches, kept for reference in case a future, separately-approved ICT strategy design reuses this exact mapping.

## ICT alert path audit (Part 3)

| Alert | Fires on | Classification | Disposition |
|---|---|---|---|
| `alertcondition(canonicalBuyNew/SellNew, "NOVA BUY"/"NOVA SELL", ...)` | Canonical state, now ORB/PROS only | **A. Context/diagnostic** (was never ICT-dedicated) | Kept. Description string updated: `"(ORB/ICT/PROS)"` → `"(ORB/PROS)"` for accuracy. Cannot fire from ICT alone, before or after this phase's structural fix. |
| Standalone ICT webhook `alert()` — `if ictBuySignal and not ictBuySignal[1]: alert('{"...","strategy_family":"ICT",...}')` (and SELL mirror) | `ictBuySignal`/`ictSellSignal` directly, independent of `buySignal`/canonical state | **B. Legacy execution-capable alert** — this is the *exact* payload shape (`strategy_family":"ICT"`) from the documented pre-engagement incident | **Disabled** (commented out, not deleted) — per instruction, any ICT alert capable of reaching the production webhook as a trade-shaped signal must be disabled or made observation-only. Commenting out (rather than deleting) preserves the code and its dependency (`_j_ict_tier`) for a possible future, separately-approved re-enablement. |
| `_j_ict_tier` (helper var for the now-disabled alert) | N/A | **C. Now-unused** (was B's dependency) | Left in place, harmless — confirmed no other alert reads it (ORB/PROS webhook alerts use a hardcoded `"tier":"2"` literal, never `_j_ict_tier`) |
| ORB/PROS webhook `alert()` calls | `orbBuySignal`/`orbSellSignal`/`prosBuySignal`/`prosSellSignal` | **A. Context/diagnostic**, unrelated to ICT | Untouched — confirmed their `setup_type` string is always ORB/PROS-specific at the moment they fire (same priority-ordering proof as above), never accidentally an ICT value |
| No `alertcondition()` was ever dedicated to ICT | — | N/A | Confirmed absent in the original audit; nothing to change here |

No webhook execution code (`main.py`, `services/execution.py`) was touched — the disable happened entirely on the Pine side, which is the only side capable of *sending* this specific alert in the first place.

## ICT intelligence preserved (Part 4)

All of the following remain exactly as before, still computed every bar, still feeding the score model and Donna scenario/confidence engine:

- Kill-zone/session context (`isKillZone`, `killZoneText`)
- HTF liquidity sweep (`sweep1hHigh/Low`, `sweep4hHigh/Low`, `htfSweepHigh/Low`, `sweepHighFresh/LowFresh`)
- BOS (`htf5mBullBOS/BearBOS`, `htf15mBullBOS/BearBOS`, `step2BullActive/BearActive`)
- OB/FVG context (`ictEntryZoneLong/Short`, `atHTFBullOB/BearOB`, `atBullFVG/BearFVG`)
- Extension context (`step3LongReady/ShortReady`, `step3LongElite/ShortElite`, `at79Bull/Bear`)
- SMT confirmation (`ictSMTLong/Short`, `bullishSMT/bearishSMT`)
- Directional agreement (`brainBullAgree/BearAgree`, consumed from `ictLongReady/ShortReady`)
- Confidence contribution (`donnaConfScore += ictLongReady or ictShortReady ? 12.0 : 0.0`, `step3LongElite or step3ShortElite ? 15.0 : 0.0`, unchanged)
- Score contribution (`buyScore += ictLongReady ? ictWeight : 0`, `ictSMTLong ? 10 : 0`, unchanged)

**No score, grade, or confidence value was moved, boosted, or reassigned to ORB or PROS as a result of this change** — the instruction not to "silently increase ORB or PROS scores by moving ICT signal eligibility elsewhere" was followed literally: `ictWeight`, `donnaConfScore`'s ICT terms, and every other ICT-derived contribution are numerically identical before and after this phase. Only the *signal-promotion* step (`ictBuySignal`/`ictSellSignal` → `buySignal`/`sellSignal`) was removed.

## Dashboard and bridge audit (Part 5)

| Location | What it shows | Classification | Action |
|---|---|---|---|
| `canonicalStrategy`/`canonicalSetup` | Feeds Phase 2 marker context, would-be dashboard/bridge export | **Actionable strategy state** | Fixed structurally (see proof above) — can never show ICT again |
| `strategy_family`/`setup_type` (raw) | Only ever read by `canonicalStrategy`/`canonicalSetup` and the ORB/PROS webhook alerts (which never reach the ICT branch at fire-time) | **Diagnostic/internal** — not independently displayed anywhere | Untouched, not exported raw anywhere a user or Python parser would see it as actionable |
| `signalReason` (`var string`, "CONT ELITE LONG"/"CONT LONG" etc. for ICT) | **Found to be entirely unused** — assigned throughout the file but never read by any table cell, plot, or bridge export, for *any* strategy (not just ICT) | **Legacy/dead**, pre-existing, unrelated to this phase | Left untouched — out of scope (general dead-code cleanup, not an ICT-specific promotion issue); noted here for future reference |
| `plot(ictBuySignal/SellSignal ? 1 : 0, "ICT_BUY"/"ICT_SELL", display=display.none)` | Hidden numeric series, for external tools (e.g. MCP `data_get_study_values`) — not the NOVA BRIDGE text table | **Diagnostic** — no consumer treats this as a trade instruction; `reasoning.py`'s `parse_nova_tables()` reads only the bottom-left text table, never these hidden plots | Left untouched, correctly diagnostic-only |
| **`CMD` bridge field (`dashCommandText` = `donnaCommand`)** | `donnaCommand`'s own ternary includes `eliteICTLong and buyScore >= donnaThreshBuy ? "BUY"` / `eliteICTShort and sellScore >= donnaThreshSell ? "SELL"` (lines ~2967–2968), where `eliteICTLong = step3LongElite and brainBullAgree` — **entirely independent of `buySignal`/`canonicalBuy`** | **Directly exposes ICT as executable** — confirmed, documented per instruction rather than silently fixed | **Not changed.** This is the same class of finding as Phase 1's original "CMD can say BUY while canonicalBuy is false" observation, now confirmed to have an ICT-specific instance: `CMD` can still say `"BUY"`/`"SELL"` driven purely by ICT's elite tier, even after this phase's fix. `CMD`/`SYS_STATE` remain deferred to a dedicated future bridge-cutover phase (per the Phase 1 precedent) — flagging this compatibility risk explicitly rather than touching the Python parser or the legacy bridge field in this Pine-only phase. |
| `SYS_STATE` bridge field (`donnaScenario`) | Can show `"ELITE CONT LONG"`/`"ELITE CONT SHORT"` (line ~2018–2019) when `eliteICTLong`/`eliteICTShort` fires | Same as `CMD` — descriptive scenario text, not gated by `canonicalBuy` | Not changed, same reasoning |

**No dashboard table cell, bridge row, or marker anywhere shows `"ICT | BUY"`, `"ICT | SELL"`, or `"ICT | EXECUTION_READY"`** — confirmed by the structural proof above for the canonical layer, and by direct inspection for `CMD`/`SYS_STATE` (which show free-text scenario descriptions, not a `"STRATEGY | DIRECTION | STATE"` triple, so they were never in that literal shape to begin with — but are flagged above for the underlying BUY/SELL-driven-by-ICT risk they do carry).

## Regression verification (Part 6, reasoned against the committed code)

1. **ORB BUY** → `orbBuySignal` unchanged → `buySignal` (still includes `orbBuySignal`) → `canonicalBuy` → `canonicalBuyNew` → `plotshape` → `alertcondition(canonicalBuyNew, "NOVA BUY", ...)`. Confirmed intact — `orbBuySignal`'s own definition and every gate feeding it are byte-unchanged.
2. **ORB SELL** — mirrored, confirmed intact.
3. **PROS BUY** — `prosBuySignal` unchanged, same path, confirmed intact.
4. **PROS SELL** — mirrored, confirmed intact.
5. **ICT-only BUY**: `ictBuySignal` can still be `true` (unchanged definition) → `buySignal = orbBuySignal or prosBuySignal` — if both are `false`, `buySignal` is `false` regardless of `ictBuySignal` → `canonicalBuy` is `false` → `canonicalBuyNew` is `false` → no `plotshape` fires → no `alertcondition` fires. Confirmed by the Part 1 diff itself (ICT literally removed from the OR-chain).
6. **ICT-only SELL** — mirrored, confirmed.
7. **ICT context remains available**: confirmed in Part 4 above — every listed calculation is untouched and still feeds diagnostics, scoring, and the (deferred) `CMD`/`SYS_STATE`/bridge context fields.
8. **No strategy family named ICT reaches execution readiness**: confirmed — `canonicalStrategy` can never be `"ICT"` (structural proof above), and the Python-side execution governance gate independently already rejects `strategy_family == "ICT"` on every profile (Phase 6.1 finding, unchanged).
9. **Rejection labels remain context-only**: confirmed — Phase 5/6/6.1 rejection code (`asiaHighReject` etc.) was not touched by this phase at all; no diff overlap.
10. **Source-specific rejection formulas remain unchanged**: confirmed via diff — zero lines in the Phase 6/6.1 rejection block changed.
11. **Break & Retest remains ORB**: confirmed — `orbValidBreakBull/Bear`, `orbRetestBull/Bear`, and all ORB entry-type logic untouched.
12. **No execution/broker code changes**: confirmed — only `indicators/nova_execution_v1.pine` was modified this phase.

## Known future option

ICT may become an approved NOVA strategy family only through a separate, explicit design decision — the same standard already applied to RP (Phase 3/3-correction). This phase does not foreclose that possibility; it only removes ICT's *unreviewed*, inherited promotion path. If ICT is ever formally approved, the disabled webhook `alert()` calls, the four now-unreachable `canonicalMarkerStrategyText` branches, and the OR-chain in `buySignal`/`sellSignal` are all still present (commented or structurally inert, not deleted) and could be re-enabled deliberately at that time.
