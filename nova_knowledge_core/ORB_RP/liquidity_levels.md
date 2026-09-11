# Liquidity Levels — Key Levels Framework

**Sources:** `TRANSCRIPTS_RAW/orb_rp_001.txt` · `TRANSCRIPTS_RAW/orb_rp_002.txt`
**Extracted:** 2026-05-29

---

## The Core Concept

The entire strategy is built on one concept: **liquidity**.

> "This entire strategy is built on one concept, liquidity. Specifically, trading at key liquidity levels."

Banks and institutions cannot execute large orders at market without moving price against themselves. Instead, they **engineer moves to key liquidity zones** to trigger clustered orders, then execute into that flow.

> "They push price to these key liquidity zones and then they execute. Our job is not to fight the banks. It's to trade with them."

---

## Where Liquidity Clusters

| Level | Why it's a liquidity pool |
|---|---|
| Above yesterday's high | Breakout traders have buy stops here |
| Below yesterday's low | Long traders have stop-losses here |
| Session highs (NY, Asia, London) | Resting orders from session participants |
| Session lows (NY, Asia, London) | Resting stop-losses from session participants |
| 8:00–8:15 AM range midpoint | Retest zone after breakout — trapped positions at break even |

> "Above yesterday's high, where breakout traders have their buy stops, and below yesterday's low, where long traders have their stop-losses. These levels are massive pools of liquidity."

---

## Key Levels to Mark

| Level | Type | Notes |
|---|---|---|
| Previous Day High (PDH) | External draw | Major liquidity pool above |
| Previous Day Low (PDL) | External draw | Major liquidity pool below |
| NY Session High | Session level | Mark as untested until tapped |
| NY Session Low | Session level | Mark as untested until tapped |
| Asia Session High | Session level | Mark as untested until tapped |
| Asia Session Low | Session level | Mark as untested until tapped |
| London Session High | Session level | Mark as untested until tapped |
| London Session Low | Session level | Mark as untested until tapped |
| 8:00–8:15 AM candle high/low/mid | Opening range | Primary ORB setup level |

---

## Untested vs. Tested Levels

**Untested levels are significantly more powerful than tested ones.**

> "You want to use untested levels because everybody who's in a trade from this level has not interacted with price until price comes back up here. Meaning, they can't take a trade down there because then they're at a big loss. But when price comes back up here, they are at break even. So maybe they're exiting their longs causing selling pressure or they're just taking shorts expecting price to go down."

**Why untested levels work:**
- Participants trapped from the original level are sitting at a loss until price returns
- When price returns to the level, those participants are at break even — they exit (adding selling/buying pressure) or initiate new positions in the reversal direction
- This creates a concentration of order flow at the level

**Why tested levels are weaker:**
- Participants have already closed at break even or worse
- The order concentration is gone
- RP showed a previously tested high produced **no reaction**; the untested high produced a strong reaction immediately

> "If you were to use this high, we had no reaction because price already had its reaction to this high down here."

**Practical rule:** Only trade levels that have **not yet been tapped.** Once a level is tagged, it loses its primary power.

---

## Age of Level = Strength

> "The further back a level is, the stronger it is. If an untested low is from 3 days ago, the trader sitting those positions have been holding for 3 days. They are far more desperate to exit than somebody who's only been in a position for 4 hours. More desperation means more orders, meaning a stronger reaction when price hits that level."

| Level age | Relative strength |
|---|---|
| Same session | Baseline |
| Previous day | Stronger |
| 2–3 days old | Strongest |
| Weekly high/low | Extra-strong |

> "This untested low is also the weekly low, meaning it's going to be a very strong level."

Full documentation in `level_strength.md`.

---

## Level Persistence — Multiple Tests

A strong level can produce valid setups across **multiple retests** before losing significance:

> "Look how many times this exact low gets respected. 1, 2, 3, 4, 5, six. You could have taken six different trades off of this level."

**DISCRETIONARY:** RP does not define how many retests exhaust a level. Judgment required. See `level_strength.md` for weakness signals.
