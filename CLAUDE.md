# NOVA — Codebase Guide

AI-native trading intelligence system for MES/ES and MNQ/NQ futures.
FastAPI backend + Claude AI + TradingView MCP + Alpaca broker.

---

## How to Run

```bash
# Backend (Render-deployed, or local dev)
uvicorn main:app --reload --port 8000
# Dashboard → http://localhost:8000/dashboard

# Local session monitor (requires TradingView Desktop open with CDP)
python donna_local_monitor.py

# One-click session launcher (Windows, starts TV + monitor together)
powershell -ExecutionPolicy Bypass -File scripts/start_trading_session.ps1
```

---

## System Architecture

```
TradingView Desktop (CDP :9222)
        │
        ▼
mcp/tradingview/          Node.js MCP server — reads chart state, switches symbols,
                          captures screenshots via Chrome DevTools Protocol

        │  subprocess calls
        ▼
donna_nova_reasoning.py   Core intelligence loop:
                          1. Reads both MES and MNQ charts via MCP
                          2. Parses NOVA EXECUTION V1 indicator tables
                          3. Runs deterministic evaluators (PROS, ORB, IB, invalidation)
                          4. Calls Claude API for setup grading (A–D) + narration
                          5. Returns structured AlertData objects

        │  AlertData
        ▼
donna_alert_engine.py     Governance + delivery:
                          - Anti-spam cooldowns, daily caps
                          - Routes by alert type to Discord channels
                          - Attaches chart screenshots to embeds

        │  parallel
        ▼
main.py (FastAPI)         Web layer:
                          - /webhook  — receives TradingView signals → execution pipeline
                          - /dashboard — serves the HTML dashboard
                          - /journal/* — trade journal CRUD + AI analysis
                          - Market data loops (Finnhub, FMP, Grok, news)

        │
        ▼
donna_execution.py        Broker layer:
                          - Multi-gate risk engine (session, macro, daily loss, locks)
                          - Routes MES→SPY, MNQ→QQQ orders via Alpaca REST API
                          - Paper mode enforced until live credentials present
```

---

## Module Reference

| Module | Role |
|---|---|
| `main.py` | FastAPI entry point — all routes, background loops, market data |
| `donna_config.py` | Constants, env vars, file paths, Anthropic client, time helpers |
| `donna_state.py` | JSON read/write helpers, journal stats computation |
| `donna_nova_reasoning.py` | NOVA intelligence pipeline — chart reading, evaluation, Claude calls |
| `donna_engines.py` | Dashboard payload builders — Harvey, scenarios, performance memory |
| `donna_alert_engine.py` | Alert governance, Discord/Telegram delivery, embed builder |
| `donna_execution.py` | Alpaca broker integration, position sizing, P&L tracking |
| `donna_execution_bridge.py` | Routes EXECUTION_READY alerts → execution layer |
| `donna_execution_trace.py` | Ring-buffer audit log of every execution event |
| `donna_signals.py` | TradingView webhook signal parser and normaliser |
| `donna_signal_log.py` | Structured log of every NOVA evaluation cycle |
| `donna_state_engine.py` | Centralised session state — trades taken, locks, risk regime |
| `donna_risk_engine.py` | Position sizing, drawdown, R:R calculation |
| `donna_macro_discord.py` | Macro intelligence alerts — calendar, VIX, breaking news |
| `donna_headlines.py` | Economic calendar ingestion, red-folder governance |
| `donna_news.py` | News feed risk scoring — Finnhub headlines → risk_state |
| `donna_finnhub.py` | Live market snapshot — yfinance quotes → risk_state |
| `donna_health.py` | System health checks — all subsystems, API keys, file state |
| `donna_assistant.py` | Claude conversational assistant with session context |
| `donna_analytics.py` | Performance analytics helpers |
| `donna_local_monitor.py` | Local session monitor — 60s poll loop, MCP health alerts |
| `donna_html.py` | Dashboard HTML/CSS/JS — server-rendered, ~4200 lines |

---

## Key Directories

```
data/                     Runtime state — JSON files auto-generated at runtime
                          All gitignored except donna_settings.json
mcp/tradingview/          Node.js MCP server (git submodule → pedroracca06-del/tradingview-mcp)
nova_knowledge_core/      Strategy rules, PROS methodology, ORB rules, IB logic
nova_ui_vision/           UI design philosophy, navigation architecture, mockups
indicators/               Pine Script — NOVA EXECUTION V1 TradingView indicator
scripts/                  Windows PowerShell ops scripts
tests/                    Test suite
docs/                     Technical documentation
```

---

## Runtime State (data/)

All JSON state lives in `data/`. Key files:

| File | Updated by | Purpose |
|---|---|---|
| `donna_risk_state.json` | Finnhub/news loops | Market snapshot, VIX, macro risk level |
| `donna_signal_log.json` | NOVA reasoning loop | Full evaluation history per cycle |
| `donna_journal.json` | /journal/add endpoint | Trade records with AI analysis |
| `donna_execution_trace.json` | Execution pipeline | Audit log of every signal → order |
| `donna_state_engine.json` | State engine | Daily trade count, locks, P&L |
| `donna_macro_events.json` | Headlines loop | Parsed economic calendar |
| `donna_settings.json` | Dashboard UI | User-configurable display preferences |

---

## Critical Patterns

**State-first architecture** — All intelligence flows from computed state objects, never invented in UI:
```
compute_macro_state() → Dashboard macro panel
compute_pros_state()  → Dashboard setup panel
compute_orb_state()   → Dashboard ORB panel
```

**Deterministic before AI** — Claude is called only when the deterministic engine detects a genuine signal. No speculative AI calls.

**MCP chart switching** — The monitor scans both MES and MNQ by switching the active TradingView chart, reading context, then restoring. Dwell time: 90 seconds per symbol.

**CDP port** — TradingView must launch with `--remote-debugging-port=9222`. Controlled via `TV_CDP_PORT` env var (defaults to 9222). The session launcher script handles this automatically.

**Execution routing** — MES/ES signals route to SPY shares; MNQ/NQ signals route to QQQ shares. Paper mode enforced by `NOVA_AUTO_EXECUTE` env var.

---

## Environment Variables

See `.env.example` for the full list. Minimum required to run:

```
ANTHROPIC_API_KEY         Claude API (grading, journal analysis, assistant)
DISCORD_BOT_TOKEN         Discord delivery
DISCORD_CHANNEL_LIVE      Fallback alert channel
ALPACA_API_KEY            Broker (paper or live)
ALPACA_SECRET_KEY
FINNHUB_API_KEY           Market data
```

---

## Deployment

- **Render** — cloud backend (`uvicorn main:app`). Auto-deploys on push to `main`.
- **Local** — TradingView MCP monitor, session launcher, Task Scheduler at 9:15 AM ET.

Render handles: API, dashboard, macro loops, journal, webhook ingestion.
Local handles: TradingView CDP, chart reading, NOVA reasoning, Discord alerts.
