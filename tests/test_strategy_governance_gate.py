"""
test_strategy_governance_gate.py — regression test for the strategy/
instrument governance gate added after the ICT_OB_FVG_ENTRY incident.

Background: donna_settings.json has always correctly restricted every
execution profile to allowed_strategies=["PROS","ORB"], and
services/execution_bridge.py's 13-gate chain would have rejected an ICT
signal. But that chain is only ever invoked by monitor.py running locally.
The public /webhook (main.py) called process_signal() -> execute_signal()
directly, with no strategy or instrument check at all -- so a live
ICT_OB_FVG_ENTRY alert from the TradingView indicator executed two real
paper trades, and a fabricated setup_type (PHASE1A_VALIDATION_TEST, used
earlier this session to validate the close-sync path) executed too.

check_strategy_and_instrument_allowed() is now the single check both the
webhook (main.py) and execute_signal() (services/execution.py) call against
the exact same donna_settings.json profile -- no broker-reaching path can
configure or bypass its way around it independently.

Run:  python -m pytest tests/test_strategy_governance_gate.py -v
      (or: python tests/test_strategy_governance_gate.py)
"""
from __future__ import annotations

import os
import sys

# Alpaca must stay unconfigured for plain imports of services.execution:
# it runs a one-time live "QQQ cleanup on load" call at module scope.
# Telegram must stay unconfigured too: log_governance_rejection() sends a
# real notification on every rejection it logs, and this file deliberately
# triggers that path.
os.environ['ALPACA_API_KEY']    = ''
os.environ['ALPACA_SECRET_KEY'] = ''
os.environ['TELEGRAM_BOT_TOKEN'] = ''
os.environ['TELEGRAM_CHAT_ID']   = ''

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import services.execution as ex


def _profile(allowed_strategies=('PROS', 'ORB'), allowed_instruments=('MNQ', 'MES')):
    return {
        'allowed_strategies':  list(allowed_strategies),
        'allowed_instruments': list(allowed_instruments),
    }


def test_ict_ob_fvg_entry_is_rejected(monkeypatch):
    """The actual incident: ICT_OB_FVG_ENTRY -> strategy_family 'ICT'."""
    monkeypatch.setattr(ex, '_active_execution_profile', lambda: _profile())
    gate = ex.check_strategy_and_instrument_allowed('ICT', 'MNQ')
    assert gate['allowed'] is False
    assert gate['code'] == 'STRATEGY_NOT_ALLOWED'


def test_phase1a_validation_test_fabricated_setup_is_rejected(monkeypatch):
    """The fabricated setup_type used to validate Phase 1A's close-sync path
    also went straight through -- normalize_payload() maps anything it
    doesn't recognize to strategy_family 'UNKNOWN'."""
    monkeypatch.setattr(ex, '_active_execution_profile', lambda: _profile())
    gate = ex.check_strategy_and_instrument_allowed('UNKNOWN', 'ES')
    assert gate['allowed'] is False
    assert gate['code'] == 'STRATEGY_NOT_ALLOWED'


def test_pros_is_allowed_when_configured(monkeypatch):
    monkeypatch.setattr(ex, '_active_execution_profile', lambda: _profile())
    gate = ex.check_strategy_and_instrument_allowed('PROS', 'MNQ')
    assert gate['allowed'] is True


def test_orb_is_allowed_when_configured(monkeypatch):
    monkeypatch.setattr(ex, '_active_execution_profile', lambda: _profile())
    gate = ex.check_strategy_and_instrument_allowed('ORB', 'MES')
    assert gate['allowed'] is True


def test_disallowed_instrument_is_rejected_even_for_an_allowed_strategy(monkeypatch):
    """ES/SPY isn't literally 'MES' -- every profile's allowed_instruments
    is ['MNQ','MES'], so even a PROS signal on ES must be rejected here."""
    monkeypatch.setattr(ex, '_active_execution_profile', lambda: _profile())
    gate = ex.check_strategy_and_instrument_allowed('PROS', 'ES')
    assert gate['allowed'] is False
    assert gate['code'] == 'INSTRUMENT_NOT_ALLOWED'


def test_all_six_legacy_strategy_strings_are_rejected_by_default(monkeypatch):
    """Requirement: ICT_ELITE, ICT_SMT_CONFIRMATION, ICT_OB_FVG_ENTRY,
    ICT_LIQUIDITY_SWEEP, FAILED_AUCTION, MOMENTUM_CONTINUATION must never
    reach Alpaca unless explicitly added to allowed_strategies. All six map
    to a strategy_family outside the default ['PROS','ORB'] allowlist."""
    monkeypatch.setattr(ex, '_active_execution_profile', lambda: _profile())
    legacy_families = ['ICT', 'ICT', 'ICT', 'ICT', 'FAILED_AUCTION', 'MOMENTUM']
    for family in legacy_families:
        gate = ex.check_strategy_and_instrument_allowed(family, 'MNQ')
        assert gate['allowed'] is False, f'{family} should be rejected by default'
        assert gate['code'] == 'STRATEGY_NOT_ALLOWED'


def test_strategy_becomes_allowed_once_explicitly_added_to_profile(monkeypatch):
    """The allowlist is live config, not a hardcoded blocklist -- adding ICT
    to allowed_strategies must let it through, proving this isn't special-
    cased against ICT specifically."""
    monkeypatch.setattr(ex, '_active_execution_profile',
                         lambda: _profile(allowed_strategies=('PROS', 'ORB', 'ICT')))
    gate = ex.check_strategy_and_instrument_allowed('ICT', 'MNQ')
    assert gate['allowed'] is True


def test_no_active_profile_falls_back_to_safe_default_not_fail_open(monkeypatch):
    """If execution_mode is 'disabled' or no profile resolves, the gate falls
    back to the same restrictive default (['PROS','ORB'] / ['MNQ','MES']) --
    it must never fail open and allow an arbitrary strategy through just
    because settings.json is missing or disabled."""
    monkeypatch.setattr(ex, '_active_execution_profile', lambda: {})
    gate = ex.check_strategy_and_instrument_allowed('PROS', 'MNQ')
    assert gate['allowed'] is True  # safe default still permits PROS/MNQ
    gate2 = ex.check_strategy_and_instrument_allowed('ICT', 'MNQ')
    assert gate2['allowed'] is False
    assert gate2['code'] == 'STRATEGY_NOT_ALLOWED'


def test_execute_signal_rejects_ict_before_reaching_alpaca(monkeypatch):
    """
    End-to-end: execute_signal() itself -- not just the standalone gate
    function -- must reject an ICT_OB_FVG_ENTRY signal_result before any
    Alpaca call. Patches _client() to explode if ever called, proving the
    broker is never touched.
    """
    def _explode():
        raise AssertionError('Alpaca client must never be constructed for a rejected strategy')

    monkeypatch.setattr(ex, '_client', _explode)
    monkeypatch.setattr(ex, '_active_execution_profile', lambda: _profile())
    monkeypatch.setattr(ex._state, 'can_execute', lambda: True)

    signal_result = {
        'data': {
            'ticker': 'MNQ1!', 'instrument': 'MNQ', 'signal': 'LONG',
            'setup_type': 'ICT_OB_FVG_ENTRY', 'strategy_family': 'ICT',
            'signal_id': 'test-ict-signal-1',
        },
        'parsed': {'verdict': 'TAKE', 'confidence': '85.0%'},
    }

    result = ex.execute_signal(signal_result)

    assert result['status'] == 'skipped'
    assert result['code'] == 'STRATEGY_NOT_ALLOWED'


if __name__ == '__main__':
    import inspect

    class _MiniMonkeypatch:
        def __init__(self):
            self._undo = []
        def setattr(self, obj, name, value):
            self._undo.append((obj, name, getattr(obj, name)))
            setattr(obj, name, value)
        def undo(self):
            for obj, name, value in reversed(self._undo):
                setattr(obj, name, value)

    tests = [v for k, v in list(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        mp = _MiniMonkeypatch() if 'monkeypatch' in inspect.signature(t).parameters else None
        try:
            t(mp) if mp else t()
            print(f'PASS  {t.__name__}')
        except AssertionError as e:
            failed += 1
            print(f'FAIL  {t.__name__}: {e}')
        finally:
            if mp:
                mp.undo()
    print(f'\n{len(tests) - failed}/{len(tests)} passed')
    sys.exit(1 if failed else 0)
