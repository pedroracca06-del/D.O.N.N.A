# Standard Deviation Logic

**Sources:**
- ICT/SMC framework — `innercircletrader.net`, `writofinance.com`, `theforexgeek.com`, `tradingfinder.com` (web research 2026-05-30)
- NOVA indicator observed output — live chart session 2026-05-29
- Evan Investing direct transcript — **none available** (confirmed permanent gap)

**Labeling convention used in this file:**
- `[ICT SOURCE]` — documented in ICT/SMC literature, web-verified
- `[NOVA OBSERVED]` — seen in NOVA EXECUTION V1 indicator output during live session
- `[INFERRED]` — logical derivation from ICT framework applied to Evan's system; not directly sourced

---

## What Standard Deviation Projection Is

`[ICT SOURCE]`

Standard deviation projections use the **Fibonacci tool anchored to the manipulation leg** to project statistical price targets both for continuations and reversals. The negative extension levels represent multiples of the original swing size — how far price "should" travel if it is delivering normally.

They are used in two ways:
1. **As profit targets** — where price is expected to reach after OTE entry
2. **As a quality/stretch filter** — to assess whether the current expansion is within normal range or overextended

---

## How to Draw

`[ICT SOURCE]`

Anchor the Fibonacci tool to the **manipulation leg** (the displacement/expansion move):

| Setup direction | Anchor from | Anchor to |
|---|---|---|
| Bullish | Low of manipulation leg | High of manipulation leg |
| Bearish | High of manipulation leg | Low of manipulation leg |

The **negative extensions** (below 0 on bearish, above 1 on bullish) represent the SD projection levels — where price is expected to travel after the OTE retracement.

---

## SD Level Map

`[ICT SOURCE]`

| Level | Label | Role |
|---|---|---|
| 0.618 – 0.705 | OTE Zone | Retracement entry area |
| -0.27 | SD1 (short) | First internal target — nearest liquidity pool |
| -0.62 | SD2 | Measured-move continuation point; useful trail stop |
| -1.0 | SD3 | Symmetrical projection — 1× the manipulation leg size |
| -2.0 | SD4 | Full standard deviation expansion — often aligns with session highs/lows |
| -2.5 | SD5 | Extended target — strong trend days |
| -4.0 | SD6 | Maximum projection — weekly bias trades only |

**Primary targets in normal sessions:** -1.0 to -2.0
**Extended targets (strong directional day):** -2.5
**Reversal/exhaustion zone:** -2.0 to -2.5 (price frequently reverses here)

> "When price reaches -2 to -2.5, a retracement or trend reversal is likely."
> "If price surpasses -2.5 and closes beyond, it may continue toward -4."

---

## OTE + StdDev — How They Work Together

`[ICT SOURCE]`

These two concepts operate on different sides of the same trade:

```
Manipulation leg forms
        ↓
Price retraces into OTE (0.618–0.705)  ← ENTRY ZONE
        ↓
Entry taken at OTE
        ↓
Price continues toward SD targets       ← TARGET ZONE
(-0.27 → -0.62 → -1.0 → -2.0)
```

**OTE defines where to enter. SD levels define where to exit.**

They are drawn from the same fib anchor on the same manipulation leg. The retracement side (0 to 1) gives the OTE zone; the extension side (negative numbers) gives the SD targets.

---

## What "STRETCHED" Means

`[NOVA OBSERVED + INFERRED]`

The NOVA EXECUTION V1 indicator displayed `STDV | STRETCHED` during a live session in which:
- The PROS engine showed `RETRACE | DEEP`
- Quality was graded `WEAK`
- Price had retraced significantly without a clean rejection at OTE

Based on this observation and the ICT framework, "STRETCHED" most likely signals one of the following conditions:

| Condition | Interpretation |
|---|---|
| Price has already reached -2.0 to -2.5 SD without an OTE retracement | Expansion is overextended; retracement to OTE is now statistically likely before any further continuation |
| Retracement has gone deeper than 0.705 (approaching 0.786+) | The pullback has consumed more of the expansion than a healthy OTE should; continuation energy may be insufficient |
| The manipulation leg itself was too small to generate a meaningful SD range | Insufficient displacement; SD levels are compressed and unreliable |

When `STDV | STRETCHED` is active in NOVA:
- Setup quality is degraded (`WEAK` or `C` grade)
- Do not enter at OTE — the statistical basis for the continuation is compromised
- Wait for a fresh expansion leg with a clean, un-stretched SD range

`[INFERRED]` The "stretched" flag functions as a **quality disqualifier**, not a reversal signal. It does not predict that price will reverse — it signals that the current setup's continuation probability is reduced below the threshold for a clean entry.

---

## StdDev as a No-Trade Filter

`[INFERRED from ICT framework + NOVA observed behavior]`

| StdDev condition | PROS setup implication |
|---|---|
| Price at OTE, SD not stretched | Clean setup — proceed with normal grading |
| Price at OTE, SD stretched (deep retrace) | Setup quality degraded — treat as C grade or skip |
| Price already at -2.0 SD without OTE retracement | No entry — wait for retrace to OTE first |
| Price beyond -2.5 SD | Potential reversal zone — no continuation entry |

---

## What Is Still Unknown

Evan's exact implementation of StdDev is **not documented in any available transcript**. Specific unknowns:

| Item | Status |
|---|---|
| Exact SD levels Evan uses (does he use -1.0, -2.0, or different levels?) | Unknown |
| Whether "stretched" refers to SD of the manipulation leg or a separate indicator | Unknown |
| The precise mathematical threshold for the "STRETCHED" flag in NOVA EXECUTION V1 | Unknown — only observable in indicator output |
| Whether StdDev is drawn on each individual manipulation leg or from a fixed daily anchor | Unknown |

This file represents the best available reconstruction from ICT source material and observed NOVA indicator behavior. It should be treated as **a working model, not a confirmed source rule**.
