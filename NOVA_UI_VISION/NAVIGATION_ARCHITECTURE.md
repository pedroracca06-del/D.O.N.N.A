# NOVA Navigation Architecture
**Status:** Load-bearing | **Version:** 1.1 | **Last updated:** 2026-05-30

Defines the screen structure, navigation hierarchy, and state-to-UI mapping
for the NOVA application (Phase 2I).

See also: `STATE_MODEL.md` (data each panel consumes), `PHASE_ROADMAP.md` (when app builds)

---

## Foundational Design Rules

**Rule 1 — One system, two form factors.**
NOVA is one operational intelligence system. Desktop is the flagship experience
(deepest workflows, full depth). Mobile is the operational companion (fast
awareness, lightweight access). Both are equally core. Neither is subordinate.
Both share the same information hierarchy — desktop expands it with depth,
mobile compresses it to essential signals.

**Rule 2 — UI consumes intelligence. It does not invent logic.**
Every panel maps to an existing `compute_Xstate()` object. No panel displays
information that doesn't already exist in the state layer. This is a locked
architectural principle.

**Rule 3 — NOVA AI is a primary tab.**
Non-negotiable. AI is not a panel, not a widget, not a sidebar feature.
It has its own tab, its own screen, its own real estate.

**Rule 4 — Maximum 5–6 surfaces on the dashboard.**
Equal-weight panel overload is the primary desktop design failure mode.
Hierarchy > completeness.

---

## Navigation Model

### Mobile (Primary)
**Bottom tab bar — 5 tabs**

```
[ Dashboard ] [ Macro ] [ AI ] [ Journal ] [ Bot ]
      ↑            ↑       ↑        ↑          ↑
   Live         Macro    NOVA     Trade      Bot
  Session      Intel     AI      Journal   Connect
```

### Desktop (Secondary)
**Left sidebar — persistent**

```
┌─────────────┬────────────────────────────────┐
│  NOVA       │                                │
│  ─────────  │   Main Content Area            │
│  Dashboard  │                                │
│  Macro      │   (context-sensitive)          │
│  AI         │                                │
│  Journal    │                                │
│  Bot        │                                │
│  ─────────  │                                │
│  Health     │                                │
└─────────────┴────────────────────────────────┘
```

---

## Tab 1 — Dashboard (Live Session)

**Purpose:** Complete operational picture for the current trading session.
**State consumed:** `compute_session_quality_state()`, `compute_pros_state()`,
`compute_orb_state()`, `compute_macro_state()` (summary)

### Layout (mobile, scrollable)

```
┌─────────────────────────────────┐
│ NOVA  ·  09:42 ET  ·  NY OPEN  │   ← session header, always visible
│ Session Quality: A              │   ← color-coded grade
├─────────────────────────────────┤
│ MARKET                          │
│  NQ  +0.4%   ES  +0.2%         │   ← compact, one line
│  VIX 18.4    Regime: TRENDING   │
├─────────────────────────────────┤
│ SETUP STATUS                    │
│  PROS: BUILDING ▲ LONG          │   ← current phase
│  OTE: APPROACHING               │   ← distance to entry zone
│  IB Draw: HIGH  [aligned ✓]     │
│  Grade candidate: A             │
├─────────────────────────────────┤
│ ORB                             │
│  High: 21,485  Mid: 21,460      │
│  Low:  21,435  Range: 50pts     │
│  Phase: DEFINED                 │
├─────────────────────────────────┤
│ MACRO                           │
│  Next: No events today          │   ← or countdown if event approaching
│  Macro risk: LOW                │
├─────────────────────────────────┤
│ NOVA  ──────────────────────    │   ← contextual intelligence line
│  OTE approaching. IB aligned.   │
│  Watch for rejection candle.    │
└─────────────────────────────────┘
```

### Desktop extensions
- Expanded PROS/ORB panels (full detail, not just summary)
- Alert feed visible alongside (right panel)
- Chart screenshot panel (latest capture from MCP)

---

## Tab 2 — Macro Intelligence

**Purpose:** Full macro state, economic calendar, session quality context.
**State consumed:** `compute_macro_state()` (full), `donna_macro_events.json`, `donna_risk_state.json`
**Mirrors:** #macro-risk Discord feed (Discord is secondary consumer of same state)

### Layout (mobile, scrollable)

```
┌─────────────────────────────────┐
│ MACRO INTELLIGENCE  ·  09:42 ET │
│ Risk: LOW  ·  Session cap: A    │
├─────────────────────────────────┤
│ TODAY'S EVENTS                  │
│  No HIGH-impact events today    │
│  ─────────────────────────────  │
│  (or list of events:)           │
│  🔴 08:30  Core PCE  2.6% f     │
│  🟡 10:00  UMich Sentiment      │
├─────────────────────────────────┤
│ NEXT EVENT                      │
│  Core PCE  ·  08:30 ET          │
│  APPROACHING — 28 min           │   ← live countdown
│  Forecast: 2.6%  Prev: 2.8%     │
│                                 │
│  NOVA                           │
│  ORB unreliable pre-data.       │
│  Stand aside until 09:45 ET.    │
├─────────────────────────────────┤
│ MARKET SNAPSHOT                 │
│  VIX 18.4  (−0.8%)             │
│  NQ  +0.3%   ES  +0.2%         │
│  10Y 4.31%   DXY 104.2          │
│  Regime: TRENDING UP            │
├─────────────────────────────────┤
│ WEEK AHEAD                      │
│  Mon 06/02  ·  ISM Mfg PMI     │
│  Wed 06/04  ·  FOMC Minutes     │
│  Fri 06/06  ·  NFP              │   ← red folder week flag if applicable
└─────────────────────────────────┘
```

### Behavior
- Live countdown timer for next event (updates every second when APPROACHING/IMMINENT)
- IMMINENT phase: event card pulses / highlights
- Session quality badge updates in real-time as macro state changes
- Week ahead pulls from `donna_macro_events.json`

---

## Tab 3 — NOVA AI

**Purpose:** Primary AI interaction layer. NOVA AI is the platform's centerpiece.
**State consumed:** Full system state (all compute_Xstate() outputs fed as context)
**Character:** Contextual intelligence, not generic chatbot

### Layout (mobile)

```
┌─────────────────────────────────┐
│ NOVA AI                         │
│ 09:42 ET  ·  Session: NY OPEN   │
├─────────────────────────────────┤
│ CURRENT CONTEXT                 │
│  Session Quality: A             │   ← AI always has full context
│  PROS: BUILDING LONG            │
│  Macro: CLEAR                   │
│  Trades today: 0                │
├─────────────────────────────────┤
│                                 │
│  ┌───────────────────────────┐  │
│  │  NOVA                     │  │
│  │                           │  │
│  │  OTE is approaching on    │  │   ← proactive intelligence
│  │  the 5M chart. IB draw    │  │      (not prompted)
│  │  confirmed to the high.   │  │
│  │  Watch for rejection at   │  │
│  │  21,460–21,465.           │  │
│  │                           │  │
│  │  Grade A candidate if     │  │
│  │  rejection is clean.      │  │
│  └───────────────────────────┘  │
│                                 │
│  [You]  What's my stop if I     │
│          enter at OTE?          │
│                                 │
│  ┌───────────────────────────┐  │
│  │  NOVA                     │  │
│  │  Below displacement base  │  │
│  │  at 21,410. 30pts on MES. │  │
│  │  Standard for this vol.   │  │
│  └───────────────────────────┘  │
│                                 │
├─────────────────────────────────┤
│  ┌─────────────────────┐  [→]  │
│  │  Ask NOVA...        │       │
│  └─────────────────────┘       │
└─────────────────────────────────┘
```

### AI Behavior Rules
- NOVA proactively surfaces intelligence when setup conditions change (no prompt needed)
- All responses follow tactical language standard (concise, operational, no essays)
- AI always has full session context injected — no need for user to re-explain
- AI can be asked about: current setup, stops/targets, session quality, macro risk, invalidation conditions
- AI references the user's own trading system (PROS, ORB, IB) — not generic TA advice

---

## Tab 4 — Trade Journal

**Purpose:** Execution history, quality review, pattern recognition.
**Character:** Intelligence system, not a log.

### Layout (mobile)

```
┌─────────────────────────────────┐
│ JOURNAL                         │
│ Week of May 26 · 3 trades       │
├─────────────────────────────────┤
│ TODAY  ─────────────────────    │
│  No trades yet                  │
├─────────────────────────────────┤
│ YESTERDAY  ──────────────────   │
│  ┌───────────────────────────┐  │
│  │ PROS LONG  ·  MES         │  │
│  │ 09:47 ET  ·  Grade: A     │  │
│  │ +2.3R  ·  IB HIGH hit     │  │
│  │ [Chart] [Notes] [Replay]  │  │
│  └───────────────────────────┘  │
│  ┌───────────────────────────┐  │
│  │ ORB E1 SHORT  ·  MES      │  │
│  │ 10:12 ET  ·  Grade: B     │  │
│  │ −1R  ·  OTE missed        │  │
│  │ [Chart] [Notes] [Replay]  │  │
│  └───────────────────────────┘  │
├─────────────────────────────────┤
│ THIS WEEK  ──────────────────   │
│  3 trades  ·  Win rate: 67%     │
│  Avg R: +1.2  ·  Best: +2.3R   │
│  Grade dist: A×2  B×1           │
├─────────────────────────────────┤
│ NOVA REVIEW  ─────────────────  │
│  Strong execution this week.    │
│  Both Grade A setups captured.  │
│  Grade B stop placement was     │
│  conservative — cost 0.5R.      │
└─────────────────────────────────┘
```

### Journal Entry Detail (tap to expand)

```
┌─────────────────────────────────┐
│ ← PROS LONG  ·  MES  ·  09:47  │
├─────────────────────────────────┤
│ [Chart screenshot at entry]     │
├─────────────────────────────────┤
│ Setup Grade:   A                │
│ Entry:         21,445           │
│ Stop:          21,415  (30pts)  │
│ TP1:           21,490  (IB H)   │
│ Exit:          21,492           │
│ R:R achieved:  +2.3R            │
│ IB aligned:    YES              │
│ Session Q:     A                │
├─────────────────────────────────┤
│ NOVA GRADE REVIEW               │
│  Entry timing: clean (at OTE)   │
│  Stop: rule-based               │
│  TP: held to IB level           │
│  Execution score: 91/100        │
├─────────────────────────────────┤
│ YOUR NOTES                      │
│  [tap to add]                   │
└─────────────────────────────────┘
```

---

## Tab 5 — Trading Bot

**Purpose:** Execution management and bot health monitoring.
**Character:** Operational control panel — not the platform identity.
**Prerequisite:** Prop-firm connectivity (Phase 2 Priority 2) must exist first.

### Layout (mobile)

```
┌─────────────────────────────────┐
│ TRADING BOT                     │
│ Status: ACTIVE  ·  MES          │
├─────────────────────────────────┤
│ CONNECTION                      │
│  Prop Firm: [Connected ✓]       │
│  Account: PA-XXXXX              │
│  Environment: Live              │
│  Permissions: Full auto         │
├─────────────────────────────────┤
│ TODAY'S SESSION                 │
│  Trades: 0 / 2                  │
│  Daily loss: 0%  (limit: 2%)    │
│  Trade permission: ENABLED      │
│  Position: FLAT                 │
├─────────────────────────────────┤
│ BOT CONTROLS                    │
│  [ Automation: ON  ●──────── ]  │
│  [ Alerts: ON      ●──────── ]  │
│  [ Screenshots: ON ●──────── ]  │
│                                 │
│  [  PAUSE SESSION  ]            │
│  [  DISABLE AUTOMATION  ]       │
├─────────────────────────────────┤
│ SYSTEM HEALTH                   │
│  Intelligence:  PASS            │
│  Market data:   PASS            │
│  Discord feed:  PASS            │
│  MCP / Chart:   PASS            │
│  Execution:     PASS            │
│                                 │
│  SAFE_TO_TRADE: TRUE            │
├─────────────────────────────────┤
│ RECENT ACTIVITY                 │
│  09:31  HEADS_UP delivered      │
│  09:47  EXECUTION_READY sent    │
│  09:47  Position opened (MES)   │
│  09:52  TP1 hit                 │
│  09:52  Position closed +2.3R   │
└─────────────────────────────────┘
```

### Bot Controls (Detail)
- **Automation toggle:** Enable/disable fully automated execution (bot takes trades)
- **Alerts toggle:** Enable/disable Discord + in-app alert delivery
- **Screenshots toggle:** Enable/disable chart capture on alerts
- **Pause Session:** Immediately stops all new entries for remainder of session (maintains existing positions)
- **Disable Automation:** Switches to alert-only mode (no auto-execution, only notifications)

---

## Desktop Extended Layout

On desktop, all 5 tabs become sections with expanded layouts.

### Dashboard Desktop
```
┌──────────────┬──────────────────────────┬──────────────┐
│  Sidebar     │  Live Session            │  Alert Feed  │
│  ──────────  │  ────────────────────    │  ──────────  │
│  Dashboard   │  Session Quality: A      │  09:31 HEADS │
│  Macro       │  PROS: BUILDING LONG     │  09:15 MACRO │
│  AI          │  OTE: APPROACHING        │  09:00 BRIEF │
│  Journal     │  ORB: DEFINED 50pts      │              │
│  Bot         │  IB Draw: HIGH ✓         │              │
│  ──────────  │  ────────────────────    │              │
│  Health      │  Market                  │              │
│              │  NQ +0.3%  ES +0.2%      │              │
│              │  VIX 18.4  TRENDING UP   │              │
│              │  ────────────────────    │              │
│              │  Chart Screenshot        │              │
│              │  [latest MCP capture]    │              │
└──────────────┴──────────────────────────┴──────────────┘
```

---

## Architectural Coherence Confirmation

As of 2026-05-30, the system has confirmed architectural coherence across all layers.
Every UI tab maps directly to an existing backend state object:

| Tab | Maps to | Discord equivalent |
|---|---|---|
| Dashboard | `compute_session_quality_state()` + `compute_pros_state()` + `compute_orb_state()` | #live-alerts (partial) |
| Macro | `compute_macro_state()` | #macro-risk (full) |
| AI | `evaluate_with_claude()` + full system context | N/A (in-app only) |
| Journal | Journal layer (`donna_journal.json`) | N/A (in-app only) |
| Bot | `compute_execution_state()` + `donna_health.py` | #system-health (partial) |

Discord is a secondary consumer of the same state objects.
The NOVA app is the primary consumer (Phase 2I).
Both consume the same backend — no duplication required.

---

## State-to-Screen Mapping

| State Object | Screen(s) that consume it |
|---|---|
| `compute_macro_state()` | Dashboard (summary), Macro tab (full), Bot tab (risk) |
| `compute_session_quality_state()` | Dashboard header, Bot tab, AI context |
| `compute_pros_state()` | Dashboard setup panel, AI context |
| `compute_orb_state()` | Dashboard ORB panel, AI context |
| `compute_invalidation_state()` | Dashboard (replaces setup panel when active), Alert feed |
| `compute_execution_state()` | Bot tab (primary), Dashboard (trade count only) |
| Alert history | Alert feed (all screens, desktop sidebar) |
| Journal entries | Journal tab (primary) |
| Health check | Bot tab (system health panel) |

---

## Notification Model

When the app is in background, alerts are delivered via:
1. In-app push notification (primary)
2. Discord (parallel — external mirror)
3. Telegram (optional secondary)

When the app is in foreground:
1. In-app feed updates in real-time
2. NOVA AI surfaces proactively on setup changes
3. No separate notification — the UI IS the feed
