"""test_execution_bot_v2_phase2.py — Execution Bot v2 Phase 2 tests.

Tests cover:
- prop_risk: default config has all gates disabled (zero/empty)
- prop_risk: load_prop_config falls back to defaults when file missing
- prop_risk: save_prop_config round-trips correctly
- prop_risk: allowed_symbols gate — PASS, FAIL, SKIP
- prop_risk: allowed_sessions gate — PASS, FAIL, SKIP
- prop_risk: max_trades_per_day gate — PASS, FAIL, SKIP
- prop_risk: max_contracts_total gate — PASS, FAIL, SKIP
- prop_risk: max_contracts_per_symbol gate (MNQ→QQQ routing) — PASS, FAIL
- prop_risk: daily_loss gate — PASS, FAIL, SKIP
- prop_risk: max_total_loss gate — PASS, FAIL, SKIP
- validate_and_record: prop gate results included in req dict
- validate_and_record: prop rejection blocks when dry_run=True
- validate_and_record: prop rejection does NOT block when dry_run=False and NOVA_PROP_GATES_ENABLED=false (default)
- validate_and_record: prop rejection blocks when NOVA_PROP_GATES_ENABLED=true in live mode
- validate_and_record: prop gate error is non-blocking (warning only)
- validate_and_record: session field flows into req dict
- validate_and_record: trace_v2 includes all prop fields

All file I/O is isolated to tmp_path.
All prop gate tests use explicit mock runtime context — no state_engine dependency.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from datetime import datetime, timezone, timedelta


# ── Helpers ────────────────────────────────────────────────────────────────────

def _isolated_er(tmp_path: Path):
    """Fresh execution_request module isolated to tmp_path."""
    for key in list(sys.modules.keys()):
        if key in ('services.execution_request', 'services.prop_risk'):
            del sys.modules[key]
    import services.execution_request as er
    er._registry_file = lambda: tmp_path / 'nova_execution_registry.json'
    er._trace_v2_file = lambda: tmp_path / 'nova_execution_trace_v2.json'
    return er


def _isolated_pr(tmp_path: Path):
    """Fresh prop_risk module isolated to tmp_path."""
    for key in list(sys.modules.keys()):
        if key == 'services.prop_risk':
            del sys.modules[key]
    import services.prop_risk as pr
    pr._prop_config_file = lambda: tmp_path / 'nova_prop_risk_config.json'
    return pr


def _past_iso(seconds: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


def _base_req(er, tmp_path, **extra):
    """Make a fresh validate_and_record call with minimal required args."""
    return er.validate_and_record(
        symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
        signal_generated_at=_past_iso(5),
        dry_run_override=True,
        **extra,
    )


# ── 1. Default config — all gates disabled ────────────────────────────────────

def test_default_config_all_gates_skip(tmp_path):
    """Default config with all-zero values should produce all SKIP results."""
    pr = _isolated_pr(tmp_path)
    config = pr.get_default_config()
    results = pr.run_prop_gates('MNQ', 'NY_OPEN', config=config)
    for r in results:
        assert r['result'] in ('SKIP', 'PASS'), (
            f"Gate {r['gate']} should be SKIP or PASS on default config, got {r['result']}"
        )
    skipped = [r for r in results if r['result'] == 'SKIP']
    assert len(skipped) >= 5, 'Most gates should be SKIP with zero config'


# ── 2. load_prop_config falls back to defaults when file missing ──────────────

def test_load_prop_config_missing_file_returns_defaults(tmp_path):
    pr = _isolated_pr(tmp_path)
    config = pr.load_prop_config()
    assert isinstance(config, dict)
    assert config.get('_config_missing') is True
    assert config.get('max_daily_loss') == 0.0
    assert config.get('allowed_symbols') == []


# ── 3. save_prop_config round-trips correctly ────────────────────────────────

def test_save_and_load_config_roundtrip(tmp_path):
    pr = _isolated_pr(tmp_path)
    cfg = pr.get_default_config()
    cfg['prop_firm_name']    = 'APEX'
    cfg['account_size']      = 50000.0
    cfg['max_daily_loss']    = 2500.0
    cfg['max_trades_per_day'] = 3
    cfg['allowed_symbols']   = ['MNQ', 'MES']
    pr.save_prop_config(cfg)
    loaded = pr.load_prop_config()
    assert loaded['prop_firm_name'] == 'APEX'
    assert loaded['account_size']   == 50000.0
    assert loaded['max_daily_loss'] == 2500.0
    assert loaded['max_trades_per_day'] == 3
    assert 'MNQ' in loaded['allowed_symbols']
    assert loaded.get('_config_missing') is False


# ── 4. allowed_symbols gate ───────────────────────────────────────────────────

def test_allowed_symbols_gate_pass(tmp_path):
    pr = _isolated_pr(tmp_path)
    cfg = pr.get_default_config()
    cfg['allowed_symbols'] = ['MNQ', 'MES']
    results = pr.run_prop_gates('MNQ', '', config=cfg)
    gate = next(r for r in results if r['gate'] == 'ALLOWED_SYMBOLS')
    assert gate['result'] == 'PASS'


def test_allowed_symbols_gate_fail(tmp_path):
    pr = _isolated_pr(tmp_path)
    cfg = pr.get_default_config()
    cfg['allowed_symbols'] = ['MES']
    results = pr.run_prop_gates('MNQ', '', config=cfg)
    gate = next(r for r in results if r['gate'] == 'ALLOWED_SYMBOLS')
    assert gate['result'] == 'FAIL'
    assert gate['rejection_code'] == 'REJECTED_SYMBOL_NOT_ALLOWED'


def test_allowed_symbols_gate_skip_when_empty(tmp_path):
    pr = _isolated_pr(tmp_path)
    cfg = pr.get_default_config()
    cfg['allowed_symbols'] = []
    results = pr.run_prop_gates('MNQ', '', config=cfg)
    gate = next(r for r in results if r['gate'] == 'ALLOWED_SYMBOLS')
    assert gate['result'] == 'SKIP'


# ── 5. allowed_sessions gate ──────────────────────────────────────────────────

def test_allowed_sessions_gate_pass(tmp_path):
    pr = _isolated_pr(tmp_path)
    cfg = pr.get_default_config()
    cfg['allowed_sessions'] = ['NY_OPEN', 'NY_AM']
    results = pr.run_prop_gates('MNQ', 'NY_OPEN', config=cfg)
    gate = next(r for r in results if r['gate'] == 'ALLOWED_SESSIONS')
    assert gate['result'] == 'PASS'


def test_allowed_sessions_gate_fail(tmp_path):
    pr = _isolated_pr(tmp_path)
    cfg = pr.get_default_config()
    cfg['allowed_sessions'] = ['NY_AM']
    results = pr.run_prop_gates('MNQ', 'ASIA', config=cfg)
    gate = next(r for r in results if r['gate'] == 'ALLOWED_SESSIONS')
    assert gate['result'] == 'FAIL'
    assert gate['rejection_code'] == 'REJECTED_SESSION'


def test_allowed_sessions_gate_skip_when_empty(tmp_path):
    pr = _isolated_pr(tmp_path)
    cfg = pr.get_default_config()
    cfg['allowed_sessions'] = []
    results = pr.run_prop_gates('MNQ', 'ASIA', config=cfg)
    gate = next(r for r in results if r['gate'] == 'ALLOWED_SESSIONS')
    assert gate['result'] == 'SKIP'


# ── 6. max_trades_per_day gate ────────────────────────────────────────────────

def test_max_trades_gate_pass(tmp_path):
    pr = _isolated_pr(tmp_path)
    cfg = pr.get_default_config()
    cfg['max_trades_per_day'] = 3
    results = pr.run_prop_gates('MNQ', '', trade_count=2, config=cfg)
    gate = next(r for r in results if r['gate'] == 'MAX_TRADES_PER_DAY')
    assert gate['result'] == 'PASS'


def test_max_trades_gate_fail_at_limit(tmp_path):
    pr = _isolated_pr(tmp_path)
    cfg = pr.get_default_config()
    cfg['max_trades_per_day'] = 3
    results = pr.run_prop_gates('MNQ', '', trade_count=3, config=cfg)
    gate = next(r for r in results if r['gate'] == 'MAX_TRADES_PER_DAY')
    assert gate['result'] == 'FAIL'
    assert gate['rejection_code'] == 'REJECTED_MAX_TRADES'


def test_max_trades_gate_skip_when_zero(tmp_path):
    pr = _isolated_pr(tmp_path)
    cfg = pr.get_default_config()
    cfg['max_trades_per_day'] = 0
    results = pr.run_prop_gates('MNQ', '', trade_count=99, config=cfg)
    gate = next(r for r in results if r['gate'] == 'MAX_TRADES_PER_DAY')
    assert gate['result'] == 'SKIP'


# ── 7. max_contracts_total gate ───────────────────────────────────────────────

def test_max_contracts_total_gate_fail(tmp_path):
    pr = _isolated_pr(tmp_path)
    cfg = pr.get_default_config()
    cfg['max_contracts_total'] = 2
    positions = [{'symbol': 'SPY'}, {'symbol': 'QQQ'}]
    results = pr.run_prop_gates('MNQ', '', open_positions=positions, config=cfg)
    gate = next(r for r in results if r['gate'] == 'MAX_CONTRACTS_TOTAL')
    assert gate['result'] == 'FAIL'
    assert gate['rejection_code'] == 'REJECTED_MAX_CONTRACTS'


def test_max_contracts_total_gate_pass(tmp_path):
    pr = _isolated_pr(tmp_path)
    cfg = pr.get_default_config()
    cfg['max_contracts_total'] = 2
    positions = [{'symbol': 'SPY'}]
    results = pr.run_prop_gates('MNQ', '', open_positions=positions, config=cfg)
    gate = next(r for r in results if r['gate'] == 'MAX_CONTRACTS_TOTAL')
    assert gate['result'] == 'PASS'


# ── 8. max_contracts_per_symbol gate (ETF routing) ───────────────────────────

def test_max_contracts_per_symbol_mnq_routes_to_qqq(tmp_path):
    """MNQ signal should count QQQ positions, not SPY."""
    pr = _isolated_pr(tmp_path)
    cfg = pr.get_default_config()
    cfg['max_contracts_per_symbol'] = 1
    # One QQQ position already open — MNQ (→QQQ) should FAIL
    positions = [{'symbol': 'QQQ'}]
    results = pr.run_prop_gates('MNQ', '', open_positions=positions, config=cfg)
    gate = next(r for r in results if r['gate'] == 'MAX_CONTRACTS_PER_SYMBOL')
    assert gate['result'] == 'FAIL'
    assert 'QQQ' in gate['reason']


def test_max_contracts_per_symbol_mes_routes_to_spy(tmp_path):
    """MES signal should count SPY positions."""
    pr = _isolated_pr(tmp_path)
    cfg = pr.get_default_config()
    cfg['max_contracts_per_symbol'] = 1
    positions = [{'symbol': 'SPY'}]
    results = pr.run_prop_gates('MES', '', open_positions=positions, config=cfg)
    gate = next(r for r in results if r['gate'] == 'MAX_CONTRACTS_PER_SYMBOL')
    assert gate['result'] == 'FAIL'


def test_max_contracts_per_symbol_different_etf_does_not_block(tmp_path):
    """QQQ position should not count against SPY (MES) limit."""
    pr = _isolated_pr(tmp_path)
    cfg = pr.get_default_config()
    cfg['max_contracts_per_symbol'] = 1
    positions = [{'symbol': 'QQQ'}]  # no SPY positions
    results = pr.run_prop_gates('MES', '', open_positions=positions, config=cfg)
    gate = next(r for r in results if r['gate'] == 'MAX_CONTRACTS_PER_SYMBOL')
    assert gate['result'] == 'PASS'


# ── 9. daily_loss gate ────────────────────────────────────────────────────────

def test_daily_loss_gate_fail(tmp_path):
    pr = _isolated_pr(tmp_path)
    cfg = pr.get_default_config()
    cfg['max_daily_loss'] = 1000.0
    results = pr.run_prop_gates('MNQ', '', daily_pnl=-1200.0, config=cfg)
    gate = next(r for r in results if r['gate'] == 'DAILY_LOSS_LIMIT')
    assert gate['result'] == 'FAIL'
    assert gate['rejection_code'] == 'REJECTED_PROP_DAILY_LOSS'


def test_daily_loss_gate_pass(tmp_path):
    pr = _isolated_pr(tmp_path)
    cfg = pr.get_default_config()
    cfg['max_daily_loss'] = 1000.0
    results = pr.run_prop_gates('MNQ', '', daily_pnl=-500.0, config=cfg)
    gate = next(r for r in results if r['gate'] == 'DAILY_LOSS_LIMIT')
    assert gate['result'] == 'PASS'


def test_daily_loss_gate_skip_when_zero(tmp_path):
    pr = _isolated_pr(tmp_path)
    cfg = pr.get_default_config()
    cfg['max_daily_loss'] = 0.0
    results = pr.run_prop_gates('MNQ', '', daily_pnl=-99999.0, config=cfg)
    gate = next(r for r in results if r['gate'] == 'DAILY_LOSS_LIMIT')
    assert gate['result'] == 'SKIP'


# ── 10. max_total_loss gate ───────────────────────────────────────────────────

def test_max_total_loss_gate_fail(tmp_path):
    pr = _isolated_pr(tmp_path)
    cfg = pr.get_default_config()
    cfg['max_total_loss']   = 3000.0
    cfg['starting_balance'] = 50000.0
    cfg['current_balance']  = 46500.0   # loss = 3500 > 3000
    results = pr.run_prop_gates('MNQ', '', config=cfg)
    gate = next(r for r in results if r['gate'] == 'MAX_TOTAL_LOSS')
    assert gate['result'] == 'FAIL'
    assert gate['rejection_code'] == 'REJECTED_PROP_MAX_LOSS'


def test_max_total_loss_gate_pass(tmp_path):
    pr = _isolated_pr(tmp_path)
    cfg = pr.get_default_config()
    cfg['max_total_loss']   = 3000.0
    cfg['starting_balance'] = 50000.0
    cfg['current_balance']  = 48000.0   # loss = 2000 < 3000
    results = pr.run_prop_gates('MNQ', '', config=cfg)
    gate = next(r for r in results if r['gate'] == 'MAX_TOTAL_LOSS')
    assert gate['result'] == 'PASS'


def test_max_total_loss_gate_skip_when_missing_balance(tmp_path):
    pr = _isolated_pr(tmp_path)
    cfg = pr.get_default_config()
    cfg['max_total_loss']   = 3000.0
    cfg['starting_balance'] = 0.0   # missing → skip
    cfg['current_balance']  = 0.0
    results = pr.run_prop_gates('MNQ', '', config=cfg)
    gate = next(r for r in results if r['gate'] == 'MAX_TOTAL_LOSS')
    assert gate['result'] == 'SKIP'


# ── 11. validate_and_record includes prop gate results ────────────────────────

def test_validate_and_record_includes_prop_fields(tmp_path):
    er = _isolated_er(tmp_path)
    pr_module = _isolated_pr(tmp_path)
    cfg = pr_module.get_default_config()
    pr_module.save_prop_config(cfg)

    with patch('services.prop_risk.get_runtime_context', return_value={
        'trade_count': 0, 'daily_pnl': 0.0, 'open_positions': [],
    }):
        req = er.validate_and_record(
            symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
            session='NY_OPEN',
            signal_generated_at=_past_iso(5),
            dry_run_override=True,
        )

    assert 'prop_gate_results' in req
    assert isinstance(req['prop_gate_results'], list)
    assert 'prop_config_loaded' in req
    assert 'rejected_gate' in req
    assert req['session'] == 'NY_OPEN'


# ── 12. prop rejection blocks in dry-run mode ─────────────────────────────────

def test_prop_gate_rejection_blocks_in_dry_run(tmp_path):
    er = _isolated_er(tmp_path)
    pr_module = _isolated_pr(tmp_path)
    cfg = pr_module.get_default_config()
    cfg['max_trades_per_day'] = 2
    pr_module.save_prop_config(cfg)

    with patch('services.prop_risk.get_runtime_context', return_value={
        'trade_count': 2, 'daily_pnl': 0.0, 'open_positions': [],
    }):
        req = er.validate_and_record(
            symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
            signal_generated_at=_past_iso(5),
            dry_run_override=True,
        )

    assert req['final_status'] == 'REJECTED_MAX_TRADES'
    assert req['rejected_gate'] == 'MAX_TRADES_PER_DAY'
    assert req['broker_called'] is False


# ── 13. prop rejection does NOT block in live mode (default) ──────────────────

def test_prop_gate_rejection_does_not_block_live_mode_by_default(tmp_path):
    """NOVA_PROP_GATES_ENABLED defaults to false — gates log but don't block live."""
    er = _isolated_er(tmp_path)
    pr_module = _isolated_pr(tmp_path)
    cfg = pr_module.get_default_config()
    cfg['max_trades_per_day'] = 1
    pr_module.save_prop_config(cfg)

    with patch('services.prop_risk.get_runtime_context', return_value={
        'trade_count': 5, 'daily_pnl': 0.0, 'open_positions': [],
    }):
        with patch.dict('os.environ', {'NOVA_PROP_GATES_ENABLED': 'false'}):
            req = er.validate_and_record(
                symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
                signal_generated_at=_past_iso(5),
                dry_run_override=False,
            )

    assert req['final_status'] == er.STATUS_RECEIVED, (
        f'Live mode with NOVA_PROP_GATES_ENABLED=false should return RECEIVED, '
        f'got {req["final_status"]}'
    )
    # Gates still ran and logged the failure
    failed = [g for g in req.get('prop_gate_results', []) if g['result'] == 'FAIL']
    assert any(g['gate'] == 'MAX_TRADES_PER_DAY' for g in failed)


# ── 14. prop rejection blocks when NOVA_PROP_GATES_ENABLED=true in live mode ─

def test_prop_gate_blocks_live_when_gates_enabled(tmp_path):
    er = _isolated_er(tmp_path)
    pr_module = _isolated_pr(tmp_path)
    cfg = pr_module.get_default_config()
    cfg['max_trades_per_day'] = 1
    pr_module.save_prop_config(cfg)

    with patch('services.prop_risk.get_runtime_context', return_value={
        'trade_count': 1, 'daily_pnl': 0.0, 'open_positions': [],
    }):
        with patch.dict('os.environ', {'NOVA_PROP_GATES_ENABLED': 'true'}):
            req = er.validate_and_record(
                symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
                signal_generated_at=_past_iso(5),
                dry_run_override=False,
            )

    assert req['final_status'] == 'REJECTED_MAX_TRADES'


# ── 15. prop gate module error is non-blocking (warning only) ─────────────────

def test_prop_gate_error_is_non_blocking(tmp_path):
    er = _isolated_er(tmp_path)

    with patch.dict('sys.modules', {'services.prop_risk': None}):
        req = er.validate_and_record(
            symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
            signal_generated_at=_past_iso(5),
            dry_run_override=True,
        )

    # Should not crash — gate error recorded as warning, still returns a valid status
    assert isinstance(req, dict)
    assert 'final_status' in req
    warnings = req.get('validation_warnings', [])
    assert any('prop_risk' in w.lower() or 'gate' in w.lower() for w in warnings)


# ── 16. session field flows into req dict ─────────────────────────────────────

def test_session_field_present_in_req(tmp_path):
    er = _isolated_er(tmp_path)
    req = er.validate_and_record(
        symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
        session='NY_AM',
        signal_generated_at=_past_iso(5),
        dry_run_override=True,
    )
    assert req['session'] == 'NY_AM'


def test_session_field_defaults_to_none_when_empty(tmp_path):
    er = _isolated_er(tmp_path)
    req = er.validate_and_record(
        symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
        signal_generated_at=_past_iso(5),
        dry_run_override=True,
    )
    assert req['session'] is None


# ── 17. trace_v2 includes all prop fields ─────────────────────────────────────

def test_trace_v2_includes_prop_fields(tmp_path):
    er = _isolated_er(tmp_path)
    req = er.validate_and_record(
        symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
        session='NY_OPEN',
        signal_generated_at=_past_iso(5),
        dry_run_override=True,
    )
    entries = er.get_trace_v2_recent(5)
    assert entries, 'trace_v2 must have at least one entry'
    latest = entries[0]
    assert 'prop_config_loaded' in latest
    assert 'prop_gate_results'  in latest
    assert 'rejected_gate'      in latest
    assert latest.get('session') == 'NY_OPEN'
