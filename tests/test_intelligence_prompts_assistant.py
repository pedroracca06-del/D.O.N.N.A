"""
test_intelligence_prompts_assistant.py — NOVA Intelligence V1 commit #5:
migrating NOVA Assistant onto intelligence.gateway.

Covers, in one file (per the approved commit #5 file list):
  1. intelligence/prompts/assistant.py — build_prompt() / parse_response()
  2. services/assistant.py::call_assistant_llm() — gateway wiring + envelope handling
  3. main.py::assistant_chat() — route response shape + exception sanitization
  4. End-to-end through the real gateway + real prompt module, mocked adapter only

Fully mocked/isolated: no real Anthropic API key is used, no real network
socket is ever opened, and budget/cache/audit all use temporary state so
this file never touches real data/*.json.

Run:  python -m pytest tests/test_intelligence_prompts_assistant.py -v
"""
from __future__ import annotations

import ast
import asyncio
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
from intelligence.envelope import IntelligenceResponse, UsageInfo
from intelligence.errors import IntelligenceErrorCode
from intelligence.prompts import assistant as assistant_prompt
from intelligence.providers.base import AdapterResult

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT_MODULE_PATH = REPO_ROOT / 'intelligence' / 'prompts' / 'assistant.py'


@pytest.fixture(autouse=True)
def _block_real_network(monkeypatch):
    real_connect = socket.socket.connect

    def _guard(self, address, *args, **kwargs):
        # Windows' asyncio ProactorEventLoop opens a real loopback
        # socketpair for its internal self-pipe -- that's not "the
        # network", it never leaves the machine. Only block genuine
        # non-loopback destinations (e.g. api.anthropic.com).
        host = address[0] if isinstance(address, tuple) else address
        if host in ('127.0.0.1', 'localhost', '::1'):
            return real_connect(self, address, *args, **kwargs)
        raise AssertionError(f'real network access attempted during assistant migration tests: {address!r}')

    monkeypatch.setattr(socket.socket, 'connect', _guard)
    yield


def _input_data(message='what matters today?', system_context='Session: NY_AM\nMacro Risk: medium'):
    return {'message': message, 'system_context': system_context}


# ═══════════════════════════════════════════════════════════════════════
# 1. intelligence/prompts/assistant.py
# ═══════════════════════════════════════════════════════════════════════

def test_build_prompt_includes_instruction_substance():
    prompt = assistant_prompt.build_prompt(_input_data())
    assert 'NOVA' in prompt
    assert 'Return JSON only' in prompt
    assert '"action"' in prompt and '"reply"' in prompt


def test_build_prompt_includes_supplied_message():
    prompt = assistant_prompt.build_prompt(_input_data(message='is it safe to trade NVDA right now?'))
    assert 'is it safe to trade NVDA right now?' in prompt


def test_build_prompt_includes_supplied_system_context():
    prompt = assistant_prompt.build_prompt(_input_data(system_context='Session: NY_OPEN\nDominant Driver: mega-cap tech'))
    assert 'Session: NY_OPEN' in prompt
    assert 'Dominant Driver: mega-cap tech' in prompt


def test_build_prompt_sections_are_clearly_delimited_and_ordered():
    prompt = assistant_prompt.build_prompt(_input_data(message='USER_MARKER_XYZ', system_context='CONTEXT_MARKER_XYZ'))
    instr_idx = prompt.find('NOVA INSTRUCTIONS')
    context_idx = prompt.find('CONTEXT_MARKER_XYZ')
    user_idx = prompt.find('USER_MARKER_XYZ')
    assert -1 not in (instr_idx, context_idx, user_idx)
    # Instructions, then generated context, then the user's own text -- never
    # interleaved, so neither the context nor the message can be mistaken
    # for authority that redefines the output contract.
    assert instr_idx < context_idx < user_idx
    assert prompt.count('===') >= 6


def test_build_prompt_is_deterministic():
    data = _input_data()
    assert assistant_prompt.build_prompt(data) == assistant_prompt.build_prompt(data)


def test_parse_response_handles_well_formed_json():
    text = '{"action": "set_focus", "value": "NVDA breakout", "reply": "Got it, focusing on NVDA."}'
    result = assistant_prompt.parse_response(text)
    assert result == {'action': 'set_focus', 'value': 'NVDA breakout', 'reply': 'Got it, focusing on NVDA.'}


def test_parse_response_recovers_json_embedded_in_prose():
    text = 'Sure thing! {"action": "none", "value": "", "reply": "Market is quiet."} Let me know if you need more.'
    result = assistant_prompt.parse_response(text)
    assert result['action'] == 'none'
    assert result['reply'] == 'Market is quiet.'


def test_parse_response_raises_on_completely_unparseable_text():
    with pytest.raises(ValueError):
        assistant_prompt.parse_response('I cannot help with that right now, sorry.')


@pytest.mark.parametrize('text', ['[1, 2, 3]', '"just a string"', '42', 'true'])
def test_parse_response_raises_on_incompatible_top_level_type(text):
    with pytest.raises(ValueError):
        assistant_prompt.parse_response(text)


def test_parse_response_defaults_missing_fields_when_object_is_present():
    result = assistant_prompt.parse_response('{"reply": "hello"}')
    assert result == {'action': 'none', 'value': '', 'reply': 'hello'}


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
    assert offenders == [], f'unexpected import(s) in prompts/assistant.py: {offenders}'


# ═══════════════════════════════════════════════════════════════════════
# 2. services/assistant.py::call_assistant_llm()
# ═══════════════════════════════════════════════════════════════════════

def _success_envelope(structured_data):
    return IntelligenceResponse(
        success=True, feature='assistant', provider='anthropic', model='claude-haiku-4-5-20251001',
        request_id='req-test', cached=False, latency_ms=1, content='ignored', structured_data=structured_data,
        usage=UsageInfo(input_tokens=10, output_tokens=5, estimated_cost_usd=0.0001),
    )


def _failure_envelope(error_code: IntelligenceErrorCode, user_message: str):
    return IntelligenceResponse(
        success=False, feature='assistant', provider='anthropic', model='claude-haiku-4-5-20251001',
        request_id='req-test', cached=False, latency_ms=1, error_code=error_code.value, user_message=user_message,
        usage=UsageInfo(),
    )


def test_call_assistant_llm_invokes_gateway_with_feature_assistant(monkeypatch):
    import services.assistant as svc

    captured = {}

    def _fake_request_intelligence(feature, input_data, user_id, request_id):
        captured['feature'] = feature
        captured['input_data'] = input_data
        captured['user_id'] = user_id
        captured['request_id'] = request_id
        return _success_envelope({'action': 'none', 'value': '', 'reply': 'ok'})

    monkeypatch.setattr(svc, 'request_intelligence', _fake_request_intelligence)
    monkeypatch.setattr(svc, 'summarize_system_context', lambda: 'FAKE CONTEXT')

    svc.call_assistant_llm('hello there')

    assert captured['feature'] == 'assistant'
    assert captured['input_data'] == {'message': 'hello there', 'system_context': 'FAKE CONTEXT'}
    assert captured['user_id'] == 'pedro'
    assert isinstance(captured['request_id'], str) and captured['request_id']


def test_call_assistant_llm_returns_structured_data_on_success(monkeypatch):
    import services.assistant as svc

    expected = {'action': 'set_focus', 'value': 'NVDA', 'reply': 'Focusing on NVDA.'}
    monkeypatch.setattr(svc, 'request_intelligence', lambda *a, **kw: _success_envelope(expected))
    monkeypatch.setattr(svc, 'summarize_system_context', lambda: 'ctx')

    result = svc.call_assistant_llm('anything')
    assert result['action'] == 'set_focus'
    assert result['value'] == 'NVDA'
    assert result['reply'] == 'Focusing on NVDA.'
    # A real answer is the only outcome allowed to act on working memory.
    assert result['outcome'] == 'ok'
    assert result['error_code'] is None


def test_call_assistant_llm_reports_empty_reply_as_empty_not_ok(monkeypatch):
    """A success envelope carrying no reply text is not an answer."""
    import services.assistant as svc

    monkeypatch.setattr(svc, 'request_intelligence',
                        lambda *a, **kw: _success_envelope({'action': 'none', 'value': '', 'reply': '   '}))
    monkeypatch.setattr(svc, 'summarize_system_context', lambda: 'ctx')

    result = svc.call_assistant_llm('anything')
    assert result['outcome'] == 'empty'
    assert result['reply'] == ''


@pytest.mark.parametrize('payload', [None, 'a bare string', [], {'action': 'none', 'value': ''}])
def test_call_assistant_llm_reports_non_conforming_payload_as_malformed(monkeypatch, payload):
    """parse_response() can hand back something that is not the agreed
    {action,value,reply} contract. That is a distinct failure from the gateway
    being down, and must never be presented as an answer."""
    import services.assistant as svc

    monkeypatch.setattr(svc, 'request_intelligence', lambda *a, **kw: _success_envelope(payload))
    monkeypatch.setattr(svc, 'summarize_system_context', lambda: 'ctx')

    result = svc.call_assistant_llm('anything')
    assert result['outcome'] == 'malformed'
    assert result['error_code'] == 'MALFORMED_OUTPUT'
    assert result['reply'] == ''


@pytest.mark.parametrize('code,message', [
    (IntelligenceErrorCode.PROVIDER_NOT_CONFIGURED, 'AI features are not configured right now.'),
    (IntelligenceErrorCode.AUTH_FAILED, 'AI features are not configured right now.'),
    (IntelligenceErrorCode.INSUFFICIENT_CREDITS, 'AI credits are unavailable right now — try again later.'),
    (IntelligenceErrorCode.RATE_LIMITED, 'AI is temporarily busy — try again in a moment.'),
    (IntelligenceErrorCode.TIMEOUT, 'AI is temporarily busy — try again in a moment.'),
    (IntelligenceErrorCode.INVALID_PROVIDER_RESPONSE, 'AI request failed.'),
    (IntelligenceErrorCode.MALFORMED_OUTPUT, 'AI request failed.'),
    (IntelligenceErrorCode.MODEL_NOT_SUPPORTED, "AI is misconfigured — the configured model isn't recognized."),
    (IntelligenceErrorCode.BUDGET_EXCEEDED, "Today's AI usage limit has been reached."),
    (IntelligenceErrorCode.BUDGET_STATE_UNAVAILABLE, 'AI usage tracking is temporarily unavailable, so no paid request was made.'),
    (IntelligenceErrorCode.CIRCUIT_OPEN, 'AI is temporarily unavailable — try again shortly.'),
])
def test_call_assistant_llm_maps_every_gateway_error_code(monkeypatch, code, message):
    import services.assistant as svc

    monkeypatch.setattr(svc, 'request_intelligence', lambda *a, **kw: _failure_envelope(code, message))
    monkeypatch.setattr(svc, 'summarize_system_context', lambda: 'ctx')

    result = svc.call_assistant_llm('anything')
    assert result['action'] == 'none'
    assert result['value'] == ''
    # The user-safe message still passes through untouched...
    assert result['reply'] == message
    # ...but it is now labelled as a failure, so no caller can mistake it for
    # an answer. This is the defect that let the page render
    # "AI features are not configured right now." as a NOVA analysis.
    assert result['outcome'] == 'unavailable'
    assert result['error_code'] == code.value


def test_call_assistant_llm_does_not_import_client_or_assistant_model():
    import services.assistant as svc
    assert not hasattr(svc, 'client')
    assert not hasattr(svc, 'ANTHROPIC_ASSISTANT_MODEL')


def test_call_assistant_llm_has_no_second_broad_exception_handler():
    """Prompt-build / unexpected adapter failures must propagate -- not be
    caught and reworded inside the service layer."""
    import inspect
    import services.assistant as svc
    source = inspect.getsource(svc.call_assistant_llm)
    tree = ast.parse(source)
    except_handlers = [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]
    assert except_handlers == []


def test_unexpected_exception_from_gateway_propagates_out_of_service(monkeypatch):
    import services.assistant as svc

    def _boom(*a, **kw):
        raise RuntimeError('a secret internal detail that must never reach the user')

    monkeypatch.setattr(svc, 'request_intelligence', _boom)
    monkeypatch.setattr(svc, 'summarize_system_context', lambda: 'ctx')

    with pytest.raises(RuntimeError):
        svc.call_assistant_llm('anything')


# ═══════════════════════════════════════════════════════════════════════
# 3. main.py::assistant_chat()
# ═══════════════════════════════════════════════════════════════════════

class _FakeRequest:
    """Duck-types starlette.requests.Request for the one method assistant_chat() calls."""
    def __init__(self, body: dict):
        self._body = body

    async def json(self):
        return self._body


def test_assistant_chat_route_is_registered():
    import main
    assert any(getattr(r, 'path', None) == '/assistant/chat' for r in main.app.routes)


def test_assistant_chat_success_preserves_response_shape():
    import main
    fake_result = {'action': 'set_focus', 'value': 'NVDA', 'reply': 'Focusing on NVDA.'}
    with patch.object(main, 'call_assistant_llm', return_value=fake_result), \
         patch.object(main, 'apply_assistant_action', return_value={'daily_focus': 'NVDA', 'tasks': [], 'reminders': []}) as mock_apply:
        result = asyncio.run(main.assistant_chat(_FakeRequest({'message': 'focus on NVDA'})))

    assert result['status'] == 'ok'
    assert result['action'] == 'set_focus'
    assert result['value'] == 'NVDA'
    assert result['reply'] == 'Focusing on NVDA.'
    assert 'assistant' in result and 'risk' in result and 'alerts' in result
    mock_apply.assert_called_once_with('set_focus', 'NVDA')


def test_assistant_chat_gateway_failure_message_passes_through_unmodified():
    """The user-safe message is preserved verbatim -- but the route must not
    call it 'ok'. Reporting a failure as a success is exactly what made the
    frontend render it in NOVA's voice."""
    import main
    fake_result = {'action': 'none', 'value': '', 'reply': 'AI credits are unavailable right now — try again later.',
                   'outcome': 'unavailable', 'error_code': 'INSUFFICIENT_CREDITS', 'cached': False}
    with patch.object(main, 'call_assistant_llm', return_value=fake_result), \
         patch.object(main, 'apply_assistant_action') as mock_apply:
        result = asyncio.run(main.assistant_chat(_FakeRequest({'message': 'hello'})))

    assert result['reply'] == 'AI credits are unavailable right now — try again later.'
    assert result['status'] == 'unavailable'
    assert result['outcome'] == 'unavailable'
    assert result['error_code'] == 'INSUFFICIENT_CREDITS'
    # A failed call carries no trustworthy action, so working memory is read,
    # never written.
    mock_apply.assert_not_called()


@pytest.mark.parametrize('outcome,status', [
    ('ok', 'ok'), ('empty', 'empty'), ('malformed', 'malformed'), ('unavailable', 'unavailable'),
])
def test_assistant_chat_status_is_distinct_per_outcome(outcome, status):
    """unavailable / empty / malformed / successful must be distinguishable by
    the client without inspecting the reply text."""
    import main
    fake_result = {'action': 'none', 'value': '', 'reply': 'x' if outcome == 'ok' else '',
                   'outcome': outcome, 'error_code': None, 'cached': False}
    with patch.object(main, 'call_assistant_llm', return_value=fake_result), \
         patch.object(main, 'apply_assistant_action', return_value={'daily_focus': None, 'tasks': [], 'reminders': []}):
        result = asyncio.run(main.assistant_chat(_FakeRequest({'message': 'hello'})))

    assert result['status'] == status
    assert result['outcome'] == outcome


def test_assistant_chat_only_a_real_answer_may_write_working_memory():
    import main
    fake_result = {'action': 'set_focus', 'value': 'NVDA', 'reply': 'Focusing on NVDA.',
                   'outcome': 'ok', 'error_code': None, 'cached': False}
    with patch.object(main, 'call_assistant_llm', return_value=fake_result), \
         patch.object(main, 'apply_assistant_action', return_value={'daily_focus': 'NVDA', 'tasks': [], 'reminders': []}) as mock_apply:
        result = asyncio.run(main.assistant_chat(_FakeRequest({'message': 'focus on NVDA'})))

    assert result['status'] == 'ok'
    mock_apply.assert_called_once_with('set_focus', 'NVDA')


def test_assistant_chat_unexpected_exception_returns_sanitized_shape():
    import main
    with patch.object(main, 'call_assistant_llm', side_effect=RuntimeError('leaked secret path /etc/passwd or API key sk-ant-XYZ')):
        result = asyncio.run(main.assistant_chat(_FakeRequest({'message': 'hello'})))

    assert result['status'] == 'error'
    assert result['action'] == 'none'
    assert result['value'] == ''
    assert result['reply'] == 'AI request failed.'
    serialized = str(result)
    assert 'leaked secret' not in serialized
    assert 'sk-ant-XYZ' not in serialized
    assert '/etc/passwd' not in serialized


def test_assistant_chat_requires_nonempty_message():
    import main
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        asyncio.run(main.assistant_chat(_FakeRequest({'message': '  '})))


# ═══════════════════════════════════════════════════════════════════════
# 4. End-to-end through the real gateway + real prompt module (mocked adapter)
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


def _mock_adapter_result(text, input_tokens=20, output_tokens=10, model='claude-haiku-4-5-20251001'):
    return AdapterResult(text=text, input_tokens=input_tokens, output_tokens=output_tokens, model=model)


@patch('intelligence.gateway.AnthropicAdapter')
def test_end_to_end_success_through_real_gateway_and_prompt_module(mock_adapter_cls):
    from intelligence.gateway import request_intelligence

    mock_adapter = MagicMock()
    mock_adapter.call.return_value = _mock_adapter_result(
        '{"action": "none", "value": "", "reply": "All quiet, no major threats right now."}'
    )
    mock_adapter_cls.return_value = mock_adapter

    response = request_intelligence(
        'assistant',
        {'message': 'what matters today?', 'system_context': 'Session: NY_AM'},
        user_id='pedro', request_id='req-e2e-1',
    )

    assert response.success is True
    assert response.cached is False
    assert response.structured_data == {'action': 'none', 'value': '', 'reply': 'All quiet, no major threats right now.'}
    mock_adapter.call.assert_called_once()
    sent_prompt = mock_adapter.call.call_args.args[0]
    assert 'what matters today?' in sent_prompt
    assert 'Session: NY_AM' in sent_prompt


@patch('intelligence.gateway.AnthropicAdapter')
def test_end_to_end_malformed_output_through_real_gateway(mock_adapter_cls):
    from intelligence.gateway import request_intelligence

    mock_adapter = MagicMock()
    mock_adapter.call.return_value = _mock_adapter_result('I refuse to answer in JSON today.')
    mock_adapter_cls.return_value = mock_adapter

    response = request_intelligence(
        'assistant',
        {'message': 'hello', 'system_context': 'ctx'},
        user_id='pedro', request_id='req-e2e-2',
    )

    assert response.success is False
    assert response.error_code == IntelligenceErrorCode.MALFORMED_OUTPUT.value
    assert response.content is None


@patch('intelligence.gateway.AnthropicAdapter')
def test_end_to_end_assistant_feature_never_cached(mock_adapter_cls):
    from intelligence.gateway import request_intelligence

    mock_adapter = MagicMock()
    mock_adapter.call.return_value = _mock_adapter_result('{"action": "none", "value": "", "reply": "ok"}')
    mock_adapter_cls.return_value = mock_adapter

    input_data = {'message': 'same message every time', 'system_context': 'ctx'}
    request_intelligence('assistant', input_data, user_id='pedro', request_id='req-e2e-3a')
    request_intelligence('assistant', input_data, user_id='pedro', request_id='req-e2e-3b')

    assert mock_adapter.call.call_count == 2  # never served from cache
    assert cache.get_cached_response('assistant', input_data) is None
