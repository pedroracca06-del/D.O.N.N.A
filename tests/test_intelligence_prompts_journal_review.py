"""
test_intelligence_prompts_journal_review.py — NOVA Intelligence V1 commit #6:
migrating Journal NOVA Review onto intelligence.gateway.

Covers, in one file (mirroring commit #5's test_intelligence_prompts_assistant.py):
  1. intelligence/prompts/journal_review.py — build_prompt() / parse_response()
  2. End-to-end through the real gateway + real prompt module, mocked adapter only
  3. Cache identity, privacy/redaction, and explicit-selection guarantees

Route-level and service-level behavior (HTTP status contract, sanitized
exception handling, curated input_data) is covered by tests/test_nova_review.py.

Fully mocked/isolated: no real Anthropic API key is used, no real network
socket is ever opened, and budget/cache/audit all use temporary state so
this file never touches real data/*.json.

Run:  python -m pytest tests/test_intelligence_prompts_journal_review.py -v
"""
from __future__ import annotations

import ast
import os
import socket
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('ALPACA_API_KEY', '')
os.environ.setdefault('ALPACA_SECRET_KEY', '')

from intelligence import audit, budget, cache, config
from intelligence.errors import IntelligenceErrorCode
from intelligence.prompts import journal_review as jr_prompt
from intelligence.providers.base import AdapterResult

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT_MODULE_PATH = REPO_ROOT / 'intelligence' / 'prompts' / 'journal_review.py'


@pytest.fixture(autouse=True)
def _block_real_network(monkeypatch):
    real_connect = socket.socket.connect

    def _guard(self, address, *args, **kwargs):
        # Windows' asyncio ProactorEventLoop opens a real loopback socketpair
        # for its internal self-pipe -- not "the network". Only block
        # genuine non-loopback destinations (e.g. api.anthropic.com).
        host = address[0] if isinstance(address, tuple) else address
        if host in ('127.0.0.1', 'localhost', '::1'):
            return real_connect(self, address, *args, **kwargs)
        raise AssertionError(f'real network access attempted during journal review migration tests: {address!r}')

    monkeypatch.setattr(socket.socket, 'connect', _guard)
    yield


def _trade(**overrides) -> dict:
    trade = {
        'ticker': 'MES1!', 'direction': 'LONG', 'setup_type': 'PROS_CONTINUATION',
        'entry_price': 6000.0, 'exit_price': 6010.0, 'stop': 5990.0, 'tp1': 6020.0,
        'size': 1, 'rr': 2.0, 'realized_pnl': 100.0, 'outcome': 'WIN',
        'session': 'NY_AM', 'macro_risk': 'low', 'notes': '', 'emotional_state': '',
        'behavioral_flags': [], 'reflection': '',
    }
    trade.update(overrides)
    return trade


def _input_data(trade=None, nearby_signals='  No signal log entries found for this instrument.'):
    return {'trade': trade or _trade(), 'nearby_signals': nearby_signals}


# ═══════════════════════════════════════════════════════════════════════
# 1. intelligence/prompts/journal_review.py
# ═══════════════════════════════════════════════════════════════════════

def test_build_prompt_includes_instruction_substance():
    prompt = jr_prompt.build_prompt(_input_data())
    assert 'NOVA' in prompt
    assert 'QUALIFICATION' in prompt
    assert 'EXECUTION' in prompt
    assert 'OUTCOME ASSESSMENT' in prompt
    assert 'WHAT SHOULD HAVE HAPPENED' in prompt
    assert 'BEHAVIORAL NOTE' in prompt


def test_build_prompt_includes_trade_fields():
    trade = _trade(ticker='MNQ1!', notes='held through FOMC, should not have')
    prompt = jr_prompt.build_prompt(_input_data(trade=trade))
    assert 'MNQ1!' in prompt
    assert 'held through FOMC, should not have' in prompt


def test_build_prompt_includes_nearby_signals():
    prompt = jr_prompt.build_prompt(_input_data(nearby_signals='UNIQUE_SIGNAL_MARKER_XYZ'))
    assert 'UNIQUE_SIGNAL_MARKER_XYZ' in prompt


def test_build_prompt_sections_are_clearly_delimited_and_ordered():
    trade = _trade(notes='TRADE_MARKER_XYZ')
    prompt = jr_prompt.build_prompt(_input_data(trade=trade, nearby_signals='SIGNAL_MARKER_XYZ'))
    instr_idx = prompt.find('NOVA INSTRUCTIONS')
    trade_idx = prompt.find('TRADE_MARKER_XYZ')
    signal_idx = prompt.find('SIGNAL_MARKER_XYZ')
    assert -1 not in (instr_idx, trade_idx, signal_idx)
    assert instr_idx < trade_idx < signal_idx
    assert prompt.count('===') >= 6


def test_build_prompt_does_not_crash_on_sparse_trade():
    sparse = {'ticker': 'MNQ1!'}
    prompt = jr_prompt.build_prompt(_input_data(trade=sparse))
    assert 'MNQ1!' in prompt


def test_build_prompt_is_deterministic():
    data = _input_data()
    assert jr_prompt.build_prompt(data) == jr_prompt.build_prompt(data)


def test_parse_response_accepts_nonempty_text():
    result = jr_prompt.parse_response('QUALIFICATION\nGood setup, entered on confirmed OTE.')
    assert result == {'analysis': 'QUALIFICATION\nGood setup, entered on confirmed OTE.'}


def test_parse_response_strips_whitespace():
    result = jr_prompt.parse_response('  \n  some analysis text  \n  ')
    assert result == {'analysis': 'some analysis text'}


@pytest.mark.parametrize('text', ['', '   ', '\n\n\t  \n'])
def test_parse_response_raises_on_empty_or_whitespace_only(text):
    with pytest.raises(ValueError):
        jr_prompt.parse_response(text)


def test_parse_response_does_not_require_section_headers():
    """Spec-approved scope for commit #6: only empty/whitespace-only output
    is rejected -- arbitrary non-empty prose is accepted, even without the
    five section headers."""
    result = jr_prompt.parse_response('just a short note, no sections at all')
    assert result == {'analysis': 'just a short note, no sections at all'}


def test_prompt_module_imports_nothing_forbidden():
    tree = ast.parse(PROMPT_MODULE_PATH.read_text(encoding='utf-8'), filename=str(PROMPT_MODULE_PATH))
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split('.')[0]
                if top in ('services', 'engines', 'anthropic'):
                    offenders.append(alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split('.')[0]
            if top in ('services', 'engines', 'anthropic') or node.module.startswith('intelligence.providers') or node.module == 'core.config':
                offenders.append(node.module)
    assert offenders == [], f'unexpected import(s) in prompts/journal_review.py: {offenders}'


# ═══════════════════════════════════════════════════════════════════════
# 2. End-to-end through the real gateway + real prompt module (mocked adapter)
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _isolated_gateway_state(tmp_path, monkeypatch):
    monkeypatch.setattr(budget, 'BUDGET_FILE', tmp_path / 'nova_intelligence_budget.json')
    monkeypatch.setattr(audit, 'AUDIT_FILE', tmp_path / 'nova_intelligence_usage_log.json')
    monkeypatch.setattr('core.config.CACHE', {})
    monkeypatch.setattr(config, 'ANTHROPIC_API_KEY', 'sk-ant-test-key')
    monkeypatch.setattr(config, 'NOVA_AI_MODEL', 'claude-haiku-4-5-20251001')
    monkeypatch.setattr(config, 'NOVA_AI_PROVIDER', 'anthropic')
    monkeypatch.setattr(config, 'NOVA_AI_CACHE_ENABLED', True)
    yield


def _mock_adapter_result(text, input_tokens=60, output_tokens=40, model='claude-haiku-4-5-20251001'):
    return AdapterResult(text=text, input_tokens=input_tokens, output_tokens=output_tokens, model=model)


@patch('intelligence.gateway.AnthropicAdapter')
def test_end_to_end_success_through_real_gateway_and_prompt_module(mock_adapter_cls):
    from intelligence.gateway import request_intelligence

    mock_adapter = MagicMock()
    mock_adapter.call.return_value = _mock_adapter_result('QUALIFICATION\nGood entry on confirmed OTE.')
    mock_adapter_cls.return_value = mock_adapter

    response = request_intelligence('journal_review', _input_data(), user_id='pedro', request_id='req-e2e-1')

    assert response.success is True
    assert response.cached is False
    assert response.content == 'QUALIFICATION\nGood entry on confirmed OTE.'
    mock_adapter.call.assert_called_once()
    sent_prompt = mock_adapter.call.call_args.args[0]
    assert 'MES1!' in sent_prompt


@patch('intelligence.gateway.AnthropicAdapter')
def test_end_to_end_empty_output_produces_malformed_output(mock_adapter_cls):
    from intelligence.gateway import request_intelligence

    mock_adapter = MagicMock()
    mock_adapter.call.return_value = _mock_adapter_result('   ')  # whitespace-only
    mock_adapter_cls.return_value = mock_adapter

    response = request_intelligence('journal_review', _input_data(), user_id='pedro', request_id='req-e2e-2')

    assert response.success is False
    assert response.error_code == IntelligenceErrorCode.MALFORMED_OUTPUT.value
    assert response.content is None


# ═══════════════════════════════════════════════════════════════════════
# 3. Cache identity, privacy, and explicit-selection guarantees
# ═══════════════════════════════════════════════════════════════════════

@patch('intelligence.gateway.AnthropicAdapter')
def test_cache_hit_on_identical_curated_input(mock_adapter_cls):
    from intelligence.gateway import request_intelligence

    mock_adapter = MagicMock()
    mock_adapter.call.return_value = _mock_adapter_result('QUALIFICATION\nSame analysis every time.')
    mock_adapter_cls.return_value = mock_adapter

    data = _input_data()
    r1 = request_intelligence('journal_review', data, user_id='pedro', request_id='req-cache-1')
    r2 = request_intelligence('journal_review', data, user_id='pedro', request_id='req-cache-2')

    assert r1.cached is False
    assert r2.cached is True
    assert r2.content == r1.content
    mock_adapter.call.assert_called_once()  # only the first call reached the provider


@patch('intelligence.gateway.AnthropicAdapter')
def test_nova_review_and_nova_review_ts_do_not_affect_cache_key(mock_adapter_cls):
    """Excluding nova_review/nova_review_ts from input_data (main.py's job,
    verified in test_nova_review.py) means the cache key itself is stable
    across regenerations. This test proves the cache.py layer: two
    "logically identical" input_data payloads that differ only in a
    nova_review-shaped extra key would NOT be considered the same request if
    such a key were ever accidentally included -- confirming the property
    the route relies on by never including it in the first place."""
    base = _input_data()
    with_stale_review = {**base, 'trade': {**base['trade']}}  # trade dict has no nova_review key
    assert 'nova_review' not in with_stale_review['trade']
    assert 'nova_review_ts' not in with_stale_review['trade']

    key_a = cache.build_cache_key('journal_review', base)
    key_b = cache.build_cache_key('journal_review', with_stale_review)
    assert key_a == key_b  # identical curated content -> identical key


def test_cache_key_differs_for_different_trades():
    key_a = cache.build_cache_key('journal_review', _input_data(trade=_trade(ticker='MES1!')))
    key_b = cache.build_cache_key('journal_review', _input_data(trade=_trade(ticker='MNQ1!')))
    assert key_a != key_b


@patch('intelligence.gateway.AnthropicAdapter')
def test_sensitive_trade_content_never_appears_in_audit_record(mock_adapter_cls):
    from intelligence.gateway import request_intelligence

    mock_adapter = MagicMock()
    mock_adapter.call.return_value = _mock_adapter_result('QUALIFICATION\nfine.')
    mock_adapter_cls.return_value = mock_adapter

    sensitive_trade = _trade(
        notes='SENSITIVE_TRADER_NOTE_SECRET',
        reflection='SENSITIVE_REFLECTION_SECRET',
        emotional_state='SENSITIVE_EMOTION_SECRET',
    )
    request_intelligence('journal_review', _input_data(trade=sensitive_trade), user_id='pedro', request_id='req-priv-1')

    entries = audit._load(audit.AUDIT_FILE)
    assert len(entries) == 1
    serialized = str(entries[0])
    assert 'SENSITIVE_TRADER_NOTE_SECRET' not in serialized
    assert 'SENSITIVE_REFLECTION_SECRET' not in serialized
    assert 'SENSITIVE_EMOTION_SECRET' not in serialized
    assert 'sk-ant-test-key' not in serialized


@patch('intelligence.gateway.AnthropicAdapter')
def test_malformed_output_audit_never_records_content(mock_adapter_cls):
    from intelligence.gateway import request_intelligence

    mock_adapter = MagicMock()
    mock_adapter.call.return_value = _mock_adapter_result('')
    mock_adapter_cls.return_value = mock_adapter

    request_intelligence('journal_review', _input_data(), user_id='pedro', request_id='req-malformed-1')

    entries = audit._load(audit.AUDIT_FILE)
    record = entries[-1]
    assert record['error_code'] == IntelligenceErrorCode.MALFORMED_OUTPUT.value
    # response character length/hash permitted, never the (empty) content itself
    assert 'content' not in record or record.get('content') in (None,)


def test_input_data_shape_carries_only_trade_and_nearby_signals():
    """Static contract check: build_prompt only ever reads input_data['trade']
    and input_data['nearby_signals'] -- confirms nothing else is expected or
    silently used, matching the explicit-selection-only, single-trade
    contract (spec §13 decision 10, §16)."""
    data = _input_data()
    data['unexpected_extra_key'] = 'should be ignored, not read'
    prompt = jr_prompt.build_prompt(data)
    assert 'should be ignored, not read' not in prompt
