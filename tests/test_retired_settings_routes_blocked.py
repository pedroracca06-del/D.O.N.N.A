"""Retired-trading safety: the two legacy settings-write routes.

The Settings audit proved that POST /execution/settings and
POST /risk-engine/settings were still fully usable while
NOVA_TRADING_SUBSYSTEM_ENABLED was false. Exercised live against an isolated
snapshot, /execution/settings accepted and durably persisted
execution_mode='live_personal' with min_grade C, 99 trades/day and 0 cooldown,
answering status:'ok'. /risk-engine/settings accepted risk_pct=-50, also with
status:'ok', because only non-numeric input was rejected.

Neither route places an order — every broker-write entry point in
services/execution.py checks the kill switch independently, and those guards
are untouched here. The exposure was a durable write to persisted
live-trading configuration that would take effect the moment the switch were
flipped.

These tests pin the correction:
  * both routes refuse while the subsystem is disabled, using the established
    TRADING_SUBSYSTEM_DISABLED contract;
  * a blocked request mutates nothing — not memory, not the settings file;
  * when the subsystem is explicitly enabled in a controlled test, invalid
    input is rejected instead of silently ignored and reported as success.
"""
from __future__ import annotations

import asyncio
import json

import pytest
from fastapi import HTTPException

import main


class _Req:
    """Duck-types the one Request method the routes call."""

    def __init__(self, body):
        self._body = body

    async def json(self):
        return self._body


def _settings_snapshot(tmp_file):
    return json.loads(tmp_file.read_text(encoding='utf-8'))


@pytest.fixture
def settings_file(tmp_path, monkeypatch):
    """An isolated settings file, shaped like the real one."""
    payload = {
        'execution_mode': 'paper_validation',
        'execution_profiles': {
            'paper_validation': {'min_grade': 'A', 'max_trades_per_day': 3,
                                 'trade_cooldown_minutes': 20, 'kill_switch': False},
            'live_personal': {'min_grade': 'A', 'max_trades_per_day': 3,
                              'trade_cooldown_minutes': 20, 'kill_switch': False},
            'prop_firm': {'min_grade': 'A', 'max_trades_per_day': 2,
                          'trade_cooldown_minutes': 30, 'kill_switch': False},
        },
    }
    path = tmp_path / 'donna_settings.json'
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    monkeypatch.setattr(main, 'SETTINGS_FILE', path)
    monkeypatch.setattr(main, 'load_settings',
                        lambda: json.loads(path.read_text(encoding='utf-8')))
    return path


def _disable(monkeypatch):
    monkeypatch.setattr(main, 'NOVA_TRADING_SUBSYSTEM_ENABLED', False)


def _enable(monkeypatch):
    monkeypatch.setattr(main, 'NOVA_TRADING_SUBSYSTEM_ENABLED', True)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Both routes are blocked while the trading subsystem is disabled
# ═══════════════════════════════════════════════════════════════════════════

def test_execution_settings_blocked_when_subsystem_disabled(monkeypatch, settings_file):
    _disable(monkeypatch)
    result = asyncio.run(main.execution_settings_update(_Req({'execution_mode': 'prop_firm'})))
    assert result['status'] == 'TRADING_SUBSYSTEM_DISABLED'
    assert result['action'] == 'execution_settings_update'
    assert 'NOVA_TRADING_SUBSYSTEM_ENABLED is false' in result['reason']


def test_risk_engine_settings_blocked_when_subsystem_disabled(monkeypatch):
    _disable(monkeypatch)
    result = asyncio.run(main.risk_engine_settings(_Req({'account_size': 100.0, 'risk_pct': 1.0})))
    assert result['status'] == 'TRADING_SUBSYSTEM_DISABLED'
    assert result['action'] == 'risk_engine_settings'


# ═══════════════════════════════════════════════════════════════════════════
# 2. A blocked request cannot change the settings file
# ═══════════════════════════════════════════════════════════════════════════

def test_blocked_execution_settings_does_not_touch_the_file(monkeypatch, settings_file):
    _disable(monkeypatch)
    before = settings_file.read_bytes()

    def _explode(*a, **kw):
        raise AssertionError('write_json_file must not be reached while disabled')

    monkeypatch.setattr(main, 'write_json_file', _explode)
    asyncio.run(main.execution_settings_update(
        _Req({'execution_mode': 'live_personal', 'min_grade': 'C',
              'max_trades_per_day': 99, 'cooldown_minutes': 0})))
    assert settings_file.read_bytes() == before, 'settings file mutated while disabled'


def test_blocked_risk_engine_settings_does_not_reach_the_writer(monkeypatch):
    _disable(monkeypatch)

    def _explode(*a, **kw):
        raise AssertionError('update_re_settings must not be reached while disabled')

    monkeypatch.setattr(main, 'update_re_settings', _explode)
    asyncio.run(main.risk_engine_settings(_Req({'account_size': 999999, 'risk_pct': 99})))


# ═══════════════════════════════════════════════════════════════════════════
# 3. live_personal cannot be persisted while disabled
# ═══════════════════════════════════════════════════════════════════════════

def test_live_personal_cannot_be_persisted_while_disabled(monkeypatch, settings_file):
    """The exact request the audit landed live, against the live file."""
    _disable(monkeypatch)
    asyncio.run(main.execution_settings_update(
        _Req({'execution_mode': 'live_personal', 'min_grade': 'C',
              'max_trades_per_day': 99, 'cooldown_minutes': 0})))
    state = _settings_snapshot(settings_file)
    assert state['execution_mode'] == 'paper_validation'
    profile = state['execution_profiles']['paper_validation']
    assert profile['min_grade'] == 'A'
    assert profile['max_trades_per_day'] == 3
    assert profile['trade_cooldown_minutes'] == 20


# ═══════════════════════════════════════════════════════════════════════════
# 4. Numeric validation — negative, non-finite, malformed, out of range
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize('risk_pct', [-50, -0.001, 100.001, 1e9, float('nan'),
                                      float('inf'), float('-inf'), 'abc', None_ := object(),
                                      True, [1], {'a': 1}])
def test_risk_pct_rejected(monkeypatch, risk_pct):
    _enable(monkeypatch)

    def _explode(*a, **kw):
        raise AssertionError('update_re_settings reached with an invalid value')

    monkeypatch.setattr(main, 'update_re_settings', _explode)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.risk_engine_settings(_Req({'account_size': 1000, 'risk_pct': risk_pct})))
    assert exc.value.status_code == 400


@pytest.mark.parametrize('account_size', [0, -1, float('nan'), float('inf'), 'x', 2e9])
def test_account_size_rejected(monkeypatch, account_size):
    _enable(monkeypatch)
    monkeypatch.setattr(main, 'update_re_settings',
                        lambda **kw: (_ for _ in ()).throw(AssertionError('reached')))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.risk_engine_settings(_Req({'account_size': account_size, 'risk_pct': 1})))
    assert exc.value.status_code == 400


def test_valid_risk_values_still_accepted(monkeypatch):
    _enable(monkeypatch)
    seen = {}

    def _capture(**kw):
        seen.update(kw)
        return {'account_size': kw.get('account_size'), 'risk_pct': kw.get('risk_pct')}

    monkeypatch.setattr(main, 'update_re_settings', _capture)
    result = asyncio.run(main.risk_engine_settings(_Req({'account_size': 50000, 'risk_pct': 1.5})))
    assert result['status'] == 'ok'
    assert seen == {'account_size': 50000.0, 'risk_pct': 1.5}


@pytest.mark.parametrize('field,value', [
    ('max_trades_per_day', 0), ('max_trades_per_day', 51), ('max_trades_per_day', float('nan')),
    ('max_trades_per_day', 'many'), ('cooldown_minutes', -1), ('cooldown_minutes', 1441),
    ('cooldown_minutes', float('inf')),
])
def test_execution_numeric_fields_rejected(monkeypatch, settings_file, field, value):
    _enable(monkeypatch)
    monkeypatch.setattr(main, 'write_json_file',
                        lambda *a, **kw: (_ for _ in ()).throw(AssertionError('wrote')))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.execution_settings_update(_Req({field: value})))
    assert exc.value.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════
# 5. Invalid execution modes cannot return false success
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize('mode', ['NOT_A_MODE', '', 'live', 'LIVE_PERSONAL', 'paper_validation x'])
def test_invalid_execution_mode_is_rejected_not_silently_ignored(monkeypatch, settings_file, mode):
    """Previously an unrecognised mode was discarded and the route still
    answered status:'ok', so a caller could not tell the write was dropped."""
    _enable(monkeypatch)
    monkeypatch.setattr(main, 'write_json_file',
                        lambda *a, **kw: (_ for _ in ()).throw(AssertionError('wrote')))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.execution_settings_update(_Req({'execution_mode': mode})))
    assert exc.value.status_code == 400
    assert _settings_snapshot(settings_file)['execution_mode'] == 'paper_validation'


@pytest.mark.parametrize('grade', ['Z', 'A++', '', 'AA', 'B-'])
def test_invalid_min_grade_is_rejected(monkeypatch, settings_file, grade):
    _enable(monkeypatch)
    monkeypatch.setattr(main, 'write_json_file',
                        lambda *a, **kw: (_ for _ in ()).throw(AssertionError('wrote')))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.execution_settings_update(_Req({'min_grade': grade})))
    assert exc.value.status_code == 400


def test_min_grade_is_case_insensitive(monkeypatch, settings_file):
    """The route upper-cases before validating, so 'a+' is accepted as 'A+'.
    That is existing behaviour and is deliberately preserved."""
    _enable(monkeypatch)
    result = asyncio.run(main.execution_settings_update(_Req({'min_grade': 'a+'})))
    assert result['status'] == 'ok'
    assert result['profile']['min_grade'] == 'A+'


def test_unknown_fields_are_rejected(monkeypatch, settings_file):
    _enable(monkeypatch)
    monkeypatch.setattr(main, 'write_json_file',
                        lambda *a, **kw: (_ for _ in ()).throw(AssertionError('wrote')))
    for body in ({'kill_switch': False}, {'allowed_strategies': ['PROS']}, {'risk_tier': 'x'}):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(main.execution_settings_update(_Req(body)))
        assert exc.value.status_code == 400
    with pytest.raises(HTTPException):
        asyncio.run(main.risk_engine_settings(_Req({'account_size': 1, 'stop_trading': True})))


def test_enabled_valid_write_is_read_back_before_reporting_success(monkeypatch, settings_file):
    _enable(monkeypatch)
    real_write = main.write_json_file

    def _write(path, data):
        real_write(path, data)

    monkeypatch.setattr(main, 'write_json_file', _write)
    result = asyncio.run(main.execution_settings_update(
        _Req({'execution_mode': 'prop_firm', 'min_grade': 'B', 'max_trades_per_day': 2}))
    ) if 'prop_firm' in _settings_snapshot(settings_file)['execution_profiles'] else None
    if result is None:
        pytest.skip('fixture has no prop_firm profile')
    assert result['status'] == 'ok'
    assert _settings_snapshot(settings_file)['execution_mode'] == 'prop_firm'


def test_success_is_withheld_when_the_write_does_not_persist(monkeypatch, settings_file):
    """A write that silently fails must not be announced as ok."""
    _enable(monkeypatch)
    monkeypatch.setattr(main, 'write_json_file', lambda *a, **kw: None)   # no-op write
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.execution_settings_update(_Req({'execution_mode': 'live_personal'})))
    assert exc.value.status_code == 500


# ═══════════════════════════════════════════════════════════════════════════
# 6. No broker-write route becomes reachable
# ═══════════════════════════════════════════════════════════════════════════

def test_no_broker_write_route_is_exposed_by_settings():
    """Settings must not reference any execution or broker route."""
    from ui.pages.settings import SETTINGS_HTML
    import ui.scripts
    surface = SETTINGS_HTML + ui.scripts.DASHBOARD_SCRIPT
    for route in ('/execution/settings', '/risk-engine/settings', '/execution/close',
                  '/execution/close-all', '/execution/cancel-orders', '/close-all',
                  '/execution/trade-permission', '/execution/macro-lock'):
        assert route not in SETTINGS_HTML, f'{route} referenced in Settings markup'
    assert 'execution_mode' not in SETTINGS_HTML
    assert 'live_personal' not in surface


def test_execution_module_kill_switch_guards_are_untouched():
    """The correction must not weaken any broker-write guard."""
    import inspect
    import services.execution as ex
    src = inspect.getsource(ex)
    assert src.count('if not NOVA_TRADING_SUBSYSTEM_ENABLED:') >= 6
    assert "'status': 'TRADING_SUBSYSTEM_DISABLED'" in src


# ═══════════════════════════════════════════════════════════════════════════
# 7. Existing close-all / kill-switch behaviour remains intact
# ═══════════════════════════════════════════════════════════════════════════

def test_close_all_still_refuses_while_disabled(monkeypatch):
    _disable(monkeypatch)
    result = asyncio.run(main.close_all_eod_manual())
    assert result['status'] == 'TRADING_SUBSYSTEM_DISABLED'


def test_disabled_settings_route_does_not_enable_execution(monkeypatch, settings_file):
    """Even a blocked configuration call leaves the execution guard untouched."""
    _disable(monkeypatch)
    asyncio.run(main.execution_settings_update(_Req({'execution_mode': 'live_personal'})))
    assert main.NOVA_TRADING_SUBSYSTEM_ENABLED is False
    result = asyncio.run(main.close_all_eod_manual())
    assert result['status'] == 'TRADING_SUBSYSTEM_DISABLED'
