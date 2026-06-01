# NOVA Delivery Architecture
**Status:** Load-bearing | **Version:** 1.0 | **Last updated:** 2026-05-30

Defines how operational state reaches users across all delivery layers.
Discord is the current primary delivery layer. The NOVA app is the target.

See also: `ARCHITECTURE_CORE.md` §2 (Discord as Bridge Layer)

---

## Delivery Layers

```
Operational State (source of truth)
        ↓
┌─────────────────────────────────────────────┐
│  Delivery Layer (thin view — format only)   │
├─────────────────┬───────────────────────────┤
│  Discord        │  NOVA App (Phase 2I)       │
│  (bridge)       │  (primary, future)         │
├─────────────────┼───────────────────────────┤
│  Telegram       │  API Endpoints             │
│  (fallback)     │  (Render backend)          │
└─────────────────┴───────────────────────────┘
```

**Rule:** Every delivery layer receives the same state object and formats it independently. State is never modified by delivery logic.

---

## Discord Architecture (Current)

### Channel Map

| Channel | Env Var | Alert Types | Fallback |
|---|---|---|---|
| #live-alerts | `DISCORD_CHANNEL_LIVE` | All unrouted alerts | None (required) |
| #heads-up | `DISCORD_CHANNEL_HEADS_UP` | HEADS_UP | #live-alerts |
| #execution | `DISCORD_CHANNEL_EXECUTION` | EXECUTION_READY | #live-alerts |
| #invalidation | `DISCORD_CHANNEL_INVALIDATION` | INVALIDATION | #live-alerts |
| #no-trade | `DISCORD_CHANNEL_NO_TRADE` | NO_TRADE | #live-alerts |
| #morning-brief | `DISCORD_CHANNEL_MORNING_BRIEF` | SESSION_BRIEF | #live-alerts |
| #macro-risk | `DISCORD_CHANNEL_MACRO` | All macro events | None (dedicated) |
| #system-health | `DISCORD_CHANNEL_SYSTEM_HEALTH` | Health reports | None |

### Alert Types

| Type | Trigger | Color | Cooldown |
|---|---|---|---|
| HEADS_UP | Setup forming (BUILDING state, OTE approaching) | Green `0x00C851` | 15 min |
| EXECUTION_READY | Setup confirmed (OTE tagged, SETUP_READY) | Blue `0x0080FF` | 30 min |
| INVALIDATION | Active setup broken | Red `0xFF4444` | 5 min |
| NO_TRADE | Session block active | Amber `0xFFBB33` | 20 min |
| SESSION_BRIEF | Morning intelligence brief | Purple `0x9B59B6` | 120 min |

### Macro Alert Severity

| Severity | Color | Events |
|---|---|---|
| CRITICAL | `0xFF0000` | CPI, NFP, FOMC day-of, circuit breakers |
| HIGH | `0xFF4444` | PPI, Retail Sales, GDP, Fed speakers |
| MEDIUM | `0xFFBB33` | Other HIGH-importance calendar events |
| LOW | `0x5865F2` | Suppressed — not delivered |

### Embed Contract

Every Discord embed must follow:
```
Title:       [emoji] [EVENT/SETUP NAME]           ← short, no repetition
Description: [timing] · [phase/severity]          ← one line
Fields:      max 6 fields, no paragraphs          ← fast scan
NOVA field:  2-3 lines, tactical language only    ← no AI prose
Footer:      NOVA [category] · [time ET]          ← always present
Timestamp:   UTC ISO (Discord renders locally)    ← always present
```

**Prohibited in embeds:**
- Paragraphs of text
- Repeated information (title info in description)
- Generic AI commentary in NOVA field
- More than 6 fields

### Anti-Spam Governance

**File:** `donna_alert_state.json` (trading alerts), `donna_macro_discord_state.json` (macro)

| Rule | Value |
|---|---|
| Daily alert cap | 20 (trading alerts) |
| Per-type cooldown | See Alert Types table above |
| Breaking news dedup | Last 20 headline keys stored |
| VIX alert cooldown | 60 minutes |
| Morning brief | Once per day, 09:00–09:20 ET window |
| Signal cleared on invalidation | Yes — allows fresh setup to form |

---

## Screenshot Pipeline

**Architecture:** Local machine only (CDP connection required)

```
Alert trigger
    ↓
capture_screenshot()  [donna_alert_engine.py]
    ↓
node src/cli/index.js screenshot --region chart  [MCP CLI]
    ↓
CDP Page.captureScreenshot()  [TradingView Desktop → Electron]
    ↓
PNG saved to mcp/tradingview/screenshots/
    ↓
send_discord() attaches as multipart file
    ↓
Discord embed + chart image
```

**Returns:** `file_path` key in MCP response JSON
**Fallback:** Most recent PNG in screenshots directory
**Cloud behavior:** Returns None on Render (no CDP) — embed sends without image, no error

**Key fix applied (2026-05-30):** `capture_screenshot()` now checks `file_path` key first (MCP actual return) before legacy fallback keys.

---

## Delivery Precedence

```
1. Discord (primary)      — rich embed + optional screenshot
2. Telegram (secondary)   — flat text, photo if available
3. API consumers          — JSON state objects (Render endpoints)
4. NOVA app (Phase 2I)    — full state feed, real-time
```

Both 1 and 2 run on every alert. Failure of Discord does not block Telegram and vice versa. Delivery result is recorded only if at least one succeeds.

---

## Future NOVA App Contract (Phase 2I)

The NOVA app will consume state objects directly — not Discord embeds.

What the NOVA app will display:
- Current session state (from `compute_session_quality_state()`)
- IB draw and liquidity map (from `compute_pros_state()`, `compute_orb_state()`)
- ORB definition and phase (from `compute_orb_state()`)
- PROS setup development (from `compute_pros_state()`)
- Macro state and event countdown (from `compute_macro_state()`)
- Execution state and behavioral blocks (from `compute_execution_state()`)
- Invalidation status (from `compute_invalidation_state()`)
- Active alert history

**Architectural implication:** Every `compute_Xstate()` function built now is also building the data layer for the NOVA app. No redesign needed at Phase 2I — only a new consumer.

---

## Render vs Local Responsibility

| Responsibility | Render (cloud) | Local machine |
|---|---|---|
| Alert delivery to Discord | YES | NO |
| Macro feed delivery | YES | NO |
| Claude AI evaluation | YES | NO |
| Webhook reception (Pine → NOVA) | YES | NO |
| Market data fetch (yfinance, FMP) | YES | NO |
| TradingView MCP connection | NO | YES |
| Chart reading (symbol, NOVA tables) | NO | YES |
| Screenshot capture | NO | YES |
| Live reasoning cycle (60s poll) | NO | YES (start_setup_monitor) |

**Rule:** Never try to connect to CDP from Render. Never expect MCP availability in cloud functions.
