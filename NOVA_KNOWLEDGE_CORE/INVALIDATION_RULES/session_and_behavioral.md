# Session and Behavioral Invalidation

**Sources:** `evan_psychology_001.txt` · `nova_strategy_core.json` · user-defined rules
**Last updated:** 2026-05-30

---

## Session Hard Invalidations

Conditions that end the trading session entirely — no further entries regardless of setup quality.

| # | Condition | Source |
|---|---|---|
| SH1 | **Daily loss at or beyond 2% of account.** Hard stop. Session is over. | User rule |
| SH2 | **Post-11:00 ET.** Personal trading window is closed. No new entries. Adjustable over time but the default is firm. | User rule · `nova_strategy_core.json` |
| SH3 | **Major macro event within 30 minutes** (FOMC, CPI, NFP, GDP, or any scheduled high-impact release). | `nova_strategy_core.json` |
| SH4 | **Two trades already taken today.** Daily maximum reached. | User rule · `session_discipline.md` |

---

## Behavioral Hard Blocks

Internal states that block any entry even when the technical setup is valid.

| # | Condition | Why |
|---|---|---|
| BH1 | **Considering Trade 2 after a loss or break-even on Trade 1.** Trade 2 is only available after a win. This is a hard system rule, not discretion. | User rule |
| BH2 | **In revenge trade state.** Actively trying to recover a loss. The goal has shifted from system execution to money recovery — every trade from this state is a forced trade. | `behavioral_blocks.md` |
| BH3 | **In FOMO state.** Considering entry because price is moving, not because the defined setup criteria are met. | `behavioral_blocks.md` |
| BH4 | **No clean setup exists.** We don't trade because we have to. We trade because we can. Forcing a trade is worse than no trade. | User rule · `session_discipline.md` |
| BH5 | **Spread > 2pts on MES at entry.** Execution quality is compromised. | `nova_strategy_core.json` |

---

## Session Soft Degradations

Conditions that reduce the quality ceiling of the entire session — not a hard block, but the best possible grade for any setup this session is capped lower.

| # | Condition | Effect | Source |
|---|---|---|---|
| SD1 | **Pre-market range is very small / choppy.** No directional sweep has formed. Manipulation leg may not materialize cleanly. | Session grade –1 | `manipulation_leg.md` · `invalidation_and_no_trade.md` |
| SD2 | **ORB range > 15pts.** Wider than normal — stops must be larger, risk/reward math is less clean. | Session grade –1 | `nova_strategy_core.json` |
| SD3 | **IB range too tight to define a clear draw.** No valid directional target for PROS setups. | Session grade –1 | `initial_balance_draw.md` |
| SD4 | **Conflicting PROS and ORB signals without resolution.** Both strategies pointing in different directions within the same session window. | Session grade –1 | `nova_strategy_core.json` |
| SD5 | **Macro event scheduled but more than 30 minutes away.** Not a hard block but introduces uncertainty — size down or wait for event to pass before seeking entries. [INFERRED — consistent with strategy core macro logic] | Caution flag | Inferred |

---

## Decision Logic Summary

```
Before any trade, run these checks in order:

1. SESSION CHECK
   — Is it within 09:30–11:00 ET?          → No: stop
   — Is daily loss < 2%?                    → No: stop
   — Is trade count < 2?                    → No: stop
   — Is macro event > 30min away?           → No: stop

2. BEHAVIORAL CHECK
   — Is this Trade 2 after a loss/BE?       → Yes: stop
   — Am I in revenge or FOMO state?         → Yes: stop
   — Is there actually a clean setup?       → No: stop

3. STRATEGY CHECK
   — PROS: run pros_invalidation.md checks
   — ORB: run orb_invalidation.md checks

4. GRADE
   — Apply soft degradations
   — If grade is D: stop
   — If grade is C: reconsider; high bar to proceed
```
