# Three Reaction Setups

**Sources:** `TRANSCRIPTS_RAW/orb_rp_001.txt` · `TRANSCRIPTS_RAW/orb_rp_002.txt` · `TRANSCRIPTS_RAW/orb_rp_003.txt`
**Extracted:** 2026-05-29

---

## Overview

RP defines three setups, all based on **price reacting at a key liquidity level**. The setups are not about predicting where price will go — they are about waiting for the market to show you a reaction and then participating in it.

> "Once you have your levels marked, you do nothing. You simply wait for price to come to one of your levels and show you a reaction to which you then take a trade off of it."

---

## Setup 1 — Bounce (Long)

**What it is:** Price reaches an untested session low and shows a rejection candle — buyers defend the level.

**Direction:** Long
**Level type:** Untested session lows, PDL, weekly lows

**Entry logic:**
1. Drop to 5m and 1m when price approaches the untested low
2. Look for a **strong rejection candle**: long lower wick touching the level, candle body closing **above** the level
3. The wick = sellers pushed below the level but could not hold it; buyers rejected it
4. Close back above the level = buyers are now in control
5. Enter on the candle closure above the level

> "What I'm looking for is a strong rejection candle, meaning a candle with a long lower wick that touches the level, but does not close below it. That wick tells me that sellers pushed the price below that level, but they were not able to keep it below that level because buyers stepped in and rejected it. The close back above the level shows me that buyers are now in control."

**Parameters:**
- Stop: ~10 points
- Target: 30–40 points
- R:R: 1:3 or 1:4

**Level failure rule:** If price blows straight through the level with no wick, no hesitation, no reaction — the level is weak. Delete it. Move to the next untested low.

> "If price comes to a level and blows straight through it without any reaction, no hesitation, no wick, no sign of respect, that level is weak. Delete it and look for the next untested low."

---

## Setup 2 — Rejection (Short)

**What it is:** Price reaches an untested session high and shows a rejection candle — sellers defend the level.

**Direction:** Short
**Level type:** Untested session highs, PDH, weekly highs

**Entry logic:**
1. Drop to 5m and 1m when price approaches the untested high
2. Look for: price touches the level, fails to **close above** it on 5m and 15m
3. A single 1m candle closure above is not sufficient — 5m and 15m must show no closures above
4. Enter when the level is confirmed as holding

> "Price hit this level and then failed to close above it."
> "Key thing here is that we only had one candle closure above it on the 1 minute time frame. But on the 5 minute and on the 15th, we didn't have any candle closures. Meaning we can go ahead and enter some shorts."

**Parameters:**
- Stop: 10 points
- Target: 30–40 points
- R:R: 1:3 or 1:4

**Level failure rule:** If price breaks straight through an untested high with no rejection, no wick, no sign of defense — the level is weak. Move on.

**Difference from Bounce:** Mechanically identical, mirrored — rejection is at highs (short), bounce is at lows (long). Same confirmation logic, same parameters.

---

## Setup 3 — Break and Retest (Preferred)

This is RP's primary setup. Fully documented in `orb_break_retest.md`.

**Summary:**
- Price breaks above or below a key level (the 8:00–8:15 range)
- Price retests the midpoint of the level
- Entry in the direction of the break
- Stop: 5–6 points beyond the zone boundary
- Target: 1:3

---

## Fallback When ORB Never Retests

If the 8:00–8:15 zone never gets retested after the NY open, the ORB entry setup does not exist for that session. In that case, fall back to **untested session high/low setups** (bounces and rejections):

> "For whatever reason, if the 8 a.m. zone just never gets retested, this is what I look for. I'm looking at the untested highs and lows of London session, Asia session, and New York session. When the 8 a.m. zone doesn't get tested, what I will do is I will look for longs off of an untested low, or shorts off of an untested high."

The ORB is the **primary** setup. Session highs/lows are the **backup**. They are not taken simultaneously — ORB takes precedence when it sets up.

---

## Reported Statistics (from RP source)

| Metric | Value | Context |
|---|---|---|
| Win rate | ~62% | Stated across the 8am break/retest strategy |
| Minimum profitable win rate at 1:4 R:R | 20% (3 of 10) | "You only need to win three out of 10 trades to be profitable" |
| Preferred R:R | 1:4 | 10pt stop, 40pt target |

**NOTE:** These statistics are stated by RP and have not been independently verified. Treat as directional context.

---

## Instrument Applicability

- **Primary:** ES futures
- **Also works:** NQ, Gold (confirmed by RP with caveat)
- Recommendation: stick to ES for simplicity

> "A lot of people ask me if this strategy works for other assets, and the answer is yes. I have seen people find success with gold and with NQ, but I just traded on ES, so I recommend that you stick to ES as well to keep it simple."

---

## Lower Timeframe Confirmation

All three setups use lower timeframe confirmation to time entry. See `candle_closure_rules.md` for the full definition of candle closure vs. wick touch.

| Timeframe | Role |
|---|---|
| 15-minute | Structural authority — decisive for level validation |
| 5-minute | Primary execution confirmation — no closures on wrong side |
| 1-minute | Entry timing — identifies reaction candle; one 1m closure alone is insufficient |

> "I like to rotate between the 1 minute, the 5 minute, and the 15-minute so that I can still find really strong levels while still having those aggressive scalping, sniper entries."

> "A quick rule of thumb is that the lower the time frame you go, the riskier your trade will be because lower time frames don't show us that much data, but the better entries you will have."

**Key rule:** A single 1-minute candle closure on the wrong side of a level does not invalidate the setup if the 5m and 15m show no closures. The 5m and 15m are the decisive timeframes.

**DISCRETIONARY:** RP does not define a specific named candle pattern (engulfing, pin bar, etc.). He reads for rejection wicks and candle closure direction as described — no further pattern requirement stated.

---

## Trend Identification — Critical Filter

RP explicitly states a trade failure caused by ignoring the higher-timeframe trend:

> "My mistake was that I failed to identify the trend. The key thing with this strategy is you want to make sure you are around clear lows and clear highs. This was not a clear low — this low was right in the path of this downtrend. We had lower high, lower high, another lower low, lower high. So I failed to identify the trend."

**Rule derived from this example:**
- Do not take a **bounce long** at a level that is embedded in a clear downtrend (lower highs, lower lows)
- Do not take a **rejection short** at a level embedded in a clear uptrend
- The level must be at a **structurally significant boundary**, not mid-range in a trending move

**DISCRETIONARY:** "Clear" trend is not numerically defined. RP uses visual structure (higher highs/higher lows or lower highs/lower lows pattern) to assess.
