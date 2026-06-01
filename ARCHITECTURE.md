# Architecture

## Overview

DONNA/NOVA is built around a strict separation between three concerns:

1. **Data acquisition** — reading live chart state from TradingView via CDP/MCP
2. **Intelligence** — deterministic rule evaluation followed by AI grading
3. **Delivery** — governed alert routing to Discord with screenshots and Telegram fallback

The system runs in two deployment contexts simultaneously:

- **Render (cloud)** — FastAPI backend serving webhooks, dashboard, market data APIs, and macro intelligence loops
- **Local machine (trading day only)** — the NOVA monitor connecting to TradingView Desktop, running the AI reasoning pipeline, and delivering session alerts

---

## Component Map

### `main.py` — FastAPI Application
The central HTTP layer. Responsibilities:
- Receive TradingView webhook payloads (`POST /webhook`)
- Serve the trading dashboard (`GET /dashboard`)
- Expose market data endpoints (quotes, futures pulse, sector heat, earnings)
- Run background async loops: macro calendar, news guard, Finnhub, Grok intelligence, EOD close, morning brief
- Route inbound signals through `donna_signals.py` → `donna_execution.py`

### `donna_nova_reasoning.py` — NOVA Reasoning Pipeline
The core intelligence module. Runs on the local machine during trading hours.

Pipeline per cycle (every 60 seconds):
1. Read all open TradingView tabs via MCP (`_collect_all_contexts`)
2. Evaluate session context — time window, trade count, loss limits
3. Parse NOVA indicator tables by header key (NOVA ENGINE / PROS ENGINE / ORB CONSOLE)
4. Run deterministic evaluators — no API calls at this stage:
   - `_evaluate_pros_phase` — displacement, retracement depth, OTE zone, continuation quality
   - `_evaluate_orb_phase` — range state, midpoint, expansion, E1/E2 classification
   - `_evaluate_ib_alignment` — IB HIGH/LOW draw alignment vs CMD direction
   - `_check_invalidation_signals` — broken structure, failed continuation
5. Classify signal type (HEADS_UP / EXECUTION_READY / INVALIDATION / NO_TRADE)
6. Skip Claude if no signal — zero API cost on quiet cycles
7. Call Claude with full chart context + pre-assessment for confirmation, grading, and alert field generation
8. Return `AlertData` objects for delivery

### `donna_alert_engine.py` — Alert Governance and Delivery
Manages the full lifecycle of an alert from generation to Discord delivery.

- **Governance** — per-signal cooldowns (15–120 min by type), daily alert cap, deduplication
- **Screenshot pipeline** — captures TradingView chart via MCP before delivery
- **Discord delivery** — rich embeds with color-coded alert types, inline fields, chart image attachment
- **Channel routing** — HEADS_UP, EXECUTION_READY, INVALIDATION, NO_TRADE, SESSION_BRIEF each route to dedicated channels with `DISCORD_CHANNEL_LIVE` fallback
- **Telegram fallback** — plain-text delivery when Discord is not configured

### `donna_state_engine.py` — State Management
Single source of truth for session state. Tracks:
- Trade permission, macro lock, red folder lock, EOD lock
- Daily trade count and loss tracking
- Open positions and thesis direction
- Cooldown expiry timestamps

All execution gates read from this state before any broker call.

### `donna_execution.py` — Broker Integration
Alpaca REST API wrapper with full gate stack:
- Trade permission check
- Macro lock / red folder lock
- EOD lock (no new entries after 3:30 PM ET)
- Daily trade count limit
- Cumulative risk limit
- Records every rejection with full gate snapshot for observability (`/execution/rejections`)

### `donna_signals.py` — Webhook Signal Processor
Validates and normalises TradingView webhook payloads. Applies Harvey/bias scoring before forwarding to execution.

### `donna_macro_discord.py` — Macro Intelligence
Background loop (every 5 minutes during market hours):
- Calendar phase detection — pre-event / impact window / post-event classification
- VIX regime monitoring — elevated / spike / extreme threshold alerts
- Breaking news guard — Finnhub news sentiment scoring
- Morning brief — fires once per day at 09:00–09:20 ET

### `donna_risk_engine.py` — Risk Calculator
On-demand position sizing, R:R calculation, and drawdown tracking. Exposed via `/risk-engine-data`.

---

## Data Flow — Alert Pipeline

```
TradingView Desktop (NOVA indicator rendering)
    │
    │  MCP CLI (node src/cli/index.js state / tables / quote / labels)
    ▼
read_chart_context()          → raw chart state dict
    │
parse_nova_tables()           → {main: {...}, pros: {...}, orb: {...}}
    │
_evaluate_pros_phase()        → {phase, direction, ote_status, has_signal}
_evaluate_orb_phase()         → {phase, range, e1/e2, has_signal}
_evaluate_ib_alignment()      → {draw, aligned, ib_range}
_check_invalidation_signals() → {invalidated, reason}
    │
_classify_signal()            → (alert_type, setup_type, rationale)
    │
    ├── None → log "no signal", return []
    │
evaluate_with_claude()        → {alert_required, grade, entry_zone, stop, tp1, notes, ...}
    │
    ├── grade C/D → no alert
    │
decision_to_alert()           → AlertData
    │
deliver_alert()
    ├── can_deliver() governance check
    ├── capture_screenshot() via MCP
    ├── send_discord() — embed + image
    └── send_telegram() — text fallback
```

---

## Data Flow — Webhook Execution Pipeline

```
TradingView alert → POST /webhook
    │
process_signal()              → verdict + confidence scoring
    │
execute_signal()
    ├── state gate checks (permission, locks, limits)
    ├── Alpaca order submission
    └── auto-journal entry
    │
SSE broadcast → dashboard live feed
```

---

## Deployment Split

| Component | Where | Why |
|---|---|---|
| FastAPI backend | Render (cloud) | Always-on webhook receiver, dashboard, market data |
| NOVA local monitor | Trading machine | Requires TradingView Desktop CDP access — Render has no TradingView |
| TradingView MCP server | Trading machine | Node.js process connecting to localhost:9222 |
| Task Scheduler | Trading machine | Auto-launches session at 9:15 AM ET weekdays |

---

## State Architecture

All mutable session state flows through `DonnaStateEngine`. No module writes state directly — they call `state.set(key, value)` and read via `state.get(key)`. This ensures a consistent snapshot is available for the dashboard, execution gates, and observability endpoints at all times.

State is persisted to `donna_state_engine.json` and reloaded on startup to survive process restarts.
