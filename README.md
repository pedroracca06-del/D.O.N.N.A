# NOVA — AI Trading Intelligence System

**AI-native market intelligence and execution infrastructure for futures trading.**

NOVA is an AI-native market-intelligence and decision-support platform for NQ/MNQ futures. Its active surfaces focus on read-only analysis, market context, journal review, and the NOVA Intelligence assistant. Historical trading/execution infrastructure remains preserved but temporarily disabled and requires separate explicit approval before any future return.

Built for: **backend engineering** · **AI systems** · **fintech infrastructure**

---

## What It Does

- **Live chart intelligence** — connects to TradingView Desktop via a custom Node.js MCP server over Chrome DevTools Protocol, reading indicator tables, OHLCV, price levels, and labels directly from the DOM
- **PRIME-aware intelligence** - current context is evaluated against PRIME and its three active execution models: Strict OTE, 10AM Key Level Open, and ORB; PROS is superseded historical lineage only
- **AI intelligence pipeline** - Assistant, Journal Review, and Market Summary run through the centralized Intelligence gateway with bounded prompts, cache, budget, audit, and provenance-aware context
- **Discord delivery** — rich embeds with chart screenshots, routed by alert type to dedicated channels with anti-spam governance (cooldowns, daily caps, grade filters)
- **Macro intelligence** — monitors economic calendar, VIX, and breaking news via Finnhub, FMP, and Grok; fires risk-tier alerts to Discord's macro channel
- **Preserved execution infrastructure** - historical broker/risk/webhook code remains on disk for a future separately approved return, but it is not currently authorized or active
- **Trade journal** — full operational intelligence journal with NOVA AI per-trade review, behavioral tracking, reasoning timeline, screenshot replay, and performance analytics
- **Dashboard** - FastAPI-served NOVA interface with Overview, Markets, Journal, NOVA Intelligence, and Settings; intelligence answers expose supplied context and Git knowledge provenance without claiming citation

---

## Architecture

```
TradingView Desktop
      │ CDP :9222
      ▼
mcp/tradingview/               Custom Node.js MCP server
      │ subprocess
      ▼
engines/reasoning.py        Deterministic evaluators + Claude grading
      │ AlertData
      ├──────────────────────► delivery/alert_engine.py   Discord/Telegram delivery
      │
      ▼
main.py  (FastAPI / Render)    Webhooks · Dashboard · Journal · Market data
      │
      ▼
services/execution.py             Multi-gate risk engine → Alpaca broker
```

**Two-environment split:**
- **Render (cloud)** — FastAPI backend, dashboard, macro loops, journal, webhook ingestion. Always on.
- **Local (trading machine)** — TradingView MCP, chart reading, NOVA reasoning monitor, Discord alerts. Active 09:15–16:00 ET weekdays via Windows Task Scheduler.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, uvicorn |
| AI | Provider-abstracted NOVA Intelligence gateway; current runtime adapter: Anthropic Claude |
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
├── engines/reasoning.py         # Core intelligence: chart reading, evaluation, Claude
├── delivery/alert_engine.py           # Alert governance and Discord/Telegram delivery
├── monitor.py          # Session monitor — 60s polling loop + MCP health
├── services/execution.py              # Alpaca broker integration and risk gates
├── services/execution_bridge.py       # Routes EXECUTION_READY alerts to execution layer
├── core/config.py                 # Constants, env vars, API clients, file paths
├── core/state.py                  # State persistence helpers, journal stats
├── engines/engines.py                # Dashboard payload builders (Harvey, scenarios)
├── engines/signals.py                # TradingView webhook signal parser
├── delivery/signal_log.py             # Per-cycle NOVA evaluation log
├── core/state_engine.py           # Session state — trades taken, locks, daily P&L
├── engines/risk_engine.py            # Position sizing, drawdown, R:R calculation
├── delivery/macro_discord.py          # Macro intelligence Discord delivery
├── services/headlines.py              # Economic calendar ingestion, red-folder governance
├── services/news.py                   # News risk scoring — headlines → risk_state
├── services/finnhub.py                # Live market data — quotes → risk_state
├── health/health.py                 # System health checks across all subsystems
├── services/assistant.py              # Claude conversational assistant
├── engines/analytics.py              # Performance analytics helpers
├── ui/html.py                   # Dashboard HTML/CSS/JS (~4,200 lines)
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
?   ??? PROS_EVAN_INVESTING/        # Superseded historical PROS lineage
?   ??? ORB_RP/                     # Historical/research ORB material
?   ??? CURRENT/PRIME/              # Git-authoritative current PRIME doctrine
?   ??? CANDIDATES/                 # Non-authoritative promotion candidates
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
python monitor.py
```

---

## Environment Variables

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Current Anthropic runtime adapter for NOVA Intelligence features |
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
