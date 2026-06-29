# MCP Architecture Design
## Reliability Upgrade + Intelligence Upgrade — Design Document

**Status**: Design only. No code changes in this document.  
**Date**: 2026-06-29  
**Goal**: Turn TradingView MCP from a fragile chart reader into NOVA's reliable market sensor,
memory system, replay system, and intelligence feedback loop.

---

## 1. Current MCP Architecture

### What MCP Is

The TradingView MCP is a Node.js subprocess that bridges NOVA's Python intelligence pipeline
to the running TradingView Desktop application via Chrome DevTools Protocol (CDP) on port 9222.

**Call path:**
```
monitor.py (60s poll loop)
  → _collect_all_contexts()  in engines/reasoning.py
    → read_chart_context(symbol)
      → _run_mcp(*args)
        → subprocess: node mcp/tradingview/src/cli/index.js <tool> <args>
          → connection.js → CDP :9222 → TradingView DOM
            → returns JSON stdout → parsed in Python
```

### What MCP Reads Per Cycle

For each symbol (MES1!, MNQ1!) in sequence with 90-second dwell:

| MCP Tool | What It Returns | Used For |
|---|---|---|
| `chart_get_state` | symbol, timeframe, indicator list, entity IDs | Identity verification |
| `quote_get` | last price, OHLC, volume | Signal context |
| `data_get_ohlcv` | 20 bars of OHLCV | Price structure |
| `data_get_pine_labels` | Text+price label pairs | Legacy level reading |
| `data_get_pine_lines` | Horizontal price lines | Legacy level reading |
| `data_get_pine_tables` | Raw table rows from indicator | NOVA BRIDGE + legacy panels |

Total subprocess calls per symbol: ~6. Total per full cycle: ~12.

### Node.js MCP Server — Functional Map

The server (`mcp/tradingview/src/server.js`) registers 78+ tools across 14 modules:

- **Health**: `tv_health_check`, `tv_discover`, `tv_ui_state`, `tv_launch`
- **Chart nav**: `chart_get_state`, `chart_set_symbol`, `chart_set_timeframe`, `chart_set_type`, `chart_manage_indicator`
- **Data reads**: `data_get_ohlcv`, `data_get_study_values`, `quote_get`, `data_get_pine_lines`, `data_get_pine_labels`, `data_get_pine_tables`, `data_get_pine_boxes`
- **Pine dev**: `pine_set_source`, `pine_get_source`, `pine_compile`, `pine_smart_compile`, `pine_get_errors`, `pine_get_console`, `pine_save`
- **Screenshot**: `capture_screenshot` (CDP or API method, saves to `screenshots/`)
- **Replay**: `replay_start`, `replay_step`, `replay_autoplay`, `replay_stop`, `replay_trade`, `replay_status`
- **Drawing**: `draw_shape`, `draw_list`, `draw_clear`, `draw_remove_one`
- **Alerts**: `alert_create`, `alert_list`, `alert_delete`
- **UI automation**: `ui_click`, `ui_open_panel`, `ui_keyboard`, `ui_type_text`, `layout_switch`
- **Batch**: `batch_run` (symbol/timeframe sweep with configurable delay)
- **Pane**: `pane_list`, `pane_set_layout`, `pane_set_symbol`
- **Tab**: `tab_list`, `tab_new`, `tab_switch`

### NOVA BRIDGE — Current Schema (21 rows, 2 cols, `position.bottom_left`)

The Pine Script indicator renders a hidden 21-row table. NOVA uses this as the
automation contract. Fields are frozen — the parser reads them by key name.

| Row | Key | Example Values |
|---|---|---|
| 0 | `NOVA BRIDGE` | (header) |
| 1 | `CMD` | `BUY`, `SELL`, `WATCH LONG`, `WATCH SHORT`, `WAIT` |
| 2 | `SYS_STATE` | `ELITE ICT LONG`, `ORB EXPANSION BULL`, `TRAP RISK`, ... |
| 3 | `SCORE` | `72` (integer 0–100) |
| 4 | `CONF` | `81% HIGH` |
| 5 | `PROS_ENG` | `CONTINUATION`, `ACTIVE`, `WAIT` |
| 6 | `P_DISPL` | `BULL`, `BEAR` |
| 7 | `P_RETRACE` | `SHALLOW`, `MID`, `OTE`, `DEEP`, `TOO DEEP` |
| 8 | `P_OTE` | `TAGGED`, `SHALLOW`, `MID ONLY` |
| 9 | `P_CONT` | `CONFIRMED`, `BUILDING`, `ZONE TOUCH` |
| 10 | `P_QUALITY` | `ELITE`, `STRONG`, `GOOD`, `WEAK` |
| 11 | `P_STDV` | `EXTREME`, `STRETCHED`, `NORMAL` |
| 12 | `IB H` | `21487.25` (price) |
| 13 | `IB L` | `21340.50` (price) |
| 14 | `O_STATE` | `ORB_EXPANDING`, `ORB_READY`, `ORB_FAILED`, ... |
| 15 | `O_BIAS` | `BULL`, `BEAR`, `NEUTRAL` |
| 16 | `O_TYPE` | `MID_REJECT`, `LIQ_REJECT`, `EDGE_REJECT` |
| 17 | `O_REJ_Q` | `ELITE`, `STRONG`, `GOOD`, `WEAK` |
| 18 | `O_HIGH` | `21510.00` |
| 19 | `O_MID` | `21425.50` |
| 20 | `O_LOW` | `21341.00` |

---

## 2. Current MCP Limitations

### A. Subprocess Fragility
Each MCP call is a cold subprocess (`node src/cli/index.js`). No persistent connection.
No shared state. No warm-up cache. ~200–400ms startup overhead per call, ~6 calls per symbol
= 1.2–2.4 seconds of subprocess overhead per cycle before any CDP latency.

### B. No Chart Identity Verification
`read_chart_context()` switches the active TradingView chart to a symbol and reads.
But it does not verify the chart finished loading before reading. If TradingView is slow
(network, chart switching lag), the read captures stale data or the wrong symbol's data.
There is no "confirm symbol loaded" check between `chart_set_symbol` and the data reads.

### C. Table Detection Is Brittle
`parse_nova_tables()` locates the NOVA BRIDGE by scanning all tables for a cell containing
"NOVA BRIDGE". If TradingView renders two tables or the indicator is hidden/missing,
the scan fails silently and falls to the legacy three-table parser, which is position-based
and highly sensitive to indicator panel layout changes.

### D. No Read Confidence Signal
After reading, NOVA has no way to know if the data was fresh. A `quote_get` returning
a price 4 seconds old looks identical to one 40 seconds old. Stale IB levels, stale ORB
state, stale scores — all pass through silently.

### E. No Cross-Validation Against External Truth
IB levels from the BRIDGE (Pine Script computation) are only loosely checked against
`_compute_ib_from_yfinance()`. The threshold is 75 NQ points (`IB_STALE_THRESHOLD`).
ORB levels, PROS state, and CMD are never cross-checked against any external source.

### F. No Snapshot History
Every read cycle overwrites the prior read. There is no record of what the indicator
said 3 minutes ago, 15 minutes ago, or yesterday. Replay, debugging, and post-trade
review require guessing from journal entries and Discord alerts.

### G. Replay Infrastructure Not Connected to Intelligence
The MCP has full replay mode (`replay_start`, `replay_step`, `replay_trade`) but nothing
in NOVA's intelligence layer uses it. Replay is an orphaned capability.

### H. No Setup Fingerprinting
NOVA has no concept of "this setup looks like setup #47 from two weeks ago." Each
evaluation starts cold. Pattern similarity, historical base rate per setup type, and
draw-independence cannot be computed.

### I. Limited Error Taxonomy
MCP failures return one of two outcomes: success or "No TradingView chart target found."
There is no distinction between CDP connection lost, chart switching lag, indicator missing,
table format changed, or partial read (some fields present, some null).

---

## 3. Current Failure Points

Ranked by operational risk:

### F1 — Chart Not Loaded When Read Occurs (HIGH)
Trigger: TradingView is slow switching symbols. MCP reads immediately after `chart_set_symbol`.
Result: Data from previous symbol is returned with new symbol name. NOVA evaluates the wrong data.
Current mitigation: None. The 90-second dwell mitigates frequency but not the loading lag problem.

### F2 — Indicator Removed or Hidden (HIGH)
Trigger: User accidentally removes NOVA EXECUTION V1, or TradingView resets on crash.
Result: `parse_nova_tables()` finds no BRIDGE, falls to legacy parser, which fails.
`_classify_signal()` receives empty context. No alert, no log, no Discord notification.
Current mitigation: Health check in `monitor.py` catches MCP failure after 3 consecutive cycles.

### F3 — NOVA BRIDGE Position Changes (MEDIUM)
Trigger: Pine Script update moves table to different position, or a second table exists.
Result: The BRIDGE scan might match the wrong table if "NOVA BRIDGE" text appears elsewhere.
Current mitigation: Row-0 header check provides partial protection.

### F4 — CDP Connection Lost Mid-Cycle (MEDIUM)
Trigger: TradingView restarts, CDP port becomes unavailable.
Result: All subprocess calls fail. `_run_mcp()` returns None. Full cycle produces no data.
Current mitigation: `_MCP_FAIL_THRESHOLD = 3` in `monitor.py`. Discord alert after 3 failures.

### F5 — IB Level Stale (MEDIUM)
Trigger: Pine Script's 1-minute IB computation is stale (e.g., chart loaded after IB window).
Result: IB H / IB L in BRIDGE shows `—`. Cross-validation against yfinance triggers IB_STALE flag.
Current mitigation: `IB_STALE_THRESHOLD = 75.0` NQ pts. `_compute_ib_from_yfinance()` fills gap.

### F6 — Quote Latency (LOW)
Trigger: Finnhub quote cache is stale, yfinance is slow.
Result: Price context in Claude prompt is minutes old during volatile sessions.
Current mitigation: Accepted. Quote is supplementary, not decision-making.

### F7 — Node.js Version Conflict (LOW)
Trigger: Windows updates Node.js, MCP server throws on startup.
Result: All subprocess calls fail immediately with non-zero exit code.
Current mitigation: None. Would surface as F4 (CDP lost) in health monitoring.

---

## 4. What Execution Depends on Today

The exact fields from `parse_nova_tables()` that gate execution decisions:

```
cmd          → _classify_signal() — primary gate (BUY/SELL triggers signal path)
score        → _apply_conviction_gate() — int compared to CONVICTION_THRESHOLD
conf_pct     → _apply_conviction_gate() — float from "81% HIGH" parsing
sys_state    → Claude prompt context + narration
pros_engine  → _evaluate_pros_phase() input
p_displ      → displacement direction evaluation
p_retrace    → OTE zone evaluation
p_ote        → OTE tag confirmation
p_cont       → continuation phase check
p_quality    → signal quality gate
p_stdv       → displacement health check
ib_high      → _compute_ib_from_yfinance() cross-validation
ib_low       → same
o_state      → _evaluate_orb_phase() input
o_bias       → ORB bias alignment check
o_type       → entry type classification
o_rej_q      → ORB rejection quality gate
o_high       → ORB level cross-check
o_mid        → ORB midpoint reference
o_low        → ORB level cross-check
```

**Secondary reads** (not from BRIDGE, but from other MCP calls):
```
quote_get → last_price → Claude prompt context, session P&L tracking
data_get_ohlcv → bars → structural context, confirmation bars
chart_get_state → symbol, timeframe → identity check (loose)
```

If any BRIDGE field is missing, the default is `None` or `""`. Missing `cmd` → signal
classifier treats it as `WAIT`. Missing `score` → conviction gate defaults to 0 (blocked).

---

## 5. What Should Move to NOVA BRIDGE

The current BRIDGE has 20 data rows (rows 1–20). Pine Script v6 has no hard limit on
table rows. The BRIDGE should be extended to add fields that eliminate ambiguity in
the Python parser and remove cross-validation guesswork.

### Priority 1 — Already computed by Pine, not yet exposed

| Proposed Field | Key | What It Carries |
|---|---|---|
| Bridge schema version | `BRIDGE_VER` | Integer, increments on schema change. Parser rejects mismatches. |
| Symbol ticker | `TICKER` | The symbol the indicator is running on (MES1!, MNQ1!). Chart identity confirmation. |
| Timeframe | `TF` | Active chart timeframe at read time. Detects drift. |
| IB status | `IB_STATUS` | `FORMING`, `COMPLETE`, `STALE`, `PRE` — Pine's own assessment of IB completeness. |
| Session | `SESSION` | `ASIA`, `LONDON`, `NY_PRE`, `NY_OPEN`, `NY_CASH`, `LUNCH`, `POWER`, `OFF` |
| ORB active flag | `ORB_ACTIVE` | `1` or `0` — whether ORB framework is running on this bar |
| PROS active flag | `PROS_ACTIVE` | `1` or `0` — whether PROS engine is tracking a leg |
| Signal cooldown | `COOLDOWN` | `1` if in cooldown (signal suppressed), `0` if ready |
| Trap risk | `TRAP` | `1` or `0` — currently readable via `data_get_study_values` but should be in BRIDGE |
| ICT step | `ICT_STEP` | `0`–`6` — current ICT setup stage |
| Peer alignment | `PEER_ALIGN` | `CONFIRM`, `CONFLICT`, `NEUTRAL` — cross-market bias |
| Draw target | `DRAW_TARGET` | Nearest unfilled draw target price (T1 or external liq level) |
| Draw direction | `DRAW_DIR` | `UP`, `DOWN`, `NONE` — primary draw direction |

### Priority 2 — New fields that enable intelligence upgrades

| Proposed Field | Key | What It Enables |
|---|---|---|
| Score delta | `SCORE_DELTA` | Change in score vs 3 bars ago. Momentum confirmation. |
| Confidence delta | `CONF_DELTA` | Confidence trending up or down. Setup ripening vs decaying. |
| IB range points | `IB_RANGE` | `ibHigh - ibLow` in NQ pts. Volatility context for sizing. |
| ORB range points | `ORB_RANGE` | `orbHigh - orbLow`. ATR context for ORB setup quality. |
| Days since last signal | `LAST_SIG_BARS` | Bars since last signal fired. Freshness signal. |
| Displacement size | `DISPL_SIZE` | NQ points of the PROS displacement leg. Sizing input. |
| Invalidation price | `INVAL_PRICE` | Hard stop reference from Pine computation. |

### What Should NOT Be Added to BRIDGE
- Historical patterns — Python handles history
- P&L data — execution layer only
- Any computed output that requires cross-file joins
- Fields that require real-time market data (quotes, externals) — those stay in Python

---

## 6. Proposed NOVA BRIDGE Schema — Extended

Schema version increments when any row is added, removed, or renamed.
All existing rows (0–20) keep their positions. New rows append from 21 onward.

```
Row 0:  NOVA BRIDGE     (header — parser anchor)
Row 1:  CMD             BUY | SELL | WATCH LONG | WATCH SHORT | WAIT
Row 2:  SYS_STATE       scenario string
Row 3:  SCORE           0–100 integer
Row 4:  CONF            "81% HIGH" format
Row 5:  PROS_ENG        CONTINUATION | ACTIVE | WAIT
Row 6:  P_DISPL         BULL | BEAR
Row 7:  P_RETRACE       SHALLOW | MID | OTE | DEEP | TOO DEEP
Row 8:  P_OTE           TAGGED | SHALLOW | MID ONLY
Row 9:  P_CONT          CONFIRMED | BUILDING | ZONE TOUCH
Row 10: P_QUALITY       ELITE | STRONG | GOOD | WEAK
Row 11: P_STDV          EXTREME | STRETCHED | NORMAL
Row 12: IB H            price float or —
Row 13: IB L            price float or —
Row 14: O_STATE         ORB state machine string
Row 15: O_BIAS          BULL | BEAR | NEUTRAL
Row 16: O_TYPE          MID_REJECT | LIQ_REJECT | EDGE_REJECT
Row 17: O_REJ_Q         ELITE | STRONG | GOOD | WEAK
Row 18: O_HIGH          price or —
Row 19: O_MID           price or —
Row 20: O_LOW           price or —
--- NEW (Priority 1) ---
Row 21: BRIDGE_VER      integer (start at 2)
Row 22: TICKER          symbol string (e.g. "MES1!")
Row 23: TF              timeframe string (e.g. "5")
Row 24: IB_STATUS       FORMING | COMPLETE | STALE | PRE
Row 25: SESSION         ASIA | LONDON | NY_PRE | NY_OPEN | NY_CASH | LUNCH | POWER | OFF
Row 26: ORB_ACTIVE      1 | 0
Row 27: PROS_ACTIVE     1 | 0
Row 28: COOLDOWN        1 | 0
Row 29: TRAP            1 | 0
Row 30: ICT_STEP        0–6
Row 31: PEER_ALIGN      CONFIRM | CONFLICT | NEUTRAL
Row 32: DRAW_TARGET     price or —
Row 33: DRAW_DIR        UP | DOWN | NONE
--- NEW (Priority 2, add later) ---
Row 34: SCORE_DELTA     -10 to +10 integer
Row 35: CONF_DELTA      -10 to +10 integer
Row 36: IB_RANGE        NQ points integer
Row 37: ORB_RANGE       NQ points integer
Row 38: DISPL_SIZE      NQ points integer
Row 39: INVAL_PRICE     price or —
```

**Table declaration change required in Pine Script:**
```pine
var table novaBridge = table.new(position.bottom_left, 2, 40, border_width=0)
```

**Schema contract rules:**
1. Keys in rows 0–20 are frozen forever. Their meaning cannot change.
2. New fields append only. Rows are never reordered.
3. BRIDGE_VER in row 21 tells the Python parser which schema it is reading.
4. Parser must check `BRIDGE_VER >= 2` before reading rows 21+.
5. Any field not present returns the Python parser's safe default.

---

## 7. Parser Hardening Plan

Current `parse_nova_tables()` in `engines/reasoning.py` has these weaknesses:
- Finds BRIDGE by scanning all tables for "NOVA BRIDGE" text (could match the wrong table)
- Falls back to legacy three-table parser silently
- Returns partial data without indicating which fields were missing
- No version check

### Hardening Steps (in priority order)

**H1 — Version Gate**  
After finding the BRIDGE table, check row 21 for `BRIDGE_VER`. If < 2, fall to legacy parser
and log a warning. If 2+, parse rows 21–39 for extended fields. This makes old indicators
non-fatal but discoverable.

**H2 — Field Completeness Tracking**  
Return a `bridge_completeness` float (0.0–1.0) with every parse. Count non-None, non-"—"
fields divided by expected field count. The reasoning pipeline can use this as a confidence
signal (< 0.6 → do not fire execution alert).

**H3 — TICKER Field Cross-Check**  
Parse `TICKER` from row 22. Compare against the symbol passed to `read_chart_context()`.
If they differ → mark context as `symbol_mismatch=True` → skip signal classification entirely.

**H4 — Explicit Legacy Fallback Log**  
When falling to legacy parser, emit a structured log event (not just print). The signal log
should record `parser_mode: "BRIDGE"` or `parser_mode: "LEGACY"` on every cycle.

**H5 — Required vs Optional Fields**  
Classify fields into REQUIRED (CMD, SCORE, CONF, SYS_STATE) and OPTIONAL (PROS fields when
ORB_ACTIVE=1, ORB fields when PROS_ACTIVE=1). Missing REQUIRED fields → block evaluation.
Missing OPTIONAL fields → soft warning in log.

**H6 — Parse Error Taxonomy**  
Return one of: `"ok"`, `"bridge_missing"`, `"bridge_stale"`, `"version_mismatch"`,
`"symbol_mismatch"`, `"partial"`. The reasoning pipeline branches on this, not on None checks.

---

## 8. Chart Identity Lock Design

The goal: guarantee that NOVA reads data for the symbol it thinks it's reading.

### Current State
`chart_set_symbol("MES1!")` is called, then after a brief wait, data is read.
There is no verification that TradingView completed the symbol switch.

### Proposed: Read-Verify-Read Pattern

```
1. Call chart_set_symbol(target)
2. Wait 2 seconds (current minimum)
3. Call chart_get_state() → read actual_symbol
4. If actual_symbol != target:
   - Wait 3 more seconds
   - Call chart_get_state() again
   - If still wrong: mark context as identity_failed=True, skip evaluation
5. If actual_symbol == target:
   - Proceed with quote_get, data_get_pine_tables, etc.
```

### TICKER Field Redundancy
Once BRIDGE_VER >= 2 is deployed, the TICKER field (row 22) provides a second identity
check from inside the indicator itself. `actual_ticker == chart_get_state().symbol == BRIDGE.TICKER`
is a three-way lock. Any mismatch in the chain → skip.

### Symbol Normalization
TradingView may return `"MES1!"` or `"CME_MINI:MES1!"` depending on resolution context.
The identity check must normalize both to `"MES1!"` before comparison.

### Home Symbol Restoration
`_collect_all_contexts()` already restores to MNQ home after scanning. The identity lock
should also verify restoration succeeded. If `chart_get_state()` after restoration shows
a symbol other than MNQ home → emit a health alert but do not retry indefinitely.

---

## 9. Health / Confidence Scoring Model

Each chart read should produce a `read_confidence` score (0.0–1.0) alongside the data.
This score feeds into the signal classifier as a meta-input.

### Components

| Component | Weight | What Degrades It |
|---|---|---|
| Bridge completeness | 30% | Missing required fields, partial parse |
| Symbol identity confirmed | 25% | Mismatch between requested and actual symbol |
| Data recency | 20% | Time since last successful read (>5 min = 0) |
| BRIDGE_VER match | 15% | Wrong version → using legacy parser |
| Quote timestamp | 10% | Quote older than 60 seconds |

### Formula
```
read_confidence = (
  0.30 * bridge_completeness +
  0.25 * (1.0 if identity_confirmed else 0.0) +
  0.20 * max(0, 1 - (seconds_since_last_read / 300)) +
  0.15 * (1.0 if version_ok else 0.0) +
  0.10 * max(0, 1 - (quote_age_seconds / 60))
)
```

### Usage Gates
- `read_confidence < 0.5` → skip signal classification, log `CONFIDENCE_BLOCK`
- `read_confidence < 0.7` → allow HEADS_UP but block EXECUTION_READY
- `read_confidence >= 0.7` → all alert types allowed

### MCP Health Score (System Level)
Separate from per-read confidence. Measures system reliability over the last 10 cycles.

```
mcp_health = successful_reads_last_10 / 10
```

- `mcp_health < 0.5` → Discord system health alert (currently: after 3 consecutive fails)
- `mcp_health < 0.7` → suppress all EXECUTION_READY alerts even if read_confidence is ok
- `mcp_health >= 0.9` → normal operation

---

## 10. Cross-Validation Plan

The current code cross-validates IB levels (Pine vs yfinance) with one threshold.
Proposed: extend to all major numeric outputs.

### Cross-Validation Matrix

| Field | Primary Source | Cross-Source | Tolerance | Action on Mismatch |
|---|---|---|---|---|
| IB High | NOVA BRIDGE row 12 | `_compute_ib_from_yfinance()` | 75 NQ pts | Flag `IB_STALE`, block ORB gate (current) |
| IB Low | NOVA BRIDGE row 13 | `_compute_ib_from_yfinance()` | 75 NQ pts | Same |
| Last Price | `quote_get.last` | yfinance live quote | 0.5% | Log warning, use yfinance |
| ORB High | NOVA BRIDGE row 18 | yfinance first 15-min high | 15 NQ pts | Log warning only (tolerance wide for timing differences) |
| ORB Low | NOVA BRIDGE row 20 | yfinance first 15-min low | 15 NQ pts | Same |
| Session | NOVA BRIDGE row 25 | `session_label()` from Python time | Exact | Log if mismatch; Python time is authoritative |
| Ticker | NOVA BRIDGE row 22 | `chart_get_state().symbol` | Exact | Block read — identity failure |

### Cross-Validation Logging
Every cross-validation result (pass or fail) should be written to the signal log with:
- field name
- primary value
- cross-source value
- delta
- outcome (pass/warn/block)

This creates an audit trail for calibrating tolerances over time.

---

## 11. Snapshot Logging Schema

Every read cycle should write a structured snapshot to a rolling file.
Current gap: no historical record of what MCP read at time T.

### File: `data/nova_mcp_snapshots.json`

Rolling ring buffer, max 500 entries (configurable). One entry per symbol per read cycle.

```json
{
  "snapshots": [
    {
      "ts_utc": "2026-06-29T14:32:15Z",
      "ts_ny": "2026-06-29 10:32:15 ET",
      "symbol": "MNQ1!",
      "session": "NY_OPEN",
      "read_confidence": 0.91,
      "parser_mode": "BRIDGE",
      "bridge_version": 2,
      "identity_confirmed": true,
      "bridge": {
        "cmd": "WATCH LONG",
        "sys_state": "ELITE ICT LONG",
        "score": 68,
        "conf_pct": 74,
        "conf_label": "HIGH",
        "pros_engine": "ACTIVE",
        "p_displ": "BULL",
        "p_retrace": "OTE",
        "p_ote": "TAGGED",
        "p_cont": "BUILDING",
        "p_quality": "STRONG",
        "p_stdv": "NORMAL",
        "ib_high": 21487.25,
        "ib_low": 21340.50,
        "ib_status": "COMPLETE",
        "o_state": "ORB_READY",
        "o_bias": "BULL",
        "o_type": null,
        "o_rej_q": null,
        "o_high": 21510.0,
        "o_mid": 21425.5,
        "o_low": 21341.0,
        "orb_active": false,
        "pros_active": true,
        "cooldown": false,
        "trap": false,
        "ict_step": 3,
        "peer_align": "CONFIRM",
        "draw_target": 21560.0,
        "draw_dir": "UP"
      },
      "quote": {
        "last": 21443.0,
        "bid": 21442.5,
        "ask": 21443.5
      },
      "cross_validation": {
        "ib_high_delta": 2.25,
        "ib_low_delta": 1.75,
        "ib_valid": true,
        "session_match": true
      },
      "signal_outcome": "HEADS_UP",
      "alert_fired": false,
      "block_reason": "conviction_below_threshold"
    }
  ]
}
```

### How to Write Snapshots
- At the end of each `read_chart_context()` call, before returning `ChartContext`
- Non-blocking: write in a daemon thread (same pattern as `_push_feed_entry`)
- If file exceeds 500 entries, drop oldest

### How Snapshots Are Used
- Post-trade review: find snapshots from ±30 minutes around a trade
- Debugging: replay exact indicator state at time of an alert
- Setup fingerprinting: extract feature vectors from snapshot `bridge` dict
- Rule discovery: aggregate snapshots by `signal_outcome` and look for common patterns

---

## 12. Replay Engine Concept

The MCP already has full TradingView replay capability. The gap is that NOVA's
intelligence pipeline is not wired to it. Proposed: a `nova_replay_session.py` module.

### What Replay Enables
1. **Historical validation**: Run a past date through the full NOVA reasoning pipeline
   exactly as it would have fired live
2. **Setup review**: Step bar-by-bar through a setup that fired (or missed) and see
   what the indicator said at each bar
3. **Rule testing**: Test a proposed rule change on historical bars before deploying
4. **Similarity confirmation**: Compare a current setup against a replayed historical one

### Replay Session Architecture

```
nova_replay_session.py
  start_replay(date: str, symbol: str)
    → MCP: replay_start(date)
    → loop:
        MCP: replay_step()
        → read_chart_context(symbol)   ← same function as live
        → parse_nova_tables()          ← same function as live
        → _classify_signal()           ← same function as live
        → write snapshot to replay_snapshots.json
        → if signal: record to replay_signals.json
    MCP: replay_stop()
```

### Safety Gates on Replay
- Replay sessions are LOCAL ONLY — they do not trigger Discord alerts
- Replay sessions do not write to `donna_signal_log.json` / `nova_signal_log.json`
- Replay sessions do not trigger execution pipeline (`_apply_market_reality_gate` is bypassed)
- Replay is always read-only from execution's perspective

### Replay Output Format
```json
{
  "replay_date": "2026-06-15",
  "symbol": "MNQ1!",
  "bars_processed": 78,
  "signals_fired": [
    {
      "bar_index": 23,
      "time_ny": "09:47 ET",
      "cmd": "BUY",
      "score": 71,
      "would_have_fired": true,
      "outcome_at_close": null
    }
  ],
  "no_signals": [],
  "summary": "1 EXECUTION_READY, 2 HEADS_UP, 3 blocks"
}
```

---

## 13. Setup Fingerprint Design

A fingerprint is a compact numeric representation of a setup state, enabling
similarity search across all historical setups.

### Feature Vector (per snapshot, at signal moment)

```python
{
  # Categorical (one-hot or ordinal)
  "cmd":          1,   # 1=BUY, -1=SELL, 0=WATCH/WAIT
  "session":      2,   # 0=ASIA, 1=LONDON, 2=NY_OPEN, 3=NY_CASH, 4=LUNCH, 5=POWER
  "p_retrace":    3,   # 0=SHALLOW, 1=MID, 2=OTE, 3=DEEP, 4=TOO_DEEP
  "p_quality":    3,   # 0=WEAK, 1=GOOD, 2=STRONG, 3=ELITE
  "o_state":      1,   # encoded ORB state machine value
  "ict_step":     3,   # 0–6
  "peer_align":   1,   # 1=CONFIRM, 0=NEUTRAL, -1=CONFLICT
  "draw_dir":     1,   # 1=UP, -1=DOWN, 0=NONE

  # Numeric (normalized)
  "score":        0.68,  # score / 100
  "conf_pct":     0.74,
  "score_delta":  0.03,  # score_delta / 10
  "ib_range_norm": 0.45, # ib_range / typical_ib_range (calibrated per symbol)
  "price_vs_ib":  0.62,  # (last - ib_low) / ib_range → 0=at IB low, 1=at IB high

  # Boolean
  "trap":         0,
  "cooldown":     0,
  "ib_complete":  1,
  "orb_active":   0,
  "pros_active":  1
}
```

Total: 20 features. Stored as a list of floats for fast cosine similarity.

### Fingerprint Storage
Each fingerprint is attached to a snapshot entry:
```json
{
  "ts_utc": "...",
  "fingerprint": [1, 2, 3, 0.68, 0.74, 0.03, 0.45, 0.62, 1, 3, 1, 3, 1, 1, 0, 0, 1, 0, 1, 0]
}
```

Fingerprints are only written when `read_confidence >= 0.7` and `cmd != "WAIT"`.

---

## 14. Similarity Matching Approach

Given a current setup fingerprint, find the K most similar historical setups
and retrieve their outcomes.

### Algorithm: Cosine Similarity

```
similarity(A, B) = dot(A, B) / (|A| * |B|)
```

Implemented in pure Python (no external ML dependency).
Operates on the fingerprint vectors from the snapshot log.

### Query Interface
```python
def find_similar_setups(current_fp, n=5, min_confidence=0.70) -> list[dict]:
    """
    Returns the n most similar historical setups above min_confidence threshold.
    Only considers snapshots with a recorded signal_outcome.
    """
```

### Outcome Lookup
For each similar setup, retrieve:
- `signal_outcome` (HEADS_UP / EXECUTION_READY / NO_TRADE)
- Whether a journal entry exists within ±30 minutes
- Journal outcome (WIN / LOSS / B/E) if available
- Date and session

### Base Rate Computation
```python
def get_setup_base_rate(similar_setups: list) -> dict:
    return {
        "n_samples": len(similar_setups),
        "win_rate": wins / total,
        "avg_score": mean(scores),
        "dominant_session": mode(sessions)
    }
```

### Usage in Claude Prompt
When base rate is available (>= 5 similar setups), inject:
> "Historical note: 7 similar setups in the past 30 days. Win rate: 71%. 
> Most common session: NY_OPEN."

This is context only — it does not gate execution. Claude uses it for narration quality.

---

## 15. Post-Trade Self-Review Design

After a trade is closed (WIN, LOSS, B/E), NOVA should retrieve the snapshot(s)
from the time of the trade entry and evaluate:

1. Was the setup fingerprint consistent with historical wins?
2. Was the BRIDGE state at entry consistent with the signal type?
3. Did the score decay before entry (trap risk)?
4. Was draw independence maintained?

### Trigger
Post-trade review is triggered by `_close_symbol_and_sync()` and `close_all_positions_eod()`.
When a journal entry transitions from OPEN → closed, the review is queued.

### Review Process
```
1. Find trade entry timestamp
2. Load snapshots from [entry_ts - 5 min, entry_ts + 5 min]
3. Extract entry snapshot (closest to entry time)
4. Compute fingerprint of entry snapshot
5. Find 5 most similar historical setups
6. Compare entry score vs historical wins/losses
7. Flag anomalies:
   - "Entered below historical win threshold (score < 65 when similar wins avg 72)"
   - "Draw was circular — TP1 was inside displacement leg"
   - "ICT step was 2, not 3+ as in similar wins"
8. Write review to journal entry as 'self_review' field
```

### Review Output (appended to journal entry)
```json
{
  "self_review": {
    "entry_snapshot_found": true,
    "entry_score": 58,
    "similar_setups_n": 7,
    "similar_win_rate": 0.71,
    "entry_score_vs_similar": "below_avg",
    "draw_independence": "circular",
    "flags": [
      "score_below_similar_threshold",
      "draw_circular_tp1_inside_displacement"
    ],
    "reviewed_at": "2026-06-29T15:45:00Z"
  }
}
```

This is observation only. No execution rules are modified automatically.

---

## 16. Rule Discovery Lab Design

The Rule Discovery Lab is an offline analysis tool. It asks: "What distinguishes
winning setups from losing setups in the snapshot history?"

### Not an Autonomous System
The lab does NOT automatically update trading rules. It produces reports for human review.
Rules that survive observation → human decision → Pine Script update → BRIDGE update.

### Analysis Dimensions
For each pair (WIN snapshots, LOSS snapshots), compare:

| Dimension | Method |
|---|---|
| Score distribution | Histogram, mean, median per outcome |
| Session distribution | Chi-square test (is NY_OPEN significantly different from NY_CASH?) |
| ICT step at entry | Mode per outcome |
| Peer alignment | Frequency of CONFIRM vs NEUTRAL vs CONFLICT per outcome |
| Draw direction alignment | % of WIN trades where draw_dir matched trade direction |
| Retrace depth | OTE wins vs DEEP wins — is OTE significantly better? |
| Score delta | Is score_delta > 0 (rising) at entry better than declining? |
| IB position | Is price above IB mid at entry better for LONG? |

### Output Format
```
RULE DISCOVERY REPORT — 2026-06-29
Samples: 43 WIN, 18 LOSS

Finding 1: Score >= 68 → 78% win rate (n=23) vs Score < 68 → 44% (n=38)
  → Proposed threshold: raise CONVICTION_THRESHOLD from 65 to 68

Finding 2: peer_align=CONFLICT in 72% of losses, 12% of wins
  → Proposed rule: block EXECUTION_READY when peer_align=CONFLICT (regardless of score)

Finding 3: No statistically significant difference in ICT_STEP at entry
  → No rule change proposed
```

### Human Gate
Every finding in the report is labeled `proposed_only`. No finding becomes a rule until:
1. Pedro reviews the report
2. Manually updates the Pine Script or Python evaluator
3. The change is deployed and validated for >= 10 trades

---

## 17. Shadow-Mode Testing Design

Shadow mode runs a proposed rule change in parallel with the live system.
Live alerts fire normally. Shadow alerts are computed but held (not delivered).
After N sessions, compare live outcomes vs shadow outcomes.

### Shadow Mode Architecture

```
read_chart_context() → parse_nova_tables()
  ↓                               ↓
_classify_signal()          _classify_signal_shadow(proposed_rules)
  ↓                               ↓
live alert → Discord        shadow alert → nova_shadow_log.json
```

### Shadow Rule Container
A rule change is expressed as a parameter delta:
```json
{
  "rule_id": "shadow_001",
  "description": "Raise conviction threshold to 68",
  "params": {
    "CONVICTION_THRESHOLD": 68
  },
  "live_since": "2026-06-29",
  "expires": "2026-07-13"
}
```

### Shadow Log Schema
```json
{
  "rule_id": "shadow_001",
  "ts_utc": "...",
  "symbol": "MNQ1!",
  "live_outcome": "EXECUTION_READY",
  "shadow_outcome": "HEADS_UP",
  "diverged": true,
  "journal_outcome": "LOSS"
}
```

### Comparison Report
After 20 divergence events:
```
SHADOW REPORT — rule shadow_001 (CONVICTION_THRESHOLD: 65 vs 68)
Divergences: 22 cases
  Live fired, Shadow held: 14 (of which 5 WIN, 9 LOSS)
  Live held, Shadow fired: 0
  Shadow improvement: blocked 9 losses, would have missed 5 wins
  Recommendation: ADOPT (net positive)
```

### Safety Constraints on Shadow Mode
- Shadow mode never writes to the live signal log
- Shadow mode never triggers Discord, Telegram, or execution
- Shadow mode is paused during paper validation phase (too few samples)
- Max 1 active shadow rule at a time

---

## 18. Intelligence Scoring Model

A session-level quality score that measures how well NOVA understood the day.

### Inputs
- Number of EXECUTION_READY alerts
- Alert outcomes (WIN/LOSS/B/E from journal)
- Number of snapshots where `read_confidence < 0.7`
- Number of identity-confirmed reads vs total reads
- Whether morning brief was generated
- Synthesis confidence at session open

### Session Intelligence Score (0–100)

| Component | Max | Scoring |
|---|---|---|
| Alert quality | 40 | (wins - losses) / total_alerts * 40 |
| Read reliability | 25 | avg(read_confidence) * 25 |
| Signal selectivity | 20 | Penalty for >4 EXECUTION_READY in one session |
| Context completeness | 15 | % of reads with complete BRIDGE |

### What It's Used For
- Morning brief each day: "Yesterday intelligence score: 72/100"
- Session memory module: feeds into session quality classification
- Trend over time: is NOVA getting smarter or degrading?

---

## 19. Safety Gates Before Execution

Ordering all gates in the execution path with their source:

```
Gate 1:  Session gate          (state_engine — session must be active)
Gate 2:  Daily loss lock       (state_engine — if daily loss exceeded)
Gate 3:  Red-folder lock       (headlines — macro event pre/post window)
Gate 4:  Macro risk gate       (risk_state — macro_risk must not be critical)
Gate 5:  Market Reality 2.0    (_apply_market_reality_gate — MR2 state alignment)
Gate 6:  read_confidence       (NEW — mcp confidence score >= 0.7 for EXECUTION_READY)
Gate 7:  mcp_health            (NEW — system-level reliability >= 0.7 for EXECUTION_READY)
Gate 8:  Identity confirmed    (NEW — chart symbol must match requested symbol)
Gate 9:  BRIDGE version        (NEW — must be >= current expected version)
Gate 10: Conviction gate       (_apply_conviction_gate — score + conf thresholds)
Gate 11: CMD gate              (cmd must be BUY or SELL, not WATCH/WAIT)
Gate 12: Concurrent position   (Gate 11 existing — per-instrument + global cap)
Gate 13: TRAP flag             (NEW — if BRIDGE TRAP=1, block EXECUTION_READY)
Gate 14: Cross-market conflict (NEW — if PEER_ALIGN=CONFLICT, block EXECUTION_READY)
```

Gates 1–5, 10–12 already exist. Gates 6–9, 13–14 are proposed additions.

Gates 6–9 are **read quality gates** — they don't change the trading rules, they ensure
the intelligence layer is operating reliably before allowing execution decisions.

Gates 13–14 are **signal quality gates** — they encode information already available
in the BRIDGE that is not currently used as hard blocks.

---

## 20. Implementation Phases

### Phase A — BRIDGE Schema Extension (Pine Script only)
**When**: Next Pine Script edit session  
**What**: Add rows 21–33 to NOVA BRIDGE (Priority 1 fields)  
**Scope**: `indicators/nova_execution_v1.pine` only  
**Safety**: BRIDGE_VER=2 in row 21. Python parser reads new fields only if version >= 2.  
**Verification**: Compile → check BRIDGE shows 34 rows → read via MCP → confirm new keys.

### Phase B — Parser Hardening + Version Gate
**When**: After Phase A is deployed and verified for 2+ sessions  
**What**: Update `parse_nova_tables()` with version check, field completeness tracking,
TICKER cross-check, explicit legacy fallback log, parse error taxonomy  
**Scope**: `engines/reasoning.py` only  
**Safety**: Legacy fallback path still exists. New gates are additive.

### Phase C — Chart Identity Lock
**When**: After Phase B is stable  
**What**: Add read-verify-read loop around symbol switch in `read_chart_context()`  
**Scope**: `engines/reasoning.py` only  
**Safety**: Max 1 retry, then skip gracefully (same as current failure handling).

### Phase D — Snapshot Logging
**When**: Phase C is stable  
**What**: Write `nova_mcp_snapshots.json` after every read cycle  
**Scope**: `engines/reasoning.py` (write call) + new `data/nova_mcp_snapshots.json` schema  
**Safety**: Daemon thread write. No impact on live path if write fails.

### Phase E — Read Confidence Score + Execution Gates
**When**: After 100+ snapshots exist (roughly 1–2 weeks of sessions)  
**What**: Compute `read_confidence` per cycle. Add gates 6–9 to execution path.  
**Scope**: `engines/reasoning.py`, `services/execution_bridge.py`  
**Safety**: Gates 6–9 are additive blocks only. They cannot false-positive execute.

### Phase F — Setup Fingerprinting + Similarity Search
**When**: After 200+ snapshots with signal outcomes  
**What**: Compute fingerprints on qualifying snapshots. Add similarity query to Claude prompt.  
**Scope**: New `engines/fingerprint.py`. Called from `engines/reasoning.py`.  
**Safety**: Similarity is context only. No execution gates change.

### Phase G — Post-Trade Self-Review
**When**: Phase F stable, paper validation ongoing  
**What**: Trigger self-review on journal close events  
**Scope**: `services/execution.py` close functions + new `engines/self_review.py`  
**Safety**: Writes to `self_review` field in journal. Never modifies other journal fields.

### Phase H — Rule Discovery Lab (Offline)
**When**: After 300+ snapshots and 30+ closed journal entries with known outcomes  
**What**: `scripts/rule_discovery.py` — read-only analysis script  
**Scope**: New standalone script. No production code changes.  
**Safety**: Read-only. Produces markdown reports only.

### Phase I — Shadow Mode Testing
**When**: Phase H has produced at least one proposed rule change  
**What**: Shadow classification alongside live classification  
**Scope**: `engines/reasoning.py` + new `data/nova_shadow_log.json`  
**Safety**: Never touches live signal log, Discord, or execution.

---

## 21. Files That Would Need Changes

| Phase | File | Change Type |
|---|---|---|
| A | `indicators/nova_execution_v1.pine` | Add 13 rows to NOVA BRIDGE table, update `table.new()` to 40 rows |
| B | `engines/reasoning.py` | `parse_nova_tables()` — version gate, completeness tracking, TICKER check, error taxonomy |
| B | `delivery/signal_log.py` | Add `parser_mode` field to signal log schema |
| C | `engines/reasoning.py` | `read_chart_context()` — read-verify-read loop after symbol switch |
| D | `engines/reasoning.py` | Write snapshot after read. Add `nova_mcp_snapshots.json` path to config. |
| D | `core/config.py` | Add `MCP_SNAPSHOTS_FILE = _data_file('nova_mcp_snapshots.json', 'donna_mcp_snapshots.json')` |
| E | `engines/reasoning.py` | Compute `read_confidence`. Pass to `_classify_signal()`. |
| E | `services/execution_bridge.py` | Check `read_confidence` and `mcp_health` before routing EXECUTION_READY |
| F | New: `engines/fingerprint.py` | Feature vector extraction, cosine similarity, base rate computation |
| F | `engines/reasoning.py` | Call fingerprint module. Inject base rate into Claude prompt. |
| G | New: `engines/self_review.py` | Post-trade review logic |
| G | `services/execution.py` | Trigger self-review on close. Add `self_review` field to journal schema. |
| H | New: `scripts/rule_discovery.py` | Offline analysis script (read-only) |
| I | `engines/reasoning.py` | Dual classification path for shadow mode |
| I | `core/config.py` | `SHADOW_LOG_FILE`, `SHADOW_RULES_FILE` constants |

### Files That Do NOT Change
- `main.py` — no route changes needed
- `delivery/alert_engine.py` — alert delivery contract is unchanged
- `services/execution.py` — execution rules are unchanged (gates added upstream)
- `core/state_engine.py` — state engine contract unchanged
- `monitor.py` — MCP health monitoring unchanged (enhanced by mcp_health score)
- Any file not in the above list

---

## Summary

| Stream | Goal | Risk | Phases |
|---|---|---|---|
| Reliability | Guarantee NOVA reads what it thinks it reads | Low — additive only | A, B, C |
| Confidence Scoring | Quantify how trustworthy each read was | Low — context only until Phase E | D, E |
| Intelligence Loop | Learn from what the indicator said over time | Low — observation only | F, G |
| Offline Analysis | Discover better rules from historical patterns | Zero — read-only | H |
| Experimental | Test proposed rules before deploying | Low — shadow only | I |

**The constraint that governs everything:**  
No phase modifies live execution rules.  
No phase lets NOVA self-modify production logic.  
Every new gate is a block, never a false-positive trigger.  
Human review is required before any finding becomes a rule.
