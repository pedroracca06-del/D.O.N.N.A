# ORB Invalidation Rules

**Sources:** `TRANSCRIPTS_RAW/orb_rp_001.txt` · `orb_rp_002.txt` · `orb_rp_003.txt` · `nova_strategy_core.json` · user-defined rules
**Last updated:** 2026-05-30

---

## Hard Invalidations — Do Not Trade

| # | Condition | Source |
|---|---|---|
| H1 | **Entry attempted before 09:30 ET.** Range construction phase only — execution is not open. No exceptions. | `orb_break_retest.md` |
| H2 | **Entry attempted after 11:00 ET.** ORB cutoff. Opening auction edge is degraded. No new ORB entries. | `orb_break_retest.md` · `nova_strategy_core.json` |
| H3 | **No clear break of ORB high or low.** Without a definitive break, there is no setup. Price inside the range at 9:30 = wait. | `orb_break_retest.md` |
| H4 | **ORB range not yet defined.** Before 08:15 ET — range construction is incomplete. Cannot trade what hasn't been built. | `orb_break_retest.md` |
| H5 | **Volume under 1,000 on the 1-minute chart at or after 9:30 ET.** Insufficient institutional participation. Do not trade even if the setup looks perfect. | `orb_break_retest.md` |
| H6 | **Retest never occurs.** If price breaks out and never returns to the midpoint zone, the ORB entry setup does not exist for this session. Fall back to untested session high/low setups. | `reaction_setups.md` |
| H7 | **Price reclaims ORB from the wrong side with conviction.** Full candle body close beyond the midpoint on the wrong side = balance has broken against the setup direction. | `nova_strategy_core.json` |
| H8 | **Multiple ORB violations in both directions.** Price breaks up, then breaks down, then up again — the range is no longer a reliable auction anchor. | `nova_strategy_core.json` |
| H9 | **Major macro event within 30 minutes.** | `nova_strategy_core.json` |
| H10 | **Daily loss at or beyond 2%.** Session is over. | User rule |

---

## Soft Degradations — Grade Downgrade

| # | Condition | Effect | Source |
|---|---|---|---|
| S1 | **ORB range > 15pts on MES.** Wide range = reduced reliability. Stops get wider and the risk/reward arithmetic becomes less clean. | Grade –1 | `nova_strategy_core.json` |
| S2 | **Breakout direction conflicts with the clear higher-timeframe trend.** RP explicitly cited this as a loss cause: "My mistake was that I failed to identify the trend." A bounce long embedded in a clear downtrend is not a valid setup. | Grade –1 | `reaction_setups.md` |
| S3 | **Midpoint reaction is weak — drift rather than decisive candle closure pattern.** Confirmation requires candle closures on the correct side of midpoint. A slow grind without clear closure behavior is not conviction. | Grade –1 | `candle_closure_rules.md` |
| S4 | **Breakout occurred before 9:30 ET without a clean retest at the NY open.** Pre-market volume is thin. The institutional confirmation that powers ORB comes from the NY open, not pre-market. | Grade –1 | `orb_break_retest.md` |
| S5 | **Setup timing in the 10:30–11:00 ET window.** Valid but later in the window — less room before cutoff and reduced session momentum. [INFERRED — consistent with cutoff logic] | Grade –1 | Inferred |
| S6 | **Single 1m candle closure on wrong side of level.** On its own this is not invalidation if 5m and 15m show no closures. But treat it as a signal to monitor — if 5m then confirms, the level may be breaking. | Monitor | `candle_closure_rules.md` |

---

## Mid-Trade Invalidation — ORB

| Condition | Action |
|---|---|
| Candle closes back on the wrong side of the midpoint after entry | Setup invalidated — exit |
| Price fails to deliver in the breakout direction within the session window | Exit before 11:00 ET cutoff if not moving |
| Midpoint is reclaimed from the wrong side (full body close) | Thesis broken — exit |
| Volume drops sharply after entry with no continuation | Monitor; trail stop to entry if structure hasn't confirmed |

---

## Fallback When ORB Fails to Set Up

If the ORB setup does not materialize (H3, H6, or H8), fall back to untested session high/low setups:
- Look for untested highs from Asia, London, or NY session
- Bounce (long) off untested session lows
- Rejection (short) off untested session highs
- Same confirmation rules apply (candle closure, no blow-through)

> "If the 8am zone just never gets retested, I look for longs off of an untested low, or shorts off of an untested high." — RP
