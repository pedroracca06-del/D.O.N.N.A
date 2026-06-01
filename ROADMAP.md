# Roadmap

## Current State — Phase 2 (Operational Validation)

The core infrastructure is built and operational. The system reads live TradingView charts, evaluates setups deterministically, calls Claude for grading, and delivers Discord alerts with chart screenshots. The execution pipeline routes TradingView webhook signals through a multi-gate risk engine to Alpaca.

The current focus is validating the AI reasoning output against real session conditions before commercialisation.

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

### 2C — Live Reasoning Validation (Active)
- Deterministic pre-assessment layer (PROS phase, ORB state, IB alignment, invalidation)
- Claude evaluation pipeline — grading, alert field generation, HEADS_UP vs EXECUTION_READY classification
- Multi-tab monitoring — reads all open TradingView tabs per cycle
- Session launcher with Windows Task Scheduler auto-start at 9:15 AM ET

### 2D — Execution Validation (Queued)
- Validate signal quality correlation with actual trade outcomes
- Measure HEADS_UP → EXECUTION_READY conversion rate
- Grade distribution analysis (A/B vs C/D ratio per session)
- False positive rate measurement

### 2E — Prop Firm Integration (Queued)
- Adapt execution pipeline for prop firm account rules (drawdown limits, consistency rules)
- Position sizing adjusted for funded account parameters
- EOD and weekly performance reporting

---

## Phase 2I — NOVA App (Planned, ~1–2 months)

A native mobile-first application consuming the DONNA backend.

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

## Known Limitations (Active Engineering)

| Limitation | Status |
|---|---|
| TradingView Desktop tabs share chart state — true multi-symbol tab reading pending | Infrastructure built, workaround in place |
| NOVA indicator requires manual install on new TradingView instances | Pine Script published to personal library |
| Render deployment has no TradingView access — local monitor required for AI alerts | By design; split architecture documented |
| MCP indicator removal can't re-add custom scripts — manual action required | Known MCP limitation |
