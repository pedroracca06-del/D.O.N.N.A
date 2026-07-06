"""prop_readiness.py — Execution Bot v2 Phase 7: Prop readiness validation.

Evaluates whether the system is ready for dry-run trial before any live prop
account deployment. Checks env vars, config files, safety monitor status,
account state, and execution infrastructure completeness.

Output file: nova_prop_readiness_report.json (DATA_DIR)

SAFETY CONTRACT — this module MUST NEVER:
  - Submit orders
  - Cancel orders
  - Modify positions
  - Call any Alpaca write endpoint

The only external calls are:
  - load_prop_config()           (reads nova_prop_risk_config.json)
  - load_prop_account_state()    (reads nova_prop_account_state.json)
  - get_latest_safety_status()   (reads nova_execution_safety_status.json)
  - execution trace file read    (reads nova_execution_trace_v2.json)

All of the above are read-only.

Public API:
    collect_prop_readiness_status() -> dict    — read all current state (no side effects)
    evaluate_prop_readiness(data)   -> dict    — pure evaluation → blockers/warnings/status
    write_prop_readiness_report()   -> dict    — collect + evaluate + write output file
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

READINESS_READY     = 'READY_FOR_DRY_RUN'
READINESS_NOT_READY = 'NOT_READY'

STALE_SAFETY_SECONDS  = 1800   # 30 min — safety status considered stale
STALE_ACCOUNT_SECONDS = 7200   # 2 hr   — account state considered stale


# ── File path ──────────────────────────────────────────────────────────────────

def _readiness_report_file() -> Path:
    try:
        from core.config import DATA_DIR
        return DATA_DIR / 'nova_prop_readiness_report.json'
    except Exception:
        return Path('data') / 'nova_prop_readiness_report.json'


# ── Env-var snapshot ───────────────────────────────────────────────────────────

def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, 'true' if default else 'false').strip().lower() == 'true'


def _read_env_snapshot() -> dict:
    return {
        'NOVA_AUTO_EXECUTE':                          _env_bool('NOVA_AUTO_EXECUTE'),
        'NOVA_EXECUTION_DRY_RUN':                     _env_bool('NOVA_EXECUTION_DRY_RUN'),
        'NOVA_PROP_GATES_ENABLED':                    _env_bool('NOVA_PROP_GATES_ENABLED'),
        'NOVA_EXECUTION_SAFETY_MONITOR_ENABLED':      _env_bool('NOVA_EXECUTION_SAFETY_MONITOR_ENABLED', default=True),
        'NOVA_EXECUTION_SAFETY_DISCORD_ENABLED':      _env_bool('NOVA_EXECUTION_SAFETY_DISCORD_ENABLED'),
        'NOVA_EXECUTION_SAFETY_ALERT_COOLDOWN_SECONDS': int(
            os.getenv('NOVA_EXECUTION_SAFETY_ALERT_COOLDOWN_SECONDS', '900')
        ),
    }


# ── Execution trace summary ────────────────────────────────────────────────────

def _load_execution_trace_summary() -> dict:
    try:
        from core.config import DATA_DIR
        p = DATA_DIR / 'nova_execution_trace_v2.json'
    except Exception:
        p = Path('data') / 'nova_execution_trace_v2.json'

    if not p.exists():
        return {'trace_file_exists': False, 'entry_count': 0, 'latest_entry': None}

    try:
        data    = json.loads(p.read_text(encoding='utf-8'))
        entries = data if isinstance(data, list) else []
        latest  = entries[-1] if entries else None
        return {
            'trace_file_exists': True,
            'entry_count':       len(entries),
            'latest_entry':      latest,
            'latest_chain_id':   latest.get('chain_id')   if latest else None,
            'latest_status':     latest.get('status')     if latest else None,
            'latest_at':         latest.get('created_at') if latest else None,
        }
    except Exception as e:
        return {'trace_file_exists': True, 'entry_count': 0, 'error': str(e)}


# ── Collection ─────────────────────────────────────────────────────────────────

def collect_prop_readiness_status() -> dict:
    """
    Read all current state needed for readiness evaluation.
    Pure collection — no evaluation, no side effects beyond file reads.
    Returns a data snapshot dict.
    """
    env = _read_env_snapshot()

    # Prop risk config
    prop_config: dict        = {}
    prop_config_missing: bool = True
    try:
        from services.prop_risk import load_prop_config
        prop_config         = load_prop_config()
        prop_config_missing = bool(prop_config.get('_config_missing', True))
    except Exception as e:
        prop_config         = {'_load_error': str(e)}
        prop_config_missing = True

    # Prop account state
    prop_account_state: dict = {}
    try:
        from services.prop_account_state import load_prop_account_state
        prop_account_state = load_prop_account_state()
    except Exception as e:
        prop_account_state = {'_load_error': str(e)}

    # Safety status
    safety_status: dict = {}
    try:
        from services.execution_safety import get_latest_safety_status
        safety_status = get_latest_safety_status()
    except Exception as e:
        safety_status = {'_load_error': str(e)}

    # Execution trace
    trace_summary = _load_execution_trace_summary()

    return {
        'collected_at':        datetime.now(timezone.utc).isoformat(),
        'env':                 env,
        'prop_config':         prop_config,
        'prop_config_missing': prop_config_missing,
        'prop_account_state':  prop_account_state,
        'safety_status':       safety_status,
        'trace_summary':       trace_summary,
    }


# ── Staleness helper ───────────────────────────────────────────────────────────

def _seconds_since(iso_str: str | None) -> float | None:
    if not iso_str:
        return None
    try:
        ts = datetime.fromisoformat(str(iso_str).replace('Z', '+00:00'))
        return (datetime.now(timezone.utc) - ts).total_seconds()
    except Exception:
        return None


# ── Evaluation ────────────────────────────────────────────────────────────────

def evaluate_prop_readiness(data: dict) -> dict:
    """
    Pure evaluation of a prop readiness data snapshot.

    Returns:
      {
        'readiness_status':        READY_FOR_DRY_RUN | NOT_READY,
        'blockers':                [str, ...],
        'warnings':                [str, ...],
        'recommended_next_action': str,
      }

    No I/O. Never raises.
    """
    blockers: list[str] = []
    warnings: list[str] = []

    env              = data.get('env') or {}
    prop_config      = data.get('prop_config') or {}
    prop_config_miss = bool(data.get('prop_config_missing', True))
    prop_account     = data.get('prop_account_state') or {}
    safety           = data.get('safety_status') or {}
    trace            = data.get('trace_summary') or {}

    auto_execute = bool(env.get('NOVA_AUTO_EXECUTE'))
    dry_run      = bool(env.get('NOVA_EXECUTION_DRY_RUN'))
    prop_gates   = bool(env.get('NOVA_PROP_GATES_ENABLED'))
    discord_on   = bool(env.get('NOVA_EXECUTION_SAFETY_DISCORD_ENABLED'))
    monitor_on   = bool(env.get('NOVA_EXECUTION_SAFETY_MONITOR_ENABLED', True))

    # ── Blockers (must fix before dry-run) ────────────────────────────────────

    # Live execution with no dry-run safety net
    if auto_execute and not dry_run:
        blockers.append(
            'NOVA_AUTO_EXECUTE=true with NOVA_EXECUTION_DRY_RUN=false: '
            'system is in LIVE execution mode. '
            'Set NOVA_EXECUTION_DRY_RUN=true before dry-run validation.'
        )

    # Prop risk config must be present and named
    if prop_config_miss:
        blockers.append(
            'Prop risk config missing or unconfigured: '
            'nova_prop_risk_config.json does not exist or has default zero values. '
            'Configure prop_firm_name, account_size, max_daily_loss, max_total_loss, '
            'trailing_drawdown_amount before dry-run.'
        )
    elif str(prop_config.get('prop_firm_name', 'NONE')).upper() in ('NONE', '', 'UNKNOWN'):
        blockers.append(
            'Prop risk config has no prop_firm_name set. '
            'Edit nova_prop_risk_config.json and set prop_firm_name '
            '(e.g. "Apex", "Topstep").'
        )

    # ── Warnings (note-worthy but do not block READY status) ─────────────────

    # Execution mode notes
    if not auto_execute and not dry_run:
        warnings.append(
            'NOVA_AUTO_EXECUTE=false and NOVA_EXECUTION_DRY_RUN=false: '
            'no signals will flow through the execution pipeline. '
            'Set NOVA_EXECUTION_DRY_RUN=true to begin dry-run validation.'
        )

    # Prop gates enforcing before validation complete
    if prop_gates:
        warnings.append(
            'NOVA_PROP_GATES_ENABLED=true: prop gates are currently enforcing. '
            'Keep false (observe-only) during dry-run validation. '
            'Enable only after 5+ clean dry-run sessions.'
        )

    # Safety monitor paused
    if not monitor_on:
        warnings.append(
            'NOVA_EXECUTION_SAFETY_MONITOR_ENABLED=false: '
            'safety monitor is paused. Enable before dry-run trial.'
        )

    # Safety status staleness
    safety_at  = safety.get('checked_at')
    safety_age = _seconds_since(safety_at)
    if safety_at is None or safety_age is None:
        warnings.append(
            'Safety monitor has never run or status file is missing. '
            'Run at least one safety check before dry-run trial.'
        )
    elif safety_age > STALE_SAFETY_SECONDS:
        minutes = int(safety_age // 60)
        warnings.append(
            f'Safety status is stale ({minutes}m old). '
            'Safety monitor may not be running. Expected: every 60–180s during market hours.'
        )

    # Prop account state never updated or stale
    acct_updated = prop_account.get('last_updated') or ''
    acct_age     = _seconds_since(acct_updated)
    if not acct_updated or acct_age is None:
        warnings.append(
            'Prop account state has never been updated from broker. '
            'Run at least one safety check cycle to initialize account state.'
        )
    elif acct_age > STALE_ACCOUNT_SECONDS:
        hours = int(acct_age // 3600)
        warnings.append(
            f'Prop account state is stale ({hours}h old). '
            'State may not be tracking live balance.'
        )

    # Discord disabled — expected during dry-run but worth calling out
    if not discord_on:
        warnings.append(
            'NOVA_EXECUTION_SAFETY_DISCORD_ENABLED=false: '
            'Discord alerts suppressed. '
            'Enable when you want real-time prop account breach notifications.'
        )

    # Broker never read
    if not prop_account.get('broker_account_read') and not prop_config_miss:
        warnings.append(
            'Prop account state broker_account_read=false: '
            'balance, HWM, and drawdown values are zero defaults. '
            'A safety check cycle will populate live values.'
        )

    # No execution trace entries yet
    if not trace.get('trace_file_exists') or trace.get('entry_count', 0) == 0:
        warnings.append(
            'Execution trace is empty: no signals have flowed through the pipeline. '
            'Dry-run trial will populate the trace.'
        )

    # ── Overall status ────────────────────────────────────────────────────────
    readiness_status = READINESS_NOT_READY if blockers else READINESS_READY

    # ── Recommended next action ───────────────────────────────────────────────
    if blockers:
        first = blockers[0]
        if 'NOVA_AUTO_EXECUTE=true' in first:
            action = (
                'Set NOVA_EXECUTION_DRY_RUN=true in your .env file and restart. '
                'Do NOT set NOVA_AUTO_EXECUTE=true without dry-run protection.'
            )
        elif 'Prop risk config' in first or 'prop_firm_name' in first:
            action = (
                'Configure nova_prop_risk_config.json: '
                'set prop_firm_name, account_size, max_daily_loss, max_total_loss, '
                'trailing_drawdown_amount. Then re-run this check.'
            )
        else:
            action = 'Resolve all blockers listed above before starting dry-run validation.'
    elif not dry_run:
        action = (
            'Set NOVA_EXECUTION_DRY_RUN=true in your .env, restart the server, '
            'then run 5 live market sessions to validate the pipeline end-to-end.'
        )
    else:
        action = (
            'System is ready for dry-run validation. '
            'Run 5 live market sessions with NOVA_EXECUTION_DRY_RUN=true. '
            'After each session: review nova_execution_trace_v2.json for duplicates, '
            'stale signals, gate decisions, and any broker mismatches.'
        )

    return {
        'readiness_status':        readiness_status,
        'blockers':                blockers,
        'warnings':                warnings,
        'recommended_next_action': action,
    }


# ── Report writer ──────────────────────────────────────────────────────────────

def write_prop_readiness_report() -> dict:
    """
    Collect current state, evaluate readiness, write nova_prop_readiness_report.json.
    Returns the full report dict. Never raises.

    SAFETY: read-only. No broker writes. No order actions.
    """
    checked_at = datetime.now(timezone.utc).isoformat()
    try:
        data       = collect_prop_readiness_status()
        evaluation = evaluate_prop_readiness(data)

        env          = data.get('env') or {}
        prop_config  = data.get('prop_config') or {}
        prop_account = data.get('prop_account_state') or {}
        safety       = data.get('safety_status') or {}
        trace        = data.get('trace_summary') or {}

        report = {
            'checked_at':            checked_at,
            'readiness_status':      evaluation['readiness_status'],
            'blockers':              evaluation['blockers'],
            'warnings':              evaluation['warnings'],
            'recommended_next_action': evaluation['recommended_next_action'],

            # Config
            'prop_firm':             prop_config.get('prop_firm_name', 'not configured'),
            'prop_config_present':   not data.get('prop_config_missing', True),

            # Account state summary
            'account_state_summary': {
                'prop_state_status':           prop_account.get('prop_state_status'),
                'current_balance':             prop_account.get('current_balance'),
                'high_water_mark':             prop_account.get('high_water_mark'),
                'daily_pnl':                   prop_account.get('daily_pnl'),
                'trailing_drawdown_remaining': prop_account.get('trailing_drawdown_remaining'),
                'daily_loss_remaining':        prop_account.get('daily_loss_remaining'),
                'broker_account_read':         prop_account.get('broker_account_read', False),
                'last_updated':                prop_account.get('last_updated'),
            },

            # Latest safety status
            'latest_safety_status': {
                'status':               safety.get('status'),
                'checked_at':           safety.get('checked_at'),
                'open_positions_count': safety.get('open_positions_count', 0),
                'unprotected_count':    len(safety.get('unprotected_positions', [])),
                'discord_enabled':      bool(safety.get('discord_enabled', False)),
            },

            # Execution trace
            'execution_trace_summary': trace,

            # Env var snapshot
            'discord_configured':      bool(env.get('NOVA_EXECUTION_SAFETY_DISCORD_ENABLED')),
            'dry_run_enabled':         bool(env.get('NOVA_EXECUTION_DRY_RUN')),
            'auto_execute_enabled':    bool(env.get('NOVA_AUTO_EXECUTE')),
            'prop_gates_enforcing':    bool(env.get('NOVA_PROP_GATES_ENABLED')),
            'safety_monitor_enabled':  bool(env.get('NOVA_EXECUTION_SAFETY_MONITOR_ENABLED', True)),
        }

        _readiness_report_file().write_text(json.dumps(report, indent=2), encoding='utf-8')
        return report

    except Exception as e:
        fallback = {
            'checked_at':            checked_at,
            'readiness_status':      READINESS_NOT_READY,
            'blockers':              [f'Readiness check failed: {e}'],
            'warnings':              [],
            'recommended_next_action': 'Fix the error above and retry.',
            'error':                 str(e),
        }
        try:
            _readiness_report_file().write_text(json.dumps(fallback, indent=2), encoding='utf-8')
        except Exception:
            pass
        return fallback
