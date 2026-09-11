# NOVA EXECUTION V1 — Phase 3 Correction: Rejection Detection Is Not a Strategy

**Status:** Corrects a strategy-architecture mistake introduced by the original Phase 3 commit. `indicators/nova_execution_v1.pine` only. Verified with TradingView's stateless server-side compile-check endpoint only — no CDP/live-chart interaction, live cloud script untouched, no `pine new`/`set`/`save`/`compile` run against the editor.

## What was wrong

The original Phase 3 commit (`ac07327`, "Add RP liquidity-rejection identity, wire into canonical signal state") introduced RP as a **standalone third strategy family** alongside ORB and PROS — a `canonicalStrategy == "RP"` branch, its own promotion gate (`rpBuySignal`/`rpSellSignal`), and its own path into `canonicalBuy`/`canonicalSell`.

This was an architecture mistake. **RP is not a NOVA strategy.** The valid strategy families are **ORB** and **PROS** only. Liquidity rejection is a detection/setup framework that can support those two strategies (or remain informational context) — it is not a third family that independently produces BUY/SELL signals of its own.

## What was reverted

Commit `ac07327` was reverted cleanly with `git revert ac07327` (new commit `0ca4cd8`, history preserved, nothing rewritten). Verified before reverting:
- `ac07327` was `HEAD` — no later commit existed, so nothing depended on it.
- Every RP-related identifier in the entire repository (`rpBuySignal`, `rpSellSignal`, `rpCandidateBull`/`Bear`, `rpReadyBull`/`Bear`, `rpStateBull`/`Bear`, `rpLiqSourceBull`/`Bear`, `rpInteractionBull`/`Bear`, `RP_BOUNCE`, `RP_REJECTION`, `INDICATOR_PHASE3_RP_IDENTITY.md`) existed only inside the two files that commit touched (`indicators/nova_execution_v1.pine` and `nova_knowledge_core/INDICATOR_PHASE3_RP_IDENTITY.md`) — confirmed by a repo-wide grep before reverting.

After the revert, `indicators/nova_execution_v1.pine` is confirmed **byte-identical** (compared as git blobs, ignoring the working tree's CRLF conversion) to commit `08930a3` (Phase 2, "Add canonical buy sell chart markers"). `nova_knowledge_core/INDICATOR_PHASE3_RP_IDENTITY.md` was deleted by the revert.

`canonicalBuy`/`canonicalSell` are back to exactly:

```pine
canonicalSignalConflict = buySignal and sellSignal
canonicalBuy  = buySignal  and not canonicalSignalConflict
canonicalSell = sellSignal and not canonicalSignalConflict
```

Phase 2 is fully intact and unmodified: `canonicalBuyNew`/`canonicalSellNew`, the `plotshape()` BUY/SELL markers, the optional context `label.new()`, the canonical `alertcondition()` mapping, and the `showSignals`/`showSignalContext`/`signalLabelSize` inputs are all exactly as committed in `08930a3`.

## Valid strategy families

**ORB:**
- Break & Retest (break out of the ORB zone → retest the ORB boundary → holds → continuation)
- Edge Rejection
- Midpoint Rejection
- ORB liquidity rejection
- Any other setup specifically created by the ORB range

**PROS:**
- Displacement
- Retracement
- Defense
- Continuation confirmation
- Continuation trade

ORB and IB remain separate structures, as established from the original audit — not merged, not touched by this correction.

## Rejection detection is a supporting layer, not a strategy

The underlying detection booleans were never removed — they live in the original, untouched pre-Phase-1 region of the script and were unaffected by either the Phase 3 mistake or this correction:

- `highSweepReject` (line 971), `lowSweepReject` (line 972) — the wick-rejection-at-a-swept-or-approached-level detectors.
- The existing ORB rejection logic (`orbPassMidRejectBull`/`Bear`, `orbPassLiqRejectBull`/`Bear`, `orbPassEdgeRejectBull`/`Bear`, `orbLiqRejectBull`/`Bear`) — untouched, already correctly ORB-owned.
- The existing liquidity context calculations (`nearPSH`/`PDH`/`PWH`/`PSL`/`PDL`/`PWL`, `sweptPSH`/`PDH`/`PWH`/`PSL`/`PDL`/`PWL`, `orbSweepTierBull`/`Bear`, `orbAsiaHighSweepNow`/`orbAsiaLowSweepNow`) — untouched.

Going forward, this collection of existing, unchanged detectors should be thought of as a **Liquidity Rejection Engine** (equivalently: **Rejection Detection Layer**) — not a strategy. Its job:

1. Identify a liquidity interaction (touch, sweep, reclaim, rejection).
2. Name the liquidity source involved.
3. Classify the interaction type.
4. Provide context.
5. **Feed an approved ORB setup** when the structure detected is ORB-owned (already the case today — `orbLiqRejectBull`/`Bear` and the `orbPassLiqRejectBull`/`Bear` gate already do exactly this, unchanged).
6. **Provide context to PROS** where relevant (not currently wired — no change made here, noted as a possible future direction only).
7. **Remain informational/context-only** when no approved strategy setup is present — it must not, by itself, create a new strategy family or produce a canonical BUY/SELL signal.

Any future proposal to promote a piece of this layer into a genuine new setup requires its own explicit design and approval — it does not happen implicitly by connecting existing booleans to `canonicalBuy`/`canonicalSell`, which is exactly the mistake this correction reverses.

## Confirmed

- `ac07327` was reverted via `git revert` (commit `0ca4cd8`) — not `git reset`, history not rewritten.
- `indicators/nova_execution_v1.pine` confirmed byte-identical to commit `08930a3` (Phase 2).
- Zero RP-related identifiers remain anywhere in the repository (`indicators/`, and a full-repo grep across `.py`/`.pine`/`.md`/`.js`).
- Phase 2 BUY/SELL markers, canonical alerts, and inputs are fully intact.
- No threshold, grade, session gate, or instrument gate was changed by either the original Phase 3 commit's revert or this documentation correction.
- No new strategy eligibility exists — `canonicalBuy`/`canonicalSell` only ever reflect ORB/ICT/PROS, exactly as Phase 1 and Phase 2 left them.
- No execution/broker file was touched at any point in this correction.
- The live TradingView cloud script was not touched — verification used only the stateless compile-check endpoint.
