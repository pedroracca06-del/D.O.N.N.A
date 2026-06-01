# NOVA Phase Roadmap
**Status:** Load-bearing | **Version:** 2.0 | **Last updated:** 2026-05-30

Defines the build sequence and phase boundaries for NOVA.
Phase ordering is architectural — not cosmetic. Sequence matters.

---

## Current Stage

**Refinement and Operational Validation Phase.**

Infrastructure survival is complete. The system now enters a different stage:
proving the intelligence layer works correctly under live market conditions,
establishing governance reliability, and building prop-firm connectivity
before migrating to an app-centric architecture.

---

## Phase Overview

```
Phase 2 (now)          Phase 2I (1-2 months)      Phase 3
─────────────────────  ──────────────────────────  ───────────────
Operational            NOVA App Layer              Polish / Scale /
Validation +           (primary operations         Commercialize
Prop-firm              center)
Connectivity
```

**Critical rule:** The NOVA app is ~1–2 months out — not because infrastructure
is missing, but because operational validation must come first. Stability,
governance reliability, and prop-firm connectivity must be proven before
the app becomes the primary operating environment.

**Commercialization does not happen before:**
- Operational stability (bot validated live)
- Execution reliability (governance proven)
- Prop-firm connectivity (funded account live)
- Intelligence stabilization (cross-feed integration complete)

---

## Phase 2 — Operational Validation + Prop-Firm Connectivity

### Priority 1 — Trading Bot Operational Validation (MOST CRITICAL)

The bot must prove stable in real market conditions before app migration.

**Validate:**
- [ ] Live execution during NY open session
- [ ] Governance locks (daily cap, cooldowns, duplicate suppression)
- [ ] Cooldown behavior across all alert types
- [ ] Invalidation detection and signal clearing
- [ ] Macro downgrade propagation into session quality
- [ ] Alert timing (HEADS_UP before confirmation, EXECUTION_READY at confirmation)
- [ ] Execution aggressiveness adaptation (session quality → alert behavior)
- [ ] Operational health system (`donna_health.py`) under real conditions
- [ ] Cross-feed integration (macro state → session quality → signal classification)
- [ ] Anti-spam governance under high-signal periods

**Success criteria:** NOVA runs through a full NY open session with no false
positives, correct invalidation behavior, and macro events correctly
downgrading session quality.

---

### Priority 2 — Prop Firm Connectivity

This is a major pre-app milestone. NOVA must be operationally viable before app rollout.

**Build:**
- [ ] Prop firm execution environment connection
- [ ] Funded account infrastructure integration
- [ ] Execution routing layer (signal → prop firm order)
- [ ] Position monitoring from prop firm account
- [ ] Risk state sync (prop firm limits → NOVA governance)
- [ ] Health check integration (prop firm connectivity in `/health`)

**Why before the app:** The Trading Bot Connection tab in the future app
(account authorization, bot permissions, execution history, active positions)
requires this infrastructure to exist first. Build the plumbing, then the UI.

---

### Priority 3 — Internal Feed Migration

Move all operational data from Discord as primary → NOVA website/dashboard as primary.

**Migrate:**
- [ ] Trading alerts (HEADS_UP, EXECUTION_READY, INVALIDATION, NO_TRADE)
- [ ] Macro intelligence feed (#macro-risk content)
- [ ] Screenshots (chart captures → dashboard panel)
- [ ] Operational state (session quality, regime, VIX, ORB status)
- [ ] Health check output (live system status panel)
- [ ] Reasoning output (PROS/ORB phase, signal classification)

**Discord becomes after migration:**
- Notification layer (push alerts for critical events)
- External operational mirror (backup feed)
- Mobile push bridge (alerts to phone)
- NOT the primary operating environment

---

### Priority 4 — TradingView Dashboard Cleanup

**Goal:** Stable, operationally clear chart environment. Functionality > visual complexity.

**Actions:**
- [ ] Audit current indicator stack — remove noise
- [ ] Keep one clean, uncluttered dashboard layout
- [ ] Optimize for screenshot readability (clean chart = clean alert image)
- [ ] Reduce visual complexity without losing operational context
- [ ] Lock the layout as the standard screenshot template

**Why now:** Screenshot attachments in alerts are only as good as the chart
they capture. A cluttered chart produces cluttered intelligence.

---

### Priority 5 — Cross-Feed Integration Completion

Complete the intelligence chain wiring. See `CROSS_FEED_INTEGRATION.md` for full spec.

**Build (Phase 2J):**
- [ ] Unify session quality source (`compute_macro_state()` as authority)
- [ ] Wire session quality into `_classify_signal()` (grade caps by session quality)
- [ ] Add execution aggressiveness level to pre-assessment dict
- [ ] Hard-gate IMMINENT macro events (suppress EXECUTION_READY)
- [ ] IB alignment grade cap enforced deterministically (not just by Claude)

---

### Completed Phase 2 Sub-phases

| Sub-phase | What was built | Status |
|---|---|---|
| 2A | Alert data model (`AlertData`) | Done |
| 2B | Anti-spam governance layer | Done |
| 2C | Live reasoning pipeline (MCP → evaluators → Claude) | Done, awaiting live test |
| 2D | Discord embed layer (5 alert types, channel routing) | Done |
| 2E | Full delivery pipeline (Discord + Telegram + screenshot) | **Live validated** |
| 2F | Macro intelligence feed (`compute_macro_state()` + #macro-risk) | **Live validated** |
| 2G | Operational health check (`donna_health.py`) | Done |
| 2H | Architecture documentation (5 load-bearing docs) | Done |

---

### Phase 2 Definition of Done

- [ ] Live session test passed (Priority 1 complete)
- [ ] Prop firm connected and tested (Priority 2 complete)
- [ ] All state objects implemented per `STATE_MODEL.md`
- [ ] Cross-feed integration wired per `CROSS_FEED_INTEGRATION.md`
- [ ] Health check full PASS across all categories
- [ ] `.env` fully populated on both local and Render
- [ ] Screenshot pipeline live-tested with real alert

---

## Phase 2I — NOVA App Layer

**Trigger:** Phase 2 definition of done. ~1–2 months from now.
**Goal:** Native application becomes the primary operations center.

### Core App Screens

1. **Live Session Dashboard** — all intelligence layers in one view (PROS, ORB, IB, macro, session quality, VIX, regime)
2. **Macro Intelligence Panel** — real-time macro state, event countdowns, session impact
3. **Setup Development Panel** — active PROS/ORB tracking, phase transitions, grade history
4. **Trading Bot Connection Tab** (see below)
5. **Trade Journal** — execution history, grading, pattern analysis, replay
6. **System Health Panel** — always-on operational status (`donna_health.py` output)

### Trading Bot Connection Tab — Core Feature

Users will be able to:
- Connect prop-firm accounts (authorization flow)
- Authorize execution environments
- Manage bot permissions (enable/disable automation)
- Monitor bot status (active, paused, stopped)
- Monitor health state (live system status)
- Monitor risk state (daily limits, loss tracking)
- Enable/disable specific alert types
- Review execution history
- Monitor active positions and P&L

**Technical note:** This tab is only possible after Priority 2 (prop-firm
connectivity) is complete. The infrastructure must exist before the UI.

### Data Layer for App

All `compute_Xstate()` functions built in Phase 2 feed the app directly.
No redesign needed. The app is a new consumer of existing state objects.

---

## Phase 3 — Polish, Package, Scale, Commercialize

**Trigger:** Phase 2I complete. App validated as primary operations center.
**What does NOT happen before Phase 3:** External user onboarding, marketing,
white-labeling, SaaS infrastructure, commercial pricing.

### Phase 3 Goals
- Performance optimization and reliability hardening
- Multi-instrument support (beyond MES/ES, MNQ/NQ)
- Multi-session support (Asia, London extended)
- User configuration layer
- Potential multi-user or licensing architecture
- Commercial packaging and distribution
