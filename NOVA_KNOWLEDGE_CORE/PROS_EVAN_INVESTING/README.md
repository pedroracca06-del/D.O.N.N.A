# PROS — Evan Investing Knowledge Base

Strategy knowledge extracted from Evan Investing source material.
Do not modify without a source transcript to back the change.

---

## Files

| File | Contents |
|---|---|
| `ote_logic.md` | FIB settings, OTE levels (0.618–0.705–0.786), fib drawing direction, entry behavior, limit order validity, stop placement, target selection |
| `stdv_logic.md` | Standard deviation projection levels (-0.27 to -4.0), OTE+StdDev relationship, what STRETCHED means, StdDev as quality filter — ICT-sourced + NOVA observed (Evan direct source unavailable) |
| `manipulation_leg.md` | Manipulation leg definition, identification, where they form, what disqualifies a leg |
| `premium_discount.md` | Premium/discount framework, why the market retraces into OTE, mechanical explanation |
| `initial_balance_draw.md` | IB window definition by session, IB as draw on liquidity, statistics, early entry conditions |
| `continuation_and_exhaustion.md` | Continuation sequence, confirmation signals, exhaustion conditions, structure break as confirmation |
| `invalidation_and_no_trade.md` | Invalidation conditions, no-trade environments, bias shift / structure invalidation |
| `session_logic.md` | NY AM vs Asia vs London, pre-market context, session trade timing |

---

## Sources Ingested

| File | Topics |
|---|---|
| `pros_ote_stdv_001.txt` | OTE, Initial Balance, draw on liquidity, manipulation leg, continuation sequence, session logic |
| `pros_fibs_002.txt` | FIB settings, fib levels (0.618/0.705/0.786), fib drawing direction, premium/discount, manipulation leg definition, limit order entries, why fibs work |

---

## Gaps — Requires Additional Sources

| Concept | Status |
|---|---|
| Standard deviation exact implementation (Evan-specific) | Partially resolved via ICT web research + NOVA indicator observation. Working model documented in `stdv_logic.md`. Evan's specific thresholds remain unknown. |
| Session entry cutoff times | Not defined |
| Numeric execution quality grading | Not present |
| PROS + ORB interaction rules | Not covered in these sources |

---

## Conventions

- **DISCRETIONARY** labels mark concepts that are judgment-based in the source material
- Rules without a direct quote are labeled as inferred
- Nothing is invented — if a concept is unclear, it is listed under Gaps
