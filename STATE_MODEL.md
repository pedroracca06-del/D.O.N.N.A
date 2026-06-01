# NOVA State Model Specification
**Status:** Load-bearing | **Version:** 1.0 | **Last updated:** 2026-05-30

Defines the operational state objects that power the NOVA intelligence layer.
All delivery and UI layers (Discord, future NOVA app) consume these objects.

See also: `ARCHITECTURE_CORE.md` §1 (State-First Architecture)

---

## Pattern: compute_Xstate()

Every NOVA subsystem exposes one function:

```python
def compute_X_state() -> dict:
    """
    Derives operational state from raw data.
    - No API calls
    - No Discord logic
    - No embed logic
    - Fast enough to run every 60 seconds
    Returns structured dict consumable by any delivery layer.
    """
```

**Contract:**
- Input: raw data files + live chart data (if available)
- Output: structured dict with deterministic fields
- Speed: <500ms
- Failure mode: returns safe defaults, never raises
- API calls: zero (deterministic only)

---

## Implemented: compute_macro_state()

**File:** `donna_macro_discord.py`

```python
{
    # Events
    'events_today':    list[dict],   # all today's calendar events
    'high_events':     list[dict],   # HIGH-importance events only
    'next_event':      dict | None,  # next actionable event
    'active_phase':    str,          # APPROACHING | IMMINENT | LIVE | CLEAR
    'minutes_to_next': int | None,

    # Market
    'vix':             float,
    'vix_pct':         float,
    'nq_pct':          float,
    'es_pct':          float,
    'us10y':           float,
    'regime':          str,          # TRENDING_UP | TRENDING_DOWN | VOLATILE | RANGING | MIXED

    # Session assessment
    'session_quality': str,          # A | B | C | Standby
    'sq_reason':       str,          # human-readable reason for grade
    'orb_reliable':    bool,
    'action':          str,          # single operational action line

    # Flags
    'macro_risk':      str,          # low | medium | high
    'red_folder_week': bool,
    'computed_at':     str,          # ISO timestamp
}
```

---

## Specified: compute_session_quality_state()

**File:** `donna_nova_reasoning.py` (to be extracted/formalized)
**Status:** Partially implemented in `evaluate_session_context()`

```python
{
    # Time
    'time_et':          str,
    'day':              str,
    'session':          str,         # NY_OPEN | PRE_MARKET | OFF_HOURS
    'in_window':        bool,        # 09:30–11:00 ET
    'ib_window_closed': bool,        # True after 10:30 ET

    # Trade state
    'daily_trades':     int,         # 0 | 1 | 2
    'daily_loss_hit':   bool,
    'first_trade_won':  bool | None,

    # Session quality (from macro state)
    'quality':          str,         # A | B | C | Standby
    'quality_reason':   str,
    'quality_source':   str,         # 'macro' | 'vix' | 'behavioral' | 'clean'

    # Blocks
    'session_blocked':  bool,
    'block_reason':     str,

    # Operational
    'action':           str,         # single operational line
}
```

---

## Specified: compute_pros_state()

**File:** `donna_nova_reasoning.py`
**Status:** Implemented as `_evaluate_pros_phase()` — needs promotion to public state object

```python
{
    # Phase
    'phase':           str,   # NONE | BUILDING | OTE_APPROACHING | OTE_TAGGED | SETUP_READY | CHOP
    'direction':       str,   # LONG | SHORT | N/A
    'setup_type':      str,   # PROS_LONG | PROS_SHORT | N/A

    # OTE
    'ote_status':      str,   # TAGGED | APPROACHING | ABOVE | BELOW | UNKNOWN
    'fib_level':       float | None,   # 0.618 | 0.705 | 0.786 | None

    # Quality signals
    'cont_quality':    str,   # STRONG | MODERATE | WEAK | UNKNOWN
    'displacement':    str,   # CONFIRMED | WEAK | NONE
    'ib_aligned':      bool | None,
    'ib_draw':         str,   # IB HIGH | IB LOW | UNCLEAR

    # Signal
    'has_signal':      bool,
    'signal_strength': str,   # high | medium | low | none
    'grade_candidate': str,   # A | B | C | D | ?  (pre-Claude estimate)
}
```

---

## Specified: compute_orb_state()

**File:** `donna_nova_reasoning.py`
**Status:** Implemented as `_evaluate_orb_phase()` — needs promotion

```python
{
    # Definition
    'orb_high':     float | None,
    'orb_low':      float | None,
    'orb_mid':      float | None,
    'orb_range':    float | None,
    'orb_wide':     bool,          # True if range > 15pts MES

    # Phase
    'phase':        str,   # UNDEFINED | INSIDE_ORB | BREAKOUT_LONG | BREAKOUT_SHORT | AT_MIDPOINT | ABOVE_ORB | BELOW_ORB
    'direction':    str,   # LONG | SHORT | N/A
    'setup_type':   str,   # ORB_E1_LONG | ORB_E1_SHORT | ORB_E2_LONG | ORB_E2_SHORT | N/A
    'entry_type':   str,   # E1_MIDPOINT | E2_LIQUIDITY | N/A

    # Signal
    'has_signal':   bool,
    'in_context':   bool,   # False after 11:00 ET
    'reliable':     bool,   # False if wide or degraded session
}
```

---

## Specified: compute_invalidation_state()

**File:** To be created in `donna_nova_reasoning.py`
**Status:** Skeleton exists as `_check_invalidation_signals()`

```python
{
    'invalidated':       bool,
    'reason':            str,    # specific invalidation condition
    'setup_type':        str,    # which setup was invalidated
    'direction':         str,    # LONG | SHORT | N/A
    'invalidated_at':    str,    # ISO timestamp
    'recovery_condition': str,   # what would allow a fresh setup
}
```

---

## Specified: compute_execution_state()

**File:** `donna_state_engine.py` (to be extended)

```python
{
    # Position
    'in_position':      bool,
    'position_side':    str,    # LONG | SHORT | FLAT
    'position_symbol':  str,

    # Session limits
    'trades_today':     int,
    'daily_loss_hit':   bool,
    'trade_permission': bool,
    'stop_trading':     bool,

    # Locks
    'macro_lock':        bool,
    'red_folder_lock':   bool,
    'eod_lock':          bool,

    # Behavioral
    'first_trade_won':  bool | None,
    'revenge_risk':     bool,   # loss → immediate re-entry pattern

    # Aggressiveness
    'aggressiveness':   str,   # NORMAL | REDUCED | MINIMAL | OFF
    'aggressiveness_reason': str,
}
```

---

## State Flow

```
Raw Data Layer
  donna_macro_events.json     ← donna_headlines.py (every 15 min)
  donna_risk_state.json       ← donna_finnhub.py (every 5 min)
  donna_state_engine.json     ← donna_state_engine.py (event-driven)
  TradingView MCP             ← live CDP connection (local only)
        ↓
State Computation Layer
  compute_macro_state()
  compute_session_quality_state()
  compute_pros_state()
  compute_orb_state()
  compute_invalidation_state()
  compute_execution_state()
        ↓
Signal Classification
  _classify_signal(pros, orb, ib, inv, session)  → alert_type, setup_type
        ↓
Quality Grading (Claude)
  evaluate_with_claude(nova_state, session_ctx, chart_ctx, pre_assess)
        ↓
AlertData / MacroEvent (delivery-ready objects)
        ↓
Consumers
  Discord (bridge layer)
  NOVA app (Phase 2I)
  API endpoints
  Health check
```

---

## State Object Rules

1. **No delivery logic** in state functions — no embed building, no Discord calls, no formatting
2. **No API calls** in state functions — read from files or MCP only
3. **Always return** — never raise, never return None at the top level (return safe defaults)
4. **Single `action` field** — every state object includes one operational action line
5. **`computed_at` timestamp** — every state object records when it was computed
6. **Typed contracts** — all keys documented here are binding; adding keys is allowed, removing is a breaking change
