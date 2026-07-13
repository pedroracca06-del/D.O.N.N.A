# NOVA EXECUTION V1 — Phase 6: Source-Specific Rejection Detection & BUY/SELL Signal-Flow Audit

**Status:** Part 2 (source-specific rejection attribution) and Part 4 (Phase 5 label integration) implemented. Part 5 (signal-flow) is audit-only — no eligibility change made. `indicators/nova_execution_v1.pine` only. Verified with TradingView's stateless server-side compile-check endpoint only — no CDP/live-chart interaction, live cloud script untouched.

---

## PART 1 — SOURCE ATTRIBUTION AUDIT

Exact current definitions (unchanged by this phase):

```pine
liqThresh = atrValue * 0.25                                    // line 701

nearPSH = f_near(prevSessionHigh, liqThresh)                    // line 985
nearPSL = f_near(prevSessionLow,  liqThresh)                    // line 986
nearPDH = f_near(prevDayHigh,     liqThresh)                    // line 987
nearPDL = f_near(prevDayLow,      liqThresh)                    // line 988
nearPWH = f_near(prevWeekHigh,    liqThresh)                    // line 989
nearPWL = f_near(prevWeekLow,     liqThresh)                    // line 990

sweptPSH = f_swept_high(prevSessionHigh)                        // line 992
sweptPSL = f_swept_low(prevSessionLow)                          // line 993
sweptPDH = f_swept_high(prevDayHigh)                            // line 994
sweptPDL = f_swept_low(prevDayLow)                              // line 995
sweptPWH = f_swept_high(prevWeekHigh)                           // line 996
sweptPWL = f_swept_low(prevWeekLow)                             // line 997

highSweepReject = (nearPSH or nearPDH or nearPWH or sweptPSH or sweptPDH or sweptPWH) and close < open and upperWick > body * 1.10 and close < high[1]   // line 1033
lowSweepReject  = (nearPSL or nearPDL or nearPWL or sweptPSL or sweptPDL or sweptPWL) and close > open and lowerWick > body * 1.10 and close > low[1]    // line 1034
```

Where `f_near(level, thresh) => not na(level) and math.abs(close - level) <= thresh` and `f_swept_high(level) => not na(level) and high > level and close < level` (and the low-side mirror) — both pure, level-specific, unchanged.

### Answer: (B) generic — not (A)

`highSweepReject`/`lowSweepReject` indicate a generic rejection from **any qualifying high-side/low-side level** among {PSH, PDH, PWH} (or {PSL, PDL, PWL}). The six-way `or` inside each formula's first clause has no memory of *which* of the six conditions was actually true — the remaining clauses (`close < open`, `upperWick > body * 1.10`, `close < high[1]`) are candle-shape checks that say nothing about which specific price level the wick interacted with. `nearPxx`/`sweptPxx` themselves (the individual level checks) **are** already source-specific and unambiguous — the false-attribution risk lives entirely in `highSweepReject`/`lowSweepReject`'s own OR, not in the near/swept primitives.

### False-attribution scenario (concrete)

Suppose PDH = 5000 and PWH = 5008 (a common real-world case — yesterday's high and the week's high often sit close together, e.g. if yesterday was also the week's high so far). `liqThresh = atrValue * 0.25`; on a typical session `atrValue` might be ~40 points, so `liqThresh` ≈ 10 — meaning PDH and PWH, 8 points apart, fall inside each other's "near" zone.

If price wicks up to 5008, sweeps through PWH (`sweptPWH` becomes true: `high > 5008 and close < 5008`), and closes back down — `highSweepReject` fires because its OR is satisfied by `sweptPWH`. **Independently**, `nearPDH = abs(close - 5000) <= 10` can *also* be true on that same bar, purely because PDH and PWH are clustered close enough together — with no requirement that the candle's wick or close ever meaningfully interacted with PDH specifically.

Phase 5's original expression, `highSweepReject and (nearPDH or sweptPDH)`, would evaluate true in this exact scenario and label the event **"PDH REJECTION"** — when the level that was actually pierced and rejected was PWH, not PDH. This is the precise false-attribution risk the user's Part 1 asked to be identified: the rejection boolean was caused by one level (PWH), another level was also nearby (PDH), and the visual label could name the wrong source. Confirmed present in the current (pre-Phase-6) Phase 5 code for all four of PDH/PDL/PWH/PWL's rejection labels — none of them can distinguish which of the six generic OR-terms actually fired.

Asia/London/Overnight never had this specific risk in Phase 5, because they had no `REJECTION` tier at all (only `TEST`/`SWEEP`, built from the level's own `f_near`/`f_swept_high`/`f_swept_low` — already fully source-specific).

---

## PART 2 — SOURCE-SPECIFIC INTERACTION STATES (implemented)

New named booleans, added to the existing `LIQUIDITY HELPERS` section, extending its established `nearPxx`/`sweptPxx` naming convention to the six levels that previously lacked one:

```pine
nearAsiaHigh      = f_near(asiaHigh, liqThresh)
nearAsiaLow       = f_near(asiaLow,  liqThresh)
nearLondonHigh    = f_near(londonHigh, liqThresh)
nearLondonLow     = f_near(londonLow,  liqThresh)
nearOvernightHigh = f_near(overnightHigh, liqThresh)
nearOvernightLow  = f_near(overnightLow,  liqThresh)

sweptAsiaHigh      = f_swept_high(asiaHigh)
sweptAsiaLow       = f_swept_low(asiaLow)
sweptLondonHigh    = f_swept_high(londonHigh)
sweptLondonLow     = f_swept_low(londonLow)
sweptOvernightHigh = f_swept_high(overnightHigh)
sweptOvernightLow  = f_swept_low(overnightLow)
```

Ten level pairs (Asia/London/Overnight/PDH-PDL/PWH-PWL), each with `xTest`/`xSweep`/`xReject`:

```pine
asiaHighTest   = nearAsiaHigh
asiaHighSweep  = sweptAsiaHigh
asiaHighReject = (nearAsiaHigh or sweptAsiaHigh) and close < asiaHigh and close < open and upperWick > body * 1.10
// ... mirrored for asiaLow, londonHigh, londonLow, overnightHigh, overnightLow

pdhTest   = nearPDH
pdhSweep  = sweptPDH
pdhReject = (nearPDH or sweptPDH) and close < prevDayHigh and close < open and upperWick > body * 1.10
// ... mirrored for pdl, pwh, pwl
```

**This fixes the Part 1 false-attribution risk directly:** each `xReject` formula only ever references its own level's `near`/`swept` boolean and its own level's price for the close-through check — there is no OR across other levels, so a PWH sweep can never be mislabeled as a PDH rejection again.

---

## PART 3 — REJECTION FORMULA, CLASSIFIED (no new strategy)

Per-level formula (high-side; low-side is the exact mirror):

```
xReject = (nearX or sweptX) and close < X and close < open and upperWick > body * 1.10
```

| Component | Classification | Notes |
|---|---|---|
| `nearX or sweptX` (touch or sweep of the exact level) | **STRUCTURAL REJECTION REQUIREMENT** | Reused verbatim — `f_near`/`f_swept_high`/`f_swept_low`, `liqThresh = atrValue * 0.25`, all unchanged |
| `close < X` / `close > X` (closes back through the exact level) | **STRUCTURAL REJECTION REQUIREMENT** | **New** — this is the fix. The original generic formula never explicitly checked "closed back through *this* level"; it only proved the candle closed below the *prior bar's high* (`close < high[1]`), which says nothing about any specific level. Required per the user's own Part 3 template ("candle closes back below/above the level") |
| `close < open` / `close > open` (bearish/bullish candle) | **STRUCTURAL REJECTION REQUIREMENT** | Reused verbatim from `highSweepReject`/`lowSweepReject` |
| `upperWick > body * 1.10` / `lowerWick > body * 1.10` | **STRUCTURAL REJECTION REQUIREMENT** | Reused verbatim — identical 1.10 multiplier, unchanged |
| `close < high[1]` / `close > low[1]` (present in the *original* generic formula) | **NEEDS USER DECISION** | **Omitted** from the new source-specific formulas. This condition has no obvious source-specific meaning (it compares to the prior bar's extreme, not to any liquidity level) and isn't part of the four components in the user's own Part 3 template. Omitting it is very slightly *less* restrictive than the original generic formula in isolation, but the new `close < X` requirement is a *more* specific, *more provable* replacement — net effect on precision is positive, but this is a genuine judgment call, not an automatic derivation, and is flagged here rather than decided silently. **Awaiting user confirmation**: keep omitted, or add `and close < high[1]` / `and close > low[1]` back to each formula for strict parity with the original? |
| Volume, MACD, HTF alignment, displacement | **CONTRADICTORY / NOT REQUIRED** | Explicitly excluded per instruction — not added anywhere |
| Instrument gate (`isESChart`) | **NOT APPLICABLE** | This layer is symbol-agnostic by design, matching the existing generic `highSweepReject`/`lowSweepReject` (also not `isESChart`-gated) — not a gap, a deliberate consistency |
| Cooldown (`canSmartBuy`/`canSmartSell`) | **STRATEGY-SPECIFIC GATE** | Not applied — these are Phase 5/6 display-only context booleans, not signals; cooldown belongs to the canonical signal path only |
| Grade (`buyGrade`/`sellGrade`) | **GRADE INPUT** | Unrelated, untouched |

**No new strategy family was created.** These booleans do not feed `canonicalBuy`/`canonicalSell`, `buySignal`/`sellSignal`, any score, or any alert — confirmed via diff (see Part 4). Rejection remains exactly what Phase 3's correction established: a detection/support layer, not a strategy.

---

## PART 4 — PHASE 5 LABEL INTEGRATION (implemented)

The ten Phase 5 classification variables were updated to use the new source-specific booleans in place of the old generic-OR expressions:

```pine
// before (Phase 5, false-attribution risk):
pdhClass = (highSweepReject and (nearPDH or sweptPDH)) ? "REJECTION" : sweptPDH ? "SWEEP" : nearPDH ? "TEST" : "NONE"

// after (Phase 6, source-specific):
pdhClass = pdhReject ? "REJECTION" : pdhSweep ? "SWEEP" : pdhTest ? "TEST" : "NONE"
```

Asia/London/Overnight gained a genuine `REJECTION` tier for the first time (previously capped at `TEST`/`SWEEP` only):

```pine
asiaHighClass = asiaHighReject ? "REJECTION" : asiaHighSweep ? "SWEEP" : asiaHighTest ? "TEST" : "NONE"
```

Priority order unchanged: `REJECTION > SWEEP > TEST > NONE`. `f_interactionLabel()` (Phase 5) and its expiry/dedup behavior are completely untouched — only the classification *inputs* changed, not the labeling mechanism. These remain context labels only; nothing here can produce a BUY or SELL.

---

## PART 5 — BUY/SELL SIGNAL-FLOW AUDIT (no eligibility changed)

**Data caveat, stated plainly:** `data/donna_signal_log.json` (94 entries, all dated 2026-07-06) predates every Phase 1–6 Pine change (Phase 1 was built 2026-07-13) and reflects the indicator version running *before* `canonicalBuy`/`canonicalSell` existed. The live TradingView cloud script has not been updated with any of these phases' code (by explicit instruction throughout). So this log cannot show live `canonicalBuy`/`canonicalSell`/`canonicalBuyNew` firing counts — no such data exists yet. Where the log's fields correspond to logic Phases 1–6 have **not** touched (ORB's own gates, PROS's own phase progression), it remains valid evidence; where it reflects the pre-canonical `donnaCommand` scenario engine, it is background context only, not a canonical-state measurement.

### ORB path
`orbPassMidRejectBull/Bear`, `orbPassLiqRejectBull/Bear`, `orbPassEdgeRejectBull/Bear` (each gated by `orbTradingWindow = orbLive and orbIsActive and isESChart and not orbDead`) → `orbBuyPass`/`orbSellPass` → `orbBuySignal`/`orbSellSignal` (+ `canSmartBuy`/`canSmartSell`, 20-bar cooldown) → `buySignal`/`sellSignal` → `canonicalBuy`/`canonicalSell` → `canonicalBuyNew`/`canonicalSellNew` → `plotshape` → `alertcondition` → bridge (`CANON_BUY`/`CANON_SELL`) / dashboard (`novaStateText` via `canonicalSignalState`).

- **Candidates:** `orb_signal` was `false` in 94/94 logged cycles (65 MNQ, 29 MES). This field reflects ORB logic untouched by any phase, so it remains valid evidence today.
- **Most common gate failure:** the instrument gate (`isESChart`) accounts for 65/94 (69%) structurally — MNQ can never pass `orbTradingWindow` at all, by design, confirmed intentional in an earlier phase. For the 29 MES cycles, `orb_state` never once reached `ORB_READY`/`ORB_RETESTING`/`ORB_ACCEPTED_*` in this sample (`ORB_INACTIVE` 56, `ORB_FAILED` 23, `ORB_EXPIRED` 15 across all 94) — meaning even on the eligible instrument, this particular sample window never got past ORB's own session-timing/failure gates.
- **Cooldown:** `canSmartBuy`/`canSmartSell` (20-bar) — cannot be evaluated as a bottleneck from this sample since no cycle got far enough to reach it.
- **Instrument restriction:** confirmed intentional (re-confirmed here, not re-litigated).
- **Chart display:** once `orbBuySignal`/`orbSellSignal` fires on a future ES/MES session, the full path to a visible marker now exists (Phase 2) and is unobstructed by anything in Phases 3–6.

### PROS path
`prosLegValidBull/Bear` (displacement leg) → `prosRejectionBull/Bear` (fib-zone rejection) → `prosContinuationBull/Bear` (confirmation close beyond the rejection candle's reference level) → `prosBuySignal`/`prosSellSignal` (+ cooldown) → `buySignal`/`sellSignal` → canonical.

- **Candidates:** `pros_phase` (Python-side classification, correlated with but not identical to the raw Pine booleby) shows `OTE_APPROACHING` 68/94 (72%) — displacement has occurred, price hasn't yet tagged/rejected the fib zone. `BUILDING` 7, `ACCEPTED_CONTINUATION` 6, `SETUP_READY` 4, `OTE_TAGGED` only 1/94 (1%), `NONE` 8.
- **Most common gate failure:** the rejection→continuation confirmation is a genuine two-stage event (`prosRejectionBull` must fire, *then* a **later**, separate bar must close beyond that specific candle's high before `prosContinuationBull` fires) — this is why so few cycles progress past "approaching": most of a session is spent in the approach phase by construction, not because of an over-restrictive gate. This matches the already-documented "PROS requires draw independence" finding (`project_draw_validation.md`).
- **Cooldown:** same 20-bar shared cooldown; not evaluable as a bottleneck from this sample for the same reason as ORB.
- **Instrument/session restriction:** PROS has no `isESChart` gate — legitimately available on both MNQ and MES, confirmed by code (no instrument check anywhere in the PROS block).
- **Chart display:** unobstructed by Phases 2–6, same as ORB.

### ICT — a discrepancy worth flagging, not fixed here
`buySignal := orbBuySignal or ictBuySignal or prosBuySignal` (and the SELL mirror) is the **original, untouched, pre-Phase-1** definition — `ictBuySignal`/`ictSellSignal` (the ICT step-model signal) has always been a third OR-branch feeding `buySignal`/`sellSignal`, and therefore `canonicalBuy`/`canonicalSell`, today. `canonicalStrategy = strategy_family`, which can independently classify a signal as `"ICT"` when the ICT branch is what fired. This means the current code can still produce an ICT-attributed canonical signal, chart marker, and alert — despite the user's Phase 3 correction stating "valid strategy families are ORB and PROS only." **This is a pre-existing condition, not something any of Phases 1–6 introduced** (verified: this exact line is part of the original untouched pre-2214 region, unchanged since before this entire engagement) — surfaced here as a finding, not altered, since removing `ictBuySignal` from `buySignal`'s definition would itself be a BUY/SELL eligibility change, explicitly out of scope for this phase. **NEEDS USER DECISION**: should ICT be treated as a valid third family (contradicting the stated architecture), demoted the same way RP was, or left as-is with documentation updated to acknowledge it? Not changed pending an answer.

### Overall scarcity assessment
Based on the available (pre-canonical) evidence plus static code-path tracing of logic unchanged since: scarcity is explained by a mix of **(a) intentional instrument restriction** (ORB on MNQ), **(b) legitimate multi-stage confirmation requirements** (PROS's two-stage rejection→continuation), and **(c) a sample window that simply didn't contain qualifying setups** for ORB even on the eligible instrument — not by contradictory gates, unreachable conditions, or a state-mismatch bug. No cooldown-suppression evidence either way (no cycle in this sample got close enough to test it). This is the same conclusion the original audit reached; nothing in Phases 1–6 has changed the underlying gate behavior for ORB or PROS.

---

## SAFEST NEXT IMPLEMENTATION STEPS (proposed, not started)

1. Resolve the two **NEEDS USER DECISION** items above (the `close < high[1]`/`close > low[1]` omission; the ICT-as-third-family discrepancy) before any further signal-flow change.
2. If desired, get fresh live signal-log data reflecting the actual canonical pipeline — requires pushing the current Pine source to the live chart (a separate, explicit decision, not assumed here).
3. Any change to ORB/PROS/ICT eligibility, cooldown, or instrument gates remains a distinct, separately-approved decision — this phase intentionally did not touch any of them.
