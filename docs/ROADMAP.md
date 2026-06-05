# Roadmap

## Current State — Phase 2E (Operational Validation)

The core infrastructure is built and operational. The system reads live TradingView charts, evaluates setups deterministically, calls Claude for grading, and delivers Discord alerts with rendered execution cards. The autonomous execution pipeline routes signals through a multi-gate risk engine to Alpaca. The system is in active paper validation collecting signal quality data before prop-firm deployment.

---

## Phase 1 — Foundation (Complete)

- FastAPI backend deployed to Render
- TradingView webhook ingestion and signal processing
- Alpaca broker integration with multi-gate execution pipeline
- Discord and Telegram alert delivery
- Trade journal with P&L tracking and analytics
- Dashboard with live market data, risk engine, and session status
- Macro news guard (Finnhub + FMP)
- Execution trace and rejection observability

---

## Phase 2 — NOVA AI Intelligence (Active)

### 2A — TradingView MCP Integration (Complete)
- Custom MCP server (Node.js) connecting to TradingView Desktop via CDP
- Live reading of symbol, timeframe, OHLCV, price levels, indicator tables, labels
- Confirmed reading NOVA indicator output: PROS ENGINE, ORB CONSOLE, NOVA ENGINE tables

### 2B — NOVA Knowledge Core (Complete)
- Strategy rules encoded in `nova_strategy_core.json`
- PROS continuation rules, ORB auction rules, invalidation logic, no-trade conditions
- Session quality classification, IB draw alignment framework
- Execution quality grading criteria (A/B/C/D)

### 2C — Live Reasoning Validation (Complete)
- Deterministic pre-assessment layer (PROS phase, ORB state, IB alignment, invalidation)
- Claude evaluation pipeline — grading, alert field generation, HEADS_UP vs EXECUTION_READY classification
- Multi-tab monitoring — reads all open TradingView tabs per cycle
- Session launcher with Windows Task Scheduler auto-start at 9:15 AM ET

### 2D — Execution Validation (Active)
- Signal quality correlation against actual trade outcomes
- HEADS_UP → EXECUTION_READY conversion rate measurement
- Grade distribution analysis (A/B vs C/D ratio per session)
- False positive rate measurement and ACCEPTED_CONTINUATION phase recognition

### 2E — Autonomous Execution + Card Renderer (Active)
- Autonomous paper execution pipeline live on Alpaca (paper mode)
- NOVA execution card renderer — programmatically generated chart visuals replace TradingView screenshots
- Multi-gate risk engine: state gate, red folder, daily trade limit, daily loss limit, position sizing
- Execution telemetry and rejection trace with full gate audit per signal
- Prop firm execution profile groundwork

---

## Phase 2F — NOVA Internal Platform Migration (Next)

**Goal:** Migrate operational workflows out of Discord and into NOVA's own internal web platform.

Discord currently acts as the alert delivery layer, operational feed, monitoring surface, execution review surface, and reasoning feed. That is a temporary arrangement. NOVA should become the primary operational environment. Discord becomes the notification and lightweight mirror layer.

### Targets
- Internal NOVA operational feed — live alert stream inside the dashboard
- Embedded execution cards and AI reasoning feed
- Session monitoring surfaces with live PROS/ORB/IB state
- Governance and rejection stream — full gate audit visibility
- Execution telemetry feed and risk engine panels
- Market state and regime panels
- Trade lifecycle visualization
- Replay and review integration

**Strategic shift:** Discord remains for mobile push and lightweight external distribution. All operational decision surfaces move inside NOVA.

---

## Phase 2G — Autonomous Execution Integration (After 2F)

**Goal:** Integrate the autonomous execution infrastructure as a first-class operational surface inside NOVA. The execution bot should not be disconnected backend infrastructure — it should be visible, controllable, and auditable from within the platform.

### Targets
- Embedded execution console inside the NOVA dashboard
- Live position monitoring and management
- Autonomous execution state feed — real-time gate status, active thesis, cooldown state
- Execution controls — kill switches, mode switching, permission management
- Prop-firm mode integration — funded account rules, drawdown visibility, consistency tracking
- Risk profile switching — standard, reduced, prop-firm, test
- Governance lock visualization — what is blocked and why
- Execution trace viewer — full signal-to-order audit trail
- Reconciliation monitoring — Alpaca position sync
- Position and event timeline
- Live execution analytics

**Strategic shift:** The prop-firm autonomous bot infrastructure becomes fully integrated into NOVA instead of existing as a disconnected backend process.

---

## Phase 2H — NOVA Interface + Design System Redesign (After 2G)

**Goal:** Complete the full NOVA visual redesign using the finalized intelligence-first interface direction. This phase happens after Discord workflow migration and execution integration are stable so the interface is designed around validated operational workflows, not invented ahead of them.

### Design direction
- Bloomberg-inspired, institutional, operational
- AI-first and intelligence-centered
- Dark/light mode capable
- Color-as-signal design language
- Mobile-first authority — desktop is mobile expanded
- Execution-card-based workflows
- Replay-first architecture
- Glanceable operational surfaces

### Targets
- Unified NOVA design system and component library
- Execution-card-driven UI throughout
- Operational dashboard redesign
- Journal redesign
- Replay and review redesign
- AI interaction redesign
- Mobile-responsive operational layout
- Feed-style operational workflows
- Clean execution visualization language
- Intelligence-first navigation architecture

**Strategic principle:** The interface is designed around the actual operational workflows once they are stable — not before.

---

## Phase 2I — NOVA App (After 2H)

The NOVA app is the final consumer layer built on top of a mature operational platform and execution ecosystem — not the next step.

The app inherits validated workflows, a finalized interface language, and integrated execution infrastructure. It does not invent these things itself.

- 5-tab architecture: NOVA AI, Market, Risk Engine, Journal, Settings
- NOVA AI tab as primary screen — live setup status, IB draw, session quality, active alerts
- Real-time SSE feed from backend
- Bloomberg-inspired dark interface, color-as-signal design language
- Mobile is design authority; desktop is mobile expanded

---

## Phase 3 — Commercialisation (Future)

- Multi-user infrastructure — authentication, per-user state isolation
- Subscription delivery — alert feeds for external subscribers
- Strategy expansion — additional instruments and session windows
- Performance analytics dashboard for track record presentation
- API productisation — expose NOVA grading as a service

---

## Phase Ordering Summary

```
2D  Execution Validation          ← active
2E  Autonomous Execution          ← active
2F  Internal Platform Migration   ← next
2G  Autonomous Execution Integration
2H  Interface + Design System Redesign
2I  NOVA App
3   Commercialisation
```

The app is the destination, not the next stop.

---

## Known Limitations (Active Engineering)

| Limitation | Status |
|---|---|
| TradingView Desktop tabs share chart state — true multi-symbol tab reading pending | Infrastructure built, workaround in place |
| NOVA indicator requires manual install on new TradingView instances | Pine Script published to personal library |
| Render deployment has no TradingView access — local monitor required for AI alerts | By design; split architecture documented |
| MCP indicator removal can't re-add custom scripts — manual action required | Known MCP limitation |
| Journal data lost on Render deploy — persistent disk setup pending | Fix shipped; Render dashboard configuration required |
