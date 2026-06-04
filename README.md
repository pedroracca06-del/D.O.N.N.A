# NOVA — AI Trading Intelligence System

**AI-native market intelligence and execution infrastructure for futures trading.**

NOVA is a production trading system that reads live TradingView charts via Chrome DevTools Protocol, evaluates MES and MNQ futures setups through a deterministic rule engine, grades signals using Claude (Anthropic), and delivers structured alerts to Discord with chart screenshots — all running on a real-time 60–90 second evaluation cycle.

Built for: **backend engineering** · **AI systems** · **fintech infrastructure**

---

## What It Does

- **Live chart intelligence** — connects to TradingView Desktop via a custom Node.js MCP server over Chrome DevTools Protocol, reading indicator tables, OHLCV, price levels, and labels directly from the DOM
- **Deterministic signal evaluation** — evaluates PROS continuation setups, Opening Range Breakout structure, Initial Balance draw alignment, and macro invalidation — no AI calls until a genuine signal is detected
- **AI grading pipeline** — calls Claude only when the deterministic engine flags a setup; grades A–D with structured narration, macro context, and execution parameters
- **Discord delivery** — rich embeds with chart screenshots, routed by alert type to dedicated channels with anti-spam governance (cooldowns, daily caps, grade filters)
- **Macro intelligence** — monitors economic calendar, VIX, and breaking news via Finnhub, FMP, and Grok; fires risk-tier alerts to Discord's macro channel
- **Execution pipeline** — processes TradingView webhooks through a multi-gate risk engine, routes paper/live orders to Alpaca via REST
- **Trade journal** — full operational intelligence journal with NOVA AI per-trade review, behavioral tracking, reasoning timeline, screenshot replay, and performance analytics
- **Dashboard** — FastAPI-served HTML dashboard with live market data, session state, risk engine, journal, and bot controls

---

## Architecture

```
TradingView Desktop
      │ CDP :9222
      ▼
mcp/tradingview/               Custom Node.js MCP server
      │ subprocess
      ▼
donna_nova_reasoning.py        Deterministic evaluators + Claude grading
      │ AlertData
      ├──────────────────────► donna_alert_engine.py   Discord/Telegram delivery
      │
      ▼
main.py  (FastAPI / Render)    Webhooks · Dashboard · Journal · Market data
      │
      ▼
donna_execution.py             Multi-gate risk engine → Alpaca broker
```

**Two-environment split:**
- **Render (cloud)** — FastAPI backend, dashboard, macro loops, journal, webhook ingestion. Always on.
- **Local (trading machine)** — TradingView MCP, chart reading, NOVA reasoning monitor, Discord alerts. Active 09:15–16:00 ET weekdays via Windows Task Scheduler.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, uvicorn |
| AI | Anthropic Claude (claude-sonnet-4-6, claude-haiku-4-5) |
| Chart integration | Node.js, Chrome DevTools Protocol, custom MCP server |
| Broker | Alpaca REST API |
| Market data | Finnhub, yfinance, FMP, xAI Grok |
| Delivery | Discord Bot API, Telegram |
| Hosting | Render (cloud), Windows Task Scheduler (local) |
| TradingView | Pine Script (NOVA EXECUTION V1 indicator) |

---

## Repository Structure

```
D.O.N.N.A/
│
├── main.py                         # FastAPI app — all routes and background loops
├── requirements.txt
│
├── donna_nova_reasoning.py         # Core intelligence: chart reading, evaluation, Claude
├── donna_alert_engine.py           # Alert governance and Discord/Telegram delivery
├── donna_local_monitor.py          # Session monitor — 60s polling loop + MCP health
├── donna_execution.py              # Alpaca broker integration and risk gates
├── donna_execution_bridge.py       # Routes EXECUTION_READY alerts to execution layer
├── donna_config.py                 # Constants, env vars, API clients, file paths
├── donna_state.py                  # State persistence helpers, journal stats
├── donna_engines.py                # Dashboard payload builders (Harvey, scenarios)
├── donna_signals.py                # TradingView webhook signal parser
├── donna_signal_log.py             # Per-cycle NOVA evaluation log
├── donna_state_engine.py           # Session state — trades taken, locks, daily P&L
├── donna_risk_engine.py            # Position sizing, drawdown, R:R calculation
├── donna_macro_discord.py          # Macro intelligence Discord delivery
├── donna_headlines.py              # Economic calendar ingestion, red-folder governance
├── donna_news.py                   # News risk scoring — headlines → risk_state
├── donna_finnhub.py                # Live market data — quotes → risk_state
├── donna_health.py                 # System health checks across all subsystems
├── donna_assistant.py              # Claude conversational assistant
├── donna_analytics.py              # Performance analytics helpers
├── donna_html.py                   # Dashboard HTML/CSS/JS (~4,200 lines)
│
├── data/                           # Runtime state (gitignored, auto-generated)
│   ├── donna_risk_state.json       # Live market snapshot, VIX, macro risk
│   ├── donna_signal_log.json       # Full NOVA evaluation history
│   ├── donna_journal.json          # Trade records with AI analysis
│   └── ...                         # Execution trace, macro events, locks
│
├── mcp/tradingview/                # Custom TradingView MCP server (Node.js)
│   └── src/                        # CDP connection, chart read/write, screenshot
│
├── nova_knowledge_core/            # Strategy rules and methodology
│   ├── PROS_EVAN_INVESTING/        # PROS continuation strategy rules
│   ├── ORB_RP/                     # Opening Range Breakout rules
│   ├── INVALIDATION_RULES/         # Position invalidation logic
│   └── RULES/nova_strategy_core.json
│
├── nova_ui_vision/                 # UI design philosophy and mockups
├── indicators/                     # Pine Script — NOVA EXECUTION V1
├── scripts/                        # Windows PowerShell session launchers
├── tests/                          # Test suite
└── docs/                           # Technical documentation
```

---

## Quick Start

**Prerequisites:** Python 3.11+, Node.js 18+, TradingView Desktop

```bash
git clone --recurse-submodules <repo>
cd D.O.N.N.A
pip install -r requirements.txt
cp .env.example .env        # add API keys

cd mcp/tradingview
npm install
```

**Backend:**
```bash
uvicorn main:app --reload --port 8000
# Dashboard → http://localhost:8000/dashboard
```

**Local session monitor** (requires TradingView Desktop with CDP):
```bash
# Windows — launches TradingView + monitor together
powershell -ExecutionPolicy Bypass -File scripts/start_trading_session.ps1

# Or manually
python donna_local_monitor.py
```

---

## Environment Variables

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude — setup grading, journal analysis, assistant |
| `DISCORD_BOT_TOKEN` | Discord bot for alert delivery |
| `DISCORD_CHANNEL_LIVE` | Fallback alert channel ID |
| `DISCORD_CHANNEL_EXECUTION` | Execution-ready alerts |
| `DISCORD_CHANNEL_HEADS_UP` | Setup-forming alerts |
| `DISCORD_CHANNEL_MACRO` | Macro risk and calendar |
| `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` | Broker integration |
| `FINNHUB_API_KEY` | Market data and news |
| `GROK_API_KEY` | xAI Grok market intelligence |
| `TV_CDP_PORT` | TradingView CDP port (default: 9222) |
| `NOVA_AUTO_EXECUTE` | Enable automated execution (default: false) |

---

## License

Private. All rights reserved.
