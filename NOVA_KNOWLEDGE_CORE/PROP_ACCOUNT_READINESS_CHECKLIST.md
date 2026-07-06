# Prop Account Readiness Checklist

**Purpose:** Verify every safety layer is functioning before live prop account deployment.
Work through this list in order. Do not skip sections.

---

## 1. Execution Request ID Chain

- [ ] Every signal that enters the execution pipeline receives a unique `exec_request_id` (UUID v4)
- [ ] The `chain_id` is propagated from `validate_and_record()` through every gate log and into the execution trace
- [ ] No two execution requests share the same `exec_request_id` — confirm via trace log inspection
- [ ] `nova_execution_trace_v2.json` contains at least 5 entries with distinct `chain_id` values

**Verify:** `GET /api/mcp-replay/shadow` — inspect `chain_id` field on recent snapshots.

---

## 2. Duplicate Protection

- [ ] Duplicate signals (same `exec_request_id` re-submitted) are rejected with `DUPLICATE_DEDUP` reason
- [ ] Dedup registry persists across restarts (`nova_execution_dedup.json` or similar)
- [ ] No two trace entries share the same `exec_request_id` within a trading session
- [ ] Phase 1 tests confirm dedup behavior: `test_duplicate_exec_request_rejected`

**Verify:** Submit the same alert twice; second must return `status: SKIP` with `reason: DUPLICATE`.

---

## 3. Stale Signal Protection

- [ ] Signals older than the configured staleness window are rejected with `STALE_SIGNAL` reason
- [ ] Stale check uses wall-clock time at bridge entry, not signal timestamp
- [ ] Staleness threshold configured and tested (Phase 1 tests cover this)

**Verify:** Send a backdated alert and confirm rejection before any broker call.

---

## 4. Prop Risk Config (`nova_prop_risk_config.json`)

- [ ] File exists in `data/` directory
- [ ] `prop_firm_name` is set to your firm (e.g., `"Apex"`, `"Topstep"`)
- [ ] `account_size` matches your account tier
- [ ] `starting_balance` reflects the balance when evaluation began
- [ ] `max_daily_loss` configured (prop firm daily loss limit in dollars)
- [ ] `max_total_loss` configured (prop firm maximum drawdown in dollars)
- [ ] `trailing_drawdown_enabled: true` if your firm uses trailing drawdown
- [ ] `trailing_drawdown_amount` matches your firm's trailing drawdown rule
- [ ] `trailing_drawdown_type` set correctly (`"trailing"` or `"static"`)

**Verify:** `GET /api/prop-readiness/status` — `prop_config_present` must be `true`.

---

## 5. Max Trades Gate

- [ ] `max_trades_per_day` configured in `nova_prop_risk_config.json` (or `0` to disable)
- [ ] Gate passes when `trade_count < max_trades_per_day`
- [ ] Gate fails with `REJECTED_MAX_TRADES` when limit reached
- [ ] Gate skips (does not block) when `max_trades_per_day=0`

---

## 6. Max Contracts Gate

- [ ] `max_contracts_total` configured (concurrent position cap)
- [ ] `max_contracts_per_symbol` configured (per-instrument cap)
- [ ] Both gates SKIP when set to `0`
- [ ] Both gates FAIL with `REJECTED_MAX_CONTRACTS` when limits exceeded

---

## 7. Daily Loss Gate

- [ ] `max_daily_loss` configured in prop risk config
- [ ] Gate blocks new entries when `daily_pnl < -max_daily_loss`
- [ ] Gate skips when `max_daily_loss=0`
- [ ] `daily_pnl` updates correctly from broker equity reads during the session

**Verify:** Phase 2 tests confirm gate behavior.

---

## 8. Total Loss Gate

- [ ] `max_total_loss` configured
- [ ] `starting_balance` set correctly (must not be `0`)
- [ ] Gate blocks when `(starting_balance - current_balance) >= max_total_loss`
- [ ] Gate skips when any of the three values is `0`

---

## 9. Trailing Drawdown Monitoring

- [ ] `trailing_drawdown_enabled: true` in prop risk config
- [ ] `trailing_drawdown_amount` matches firm rule
- [ ] High-water mark (HWM) updates correctly — never decreases
- [ ] `trailing_drawdown_threshold = high_water_mark - trailing_drawdown_amount`
- [ ] `PROP_TRAILING_DRAWDOWN_WARNING` fires when remaining buffer ≤ 25%
- [ ] `PROP_TRAILING_DRAWDOWN_BREACHED` fires when `current_balance < threshold`
- [ ] `nova_prop_account_state.json` exists and is being updated each safety cycle
- [ ] `broker_account_read: true` in the state file

**Verify:** `GET /api/prop-account/state` — all fields populated with live values.

---

## 10. Open-Position Conflict Detection

- [ ] Gate 11 (concurrent position guard): no new entries if same instrument already open
- [ ] Global cap enforced: `max_concurrent_positions` respected
- [ ] Correlated exposure guard: MES + ES or MNQ + NQ treated as correlated

**Verify:** Phase 4 tests cover concurrent position detection.

---

## 11. Broker/Journal Reconciliation

- [ ] `reconcile_execution_state()` runs on every safety check cycle
- [ ] Each broker position cross-referenced against open journal trades
- [ ] `JOURNAL_POSITION_MISMATCH` detected when broker holds a position not in journal
- [ ] Reconciliation results visible in `GET /api/execution-safety/status`

**Verify:** Safety status endpoint shows `reconciliations` list — no mismatches in last 3 cycles.

---

## 12. Protective Order Confirmation

- [ ] After each execution, `protective_stop_found` is verified
- [ ] `UNPROTECTED_POSITION` alert fires when a stop is missing
- [ ] No position has been open for more than one session without a stop order

**Verify:** Safety status shows `unprotected_positions: []` for the last 3 cycles.

---

## 13. Unprotected Position Alerting

- [ ] Safety monitor sends `CRITICAL: UNPROTECTED POSITION DETECTED` Discord embed
- [ ] Alert fires within one safety cycle (60–180s) of stop order absence
- [ ] Cooldown prevents alert repeat spam (default 900s = 15 min)
- [ ] `NOVA_EXECUTION_SAFETY_DISCORD_ENABLED=true` required for Discord delivery

---

## 14. Discord Alert Controls

- [ ] `NOVA_EXECUTION_SAFETY_DISCORD_ENABLED` is set correctly (default `false`)
- [ ] `NOVA_EXECUTION_SAFETY_ALERT_COOLDOWN_SECONDS` configured (default 900)
- [ ] `DISCORD_BOT_TOKEN` is valid and bot has permission in target channel
- [ ] `DISCORD_CHANNEL_SYSTEM_HEALTH` or `DISCORD_CHANNEL_LIVE` is set
- [ ] Test: trigger a WARNING condition and confirm Discord embed is received

---

## 15. Dry-Run Mode

- [ ] `NOVA_EXECUTION_DRY_RUN=true` in `.env`
- [ ] `validate_and_record()` runs all gates and logs result
- [ ] No broker API call is made in dry-run mode
- [ ] Response status is `DRY_RUN_VALIDATED` not `EXECUTED`
- [ ] `nova_execution_trace_v2.json` shows `dry_run: true` entries
- [ ] 5+ sessions completed with no gate errors, no duplicate IDs, no stale signals

---

## 16. Paper Mode

- [ ] `NOVA_AUTO_EXECUTE=false` (paper / off)
- [ ] OR: Alpaca paper credentials in use (not live API keys)
- [ ] No live fills appear in Alpaca account — confirm via broker portal
- [ ] `execution_mode` in response is `paper` or `off`, not `live`

---

## 17. Manual Emergency Process

In the event of any detected breach or system failure:

1. **Stop the session launcher** — close TradingView monitor and task scheduler jobs
2. **Disable NOVA_AUTO_EXECUTE** — set to `false` in `.env` and restart server
3. **Check Alpaca positions** — log into Alpaca portal and verify positions manually
4. **Manually close any unprotected positions** — do not rely on NOVA to flatten
5. **Review `nova_execution_trace_v2.json`** — audit the last 10 entries for unexpected orders
6. **Review `nova_execution_safety_log.json`** — check what the monitor last saw
7. **Document the incident** — note what triggered the failure and what was expected

**NOVA does not auto-flatten.** No position will be closed automatically by the system.
The trader is responsible for manual intervention at all times.

---

## 18. Known Limitations

| Limitation | Status | Workaround |
|---|---|---|
| No auto-flatten | By design | Manual close via broker portal |
| No auto-stop submission | By design | Manual stop placement required |
| Prop gates observe-only by default | `NOVA_PROP_GATES_ENABLED=false` | Enable only after dry-run validation |
| Trailing drawdown check is state-file based | Updates on safety cycle (60–180s lag) | Monitor portal directly for real-time |
| Discord alerts require bot token | Config required | Set `DISCORD_BOT_TOKEN` and channel ID |
| Journal write lock deferred | No process-wide lock | Avoid concurrent journal writers |

---

## 19. Required Environment Variables

| Variable | Required for | Default |
|---|---|---|
| `NOVA_AUTO_EXECUTE` | Live execution | `false` |
| `NOVA_EXECUTION_DRY_RUN` | Dry-run validation | `false` |
| `NOVA_PROP_GATES_ENABLED` | Prop enforcement | `false` |
| `NOVA_EXECUTION_SAFETY_MONITOR_ENABLED` | Safety monitor loop | `true` |
| `NOVA_EXECUTION_SAFETY_DISCORD_ENABLED` | Discord alert delivery | `false` |
| `NOVA_EXECUTION_SAFETY_ALERT_COOLDOWN_SECONDS` | Repeat-alert cooldown | `900` |
| `ANTHROPIC_API_KEY` | Claude grading + journal | required |
| `DISCORD_BOT_TOKEN` | Alert delivery | required for alerts |
| `DISCORD_CHANNEL_LIVE` | Fallback alert channel | required |
| `DISCORD_CHANNEL_SYSTEM_HEALTH` | System health alerts | optional (falls back to LIVE) |
| `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` | Broker (paper or live) | required |
| `FINNHUB_API_KEY` | Market data | required |

---

## 20. Go / No-Go Criteria

### Not Ready (blockers — must resolve before any prop deployment):

- `NOVA_AUTO_EXECUTE=true` AND `NOVA_EXECUTION_DRY_RUN=false` — live execution without dry-run protection
- `nova_prop_risk_config.json` missing or `prop_firm_name=NONE` — no risk config
- `max_daily_loss=0` or `max_total_loss=0` — limits not configured
- `trailing_drawdown_enabled=false` when your firm uses trailing drawdown
- `broker_account_read=false` in prop account state — balance not tracking
- Open unprotected positions detected by safety monitor

### Ready for Dry-Run (proceed to 5-session trial):

- `NOVA_EXECUTION_DRY_RUN=true`
- `nova_prop_risk_config.json` present with all limits configured
- `NOVA_PROP_GATES_ENABLED=false` (observe-only during trial)
- Safety monitor running and status file updated in last 5 minutes
- No unprotected positions
- No duplicate IDs in last session trace

### Ready for Live Prop Deployment (all of the above PLUS):

- 5+ dry-run sessions with `DRY_RUN_VALIDATED` results and zero gate errors
- HWM values in `nova_prop_account_state.json` verified accurate against broker portal
- `trailing_drawdown_amount` confirmed correct for your account tier
- `max_daily_loss` and `max_total_loss` confirmed match your firm's rules
- Zero unprotected-position alerts across all 5 sessions
- Zero journal/broker mismatches across all 5 sessions
- Zero duplicate execution requests across all 5 sessions
- Zero stale signal executions
- User explicitly sets `NOVA_PROP_GATES_ENABLED=true` and reviews the enforcement gate log
