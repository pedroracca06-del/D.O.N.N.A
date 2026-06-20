# NOVA Knowledge Map
**Date:** 2026-06-20  
**Version:** 1.0 — Baseline audit before intelligence expansion  
**Purpose:** Define what NOVA is, what it knows, and what it should become. Govern all future intelligence development.

---

## Governing Principle

NOVA is a market intelligence system. PROS and ORB are strategies NOVA understands. They are not NOVA's identity.

**The test:** If PROS and ORB were removed from the system tomorrow, would NOVA still understand markets? The knowledge map is honest about where the answer is currently "no."

**The distinction used throughout this document:**
- **Active intelligence** — NOVA computes this independently, every cycle, with no dependency on any strategy
- **Strategy-embedded knowledge** — This exists in nova_knowledge_core as rules, but only activates during PROS/ORB evaluation. It is Level 3, not Level 1.
- **Absent** — Does not exist anywhere in the system

---

## Rating Scale

| Rating | Definition |
|---|---|
| NONE | No awareness. The concept is entirely absent. |
| BASIC | Surface-level data or rules exist. No independent reasoning about the concept. |
| INTERMEDIATE | Active computation, classification, and prompt injection. NOVA reasons with this. |
| ADVANCED | Synthesis, implication, forward projection. NOVA explains "so what" not just "what." |

---

## 1. Market Structure

| Concept | Rating | Evidence | Gap |
|---|---|---|---|
| Overnight High / Overnight Low | INTERMEDIATE | `engines/market_structure.py` — computed every cycle, ABOVE/INSIDE/BELOW classification | — |
| Prior Week High / Prior Week Low | INTERMEDIATE | `engines/market_structure.py` — full Mon-Fri prior week, price-vs-level classification | — |
| Monthly Open | INTERMEDIATE | `engines/market_structure.py` — first bar of current month | — |
| Daily Open | INTERMEDIATE | `engines/market_reality_v2.py` — first 9:30 bar | — |
| Initial Balance (IB) High/Low/Mid | INTERMEDIATE | `engines/market_reality_v2.py` — 9:30-10:30 range. Used in reasoning prompt. | Knows the levels, not the auction mechanics behind them |
| ORB Range (8:00-8:15) | INTERMEDIATE | `engines/reasoning.py` — read from indicator, evaluated against current price | Computed via indicator read, not independent OHLC computation |
| Session High / Session Low | BASIC | `engines/market_reality_v2.py` — tracked but not classified against structural context | Not yet classified as "new high of day" or "failed to reach yesterday's high" |
| VWAP | BASIC | `engines/market_reality_v2.py` — computed, in reasoning prompt | Present but rarely synthesized into a signal |
| Gap (open vs prior close) | INTERMEDIATE | `engines/market_structure.py` — GAP_UP / GAP_DOWN / NO_GAP with ±0.20% threshold | — |
| Previous Day High (PDH) | BASIC | In `nova_knowledge_core/ORB_RP/liquidity_levels.md` as strategy rule | Not computed as Level 1 intelligence. Exists only in PROS/ORB context. |
| Previous Day Low (PDL) | BASIC | Same as PDH | Same gap |
| Asia / London Session High / Low | NONE | Listed in `liquidity_levels.md` but not computed by any engine | No multi-session structure tracking |
| Swing High / Swing Low identification | NONE | Absent from all engines | Requires pattern detection algorithm on price bars |
| Consolidation range / balance area | NONE | Absent | Requires time-at-price logic |
| Trend structure (HH/HL, LH/LL pattern) | NONE | Absent | Requires sequence detection across multiple bars |
| Fair Value Gap (FVG) | NONE | Absent | Level 2 concept — ICT framework |
| Breaker / Order Block | NONE | Absent | Level 2 concept — ICT framework |

**Level 1 gap:** PDH/PDL are the most leveraged missing active structure levels. Every professional trader marks them. NOVA has them as strategy rules but not as independent intelligence.

---

## 2. Liquidity

| Concept | Rating | Evidence | Gap |
|---|---|---|---|
| Liquidity as a concept | BASIC | `nova_knowledge_core/ORB_RP/liquidity_levels.md` — comprehensive rule documentation | Knowledge exists in strategy layer only. Not independently computed. |
| PDH/PDL as liquidity pools | BASIC | Documented as strategy rule, read by Claude via reasoning context | Not flagged as live levels by any engine |
| Session highs/lows as liquidity pools | BASIC | Same — documented in strategy knowledge | Not computed independently |
| Untested vs tested levels | BASIC | Documented in `level_strength.md` — age of level = strength | Not tracked by any engine |
| Liquidity sweep detection | NONE | No engine detects or flags when price sweeps a key level and reverses | Highest single gap in this domain |
| Absorption detection | BASIC | Partial — `price_vol_confirm=DIVERGING` in participation engine catches the signature | Not named or interpreted as absorption |
| Resting orders / stop clusters | NONE | Absent | Requires L2 data (not available without premium source) |
| Equal highs / Equal lows (consolidation liquidity pools) | NONE | Absent | Requires bar pattern detection |
| Volume at price | NONE | Absent | Requires tick or volume profile data |
| Bid/ask spread intelligence | NONE | Absent | Requires L2 data |

**Critical finding:** The word "liquidity" appears throughout NOVA's codebase (PROS draw, ORB setup names) but NOVA has zero independent understanding of what liquidity is. It receives liquidity labels from the indicator. It cannot compute or classify liquidity conditions on its own. This is the deepest gap in the system.

---

## 3. Auction Market Theory

| Concept | Rating | Evidence | Gap |
|---|---|---|---|
| Initial Balance as opening auction | BASIC | IB is computed and used, but NOVA doesn't reason about it as an auction mechanism | Knows the level, not why it exists |
| Price as a two-sided auction process | NONE | Absent | Foundational AMT concept — NOVA never asks "did this auction succeed or fail?" |
| Price acceptance vs rejection | NONE | Absent | Key behavioral concept — price staying at a level = acceptance, reverting quickly = rejection |
| Value Area (70% of volume) | NONE | Absent | Requires volume profile data |
| Point of Control (POC) | NONE | Absent | Requires volume profile data |
| Profile shape recognition (P/b/D-shaped) | NONE | Absent | Requires TPO data |
| Balance / Imbalance identification | NONE | Absent | NOVA cannot distinguish a balanced consolidation from a directional imbalance |
| Session type classification (Trend / Normal / Neutral / Poor) | BASIC | `engines/participation.py` — TREND_DAY / HIGH_PARTICIPATION / RANGE_DAY / LOW_CONVICTION is functionally equivalent but derived from RVOL, not from price behavior in an auction context | Not grounded in AMT framework |
| "What is the market trying to do?" | NONE | Absent | This is the central AMT question. NOVA cannot answer it. |
| Failed auction signal | NONE | Absent | When the market tries to extend a range and fails — no detection |

**Level 1 opportunity:** A basic AMT framework would allow NOVA to interpret IB, session type, and daily range in a fundamentally more sophisticated way. It would also provide the synthesis layer for answering "what is the market trying to do today?" without needing AI generation.

---

## 4. Cross-Market Analysis

| Concept | Rating | Evidence | Gap |
|---|---|---|---|
| NQ vs ES relative performance (spread) | INTERMEDIATE | `engines/cross_market.py` — TECH_LEADING / ALIGNED / TECH_LAGGING | — |
| DXY direction and equity implications | INTERMEDIATE | `engines/cross_market.py` — DXY_HEADWIND / DXY_TAILWIND | Dollar correlation is simplistic — only ±move, not trend or momentum |
| Treasury yield pressure | INTERMEDIATE | `engines/cross_market.py` — YIELD_PRESSURE / YIELD_RELIEF (±5bps) | Rate level context missing (is 4.5% normal or extreme?) |
| Gold signal (risk-off / inflation) | INTERMEDIATE | `engines/cross_market.py` — GOLD_RISK_OFF / GOLD_INFLATION etc. | Gold interpretation logic is heuristic, not nuanced |
| BTC as risk-on proxy | INTERMEDIATE | `engines/cross_market.py` — BTC_RISK_ON / BTC_RISK_OFF | BTC correlation to NQ varies by regime — NOVA doesn't know the regime |
| VIX regime and speed | INTERMEDIATE | `engines/cross_market.py` — FEAR_SPIKE / FEAR_RISING / FEAR_CALMING + VIX level | — |
| Cross-market bias synthesis | INTERMEDIATE | `engines/cross_market.py` — BULLISH_SUPPORT through BEARISH_PRESSURE | — |
| Yield curve shape (2/10 spread) | NONE | Absent | Recession signaling, risk appetite |
| Credit spreads (HYG, LQD) | NONE | Absent | Risk-on/off confirmation beyond equities |
| Sector rotation (XLK, XLF, XLE relative) | NONE | Absent | Which sectors are leading tells you what the move is about |
| Intermarket seasonal patterns | NONE | Absent | Month-of-year, time-of-year correlations |
| Fed policy regime awareness | NONE | Absent | Are we in hiking, pausing, or cutting cycle? This changes all correlations. |
| VIX term structure (VIX vs VX spread) | NONE | Absent | VX backwardation/contango tells you if hedgers are protecting short or long |

---

## 5. Macro

| Concept | Rating | Evidence | Gap |
|---|---|---|---|
| VIX level classification | INTERMEDIATE | `engines/cross_market.py` + `services/finnhub.py` risk state | — |
| Economic event detection | INTERMEDIATE | `services/headlines.py` — red-folder event ingestion, 3-phase lifecycle | — |
| Event phase awareness | INTERMEDIATE | PRE_EVENT / POST_EVENT / NORMALIZING — governs red-folder locks | — |
| Macro risk classification | INTERMEDIATE | risk_state.macro_risk — EXTREME / HIGH / ELEVATED / MODERATE / LOW | — |
| Headline risk scoring | INTERMEDIATE | `services/news.py` — keyword-based risk classification | Keyword matching, not semantic interpretation |
| Grok/X sentiment | BASIC | `engines/market_reality.py` — sentiment read injected into MR prompt | External read-in, not synthesized with structure |
| Fed cycle stage | NONE | Absent | NOVA doesn't know if we're in hiking, pausing, or cutting cycle |
| Earnings season awareness | BASIC | `engines/engines.py` — fetches next-week earnings dates | Not integrated into session quality or risk scoring |
| Quantitative tightening/easing effects | NONE | Absent | Liquidity regime affects everything — NOVA is unaware |
| Treasury issuance calendar | NONE | Absent | Supply effects on yield, particularly around quarter-end |
| FOMC dot plot / guidance context | NONE | Absent | NOVA knows FOMC is a red-folder event, not what it said or means |
| Positioning / COT data | NONE | Absent | Requires premium data source |

---

## 6. News

| Concept | Rating | Evidence | Gap |
|---|---|---|---|
| Headline ingestion | INTERMEDIATE | `services/finnhub.py` + Finnhub news endpoint | Limited to Finnhub coverage |
| Keyword-based risk classification | INTERMEDIATE | `services/news.py` — keyword matching → risk score | Keyword matching, not semantic understanding |
| Red-folder event identification | INTERMEDIATE | `services/headlines.py` — economic calendar, event priority | — |
| News directionality | NONE | NOVA knows a CPI print happened, not whether it was above or below expectations and what that means | Biggest gap in this domain |
| Behavioral pattern after event type | NONE | NOVA doesn't know "NFP beats tend to produce X behavior for Y minutes" | Requires historical pattern library |
| Market's prior positioning relative to news | NONE | Was the market already priced for this result? NOVA cannot answer this. | Requires understanding of positioning, which is absent |
| Earnings reaction patterns | NONE | Absent | No earnings impact model |
| News that matters vs noise | BASIC | Keyword priority scoring provides rough filtering | Misses context — the same headline can be high or low impact depending on positioning |

---

## 7. Participation

| Concept | Rating | Evidence | Gap |
|---|---|---|---|
| Relative Volume (RVOL) | INTERMEDIATE | `engines/participation.py` — time-of-day aware, 10-session baseline | — |
| Session type classification | INTERMEDIATE | `engines/participation.py` — TREND_DAY / HIGH_PARTICIPATION / RANGE_DAY / LOW_CONVICTION | Based on RVOL + volume trend + price-vol confirm — solid foundation |
| Volume trend (expanding/contracting) | INTERMEDIATE | `engines/participation.py` — recent vs prior bar comparison | — |
| Price-volume confirmation | INTERMEDIATE | `engines/participation.py` — UP/DOWN_CONFIRMED / DIVERGING / MIXED | — |
| Breadth proxy (SPY vs IWM) | INTERMEDIATE | `engines/participation.py` — session % change comparison | Proxy only — actual breadth requires NYSE TICK or A/D data |
| NYSE TICK (cumulative tick divergence) | NONE | Absent | Requires real-time data feed |
| Advance/Decline ratio | NONE | Absent | Requires NYSE data |
| Up volume vs Down volume ratio | NONE | Absent | Requires tick or bar-level data |
| Put/Call ratio | NONE | Absent | Options data not in system |
| TRIN (Arms Index) | NONE | Absent | Requires NYSE data |
| Cumulative Volume Delta (CVD) | NONE | Absent | Requires tick data or premium bar data |
| Block trades / institutional footprint | NONE | Absent | Requires L2 or premium data |

**Note:** Many of the professional participation tools (TICK, CVD, A/D) require data sources not currently available. The current RVOL + session type + breadth proxy is the maximum achievable with free yfinance data.

---

## 8. Trading Psychology

| Concept | Rating | Evidence | Gap |
|---|---|---|---|
| Behavioral block rules (documented) | BASIC | `nova_knowledge_core/NO_TRADE_CONDITIONS/behavioral_blocks.md` — FOMO, revenge trading, overleverage, spiral pattern | Rules exist as governance blocks but NOVA doesn't actively detect psychological state |
| Active psychological state detection | NONE | Absent | NOVA cannot detect "user is in revenge-trading state right now" |
| Session performance effects on behavior | NONE | Absent | NOVA doesn't know if the user is 2 losses in and escalating |
| Retail sentiment indicators | NONE | Absent |  |
| Contrarian signal from extreme positioning | NONE | Absent | |
| Herding behavior detection | NONE | Absent | |
| Session-level emotional context | NONE | Absent | After a big loss vs after a big win — NOVA treats both identically |

**Assessment:** NOVA has documented the behavioral rules correctly. They function as governance blocks (entry blocked in defined states). But NOVA has no ability to assess the trader's psychological state in real time and no ability to adapt its communication accordingly. This is a meaningful gap for a "market partner."

---

## 9. Journal Intelligence

| Concept | Rating | Evidence | Gap |
|---|---|---|---|
| Trade recording | INTERMEDIATE | `donna_journal.json` — full trade records with metadata | — |
| AI trade analysis per trade | INTERMEDIATE | Claude-generated analysis on journal entries | Quality depends on context provided — context is currently limited |
| Basic analytics (win rate, expectancy) | INTERMEDIATE | `engines/analytics.py` — win rate, avg win/loss, expectancy, by-strategy bucketing | — |
| Thesis analysis framework | BASIC | `engines/thesis_analysis.py` — 8 classification labels, MAE/MFE | Blocked pending classification validation on real trades |
| Performance correlation with session type | NONE | Absent | NOVA can't say "you perform better on TREND_DAY sessions" |
| Performance correlation with structure | NONE | Absent | NOVA can't say "you perform better when opening above PWH" |
| Performance correlation with RVOL | NONE | Absent | Requires joining participation data to journal entries |
| Behavioral pattern recognition | NONE | Absent | NOVA can't identify "you tend to take early exits on winning trades" |
| P&L attribution by setup type | BASIC | `by_setup_type` bucket in analytics, but not synthesized into insight | Raw bucketing without interpretation |
| Performance over time / regime | NONE | Absent | Is NOVA's edge deteriorating? NOVA cannot answer. |
| Expectancy by context type | NONE | Absent | What is NOVA's expectancy on TREND_DAY vs LOW_CONVICTION sessions? |

---

## 10. Risk Management

| Concept | Rating | Evidence | Gap |
|---|---|---|---|
| Daily P&L caps | INTERMEDIATE | `services/execution.py` — daily loss limit, hard locks | — |
| Session trade limits | INTERMEDIATE | Max 2 trades per day, enforced via state engine | — |
| Position sizing | INTERMEDIATE | `engines/risk_engine.py` — sizing based on R:R and stop distance | — |
| Multi-gate governance | INTERMEDIATE | 11-gate execution check sequence | — |
| Drawdown regime awareness | NONE | NOVA knows today's P&L. It doesn't know if we're 3 losing days into a drawdown and what that implies for sizing. | |
| Kelly criterion / optimal position sizing | NONE | Absent | Current sizing is fixed-R, not optimal |
| Risk-of-ruin calculation | NONE | Absent | |
| Sharpe / Sortino from live data | NONE | Absent | Analytics doesn't compute risk-adjusted return metrics |
| Correlation-adjusted exposure | BASIC | Gate 11 checks for correlated instrument exposure (NQ + MNQ) | Simple guard, not true correlation weighting |
| Regime-aware sizing | NONE | Absent | Size down in LOW_CONVICTION sessions — rule exists in session_quality.md, not enforced in engine |

---

## 11. Execution Intelligence

| Concept | Rating | Evidence | Gap |
|---|---|---|---|
| Paper execution | INTERMEDIATE | `services/execution.py` — paper mode active, order routing | — |
| Execution audit trail | INTERMEDIATE | `services/execution_trace.py` — full ring-buffer audit log | — |
| Order routing (MES→SPY, MNQ→QQQ) | INTERMEDIATE | `services/execution_bridge.py` — correct routing | — |
| Execution timing analysis | NONE | Absent | Did NOVA enter at the right time relative to the signal? |
| Fill quality analysis | NONE | Absent | How does actual fill compare to signal price? |
| Slippage tracking | NONE | Absent | Paper mode uses market orders — slippage not modeled |
| Time-in-trade analysis | NONE | Absent | Are holds too short (cutting profits) or too long (letting losses run)? |
| Execution edge measurement | NONE | Absent | Does NOVA's execution timing add or subtract value vs. theoretical? |

---

## 12. Strategy Recognition

| Strategy / Framework | Rating | Evidence | Gap |
|---|---|---|---|
| PROS (Evan Investing) | INTERMEDIATE | Full indicator integration, A-D grading, entry type classification, draw evaluation | Reads indicator output, not computed from first principles |
| ORB (Opening Range Breakout) | INTERMEDIATE | ORB range detection, LIQ_REJECT / MID_REJECT / EDGE_REJECT entries, timing gates | — |
| ICT concepts (liquidity pools, FVG, displacement) | NONE | Absent as active intelligence | Some ICT vocabulary used in ORB context (liquidity sweep) but not understood systematically |
| Wyckoff Method | NONE | Absent | |
| Market Profile / TPO | NONE | IB is a Market Profile concept but NOVA doesn't understand the full framework | |
| Auction Market Theory | NONE | Absent as active intelligence | |
| Momentum strategies | NONE | Absent | |
| Mean Reversion strategies | NONE | Absent | |
| Order Flow strategies | NONE | Absent | |
| Trend Following strategies | NONE | Absent | |

---

## Summary: Current NOVA Knowledge Map

```
DOMAIN                  ACTIVE INTELLIGENCE LEVEL
─────────────────────────────────────────────────
Market Structure        ████████░░  INTERMEDIATE
Liquidity               ██░░░░░░░░  BASIC (strategy-embedded only)
Auction Market Theory   █░░░░░░░░░  NONE → BASIC
Cross-Market Analysis   ██████░░░░  INTERMEDIATE
Macro                   ██████░░░░  INTERMEDIATE
News                    ████░░░░░░  BASIC → INTERMEDIATE
Participation           ██████░░░░  INTERMEDIATE
Trading Psychology      ██░░░░░░░░  BASIC (rules only, no active detection)
Journal Intelligence    ████░░░░░░  BASIC → INTERMEDIATE
Risk Management         ██████░░░░  INTERMEDIATE (execution layer)
Execution Intelligence  ██████░░░░  INTERMEDIATE
Strategy Recognition    ████░░░░░░  INTERMEDIATE (PROS/ORB only)
```

**Without PROS and ORB, NOVA's Level 1 intelligence is:**
Market Structure (good), Cross-Market (good), Participation (good), Macro (good), News (partial).
Missing: Liquidity, Auction mechanics, Psychology, Journal pattern learning, News directionality.

---

## Desired Future NOVA Knowledge Map

Target state for each domain after 12 months of intelligence development:

```
DOMAIN                  TARGET LEVEL
──────────────────────────────────────
Market Structure        ████████████  ADVANCED  (multi-session levels, swing structure, consolidation)
Liquidity               ████████░░░░  INTERMEDIATE (independent sweep detection, level age, tested/untested)
Auction Market Theory   ██████░░░░░░  INTERMEDIATE (price acceptance/rejection, session type from first principles)
Cross-Market Analysis   ████████░░░░  INTERMEDIATE+ (sector rotation, credit spreads, VIX structure)
Macro                   ████████░░░░  INTERMEDIATE+ (Fed cycle, earnings context, positioning awareness)
News                    ██████░░░░░░  INTERMEDIATE (directionality, behavioral patterns after event types)
Participation           ████████░░░░  INTERMEDIATE+ (proxy breadth replaced by real breadth when data available)
Trading Psychology      ████████░░░░  INTERMEDIATE (active state detection, performance-aware communication)
Journal Intelligence    ████████░░░░  INTERMEDIATE (performance correlations, behavioral patterns, expectancy by context)
Risk Management         ████████░░░░  INTERMEDIATE+ (regime-aware sizing, performance-informed risk)
Execution Intelligence  ████████████  ADVANCED (fill quality, timing, slippage, execution edge measurement)
Strategy Recognition    ██████████░░  INTERMEDIATE+ (PROS/ORB + ICT vocabulary + AMT classification)
```

---

## Highest-Leverage Intelligence Gaps

Ranked by: impact on understanding markets × feasibility with existing data sources.

### Gap #1 — Liquidity as Independent Intelligence (highest leverage)
**What's missing:** NOVA uses the word "liquidity" constantly but cannot compute any liquidity signal independently. It receives PDH/PDL, session highs/lows, and liquidity labels from the PROS indicator. Remove the indicator and NOVA is liquidity-blind.

**What it would unlock:** NOVA could independently identify when price is sweeping a key level, when a sweep has occurred and price has reclaimed, and whether a setup is occurring in a liquidity-seeking or liquidity-providing context. This is prerequisite knowledge for understanding PROS from first principles.

**Feasibility:** High. PDH/PDL and session high/lows can be computed from yfinance daily + intraday bars, similar to what market_structure.py already does.

### Gap #2 — Synthesis Layer: "What is the market trying to do today?"
**What's missing:** NOVA has 6 intelligence layers but no synthesis. It cannot produce a unified situational read. A professional analyst looks at all available information and forms a narrative thesis. NOVA cannot do this.

**What it would unlock:** Morning context brief, session narrative, the ability for the assistant to answer "what's happening today" with real intelligence rather than reporting individual signals.

**Feasibility:** High. This is an AI generation task (Claude synthesizes existing intelligence layers into a narrative), not a new data source.

### Gap #3 — Session-to-Session Memory
**What's missing:** Every Monday, NOVA starts fresh. It doesn't know what happened last Thursday. It doesn't know if the market has failed at the same level three days in a row. It doesn't know the narrative that's been building all week.

**What it would unlock:** Continuity. NOVA's assistant would be able to say "this level has rejected twice this week — treat it differently" rather than seeing it as new information.

**Feasibility:** Medium-high. Requires a rolling session summary that's saved and loaded, similar to how execution_trace.py works.

### Gap #4 — News Directionality
**What's missing:** NOVA knows a CPI print happened. It doesn't know if it came in above or below expectations, what the consensus was, and what a hot vs. cold print means for the next hour of price action.

**What it would unlock:** Pre-event positioning context and post-event interpretation. Currently NOVA applies the same red-folder governance regardless of what the event said. A hot CPI print and a cold CPI print are categorically different events.

**Feasibility:** Medium. Requires either a news API that includes the actual print vs. expectations (some free APIs provide this), or structured Grok/X monitoring for event reactions.

### Gap #5 — Previous Day High / Previous Day Low as Active Intelligence
**What's missing:** PDH and PDL are the single most referenced levels by professional traders every morning. NOVA has them documented in strategy knowledge but no engine computes them as independent structural levels.

**What it would unlock:** NOVA could independently classify where price is relative to the key reference levels every professional uses, without depending on the PROS indicator.

**Feasibility:** Very high. Extend market_structure.py by one daily bar lookback.

### Gap #6 — Journal Pattern Recognition
**What's missing:** NOVA has 50+ trade records (after paper validation) and no ability to find patterns in them. It cannot identify correlations between session type, structure, and performance.

**What it would unlock:** NOVA starts learning from experience. "Your win rate on TREND_DAY sessions with RVOL > 1.3x is 73%. Your win rate on LOW_CONVICTION sessions is 41%." That's the difference between a system that accumulates data and a system that gets smarter over time.

**Feasibility:** High. Requires joining participation.json state at trade entry to the journal entry (context_snapshot already partially captures this).

---

## Recommended Development Order

### Immediate (this weekend / next week)
These have high leverage, free data sources, and clear implementation paths.

**1. PDH / PDL as active structure levels**
Extend `engines/market_structure.py` to compute previous day high/low/close from the daily bar history already being fetched. Zero additional API calls. This alone closes one of the most embarrassing gaps — NOVA has prior week levels but not yesterday's levels.

**2. Session synthesis — "What is the market doing today?"**
Add a synthesis function to the assistant or reasoning pipeline that takes all intelligence blocks (MR2 + cross_market + market_structure + participation) and generates one structured situational read per session. This is the Jarvis Project #5 (Morning Context Brief). Closes the synthesis gap.

**3. Session-to-Session Memory**
Rolling 5-session summary saved at session close. Loaded into morning brief and reasoning context. This is Jarvis Project #6.

### Near-Term (2-4 weeks)
**4. Liquidity Intelligence as Level 1 Engine**
Independent computation of PDH/PDL, ONH/ONL, session highs/lows, untested vs. tested status, level age. NOVA should know this without the indicator.

**5. Session Quality Score synthesis**
Jarvis Project #4 — combines macro, participation, structure, and news into a single HIGH/MEDIUM/LOW/AVOID verdict per session. Answers "should I trade aggressively today?"

**6. Basic Auction Market Theory awareness**
Teach NOVA to classify whether a session is in balance or imbalance, whether a price extension was accepted or rejected, and what the IB means in an auction context. No new data required — this is reasoning about data we already have.

### Medium-Term (1-3 months)
**7. News Directionality**
Structured interpretation of economic event outcomes (actual vs. expected) and what they imply for the next 30-60 minutes. Requires event consensus data source.

**8. Journal Pattern Recognition**
Correlation analysis between journal trades and their environmental context (session type, structure, participation, time of day). NOVA starts learning from accumulated experience.

**9. ICT vocabulary as Level 2 Concept Library**
Document equal highs/lows, displacement, FVG as concepts NOVA understands — not to make NOVA an ICT trader but to enrich its structural interpretation. Implemented as classification functions that label formations when detected.

### Deferred
**10. NYSE TICK / Cumulative Delta / True Breadth**
Requires premium data source or real-time feed. High leverage but blocked on data access.

**11. Options Intelligence (Put/Call, dealer positioning)**
Requires options data feed. Very high leverage for understanding market maker behavior but not achievable with free data sources.

---

## What NOVA Is vs What NOVA Should Be

| Question | Today | Target |
|---|---|---|
| "Where is price relative to structure?" | YES — Good | YES — add PDH/PDL, swing levels |
| "What is the cross-market environment?" | YES — Good | YES — add sector rotation, VIX structure |
| "Is participation strong?" | YES — Good | YES — improve with better breadth data |
| "What is the market trying to do today?" | NO | YES — synthesis layer, morning brief |
| "Who is driving this move?" | NO | PARTIAL — can't know without institutional data |
| "Does this setup have liquidity behind it?" | PARTIAL — via indicator | YES — independent computation |
| "What happened in prior sessions?" | NO | YES — session memory |
| "Is this news bullish or bearish?" | NO | PARTIAL — directionality model |
| "Am I performing better in some environments?" | NO | YES — journal intelligence |
| "What does this pattern mean historically?" | NO | PARTIAL — journal pattern recognition |

---

*This document is the baseline. The goal is not to add features. The goal is to build the brain.*
*Strategies are consumers of intelligence. They are not the brain.*
