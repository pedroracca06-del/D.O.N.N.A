"""
test_intelligence_gateway.py — NOVA Intelligence V1 commit #4: intelligence/gateway.py orchestration.

Fully mocked: the Anthropic adapter is patched at the class gateway.py
imports, and every feature's prompt_module is patched via gateway.py's own
import_module name (registry.py's prompt_module strings point at modules
that do not exist until commits #5-#7). Budget/cache/audit all use temporary
state, isolated from real runtime files and the shared in-memory CACHE dict.

Run:  python -m pytest tests/test_intelligence_gateway.py -v
"""
from __future__ import annotations

import os
import socket
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intelligence import audit, budget, cache, config, gateway
from intelligence.errors import IntelligenceErrorCode
from intelligence.providers.base import AdapterResult, ProviderError

GATEWAY_MODULE = 'intelligence.gateway'


# ── Isolation: temp budget/audit files, fresh cache dict, no real network ──
@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(budget, 'BUDGET_FILE', tmp_path / 'nova_intelligence_budget.json')
    monkeypatch.setattr(audit, 'AUDIT_FILE', tmp_path / 'nova_intelligence_usage_log.json')
    monkeypatch.setattr('core.config.CACHE', {})
    monkeypatch.setattr(gateway, '_circuit_state', {})
    monkeypatch.setattr(config, 'ANTHROPIC_API_KEY', 'sk-ant-test-key')
    monkeypatch.setattr(config, 'NOVA_AI_MODEL', 'claude-haiku-4-5-20251001')
    monkeypatch.setattr(config, 'NOVA_AI_PROVIDER', 'anthropic')
    monkeypatch.setattr(config, 'NOVA_AI_CACHE_ENABLED', True)
    yield


@pytest.fixture(autouse=True)
def _block_real_network(monkeypatch):
    def _guard(*_a, **_kw):
        raise AssertionError('real network access attempted during intelligence gateway tests')
    monkeypatch.setattr(socket.socket, 'connect', _guard)
    yield


def _fake_prompt_module(build_prompt=None, parse_response=None):
    return SimpleNamespace(
        build_prompt=build_prompt or (lambda input_data: 'a built prompt'),
        parse_response=parse_response,
    )


def _patch_prompt_module(monkeypatch, module_obj):
    def _fake_import(name):
        return module_obj
    monkeypatch.setattr(f'{GATEWAY_MODULE}.import_module', _fake_import)


def _adapter_result(text='ok', input_tokens=10, output_tokens=5, model='claude-haiku-4-5-20251001'):
    return AdapterResult(text=text, input_tokens=input_tokens, output_tokens=output_tokens, model=model)


# ── Unknown feature: no side effects at all ─────────────────────────────────
def test_unknown_feature_raises_before_any_side_effect(monkeypatch):
    calls = []
    monkeypatch.setattr(f'{GATEWAY_MODULE}.import_module', lambda name: calls.append(('import', name)))
    monkeypatch.setattr(cache, 'get_cached_response', lambda *a, **kw: calls.append('cache'))
    monkeypatch.setattr(budget, 'reserve', lambda **kw: calls.append('budget'))
    monkeypatch.setattr(audit, 'write_record', lambda *a, **kw: calls.append('audit'))

    with pytest.raises(ValueError):
        gateway.request_intelligence('not_a_real_feature', {}, 'pedro', 'req_1')

    assert calls == []


# ── Provider not configured: checked before cache, no calls anywhere ───────
def test_missing_api_key_returns_provider_not_configured_before_cache(monkeypatch):
    monkeypatch.setattr(config, 'ANTHROPIC_API_KEY', '')
    monkeypatch.setattr(cache, 'get_cached_response', MagicMock(side_effect=AssertionError('cache should not be consulted')))

    response = gateway.request_intelligence('journal_review', {'trade_id': 1}, 'pedro', 'req_1')

    assert response.success is False
    assert response.error_code == IntelligenceErrorCode.PROVIDER_NOT_CONFIGURED.value
    assert response.cached is False


# ── Full success path ───────────────────────────────────────────────────────
@patch(f'{GATEWAY_MODULE}.AnthropicAdapter')
def test_full_success_path_returns_envelope_and_writes_cache_and_audit(mock_adapter_cls, monkeypatch):
    mock_adapter = MagicMock()
    mock_adapter.call.return_value = _adapter_result(text='hello', input_tokens=20, output_tokens=8)
    mock_adapter_cls.return_value = mock_adapter
    _patch_prompt_module(monkeypatch, _fake_prompt_module())

    response = gateway.request_intelligence('journal_review', {'trade_id': 42}, 'pedro', 'req_1')

    assert response.success is True
    assert response.cached is False
    assert response.content == 'hello'
    assert response.usage.input_tokens == 20
    assert response.usage.output_tokens == 8
    assert response.usage.estimated_cost_usd > 0
    mock_adapter.call.assert_called_once()

    # Second identical call now hits the cache -- zero further adapter calls.
    response2 = gateway.request_intelligence('journal_review', {'trade_id': 42}, 'pedro', 'req_2')
    assert response2.cached is True
    assert response2.success is True
    assert response2.usage.estimated_cost_usd == 0.0
    assert response2.usage.input_tokens == 20
    mock_adapter.call.assert_called_once()  # still just the one real call


# ── Cache hit bypasses circuit breaker, budget, prompt loading, provider ───
@patch(f'{GATEWAY_MODULE}.AnthropicAdapter')
def test_cache_hit_bypasses_everything(mock_adapter_cls, monkeypatch):
    mock_adapter = MagicMock()
    mock_adapter.call.return_value = _adapter_result()
    mock_adapter_cls.return_value = mock_adapter
    _patch_prompt_module(monkeypatch, _fake_prompt_module())

    gateway.request_intelligence('journal_review', {'x': 1}, 'pedro', 'req_1')
    mock_adapter.call.assert_called_once()

    # Trip the circuit breaker open for this feature.
    for _ in range(3):
        gateway._record_circuit_failure('journal_review')
    assert gateway._circuit_is_open('journal_review')

    import_calls = []
    monkeypatch.setattr(f'{GATEWAY_MODULE}.import_module', lambda name: import_calls.append(name) or (_ for _ in ()).throw(AssertionError))

    response = gateway.request_intelligence('journal_review', {'x': 1}, 'pedro', 'req_2')

    assert response.cached is True
    assert response.success is True
    mock_adapter.call.assert_called_once()  # no new provider call
    assert import_calls == []  # prompt module never touched on a cache hit
    state = budget._read_state(budget.BUDGET_FILE)
    assert state.request_count == 1  # unchanged since the first (real) call
    assert state.reserved_count == 0


# ── Assistant is never cached ───────────────────────────────────────────────
@patch(f'{GATEWAY_MODULE}.AnthropicAdapter')
def test_assistant_feature_is_never_cached(mock_adapter_cls, monkeypatch):
    mock_adapter = MagicMock()
    mock_adapter.call.return_value = _adapter_result()
    mock_adapter_cls.return_value = mock_adapter
    _patch_prompt_module(monkeypatch, _fake_prompt_module())

    gateway.request_intelligence('assistant', {'q': 'hi'}, 'pedro', 'req_1')
    gateway.request_intelligence('assistant', {'q': 'hi'}, 'pedro', 'req_2')

    assert mock_adapter.call.call_count == 2  # never served from cache


# ── Circuit breaker: opens after 3 consecutive failures, blocks the 4th ────
@patch(f'{GATEWAY_MODULE}.AnthropicAdapter')
def test_circuit_breaker_opens_after_three_failures(mock_adapter_cls, monkeypatch):
    mock_adapter = MagicMock()
    mock_adapter.call.side_effect = ProviderError(IntelligenceErrorCode.AUTH_FAILED, False)
    mock_adapter_cls.return_value = mock_adapter
    _patch_prompt_module(monkeypatch, _fake_prompt_module())

    for i in range(3):
        response = gateway.request_intelligence('market_summary', {'n': i}, 'pedro', f'req_{i}')
        assert response.error_code == IntelligenceErrorCode.AUTH_FAILED.value

    response = gateway.request_intelligence('market_summary', {'n': 99}, 'pedro', 'req_open')
    assert response.error_code == IntelligenceErrorCode.CIRCUIT_OPEN.value
    assert mock_adapter.call.call_count == 3  # the 4th request never reached the provider


# ── Retry: retryable TIMEOUT gets exactly one retry ─────────────────────────
@patch(f'{GATEWAY_MODULE}.AnthropicAdapter')
def test_retryable_timeout_retries_exactly_once_then_succeeds(mock_adapter_cls, monkeypatch):
    mock_adapter = MagicMock()
    mock_adapter.call.side_effect = [
        ProviderError(IntelligenceErrorCode.TIMEOUT, True),
        _adapter_result(text='recovered', input_tokens=5, output_tokens=5),
    ]
    mock_adapter_cls.return_value = mock_adapter
    _patch_prompt_module(monkeypatch, _fake_prompt_module())

    response = gateway.request_intelligence('market_summary', {'n': 1}, 'pedro', 'req_1')

    assert response.success is True
    assert response.content == 'recovered'
    assert mock_adapter.call.call_count == 2


# ── Retry: retryable connection/5xx-style failure gets one retry, still fails ─
@patch(f'{GATEWAY_MODULE}.AnthropicAdapter')
def test_retryable_failure_exhausted_after_one_retry(mock_adapter_cls, monkeypatch):
    mock_adapter = MagicMock()
    mock_adapter.call.side_effect = [
        ProviderError(IntelligenceErrorCode.INVALID_PROVIDER_RESPONSE, True),
        ProviderError(IntelligenceErrorCode.INVALID_PROVIDER_RESPONSE, True),
    ]
    mock_adapter_cls.return_value = mock_adapter
    _patch_prompt_module(monkeypatch, _fake_prompt_module())

    response = gateway.request_intelligence('market_summary', {'n': 1}, 'pedro', 'req_1')

    assert response.success is False
    assert response.error_code == IntelligenceErrorCode.INVALID_PROVIDER_RESPONSE.value
    assert mock_adapter.call.call_count == 2


# ── Non-retryable: never retried, exactly one attempt each ─────────────────
@pytest.mark.parametrize('code', [
    IntelligenceErrorCode.AUTH_FAILED,
    IntelligenceErrorCode.INSUFFICIENT_CREDITS,
    IntelligenceErrorCode.RATE_LIMITED,
    IntelligenceErrorCode.PROVIDER_NOT_CONFIGURED,
])
@patch(f'{GATEWAY_MODULE}.AnthropicAdapter')
def test_non_retryable_errors_are_never_retried(mock_adapter_cls, monkeypatch, code):
    mock_adapter = MagicMock()
    mock_adapter.call.side_effect = ProviderError(code, False)
    mock_adapter_cls.return_value = mock_adapter
    _patch_prompt_module(monkeypatch, _fake_prompt_module())

    response = gateway.request_intelligence('market_summary', {'n': 1}, 'pedro', 'req_1')

    assert response.success is False
    assert response.error_code == code.value
    assert mock_adapter.call.call_count == 1


# ── Non-retryable 404-style permanent INVALID_PROVIDER_RESPONSE ────────────
@patch(f'{GATEWAY_MODULE}.AnthropicAdapter')
def test_permanent_invalid_provider_response_not_retried(mock_adapter_cls, monkeypatch):
    mock_adapter = MagicMock()
    mock_adapter.call.side_effect = ProviderError(IntelligenceErrorCode.INVALID_PROVIDER_RESPONSE, False)
    mock_adapter_cls.return_value = mock_adapter
    _patch_prompt_module(monkeypatch, _fake_prompt_module())

    response = gateway.request_intelligence('market_summary', {'n': 1}, 'pedro', 'req_1')

    assert response.error_code == IntelligenceErrorCode.INVALID_PROVIDER_RESPONSE.value
    assert mock_adapter.call.call_count == 1


# ── Model not supported: zero provider calls, no reservation left behind ──
@patch(f'{GATEWAY_MODULE}.AnthropicAdapter')
def test_model_not_supported_makes_no_provider_call(mock_adapter_cls, monkeypatch):
    monkeypatch.setattr(config, 'NOVA_AI_MODEL', 'not-a-real-model')
    mock_adapter = MagicMock()
    mock_adapter_cls.return_value = mock_adapter
    _patch_prompt_module(monkeypatch, _fake_prompt_module())

    response = gateway.request_intelligence('market_summary', {'n': 1}, 'pedro', 'req_1')

    assert response.error_code == IntelligenceErrorCode.MODEL_NOT_SUPPORTED.value
    mock_adapter.call.assert_not_called()
    assert not budget.BUDGET_FILE.exists()


# ── Malformed output: correct envelope, never cached ────────────────────────
@patch(f'{GATEWAY_MODULE}.AnthropicAdapter')
def test_malformed_output_not_cached(mock_adapter_cls, monkeypatch):
    mock_adapter = MagicMock()
    mock_adapter.call.return_value = _adapter_result(text='not json')
    mock_adapter_cls.return_value = mock_adapter

    def _bad_parse(text):
        raise ValueError('does not match schema')

    _patch_prompt_module(monkeypatch, _fake_prompt_module(parse_response=_bad_parse))

    response = gateway.request_intelligence('journal_review', {'trade_id': 1}, 'pedro', 'req_1')
    assert response.success is False
    assert response.error_code == IntelligenceErrorCode.MALFORMED_OUTPUT.value
    assert response.content is None

    # A second identical call must NOT be served from cache (never cached).
    response2 = gateway.request_intelligence('journal_review', {'trade_id': 1}, 'pedro', 'req_2')
    assert response2.cached is False
    assert mock_adapter.call.call_count == 2


# ── Reservations released on every terminal path ────────────────────────────
@patch(f'{GATEWAY_MODULE}.AnthropicAdapter')
def test_reservation_released_after_non_retryable_failure(mock_adapter_cls, monkeypatch):
    mock_adapter = MagicMock()
    mock_adapter.call.side_effect = ProviderError(IntelligenceErrorCode.AUTH_FAILED, False)
    mock_adapter_cls.return_value = mock_adapter
    _patch_prompt_module(monkeypatch, _fake_prompt_module())

    gateway.request_intelligence('market_summary', {'n': 1}, 'pedro', 'req_1')

    state = budget._read_state(budget.BUDGET_FILE)
    assert state.reserved_count == 0
    assert state.request_count == 1


@patch(f'{GATEWAY_MODULE}.AnthropicAdapter')
def test_reservation_released_when_prompt_construction_fails(mock_adapter_cls, monkeypatch):
    mock_adapter = MagicMock()
    mock_adapter_cls.return_value = mock_adapter

    def _broken_build(_input_data):
        raise RuntimeError('prompt module not ready')

    _patch_prompt_module(monkeypatch, _fake_prompt_module(build_prompt=_broken_build))

    with pytest.raises(RuntimeError):
        gateway.request_intelligence('market_summary', {'n': 1}, 'pedro', 'req_1')

    mock_adapter.call.assert_not_called()
    state = budget._read_state(budget.BUDGET_FILE)
    assert state.reserved_count == 0
    assert state.request_count == 0


# ── Prompt loading is lazy: only imported on a cache-miss, cache-enabled or
#    not, never on any early-exit path ─────────────────────────────────────
def test_prompt_module_not_imported_when_provider_not_configured(monkeypatch):
    monkeypatch.setattr(config, 'ANTHROPIC_API_KEY', '')
    import_calls = []
    monkeypatch.setattr(f'{GATEWAY_MODULE}.import_module', lambda name: import_calls.append(name))

    gateway.request_intelligence('market_summary', {'n': 1}, 'pedro', 'req_1')

    assert import_calls == []


# ── Audit: exactly one record per request, redacted ─────────────────────────
@patch(f'{GATEWAY_MODULE}.AnthropicAdapter')
def test_audit_writes_exactly_one_record_and_redacts_content(mock_adapter_cls, monkeypatch):
    mock_adapter = MagicMock()
    mock_adapter.call.return_value = _adapter_result(text='super secret model output')
    mock_adapter_cls.return_value = mock_adapter
    _patch_prompt_module(monkeypatch, _fake_prompt_module())

    gateway.request_intelligence('journal_review', {'trade_id': 1, 'notes': 'private trade detail'}, 'pedro', 'req_1')

    entries = audit._load(audit.AUDIT_FILE)
    assert len(entries) == 1
    record = entries[0]
    assert record['feature'] == 'journal_review'
    serialized = str(record)
    assert 'super secret model output' not in serialized
    assert 'private trade detail' not in serialized
    assert 'sk-ant-test-key' not in serialized


@patch(f'{GATEWAY_MODULE}.AnthropicAdapter')
def test_audit_malformed_output_records_length_and_hash_not_content(mock_adapter_cls, monkeypatch):
    mock_adapter = MagicMock()
    mock_adapter.call.return_value = _adapter_result(text='not valid json content here')
    mock_adapter_cls.return_value = mock_adapter

    def _bad_parse(text):
        raise ValueError('schema mismatch')

    _patch_prompt_module(monkeypatch, _fake_prompt_module(parse_response=_bad_parse))

    gateway.request_intelligence('journal_review', {'trade_id': 1}, 'pedro', 'req_1')

    entries = audit._load(audit.AUDIT_FILE)
    record = entries[-1]
    assert record['malformed_response_length'] == len('not valid json content here')
    assert record['malformed_response_hash'] is not None
    assert 'not valid json content here' not in str(record)


# ── No real network access ──────────────────────────────────────────────────
def test_socket_connect_is_blocked_by_fixture():
    with pytest.raises(AssertionError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(('api.anthropic.com', 443))
