# Deployment

DONNA runs across two environments simultaneously. Understanding the split is critical — the cloud backend and the local monitor serve different purposes and neither can fully substitute for the other.

---

## Architecture Split

```
┌─────────────────────────────────┐    ┌──────────────────────────────────────┐
│         Render (Cloud)          │    │         Trading Machine (Local)       │
│                                 │    │                                      │
│  FastAPI backend                │    │  TradingView Desktop (CDP port 9222) │
│  ├── /webhook                   │    │  MCP Server (Node.js)                │
│  ├── /dashboard                 │    │  donna_local_monitor.py              │
│  ├── /market-data               │    │  donna_nova_reasoning.py             │
│  ├── /risk-engine-data          │    │                                      │
│  ├── Macro intelligence loops   │    │  Runs: 09:15–11:00 ET weekdays       │
│  └── Morning brief (09:00 ET)   │    │  Auto-start: Task Scheduler          │
│                                 │    │                                      │
│  Always on                      │    │  Requires TradingView Desktop        │
└─────────────────────────────────┘    └──────────────────────────────────────┘
```

The cloud backend handles all persistent services — webhook reception, market data, macro loops, dashboard. The local monitor handles everything that requires a live TradingView Desktop connection, which Render cannot provide.

---

## Cloud Deployment (Render)

### Initial Setup

1. Create a new **Web Service** on Render
2. Connect the GitHub repository
3. Set the following:

| Setting | Value |
|---|---|
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Instance Type | Starter or above (background loops require persistent memory) |

4. Add all environment variables from `.env` in the Render dashboard under **Environment**

### Environment Variables (Render)

Set all variables from `.env.example`. At minimum:

```
ANTHROPIC_API_KEY
DISCORD_BOT_TOKEN
DISCORD_CHANNEL_LIVE
DISCORD_CHANNEL_MACRO
ALPACA_API_KEY
ALPACA_SECRET_KEY
FINNHUB_API_KEY
FMP_API_KEY
GROK_API_KEY
```

### Webhook URL

TradingView alert webhooks must point to:
```
https://<your-render-url>/webhook
```

Configure this in TradingView alert settings. The payload must be valid JSON — the NOVA EXECUTION V1 Pine Script indicator handles formatting automatically via `alert()` calls.

---

## Local Monitor Setup

The local monitor connects to TradingView Desktop via CDP and runs the NOVA AI reasoning pipeline. It must run on the same machine as TradingView.

### One-time Setup

```powershell
# Install Python dependencies
pip install -r requirements.txt

# Install MCP server dependencies
cd mcp/tradingview
npm install

# Register Windows Task Scheduler (auto-start at 9:15 AM ET weekdays)
powershell -ExecutionPolicy Bypass -File scripts/schedule_session.ps1
```

### Daily Operation

The Task Scheduler fires automatically at 9:15 AM. Alternatively, run manually:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_trading_session.ps1
```

This script:
1. Detects TradingView Desktop via `Get-AppxPackage`
2. Kills any existing TradingView process
3. Relaunches TradingView with `--remote-debugging-port=9222`
4. Opens `donna_local_monitor.py` in a persistent terminal window

The monitor runs until you close the terminal window. It is self-contained — closing Claude Code or any other process does not affect it.

### TradingView CDP Requirement

TradingView Desktop **must be launched with the CDP flag** for the MCP to connect:

```
TradingView.exe --remote-debugging-port=9222
```

The session launcher script handles this automatically. Do not launch TradingView manually during trading sessions — always use the launcher.

---

## Local Development

```bash
# Clone and install
git clone <repo>
cd D.O.N.N.A
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Install MCP server
cd mcp/tradingview && npm install && cd ../..

# Run backend locally
uvicorn main:app --reload --port 8000

# Run monitor (separate terminal, requires TradingView Desktop running with CDP)
python donna_local_monitor.py
```

Dashboard available at `http://localhost:8000/dashboard`

---

## Health Checks

| Endpoint | Purpose |
|---|---|
| `GET /` | Basic liveness check |
| `GET /check-env` | Verify all API keys and file state |
| `GET /system-health` | Cache state, data source status |
| `GET /system-check` | Full subsystem status — Alpaca, Grok, Finnhub, open positions |
| `GET /execution-gate` | Current execution permission state |
| `GET /alert-status` | Alert governance state and cooldowns |
| `GET /macro-status` | Macro Discord feed health |

---

## Monitoring

- **Execution trace** — `GET /execution/trace` returns every signal event from webhook receipt through verdict, gate checks, and broker response
- **Rejections** — `GET /execution/rejections` returns all blocked signals with gate context and rejection codes
- **State engine** — `GET /state-engine` returns full session state snapshot

---

## Updating

```bash
git pull origin main
# Render auto-deploys on push to main
# Local monitor picks up changes on next restart
```
