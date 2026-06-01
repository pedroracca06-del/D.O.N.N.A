# D.O.N.N.A — ROADMAP

**Data-Oriented Neural Network Assistant**
AI-native trading intelligence system.

---

## Architecture

```
AI Layer          → Claude / NOVA intelligence engine
Quant Layer       → probabilities · statistics · regime analytics
Execution Layer   → trading bot · broker routing · risk governance
Experience Layer  → TradingPal interface · dashboards · mission control
Behavioral Layer  → journaling · emotion tracking · replay · memory
Infrastructure    → backend · cloud · databases · mobile · notifications
```

TradingView = visualization + chart access + live data interface
Pine Script = chart annotation helper only
Claude / NOVA = the intelligence engine

---

## Layers

### 1 — AI Layer
Claude-powered intelligence. Reads live market data, interprets setups, grades quality, generates execution commentary, and orchestrates all downstream layers.

| Component | Description |
|---|---|
| NOVA Engine | Core strategy interpreter — PROS + ORB logic |
| Chart Interpretation | Live CDP chart reading via TradingView MCP |
| Execution Reasoning | Setup grading, entry zone identification, invalidation logic |
| Market Intelligence | Session awareness, macro context, volatility regime |
| Orchestration | Routes signals and commentary to Execution + Experience layers |

### 2 — Quant Layer
Statistical support layer. Augments NOVA intelligence with probability context. Does not replace contextual reasoning.

| Component | Description |
|---|---|
| Expectancy Engine | Win rate · R/R · expectancy by setup type and session |
| Continuation Statistics | PROS continuation probabilities by context |
| ORB Statistics | ORB breakout probabilities · midpoint acceptance rates |
| Regime Analytics | Bull / bear / choppy regime detection and performance by regime |
| Volatility Intelligence | ATR context · spread monitoring · expansion detection |
| Session Statistics | Edge by session window · time-of-day performance |

### 3 — Execution Layer
Automated trading and risk governance. Executes on NOVA signals with full rule-based guardrails.

| Component | Description |
|---|---|
| Trading Bot | Alpaca-connected execution engine |
| Broker Routing | Order routing · bracket management · position tracking |
| Governance Engine | No-trade condition enforcement · orchestration locks |
| Risk Engine | Daily loss limits · position sizing · drawdown controls |
| State Engine | Centralized execution state authority (DonnaStateEngine) |

### 4 — Experience Layer
Operator-facing interface. Institutional feel. Single mission control surface.

| Component | Description |
|---|---|
| TradingPal Interface | Primary trading UI · execution terminal · session scorecard |
| Mission Control Dashboard | Live market state · NOVA status · active setups · alerts |
| Watchlist Intelligence | Multi-symbol monitoring · setup classification · alert routing |
| Execution Terminal | Real-time NOVA commentary · setup grade display · entry zones |
| AI Commentary Feed | Human-readable execution intelligence · not indicator spam |
| News + Macro Panel | Headlines · economic calendar · macro risk display |

### 5 — Behavioral Layer
Trader performance system. Tracks psychology, execution quality, and pattern history.

| Component | Description |
|---|---|
| Trade Journal | Entry logging · outcome tracking · setup tagging |
| P&L Tracking | Realized P&L · daily / weekly / monthly summaries |
| Emotion Tracking | Pre-trade state · post-trade reflection · behavioral flags |
| Replay + Review | Bar-replay practice · execution review · mistake analysis |
| Trader Profiling | Performance patterns · edge identification · weak spots |
| Execution Memory | Historical NOVA decisions · outcome correlation |

### 6 — Infrastructure Layer
Backend, cloud, and platform systems.

| Component | Description |
|---|---|
| Backend | Python / FastAPI server (Render-hosted) |
| Databases | State persistence · journal storage · quant data |
| Notifications | Telegram alerts · mobile push · webhook routing |
| Mobile App | Monitoring interface · alerts · journal on mobile |
| Multi-User | Future: team/prop desk support |
| Cloud Orchestration | Scheduled jobs · morning brief · background intelligence loops |

---

## Phases

### Completed

| Phase | Description | Status |
|---|---|---|
| Phase 1A | Core backend + DONNA assistant server | ✅ Done |
| Phase 1B | News engine + macro calendar | ✅ Done |
| Phase 1C | Risk engine + governance layer | ✅ Done |
| Phase 1D | Execution engine (Alpaca) + state engine | ✅ Done |
| Phase 1E | Trade journal + P&L tracking | ✅ Done |
| Phase 1F | Dashboard + experience layer v1 | ✅ Done |
| Phase 1G | PROS Pine indicator (visual layer) | ✅ Done |
| Phase 1H | ORB Pine indicator (visual layer) | ✅ Done |
| Phase 2A | TradingView MCP integration (CDP bridge) | ✅ Done |
| Phase 2B | NOVA Knowledge Core | ✅ Done |

---

## Phase 2 — OPERATIONAL NOVA

> **Goal: NOVA becomes a fully usable daily trading operating system — personally operational for Pedro — before any commercialization begins.**
>
> The app and operational ecosystem must exist and be stable BEFORE Phase 3.
> Phase 2 = build the weapon. Phase 3 = package the weapon.

---

### Phase 2C — Live Reasoning Validation

**Status: ACTIVE**

Validate live ORB + PROS reasoning on real charts.

**Goal:** Confirm NOVA correctly applies all strategy logic against live price action.

- [ ] ORB setup recognition on live MES/ES chart
- [ ] PROS setup recognition on live MES/ES chart
- [ ] Invalidation rule application in real time
- [ ] No-trade condition detection
- [ ] Session quality assessment
- [ ] IB directional draw identification
- [ ] Continuation quality grading
- [ ] Behavioral governance enforcement

**Exit criteria:** NOVA produces accurate, structured analysis during a live session with no material reasoning errors.

---

### Phase 2D — Execution Validation

**Status: QUEUED**

Stabilize the execution infrastructure.

**Goal:** Reliable, consistent, non-spamming execution layer.

- [ ] Bot reliability audit + fixes
- [ ] Alert spam elimination
- [ ] Execution governance enforcement
- [ ] Webhook consistency validation
- [ ] State-engine synchronization
- [ ] Missed ORB/PROS setup detection
- [ ] Execution timing reliability

**Exit criteria:** Stable execution infrastructure. No missed setups, no duplicate alerts, no state drift.

---

### Phase 2E — Operational Alert System

**Status: QUEUED**

Screenshot-based contextual intelligence delivery system.

**Goal:** NOVA delivers rich, timely, actionable alerts — not just at confirmation, but as setups form.

**Alert types:**
- Setup-approach alerts (setup forming, not yet confirmed)
- Heads-up alerts (early warning)
- Contextual alignment alerts (multi-timeframe bias confirmation)
- No-trade alerts (session or condition blocks)
- Invalidation alerts (setup broken)
- Setup proximity alerts (price approaching key zone)

**Example alert format:**
```
🟢 HEADS UP — ES LONG FORMING

30M PROS forming — 3 min to close

Daily:          🟢 BULLISH
4H:             🟢 BULLISH
IB Draw:        🟢 IB HIGH
Session Quality: A

Watch for confirmation at 10:00 AM ET
[TradingView screenshot attached]
```

**Delivery:**
- [ ] Discord delivery pipeline
- [ ] Telegram delivery pipeline
- [ ] TradingView screenshot auto-attach
- [ ] Anti-spam governance
- [ ] Alert timing logic
- [ ] Setup proximity detection
- [ ] Multi-timeframe alignment scoring

**Exit criteria:** NOVA delivers timely, accurate, non-spamming alerts across Discord and Telegram with screenshots attached.

---

### Phase 2F — Morning Brief System

**Status: QUEUED**

AI-generated premarket operational briefings.

**Goal:** NOVA becomes a real premarket operations assistant.

**Brief contents:**
- [ ] Macro events for the day (FOMC, CPI, NFP, GDP)
- [ ] Overnight expansion summary
- [ ] Liquidity map (key levels above and below)
- [ ] IB directional draw expectation
- [ ] Session quality forecast
- [ ] Regime state
- [ ] Watchlist setup scan
- [ ] Expected conditions and key scenarios

**Exit criteria:** Morning brief delivered automatically before 09:15 ET with actionable session intelligence.

---

### Phase 2G — Quant + Statistical Intelligence

**Status: QUEUED**

Build NOVA's long-term statistical edge layer.

- [ ] Expectancy analytics by setup type and session
- [ ] Regime clustering (bull / bear / choppy)
- [ ] Continuation degradation analysis
- [ ] Setup quality statistics (grade A/B/C outcome rates)
- [ ] Confidence calibration
- [ ] Execution-quality analytics
- [ ] Behavioral performance tracking (discipline scoring)

**Exit criteria:** NOVA surfaces statistically grounded context to support live reasoning — not to replace it.

---

### Phase 2H — Replay + Review System

**Status: QUEUED**

Post-session and historical review infrastructure.

- [ ] Execution review (what was taken, what was missed)
- [ ] Behavioral review (discipline scoring, emotional flags)
- [ ] TradingView replay system integration
- [ ] Mistake detection and pattern tagging
- [ ] Performance analysis by setup, session, regime
- [ ] Post-trade intelligence reports

**Exit criteria:** NOVA produces meaningful post-session review automatically. Replay is accessible and functional.

---

### Phase 2I — NOVA Application Layer

**Status: QUEUED**

NOVA becomes a real application ecosystem. Not consumer-grade yet — but functionally complete and personally operational.

- [ ] Desktop workstation interface
- [ ] Mobile app (monitoring + alerts + journal)
- [ ] Live intelligence feed
- [ ] Operational dashboard
- [ ] Watchlist interface
- [ ] Morning brief delivery interface
- [ ] Screenshot alert display
- [ ] Execution summaries
- [ ] AI assistant interface
- [ ] Journaling interface
- [ ] Replay interface

**Exit criteria:** Pedro can run the full NOVA system from a single operational hub — desktop and mobile.

---

### Phase 2J — Stable Operational NOVA

**Status: MILESTONE**

> **This is the "daily weapon" milestone.**

NOVA is:
- Reliable
- Intelligent
- Operational
- Personally usable every trading day
- Stable enough for serious daily trading usage

Everything built in 2C–2I is working, integrated, and stable. Pedro uses NOVA as his primary trading operating system.

**This milestone gates Phase 3. Phase 3 does not begin until Phase 2J is achieved.**

---

## Phase 3 — Commercialization + User Experience Evolution

> **Phase 3 begins only after NOVA is personally operational and stable (Phase 2J complete).**
>
> The application already exists. Phase 3 is about packaging, scaling, and evolving the UX for external users.

| Phase | Description |
|---|---|
| Phase 3A | Onboarding system — new user setup, account creation, strategy selection |
| Phase 3B | Subscription + billing infrastructure |
| Phase 3C | Branding + public-facing identity |
| Phase 3D | Adaptive UI — personalization, user preferences, configurable dashboards |
| Phase 3E | Multi-user architecture — team/prop desk support |
| Phase 3F | Consumer-grade mobile UX refinement |
| Phase 3G | Public-facing platform + scaling infrastructure |
| Phase 3H | User strategy personalization — NOVA adapts to different strategies and risk profiles |

---

## Development Rules

**DO**
- Simplify
- Observe runtime behavior
- Prioritize intelligence and execution clarity
- Let Claude be the brain — not Pine, not indicators
- Build the weapon before packaging it

**DO NOT**
- Overfit rules to recent price action
- Overbuild Pine Script
- Stack endless indicators on TradingView
- Rewrite the roadmap impulsively
- Build quant before intelligence is validated
- Begin Phase 3 work before Phase 2J is achieved
