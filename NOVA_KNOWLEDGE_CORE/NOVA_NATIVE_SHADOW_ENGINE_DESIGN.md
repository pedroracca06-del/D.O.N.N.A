# NOVA-Native Shadow Engine — Design Document

**Status:** Phase 1 complete (audit). Phase 2 (build) pending approval.
**Scope:** Observability only. No execution impact. No strategy changes.
**Goal:** "TradingView bridge says X. Python-native shadow says Y. They match / partially match / mismatch."

---

## 1. What the Audit Found

### 1.1 Current data flow

```
TradingView / Pine Script
    │
    ├─ Computes IB levels (request.security 1m bars, 9:30–10:29 ET)
    ├─ Computes ORB levels (8:00–8:15 ET candle accumulation)
    ├─ Computes ORB state machine (ATR + wick + body + sequence counters)
    ├─ Computes ORB pass gates (MID_REJECT / LIQ_REJECT / EDGE_REJECT)
    ├─ Computes PROS displacement (SMA body/range thresholds + close conditions)
    ├─ Computes PROS fib zones (50% / 61.8% / 70.5% / 78.6%)
    ├─ Computes PROS rejection + continuation phases
    └─ Publishes summary state strings to NOVA BRIDGE table
           │
           ▼
    parse_nova_tables()  →  orb_table + pros_state + bridge_v2 dicts
           │
           ▼
    _evaluate_pros_phase()   — keyword mapping from pros_state string values
    _evaluate_orb_phase()    — keyword mapping from orb_table + ORB levels extracted from labels
    _evaluate_ib_alignment() — float parsing from pros_state + yfinance 1m cross-validation
```

Python currently has **no independent computation** of ORB or PROS logic. It reads Pine's output strings and maps them to internal enums. The only exception is `_compute_ib_from_yfinance()`, which independently derives IB H/L from yfinance 1m NQ=F bars — this is the template for the shadow engine.

### 1.2 What Python evaluators actually do

**`_evaluate_pros_phase(main_state, pros_state, chart_ctx)`**
- Input: `pros_state['PROS ENGINE']` string (CONTINUATION/BUILDING/ACTIVE/WAIT)
- Input: `pros_state['OTE']` string (TAGGED/MID ONLY/DEEP/SHALLOW/—)
- Input: `pros_state['RETRACE']` string (OTE/DEEP/MID/ABOVE/—)
- Input: `pros_state['CONT']` string (CONFIRMED/BUILDING/WAIT/—)
- Input: `main_state['CMD']` string (BUY/SELL/WAIT)
- Output: `{phase, direction, setup_type, ote_status, cont_quality, has_signal, signal_strength}`
- **No raw candle data used.** Pure string-to-enum translation.

**`_evaluate_orb_phase(main_state, chart_ctx, session_ctx, orb_table)`**
- Input: ORB HIGH/LOW levels from MCP chart labels (already float-extracted)
- Input: `orb_table['TYPE']` string (MID_REJECT/LIQ_REJECT/EDGE_REJECT/context labels)
- Input: `orb_table['BIAS']` string (BULL/BEAR/BULL DEAD/BEAR DEAD/NEUTRAL)
- Input: `orb_table['REJ Q']` string (WEAK/GOOD/STRONG/ELITE)
- Output: `{phase, direction, setup_type, has_signal, entry_type, entry_quality, orb_high, orb_low, orb_mid, orb_range, orb_wide, in_context}`
- **No raw candle data used.** Passes through Pine's pre-computed values.

**`_evaluate_ib_alignment(main_state, chart_ctx, pros_state)`**
- Primary: float-parse `pros_state['IB H']` / `pros_state['IB L']`
- Fallback: MCP label extraction for older Pine builds
- Cross-validation: yfinance 1m NQ=F bars → independent IB H/L computation
- Output: `{draw, draw_source, ib_high, ib_low, ib_range, aligned, ib_tight, ib_source}`
- **This is the only function with Python-native computation.** The yfinance path already IS a shadow engine for IB.

### 1.3 Pine-side logic depth (shadow replication complexity)

| Component | Logic depth | Shadow complexity |
|---|---|---|
| IB High/Low | 1m bar accumulation (9:30–10:29 ET) | **LOW** — yfinance already does this |
| ORB High/Low | 1m bar accumulation (8:00–8:15 ET) | **LOW** — yfinance ES=F straightforward |
| ORB state machine | ATR + sequence counters across all live bars | **MEDIUM** — needs bar replay, state vars |
| ORB MID_REJECT gate | Body/wick ratios + prior breakout + 2-bar sequence | **HIGH** — needs rolling metrics, counters |
| ORB LIQ_REJECT gate | Sweep tier + reclaim counter + mid acceptance | **HIGH** — sweep tier logic not in yfinance |
| ORB EDGE_REJECT gate | Edge counter + wick ratio | **HIGH** — same dependencies |
| PROS displacement | SMA(body,20) + SMA(range,20) + close conditions | **MEDIUM** — needs 20+ bars of history |
| PROS fib zones | Arithmetic from leg endpoints | **LOW** — pure math once leg is found |
| PROS rejection | Sticky zone-touch flag + close reclaim | **MEDIUM** — stateful across bars |
| PROS continuation | Reference anchor + break within 20 bars | **MEDIUM** — stateful, reference tracking |

---

## 2. Available Raw Data (Python-side)

### 2.1 From MCP OHLCV call (per chart read cycle)
```python
ohlcv = chart_ctx.get('ohlcv', {})
# Contains:
#   range_30    — 30-bar total range
#   change_pct  — % change
#   avg_volume  — average volume
#   high_30     — 30-bar high
#   low_30      — 30-bar low
#   last_5      — list of 5 most recent bar dicts [{open, high, low, close, volume}, ...]
```
**Limitation:** Only 5 raw bars available per cycle. Not enough for SMA-20 body/range or sequence-counter logic.

### 2.2 From yfinance (on demand)
```python
import yfinance as yf
hist = yf.Ticker('NQ=F').history(period='1d', interval='1m', prepost=True)
# Full 1-minute OHLCV for today's session — typically 400–500 bars
# Also available: ES=F for ORB (ES chart only)
```
**This is the primary raw data source for the shadow engine.** Already used for IB cross-validation.

### 2.3 Data gaps
- **Sweep tier logic** (orbSweepTierBull/Bear): requires external key level database (PDH/PDL/ONH/ONL/weekly levels) aligned bar-by-bar. Not trivially available from yfinance. → ORB LIQ_REJECT shadow will be approximate.
- **Stacked liquidity** (orbStackedBull/Bear): requires same key level database.
- **Trap detection** (orbBullTrap/orbBearTrap): depends on Pine's trap engine — not shadowed in Phase 1.
- **Pine's exact `canSmartBuy/canSmartSell` gates**: depends on full score system — out of scope.

---

## 3. Shadow Engine Scope — Phase 2

### What will be built

**Three shadow functions in `engines/native_shadow.py`:**

```
compute_native_ib(candles_1m, session_ctx) -> dict
    Input:  1m NQ=F (or ES=F) bars, today's date
    Output: {ib_high, ib_low, ib_range, ib_forming, source}
    Logic:  bars where open_time ∈ [9:30, 10:30) ET → max(high) / min(low)
    Status: TRIVIAL — already implemented in _compute_ib_from_yfinance()

compute_native_orb(candles_1m_es, session_ctx) -> dict
    Input:  1m ES=F bars, today's date
    Output: {orb_high, orb_low, orb_mid, orb_state, source}
    Logic:  bars where open_time ∈ [8:00, 8:15) ET → max(high) / min(low)
            orb_state: EXPIRED (hourNow >= 11) / ACTIVE / FORMING / INACTIVE
    Status: MEDIUM — ORB levels easy; gate type replication limited

compute_native_pros(candles_1m, session_ctx) -> dict
    Input:  1m NQ=F bars, today's date (min 50 bars needed)
    Output: {phase, direction, leg_high, leg_low, fib_618, fib_786, ote_zone, source}
    Logic:  scan bars for displacement → anchor leg → compute fib → detect rejection → detect continuation
    Status: MEDIUM — stateful replay of 4-phase sequence

compare_shadow_to_bridge(native, bridge_state) -> dict
    Input:  native shadow output + parsed bridge values
    Output: {ib_match, orb_level_match, pros_phase_match, overall_match, notes}
```

### Match status vocabulary
```
MATCH         — shadow and bridge agree within tolerance
PARTIAL_MATCH — direction/type agrees but level or quality differs
MISMATCH      — shadow and bridge disagree on key classification
NO_DATA       — insufficient bars for shadow to compute
BRIDGE_ONLY   — bridge has value but shadow has no analog (sweep tier, trap)
```

### What will NOT be built in Phase 1
- Full ORB gate replication (MID_REJECT / LIQ_REJECT / EDGE_REJECT with all sub-conditions)
- Sweep tier logic (no key level database)
- Trap detection
- canSmartBuy/canSmartSell — score system gate

---

## 4. Comparison Contract

The `compare_shadow_to_bridge()` function produces a fixed-shape dict injected into decision snapshots as `native_shadow`. Shape:

```python
{
    # IB comparison
    'shadow_ib_high':    float | None,
    'shadow_ib_low':     float | None,
    'bridge_ib_high':    float | None,
    'bridge_ib_low':     float | None,
    'ib_high_delta':     float | None,   # abs diff in points
    'ib_low_delta':      float | None,
    'ib_match':          str,            # MATCH / PARTIAL_MATCH / MISMATCH / NO_DATA

    # ORB comparison
    'shadow_orb_high':   float | None,
    'shadow_orb_low':    float | None,
    'shadow_orb_mid':    float | None,
    'shadow_orb_state':  str | None,     # EXPIRED / ACTIVE / FORMING / INACTIVE
    'bridge_orb_high':   float | None,
    'bridge_orb_low':    float | None,
    'bridge_orb_state':  str | None,
    'orb_level_match':   str,            # MATCH / PARTIAL_MATCH / MISMATCH / NO_DATA
    'orb_state_match':   str,

    # PROS comparison
    'shadow_pros_phase': str | None,     # SETUP_READY / OTE_TAGGED / BUILDING / NONE / NO_DATA
    'shadow_pros_dir':   str | None,     # LONG / SHORT / N/A
    'bridge_pros_phase': str | None,     # from _evaluate_pros_phase() output
    'bridge_pros_dir':   str | None,
    'pros_phase_match':  str,            # MATCH / PARTIAL_MATCH / MISMATCH / NO_DATA

    # Overall
    'overall_match':     str,            # ALL_MATCH / PARTIAL / DIVERGED / INSUFFICIENT
    'shadow_source':     str,            # 'yfinance_1m' or 'no_data'
    'shadow_ts':         str,            # ISO timestamp of shadow computation
    'notes':             list[str],      # human-readable discrepancy notes
}
```

**Tolerance for level matching:**
- IB levels: ≤ 5 NQ points = MATCH, 5–75 = PARTIAL_MATCH, > 75 = MISMATCH (same threshold as IB guard)
- ORB levels: ≤ 3 ES points = MATCH, 3–20 = PARTIAL_MATCH, > 20 = MISMATCH

---

## 5. Integration Points

### Snapshot injection
In `_evaluate_single_chart()` (reasoning.py), after the existing evaluators run, call:
```python
from engines.native_shadow import compute_shadow_report
snap['native_shadow'] = compute_shadow_report(chart_ctx, session_ctx, bridge_state)
```
This is the ONLY change to reasoning.py. No evaluator logic is modified. No gates are added.

### New endpoint
`GET /api/mcp-replay/shadow?limit=50`
Returns the `native_shadow` field from the last N decision snapshots, alongside `decision_id` and `timestamp`. Read-only. No mutations.

### No new alert types. No execution path changes. No governance changes.

---

## 6. PROS Replication Strategy

### The 4-phase replay loop

```
for each 1m bar (chronological):
    1. Compute body, range, avgBody(SMA-20), avgRange(SMA-20)
    2. Detect displacement: body > 1.2×avg AND range > 1.1×avg AND close > highest(high,3) [bull]
    3. If displacement fires: anchor leg (prosLegLow = lowest(low,10), prosLegHigh = current high)
    4. Track leg freshness (≤ 50 bars), invalidate if close < legLow
    5. Compute fib levels from leg endpoints
    6. Track zone touch (close in 50–78.6% or wick ≤ 61.8%)
    7. Detect rejection: zone touched AND close > 50% (bull)
    8. If rejection: anchor reference (high of rejection bar)
    9. Track reference freshness (≤ 20 bars)
   10. Detect continuation: close > refHigh (bull) within 20 bars
   11. Determine phase: SETUP_READY / OTE_TAGGED / BUILDING / NONE
```

### Depth mapping (retrace depth 1–5)
```
1: above 50% (ABOVE)
2: between 50%–61.8% (MID)
3: between 61.8%–70.5% (OTE)    → prosOteText = "TAGGED"
4: between 70.5%–78.6% (DEEP)   → prosOteText = "DEEP"
5: below 78.6% (TOO DEEP)       → invalidated leg
```

### Phase mapping from shadow state
```
prosContinuationBull fires   → shadow_phase = 'SETUP_READY'
prosConFreshBull AND OTE     → shadow_phase = 'OTE_TAGGED'
prosConFreshBull AND DEEP    → shadow_phase = 'OTE_APPROACHING'
prosLegValidBull (no ref)    → shadow_phase = 'BUILDING'
no valid leg                 → shadow_phase = 'NONE'
```

---

## 7. ORB Replication Strategy

### Level computation
```python
# ES=F 1m bars
ib_window_bars = [b for b in bars if 8*60 <= bar_minute(b) < 8*60+15]
orb_high = max(b['high'] for b in ib_window_bars)
orb_low  = min(b['low']  for b in ib_window_bars)
orb_mid  = (orb_high + orb_low) / 2
```

### State (time-based approximation)
```python
now_et = datetime.now(ZoneInfo('America/New_York'))
mins   = now_et.hour * 60 + now_et.minute
if mins < 8*60:         state = 'INACTIVE'
elif mins < 8*60+15:    state = 'FORMING'
elif mins < 11*60:      state = 'ACTIVE'    # simplified — no thesis-death tracking
else:                   state = 'EXPIRED'
```

### Gate type: approximate only
Full MID_REJECT / LIQ_REJECT / EDGE_REJECT replication is deferred. In Phase 1, the shadow reports `orb_level_match` (levels agree?) and `orb_state_match` (expired/active/forming agree?). Gate-type matching is flagged as `BRIDGE_ONLY` when bridge has a TYPE and shadow cannot verify it.

---

## 8. IB Replication Strategy

Already implemented in `_compute_ib_from_yfinance()`. The shadow engine wraps this call:
```python
shadow_ib = _compute_ib_from_yfinance()  # returns {ib_high, ib_low, forming}
```
Compare against bridge values:
```python
bridge_ib_h = float(pros_state.get('IB H', '') or 'nan')
bridge_ib_l = float(pros_state.get('IB L', '') or 'nan')
delta_h = abs(shadow_ib['ib_high'] - bridge_ib_h)
ib_match = 'MATCH' if delta_h <= 5 else 'PARTIAL_MATCH' if delta_h <= 75 else 'MISMATCH'
```

---

## 9. Test Plan

Tests live in `tests/test_native_shadow.py`:

| Test | What it covers |
|---|---|
| IB computation from synthetic 1m bars | ORB window logic, edge cases |
| PROS displacement detection | Body/range thresholds, SMA window |
| PROS fib zone calculation | Arithmetic correctness |
| PROS rejection detection | Sticky zone-touch flag |
| PROS continuation detection | Reference anchor + break |
| ORB level computation | 8:00–8:15 window |
| compare_shadow_to_bridge — IB match | Delta within tolerance |
| compare_shadow_to_bridge — IB mismatch | Delta beyond threshold |
| compare_shadow_to_bridge — NO_DATA | Missing bars |
| compare_shadow_to_bridge — output keys | No forbidden keys |
| Insufficient data safety | < 20 bars → NO_DATA, no crash |
| No execution keys in output | 'is_execution_ready' absent |

---

## 10. File Plan

```
engines/native_shadow.py          — NEW: shadow computation functions
tests/test_native_shadow.py       — NEW: shadow engine tests
main.py                           — MODIFY: add GET /api/mcp-replay/shadow endpoint
engines/reasoning.py              — MODIFY: inject native_shadow into decision snapshots
                                    (single call, no logic changes)
```

Total new code: ~300 lines (shadow engine) + ~150 lines (tests).

---

## 11. Hard Constraints (reiterated)

- Shadow output is **never read by any execution gate**
- Shadow output is **never read by any alert generator**
- Shadow output is **never used to modify or block a signal**
- The `_evaluate_pros_phase()` / `_evaluate_orb_phase()` / `_evaluate_ib_alignment()` functions are **not modified**
- TradingView/Pine remains the **sole authoritative source** for execution decisions
- Shadow mismatch logs are **observability only** — no automatic action taken
