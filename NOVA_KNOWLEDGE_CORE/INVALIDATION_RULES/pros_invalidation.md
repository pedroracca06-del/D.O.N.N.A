# PROS Invalidation Rules

**Sources:** `TRANSCRIPTS_RAW/pros_ote_stdv_001.txt` · `TRANSCRIPTS_RAW/pros_fibs_002.txt` · `nova_strategy_core.json` · user-defined rules
**Last updated:** 2026-05-30

---

## Hard Invalidations — Do Not Trade

A single hard condition met = setup is off. No override, no discretion.

| # | Condition | Source |
|---|---|---|
| H1 | **No IB draw established.** IB high/low not locked or directional draw is ambiguous after window closes. | `initial_balance_draw.md` |
| H2 | **Price closes beyond the displacement base.** The origin of the expansion leg is violated — the directional thesis is broken. | `nova_strategy_core.json` |
| H3 | **Structure shifts against bias before OTE is reached.** New opposing expansion establishes a fresh directional leg. The prior setup no longer exists. | `invalidation_and_no_trade.md` |
| H4 | **Opposing expansion forms during retracement.** Price does not pull back — it expands in the opposite direction. The manipulation leg is cancelled. | `nova_strategy_core.json` |
| H5 | **No clear manipulation leg.** Cannot anchor the fib without a clean, measurable expansion leg. No OTE zone can be defined. | `manipulation_leg.md` |
| H6 | **IB range too small or price action is choppy.** No directional draw worth targeting. No valid manipulation leg can form inside a tight, overlapping range. | `invalidation_and_no_trade.md` · `manipulation_leg.md` |
| H7 | **Setup forming outside personal trading window (post-11:00 ET).** Session is closed for new entries. | `nova_strategy_core.json` · user rule |
| H8 | **Major macro event within 30 minutes** (FOMC, CPI, NFP, GDP). Execution risk is unquantifiable. | `nova_strategy_core.json` |
| H9 | **Daily loss at or beyond 2%.** Session is over regardless of setup quality. | User rule |
| H10 | **Already in a position.** Single-position architecture — no stacking. | `nova_strategy_core.json` |

---

## Soft Degradations — Grade Downgrade

Soft conditions reduce the setup quality grade by one tier. If a setup is already borderline (C), a soft condition makes it a D.

| # | Condition | Effect | Source |
|---|---|---|---|
| S1 | **Retracement only reaches 0.5 fib.** OTE zone (0.618–0.705) not tapped. Entry at 0.5 is statistically suboptimal — "probably would have got break even or took a loss." | Grade –1 | `ote_logic.md` |
| S2 | **Retracement exceeds 0.786 without clear structural reason.** Outer boundary breached. Setup is not yet fully invalidated but confidence is significantly reduced. | Grade –1 | `nova_strategy_core.json` |
| S3 | **Single confluence factor at OTE.** Strong setups have 2+ stacked factors (e.g., TDO + VWAP band + fib level). A lone fib tap with no other confluence is thin. | Grade –1 | `ote_logic.md` |
| S4 | **Internal high/low not swept cleanly into OTE.** The liquidity sweep into the zone strengthens the entry. Absence of sweep means the manipulation leg may be incomplete. | Grade –1 | `manipulation_leg.md` |
| S5 | **IB draw not yet confirmed.** IB window still open — range is still developing. Entry can be valid (Evan does this) but requires high confidence and is explicitly discretionary. | Grade –1 | `initial_balance_draw.md` |
| S6 | **Multiple failed rejections at the same OTE zone.** Each failed attempt at the same zone reduces its remaining edge. If two rejections have already failed, the zone is exhausted. | Grade –1 | `nova_strategy_core.json` |
| S7 | **PROS setup conflicts with unresolved ORB context.** If ORB auction is still active and unresolved, a PROS setup in the same window needs alignment. Conflicting signals without resolution = degraded. | Grade –1 | `nova_strategy_core.json` |
| S8 | **Session timing in the later half of the window (10:30–11:00 ET).** Setup is valid but execution edge is reduced as the session winds down. [INFERRED — consistent with session cutoff logic] | Grade –1 | Inferred |

---

## Mid-Trade Invalidation

Conditions that invalidate a setup **after entry** — triggers stop management or exit:

| Condition | Action |
|---|---|
| Internal high (for longs) gets swept but price then manipulates back above it | Bias questioned — evaluate whether structure has shifted; trail stop to entry at minimum |
| Price fails to deliver toward the IB draw within session window | Hold only if price is not actively invalidating; exit before 11:00 ET |
| Opposing expansion forms while in trade | Exit — directional thesis is broken |
| Structure breaks in the trade direction | Trail stop to structural level — near-zero risk position |
