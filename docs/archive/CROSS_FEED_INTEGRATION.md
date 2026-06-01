# NOVA Cross-Feed Integration
**Status:** Load-bearing | **Version:** 1.0 | **Last updated:** 2026-05-30

Defines how NOVA's intelligence layers connect and influence each other.
This is the core intelligence chain — the connective tissue of the system.

---

## The Intelligence Chain

```
Macro Events + Market Data
        ↓
compute_macro_state()
        ↓
Session Quality Assessment
        ↓
Signal Classification (PROS / ORB / IB / Invalidation)
        ↓
Execution Aggressiveness
        ↓
Alert Aggressiveness
        ↓
Delivery Behavior
```

Each node modifies or gates the nodes below it.
This chain runs deterministically before any Claude call is made.

---

## Node 1: Macro State → Session Quality

**Source:** `compute_macro_state()` in `donna_macro_discord.py`
**Target:** `compute_session_quality_state()` / `evaluate_session_context()`

### Rules

| Macro Condition | Session Quality Impact |
|---|---|
| CRITICAL event same day (CPI, NFP, FOMC) | Cap at C |
| 2+ HIGH events same day | Cap at C |
| 1 HIGH event same day | Cap at B |
| VIX >= 25 | Cap at C |
| VIX 20–25 | Cap at B |
| Red folder week, no HIGH events today | Cap at B |
| Active phase IMMINENT | Force cap at B regardless |
| Clean environment | A |

**Implementation status:** `compute_macro_state()` computes `session_quality` and `sq_reason`. These must become the authoritative source for session quality — replacing the independent computation currently in `evaluate_session_context()`. [TODO Phase 2J]

---

## Node 2: Session Quality → Signal Classification

**Source:** `compute_session_quality_state()`
**Target:** `_classify_signal()` in `donna_nova_reasoning.py`

### Rules

| Session Quality | Signal Classification Impact |
|---|---|
| A | All signal types permitted |
| B | HEADS_UP and EXECUTION_READY permitted; extra scrutiny on grade |
| C | HEADS_UP only; EXECUTION_READY suppressed |
| Standby | No trading signals; only NO_TRADE if condition warrants |
| Session blocked | All trading signals suppressed; NO_TRADE if daily_loss_hit |

**Implementation status:** Partially implemented. `_classify_signal()` checks `session_blocked` but does not yet read `session_quality` from `compute_macro_state()`. [TODO Phase 2J]

---

## Node 3: Signal Classification → Execution Aggressiveness

**Source:** `_classify_signal()` + session quality
**Target:** `_build_evaluation_prompt()` in `donna_nova_reasoning.py`

### Aggressiveness Levels

| Level | Conditions | Effect on Claude Prompt |
|---|---|---|
| NORMAL | Session A, no macro event imminent, VIX < 20 | Standard evaluation |
| REDUCED | Session B, or macro event approaching, or VIX 20–25 | Note reduced confidence; cap grade at B |
| MINIMAL | Session C, or macro event imminent, or VIX 25+ | HEADS_UP only; note degraded conditions |
| OFF | Session blocked | No Claude call; return empty |

**Implementation status:** Not yet implemented. Claude currently receives session info in the prompt but there is no formal aggressiveness level that caps grading. [TODO Phase 2K]

---

## Node 4: Alert Aggressiveness → Delivery Behavior

**Source:** Execution aggressiveness level
**Target:** `deliver_alert()` in `donna_alert_engine.py`

### Rules

| Aggressiveness | Delivery Changes |
|---|---|
| NORMAL | Standard delivery, all channels, normal cooldowns |
| REDUCED | HEADS_UP only for new setups; EXECUTION_READY still permitted for confirmed setups |
| MINIMAL | HEADS_UP only; add degraded-session note to embed |
| OFF | Suppress all trading alerts; only INVALIDATION and macro alerts pass |

**Implementation status:** Not implemented. Delivery is currently aggressiveness-agnostic. [TODO Phase 2K]

---

## Node 5: Macro State → NO_TRADE Alerts

**Source:** `compute_macro_state()` active_phase
**Target:** `run_reasoning_cycle()` + macro alert delivery

### Rules

| Macro Phase | NO_TRADE Behavior |
|---|---|
| IMMINENT (event < 10 min) | Suppress EXECUTION_READY; emit NO_TRADE if setup was forming |
| LIVE | Suppress all trading alerts immediately |
| APPROACHING (10–45 min) | Flag to Claude as risk context; no hard suppression |
| CLEAR | No macro constraint on trading alerts |

**Implementation status:** Macro phase is passed to Claude in the prompt but does not hard-gate the signal classifier. IMMINENT/LIVE should become hard stops. [TODO Phase 2J]

---

## Node 6: VIX → Session Quality → Everywhere

**Source:** `donna_risk_state.json` (VIX from donna_finnhub.py)
**Target:** `compute_macro_state()` → all downstream nodes

### VIX Thresholds

| VIX Level | Classification | Session Quality Impact |
|---|---|---|
| < 20 | Normal | None |
| 20–24.9 | Caution | Session cap B |
| 25–29.9 | Elevated | Session cap C, VIX WARNING alert |
| 30+ | Critical | Session cap Standby, CRITICAL VIX WARNING |

**VOLATILITY_WARNING alert thresholds:**
- HIGH: VIX >= 20
- CRITICAL: VIX >= 30 or VIX spike >= 15% in session

**Cooldown:** 60 minutes between VIX alerts.

---

## Node 7: IB Alignment → Setup Grade

**Source:** `_evaluate_ib_alignment()` in `donna_nova_reasoning.py`
**Target:** Claude evaluation prompt + grade cap

### Rules (from `NOVA_KNOWLEDGE_CORE/PROS_EVAN_INVESTING/initial_balance_draw.md`)

| IB Condition | Grade Impact |
|---|---|
| IB draw confirmed, setup aligned | Grade A candidate |
| IB draw unclear | Grade B cap |
| IB draw confirmed, setup opposes draw (countertrend) | Grade C cap |
| IB range too tight (< 5pts) | Grade B cap, draw unreliable |
| IB window not yet closed (pre-10:30) | Early entry valid if confluence strong |

**Implementation status:** Partially implemented. `_evaluate_ib_alignment()` detects draw and alignment. Claude prompt includes this. Grade cap enforcement is done by Claude — not yet enforced deterministically. [TODO Phase 2J]

---

## Current Integration Status

| Integration | Status |
|---|---|
| Macro state → session quality | Partial (compute_macro_state has sq, but evaluate_session_context is independent) |
| Session quality → signal classification | Partial (blocked check only, no quality grade check) |
| Signal classification → execution aggressiveness | Not implemented |
| Aggressiveness → delivery behavior | Not implemented |
| Macro phase → NO_TRADE hard gate | Not implemented (soft hint to Claude only) |
| VIX → session quality | Implemented in compute_macro_state() |
| IB alignment → grade cap | Partial (Claude enforces, not deterministic) |
| PROS/ORB/IB → pre-assessment → Claude | Implemented |

---

## Phase 2J Build Plan (Cross-Feed Integration)

**Goal:** Wire all nodes deterministically. Claude becomes a grader, not a gatekeeper.

### Step 1 — Unify session quality source
- `compute_macro_state()` becomes the single authority for `session_quality`
- `evaluate_session_context()` reads `session_quality` from macro state (not recomputing)

### Step 2 — Wire session quality into signal classifier
- `_classify_signal()` accepts `session_quality` and applies the grade-cap rules above
- EXECUTION_READY suppressed at session quality C
- All trading signals suppressed at Standby

### Step 3 — Add aggressiveness level to pre-assessment
- `_classify_signal()` returns aggressiveness level alongside signal type
- `_build_evaluation_prompt()` includes explicit aggressiveness instruction for Claude

### Step 4 — Hard gate IMMINENT macro events
- `run_reasoning_cycle()` checks `active_phase` from macro state
- IMMINENT → suppress EXECUTION_READY, return NO_TRADE if setup was active

### Step 5 — IB grade cap deterministic
- `_classify_signal()` applies IB alignment cap to `grade_candidate` before Claude call
- Claude prompt states the pre-assessed grade ceiling explicitly
