# EXECUTION BOT V2 — PHASE 2 IMPLEMENTATION NOTE

**Date:** 2026-06-30  
**Status:** COMPLETE — 31/31 tests passing  
**Constraint:** Gates run and log in live mode but do NOT block unless `NOVA_PROP_GATES_ENABLED=true`.  
No broker changes. No strategy changes. No live prop trading enabled.

---

## What Was Built

Phase 2 adds prop-firm risk gate evaluation to the execution request backbone.
Every execution attempt now evaluates 7 configurable risk gates before broker logic runs.
Gates always execute for observability; enforcement is controlled by env vars.

### New Files

**`services/prop_risk.py`**  
Prop-firm risk config I/O and gate evaluation engine. Public API:

- `get_default_config() -> dict` — safe zero-config; all gates disabled
- `load_prop_config() -> dict` — load from file, fall back to defaults
- `save_prop_config(config)` — write to file (strips internal `_` fields)
- `run_prop_gates(symbol, session, trade_count, daily_pnl, open_positions, config) -> list` — pure evaluation; never reads external state
- `get_runtime_context() -> dict` — read trade_count / daily_pnl / open_positions from state_engine

**`data/nova_prop_risk_config.json`** (auto-created on first load)  
Prop-firm risk config. Edit this file to configure a prop account.
Default: all zeros / empty lists — all gates skip.

**`tests/test_execution_bot_v2_phase2.py`**  
31 tests — all passing.

### Modified Files

**`services/execution_request.py`**

New Phase 2 status constants:
```python
STATUS_REJECTED_PROP_DAILY_LOSS  = 'REJECTED_PROP_DAILY_LOSS'
STATUS_REJECTED_PROP_MAX_LOSS    = 'REJECTED_PROP_MAX_LOSS'
STATUS_REJECTED_MAX_TRADES       = 'REJECTED_MAX_TRADES'
STATUS_REJECTED_MAX_CONTRACTS    = 'REJECTED_MAX_CONTRACTS'
STATUS_REJECTED_SYMBOL           = 'REJECTED_SYMBOL_NOT_ALLOWED'
STATUS_REJECTED_SESSION          = 'REJECTED_SESSION'
```

New public function:
```python
def prop_gates_enforced(dry_run: bool) -> bool:
    """True if dry_run=True OR NOVA_PROP_GATES_ENABLED=true."""
```

New `session: str = ''` parameter in `validate_and_record()`.

Phase 2 gate evaluation is wired inside `_validate_and_record_impl()`:
1. `load_prop_config()` — load config (defaults if file missing)
2. `get_runtime_context()` — read state_engine for trade_count, daily_pnl, open_positions
3. `run_prop_gates(...)` — evaluate all 7 gates; always runs for observability
4. If a gate fails AND `prop_gates_enforced(dry_run)` is True → rejection status returned

New fields in every `validate_and_record()` return dict:
```python
'session':            str | None       # session passed to bridge
'prop_config_loaded': bool             # whether config file was present
'prop_firm_name':     str | None       # from config
'prop_account_size':  float | None     # from config
'prop_gate_results':  list[dict]       # one entry per gate evaluated
'rejected_gate':      str | None       # gate name that failed (if any)
```

**`services/execution_bridge.py`**  
`session` is now passed to `validate_and_record()`:
```python
_phase1_req = validate_and_record(
    ...
    session = session,
    ...
)
```
Log line updated: `PHASE1+2` prefix.

---

## Gate Summary

| Gate | Config Key | Skip Condition | Rejection Code |
|---|---|---|---|
| Allowed Symbols | `allowed_symbols` | `[]` (empty) | `REJECTED_SYMBOL_NOT_ALLOWED` |
| Allowed Sessions | `allowed_sessions` | `[]` (empty) | `REJECTED_SESSION` |
| Max Trades Per Day | `max_trades_per_day` | `0` | `REJECTED_MAX_TRADES` |
| Max Contracts Total | `max_contracts_total` | `0` | `REJECTED_MAX_CONTRACTS` |
| Max Contracts Per Symbol | `max_contracts_per_symbol` | `0` | `REJECTED_MAX_CONTRACTS` |
| Daily Loss Limit | `max_daily_loss` | `0.0` | `REJECTED_PROP_DAILY_LOSS` |
| Max Total Loss | `max_total_loss` + `starting_balance` + `current_balance` | any is `0` | `REJECTED_PROP_MAX_LOSS` |

All gates evaluate even when earlier gates fail (full observability).

---

## Symbol → ETF Routing

Gates that count open positions use the same ETF routing as the broker:

| Futures Symbol | Routed ETF |
|---|---|
| MNQ / NQ | QQQ |
| MES / ES | SPY |

`max_contracts_per_symbol=1` with `MNQ` signal counts open QQQ positions.

---

## Gate Enforcement Logic

```
dry_run=True    → enforce (gates block; final_status = rejection code)
dry_run=False   + NOVA_PROP_GATES_ENABLED=true  → enforce
dry_run=False   + NOVA_PROP_GATES_ENABLED=false → observe only (RECEIVED returned)
```

**Default live behavior:** `NOVA_PROP_GATES_ENABLED=false`.  
Gates always run and log `prop_gate_results` for audit. Broker path continues unchanged.

---

## prop_risk_config Schema

```json
{
  "prop_firm_name":            "NONE",
  "account_size":              0.0,
  "starting_balance":          0.0,
  "current_balance":           0.0,
  "max_daily_loss":            0.0,
  "max_total_loss":            0.0,
  "trailing_drawdown_enabled": false,
  "trailing_drawdown_amount":  0.0,
  "trailing_drawdown_type":    "FIXED_FROM_START",
  "trailing_hwm":              0.0,
  "max_contracts_total":       0,
  "max_contracts_per_symbol":  0,
  "max_trades_per_day":        0,
  "allowed_symbols":           [],
  "allowed_sessions":          [],
  "flatten_before_close":      true,
  "news_trading_allowed":      false,
  "consistency_rule_enabled":  false,
  "daily_profit_cap_if_any":   null
}
```

Fields with `0` / `[]` / `false` values produce `SKIP` results — they do not block.

---

## How to Configure for a Prop Account

1. Edit `data/nova_prop_risk_config.json` with account-specific limits
2. Set `NOVA_EXECUTION_DRY_RUN=true` and run monitor to validate gate behavior
3. Inspect `data/nova_execution_trace_v2.json` → verify `prop_gate_results` fields
4. When dry-run results are clean, set `NOVA_PROP_GATES_ENABLED=true` for live enforcement

Example Apex 50K config:
```json
{
  "prop_firm_name":            "APEX",
  "account_size":              50000.0,
  "starting_balance":          50000.0,
  "current_balance":           50000.0,
  "max_daily_loss":            2500.0,
  "max_total_loss":            3000.0,
  "max_contracts_total":       5,
  "max_contracts_per_symbol":  2,
  "max_trades_per_day":        10,
  "allowed_symbols":           ["MNQ", "MES"],
  "allowed_sessions":          ["NY_OPEN", "NY_AM", "NY_PM"]
}
```

---

## Environment Variables

| Variable | Default | Effect |
|---|---|---|
| `NOVA_EXECUTION_DRY_RUN` | `false` | `true` = Phase 1+2 result is final; broker never called |
| `NOVA_PROP_GATES_ENABLED` | `false` | `true` = prop gates enforce in live mode |
| `NOVA_MAX_SIGNAL_AGE_SECONDS` | `120` | Max signal age before `REJECTED_STALE` |

---

## What Is NOT Yet Active

| Feature | Status |
|---|---|
| `decision_id` populated from reasoning snapshot | NOT wired (Phase 1 known gap) |
| Trailing drawdown tracking (HWM) | NOT built — Phase 3 |
| `current_balance` auto-updated from Alpaca | NOT wired — must be set manually in config |
| Protective order confirmation | NOT built — Phase 3 |
| Broker↔state reconciliation | NOT built — Phase 4 |

---

## Phase 3 Scope (after Phase 2)

1. Trailing drawdown tracking — HWM + `trailing_drawdown_amount` gate
2. `UNPROTECTED_POSITION` detection after broker fill
3. Protective order confirmation status (`PROTECTIVE_ORDERS_PLACED`)

## Phase 4 Scope (after Phase 3)

1. Periodic broker↔state-engine reconciliation
2. Journal↔Alpaca open position reconciliation
3. `RECONCILED` status in trace_v2
