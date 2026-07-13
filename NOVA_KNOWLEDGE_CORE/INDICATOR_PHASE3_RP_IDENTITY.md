# NOVA EXECUTION V1 — Phase 3: RP Liquidity-Rejection Identity

**Status:** Implemented in `indicators/nova_execution_v1.pine` only. Verified with TradingView's stateless server-side compile-check endpoint only (0 errors, 0 warnings) — no CDP/live-chart interaction, live cloud script untouched, no `pine new`/`set`/`save`/`compile` run against the editor.

## Problem this closes

Per the audit's root cause #1 ("RP does not have a proper Pine strategy identity"), `highSweepReject`/`lowSweepReject` fed only `strategy_family`'s generic `"REVERSAL"` bucket and never reached `canonicalBuy`/`canonicalSell` — an RP-style rejection at PDH/PSH/PWH/PDL/PSL/PWL could raise `donnaCommand` to `"BUY"`/`"SELL"` but could never produce a canonical signal, a chart marker, or a canonical alert. Phase 3 gives RP a proper identity and its own promotion gate, then wires that gate into `canonicalBuy`/`canonicalSell` alongside ORB/ICT/PROS.

## Terminology used throughout (per user correction, locked in)

RP only — never "RAP." Break & Retest is strictly an ORB setup, never RP. RP's four approved setup types: **Rejection, Bounce, Failed Breakout, Sweep & Reclaim.**

## What got real detection this phase, and why

Per `nova_knowledge_core/ORB_RP/reaction_setups.md`: *"Difference from Bounce: Mechanically identical, mirrored — rejection is at highs (short), bounce is at lows (long). Same confirmation logic, same parameters."*

Because the knowledge base itself says Bounce and Rejection are the exact same mechanism mirrored by direction, and the exact mechanism (`lowSweepReject`/`highSweepReject`, lines 963–964, unchanged) already exists for both directions, Phase 3 wires up **both** under their historically correct names — not just Rejection — since doing so required zero new detection logic, only correct naming. This is consistent with "focus first on RP REJECTION" as the primary new deliverable, with BOUNCE following at no extra detection cost.

**Failed Breakout and Sweep & Reclaim are not wired to real detection this phase.** No non-ORB mechanism for either already exists in this script (ORB has its own sweep/reclaim/failure tracking, but that's ORB-scoped and off-limits to reuse for RP per "do not merge ORB and RP"). Building new detection for either would be inventing criteria, explicitly out of scope ("use the rejection logic and thresholds already present... do not invent looser criteria"). They exist as valid `setup_type` category names for forward compatibility but never fire.

## Exact variables added (`indicators/nova_execution_v1.pine`, new "PHASE 3" block inserted immediately before the Phase 1 canonical block, so `canonicalBuy`/`canonicalSell` can reference `rpBuySignal`/`rpSellSignal`)

| Variable | Definition | Wraps / derived from |
|---|---|---|
| `rpLiqSourceBull` / `rpLiqSourceBear` | PWL/PDL/PSL or PWH/PDH/PSH by existing sweep/near tier, else `"NONE"` | Existing `sweptPxx`/`nearPxx` booleans (922–927, 915–920) — unchanged |
| `rpInteractionBull` / `rpInteractionBear` | `"SWEEP_REJECT"` if the level was truly swept, `"NEAR_REJECT"` if only approached, else `"NONE"` | Same existing `sweptPxx`/`nearPxx` booleans |
| `rpContextBull` / `rpContextBear` | Tier-1 "rejection context detected" — near or swept, wick pattern not yet confirmed | Existing `nearPxx`/`sweptPxx` only |
| `rpCandidateBull` / `rpCandidateBear` | Tier-2 "RP candidate" — the full wick-rejection pattern confirmed this bar | `= lowSweepReject` / `= highSweepReject` verbatim (963–964), unchanged |
| `rpSetupTypeBull` / `rpSetupTypeBear` | `"BOUNCE"` / `"REJECTION"` when the candidate fires, else `""` | Derived from `rpCandidateBull`/`Bear` |
| `rpCandidateBullBar`/`Bear`, `rpCandidateBullFresh`/`Bear` | A 3-bar "freshness" window, reset on `newDay` | New bookkeeping, **display continuity only** — mirrors the existing `prosContStickyBull`/`Bear` pattern already in this file. Does **not** gate promotion; `rpBuySignal`/`rpSellSignal` still fire strictly on the same bar as the candidate. |
| `rpReadyBull` / `rpReadyBear` | Tier-3/4 promotion gate | `= rpCandidateBull and localBullBias and not nearLiquidityHigh` — **verbatim** the existing `liqLongReady` formula (line 1784: `lowSweepReject and localBullBias and not nearLiquidityHigh`). Confirmed identical via grep, not re-derived. `rpReadyBear` mirrors `liqShortReady` (1785) the same way. |
| `rpBuySignal` / `rpSellSignal` | `rpReadyBull and canSmartBuy` / `rpReadyBear and canSmartSell` | `canSmartBuy`/`canSmartSell` — the existing 20-bar cooldown (1771–1772), unchanged, shared with ORB/ICT/PROS rather than a new clock |
| `rpBlockReasonBull` / `rpBlockReasonBear` | `"NO_BULL_BIAS"` / `"NEAR_OVERHEAD_LIQUIDITY"` / `"COOLDOWN"` / `""`, only while a candidate is fresh and not yet promoted | Names the exact existing gate variables that blocked promotion |
| `rpStateBull` / `rpStateBear` | Five-tier ladder: `"NONE"` → `"RP_CONTEXT"` → `"RP_HEADS_UP"` → `"RP_READY"` → `"RP_BUY"`/`"RP_SELL"` | Composite of all of the above |

**Mutual exclusivity, proven by construction (no runtime guard needed):** `lowSweepReject` requires `close > open`; `highSweepReject` requires `close < open`. A single bar's close is either greater than, less than, or equal to its open — never both greater and less — so `rpCandidateBull` and `rpCandidateBear` can never both be true on the same bar, and therefore neither can `rpBuySignal`/`rpSellSignal`. This is a stronger, simpler guarantee than `canonicalSignalConflict`'s guard (which handles the ORB/ICT/PROS/RP cross-family case, where independent evaluators genuinely could disagree).

## Canonical wiring (Phase 1 constructs, extended — not replaced)

```pine
canonicalSignalConflict = (buySignal or rpBuySignal) and (sellSignal or rpSellSignal)
canonicalBuy  = (buySignal  or rpBuySignal)  and not canonicalSignalConflict
canonicalSell = (sellSignal or rpSellSignal) and not canonicalSignalConflict
```

**Important correction made during implementation:** the original Phase 1 conflict guard was `buySignal and sellSignal`. Once RP is OR'd in, that literal form would miss a real cross-family case — e.g. `buySignal` (ORB/ICT/PROS long) and `rpSellSignal` (RP short) both true on the same bar, which is structurally possible since they're independent evaluators. The guard was generalized to `(buySignal or rpBuySignal) and (sellSignal or rpSellSignal)`, which is mathematically equivalent to the Phase 1 version whenever RP hasn't fired (no behavior change to any case Phase 1 already covered) and correctly extends to the new case. `canonicalBuy`/`canonicalSell` mutual exclusivity is preserved by the same proof technique as Phase 1.

`buySignal`/`sellSignal` **themselves are untouched** — still exactly `orbBuySignal or ictBuySignal or prosBuySignal` (and the SELL mirror). Only `canonicalBuy`/`canonicalSell`, Phase 1's own construct, was extended — the same way ORB/ICT/PROS already coexist as independent OR-ed branches.

`canonicalStrategy`/`canonicalSetup` now report `"RP"` / `"RP_BOUNCE"` or `"RP_REJECTION"` **only when `canonicalBuy`/`canonicalSell` became true solely because RP fired** (`buySignal`/`sellSignal` both false) — when ORB/ICT/PROS fired, display is byte-identical to before Phase 3. `canonicalLiquiditySource`/`canonicalInteraction` were extended with a new `canonicalStrategy == "RP"` branch, following the exact same pattern Phase 1 already established for `canonicalStrategy == "ORB"`. `canonicalGrade` needed no change — it was already purely score-based (`buyGrade`/`sellGrade`), correct for any family.

The Phase 2 marker's context-text mapping (`canonicalMarkerStrategyText`) gained two new branches: `"RP_BOUNCE"` → `"RP BOUNCE"`, `"RP_REJECTION"` → `"RP REJECTION"`. No other Phase 2 code needed to change — the liquidity-source second line was already generic over `canonicalLiquiditySource`.

## Known limitation, confirmed during implementation

The "RP | SELL | ASIA HIGH | SWEEP_REJECT" example from the original request is not reachable today. `highSweepReject`/`lowSweepReject` only check `nearPSH/nearPDH/nearPWH/sweptPSH/sweptPDH/sweptPWH` (and the low-side mirror) — Asia High/Low and London High/Low are not part of that existing gate's inputs. Adding them would expand the detector's own criteria (more trigger conditions than it has today), which is exactly what "do not invent looser criteria" rules out for this phase. `rpLiqSourceBull`/`Bear` can therefore only ever report PSH/PDH/PWH or PSL/PDL/PWL, never Asia/London — documented rather than silently worked around, same as Phase 2's "ORB BREAK & RETEST" limitation.

`rpStateBull`/`rpStateBear` and `rpBlockReasonBull`/`rpBlockReasonBear` are computed and correctly available now, but **not yet exposed** to the NOVA BRIDGE table or the on-chart dashboard — those are Phase 5 and Phase 6 territory respectively, per the approved phase plan. `canonicalStrategy`/`canonicalSetup`/`canonicalLiquiditySource`/`canonicalInteraction`/`canonicalGrade` (which already flow into the Phase 2 marker) are the only RP-derived fields visible on the chart as of this phase.

## Confirmed unchanged

- `buySignal`/`sellSignal`, `orbBuySignal`/`orbSellSignal`/`ictBuySignal`/`ictSellSignal`/`prosBuySignal`/`prosSellSignal`, all score/grade thresholds, session/instrument gates: **byte-identical** to Phase 2 — verified via `diff` against commit `08930a3` for every line before the new Phase 3 block (exit code 0, zero differences).
- `liqLongReady`/`liqShortReady` (1784–1785) themselves are untouched; `rpReadyBull`/`rpReadyBear` independently reuse the identical formula rather than modifying or calling them, so nothing that already consumed `liqLongReady`/`liqShortReady` (the score model, `donnaLiqReversalLong`/`Short`) is affected.
- `CMD`/`SYS_STATE` bridge fields and `engines/reasoning.py` — not touched. `donnaCommand`/`donnaScenario` still don't know about RP; that cutover remains explicitly deferred to Phase 5, same precedent as Phase 1.
- No execution/broker file was modified — only `indicators/nova_execution_v1.pine` and this documentation file changed.
- ORB and IB logic and visibility — untouched.

## Test verification

- All 22 new variables confirmed declared exactly once (`grep -c`), no name collisions with any existing identifier in the file.
- Declaration order traced and confirmed: every new variable is used only after its own definition point, both within the new block and in the (extended) Phase 1 canonical block and Phase 2 marker block downstream.
- `rpReadyBull`/`rpReadyBear` confirmed **byte-identical in logic** to `liqLongReady`/`liqShortReady` via direct grep comparison of both formulas.
- `git diff` against commit `08930a3` confirmed zero changes to any line before the new Phase 3 insertion point — proving no threshold, gate, or strategy-eligibility change anywhere in the pre-existing code.
- TradingView server-side compile check: 0 errors, 0 warnings.
