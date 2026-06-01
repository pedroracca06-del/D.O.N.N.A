# DONNA / NOVA

**AI-native market intelligence and operational trading infrastructure for futures.**

DONNA is the backend execution and intelligence layer. NOVA is the AI reasoning engine embedded within it. Together they form a real-time system that reads live TradingView charts via CDP, evaluates trading setups against a deterministic rule engine, calls Claude (Anthropic) for grading and narration, and delivers structured alerts to Discord with chart screenshots.

Built for trading MES/ES and MNQ/NQ futures during the NY Open session.

---

## What It Does

- **Live chart reading** — connects to TradingView Desktop via Chrome DevTools Protocol (CDP) and a custom MCP server, reading NOVA indicator tables, OHLCV data, price levels, and labels directly from the chart
- **Deterministic pre-assessment** — evaluates PROS continuation setups, ORB auction structure, IB draw alignment, and invalidation signals without any API calls
- **AI grading** — calls Claude (Anthropic) only when a genuine signal is detected; grades setup quality A–D and generates structured Discord alert fields
- **Discord delivery** — rich embeds with chart screenshots, routed by alert type to dedicated channels with anti-spam governance
- **Macro intelligence** — monitors economic calendar events, VIX conditions, and breaking news via Finnhub, FMP, and Grok; delivers risk context to a dedicated macro channel
- **Execution pipeline** — processes TradingView webhooks, applies a multi-gate risk engine, and routes live orders to Alpaca broker
- **Dashboard** — FastAPI-served HTML dashboard with live market data, risk engine, trade journal, and session status

---

## Architecture Overview

```
TradingView Desktop
      │
      │  CDP (port 9222)
      ▼
  MCP Server (Node.js)          ← custom TradingView MCP
      │
      │  subprocess / JSON
      ▼
donna_nova_reasoning.py         ← deterministic evaluators + Claude grading
      │
      │  AlertData
      ▼
donna_alert_engine.py           ← governance + Discord/Telegram delivery
      │
      ├── REST API (webhooks + dashboard)
      ▼
main.py  (FastAPI)              ← webhook ingestion, market data, journal
      │
      ▼
donna_execution.py              ← Alpaca broker integration
```

---

## Repository Structure

```
D.O.N.N.A/
├── main.py                        # FastAPI app — webhooks, dashboard, market data
├── donna_nova_reasoning.py        # NOVA AI reasoning pipeline
├── donna_alert_engine.py          # Alert governance + Discord/Telegram delivery
├── donna_local_monitor.py         # Local session monitor (runs during NY Open)
├── donna_state_engine.py          # Centralised state management
├── donna_execution.py             # Alpaca broker integration + risk gates
├── donna_config.py                # Environment, constants, API clients
├── donna_signals.py               # TradingView webhook signal processor
├── donna_engines.py               # Dashboard payload builders
├── donna_risk_engine.py           # Position sizing, drawdown, R:R calculation
├── donna_macro_discord.py         # Macro intelligence Discord delivery
├── donna_html.py                  # Dashboard HTML
├── indicators/
│   └── nova_execution_v1.pine     # TradingView Pine Script indicator
├── mcp/tradingview/               # Custom TradingView MCP server (Node.js)
├── scripts/
│   ├── start_trading_session.ps1  # One-click session launcher
│   └── schedule_session.ps1       # Windows Task Scheduler registration
└── NOVA_KNOWLEDGE_CORE/           # Strategy rules and knowledge base (JSON)
```

---

## Quick Start

**Prerequisites:** Python 3.11+, Node.js 18+, TradingView Desktop

```bash
git clone <repo>
cd D.O.N.N.A
pip install -r requirements.txt
cp .env.example .env   # fill in API keys
cd mcp/tradingview && npm install
```

**Run the backend:**
```bash
uvicorn main:app --reload --port 8000
```

**Run the local session monitor:**
```bash
python donna_local_monitor.py
```

Or run `scripts/start_trading_session.ps1` — launches TradingView in CDP mode and the monitor together.

---

## Environment Variables

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API — setup grading and alert generation |
| `DISCORD_BOT_TOKEN` | Discord bot for alert delivery |
| `DISCORD_CHANNEL_LIVE` | Fallback alert channel ID |
| `DISCORD_CHANNEL_EXECUTION` | Execution-ready alert channel |
| `DISCORD_CHANNEL_HEADS_UP` | Setup-forming alert channel |
| `DISCORD_CHANNEL_MACRO` | Macro risk and calendar channel |
| `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` | Broker integration |
| `FINNHUB_API_KEY` | Market data and news |
| `FMP_API_KEY` | Financial Modeling Prep data |
| `GROK_API_KEY` | xAI Grok market intelligence |
| `TELEGRAM_BOT_TOKEN` | Telegram fallback delivery |

---

## License

Private. All rights reserved.
