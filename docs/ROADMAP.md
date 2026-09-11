# Roadmap

## Current State - Intelligence / Knowledge Consolidation

NOVA currently operates as a read-only market-intelligence and decision-support platform. Assistant, Journal Review, and Market Summary run through the centralized Intelligence gateway; current PRIME knowledge is Git-authoritative under `nova_knowledge_core/CURRENT/PRIME/`; Obsidian planning is non-executing. Trading/execution infrastructure is preserved but temporarily disabled and requires separate explicit approval before any future return.

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
- Historical TradingView/MCP parsing infrastructure is preserved; current indicator direction is the visual-only Market Map evolving toward PRIME-aware context

### 2B — NOVA Knowledge Core (Complete)
- Strategy rules encoded in `nova_strategy_core.json`
- Exactly three current PRIME execution models: Strict OTE, 10AM Key Level Open, and ORB; PROS is superseded historical lineage
- Research/history/candidates are separated from the current authority layer
- Deterministic contamination tests prevent legacy doctrine from re-entering current surfaces

### 2C — Live Reasoning Validation (Complete)
- Centralized Intelligence gateway for Assistant, Journal Review, and Market Summary
- Deterministic read-only CURRENT/PRIME retrieval with explicit source provenance and content hashes
- Journal Review and Assistant are protected from legacy PROS/IB/grading contamination
- Obsidian V2 authority namespaces separate CURRENT, RESEARCH, HISTORY, EVIDENCE, PROJECTS, and INBOX

### 2D - Historical Execution Validation Infrastructure (Preserved, Disabled)
- Signal quality correlation against actual trade outcomes
- HEADS_UP → EXECUTION_READY conversion rate measurement
- Grade distribution analysis (A/B vs C/D ratio per session)
- False positive rate measurement and ACCEPTED_CONTINUATION phase recognition

### 2E - Autonomous Execution + Card Renderer (Preserved, Temporarily Disabled)
- Historical Alpaca paper-execution pipeline is preserved but not currently authorized or active
- NOVA execution card renderer — programmatically generated chart visuals replace TradingView screenshots
- Multi-gate risk engine: state gate, red folder, daily trade limit, daily loss limit, position sizing
- Execution telemetry and rejection trace with full gate audit per signal
- Prop firm execution profile groundwork

---

## Phase 2F - NOVA Internal Platform + Brain Integration (Next Active Product Work, Read-Only)

**Goal:** Migrate operational workflows out of Discord and into NOVA's own internal web platform. Phase 2F is Brain/intelligence work and is read-only: it surfaces reasoning, market state, session context, and past review — it does not add execution controls, execution telemetry, or a governance/rejection execution stream. Those surfaces are Phase 2G and require separate owner approval before any of them is built or activated.

Discord currently acts as the alert delivery layer, operational feed, monitoring surface, execution review surface, and reasoning feed. That is a temporary arrangement. NOVA should become the primary environment for intelligence and read-only monitoring. Discord becomes the notification and lightweight mirror layer.

### Targets (read-only / intelligence)
- Internal NOVA operational feed — live alert stream inside the dashboard
- AI reasoning feed inside the dashboard
- Session monitoring surfaces with current PRIME-aware context and provenance
- Market state and regime panels
- Replay and review integration (journal/decision review, read-only)

**Strategic shift:** Discord remains for mobile push and lightweight external distribution. All read-only intelligence and operational-visibility surfaces move inside NOVA. Execution cards, execution telemetry, risk-engine panels, the governance/rejection execution stream, and execution-specific trade-lifecycle visualization are explicitly out of scope for 2F; they live exclusively in Phase 2G.

---

## Phase 2G - Future Trading/Execution Reintegration (Separately Approved)

**Goal:** If Pedro separately approves the trading subsystem to return, reintegrate the preserved execution infrastructure as a visible, controllable, and auditable NOVA surface. This phase is not currently active and the roadmap itself grants no activation authority.

### Targets
- Embedded execution console inside the NOVA dashboard
- Embedded execution cards and execution reasoning-feed integration (moved from 2F — execution-specific)
- Execution telemetry feed and risk engine panels (moved from 2F — execution-specific)
- Governance and rejection stream — full gate audit visibility (moved from 2F — execution-specific)
- Trade lifecycle visualization — execution/position lifecycle (moved from 2F — execution-specific)
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

**Strategic condition:** Preserved bot infrastructure may become fully integrated only after a separate owner-approved system change; until then it remains disabled historical/future infrastructure. Listing these targets here preserves the plan; it does not authorize building or activating any of them.

---

## Phase 2H — NOVA Interface + Design System Redesign (After 2F)

**Goal:** Complete the full NOVA visual redesign using the finalized intelligence-first interface direction. This phase happens after the Discord-to-NOVA workflow migration (Phase 2F) is stable, so the interface is designed around validated intelligence/internal-platform workflows, not invented ahead of them. It does not depend on trading/execution returning: Phase 2G remains separately approved and optional, and redesign work may proceed on validated intelligence/internal-platform workflows alone. If execution is later separately approved and reintegrated, its surfaces adopt this design system rather than gating it.

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
- NOVA Intelligence as primary assistant surface - current context, provenance, and authority-aware responses
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
2B  Current PRIME authority       - implemented / validating
2C  Brain authority integration   - active
2F  Internal Platform Migration   ← next (read-only / intelligence)
2G  Trading/Execution Reintegration - future, separate approval required
2H  Interface + Design System Redesign - after 2F; does not require 2G
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
