"""intelligence/gateway.py — request_intelligence(), the only function application code calls (spec §6.1, §7.1).

Full orchestration (spec §14 commit #4): feature validation, config/provider
validation, cache lookup, circuit-breaker check, model + budget reservation,
lazy prompt construction, one provider attempt with NOVA's single controlled
retry, budget settlement, cache write on valid success, audit write, response
envelope.

Still zero feature migration -- nothing in NOVA calls this yet. Each
feature's prompt_module (registry.py) is resolved lazily via importlib and
does not exist until its own migration commit (§14 commits #5-#7); commit
#4's own tests supply a mocked module.

Stays provider-agnostic throughout: this file never imports anthropic, never
inspects a provider status code, and never inspects a raised exception's
__cause__. Retry eligibility is read directly from
providers.base.ProviderError.retryable, decided entirely inside the adapter
boundary (see errors.classify_provider_error).
"""
from __future__ import annotations

import hashlib
import json
import time
from importlib import import_module
from typing import Optional

from . import audit, budget, cache, config
from .envelope import IntelligenceResponse, UsageInfo
from .errors import IntelligenceErrorCode
from .providers.anthropic_adapter import AnthropicAdapter
from .providers.base import ProviderError
from .registry import FEATURE_REGISTRY

_VALID_PROVIDERS = ('anthropic',)

_MAX_BOUNDED_INPUT_TOKENS = 4_000  # spec §8 row 2 -- rough char-count guard, not exact tokenization

_CIRCUIT_FAILURE_THRESHOLD = 3
_CIRCUIT_WINDOW_SECONDS = 5 * 60
_CIRCUIT_OPEN_SECONDS = 15 * 60

_circuit_state: dict = {}  # feature -> {'failure_times': [...], 'open_until': float | None}

_USER_MESSAGES = {
    IntelligenceErrorCode.PROVIDER_NOT_CONFIGURED: 'AI features are not configured right now.',
    IntelligenceErrorCode.AUTH_FAILED: 'AI features are not configured right now.',
    IntelligenceErrorCode.INSUFFICIENT_CREDITS: 'AI credits are unavailable right now — try again later.',
    IntelligenceErrorCode.RATE_LIMITED: 'AI is temporarily busy — try again in a moment.',
    IntelligenceErrorCode.TIMEOUT: 'AI is temporarily busy — try again in a moment.',
    IntelligenceErrorCode.INVALID_PROVIDER_RESPONSE: 'AI request failed.',
    IntelligenceErrorCode.MALFORMED_OUTPUT: 'AI request failed.',
    IntelligenceErrorCode.BUDGET_EXCEEDED: "Today's AI usage limit has been reached.",
    IntelligenceErrorCode.BUDGET_STATE_UNAVAILABLE: 'AI usage tracking is temporarily unavailable, so no paid request was made.',
    IntelligenceErrorCode.CIRCUIT_OPEN: 'AI is temporarily unavailable — try again shortly.',
    IntelligenceErrorCode.MODEL_NOT_SUPPORTED: "AI is misconfigured — the configured model isn't recognized.",
}


def _now() -> float:
    """Injectable monotonic clock for the circuit breaker (tests monkeypatch this)."""
    return time.monotonic()


def _circuit_is_open(feature: str) -> bool:
    state = _circuit_state.get(feature)
    if not state or state.get('open_until') is None:
        return False
    if _now() >= state['open_until']:
        state['open_until'] = None
        state['failure_times'] = []
        return False
    return True


def _record_circuit_failure(feature: str) -> None:
    now = _now()
    state = _circuit_state.setdefault(feature, {'failure_times': [], 'open_until': None})
    state['failure_times'] = [t for t in state['failure_times'] if now - t <= _CIRCUIT_WINDOW_SECONDS]
    state['failure_times'].append(now)
    if len(state['failure_times']) >= _CIRCUIT_FAILURE_THRESHOLD:
        state['open_until'] = now + _CIRCUIT_OPEN_SECONDS
        state['failure_times'] = []


def _record_circuit_success(feature: str) -> None:
    _circuit_state[feature] = {'failure_times': [], 'open_until': None}


def _estimate_input_tokens(input_data: dict) -> int:
    normalized = json.dumps(input_data, sort_keys=True, default=str)
    return min(max(1, len(normalized) // 4), _MAX_BOUNDED_INPUT_TOKENS)


def _resolve_adapter(provider_name: str):
    # A plain conditional, not a module-level {name: ClassObject} dict --
    # a dict built at import time would bind the real class by value,
    # which a test-time patch of the module-level AnthropicAdapter name
    # could never retroactively affect. This looks the name up fresh on
    # every call, same as `AnthropicAdapter()` written inline would.
    if provider_name == 'anthropic':
        return AnthropicAdapter()
    return None


def request_intelligence(feature: str, input_data: dict, user_id: str, request_id: str) -> IntelligenceResponse:
    start = time.monotonic()

    # 1. Feature validation -- caller-contract violation, no side effects at all.
    if feature not in FEATURE_REGISTRY:
        raise ValueError(f'unknown feature "{feature}" — must be one of {sorted(FEATURE_REGISTRY)}')
    feature_config = FEATURE_REGISTRY[feature]

    provider_name = config.NOVA_AI_PROVIDER
    model = config.NOVA_AI_MODEL

    def _envelope(**overrides) -> IntelligenceResponse:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        fields = dict(
            success=False, feature=feature, provider=provider_name, model=model,
            request_id=request_id, cached=False, latency_ms=elapsed_ms,
        )
        fields.update(overrides)
        return IntelligenceResponse(**fields)

    def _write_audit(response: IntelligenceResponse, *, input_tokens_estimate: Optional[int],
                      malformed_response_length: Optional[int] = None, malformed_response_hash: Optional[str] = None) -> None:
        record = audit.AuditRecord(
            request_id=response.request_id,
            feature=response.feature,
            provider=response.provider,
            model=response.model,
            cached=response.cached,
            success=response.success,
            error_code=response.error_code,
            input_tokens_estimate=input_tokens_estimate,
            input_tokens_actual=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            estimated_cost_usd=response.usage.estimated_cost_usd,
            latency_ms=response.latency_ms,
            timestamp=audit.utc_now_iso(),
            malformed_response_length=malformed_response_length,
            malformed_response_hash=malformed_response_hash,
        )
        audit.write_record(record)

    # 2. Configuration/provider validation.
    if provider_name not in _VALID_PROVIDERS or not config.ANTHROPIC_API_KEY:
        response = _envelope(
            error_code=IntelligenceErrorCode.PROVIDER_NOT_CONFIGURED.value,
            user_message=_USER_MESSAGES[IntelligenceErrorCode.PROVIDER_NOT_CONFIGURED],
        )
        _write_audit(response, input_tokens_estimate=None)
        return response

    # 3. Cache lookup -- bypasses circuit breaker, budget, prompt loading, and
    #    the provider entirely on a hit.
    cache_enabled_for_feature = feature_config.cache_ttl_seconds is not None and config.NOVA_AI_CACHE_ENABLED
    if cache_enabled_for_feature:
        cached_response = cache.get_cached_response(feature, input_data)
        if cached_response is not None:
            response = _envelope(
                success=True, cached=True,
                content=cached_response.content, structured_data=cached_response.structured_data,
                usage=UsageInfo(
                    input_tokens=cached_response.input_tokens,
                    output_tokens=cached_response.output_tokens,
                    estimated_cost_usd=0.0,
                ),
            )
            _write_audit(response, input_tokens_estimate=None)
            return response

    # 4. Circuit-breaker check.
    if _circuit_is_open(feature):
        response = _envelope(
            error_code=IntelligenceErrorCode.CIRCUIT_OPEN.value,
            user_message=_USER_MESSAGES[IntelligenceErrorCode.CIRCUIT_OPEN],
        )
        _write_audit(response, input_tokens_estimate=None)
        return response

    # 5. Model + budget validation/reservation (spec §8.2, §8.3).
    estimated_input_tokens = _estimate_input_tokens(input_data)
    try:
        reservation = budget.reserve(
            estimated_input_tokens=estimated_input_tokens,
            max_output_tokens=feature_config.max_output_tokens,
            model=model,
        )
    except budget.ModelNotSupported:
        response = _envelope(
            error_code=IntelligenceErrorCode.MODEL_NOT_SUPPORTED.value,
            user_message=_USER_MESSAGES[IntelligenceErrorCode.MODEL_NOT_SUPPORTED],
        )
        _write_audit(response, input_tokens_estimate=estimated_input_tokens)
        return response
    except budget.BudgetExceeded:
        response = _envelope(
            error_code=IntelligenceErrorCode.BUDGET_EXCEEDED.value,
            user_message=_USER_MESSAGES[IntelligenceErrorCode.BUDGET_EXCEEDED],
        )
        _write_audit(response, input_tokens_estimate=estimated_input_tokens)
        return response
    except budget.BudgetStateUnavailable:
        response = _envelope(
            error_code=IntelligenceErrorCode.BUDGET_STATE_UNAVAILABLE.value,
            user_message=_USER_MESSAGES[IntelligenceErrorCode.BUDGET_STATE_UNAVAILABLE],
        )
        _write_audit(response, input_tokens_estimate=estimated_input_tokens)
        return response

    # 6. Prompt construction -- lazily resolved; if it fails before the
    #    provider is ever called, release the reservation and let the
    #    original exception propagate (no §9 code models "prompt build
    #    failed", and nothing calls this in production yet).
    try:
        prompt_module = import_module(feature_config.prompt_module)
        prompt = prompt_module.build_prompt(input_data)
    except Exception:
        budget.release_reservation(reservation)
        raise

    # 7-8. Adapter call, with NOVA's single controlled retry when the
    #      adapter's own classification says the failure is retryable. The
    #      circuit breaker is not re-checked between attempt 1 and the retry.
    adapter = _resolve_adapter(provider_name)
    attempts: list = []
    result = None
    final_error: Optional[ProviderError] = None

    try:
        try:
            result = adapter.call(prompt, feature_config.max_output_tokens, feature_config.timeout_seconds)
            attempts.append(budget.AttemptOutcome(had_usage=True, input_tokens=result.input_tokens, output_tokens=result.output_tokens))
        except ProviderError as exc:
            attempts.append(budget.AttemptOutcome(had_usage=False))
            final_error = exc
            if exc.retryable:
                try:
                    result = adapter.call(prompt, feature_config.max_output_tokens, feature_config.timeout_seconds)
                    attempts.append(budget.AttemptOutcome(had_usage=True, input_tokens=result.input_tokens, output_tokens=result.output_tokens))
                    final_error = None
                except ProviderError as retry_exc:
                    attempts.append(budget.AttemptOutcome(had_usage=False))
                    final_error = retry_exc
    except Exception:
        # A genuinely unexpected (non-ProviderError) failure -- still release
        # the reservation before letting it propagate.
        budget.release_reservation(reservation)
        raise

    # 9. Budget settlement.
    try:
        settled_cost = budget.settle(reservation, attempts=attempts, model=model)
    except budget.BudgetStateUnavailable:
        # Extremely unlikely (the file was readable moments ago at
        # reservation time) -- the provider call already happened and the
        # caller must still get the real result, so fall back to the
        # reservation's own worst-case figure for the recorded cost.
        settled_cost = reservation.cost_reserved

    if final_error is not None:
        _record_circuit_failure(feature)
        response = _envelope(
            error_code=final_error.error_code.value,
            user_message=_USER_MESSAGES[final_error.error_code],
            usage=UsageInfo(estimated_cost_usd=settled_cost),
        )
        _write_audit(response, input_tokens_estimate=estimated_input_tokens)
        return response

    _record_circuit_success(feature)

    # 10. Parse/validate structured output, if the prompt module defines it.
    text = result.text
    structured_data = None
    malformed = False
    parse_response = getattr(prompt_module, 'parse_response', None)
    if parse_response is not None:
        try:
            structured_data = parse_response(text)
        except Exception:
            malformed = True

    if malformed:
        response = _envelope(
            error_code=IntelligenceErrorCode.MALFORMED_OUTPUT.value,
            user_message=_USER_MESSAGES[IntelligenceErrorCode.MALFORMED_OUTPUT],
            usage=UsageInfo(input_tokens=result.input_tokens, output_tokens=result.output_tokens, estimated_cost_usd=settled_cost),
        )
        _write_audit(
            response, input_tokens_estimate=estimated_input_tokens,
            malformed_response_length=len(text),
            malformed_response_hash=hashlib.sha256(text.encode('utf-8')).hexdigest(),
        )
        return response

    # 11. Cache write on valid success only.
    if cache_enabled_for_feature:
        cache.store_cached_response(
            feature, input_data,
            cache.CachedResponse(
                content=text, structured_data=structured_data, model=model,
                input_tokens=result.input_tokens, output_tokens=result.output_tokens,
            ),
            feature_config.cache_ttl_seconds,
        )

    # 12. Response envelope.
    response = _envelope(
        success=True,
        content=text,
        structured_data=structured_data,
        usage=UsageInfo(input_tokens=result.input_tokens, output_tokens=result.output_tokens, estimated_cost_usd=settled_cost),
    )
    _write_audit(response, input_tokens_estimate=estimated_input_tokens)
    return response
