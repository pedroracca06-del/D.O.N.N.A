# Morning Checklist — Pre-Market Preparation Flow

**Last updated:** 2026-05-30
**Personal trading window:** 09:30–11:00 ET

---

## Step 1 — Macro Screen (Before 08:00 ET)

Check the economic calendar for today's scheduled events.

| Check | What to note |
|---|---|
| Any high-impact events today? | FOMC, CPI, NFP, GDP, Fed speakers |
| Event timing relative to 09:30–11:00 ET window | If within window: flag as hard block or caution |
| Event within 30 minutes of 09:30 open? | → Hard invalidation: do not trade the open |

**Output:** Green (no major events), Yellow (event outside window but same day), Red (event within trading window — do not trade).

---

## Step 2 — ORB Range Construction (08:00–08:15 ET)

This is a passive observation window. No execution.

| Action | Detail |
|---|---|
| Switch to 15m chart | Observe the 08:00–08:15 ET candle forming |
| At 08:15: lock the range | Mark ORB high, ORB low, ORB midpoint as a rectangle |
| Enable midline | Midpoint = (high + low) / 2 — this is the critical execution level |
| Note range width | > 15pts MES = wide session flag — see `session_quality.md` |

> "When volume is high, it tells you that the levels matter." — RP

**Output:** ORB high / ORB low / ORB midpoint locked. Range width noted.

---

## Step 3 — Key Level Identification (08:15–09:15 ET)

Mark the structural levels that will serve as draws and targets for the session.

| Level | Source | Priority |
|---|---|---|
| Previous day high (PDH) | Daily chart | High |
| Previous day low (PDL) | Daily chart | High |
| Overnight high / Asia session high | 1h or 15m chart | High |
| Overnight low / Asia session low | 1h or 15m chart | High |
| London session high / low (if formed) | 1h or 15m chart | Medium |
| Equal highs / equal lows visible | 15m chart | Medium |
| ORB midpoint (already locked) | ORB rectangle | High |

> "My target is the London low... the previous day low... or an untested session high or low." — RP

**Output:** Levels marked. Identify which untested highs/lows are the most relevant draws for today.

---

## Step 4 — Pre-Market Bias Read (08:15–09:30 ET)

Observe pre-market price action for directional context. This is not an entry signal — it informs bias.

| Observation | Interpretation |
|---|---|
| Pre-market sweep of overnight lows, then reversal up | Bullish bias forming — manipulation swept shorts |
| Pre-market sweep of overnight highs, then reversal down | Bearish bias forming — manipulation swept longs |
| Choppy, overlapping pre-market range with no sweep | No clean directional bias yet — wait for 09:30 |
| Price sitting above ORB zone entering 09:30 | Likely bullish open |
| Price sitting below ORB zone entering 09:30 | Likely bearish open |
| Price inside ORB zone at 09:30 | Wait — no setup, observe direction |

> "We come down pre-market, we sweep these lows, and then as soon as market opens, we rip to the upside." — Evan

**Output:** Preliminary bias (bullish / bearish / neutral / wait). Not locked in — subject to revision at 09:30.

---

## Step 5 — IB Directional Draw (09:30–10:30 ET, locked at 10:30)

The IB is the session's primary draw. It must be established before any PROS setup is evaluated.

| Action | Timing |
|---|---|
| Observe the first hour price action (09:30–10:30 ET) | Developing — do not lock until 10:30 |
| At 10:30: lock IB high and IB low | Range is fixed for the session |
| Determine directional draw | Is price targeting IB high (bullish) or IB low (bearish)? |
| Check if draw aligns with pre-market bias | Alignment = stronger conviction |

> "If you think price is going to continue higher, then you would trade up to this high." — Evan

**Note:** Entry can be taken before 10:30 closes if bias, manipulation leg, and confluence are all clearly established (Evan confirms this explicitly).

**Output:** IB high / IB low / IB midpoint. Directional draw identified: targeting [HIGH / LOW].

---

## Step 6 — Session Open Assessment (09:30 ET)

At the open, assess the ORB direction and volume before anything else.

| Check | Threshold | Action if failed |
|---|---|---|
| Volume on 1m chart | Must be > 1,000 | Do not trade — wait for volume |
| Price location relative to ORB | Above / below / inside | Inside = wait; above or below = note direction |
| Clean break of ORB? | 5–10+ points beyond midpoint | Less than 5pts = ambiguous — wait |
| Pre-market bias confirmed? | Same direction as ORB break | Alignment = stronger setup |

**Output:** Direction confirmed / not yet confirmed. Volume check passed / failed.

---

## Summary Output Template

Before trading, you should be able to fill this in:

```
Date:
Macro: [Green / Yellow / Red — event name if applicable]
ORB: High [X] / Low [X] / Mid [X] / Width [X pts]
Key levels above: PDH [X], Overnight high [X], London high [X]
Key levels below: PDL [X], Overnight low [X], London low [X]
Pre-market bias: [Bullish / Bearish / Neutral]
9:30 ORB direction: [Above / Below / Inside zone]
Volume at open: [X — pass/fail]
IB draw: Targeting [HIGH / LOW — lock at 10:30]
Session quality: [A / B / C / Degraded — see session_quality.md]
Active strategy today: [PROS / ORB / Both / Standby]
```
