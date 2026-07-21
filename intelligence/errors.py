"""intelligence/errors.py — fixed error_code vocabulary (spec §9). No other codes may be added without a spec revision."""
from __future__ import annotations

from enum import Enum


class IntelligenceErrorCode(str, Enum):
    PROVIDER_NOT_CONFIGURED = 'PROVIDER_NOT_CONFIGURED'
    AUTH_FAILED = 'AUTH_FAILED'
    INSUFFICIENT_CREDITS = 'INSUFFICIENT_CREDITS'
    RATE_LIMITED = 'RATE_LIMITED'
    TIMEOUT = 'TIMEOUT'
    INVALID_PROVIDER_RESPONSE = 'INVALID_PROVIDER_RESPONSE'
    MALFORMED_OUTPUT = 'MALFORMED_OUTPUT'
    BUDGET_EXCEEDED = 'BUDGET_EXCEEDED'
    BUDGET_STATE_UNAVAILABLE = 'BUDGET_STATE_UNAVAILABLE'
    CIRCUIT_OPEN = 'CIRCUIT_OPEN'
    MODEL_NOT_SUPPORTED = 'MODEL_NOT_SUPPORTED'


# Provider-agnostic failure kinds a ProviderAdapter can classify a caught
# exception into, mapped to the fixed vocabulary above (spec §9). This is
# "the only place that translates 'Anthropic raised X' into 'NOVA means Y'"
# (spec §6.1) — it takes plain strings, not SDK exception types, so this
# module never needs to import a provider SDK.
_PROVIDER_ERROR_KINDS: dict[str, IntelligenceErrorCode] = {
    'missing_config': IntelligenceErrorCode.PROVIDER_NOT_CONFIGURED,
    'authentication': IntelligenceErrorCode.AUTH_FAILED,
    'permission_denied_billing': IntelligenceErrorCode.INSUFFICIENT_CREDITS,
    'permission_denied_other': IntelligenceErrorCode.AUTH_FAILED,
    'rate_limited': IntelligenceErrorCode.RATE_LIMITED,
    'timeout': IntelligenceErrorCode.TIMEOUT,
    'connection_error': IntelligenceErrorCode.INVALID_PROVIDER_RESPONSE,
    'not_found': IntelligenceErrorCode.INVALID_PROVIDER_RESPONSE,
    'status_error': IntelligenceErrorCode.INVALID_PROVIDER_RESPONSE,
}


def classify_provider_error(kind: str) -> IntelligenceErrorCode:
    try:
        return _PROVIDER_ERROR_KINDS[kind]
    except KeyError:
        raise ValueError(f'unrecognized provider-error kind: {kind!r}') from None
