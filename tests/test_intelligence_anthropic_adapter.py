"""
test_intelligence_anthropic_adapter.py — NOVA Intelligence V1 commit #3.

Covers intelligence/providers/base.py (ProviderAdapter contract) and
intelligence/providers/anthropic_adapter.py (the one V1 provider adapter,
spec §5/§13 decision 9). Fully mocked — no real Anthropic API key is used,
no real network socket is ever opened (spec §15 test 18).

Does not test gateway.py, budget.py, cache.py, or any feature migration —
none of those exist yet (commit #4+).

Run:  python -m pytest tests/test_intelligence_anthropic_adapter.py -v
"""
from __future__ import annotations

import ast
import json
import os
import socket
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic

from intelligence.errors import IntelligenceErrorCode, classify_provider_error
from intelligence.providers.anthropic_adapter import AnthropicAdapter
from intelligence.providers.base import AdapterResult, ProviderAdapter, ProviderError

REPO_ROOT = Path(__file__).resolve().parents[1]
INTELLIGENCE_DIR = REPO_ROOT / 'intelligence'
ADAPTER_MODULE = 'intelligence.providers.anthropic_adapter'


# ── No real network access anywhere in this module (spec §15 test 18) ──────
@pytest.fixture(autouse=True)
def _block_real_network(monkeypatch):
    def _guard(*_args, **_kwargs):
        raise AssertionError('real network access attempted during intelligence adapter tests')
    monkeypatch.setattr(socket.socket, 'connect', _guard)
    yield


def _status_error(cls, status_code: int, error_type: str):
    """Build a real anthropic status-error instance without any network I/O."""
    req = httpx.Request('POST', 'https://api.anthropic.com/v1/messages')
    body = {'type': 'error', 'error': {'type': error_type, 'message': 'mocked'}}
    resp = httpx.Response(status_code, request=req, content=json.dumps(body).encode())
    return cls('mocked', response=resp, body=body)


def _connection_error(cls):
    req = httpx.Request('POST', 'https://api.anthropic.com/v1/messages')
    if cls is anthropic.APITimeoutError:
        return cls(request=req)
    return cls(request=req)


def _mock_response(text='ok', input_tokens=12, output_tokens=34, model='claude-haiku-4-5-20251001'):
    block = MagicMock()
    block.type = 'text'
    block.text = text
    response = MagicMock()
    response.content = [block]
    response.usage.input_tokens = input_tokens
    response.usage.output_tokens = output_tokens
    response.model = model
    return response


def _patched_client(mock_anthropic_cls):
    """Wire mock_anthropic_cls() -> mock_client, mock_client.with_options(...) -> mock_timed_client."""
    mock_client = MagicMock()
    mock_timed_client = MagicMock()
    mock_client.with_options.return_value = mock_timed_client
    mock_anthropic_cls.return_value = mock_client
    return mock_client, mock_timed_client


@pytest.fixture(autouse=True)
def _configured_key(monkeypatch):
    monkeypatch.setattr('intelligence.providers.anthropic_adapter.config.ANTHROPIC_API_KEY', 'sk-ant-test-key')
    monkeypatch.setattr('intelligence.providers.anthropic_adapter.config.NOVA_AI_MODEL', 'claude-haiku-4-5-20251001')
    yield


# ── 1. Adapter contract compliance ──────────────────────────────────────────
def test_adapter_implements_provider_adapter_contract():
    assert issubclass(AnthropicAdapter, ProviderAdapter)
    adapter = AnthropicAdapter()
    assert callable(adapter.call)
    with pytest.raises(TypeError):
        ProviderAdapter()  # abstract — cannot be instantiated directly


# ── 2-4. Successful response: text, tokens, model normalization ────────────
@patch(f'{ADAPTER_MODULE}.anthropic.Anthropic')
def test_successful_call_normalizes_text_tokens_and_model(mock_anthropic_cls):
    _mock_client, mock_timed_client = _patched_client(mock_anthropic_cls)
    mock_timed_client.messages.create.return_value = _mock_response(
        text='hello from claude', input_tokens=100, output_tokens=42, model='claude-haiku-4-5-20251001',
    )

    result = AnthropicAdapter().call(prompt='hi', max_tokens=400, timeout=30.0)

    assert isinstance(result, AdapterResult)
    assert result.text == 'hello from claude'
    assert result.input_tokens == 100
    assert result.output_tokens == 42
    assert result.model == 'claude-haiku-4-5-20251001'


# ── 5. Exact Anthropic request arguments ────────────────────────────────────
@patch(f'{ADAPTER_MODULE}.anthropic.Anthropic')
def test_request_sends_only_model_max_tokens_and_user_message(mock_anthropic_cls):
    _mock_client, mock_timed_client = _patched_client(mock_anthropic_cls)
    mock_timed_client.messages.create.return_value = _mock_response()

    AnthropicAdapter().call(prompt='the exact prompt', max_tokens=400, timeout=30.0)

    mock_timed_client.messages.create.assert_called_once_with(
        model='claude-haiku-4-5-20251001',
        max_tokens=400,
        messages=[{'role': 'user', 'content': 'the exact prompt'}],
    )
    kwargs = mock_timed_client.messages.create.call_args.kwargs
    assert set(kwargs.keys()) == {'model', 'max_tokens', 'messages'}
    assert 'thinking' not in kwargs
    assert 'tools' not in kwargs
    assert 'system' not in kwargs
    assert 'stream' not in kwargs
    assert 'output_config' not in kwargs


# ── 6. Timeout passed through with_options(), not messages.create() ────────
@patch(f'{ADAPTER_MODULE}.anthropic.Anthropic')
def test_timeout_applied_via_with_options_not_create_kwargs(mock_anthropic_cls):
    mock_client, mock_timed_client = _patched_client(mock_anthropic_cls)
    mock_timed_client.messages.create.return_value = _mock_response()

    AnthropicAdapter().call(prompt='hi', max_tokens=400, timeout=17.5)

    mock_client.with_options.assert_called_once_with(timeout=17.5)
    kwargs = mock_timed_client.messages.create.call_args.kwargs
    assert 'timeout' not in kwargs


# ── 7. max_retries=0 ─────────────────────────────────────────────────────────
@patch(f'{ADAPTER_MODULE}.anthropic.Anthropic')
def test_client_constructed_with_max_retries_zero(mock_anthropic_cls):
    _mock_client, mock_timed_client = _patched_client(mock_anthropic_cls)
    mock_timed_client.messages.create.return_value = _mock_response()

    AnthropicAdapter().call(prompt='hi', max_tokens=400, timeout=30.0)

    _, kwargs = mock_anthropic_cls.call_args
    assert kwargs.get('max_retries') == 0


# ── 8. Exactly one provider attempt — no retry loop in the adapter ─────────
@patch(f'{ADAPTER_MODULE}.anthropic.Anthropic')
def test_exactly_one_attempt_on_transient_failure(mock_anthropic_cls):
    _mock_client, mock_timed_client = _patched_client(mock_anthropic_cls)
    mock_timed_client.messages.create.side_effect = _connection_error(anthropic.APITimeoutError)

    with pytest.raises(ProviderError):
        AnthropicAdapter().call(prompt='hi', max_tokens=400, timeout=30.0)

    assert mock_timed_client.messages.create.call_count == 1
    mock_anthropic_cls.assert_called_once()


# ── 9. Every approved error mapping ─────────────────────────────────────────
@pytest.mark.parametrize(
    'make_exc, expected_code',
    [
        (lambda: _status_error(anthropic.AuthenticationError, 401, 'authentication_error'), IntelligenceErrorCode.AUTH_FAILED),
        (lambda: _status_error(anthropic.PermissionDeniedError, 403, 'billing_error'), IntelligenceErrorCode.INSUFFICIENT_CREDITS),
        (lambda: _status_error(anthropic.PermissionDeniedError, 403, 'permission_error'), IntelligenceErrorCode.AUTH_FAILED),
        (lambda: _status_error(anthropic.RateLimitError, 429, 'rate_limit_error'), IntelligenceErrorCode.RATE_LIMITED),
        (lambda: _status_error(anthropic.APIStatusError, 529, 'overloaded_error'), IntelligenceErrorCode.RATE_LIMITED),
        (lambda: _connection_error(anthropic.APITimeoutError), IntelligenceErrorCode.TIMEOUT),
        (lambda: _connection_error(anthropic.APIConnectionError), IntelligenceErrorCode.INVALID_PROVIDER_RESPONSE),
        (lambda: _status_error(anthropic.NotFoundError, 404, 'not_found_error'), IntelligenceErrorCode.INVALID_PROVIDER_RESPONSE),
        (lambda: _status_error(anthropic.APIStatusError, 500, 'api_error'), IntelligenceErrorCode.INVALID_PROVIDER_RESPONSE),
    ],
    ids=[
        'AuthenticationError->AUTH_FAILED',
        'PermissionDenied(billing_error)->INSUFFICIENT_CREDITS',
        'PermissionDenied(other)->AUTH_FAILED',
        'RateLimitError->RATE_LIMITED',
        'APIStatusError(529)->RATE_LIMITED',
        'APITimeoutError->TIMEOUT',
        'APIConnectionError->INVALID_PROVIDER_RESPONSE',
        'NotFoundError->INVALID_PROVIDER_RESPONSE',
        'APIStatusError(500)->INVALID_PROVIDER_RESPONSE',
    ],
)
@patch(f'{ADAPTER_MODULE}.anthropic.Anthropic')
def test_error_mappings(mock_anthropic_cls, make_exc, expected_code):
    _mock_client, mock_timed_client = _patched_client(mock_anthropic_cls)
    mock_timed_client.messages.create.side_effect = make_exc()

    with pytest.raises(ProviderError) as exc_info:
        AnthropicAdapter().call(prompt='hi', max_tokens=400, timeout=30.0)

    assert exc_info.value.error_code == expected_code


def test_classify_provider_error_rejects_unknown_kind():
    with pytest.raises(ValueError):
        classify_provider_error('not_a_real_kind')


# ── 10. Missing API key — never constructs or calls a live client ──────────
@patch(f'{ADAPTER_MODULE}.anthropic.Anthropic')
def test_missing_api_key_never_constructs_client(mock_anthropic_cls, monkeypatch):
    monkeypatch.setattr(f'{ADAPTER_MODULE}.config.ANTHROPIC_API_KEY', '')

    with pytest.raises(ProviderError) as exc_info:
        AnthropicAdapter().call(prompt='hi', max_tokens=400, timeout=30.0)

    assert exc_info.value.error_code == IntelligenceErrorCode.PROVIDER_NOT_CONFIGURED
    mock_anthropic_cls.assert_not_called()


# ── 11. Static confirmation: anthropic_adapter.py is the only intelligence/
#        module (excluding tests) importing anthropic ────────────────────
def test_only_anthropic_adapter_imports_anthropic_sdk():
    offenders = []
    for py_file in INTELLIGENCE_DIR.rglob('*.py'):
        if py_file == INTELLIGENCE_DIR / 'providers' / 'anthropic_adapter.py':
            continue
        tree = ast.parse(py_file.read_text(encoding='utf-8'), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(a.name.split('.')[0] == 'anthropic' for a in node.names):
                offenders.append(str(py_file.relative_to(REPO_ROOT)))
            if isinstance(node, ast.ImportFrom) and node.module and node.module.split('.')[0] == 'anthropic':
                offenders.append(str(py_file.relative_to(REPO_ROOT)))
    assert offenders == [], f'unexpected anthropic import(s) outside anthropic_adapter.py: {offenders}'


# ── 12. No real network access (structural — see also the autouse fixture) ─
def test_socket_connect_is_blocked_by_fixture():
    with pytest.raises(AssertionError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(('api.anthropic.com', 443))
