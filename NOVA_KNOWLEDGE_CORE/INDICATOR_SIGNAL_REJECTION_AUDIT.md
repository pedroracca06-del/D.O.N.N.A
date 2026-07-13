# NOVA EXECUTION V1 — Indicator Signal & Rejection Audit

**Status:** READ-ONLY AUDIT. No Pine code, execution logic, broker logic, strategy logic, thresholds, or gates were modified to produce this document.
**Scope audited:** `indicators/nova_execution_v1.pine` (2,977 lines, full read), `engines/reasoning.py` (bridge parser + Python-side state machine), `engines/liquidity.py` / `engines/market_structure.py` (Python-side liquidity intelligence), `data/donna_signal_log.json` (94 most recent live evaluation cycles, MNQ + MES, spanning the current operational window), `git log` history of the indicator file.
**Method:** every claim below is anchored to an exact line number, variable name, or a count pulled from the live log. Where evidence was insufficient to state something as fact, it is flagged as "not evidenced" rather than assumed.

---

## EXECUTIVE SUMMARY — the five root causes

**Corrected framing (post-review):** RP is the correct terminology — RAP is not part of this framework and has been removed from this document. Break & Retest is strictly an ORB setup (break out of the ORB zone, return to test the ORB boundary, retest holds, continuation follows) — it is not, and was never classified in this audit as, an RP setup; see Part 4. ORB's restriction to ES/MES (`isESChart`) is **intentional current configuration, not a bug** — it is not a root cause and is not being proposed for removal. The MNQ Asia-High-rejection acceptance example was never going to be an ORB setup; it should have been evaluated and promoted through the **RP liquidity-rejection path**, which is where the real gap is.

1. **RP does not have a proper Pine strategy identity.** The knowledge base (`nova_knowledge_core/ORB_RP/reaction_setups.md`) fully documents three RP setups (Bounce, Rejection, Break & Retest as RP's own fallback language — not to be confused with the ORB Break & Retest setup, which is a separate, ORB-owned concept) as level-reaction trades independent of ORB. None of RP's setups are implemented as a named strategy family in Pine. The only structurally similar Pine logic (`highSweepReject`/`lowSweepReject`, lines 963–964) is unlabeled and falls into a generic `"REVERSAL"` bucket in `strategy_family` at best — it has no RP-specific direction/liquidity-source/interaction-type/setup-state/grade output (Part 3, Part 9 Phase 3).

2. **Existing sweep/rejection conditions do not feed the canonical BUY/SELL signal path.** `highSweepReject`/`lowSweepReject` feed `liqLongReady`/`liqShortReady` and `donnaLiqReversalLong`/`Short`, which can move `donnaCommand` to `"BUY"`/`"SELL"` — but this never reaches the `buySignal`/`sellSignal` composite (line 2140–2141) that the on-chart state and (once built) any chart marker would consume. There is no single canonical signal state today; there are at least three independent representations (`buySignal`/`sellSignal`, `donnaCommand`, `novaStateText`) that can disagree (Part 2, Part 9 Phase 1).

3. **The visible chart state and the bridge command can disagree.** Concretely: `novaStateText` (line 2824–2827, the on-chart strip) only recognizes `"WATCH LONG"`/`"WATCH SHORT"` from `dashCommandText`, never checking for `"BUY"`/`"SELL"` — so a bar can exist where the bridge `CMD` field says `"BUY"` while the on-chart strip says `"WAIT"` simultaneously. This is a reachable, evidenced contradiction, not a hypothetical (Part 3 Q23, Part 2 Q3–Q4).

4. **No on-chart BUY/SELL plotting system currently exists.** `plotshape`, `plotchar`, and `plotarrow` do not appear anywhere in `nova_execution_v1.pine`, in any commit, ever (verified with `git log --all -S"plotshape"` across the full history — zero hits). The `showSignals` input (line 25) is declared but never read anywhere in the file. The "BUY"/"SELL" text referenced from memory is table text (`dashCommandText`, `commandText`, `donnaCommand`) inside the on-chart NOVA panel/bridge tables — never a chart-anchored marker. **This needs to be built new — there is no prior working version in this repo's history to restore** (Part 3, Part 9 Phase 2).

5. **Major external liquidity levels are not exported consistently.** Asia/London H-L, PDH/PDL, PWH/PWL are computed in Pine (lines 574–628) but never exported to the NOVA BRIDGE table, and are separately computed a second time in Python (`engines/liquidity.py`, `engines/market_structure.py`) from yfinance-derived JSON files, entirely disconnected from the chart. Two parallel, non-communicating liquidity systems exist; neither drives what a human sees on the chart (Part 1, Part 7, Part 9 Phase 5).

**Note on ORB/ES scope (not a root cause, kept for context only):** ORB is hard-gated to ES-family charts (`isESChart`, line 89, feeding `orbLive` at line 130). On MNQ/NQ charts — 65 of the 94 recently logged cycles — the ORB engine is structurally inactive by design (`orb_signal` is `false` in all 94/94 logged cycles, `orb_state` never reached an active state in the sample). This is confirmed intentional current configuration per user direction and is explicitly **not** being changed by this audit or the phase plan below. Any future change to this gate is a separate strategy-scope decision requiring its own explicit approval — it is out of scope for Phases 1–6.

---

## PART 1 — LIQUIDITY LEVEL INVENTORY

| Level | Calculated? | Variable | Where (line) | Displayed? | Render call | Extended thru NY? | Labeled clearly? | Desktop readable? | Mobile readable? | → Signal logic? | → Bridge/MCP? | → Scoring? | → Rejection detection? | Tapped/untapped/swept/reclaimed? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Asia High | Yes | `asiaHigh` | 575, updated 582–587 | Box only, no dedicated H/L label | `asiaBox` (1339–1345) + single `"ASIA"` label at box top (1398) | No — box freezes at session end, no line extension | **No** — one generic "ASIA" tag, not "ASIA HIGH"/"ASIA LOW" | Poor | Poor | Yes (`orbAsiaHighSweepNow` etc., ORB-gated) | **No** | Yes, via `orbExtLiqTierBear` (tier 4, ORB-gated only) | Yes, but only inside ORB engine (`orbLive` required) | Sweep only (`orbAsiaHighSweepNow`); no reclaim classification exported |
| Asia Low | Yes | `asiaLow` | 576, 582–587 | Same box, no low-specific label | same | No | No | Poor | Poor | Yes (`orbAsiaLowSweepNow`, ORB-gated) | No | Yes (tier 4) | Yes, ORB-gated only | Sweep only |
| London High | Yes | `londonHigh` | 577, 588–593 | Box only, single "LONDON" label | 1358–1364, 1400 | No | No | Poor | Poor | Only via `orbHighNearPSH`-style aggregation (no direct London-specific gate) | No | Indirect (folded into `prevSessionHigh`) | No dedicated London rejection detector | Not classified |
| London Low | Yes | `londonLow` | 578, 588–593 | Box only | same | No | No | Poor | Poor | Same (folded into `prevSessionLow`) | No | Indirect | No | Not classified |
| Overnight High/Low | **Not separately modeled** | — | — | — | — | — | — | — | — | — | — | — | — | Not evidenced in Pine — Python side (`market_structure.py` → `ONH`/`ONL`) computes this independently, disconnected from chart |
| Previous Day High | Yes | `prevDayHigh` | 625 (`request.security(..., "D", high[1])`) | Line only, 12 bars long | `pdhLine` (2277–2278) | **No — extends only 12 bars right, redrawn once per `barstate.islast`** | **No text label at all** — solid green line, indistinguishable from PSH except by width/shade | Poor (short, no label) | Poor | Yes (`nearPDH`, `sweptPDH`, `orbHighNearPDH`) | **No** | Yes (`liqAboveTier`/`sweepHighTier`, tier 3) | Yes (`f_swept_high(prevDayHigh)`, contributes to `orbExtLiqTierBear`) | Near / swept / accepted-above all computed (`nearPDH`, `sweptPDH`, `acceptedAbovePDH`) but not "reclaimed" |
| Previous Day Low | Yes | `prevDayLow` | 626 | Line, 12 bars | `pdlLine` (2279–2280) | No | No text label | Poor | Poor | Yes | No | Yes (tier 3) | Yes | Near/swept/accepted computed, no reclaim state |
| Previous Week High | Yes | `prevWeekHigh` | 627 | Dashed thin line, 12 bars | `pwhLine` (2281–2282) | No | No text label | Poor (dashed + thin = easy to lose against grid) | Poor | Yes (`nearPWH`, `sweptPWH`, tier 4 in Liquidity Engine V2) | No | Yes (tier 4 — highest liquidity tier) | Yes | Near/swept/accepted computed |
| Previous Week Low | Yes | `prevWeekLow` | 628 | Dashed thin line, 12 bars | `pwlLine` (2283–2284) | No | No text label | Poor | Poor | Yes | No | Yes (tier 4) | Yes | Near/swept/accepted computed |
| Daily High/Low | **Same variable as PDH/PDL** — no separate "current daily high/low" concept exists; `prevDayHigh`/`Low` is the only daily-timeframe level | — | — | — | — | — | — | — | — | — | — | — | — | — |
| Weekly High/Low | Same as PWH/PWL — no separate current-week-in-progress high/low tracked | — | — | — | — | — | — | — | — | — | — | — | — | — |
| Session High/Low | Yes | `nyHigh`/`nyLow` (current), `prevSessionHigh`/`prevSessionLow` (prior) | 579–580, 601–622 | Box only (NY box), one "NEW YORK" label | 1365–1383, 1402 | No | No H/L split | Poor | Poor | Yes (tier 1/2 in Liquidity Engine V2) | No | Yes | Yes | Near/swept/accepted computed |
| Equal Highs | **Not implemented** | — | — | — | — | — | — | — | — | — | — | — | — | Not evidenced anywhere in file |
| Equal Lows | **Not implemented** | — | — | — | — | — | — | — | — | — | — | — | — | Not evidenced |
| Major Swing High Liquidity | Partially — `last1hSwingHigh`/`last4hSwingHigh` (1541–1553) exist for the ICT step model only | `last1hSwingHigh`, `last4hSwingHigh` | 1536–1553 | Not plotted at all | — | — | No | — | — | Yes, ICT-step only (`sweep1hHigh`, `sweep4hHigh`) | No | Yes (ICT weight only) | Yes, ICT sweep detection only | Not classified as tapped/untapped |
| Major Swing Low Liquidity | Same pattern | `last1hSwingLow`, `last4hSwingLow` | 1541–1553 | Not plotted | — | — | No | — | — | Yes (ICT) | No | Yes | Yes | Not classified |
| Untapped Liquidity | Conceptually yes (`liqAboveTier`/`liqBelowTier` = "near, not yet swept") | derived, not a stored var | 936–948 | Only via the unlabeled lines above | — | — | No dedicated "untapped" tag/color | — | — | Yes (`liqBullDraw`/`liqBearDraw`) | No | Yes | Feeds `highSweepReject`/`lowSweepReject` only after the fact | Yes, "near vs swept" is the closest proxy to tapped/untapped, but never rendered as a distinct visual state |
| Swept Liquidity | Yes | `sweepHigh`/`sweepLow`, `sweepHighLabel`/`sweepLowLabel` | 922–927, 953–954, 969–975 | Only as text inside `liqStateText`/`liqClusterText`, which are **not plotted on the chart at all** (used only in dashboard-table strings, e.g. `dashLiqText`) — no chart annotation fires when a sweep happens | — | — | Text exists (`"SWEEP PD HIGH"` etc.) but never reaches a `label.new`/table cell tied to price on the chart itself; only reaches the bridge? **No** — not in bridge table either | — | — | Yes (feeds `highSweepReject`/`lowSweepReject`, `donnaLiqReversalLong/Short`) | **No** — not in NOVA BRIDGE table | Yes | Yes (`f_swept_high`/`f_swept_low`) | Swept = yes; reclaimed = only informally via `highBreakHold`/`lowBreakHold` (acceptance beyond, not "reclaim back through") |
| Reclaimed Liquidity | Only inside ORB (`orbReclaimBullBars`/`orbReclaimBearBars`, ORB-gated) — **no generic (non-ORB) reclaim tracker exists** | `orbReclaimBullBars`, `orbReclaimBearBars` | 741–787 | Not directly plotted; only feeds `orbCtxText` (dashboard string) | — | — | No | — | — | Yes, ORB-gated only | **No** | Yes (`orbCtxBullBonus`/`orbCtxBearBonus`) | Yes, ORB-gated only | Reclaim bar-count tracked (1/2/3+) but only for ORB; non-ORB reclaim of PDH/PDL/PWH/PWL/Asia/London is not tracked at all |

**Visibility clarification honored:** ORB High/Low and IB High/Low visibility were not touched or re-evaluated for change — both already use dedicated, extended, clearly labeled lines (`orbHighLine`/`orbLowLine`, `ibHighLine`/`ibLowLine` + `"IB HIGH"`/`"IB LOW"` labels, lines 410–426 and 455–496). **IB is the correct reference model** for what "acceptable visibility" looks like: a persistent line from session start to current bar, plus a text label naming the level. None of Asia/London/PDH/PDL/PWH/PWL currently meet that bar.

---

## PART 2 — REJECTION ENGINE AUDIT

There is **no single, unified rejection engine**. There are three independent, non-communicating rejection paths:

### 2a. ORB rejection (ES-only)
- **Midpoint rejection** — `orbPassMidRejectBull`/`Bear` (2012–2026): requires `orbTradingWindow` (ES-only + `orbIsActive` + not dead/trapped), a confirmed prior breakout bar (`orbBullBreakBar`/`orbBearBreakBar` not na), price back inside the box, wick > 0.8×body at the midpoint, **and** `orbMidRejectQualityBull/Bear` (≥2-candle rejection sequence, tracked at 265–301).
- **Liquidity rejection** — `orbPassLiqRejectBull`/`Bear` (2031–2043): requires `orbSweepTierBull/Bear >= 1` (an external level — Asia/PWH/PDH/PSH — was swept) **and** `orbReclaimBullBars/Bear >= 2` (2+ bars holding beyond the swept level).
- **Edge rejection** — `orbPassEdgeRejectBull`/`Bear` (2048–2058): requires `orbEdgeRejectQualityBull/Bear` (≥2-candle sequence at the ORB edge, tracked 280–295), independent of prior breakout.
- All three require `isESChart` transitively via `orbTradingWindow` → `orbLive` (line 130). **This is the single largest gate**, since it structurally excludes MNQ/NQ, which is the majority instrument in the live log (65/94 cycles).
- Reachable, but empirically never reached in the sample: **0/94 logged cycles have `orb_signal = true`.**

### 2b. Generic (non-ORB) liquidity rejection — the closest thing to RP
- `highSweepReject`/`lowSweepReject` (963–964): fires when price is near/at/through a PSH/PDH/PWH (or PSL/PDL/PWL) level, closes back through it, with wick > 1.10×body. This is unlabeled, symbol-agnostic, and the closest existing analog to RP Setup 1/2 (Bounce/Rejection).
- Feeds `liqLongReady`/`liqShortReady` (1776–1777, requires `localBullBias`/`localBearBias` HTF-alignment AND-condition — RP's methodology explicitly allows counter-nothing trades at "clear" levels and only warns against fighting a *clear* trend, which is a looser and more discretionary condition than a hard EMA-bias AND-gate).
- Feeds `donnaLiqReversalLong`/`Short` (2461–2462, requires additionally `clusterBelow`/`clusterAbove` or nearness, plus `bullOBSupport`/`bearOBResistance`).
- **Does not feed `buySignal`/`sellSignal`** (2140–2141 only OR-combine `orbBuySignal`, `ictBuySignal`, `prosBuySignal`). This means RP-style setups can drive `donnaCommand` to `"BUY"`/`"SELL"` (via `donnaLiqReversalLong/Short` inside the `donnaCommand` ternary chain, 2495–2516) **without ever setting the raw `buySignal`/`sellSignal` booleans** that `novaStateText` (2824–2827) checks for `EXECUTION_READY`.

### 2c. PROS rejection (fib-zone based, separate concept from RP/ORB)
- `prosRejectionBull`/`Bear` (1172–1173): fires when a fib-zone touch (`prosZoneTouchedBull/Bear`) is followed by a close back through the 50% level. This is a different mechanism from RP (fib-retracement zone, not external liquidity level) and is correctly kept separate — no cross-contamination found here.

### Answers to the specific Part 2 questions
1. **Is rejection detection ever returning true?** Yes — `highSweepReject`/`lowSweepReject` and `prosRejectionBull/Bear` are reachable and do fire (evidenced by non-zero `pros_phase` variety in the log, e.g. `OTE_TAGGED`: 1, `SETUP_READY`: 4). ORB-family rejection (`orbPassMidRejectBull` etc.) is reachable in principle but **0/94 observed firing**, 100% attributable to `isESChart`/`orbLive` gating combined with MNQ dominance.
2. **Which gates reject the most candidates?** From the log: `pre_signal` (Python's own pre-Claude classification) is `HEADS_UP` in 87/94 (92.6%) and `EXECUTION_READY` in only 1/94 (1.1%) — the single largest drop-off is between "a setup is forming" and "a setup is confirmed," which in Pine corresponds to the OTE/continuation-confirmation requirement (`prosContinuationBull/Bear`, which needs a *second*, later close through the rejection-candle's high/low — `prosContinuationBull` at 1223–1224). This is a real, working gate, not a bug — but it means the visible state is overwhelmingly "watching," which matches the user's Goal #5 complaint independent of anything broken.
3. **Are rejection candidates generated and then blocked later?** Yes, specifically the RP-shaped ones (2b above) — generated (`highSweepReject`/`lowSweepReject` fire), scored (feed `buyScore`/`sellScore` and `donnaCommand`), but never promoted to the boolean state (`buySignal`/`sellSignal`) that would let a future chart marker or the on-chart `novaStateText` strip show them.
4. **Are they converted only into HEADS_UP?** Worse — they can produce `donnaCommand == "BUY"/"SELL"` (a stronger signal than HEADS_UP) in the bridge `CMD` field while the on-chart `novaStateText` shows `"WAIT"` (since it never reaches `"WATCH LONG"/"WATCH SHORT"` either — see contradiction in Executive Summary #3). This is a state-name/severity mismatch, not a simple under-promotion.
5. **Failing because liquidity levels aren't passed into the evaluator?** No — Pine itself has all six external levels computed locally and does pass them into `highSweepReject`/`orbSweepTier*`. The failure is downstream (not reaching `buySignal`) and upstream on the Python side (levels never reach the bridge — see Part 7).
6. **Liquidity source UNKNOWN/missing?** `strategy_family` (2108–2114) has a `"REVERSAL"` bucket exactly for `liqLongReady/liqShortReady`, and `"UNKNOWN"` as the terminal fallback — so RP-style setups are classifiable as `"REVERSAL"`, not `"UNKNOWN"`, when they do fire. They are just never surfaced visually.
7. **Is the bridge receiving rejection state?** No dedicated rejection field exists in the NOVA BRIDGE table (rows 0–33 enumerated at lines 2894–2963) — no `REJECTION_TYPE`, `REJECTION_SOURCE`, or `REJECTION_DIRECTION` key. The closest is the ORB-only `O_TYPE`/`O_REJ_Q` (rows 16–17), which is silent whenever the chart is MNQ/NQ.
8. **Is the dashboard dropping/mislabeling rejection setups?** The chart-side dashboard cannot label what it never receives — see #7. The Python-side `pre_signal`/`pre_setup` fields (evidenced in the log: `pre_setup: "PROS_LONG"`) show reasoning.py is a completely separate PROS/IB/ORB-string-parsing state machine layered on top of the bridge text fields, and it has no `pre_setup` value corresponding to "RP"/"liquidity reversal" at all in the 94-row sample (`pre_setup` values observed were all PROS-related in the excerpt reviewed) — consistent with RP simply not being modeled end-to-end.
9. **Are labels hidden even when rejection logic triggers?** N/A — no labels exist to hide (see Part 3).
10. **Are ORB and RP rejection paths both reachable?** ORB's is reachable but empirically dead on the dominant instrument (MNQ). RP has no dedicated path — only the generic proxy in 2b, which is reachable but structurally capped below `EXECUTION_READY`/chart-marker eligibility.

---

## PART 3 — ON-CHART BUY/SELL LABEL AUDIT

**Direct answers:**

1. **Are the BUY booleans ever becoming true?** Yes. `buySignal` (composite, line 2140) is true whenever `orbBuySignal or ictBuySignal or prosBuySignal`. Per the log, `nova_cmd` (a related but distinct text field, `donnaCommand`) shows `"BUY"` in 8/94 cycles and `"SELL"` in 6/94 — so directional signals do fire in the current operational window.
2. **Are the SELL booleans ever becoming true?** Yes, same evidence (6/94 `SELL`).
3. **Exact BUY boolean variable names:** `buySignal` (line 2140, composite), `orbBuySignal` (2099), `ictBuySignal` (2101), `prosBuySignal` (2103).
4. **Exact SELL boolean variable names:** `sellSignal` (2141), `orbSellSignal` (2100), `ictSellSignal` (2102), `prosSellSignal` (2104).
5. **Are `plotshape()` calls still present?** **No. Zero occurrences in the file.**
6. **Are `label.new()` calls still present?** Yes, but none are wired to `buySignal`/`sellSignal` — only to IB HIGH/LOW (479, 489), ASIA/LONDON/NEW YORK session tags (1398, 1400, 1402), and T1/T2/MR smart-target labels (2339, 2342, 2345).
7. **What exact conditions surround the plotting calls?** N/A — there is no plotting call for BUY/SELL to have conditions around.
8. **Are the plotting conditions reachable?** N/A.
9. **Are labels disabled by an input?** No input (`showSignals`, line 25) is declared but **never referenced anywhere else in the file** — it is dead code. It looks like a vestige of a BUY/SELL-marker feature that either was planned and never built, or was removed before this file entered version control (git history shows the input existing since before the earliest tracked commit — `showSignals` is not part of any diff in the 33-commit history, meaning it predates git tracking of this file).
10. **Is `showSignals`/similar defaulting to false?** It defaults to `true` (line 25: `input.bool(true, "Show Signals")`), but since nothing reads it, its value is irrelevant.
11. **Are labels being deleted immediately?** N/A.
12. **Off-screen y-values?** N/A.
13. **Transparent colors?** N/A.
14. **Sizes too small?** N/A.
15. **Mobile/desktop presets hiding them?** No such presets exist for anything in this file (single global toggles only).
16. **`max_labels_count`/object limits?** `max_labels_count=500`, `max_lines_count=500`, `max_boxes_count=200` (line 2) — generous, not a binding constraint given current usage (a handful of persistent labels + per-bar historical fade boxes capped at `histLookback` ≤ 5).
17. **BUY/SELL states converted only into HEADS_UP text?** They convert into table-cell text (`dashCommandText`, `commandText`) — never into a chart-anchored visual of any kind, HEADS_UP or otherwise.
18. **Is EXECUTION_READY incorrectly required before a marker can appear?** N/A today (no marker exists at all) — but this is the exact trap to avoid in the fix: `novaStateText` gates on `buySignal`/`sellSignal`, which already excludes the RP-style setups (Part 2). If a future marker is wired to `buySignal`/`sellSignal` directly, it will inherit the same blind spot.
19. **Are valid ORB or RP rejection candidates blocked before the plotting section?** ORB on non-ES charts is blocked by design (intentional configuration, not in scope). RP-style setups are blocked because they never reach the canonical signal path (Executive Summary #1–#2) — moot today since there is no plotting section, but this is exactly what Phase 3 (RP identity) must close before Phase 2 (markers) can show RP setups at all.
20. **Do `alertcondition()` and the plotted labels use the same source?** N/A for labels. `alertcondition()` (2217–2220) covers only `orbBuySignal`, `orbSellSignal`, `prosBuySignal`, `prosSellSignal` — **`ictBuySignal`/`ictSellSignal` have no `alertcondition()` entry** (they do have `alert()` JSON webhook calls, 2247–2251). This is a minor asymmetry, not a functional bug, since the documented workflow (comment at 2223–2224) is to use a single "Any alert() function call" TradingView alert, which does cover ICT via the JSON `alert()` calls.
21. **Can an alert fire without a visible chart marker?** Yes, today, for every signal type — there are no chart markers at all, so every alert (`alertcondition` or `alert()` JSON) fires invisibly on the chart.
22. **Can a marker appear without an alert?** N/A (no markers).
23. **State-name mismatches such as READY vs EXECUTION_READY?** Yes — found one concretely: `novaStateText` (2824–2827) only recognizes `"WATCH LONG"`/`"WATCH SHORT"` from `dashCommandText` as its HEADS_UP trigger; it does not check for `dashCommandText == "BUY"`/`"SELL"`. Since `dashCommandText = donnaCommand`, and `donnaCommand` can independently resolve to `"BUY"`/`"SELL"` via paths that never set `buySignal`/`sellSignal` (e.g. `donnaLiqReversalLong` + `buyScore >= donnaThreshBuy`, line 2511), there exist reachable bars where the bridge `CMD` field says `"BUY"` while the on-chart status strip says `"WAIT"` (falls through the full ternary chain at 2824–2827 to the final `else` because none of its three conditions match). This is a genuine, reachable state contradiction between two parts of the same script.
24. **Duplicate/cooldown rules suppressing the chart marker?** `canSmartBuy`/`canSmartSell` (1771–1772, 20-bar cooldown) gate `orbBuySignal`/`orbSellSignal`/`ictBuySignal`/`ictSellSignal`/`prosBuySignal`/`prosSellSignal` — reachable and by design, not a bug, but relevant context: even once markers exist, a 20-bar cooldown will suppress a second marker of the same direction shortly after the first.
25. **Old labels overwritten/removed by dashboard/object cleanup?** The only recurring delete-then-recreate pattern is on `barstate.islast` for session labels/target labels/liquidity lines (1390–1396, 2260–2272, 2318–2336) — this is a normal "redraw on the last bar only" pattern for TradingView overlays and does not affect anything BUY/SELL related since none exist.

**Root cause of why BUY/SELL labels "no longer appear": there is no evidence they were ever a Pine-drawn chart object in this codebase's history.** The most likely explanation, given `showSignals` is declared but unused and predates the tracked git history, is that this is either (a) a feature that was planned/named but never implemented, or (b) markers existed in a version of the script edited directly in the TradingView UI and never committed back to this repository before being lost in a subsequent from-scratch rewrite (the dashboard was rebuilt at least twice per the commit log: `e1a861c feat(dashboard): rebrand from ICT-centered to NOVA/PROS architecture` and `c3f3ee2 feat(dashboard): execution terminal UX`). This audit cannot distinguish between those two without the pre-git version of the file, which is not available. **Do not assume regression — assume "needs to be built."**

---

## PART 4 — STRATEGY SEPARATION

| Strategy | Pine identity | Status |
|---|---|---|
| ORB (Edge Rejection, Midpoint Rejection, Liquidity Rejection, Break & Retest) | `orbPassEdgeRejectBull/Bear`, `orbPassMidRejectBull/Bear`, `orbPassLiqRejectBull/Bear`, `orbValidBreakBull/Bear` (2000–2094) | Correctly kept as one family (`strategy_family == "ORB"`), correctly distinct from RP conceptually, but ES-gated (see above). "Break & Retest" here maps to `orbValidBreakBull/Bear` + prior retest logic (`orbRetestBull/Bear`, 260–261) — correctly modeled as an ORB-native concept, not folded into RP. **No violation of the "Break & Retest is an ORB term" rule found.** |
| RP (Rejection at major liquidity, Bounce, Failed breakout, Sweep and reclaim) | `highSweepReject`/`lowSweepReject`, `donnaLiqReversalLong/Short` | **No dedicated identity.** Falls into the generic `"REVERSAL"` bucket of `strategy_family` (2114) only when it fires, otherwise silently absent. Not violated (nothing is *mis*-labeled as ORB), but not *built* either — it is the weakest-modeled of the four frameworks. |
| PROS (Continuation, Displacement, Retracement, Defense) | `prosLegValidBull/Bear`, `prosRejectionBull/Bear`, `prosContinuationBull/Bear` (1066–1310) | Well-modeled, clearly separated (`strategy_family == "PROS"`), highest field-count in the bridge (`P_DISPL`/`P_RETRACE`/`P_OTE`/`P_CONT`/`P_QUALITY`/`P_STDV`, rows 6–11). Dominant in the log (`pros_phase` present on all 94 rows). |
| IB | `ibHigh`/`ibLow`, dedicated 1-minute-anchored calc (201–244) | Correctly separate from ORB, not merged. Visibility already acceptable per user note and per this audit's own comparison (Part 1) — left untouched. |

No instance of ORB and RP logic being merged into one generic bucket was found — the failure mode here is *absence* of RP as a first-class concept, not *conflation*.

---

## PART 5 — VISUAL HIERARCHY AUDIT (desktop AND mobile)

Confirmed problems, all in the "LIQUIDITY MARKERS" block (2252–2284) and session-box labels (1385–1402):

| Level pair | Line color/width/style | Extension | Label | Problem |
|---|---|---|---|---|
| PSH/PSL | green/red @ 40% opacity, width 2, solid | 12 bars only | none | Same color family as PDH/PDL — only opacity differs (40% vs 0%), which is a poor discriminator, especially on mobile at small sizes/DPI |
| PDH/PDL | solid green/red, width 2 | 12 bars only | none | Indistinguishable from PSH/PSL except opacity |
| PWH/PWL | dashed green/red @ 0% opacity, width 1 | 12 bars only | none | Thinnest, most transparent-adjacent, easiest to lose against candles/grid despite being the highest-tier (tier 4) level in the scoring model |
| Asia/London/NY | box + one label at box top only | Box stops growing after session ends (no line/extension into NY) | Single session-name label (`"ASIA"`), not H vs L | The box's *bottom* (the low) has no label at all; only the top (which the label is anchored to, `box_top`) gets named, and even that name doesn't say "HIGH" |

All six external-level lines are recreated **only on `barstate.islast`** (2260 for PSH-PWL, 1390 for session boxes) and extend a fixed **12 bars** to the right (`bar_index + 12`, e.g. 2274). On any timeframe faster than a few minutes, 12 bars is a few minutes of chart width — these lines will visually appear to "disappear" almost immediately relative to a full NY session, which directly explains "the line disappears too early" from the Part 5 checklist. This is a real, evidenced bug pattern (not a hypothesis) — contrast directly with IB's lines, which extend from `ibStartBar`/`ibLockBar` to the live `bar_index` every bar (462–476) and are visible for the entire session by construction.

**Proposed priority tiers (per user's Part 5 spec, not implemented here):**
- Tier 1 (highest): level currently being tested/swept/reclaimed/rejected; nearest major external level; active ORB structure when ORB is the active setup; active RP level when RP is active.
- Tier 2: other major external levels, daily/weekly references, session ranges.
- Labels should name the source explicitly (ASIA HIGH, ASIA LOW, LONDON HIGH, LONDON LOW, PDH, PDL, PWH, PWL) exactly as IB HIGH/IB LOW already do — this is a proven, already-working pattern in the same file, not a new design.

---

## PART 6 — DASHBOARD READABILITY AUDIT

Two distinct dashboards exist and should not be conflated:

1. **The Pine on-chart panel** (`novaStrip`, `table.new(position.top_right, 7, 1, ...)`, line 2560) — a single row, 7 columns, `size.tiny` text (2864–2870). This is compact but not "overloaded" by field count; the readability risk here is `size.tiny` on a 7-column single row at typical mobile pixel density, and the fact that the *values* it shows (`novaBiasText`, `novaSetupText`, `novaStateText`) are a narrower, less current signal set than the bridge (Executive Summary #3) — so it can look "stuck" even when other parts of the same script have moved on.
2. **The NOVA BRIDGE table** (`novaBridge`, `table.new(position.bottom_left, 2, 34, ...)`, line 2562) — 34 rows, but **invisible by default** (`showBridge` input defaults to `false`, line 26; `_brBg`/`_brKey`/`_brVal` all resolve to 99–100% transparent when hidden, 2890–2892). This is not the readability problem the user is describing on a normal trading session, since it isn't shown.
3. **The separate web dashboard** (`ui/html.py`, ~6,462 lines, 567 occurrences of size/compact-density CSS patterns) is NOT part of this indicator and was not modified or deeply re-audited here per the "read-only, indicator-focused" scope of this task — it already has a documented, approved-but-not-yet-implemented consolidation plan (see memory: `project_dashboard_tab_architecture.md`, 3-tab model, "NOT yet implemented — stability first"). If the "dashboard too compressed" complaint is about the web app rather than the chart panel, that backlog item is the right place to continue, not this Pine file.

No `AUTO`/`DESKTOP READABLE`/`MOBILE READABLE`/`OFF` dashboard-mode concept exists anywhere in the Pine file today — there is exactly one `showDashboard` boolean (line 22) controlling both `novaStrip` and (independently) `showBridge` gates `novaBridge`. Building distinct modes would be new work, not a fix to something broken.

---

## PART 7 — BRIDGE / MCP AUDIT

**Current NOVA BRIDGE fields** (table `novaBridge`, rows 0–33, lines 2894–2963), grouped:

- Core (rows 1–4): `CMD` (`dashCommandText`=`donnaCommand`), `SYS_STATE` (`donnaScenario`), `SCORE` (`dashScoreText`), `CONF` (`donnaConfText`)
- PROS (rows 5–11): `PROS_ENG`, `P_DISPL`, `P_RETRACE`, `P_OTE`, `P_CONT`, `P_QUALITY`, `P_STDV`
- IB (rows 12–13): `IB H`, `IB L`
- ORB (rows 14–20): `O_STATE`, `O_BIAS`, `O_TYPE`, `O_REJ_Q`, `O_HIGH`, `O_MID`, `O_LOW`
- v2 metadata (rows 21–33): `BRIDGE_VER`, `TICKER`, `TF`, `IB_STATUS`, `SESSION`, `ORB_ACTIVE`, `PROS_ACTIVE`, `COOLDOWN`, `TRAP`, `ICT_STEP`, `PEER_ALIGN`, `DRAW_TARGET`, `DRAW_DIR`

**Confirmed missing from the bridge, despite being calculated in Pine:**
- Asia High/Low, London High/Low, PDH/PDL, PWH/PWL values themselves (only ORB's own `O_HIGH`/`O_MID`/`O_LOW` are exported — no external-liquidity equivalent)
- `buySignal`/`sellSignal` raw booleans (only the derived text `CMD` is exported)
- Sweep tier / reclaim-bar-count (`orbSweepTierBull/Bear`, `orbReclaimBullBars/Bear`) — internal to ORB's own display strings (`O_TYPE`, `O_REJ_Q`) as text, not as a structured field
- Any rejection-type/rejection-source/rejection-direction field for the non-ORB liquidity path
- `strategy_family`/`setup_type` (computed in Pine at 2108–2132, richly detailed, but **never written to the bridge table at all** — confirmed absent from all 34 rows)

**Confirmed stale/mismatch risk:** `SYS_STATE` = `donnaScenario`, a free-text string (e.g. `"LIQ SWEEP LONG"`, `"TRAP RISK — WAIT"`) — not an enum, and not the same value as the on-chart `novaStateText` enum (`WAIT`/`HEADS_UP`/`EXECUTION_READY`/`LOCKED`), which **is never exported to the bridge at all**. `engines/reasoning.py`'s `parse_nova_tables()` (confirmed via grep) reads `CMD`/`SYS_STATE`/`SCORE`/`CONF`/`PROS_ENG` etc. directly and reconstructs its own Python-side HEADS_UP/EXECUTION_READY state machine independently — meaning **the Pine-side `novaStateText` enum is decorative only** and not what actually drives NOVA's alerting decision. This matters for Goal #5: fixing `novaStateText`'s internal contradiction (Part 3 Q23) would improve what a human sees on the chart, but would not by itself change NOVA's actual alert behavior, since Python already works from `CMD`/`SYS_STATE` text, not from `novaStateText`.

**Calculated but not exported (confirmed):** `strategy_family`, `setup_type`, `buySignal`/`sellSignal`, `orbCtxText`/`orbCtxColor` (contextual sweep/reclaim narrative), all six external liquidity level values.
**Exported but seemingly redundant with Python's own computation:** none found — the Python-side liquidity/structure intelligence (`engines/liquidity.py`, `engines/market_structure.py`) is entirely yfinance-sourced from JSON files (`donna_market_structure.json`, `donna_market_reality_v2.json`), independent of anything the chart could export; it is explicitly documented as "Observation only" and does not currently feed back into chart-side promotion logic.

---

## PART 8 — LIVE OPERATIONAL EVIDENCE (94 most recent cycles, `data/donna_signal_log.json`)

```
symbol counts:        MNQ 65  |  MES 29
orb_state counts:     ORB_INACTIVE 56  |  ORB_FAILED 23  |  ORB_EXPIRED 15   (never READY/RETESTING/ACCEPTED)
orb_signal counts:    False 94  |  True 0
nova_cmd counts:      WAIT 73  |  BUY 8  |  SELL 6  |  WATCH LONG 5  |  WATCH SHORT 2
pre_signal counts:    HEADS_UP 87  |  INVALIDATION 6  |  EXECUTION_READY 1
alert_required:       False 64  |  True 30
grade counts:         C 39  |  B 32  |  D 23   (zero A grades observed in this sample)
pros_phase counts:    OTE_APPROACHING 68 | NONE 8 | BUILDING 7 | ACCEPTED_CONTINUATION 6 | SETUP_READY 4 | OTE_TAGGED 1
```

**Where candidates die, in order of volume:**
1. **ORB dies at the instrument gate** — 100% suppression, before any rejection-quality logic even runs, whenever `symbol != ES/MES`.
2. **PROS setups die at the OTE-approach → confirmed-rejection boundary** — 68/94 cycles are stuck at `OTE_APPROACHING` (displacement happened, price hasn't yet tagged and rejected the fib zone); only 1/94 reached `OTE_TAGGED`. This is the score-model working as designed (PROS requires draw independence per the already-documented `project_draw_validation.md` finding), not a bug, but it is the single biggest contributor to "WAIT/HEADS_UP without progressing," simply because most of the trading day is spent in the approach phase by construction.
3. **Governance/session-quality gates further compress `HEADS_UP` (87) down to `alert_required=True` (30)** — roughly two-thirds of Python-classified HEADS_UP candidates are additionally suppressed before Discord/dashboard delivery (cooldowns, caps, conviction capping per `reasoning.py` lines ~1956–2021 — the `CONFLICTED`/`LOW` conviction cap to HEADS_UP, and cooldown/dedup logic in `delivery/alert_engine.py`, not re-examined line-by-line here since it is outside the indicator's scope).

This confirms the system is **not silently broken** — it is evaluating, scoring, and gating every cycle — but the combination of (a) ORB's instrument gate, (b) PROS's strict rejection-confirmation requirement, and (c) RP's absence as a first-class path, means the *visible* surface (chart panel + most delivered alerts) is dominated by "still forming" states, and a large class of valid external-liquidity reactions (the Asia High example) has no path to visibility at all rather than merely a slow one.

---

## PART 9 — APPROVED IMPLEMENTATION PHASES

Audit approved by user 2026-07-13, with the following corrections locked in before any coding began:
- Terminology is **RP**, never "RAP" (RAP is not part of this framework).
- ORB Break & Retest remains strictly an ORB setup (break out of the ORB zone → retest the ORB boundary → retest holds → continuation) — never classified as an RP setup.
- ORB's restriction to ES/MES (`isESChart`) is **intentional current configuration** and is **not being changed** by this plan.
- Root causes are the five listed in the Executive Summary, not "ORB failed on MNQ."

**Phase 1 — Canonical signal-state repair**
Unify chart, alerts, and bridge around one authoritative Pine signal model (`canonicalSignalState`, `canonicalDirection`, `canonicalStrategy`, `canonicalSetup`, `canonicalGrade`, `canonicalLiquiditySource`, `canonicalInteraction`, `canonicalBuy`, `canonicalSell`). Preserve existing thresholds/gates — wrap, don't loosen.

**Phase 2 — On-chart BUY/SELL markers**
Build `plotshape()`/`label.new()` markers driven by `canonicalBuy`/`canonicalSell` from Phase 1. Wire up the currently-dead `showSignals` input plus new `showSignalContext`/`signalLabelSize` inputs. No dependency on execution/broker/prop state.

**Phase 3 — RP liquidity-rejection identity**
Give RP a first-class Pine identity (REJECTION first, then BOUNCE/FAILED_BREAKOUT/SWEEP_RECLAIM) built from the existing `highSweepReject`/`lowSweepReject` logic and thresholds — no invented criteria. Distinguish rejection-context-detected → RP candidate → RP HEADS_UP → RP READY → RP BUY/SELL. Only a setup that passes RP's own gates may become `canonicalBuy`/`canonicalSell`.

**Phase 4 — Major external liquidity visibility**
Asia H/L, London H/L, PDH/PDL, PWH/PWL, Daily H/L, Weekly H/L only — ORB H/L and IB H/L are already acceptable and untouched. Persistent, clearly labeled, session-appropriate lines with configurable width/opacity/style, nearest/active level emphasized over the rest.

**Phase 5 — Bridge liquidity and signal export**
Export the canonical Pine state (signal_state, signal_direction, strategy, setup, grade, buy, sell, active liquidity source/price, interaction, rejection detected/direction) plus the six external liquidity level values. Keep the Python liquidity engine running in parallel — compare and log mismatches, do not silently switch sources yet. Observability-first.

**Phase 6 — Dashboard readability**
Add `AUTO`/`DESKTOP_READABLE`/`MOBILE_READABLE`/`OFF` modes to the on-chart panel, prioritizing Direction/Strategy/Signal State (row 1) and Liquidity Source/Interaction/Grade (row 2) over full field dumps.

**Non-goals for every phase:** no execution/broker logic changes, no threshold loosening, no blind signal-frequency increase, no touching the Execution Bot. Implementation proceeds one phase at a time, each compiled, reported, and committed separately before the next begins.

---

## Appendix — items explicitly out of scope / not touched
- ORB High/Low and IB High/Low visibility (left as-is per instruction; used here only as the "what good looks like" reference).
- `services/execution.py`, `services/execution_bridge.py`, broker/risk-gate logic — not read as part of this audit; this document only concerns the Pine indicator and its bridge to `engines/reasoning.py`.
- `delivery/alert_engine.py` cooldown/dedup internals — referenced only via the aggregate `alert_required` count in Part 8, not line-audited.
- `ui/html.py` (web dashboard) — noted in Part 6 as a separate system with its own existing backlog item; not deeply re-audited here.
