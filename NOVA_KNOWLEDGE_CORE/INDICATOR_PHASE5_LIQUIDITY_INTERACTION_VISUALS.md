# NOVA EXECUTION V1 — Phase 5: Liquidity Interaction Visualization

**Status:** Visual context phase only — not a signal, execution, or strategy phase. `indicators/nova_execution_v1.pine` only. Verified with TradingView's stateless server-side compile-check endpoint only — no CDP/live-chart interaction, live cloud script untouched.

## PART 1 — AUDIT OF EXISTING INTERACTION LOGIC (pre-Phase-5 state)

| Concept | Exact variable(s) | Computed at | Used by | Currently visible? |
|---|---|---|---|---|
| Near a level (generic) | `f_near(level, thresh)` (helper, line 693); `nearPSH`/`nearPDH`/`nearPWH`/`nearPSL`/`nearPDL`/`nearPWL` (lines 975–980) | `liqThresh = atrValue * 0.25` (line 691) | Liquidity Engine V2 score model, `liqStateText`/`liqClusterText` (dashboard text), `f_liqLevel`'s Phase 4 emphasis calls | Only as dashboard text (`dashLiqText`) — never as an on-chart label |
| Swept (high/low pierced then closed back through) | `f_swept_high(level)`/`f_swept_low(level)` (helper, lines 696–700); `sweptPSH`/`sweptPDH`/`sweptPWH`/`sweptPSL`/`sweptPDL`/`sweptPWL` (lines 982–987) | Same block | Score model, `sweepHighLabel`/`sweepLowLabel` (dashboard text only), `orbExtLiqTierBull`/`Bear` (ORB-scoped) | Same — dashboard text only |
| Accepted beyond a level | `acceptedAbovePSH`/`PDH`/`PWH`, `acceptedBelowPSL`/`PDL`/`PWL` (lines 989–994) | Same block | `highBreakHold`/`lowBreakHold`, cluster/tier calculations | Not visualized at all |
| Wick rejection (generic, symbol-agnostic) | `highSweepReject`/`lowSweepReject` (lines 1023–1024) | Combines `nearPxx`/`sweptPxx` (PSH/PDH/PWH or PSL/PDL/PWL only — **not** Asia/London/Overnight) with a wick/body ratio and close-through-level condition | `liqLongReady`/`liqShortReady`, `donnaLiqReversalLong`/`Short`, score model | Not visualized — this is the exact boolean the Phase 3 correction discussed; still context-only, still not level-attributed on its own |
| Break-hold (acceptance confirmed) | `highBreakHold`/`lowBreakHold` (lines 1026–1027) | Same block | Score model only | Not visualized |
| Reclaim (multi-bar, tiered) | `orbReclaimBullBars`/`orbReclaimBearBars`, `orbSweepTierBull`/`Bear` | ORB-scoped — requires `orbLive` (ES-only), part of the ORB engine (lines 796–892) | ORB score model, `orbCtxText` | ORB-only display (`O_TYPE`/`O_REJ_Q` bridge rows, `orbCtxText` dashboard string) — **no generic (non-ORB) reclaim concept exists anywhere in this script** |
| Failed acceptance / failed auction | `orbFailedAcceptBull`/`Bear` (ORB-scoped), `failedAuctionBull`/`Bear` (generic, lines further down, keyed to ORB-break or PDH/PSH acceptance specifically) | ORB-scoped and ORB/PDH/PSH-break-scoped respectively | Score model, `donnaScenario` | Dashboard text only |

**Key finding, consistent with the Phase 3 correction:** `highSweepReject`/`lowSweepReject` do not check Asia High/Low, London High/Low, or Overnight High/Low at all — only PSH/PDH/PWH (highs) and PSL/PDL/PWL (lows). This is unchanged in this phase (expanding those detectors' own criteria would be new/looser detection logic, explicitly out of scope). **Reclaim has no non-ORB equivalent anywhere in the script.** Both facts directly shape what Part 2 below can honestly support.

## PART 2 — WHAT CAN BE SHOWN, PER LEVEL (no new interaction logic invented)

| Level | TEST (near) | SWEEP | REJECTION | RECLAIM |
|---|---|---|---|---|
| Asia High/Low | ✅ `f_near` | ✅ `f_swept_high`/`low` | ❌ not detected by any existing non-ORB boolean | ❌ no non-ORB mechanism exists |
| London High/Low | ✅ | ✅ | ❌ | ❌ |
| Overnight High/Low | ✅ | ✅ | ❌ | ❌ |
| PDH/PDL | ✅ (`nearPDH`/`PDL`) | ✅ (`sweptPDH`/`PDL`) | ✅ — `highSweepReject`/`lowSweepReject` attributed to PDH/PDL specifically via `(nearPDH or sweptPDH)` / `(nearPDL or sweptPDL)` | ❌ |
| PWH/PWL | ✅ (`nearPWH`/`PWL`) | ✅ (`sweptPWH`/`PWL`) | ✅ — same attribution pattern | ❌ |

**Consequence for the acceptance example:** the recent MNQ Asia High interaction can correctly display `ASIA HIGH SWEEP` or `ASIA HIGH TEST` (both reachable with existing logic), but **not** `ASIA HIGH REJECTION` — that specific word requires the wick-rejection pattern, which `highSweepReject` doesn't check for Asia at all. This mirrors the exact limitation already documented in Phase 3 and Phase 4; not a new gap introduced here. `PDH TEST`, `PDL SWEEP` (or `RECLAIM`, if it existed), `PWH REJECTION` are handled per the table — `RECLAIM` specifically is never shown anywhere outside ORB, since no such concept exists to reuse.

## PART 3 — IMPLEMENTATION

Ten per-level classification variables (Asia H/L, London H/L, Overnight H/L, PDH/PDL, PWH/PWL), each a priority chain over the existing booleans only:

```pine
asiaHighClass = f_swept_high(asiaHigh) ? "SWEEP" : f_near(asiaHigh, liqThresh) ? "TEST" : "NONE"
...
pdhClass = (highSweepReject and (nearPDH or sweptPDH)) ? "REJECTION" : sweptPDH ? "SWEEP" : nearPDH ? "TEST" : "NONE"
...
```

A reusable function, `f_interactionLabel(showFlag, classification, levelPrice, levelName, labelColor)`, creates a label **only when the classification changes to a new, non-"NONE" value** (not every bar it happens to hold) — using a function-local `var string` to remember the previous classification and compare, so a sustained TEST condition across many bars fires once, not every bar, and escalating to SWEEP or REJECTION mid-hold fires a fresh label (a genuinely new, more significant event). The label is deleted after `interactionLabelBars` bars (default 6) via a stored expiry bar-index — no `barstate.islast`-only redraw loop and no permanent object; each label is temporary and self-expiring.

## PART 4 — NEW INPUTS

```pine
showLiquidityInteractionLabels = input.bool(true, "Show Liquidity Interaction Labels", group="Liquidity Interaction Context")
interactionLabelBars           = input.int(6, "Interaction Label Duration (bars)", minval=1, maxval=50, group="Liquidity Interaction Context")
interactionLabelSizeInput      = input.string("Normal", "Interaction Label Size", options=["Small", "Normal", "Large"], group="Liquidity Interaction Context")
```

## PART 5 — OBJECT MANAGEMENT

One label object per level (10 total), created only on a genuine classification change and deleted on expiry (or immediately if the governing show-flag is toggled off) — never more than 10 interaction labels exist at once, and none persist indefinitely. Combined with Phase 4's 14 persistent level objects, total object usage remains far below `max_lines_count=500`/`max_labels_count=500` (declared at the top of the file, unchanged).

## PART 6 — SCOPE EXCLUSIONS

ORB and IB are explicitly excluded from this layer, per instruction — they have their own visual identity and their own interaction concepts (`orbCtxText`, `orbTypeText`, IB's own state), untouched here.

## PART 7 — CONFIRMED NO STRATEGY IMPACT

None of the new classification variables or the `f_interactionLabel` function write to, read from, or are read by `canonicalBuy`, `canonicalSell`, `canonicalSignalState`, `buyScore`/`sellScore`, any grade, any alert, or any execution-related code. They are computed fresh from existing, already-scored booleans purely for display text — the same pattern already used and verified in Phase 4's emphasis calculations.
