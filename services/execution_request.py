"""execution_request.py — Execution Bot v2 Phase 1+2: request backbone + prop gates.

Every execution attempt generates an execution_request_id, is deduplicated
against a persistent registry, checked for signal freshness, run through
prop-firm risk gates, and recorded in a v2 trace file.

This module is a PARALLEL validation layer. It does not replace or call
the existing execution path. In live mode (DRY_RUN=false) with
NOVA_PROP_GATES_ENABLED=false (default) it logs and returns, then the caller
continues to the existing gates. In dry-run mode (DRY_RUN=true) or with
NOVA_PROP_GATES_ENABLED=true its result is final and no broker call is made.

Public API:
    validate_and_record(**kwargs) -> dict   — call once per execution attempt
    is_dry_run() -> bool                    — read env var at call time
    prop_gates_enforced(dry_run) -> bool    — whether prop gates block execution
    get_registry_stats() -> dict            — summary for /api endpoints
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Constants ──────────────────────────────────────────────────────────────────

MAX_SIGNAL_AGE_SECONDS = int(os.getenv('NOVA_MAX_SIGNAL_AGE_SECONDS', '120'))
REGISTRY_MAX = 5000   # oldest records are dropped when limit is exceeded
TRACE_V2_MAX = 5000

# Phase 1 status codes
STATUS_RECEIVED          = 'RECEIVED'
STATUS_BAD_PAYLOAD       = 'REJECTED_BAD_PAYLOAD'
STATUS_DUPLICATE         = 'REJECTED_DUPLICATE'
STATUS_STALE             = 'REJECTED_STALE'
STATUS_DRY_RUN_VALIDATED = 'DRY_RUN_VALIDATED'
STATUS_FAILED            = 'FAILED'

# Phase 2 prop gate rejection codes
STATUS_REJECTED_PROP_DAILY_LOSS  = 'REJECTED_PROP_DAILY_LOSS'
STATUS_REJECTED_PROP_MAX_LOSS    = 'REJECTED_PROP_MAX_LOSS'
STATUS_REJECTED_MAX_TRADES       = 'REJECTED_MAX_TRADES'
STATUS_REJECTED_MAX_CONTRACTS    = 'REJECTED_MAX_CONTRACTS'
STATUS_REJECTED_SYMBOL           = 'REJECTED_SYMBOL_NOT_ALLOWED'
STATUS_REJECTED_SESSION          = 'REJECTED_SESSION'

# Phase 3 open-position conflict + reconciliation codes
STATUS_REJECTED_OPEN_POSITION    = 'REJECTED_OPEN_POSITION'
# Reconciliation statuses (go in reconciliation_status field, not final_status,
# except REJECTED_OPEN_POSITION which can become final_status when enforced)
STATUS_RECON_SYNCED              = 'SYNCED'
STATUS_RECON_RECONCILED          = 'RECONCILED'
STATUS_RECON_BROKER_MISSING      = 'BROKER_POSITION_MISSING'
STATUS_RECON_JOURNAL_MISSING     = 'JOURNAL_MISSING'
STATUS_RECON_SIZE_MISMATCH       = 'SIZE_MISMATCH'
STATUS_RECON_DIRECTION_MISMATCH  = 'DIRECTION_MISMATCH'
STATUS_RECON_UNPROTECTED         = 'UNPROTECTED_POSITION'
STATUS_RECON_UNKNOWN             = 'UNKNOWN_BROKER_STATE'
STATUS_RECON_INSUFFICIENT        = 'INSUFFICIENT_DATA'

_lock = threading.Lock()

# ── File paths (resolved lazily so DATA_DIR env is respected) ─────────────────

def _registry_file() -> Path:
    try:
        from core.config import DATA_DIR
        return DATA_DIR / 'nova_execution_registry.json'
    except Exception:
        return Path('data') / 'nova_execution_registry.json'


def _trace_v2_file() -> Path:
    try:
        from core.config import DATA_DIR
        return DATA_DIR / 'nova_execution_trace_v2.json'
    except Exception:
        return Path('data') / 'nova_execution_trace_v2.json'


# ── Dry-run mode ──────────────────────────────────────────────────────────────

def is_dry_run() -> bool:
    """Read env var at call time so changes take effect without restart."""
    return os.getenv('NOVA_EXECUTION_DRY_RUN', 'false').strip().lower() == 'true'


def prop_gates_enforced(dry_run: bool) -> bool:
    """
    Prop gates block execution when:
    - dry_run=True (always enforce in dry-run), OR
    - NOVA_PROP_GATES_ENABLED=true (explicit live enforcement)
    Default: gates run and log but do NOT block the live path.
    """
    if dry_run:
        return True
    return os.getenv('NOVA_PROP_GATES_ENABLED', 'false').strip().lower() == 'true'


# ── ID generation ─────────────────────────────────────────────────────────────

def build_execution_request_id(
    symbol: str,
    direction: str,
    setup_type: str,
    decision_id: str = '',
    signal_id: str = '',
    signal_generated_at: str = '',
) -> str:
    """
    Deterministic EXREQ_YYYYMMDD_HHMMSS_HASH8 from available signal fields.

    Same signal fields always produce the same ID within the same second,
    making it idempotent for rapid duplicate calls and predictable in tests.
    """
    now = datetime.now(timezone.utc)
    ts  = now.strftime('%Y%m%d_%H%M%S')
    raw = '|'.join([
        (decision_id or '').strip(),
        (signal_id or '').strip(),
        symbol.upper().strip(),
        direction.upper().strip(),
        setup_type.upper().strip(),
        (signal_generated_at or '').strip(),
    ])
    h = hashlib.sha256(raw.encode()).hexdigest()[:8].upper()
    return f'EXREQ_{ts}_{h}'


# ── Registry I/O ──────────────────────────────────────────────────────────────

def _load_registry() -> dict:
    try:
        p = _registry_file()
        if p.exists():
            data = json.loads(p.read_text(encoding='utf-8'))
            if isinstance(data, dict) and 'records' in data:
                return data
    except Exception:
        pass
    return {'version': '1', 'records': []}


def _save_registry(reg: dict) -> None:
    records = reg.get('records', [])
    if len(records) > REGISTRY_MAX:
        reg['records'] = records[-REGISTRY_MAX:]
    _registry_file().write_text(json.dumps(reg, indent=2), encoding='utf-8')


# ── Trace v2 I/O ──────────────────────────────────────────────────────────────

def _load_trace_v2() -> list:
    try:
        p = _trace_v2_file()
        if p.exists():
            data = json.loads(p.read_text(encoding='utf-8'))
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []


def _save_trace_v2(entries: list) -> None:
    if len(entries) > TRACE_V2_MAX:
        entries = entries[-TRACE_V2_MAX:]
    _trace_v2_file().write_text(json.dumps(entries, indent=2), encoding='utf-8')


# ── Dedup check ───────────────────────────────────────────────────────────────

def _check_duplicate(
    execution_request_id: str,
    decision_id: str,
    signal_id: str,
    registry: dict,
) -> dict:
    """
    Check registry for any matching record by any of the three ID fields.
    Returns a result dict; is_duplicate=True means at least one match found.
    """
    for rec in registry.get('records', []):
        if rec.get('execution_request_id') == execution_request_id:
            return {
                'checked': True, 'is_duplicate': True,
                'matched_on': 'execution_request_id',
                'matched_id': execution_request_id,
            }
        if decision_id and rec.get('decision_id') == decision_id:
            return {
                'checked': True, 'is_duplicate': True,
                'matched_on': 'decision_id',
                'matched_id': decision_id,
            }
        if signal_id and rec.get('signal_id') == signal_id:
            return {
                'checked': True, 'is_duplicate': True,
                'matched_on': 'signal_id',
                'matched_id': signal_id,
            }
    return {'checked': True, 'is_duplicate': False, 'matched_on': None, 'matched_id': None}


# ── Stale signal check ────────────────────────────────────────────────────────

def _check_stale(
    signal_generated_at: str,
    max_age_seconds: int = MAX_SIGNAL_AGE_SECONDS,
) -> dict:
    """
    Validate signal age against max_age_seconds.

    If signal_generated_at is absent: marks missing_timestamp=True.
    Caller decides whether to block (Phase 1: warn + allow in dry-run only).
    """
    if not signal_generated_at:
        return {
            'checked': True,
            'is_stale': False,
            'missing_timestamp': True,
            'signal_age_seconds': None,
            'max_age_seconds': max_age_seconds,
        }
    try:
        generated = datetime.fromisoformat(signal_generated_at.replace('Z', '+00:00'))
        now       = datetime.now(timezone.utc)
        age       = (now - generated).total_seconds()
        return {
            'checked': True,
            'is_stale': age > max_age_seconds,
            'missing_timestamp': False,
            'signal_age_seconds': round(age, 3),
            'max_age_seconds': max_age_seconds,
        }
    except Exception as e:
        return {
            'checked': True,
            'is_stale': False,
            'missing_timestamp': True,
            'signal_age_seconds': None,
            'max_age_seconds': max_age_seconds,
            'parse_error': str(e),
        }


# ── Core validation ───────────────────────────────────────────────────────────

def validate_and_record(
    *,
    symbol: str,
    direction: str,
    setup_type: str,
    signal_type: str = '',
    grade: str = '',
    session: str = '',
    entry: Optional[float] = None,
    stop: Optional[float] = None,
    target: Optional[float] = None,
    qty: Optional[int] = None,
    source: str = 'BRIDGE',
    decision_id: str = '',
    signal_id: str = '',
    signal_generated_at: str = '',
    dry_run_override: Optional[bool] = None,
) -> dict:
    """
    Phase 1+2 entry point. Call once per execution attempt before any broker logic.

    Returns a record dict with 'final_status':
      DRY_RUN_VALIDATED          — all checks passed, dry-run mode active
      RECEIVED                   — all checks passed, live mode (caller continues to broker)
      REJECTED_BAD_PAYLOAD
      REJECTED_DUPLICATE
      REJECTED_STALE
      REJECTED_PROP_DAILY_LOSS   — prop daily loss limit hit (Phase 2)
      REJECTED_PROP_MAX_LOSS     — prop total loss limit hit (Phase 2)
      REJECTED_MAX_TRADES        — max_trades_per_day reached (Phase 2)
      REJECTED_MAX_CONTRACTS     — position cap reached (Phase 2)
      REJECTED_SYMBOL_NOT_ALLOWED
      REJECTED_SESSION
      REJECTED_OPEN_POSITION     — existing broker position for same instrument (Phase 3)
      FAILED                     — unexpected error in this module

    Phase 2+3 gate enforcement:
      - dry_run=True OR NOVA_PROP_GATES_ENABLED=true → gates block execution
      - Otherwise: gates run and log but do NOT block (default for live)
    """
    dry_run    = dry_run_override if dry_run_override is not None else is_dry_run()
    created_at = _utc_now()

    try:
        return _validate_and_record_impl(
            symbol=symbol,
            direction=direction,
            setup_type=setup_type,
            signal_type=signal_type,
            grade=grade,
            session=session,
            entry=entry,
            stop=stop,
            target=target,
            qty=qty,
            source=source,
            decision_id=decision_id,
            signal_id=signal_id,
            signal_generated_at=signal_generated_at,
            dry_run=dry_run,
            created_at=created_at,
        )
    except Exception as e:
        failed = {
            'execution_request_id': f'EXREQ_ERR_{uuid.uuid4().hex[:8].upper()}',
            'decision_id': decision_id or None,
            'signal_id': signal_id or None,
            'symbol': symbol, 'direction': direction, 'setup_type': setup_type,
            'signal_type': signal_type, 'grade': grade,
            'session': session,
            'entry': entry, 'stop': stop, 'target': target, 'qty': qty,
            'source': source, 'created_at': created_at,
            'signal_generated_at': signal_generated_at or None,
            'signal_age_seconds': None,
            'status': STATUS_FAILED, 'dry_run': dry_run,
            'validation_errors': [f'Phase 1+2+3+4 internal error: {e}'],
            'validation_warnings': [],
            'duplicate_check': {'checked': False},
            'stale_check': {'checked': False},
            'prop_config_loaded': False,
            'prop_firm_name': None,
            'prop_account_size': None,
            'prop_gate_results': [],
            'rejected_gate': None,
            # Phase 3 fields
            'open_position_check':        {'checked': False, 'conflict': False},
            'broker_positions_count':     0,
            'broker_orders_count':        0,
            'journal_open_trades_count':  0,
            'reconciliation_status':      None,
            'protective_stop_found':      None,
            'protective_target_found':    None,
            'unprotected_position_warning': False,
            'reconciliation_warnings':    [],
            'reconciliation_errors':      [],
            # Phase 4 fields
            'protective_confirmation_status': None,
            'entry_order_found':    None,
            'entry_filled':         None,
            'position_found':       None,
            'stop_order_found':     None,
            'target_order_found':   None,
            'bracket_or_oco_detected': None,
            'emergency_alert':      None,
            'emergency_alert_type': None,
            'emergency_alert_severity': None,
            'broker_called': False,
            'final_status': STATUS_FAILED,
        }
        _append_trace_v2(failed)
        return failed


def _validate_and_record_impl(
    *, symbol, direction, setup_type, signal_type, grade, session,
    entry, stop, target, qty, source,
    decision_id, signal_id, signal_generated_at,
    dry_run, created_at,
) -> dict:
    validation_errors:   list[str] = []
    validation_warnings: list[str] = []

    # ── Required field validation
    if not str(symbol).strip():
        validation_errors.append('symbol is required')
    if str(direction).upper().strip() not in ('LONG', 'SHORT', 'BUY', 'SELL'):
        validation_errors.append(f'direction must be LONG/SHORT/BUY/SELL, got: {direction!r}')
    if not str(setup_type).strip():
        validation_errors.append('setup_type is required')

    if validation_errors:
        req = _build_req(
            execution_request_id=f'EXREQ_BAD_{uuid.uuid4().hex[:8].upper()}',
            symbol=symbol, direction=direction, setup_type=setup_type,
            signal_type=signal_type, grade=grade, session=session,
            entry=entry, stop=stop, target=target, qty=qty,
            source=source, decision_id=decision_id, signal_id=signal_id,
            signal_generated_at=signal_generated_at,
            created_at=created_at, dry_run=dry_run,
            validation_errors=validation_errors,
            validation_warnings=validation_warnings,
            duplicate_check={'checked': False},
            stale_check={'checked': False},
            prop_config_loaded=False, prop_firm_name=None, prop_account_size=None,
            prop_gate_results=[], rejected_gate=None,
            final_status=STATUS_BAD_PAYLOAD,
            # Phase 3+4 — skipped on bad payload
            open_position_check={'checked': False, 'conflict': False},
            protective_confirmation_status=None,
            entry_order_found=None, entry_filled=None, p4_position_found=None,
            stop_order_found=None, target_order_found=None,
            bracket_or_oco_detected=None,
            emergency_alert=None, emergency_alert_type=None, emergency_alert_severity=None,
        )
        _append_trace_v2(req)
        return req

    # ── Build execution_request_id
    execution_request_id = build_execution_request_id(
        symbol=symbol,
        direction=direction,
        setup_type=setup_type,
        decision_id=decision_id,
        signal_id=signal_id,
        signal_generated_at=signal_generated_at,
    )

    # ── decision_id missing warning
    if not decision_id:
        validation_warnings.append('decision_id missing — reasoning→bridge chain not yet wired')

    # ── Stale signal check
    stale_check = _check_stale(signal_generated_at)
    if stale_check.get('missing_timestamp'):
        validation_warnings.append(
            'MISSING_SIGNAL_TIMESTAMP — signal age cannot be validated; '
            'live execution is allowed but dry-run is recommended'
        )

    # ── Dedup + registry write (single lock acquisition for atomicity)
    with _lock:
        registry  = _load_registry()
        dup_check = _check_duplicate(execution_request_id, decision_id, signal_id, registry)

        # Write to registry NOW if this is not a duplicate or stale rejection
        # (we write before determining final_status so the registry reflects all
        # attempts, not just successful ones — except bad-payload and true dupes)
        should_register = (
            not dup_check['is_duplicate']
            and not (stale_check.get('is_stale') and not stale_check.get('missing_timestamp'))
        )
        if should_register:
            _append_registry_locked(
                registry=registry,
                execution_request_id=execution_request_id,
                decision_id=decision_id,
                signal_id=signal_id,
                symbol=symbol,
                direction=direction,
                setup_type=setup_type,
                created_at=created_at,
                status=STATUS_RECEIVED,
            )

    # ── Phase 2: Prop risk gate evaluation (always runs for observability)
    prop_config_loaded  = False
    prop_firm_name      = None
    prop_account_size   = None
    prop_gate_results:  list = []
    rejected_gate:      Optional[str] = None
    prop_rejection_code: Optional[str] = None

    try:
        from services.prop_risk import (
            load_prop_config, run_prop_gates, get_runtime_context,
        )
        prop_config       = load_prop_config()
        prop_config_loaded = not prop_config.get('_config_missing', True)
        prop_firm_name    = prop_config.get('prop_firm_name') or None
        prop_account_size = prop_config.get('account_size') or None
        runtime           = get_runtime_context()
        prop_gate_results = run_prop_gates(
            symbol         = symbol,
            session        = session,
            trade_count    = runtime.get('trade_count', 0),
            daily_pnl      = runtime.get('daily_pnl', 0.0),
            open_positions = runtime.get('open_positions', []),
            config         = prop_config,
        )
        failed_gate = next(
            (g for g in prop_gate_results if g.get('result') == 'FAIL'), None
        )
        if failed_gate:
            rejected_gate       = failed_gate['gate']
            prop_rejection_code = failed_gate['rejection_code']
    except Exception as _pe:
        validation_warnings.append(f'prop_risk gate error (non-blocking): {_pe}')

    # ── Phase 3: Open position conflict + broker/journal reconciliation ────────
    p3_open_check:           dict           = {'checked': False, 'conflict': False}
    p3_broker_pos_count:     int            = 0
    p3_broker_ord_count:     int            = 0
    p3_journal_count:        int            = 0
    p3_recon_status:         Optional[str]  = None
    p3_stop_found:           Optional[bool] = None
    p3_target_found:         Optional[bool] = None
    p3_unprotected_warn:     bool           = False
    p3_recon_warnings:       list           = []
    p3_recon_errors:         list           = []
    p3_open_rejection_code:  Optional[str]  = None

    # Shared broker state — populated by Phase 3, consumed by Phase 4
    _shared_broker_positions: list = []
    _shared_broker_orders:    list = []

    try:
        from services.execution_reconcile import (
            get_broker_positions_safe,
            get_broker_orders_safe,
            get_open_journal_trades_safe,
            check_open_position_conflict,
            detect_protective_orders,
            reconcile_execution_state,
            _symbol_to_etf as _recon_etf,
        )
        routed_etf       = _recon_etf(symbol)
        broker_positions = get_broker_positions_safe()
        broker_orders    = get_broker_orders_safe()
        journal_trades   = get_open_journal_trades_safe()

        _shared_broker_positions = broker_positions   # share for Phase 4
        _shared_broker_orders    = broker_orders

        p3_broker_pos_count = len(broker_positions)
        p3_broker_ord_count = len(broker_orders)
        p3_journal_count    = len(journal_trades)

        # Open position conflict gate
        p3_open_check = check_open_position_conflict(
            symbol         = symbol,
            direction      = direction,
            routed_etf     = routed_etf,
            broker_positions = broker_positions,
        )
        if p3_open_check.get('conflict'):
            p3_open_rejection_code = STATUS_REJECTED_OPEN_POSITION

        # Protective order detection for any existing position
        protective  = detect_protective_orders(routed_etf, broker_positions, broker_orders)
        p3_stop_found    = protective.get('stop_found')
        p3_target_found  = protective.get('target_found')
        p3_unprotected_warn = bool(protective.get('unprotected'))
        if p3_unprotected_warn:
            validation_warnings.append(
                f'UNPROTECTED_POSITION: {routed_etf} position detected with no stop order'
            )

        # Reconciliation scaffold
        recon = reconcile_execution_state(
            execution_request = {'symbol': symbol, 'direction': direction, 'qty': qty},
            broker_positions  = broker_positions,
            broker_orders     = broker_orders,
            journal_trades    = journal_trades,
        )
        p3_recon_status   = recon.get('reconciliation_status')
        p3_recon_warnings = recon.get('warnings', [])
        p3_recon_errors   = recon.get('errors', [])
        if p3_recon_warnings:
            validation_warnings.extend(p3_recon_warnings)
        if p3_recon_errors:
            validation_warnings.extend(p3_recon_errors)   # logged as warnings; not hard errors

    except Exception as _p3_err:
        validation_warnings.append(f'Phase 3 reconcile error (non-blocking): {_p3_err}')

    # ── Phase 4: Post-submit protective confirmation on existing positions ─────
    p4_conf_status:      Optional[str]  = None
    p4_entry_order_found: Optional[bool] = None
    p4_entry_filled:     Optional[bool]  = None
    p4_pos_found:        Optional[bool]  = None
    p4_stop_found:       Optional[bool]  = None
    p4_target_found:     Optional[bool]  = None
    p4_bracket:          Optional[bool]  = None
    p4_emergency_alert:  Optional[dict]  = None
    p4_alert_type:       Optional[str]   = None
    p4_alert_severity:   Optional[str]   = None

    try:
        from services.execution_reconcile import confirm_protective_orders_after_submit
        _p4_req = {
            'symbol':               symbol,
            'direction':            direction,
            'execution_request_id': execution_request_id,
            'decision_id':          decision_id or None,
        }
        p4 = confirm_protective_orders_after_submit(
            execution_request = _p4_req,
            broker_orders     = _shared_broker_orders,
            broker_positions  = _shared_broker_positions,
        )
        p4_conf_status       = p4.get('confirmation_status')
        p4_entry_order_found = p4.get('entry_order_found')
        p4_entry_filled      = p4.get('entry_filled')
        p4_pos_found         = p4.get('position_found')
        p4_stop_found        = p4.get('stop_order_found')
        p4_target_found      = p4.get('target_order_found')
        p4_bracket           = p4.get('bracket_or_oco_detected')
        p4_emergency_alert   = p4.get('emergency_alert')
        if p4_emergency_alert:
            p4_alert_type     = p4_emergency_alert.get('alert_type')
            p4_alert_severity = p4_emergency_alert.get('severity')
            validation_warnings.append(
                f'EMERGENCY {p4_alert_type}: {p4_emergency_alert.get("message", "")}'
            )
        for err in (p4.get('errors') or []):
            validation_warnings.append(err)
    except Exception as _p4_err:
        validation_warnings.append(f'Phase 4 confirmation error (non-blocking): {_p4_err}')

    # ── Determine final status ─────────────────────────────────────────────────
    # Priority: dup > stale > prop_gates > open_position_conflict > dry_run/live
    enforce = prop_gates_enforced(dry_run)

    if dup_check['is_duplicate']:
        final_status = STATUS_DUPLICATE
    elif stale_check.get('checked') and not stale_check.get('missing_timestamp') and stale_check.get('is_stale'):
        final_status = STATUS_STALE
    elif enforce and prop_rejection_code:
        final_status = prop_rejection_code
    elif enforce and p3_open_rejection_code:
        final_status = p3_open_rejection_code
    elif dry_run:
        final_status = STATUS_DRY_RUN_VALIDATED
    else:
        final_status = STATUS_RECEIVED

    req = _build_req(
        execution_request_id=execution_request_id,
        symbol=symbol, direction=direction, setup_type=setup_type,
        signal_type=signal_type, grade=grade, session=session,
        entry=entry, stop=stop, target=target, qty=qty,
        source=source, decision_id=decision_id, signal_id=signal_id,
        signal_generated_at=signal_generated_at,
        created_at=created_at, dry_run=dry_run,
        validation_errors=validation_errors,
        validation_warnings=validation_warnings,
        duplicate_check=dup_check,
        stale_check=stale_check,
        prop_config_loaded=prop_config_loaded,
        prop_firm_name=prop_firm_name,
        prop_account_size=prop_account_size,
        prop_gate_results=prop_gate_results,
        rejected_gate=rejected_gate,
        # Phase 3
        open_position_check=p3_open_check,
        broker_positions_count=p3_broker_pos_count,
        broker_orders_count=p3_broker_ord_count,
        journal_open_trades_count=p3_journal_count,
        reconciliation_status=p3_recon_status,
        protective_stop_found=p3_stop_found,
        protective_target_found=p3_target_found,
        unprotected_position_warning=p3_unprotected_warn,
        reconciliation_warnings=p3_recon_warnings,
        reconciliation_errors=p3_recon_errors,
        # Phase 4
        protective_confirmation_status=p4_conf_status,
        entry_order_found=p4_entry_order_found,
        entry_filled=p4_entry_filled,
        p4_position_found=p4_pos_found,
        stop_order_found=p4_stop_found,
        target_order_found=p4_target_found,
        bracket_or_oco_detected=p4_bracket,
        emergency_alert=p4_emergency_alert,
        emergency_alert_type=p4_alert_type,
        emergency_alert_severity=p4_alert_severity,
        final_status=final_status,
    )

    _append_trace_v2(req)
    return req


def _build_req(
    *, execution_request_id, symbol, direction, setup_type,
    signal_type, grade, session, entry, stop, target, qty,
    source, decision_id, signal_id, signal_generated_at,
    created_at, dry_run, validation_errors, validation_warnings,
    duplicate_check, stale_check,
    prop_config_loaded, prop_firm_name, prop_account_size,
    prop_gate_results, rejected_gate,
    # Phase 3
    open_position_check=None, broker_positions_count=0,
    broker_orders_count=0, journal_open_trades_count=0,
    reconciliation_status=None,
    protective_stop_found=None, protective_target_found=None,
    unprotected_position_warning=False,
    reconciliation_warnings=None, reconciliation_errors=None,
    # Phase 4
    protective_confirmation_status=None,
    entry_order_found=None, entry_filled=None, p4_position_found=None,
    stop_order_found=None, target_order_found=None,
    bracket_or_oco_detected=None,
    emergency_alert=None, emergency_alert_type=None, emergency_alert_severity=None,
    final_status='FAILED',
) -> dict:
    return {
        'execution_request_id': execution_request_id,
        'decision_id':          decision_id or None,
        'signal_id':            signal_id or None,
        'symbol':               symbol,
        'direction':            direction,
        'setup_type':           setup_type,
        'signal_type':          signal_type,
        'grade':                grade,
        'session':              session or None,
        'entry':                entry,
        'stop':                 stop,
        'target':               target,
        'qty':                  qty,
        'source':               source,
        'created_at':           created_at,
        'signal_generated_at':  signal_generated_at or None,
        'signal_age_seconds':   stale_check.get('signal_age_seconds'),
        'status':               final_status,
        'dry_run':              dry_run,
        'validation_errors':    validation_errors,
        'validation_warnings':  validation_warnings,
        'duplicate_check':      duplicate_check,
        'stale_check':          stale_check,
        # Phase 2 prop gate trace fields
        'prop_config_loaded':   prop_config_loaded,
        'prop_firm_name':       prop_firm_name,
        'prop_account_size':    prop_account_size,
        'prop_gate_results':    prop_gate_results,
        'rejected_gate':        rejected_gate,
        # Phase 3 reconciliation trace fields
        'open_position_check':          open_position_check or {'checked': False, 'conflict': False},
        'broker_positions_count':       broker_positions_count,
        'broker_orders_count':          broker_orders_count,
        'journal_open_trades_count':    journal_open_trades_count,
        'reconciliation_status':        reconciliation_status,
        'protective_stop_found':        protective_stop_found,
        'protective_target_found':      protective_target_found,
        'unprotected_position_warning': unprotected_position_warning,
        'reconciliation_warnings':      reconciliation_warnings or [],
        'reconciliation_errors':        reconciliation_errors or [],
        # Phase 4 protective confirmation trace fields
        'protective_confirmation_status': protective_confirmation_status,
        'entry_order_found':              entry_order_found,
        'entry_filled':                   entry_filled,
        'position_found':                 p4_position_found,
        'stop_order_found':               stop_order_found,
        'target_order_found':             target_order_found,
        'bracket_or_oco_detected':        bracket_or_oco_detected,
        'emergency_alert':                emergency_alert,
        'emergency_alert_type':           emergency_alert_type,
        'emergency_alert_severity':       emergency_alert_severity,
        'broker_called':        False,
        'final_status':         final_status,
    }


# ── Internal I/O helpers ──────────────────────────────────────────────────────

def _append_registry_locked(
    *, registry, execution_request_id, decision_id, signal_id,
    symbol, direction, setup_type, created_at, status,
) -> None:
    """Must be called inside _lock. Mutates registry and writes to disk."""
    registry.setdefault('records', []).append({
        'execution_request_id': execution_request_id,
        'decision_id':          decision_id or None,
        'signal_id':            signal_id or None,
        'symbol':               symbol,
        'direction':            direction,
        'setup_type':           setup_type,
        'created_at':           created_at,
        'status':               status,
    })
    _save_registry(registry)


def _append_trace_v2(req: dict) -> None:
    with _lock:
        entries = _load_trace_v2()
        entries.append({**req, 'timestamp': req.get('created_at', _utc_now())})
        _save_trace_v2(entries)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Public helpers ────────────────────────────────────────────────────────────

def get_registry_stats() -> dict:
    """Summary stats for /api/execution-registry endpoint."""
    try:
        with _lock:
            reg = _load_registry()
        records = reg.get('records', [])
        by_status: dict = {}
        for r in records:
            s = r.get('status', 'UNKNOWN')
            by_status[s] = by_status.get(s, 0) + 1
        return {
            'total_records': len(records),
            'by_status':     by_status,
            'latest':        records[-1] if records else None,
        }
    except Exception as e:
        return {'error': str(e)}


def get_trace_v2_recent(limit: int = 50) -> list:
    """Return the most recent trace_v2 entries (newest first)."""
    try:
        with _lock:
            entries = _load_trace_v2()
        return list(reversed(entries[-limit:]))
    except Exception:
        return []
