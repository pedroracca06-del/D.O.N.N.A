# ORB — Break and Retest Setup

**Sources:** `TRANSCRIPTS_RAW/orb_rp_001.txt` · `TRANSCRIPTS_RAW/orb_rp_002.txt` · `TRANSCRIPTS_RAW/orb_rp_003.txt`
**Extracted:** 2026-05-29

---

## Overview

RP's primary and favorite setup. Combines the opening range definition, midpoint ownership, and directional continuation logic into a single clean framework.

> "This specific setup combines all of these concepts."

---

## ORB Phase Structure — RESOLVED

The ORB operates in two distinct phases with a hard cutoff:

| Phase | Window | Action |
|---|---|---|
| **Range Construction** | 08:00–08:15 ET | Lock ORB high, low, midpoint. No execution. |
| **Execution Phase** | 09:30 ET onward | Auction interpretation begins. ORB entries valid. |
| **Cutoff** | 11:00 ET | No new ORB entries. Edge considered degraded. |

**No execution before 9:30 ET.** The 8:00–8:15 window exists solely to define the range. Trading during range construction is not part of this framework.

**No new ORB entries after 11:00 ET.** Opening auction logic is only valid during the active NY morning session.

---

## Why the 8:00–8:15 Candle

Three reasons this candle is the anchor level:

1. **Highest volume of any 15-minute window in the trading day** — most orders, most institutional activity, highest liquidity concentration
2. **Creates a clear magnet range** — price will break above, break below, or chop inside it; the range defines the day's battlefield
3. **Removes guesswork** — one candle, three levels (high / low / mid), zero ambiguity

> "When volume is high, it tells you that the levels matter."

**Psychology:** Traders who go long at the range low and short at the range top are trapped when price breaks out. When price retests the range after the break, they exit at break even — that forced exit flow is what drives the continuation.

---

## Range Construction (08:00–08:15 ET)

- Use the **15-minute timeframe**
- Mark the **high** (top wick) and **low** (bottom wick) of the 8:00–8:15 candle as a rectangle
- Enable the **midline** in the rectangle settings — this is the critical execution level
- Recommended midline style: **black, dotted**
- Midpoint = (high + low) / 2
- These three levels — ORB high, ORB low, ORB mid — are fixed for the session

> "Double click this rectangle and make sure that you have checked this middle line feature right here. And what I recommend is having a black midline with a dotted line on it."

---

## Entry Trigger — The Sequence (from 09:30 ET)

```
1. BREAK   — After 9:30 ET: price moves clearly below range low OR above range high
2. RETEST  — Price returns to the MIDPOINT of the rectangle
3. ENTRY   — Trade taken at the midpoint in the direction of the break
4. CONTINUE — Price resumes in the original breakout direction
```

> "It's a break, it's a retest, and then a continuation in the initial direction that we broke out to."

**Directional rule:**
- Break **below** range low → look for SHORT at midpoint retest
- Break **above** range high → look for LONG at midpoint retest

**Bias read at 9:30 ET — three possible states:**

| Price location at 9:30 | Action |
|---|---|
| **Above** the ORB zone | Look for midpoint retest → enter LONG |
| **Below** the ORB zone | Look for midpoint retest → enter SHORT |
| **Inside** the ORB zone (between high and low) | Wait — no setup yet |

> "At 9:30, you will see that price is either above this zone or below this zone. If it's in the middle of the zone, just wait."

- Look for a **clean break — ideally 5 to 10 points beyond the midpoint** at the open
- Do not react to choppy movement before 9:30; wait for the volume and volatility of the NY open

> "I like to wait until 9:30 a.m. Eastern Standard Time and see which direction the market is breaking to. I'm not paying attention to any choppy movement before that."

> "At 9:30, I want to see a clean break, ideally 5 to 10 points below the midpoint."

**Volume filter — mandatory before entry:**
- Check volume on the **1-minute chart** at/after 9:30
- If volume is **under 1,000**, do not trade — volume is too low to confirm institutional participation
- Wait for the volume that comes in at the NY open

> "Even if the setup looks perfect at 8:45, the volume is too low before the open. I check volume on the 1 minute chart. If it's under 1,000, I don't trade."

**Retest confirmation:**
- After the break, price pulls back to the **bottom of the zone** (for shorts) or **top of the zone** (for longs), or to the **midpoint**
- Confirm via **candle closures** on the correct side of the midpoint — see `candle_closure_rules.md`
- Entry taken on the next candle after closure confirmation

> "I want to see candle closures below the midpoint. Just like this, we tap the midpoint and then we continue to close below it. If price is failing to close above the level in any meaningful way, that's my confirmation and I enter on the next candle."

> "We didn't have a single candle closure above this midpoint. We were moving to the downside."

---

## Midpoint — Invalidation vs Confirmation

The midpoint is not just an entry level. It serves a dual role:

| Midpoint behavior | Meaning |
|---|---|
| Price closes **below** midpoint (for longs) | **Invalidation** — setup does not play out |
| Price closes **above** midpoint (for longs) | **Confirmation** — continuation move begins |

> "This midpoint acts as an inflection point. Meaning this midpoint is where the volume either comes in and we get that big move up or it's where the volume dies down and the setup doesn't play out."

> "So this is either our zone of invalidation, meaning if price comes below this zone and closes under it, our setup's not going to play out, or it's our zone of confirmation, meaning when price does actually close above this zone, we are going to get that big move."

Mirror for shorts: closes **above** midpoint = invalidation; closes **below** midpoint = confirmation.

---

## Stop Placement

| Condition | Stop Size |
|---|---|
| Normal conditions | 5–8 points |
| Volatile day or wide opening range | 10 points |
| Hard ceiling | 12 points maximum |

Stop is placed **just outside the zone boundary** — slightly beyond the ORB high or low (not just above/below the midpoint). This absorbs a potential liquidity grab before continuation.

> "I like to have my stop loss at five to eight points placed just on the other side of the level being respected. If the market is super volatile or if the opening range is big, I'll go up to a 10 point stop, but I keep it under 12."

> "Your stop loss goes just outside the zone at 10 points."

---

## Target

| Parameter | Value |
|---|---|
| Preferred R:R | **1:4** (10pt stop → 40pt target) |
| Acceptable R:R | 1:3 |
| Primary target | Nearest **untested session high or low** (Asia/London/NY) |
| Named example | London low targeted in a short trade |
| Secondary target | Previous day high or low |
| If no untested levels nearby | Fixed 20 points |

> "With this strategy, we operate on a strict 1:4 risk-to-reward ratio. This means for every dollar we risk, we are aiming to make $4 back. Your stop loss goes just outside the zone at 10 points, and your take-profit is four times that at 40 points. Sometimes I'll target a 1 to 3 risk-to-reward, but I like to stick to 1 to four."

> "My target is 15 to 20 points, sometimes 30 if my stop loss is bigger, but it's almost always 15 to 20."

**Note on parameter variation:** Stop size (5–12pt) and target (15–40pt) both scale with the size of the opening range and day's volatility. The ratio (1:3 or 1:4) stays constant; the absolute points flex.

---

## ORB Zone as TP Level (When Not Used as Entry)

The 8:00–8:15 range remains a significant liquidity zone even when it never provides an entry setup. When taking trades off untested session highs/lows, the ORB zone can serve as a **take-profit target**.

> "Sometimes if we're not using it to take entries, we will take profit right around this zone because it is a big area of liquidity. You can see the price reversed right when we hit that zone."

---

## Worked Example (SHORT)

1. 8:00–8:15 range formed with high and low
2. At 9:30 ET — price breaks below the range low with no candle closures above midpoint
3. Price retraces back to the midpoint of the rectangle
4. Short entered at midpoint
5. Stop 6 points above the zone boundary
6. Target: 18 points below entry (1:3)
7. Trade hit TP quickly

Result stated: ~18 points = ~$7,500 (position size not stated for this example)

---

## Invalidation

Conditions that invalidate this setup:

| Condition | Notes |
|---|---|
| Entry attempted before 09:30 ET | Execution phase not open — range construction only |
| Entry attempted after 11:00 ET | ORB cutoff — edge degraded, no new entries |
| No clear break of the range high or low | Without a break, there is no setup — price must leave the range |
| Candle closes back inside the range on the wrong side of midpoint | Break is not confirmed; price is back in balance |
| Breakout direction conflicts with clear higher-timeframe trend | Entering a bounce against a clear downtrend is a documented failure mode |
| Retest never occurs | "If price never retests the New York open, we can't take a trade around the New York open" |

---

## Relationship to NOVA ORB Framework

This setup maps to **ORB Entry 1 (E1 — Midpoint Rejection)**:

| NOVA E1 | RP Break and Retest |
|---|---|
| ORB range locked at 08:00–08:15 ET | 8:00–8:15 candle defines range |
| Execution begins at 09:30 ET | Direction assessed at 9:30 ET |
| Price breaks ORB, re-enters, taps midpoint | Break → retest → midpoint |
| Rejection at midpoint confirmed | Entry taken at midpoint |
| Continuation in breakout direction | Continuation in breakout direction |
| No new entries after 11:00 ET | ORB cutoff — edge degraded |
