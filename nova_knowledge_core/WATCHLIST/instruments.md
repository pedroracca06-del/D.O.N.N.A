# Instruments — What to Assess Per Market

**Last updated:** 2026-05-30

---

## Instrument Tiers

| Tier | Instruments | Role |
|---|---|---|
| **Primary** | ES / MES | All entries taken here |
| **Secondary** | NQ / MNQ | Directional correlation context |
| **Macro context** | DXY, Gold, Oil, VIX | Risk regime and environment [INFERRED layer] |

Items labeled **[INFERRED]** are not sourced from Evan or RP transcripts — they are general market knowledge applied to the NOVA framework.

---

## ES / MES — Primary Execution Instrument

**Source:** All transcripts. All strategy rules are built for ES/MES.

| What to check | When | Notes |
|---|---|---|
| Previous day high (PDH) | Before 09:00 ET | Primary draw above |
| Previous day low (PDL) | Before 09:00 ET | Primary draw below |
| Overnight high and low | Before 09:00 ET | Untested session highs/lows — valid targets/entry levels |
| Asia and London session highs/lows | Before 09:30 ET | Untested levels are the fallback ORB targets |
| ORB range (08:00–08:15 ET candle) | Lock at 08:15 | High / low / midpoint — fixed for session |
| IB high and low (09:30–10:30 ET) | Lock at 10:30 | Primary draw for PROS setups |
| Spread at open | 09:30 ET | Must be ≤ 2pts to proceed |
| Volume at 09:30 on 1m chart | 09:30 ET | Must be > 1,000 to proceed |

**Preferred timeframes:** 15m (structure), 5m (confirmation), 1m (entry timing)
**Preferred instrument:** MES for position sizing precision. ES for reading institutional footprint.

---

## NQ / MNQ — Secondary Correlation

**Source:** `reaction_setups.md` (RP confirms NQ works with same strategy). `nova_strategy_core.json` watchlist.

| What to check | Notes |
|---|---|
| Direction at 09:30 relative to its own ORB | Does NQ break in the same direction as ES? |
| Is NQ aligned with ES? | Alignment = stronger directional bias; divergence = caution flag [INFERRED] |
| NQ making new highs/lows vs. ES | Relative strength/weakness as context [INFERRED] |

**Note:** NQ can be traded with the same PROS/ORB framework (RP confirms). Not the primary focus — ES is preferred for simplicity. NQ is monitored for context unless an explicit NQ setup is being taken.

---

## Gold — Macro Context

**Source:** RP confirms Gold works with ORB strategy (`reaction_setups.md`). Macro correlation is [INFERRED].

| What to check | Notes |
|---|---|
| Direction at NY open | Risk-on (Gold down) vs. risk-off (Gold up) [INFERRED] |
| Breaking above / below prior day range | Context for broader risk environment [INFERRED] |
| ORB structure if running Gold setups | Same 08:00–08:15 range logic applies — RP confirmed |

**Primary use:** Macro sentiment context. Secondary use: active ORB setup instrument if conditions warrant.

---

## Oil (CL) — Macro Context [INFERRED]

**Source:** Not in transcripts. General market knowledge.

| What to check | Notes |
|---|---|
| Direction at NY open | Rising oil = potential inflation concern / risk complexity |
| Major move > 2% | Can affect equity sentiment and increase volatility |
| Inventory data release timing | If within trading window — caution flag |

**Use:** Background context only. Not an execution instrument in this system.

---

## DXY — Dollar Context [INFERRED]

**Source:** Not in transcripts. General market knowledge.

| What to check | Notes |
|---|---|
| DXY direction at NY open | Strong dollar = equity headwind in risk-off environments |
| DXY breaking above/below key level | May signal macro regime shift |
| Alignment with ES direction | DXY up + ES up = risk-on strength; DXY up + ES down = flight to safety |

**Use:** Background context only. Helps interpret whether ES moves are organic or macro-driven.

---

## VIX — Volatility Context [INFERRED]

**Source:** Not in transcripts. General market knowledge.

| What to check | Notes |
|---|---|
| VIX level at open | Elevated VIX = wider price swings, larger wicks, less clean setups |
| VIX > 20 | Increased uncertainty — session quality may be degraded |
| VIX > 30 | High-volatility environment — stops may need to be wider; setup quality harder to read |
| VIX spiking intraday | Potential news-driven volatility entering — monitor macro for catalyst |

**Use:** Session quality modifier. High VIX is a soft degradation flag — see `session_quality.md`.

---

## Macro Events — Economic Calendar

**Source:** `nova_strategy_core.json`

| Event | Impact |
|---|---|
| FOMC (Fed rate decision / minutes) | Hard block if within 30 min of entry |
| CPI (Consumer Price Index) | Hard block if within 30 min |
| NFP (Non-Farm Payrolls) | Hard block if within 30 min |
| GDP | Hard block if within 30 min |
| Fed speaker (scheduled) | Caution — can cause sharp intraday moves |
| Any high-impact event within trading window | Evaluate timing; soft block or hard block depending on proximity |

**Morning action:** Check calendar before 08:00 ET. Classify the day as Green / Yellow / Red before touching the chart.
