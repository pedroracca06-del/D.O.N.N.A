# OTE Logic — Evan Investing

**Sources:** `TRANSCRIPTS_RAW/pros_ote_stdv_001.txt` · `TRANSCRIPTS_RAW/pros_fibs_002.txt`
**Extracted:** 2026-05-29

---

## What OTE Is

OTE = Optimal Trade Entry.
The fib retracement zone drawn over the **manipulation leg** (the expansion / displacement move).
It is the pullback destination — where price is expected to retrace before continuing in the original direction.

OTE is **not** an entry trigger on its own. It is an **entry zone** requiring confluence confirmation.

---

## FIB Settings (Evan's Chart Setup)

Levels used: **0, 0.5, 0.618, 0.705, 0.786, 1**
Display: white lines, no background, no price labels — levels only.

> "I have 0, 618, 1, 76, 705, and .5 all in white. I have the background turned off. I have the prices turned off. I just have the levels on here."

---

## OTE Fib Levels

| Level | Role |
|---|---|
| 0.5 | Suboptimal — entries here frequently result in break even or loss |
| 0.618 | **Primary OTE zone** — most statistically reliable level |
| 0.705 | **Core OTE zone** — valid, often stacks with 0.618 |
| 0.786 | Extended OTE — valid but outer boundary; less reliable than 0.618–0.705 |

> "We only tap it at 0.5. So if you did take that, you probably would have got break even or took a loss on that."

> "Preferably 618. I use this one the most because it is just the best and it just statistically works the best."

> "It actually tapped 786. Boom. Get tagged in. Target the lows." — 0.786 shown as valid in one example.

> "We have very low statistics of price coming back up to this point." — referring to a level beyond 0.786; implies 0.786 is the outer boundary of the OTE range.

The **0.618–0.705 band** is the primary actionable OTE zone.
**0.786** is the outer boundary — valid but treat as extended, not preferred.
**0.5** is insufficient on its own — do not treat it as OTE.

---

## How OTE Is Applied

1. **Identify the manipulation leg** — the impulsive directional move that establishes bias and range
2. **Draw fib over the manipulation leg:**
   - SHORT setup: draw from HIGH to LOW of the down move
   - LONG setup: draw from LOW to HIGH of the up move
3. **Wait for price to pull back into the 0.618–0.705 zone** (0.786 as outer boundary)
4. **Look for confluence** at the zone before entering
5. **Enter with directional bias confirmed** — targeting the draw on liquidity (IB high/low, PDL/PDH, equal highs/lows)

> "You draw out the top to the bottom of the move in a short position or the bottom to the top in a long position."

**Limit orders are valid at OTE.** Evan explicitly states a limit can be set at 0.618 or 0.705 without waiting for a candle-based signal, provided bias and draw are clear.

> "You could literally just set a limit order. Even on 618, you could put your stops maybe above this high to be safe and then target something like this."

> "You don't need to wait for any other confluences. You could just set a limit on that order."

**DISCRETIONARY:** The decision to use a limit order vs. waiting for a candle reaction is framed as personal preference. Limit orders carry more risk of entry before full OTE tap; candle reactions provide more confirmation. Both are described as valid.

---

## Confluence at OTE

Confluence mentioned in transcript that strengthens an OTE entry:

| Factor | Notes |
|---|---|
| True Day Open | Aligns with OTE zone |
| VWAP / Bottom Band of VWAP | Stacks with OTE level |
| Stacked fib levels | Multiple fibs converging |
| Previous Day Low / High | External draw in same direction |
| Equal Highs / Equal Lows | Liquidity draw aligning with OTE |
| Internal structure sweep | Internal high/low swept into OTE zone |

> "We have two stacked levels. We have true day open right here. As well as this bottom band of VWAP. We have everything lining up perfectly in this range."

**DISCRETIONARY:** The weighting and selection of confluence factors is discretionary. Transcript does not define a minimum confluence count.

---

## OTE Entry Behavior

- Entry is taken **at or within the OTE zone** after confluence is identified
- Do not enter before the manipulation leg is clear and measurable
- Entry can be taken before the IB window closes if bias and confluence are strong enough

> "Even though 10:30 did not form yet, we still have this high and bound. We still have this low and bound. And we are respecting these levels... I can look for a long off of this level."

**DISCRETIONARY:** Early entry (before IB window closes) is described as valid when the trend, confluence, and manipulation leg are all clearly established. It requires high confidence.

---

## Stop Placement

| Condition | Stop Size |
|---|---|
| Normal volatility | 30 points (ES/MES) |
| High volatility day | 40 points (ES/MES) |
| Asia session | ~20 points (lower volatility) |
| After structure break | Trail stop to internal high/low (near-zero risk) |

> "I typically do like a 20 to 30 point stop. 30 points would probably be better. Maybe 40 in this case cuz it was pretty volatile today."

> "My stops were immediately put to this high right here, which was literally 1.25 points."

Stop trail is triggered when a **structural low (or high) breaks in the trade's direction**, confirming delivery has begun.

---

## Target Selection

Primary targets in priority order as stated in transcript:

1. **Initial Balance high or low** (the session draw)
2. **Equal highs / equal lows** (liquidity pools)
3. **Previous Day Low / High** (external draw)

> "You could either TP right at the initial balance low or you could TP at a further draw if your draw is going in that direction."

**DISCRETIONARY:** Choice of TP level is discretionary based on how confident the trader is in the draw. Transcript does not mandate a fixed rule.
