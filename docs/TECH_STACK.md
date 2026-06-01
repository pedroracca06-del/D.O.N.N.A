# Tech Stack

## Backend

| Technology | Version | Role |
|---|---|---|
| Python | 3.14 | Primary runtime |
| FastAPI | 0.135 | HTTP framework — webhooks, dashboard API, market data endpoints |
| Uvicorn | 0.42 | ASGI server |
| Pydantic | 2.12 | Request validation and data modelling |
| python-dotenv | 1.2 | Environment configuration |
| requests | 2.33 | Outbound HTTP — broker APIs, market data, Discord REST |

---

## AI / LLM

| Technology | Role |
|---|---|
| Anthropic API (Claude Sonnet 4.6 / Haiku 4.5) | Setup grading, alert generation, NOVA reasoning |
| xAI Grok API | Market intelligence summaries, sentiment analysis |

Claude is invoked only after a deterministic pre-assessment confirms a potential signal — zero API cost on quiet cycles. Haiku handles fast reasoning cycles; Sonnet is used for high-context evaluations.

---

## TradingView Integration

| Technology | Role |
|---|---|
| TradingView Desktop | Chart rendering, indicator output, alert webhooks |
| Chrome DevTools Protocol (CDP) | Live chart data bridge — connects Python to TradingView Desktop |
| Custom MCP Server (Node.js) | CLI wrapper around CDP — exposes `state`, `quote`, `ohlcv`, `data tables`, `screenshot`, `tab`, `symbol` commands |
| Pine Script (v6) | NOVA EXECUTION V1 indicator — PROS engine, ORB console, IB tracking, signal generation |
| TradingView Webhooks | Alert-triggered signal delivery to `/webhook` endpoint |

The MCP server is a custom Node.js process that connects to TradingView's internal WebSocket via CDP on port 9222. It exposes a CLI and JSON API used by the Python reasoning pipeline.

---

## Broker

| Technology | Role |
|---|---|
| Alpaca Broker API | Order execution, position management, account data |
| Alpaca REST API | Bracket orders, position queries, EOD close |

---

## Market Data

| Provider | Role |
|---|---|
| Finnhub | Real-time quotes, company news, earnings calendar |
| Financial Modeling Prep (FMP) | Economic calendar, sector data |
| Alpha Vantage | Supplementary quote data |

---

## Delivery

| Technology | Role |
|---|---|
| Discord Bot API (REST v10) | Primary alert channel — rich embeds with chart screenshots |
| Telegram Bot API | Fallback text delivery |

Discord delivers structured embeds with color-coded alert types, inline context fields, and an attached chart screenshot per alert. Governance prevents duplicate and spam delivery with per-type cooldowns and daily caps.

---

## Deployment

| Technology | Role |
|---|---|
| Render | Cloud hosting for FastAPI backend — always-on webhook receiver and dashboard |
| Windows Task Scheduler | Local auto-launch of TradingView + NOVA monitor at 9:15 AM ET weekdays |
| PowerShell | Session launcher scripts |

---

## Frontend (Dashboard)

The dashboard is server-side rendered HTML served directly by FastAPI at `/dashboard`. No frontend build step.

- Vanilla JS with fetch-based polling
- SSE (Server-Sent Events) for live signal feed
- No external CSS frameworks

---

## Development Tools

| Tool | Role |
|---|---|
| Claude Code | AI-assisted development — architecture, implementation, debugging |
| Git | Version control |
| VS Code | Primary editor |
| Node.js 18+ | MCP server runtime |
