# NOVA Architecture Core
**Status:** Load-bearing | **Version:** 2.1 | **Last updated:** 2026-05-30

This document is the authoritative source for NOVA's foundational architectural constraints.
Every build decision must be consistent with these rules.

---

## 1. State-First Architecture

**Rule:** Operational state objects are the source of truth. Delivery and UI layers consume state — they never define it.

```
Raw Data Sources
    ↓
compute_Xstate()        ← source of truth
    ↓
Consumers:
  - Discord embeds      (bridge layer, current)
  - NOVA app layer      (primary, Phase 2I)
  - API endpoints       (Render backend)
  - Health checks       (operational audit)
```

**Implication:** If a delivery layer needs a piece of information, that information must exist in the state object first. Embed builders are thin view functions — they format state, they do not derive it.

**Implemented in:** `compute_macro_state()` in `donna_macro_discord.py`
**Pattern to replicate:** `compute_pros_state()`, `compute_orb_state()`, `compute_session_quality_state()`, `compute_execution_state()`, `compute_invalidation_state()`

---

## 2. Discord Is a Bridge Layer

Discord is **not** the final operating environment.

Discord is:
- Temporary UI layer during Phase 2 validation
- Notification system (permanent role)
- Operational feed (permanent role)
- Workflow validation layer (Phase 2 role)

Discord is **not**:
- The core data model
- The source of intelligence
- The final user experience
- The authority on system state

**Architectural implication:** Never architect around Discord. The Discord embed format must never dictate what information the system computes. State is computed because it is operationally meaningful — not because an embed needs it.

---

## 3. Deterministic Before AI

**Rule:** Deterministic rule-based logic runs first. Claude/LLM is a quality grader and edge-case resolver — not the primary signal generator.

```
Deterministic pre-filter (fast, always available, no API cost)
    ↓
Signal classified? Yes → Claude (grading, entry levels, notes)
Signal classified? No  → skip Claude, return empty
```

**Implemented in:** `run_reasoning_cycle()` in `donna_nova_reasoning.py`
**Implication:** The system must function at reduced quality without AI. AI upgrades output — it does not own it.

---

## 4. Tactical Language Standard

NOVA output (alerts, assessments, NOVA fields) must be:
- Concise — max 3 lines per NOVA block
- Operational — specific conditions, levels, actions
- Glanceable — readable in under 3 seconds on mobile
- Deterministic — rule-based vocabulary, not generative prose

**Good:**
- `ORB unreliable at open.`
- `Elevated sweep probability both sides.`
- `Stand aside until 09:45 ET.`
- `Grade A only. Size -50%.`

**Prohibited:**
- Verbose macro commentary
- Generic AI sentiment language
- Paragraphs in operational fields
- Obvious market observations

---

## 5. Local vs Cloud Separation

| Layer | Where | What |
|---|---|---|
| Intelligence + routing | Render (cloud) | Claude eval, alert delivery, macro feed, state management |
| Chart capture + MCP | Local machine | TradingView CDP, screenshot pipeline, live chart reading |

**Rule:** Never deploy MCP/CDP code to Render. Never expect screenshot availability on Render. The cloud layer receives webhook payloads and delivers to Discord — it does not see the chart directly.

**Implication:** Screenshot attachments on alerts are local-only. Cloud alerts send embed-only. This is intentional and correct.

---

## 6. Single-Position Architecture

NOVA operates one position at a time. No stacking, no hedging, no concurrent setups.

**Implication:**
- Alert governance enforces one active signal per symbol
- Execution state tracks position existence before allowing new entries
- Invalidation of one setup clears the signal — no overlap

---

## 7. Quality Over Quantity

**Rule:** Silence is correct when there is no edge. A missed alert is better than a false positive.

Applied to:
- Setup grading (Grade C or D → no alert)
- Macro feed (LOW severity events → suppressed)
- Session quality (C/Standby → no EXECUTION_READY)
- Anti-spam governance (cooldowns, daily caps)

---

## 8. Session Window is Hard

Trading window: **09:30–11:00 ET, Monday–Friday**

No alerts, no entries, no execution outside this window — regardless of indicator state.
This is a hard rule, not a soft preference.

Exception: SESSION_BRIEF and macro alerts may fire outside this window.

---

## 9. Operational Validation Before App Migration

**Rule:** The NOVA app becomes the primary operations center only after the bot
proves stable in live conditions. Stability must be earned, not assumed.

Minimum validation gates before Phase 2I:
1. Live session test (full NY open, real signals)
2. Governance reliability (cooldowns, caps, dedup under pressure)
3. Prop-firm connectivity (funded account execution live)
4. Cross-feed integration (macro → session quality → alert aggressiveness)
5. Intelligence stabilization (no false positives in sustained operation)

**Implication:** Infrastructure being complete does not mean the system is
ready for app migration. Operational proof is the gate — not build completion.

---

## 10. Prop-Firm Connectivity Is Pre-App Infrastructure

Prop-firm execution connection must exist before the app launches.
The Trading Bot Connection tab in the NOVA app requires this plumbing.
Build the execution routing layer in Phase 2, surface it in Phase 2I.

---

## Core File Map

| File | Role |
|---|---|
| `donna_config.py` | Env vars, API clients, shared utilities |
| `donna_nova_reasoning.py` | Live intelligence pipeline (MCP → evaluators → Claude → AlertData) |
| `donna_alert_engine.py` | Alert delivery (Discord + Telegram, governance, screenshot) |
| `donna_macro_discord.py` | Macro intelligence feed (compute_macro_state → #macro-risk) |
| `donna_headlines.py` | Economic calendar fetcher (FMP + ForexFactory → donna_macro_events.json) |
| `donna_finnhub.py` | Market snapshot fetcher (yfinance → donna_risk_state.json) |
| `donna_news.py` | Live news scorer (Finnhub/FMP → headline_risk) |
| `donna_health.py` | Operational health check (pre-flight audit) |
| `donna_state_engine.py` | Session state authority (trades, permission, locks) |
| `donna_risk_engine.py` | Risk management (position sizing, drawdown) |
| `main.py` | FastAPI server, background loops, webhook endpoints |
