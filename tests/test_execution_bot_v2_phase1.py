"""test_execution_bot_v2_phase1.py — Execution Bot v2 Phase 1 tests.

Tests cover:
- execution_request_id generation (deterministic)
- Full request build with and without decision_id
- Persistent dedup: by execution_request_id, decision_id, signal_id
- Registry survives reload (persistent across "restart")
- Stale signal rejection
- Fresh signal validation
- Missing signal timestamp: warns, does not block in dry-run
- Dry-run mode: DRY_RUN_VALIDATED, broker NOT called
- Trace v2 record written for every attempt
- Malformed payload: REJECTED_BAD_PAYLOAD
- No execution behavior change in live path (existing bridge path unchanged)

All file I/O is isolated to tmp_path via module-level function patching.
dry_run_override is passed explicitly rather than env-var patching so tests
remain deterministic regardless of local NOVA_EXECUTION_DRY_RUN setting.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────────

def _isolated_module(tmp_path: Path):
    """
    Import execution_request with file paths isolated to tmp_path.
    Returns the module object.
    """
    for key in list(sys.modules.keys()):
        if key == 'services.execution_request':
            del sys.modules[key]

    import services.execution_request as er
    er._registry_file = lambda: tmp_path / 'nova_execution_registry.json'
    er._trace_v2_file = lambda: tmp_path / 'nova_execution_trace_v2.json'
    return er


def _past_iso(seconds: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


# ── Test 1: execution_request_id is deterministic ─────────────────────────────

def test_execution_request_id_deterministic(tmp_path):
    """Same inputs within the same second produce the same EXREQ hash."""
    er = _isolated_module(tmp_path)
    fixed_ts = datetime(2026, 6, 30, 14, 0, 0, tzinfo=timezone.utc)
    with patch('services.execution_request.datetime') as mock_dt:
        mock_dt.now.return_value = fixed_ts
        mock_dt.fromisoformat = datetime.fromisoformat
        id1 = er.build_execution_request_id('MNQ', 'LONG', 'PROS_LONG', 'DEC123', 'SIG456', '2026-01-01T10:00:00Z')
        id2 = er.build_execution_request_id('MNQ', 'LONG', 'PROS_LONG', 'DEC123', 'SIG456', '2026-01-01T10:00:00Z')
    assert id1 == id2
    assert id1.startswith('EXREQ_')
    parts = id1.split('_')
    assert len(parts) == 4, f'Expected EXREQ_YYYYMMDD_HHMMSS_HASH8 but got: {id1}'


def test_execution_request_id_differs_on_different_inputs(tmp_path):
    er = _isolated_module(tmp_path)
    id1 = er.build_execution_request_id('MNQ', 'LONG',  'PROS_LONG')
    id2 = er.build_execution_request_id('MES', 'SHORT', 'ORB_E1_SHORT')
    assert id1 != id2


# ── Test 2: builds full request with decision_id ──────────────────────────────

def test_request_builds_with_decision_id(tmp_path):
    er = _isolated_module(tmp_path)
    req = er.validate_and_record(
        symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
        decision_id='DEC-001', signal_id='SIG-001',
        signal_generated_at=_past_iso(10),
        dry_run_override=True,
    )
    assert req['final_status'] == er.STATUS_DRY_RUN_VALIDATED
    assert req['decision_id'] == 'DEC-001'
    assert req['signal_id'] == 'SIG-001'
    assert req['symbol'] == 'MNQ'
    assert req['direction'] == 'LONG'
    assert req['setup_type'] == 'PROS_LONG'
    assert req['execution_request_id'].startswith('EXREQ_')
    assert req['broker_called'] is False
    assert req['dry_run'] is True


# ── Test 3: builds safely without decision_id ─────────────────────────────────

def test_request_builds_without_decision_id(tmp_path):
    er = _isolated_module(tmp_path)
    req = er.validate_and_record(
        symbol='MES', direction='SHORT', setup_type='ORB_E1_SHORT',
        signal_generated_at=_past_iso(5),
        dry_run_override=True,
    )
    assert req['final_status'] == er.STATUS_DRY_RUN_VALIDATED
    assert req['decision_id'] is None
    assert any('decision_id missing' in w for w in req['validation_warnings'])
    assert req['validation_errors'] == []


# ── Test 4: duplicate by signal_id rejected ───────────────────────────────────

def test_duplicate_by_signal_id_rejected(tmp_path):
    er = _isolated_module(tmp_path)
    r1 = er.validate_and_record(
        symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
        signal_id='SIG-DUP-001',
        signal_generated_at=_past_iso(10),
        dry_run_override=True,
    )
    assert r1['final_status'] == er.STATUS_DRY_RUN_VALIDATED

    r2 = er.validate_and_record(
        symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
        signal_id='SIG-DUP-001',
        signal_generated_at=_past_iso(10),
        dry_run_override=True,
    )
    assert r2['final_status'] == er.STATUS_DUPLICATE
    assert r2['duplicate_check']['matched_on'] == 'signal_id'
    assert r2['duplicate_check']['matched_id'] == 'SIG-DUP-001'


# ── Test 5: duplicate by decision_id rejected ─────────────────────────────────

def test_duplicate_by_decision_id_rejected(tmp_path):
    er = _isolated_module(tmp_path)
    r1 = er.validate_and_record(
        symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
        decision_id='DEC-DEDUP-002',
        signal_generated_at=_past_iso(10),
        dry_run_override=True,
    )
    assert r1['final_status'] == er.STATUS_DRY_RUN_VALIDATED

    r2 = er.validate_and_record(
        symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
        decision_id='DEC-DEDUP-002',
        signal_generated_at=_past_iso(10),
        dry_run_override=True,
    )
    assert r2['final_status'] == er.STATUS_DUPLICATE
    assert r2['duplicate_check']['matched_on'] == 'decision_id'


# ── Test 6: duplicate by execution_request_id rejected ───────────────────────

def test_duplicate_by_execution_request_id_rejected(tmp_path):
    """Two calls with identical inputs in the same second share the same EXREQ id → duplicate."""
    er = _isolated_module(tmp_path)
    fixed_ts = datetime(2026, 6, 30, 14, 0, 0, tzinfo=timezone.utc)
    sig_ts   = _past_iso(5)

    with patch('services.execution_request.datetime') as mock_dt:
        mock_dt.now.return_value = fixed_ts
        mock_dt.fromisoformat = datetime.fromisoformat
        r1 = er.validate_and_record(
            symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
            signal_generated_at=sig_ts,
            dry_run_override=True,
        )
    assert r1['final_status'] == er.STATUS_DRY_RUN_VALIDATED

    # Same second → same EXREQ id → DUPLICATE
    with patch('services.execution_request.datetime') as mock_dt:
        mock_dt.now.return_value = fixed_ts
        mock_dt.fromisoformat = datetime.fromisoformat
        r2 = er.validate_and_record(
            symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
            signal_generated_at=sig_ts,
            dry_run_override=True,
        )
    assert r2['final_status'] == er.STATUS_DUPLICATE
    assert r2['duplicate_check']['matched_on'] == 'execution_request_id'


# ── Test 7: registry persists across reload ───────────────────────────────────

def test_registry_persists_across_reload(tmp_path):
    """Dedup registry survives module re-import (simulates process restart)."""
    er = _isolated_module(tmp_path)
    r1 = er.validate_and_record(
        symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
        signal_id='SIG-PERSIST-004',
        signal_generated_at=_past_iso(10),
        dry_run_override=True,
    )
    assert r1['final_status'] == er.STATUS_DRY_RUN_VALIDATED

    # Verify registry file exists on disk
    registry_path = tmp_path / 'nova_execution_registry.json'
    assert registry_path.exists(), 'Registry file must be written to disk'

    # Simulate restart: re-import the module
    er2 = _isolated_module(tmp_path)   # clears sys.modules cache
    r2 = er2.validate_and_record(
        symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
        signal_id='SIG-PERSIST-004',
        signal_generated_at=_past_iso(10),
        dry_run_override=True,
    )
    assert r2['final_status'] == er2.STATUS_DUPLICATE, \
        'Registry must survive module reload — dedup must not reset on restart'


# ── Test 8: stale signal rejected ─────────────────────────────────────────────

def test_stale_signal_rejected(tmp_path):
    er = _isolated_module(tmp_path)
    req = er.validate_and_record(
        symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
        signal_generated_at=_past_iso(500),   # 500s >> 120s limit
        dry_run_override=True,
    )
    assert req['final_status'] == er.STATUS_STALE
    assert req['stale_check']['is_stale'] is True
    assert req['stale_check']['signal_age_seconds'] > 120


# ── Test 9: fresh signal passes ───────────────────────────────────────────────

def test_fresh_signal_passes(tmp_path):
    er = _isolated_module(tmp_path)
    req = er.validate_and_record(
        symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
        signal_generated_at=_past_iso(5),     # 5s — well within 120s limit
        dry_run_override=True,
    )
    assert req['final_status'] == er.STATUS_DRY_RUN_VALIDATED
    assert req['stale_check']['is_stale'] is False
    assert req['stale_check']['signal_age_seconds'] < 120


# ── Test 10: missing signal timestamp warns, does not block ───────────────────

def test_missing_signal_timestamp_warns_not_blocks(tmp_path):
    er = _isolated_module(tmp_path)
    req = er.validate_and_record(
        symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
        signal_generated_at='',
        dry_run_override=True,
    )
    assert req['final_status'] == er.STATUS_DRY_RUN_VALIDATED  # not stale-rejected
    assert req['stale_check']['missing_timestamp'] is True
    assert any('MISSING_SIGNAL_TIMESTAMP' in w for w in req['validation_warnings'])


# ── Test 11: dry-run does not call broker ─────────────────────────────────────

def test_dry_run_does_not_call_broker(tmp_path):
    er = _isolated_module(tmp_path)
    broker_calls = []

    with patch('services.execution.execute_signal', side_effect=lambda *a, **k: broker_calls.append(1)):
        req = er.validate_and_record(
            symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
            signal_generated_at=_past_iso(5),
            dry_run_override=True,
        )

    assert req['broker_called'] is False
    assert broker_calls == [], 'execute_signal must never be called by Phase 1 module'


# ── Test 12: trace_v2 record is written ───────────────────────────────────────

def test_trace_v2_record_written(tmp_path):
    er = _isolated_module(tmp_path)
    req = er.validate_and_record(
        symbol='MES', direction='SHORT', setup_type='ORB_E1_SHORT',
        signal_generated_at=_past_iso(5),
        dry_run_override=True,
    )
    entries = er.get_trace_v2_recent(10)
    assert len(entries) >= 1
    latest = entries[0]
    assert latest['execution_request_id'] == req['execution_request_id']
    assert latest['final_status'] == er.STATUS_DRY_RUN_VALIDATED
    assert 'timestamp' in latest


def test_trace_v2_written_for_rejected(tmp_path):
    """Every rejection also produces a trace_v2 record."""
    er = _isolated_module(tmp_path)
    req = er.validate_and_record(
        symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
        signal_generated_at=_past_iso(500),   # stale
        dry_run_override=True,
    )
    assert req['final_status'] == er.STATUS_STALE
    entries = er.get_trace_v2_recent(10)
    assert any(e['final_status'] == er.STATUS_STALE for e in entries)


# ── Test 13: malformed payload returns REJECTED_BAD_PAYLOAD ───────────────────

def test_missing_symbol_bad_payload(tmp_path):
    er = _isolated_module(tmp_path)
    req = er.validate_and_record(
        symbol='', direction='LONG', setup_type='PROS_LONG', dry_run_override=True,
    )
    assert req['final_status'] == er.STATUS_BAD_PAYLOAD
    assert any('symbol' in e for e in req['validation_errors'])


def test_invalid_direction_bad_payload(tmp_path):
    er = _isolated_module(tmp_path)
    req = er.validate_and_record(
        symbol='MNQ', direction='N/A', setup_type='PROS_LONG', dry_run_override=True,
    )
    assert req['final_status'] == er.STATUS_BAD_PAYLOAD
    assert any('direction' in e for e in req['validation_errors'])


def test_missing_setup_type_bad_payload(tmp_path):
    er = _isolated_module(tmp_path)
    req = er.validate_and_record(
        symbol='MNQ', direction='LONG', setup_type='', dry_run_override=True,
    )
    assert req['final_status'] == er.STATUS_BAD_PAYLOAD
    assert any('setup_type' in e for e in req['validation_errors'])


# ── Test 14: live path unchanged ──────────────────────────────────────────────

def test_live_mode_returns_received_not_dry_run(tmp_path):
    er = _isolated_module(tmp_path)
    req = er.validate_and_record(
        symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
        signal_generated_at=_past_iso(5),
        dry_run_override=False,
    )
    assert req['final_status'] == er.STATUS_RECEIVED
    assert req['dry_run'] is False


def test_bridge_phase1_error_does_not_block_live_path(tmp_path):
    """
    If Phase 1 raises an exception in route_to_execution(), it must be caught
    in the try-except block and never propagate to the caller.
    Phase 1 is an observation layer — it must never crash the bridge.
    """
    from delivery.alert_engine import AlertData, EXECUTION_READY
    from services.execution_bridge import route_to_execution

    alert = AlertData(
        alert_type  = EXECUTION_READY,
        symbol      = 'MES',
        setup_type  = 'PROS_LONG',
        direction   = 'LONG',
        grade       = 'A',
        session     = 'NY_OPEN',
    )

    # Patch Phase 1 to raise — bridge must not propagate the exception
    with patch('services.execution_request.validate_and_record', side_effect=RuntimeError('Phase 1 exploded')):
        # Should NOT raise; Phase 1 errors are caught with try-except in bridge
        result = route_to_execution(alert)

    # Bridge returned a result dict (did not crash)
    assert isinstance(result, dict)
    assert 'status' in result
    # Phase 1 error was non-blocking: either recorded in execution_request (early-exit gates)
    # or the bridge continued past Phase 1 to a downstream gate (proven by a rejection code).
    er_field = result.get('execution_request', {})
    phase1_recorded     = (er_field.get('error') == 'Phase 1 exploded'
                           or er_field.get('final_status') == 'FAILED')
    downstream_rejected = bool(result.get('code'))   # any gate code proves bridge ran past Phase 1
    assert phase1_recorded or downstream_rejected, (
        f'Phase 1 exception blocked the bridge unexpectedly: {result}'
    )
