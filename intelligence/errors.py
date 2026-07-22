"""intelligence/errors.py — fixed error_code vocabulary (spec §9). No other codes may be added without a spec revision."""
from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class ProviderErrorClassification:
    error_code: IntelligenceErrorCode
    retryable: bool


# Provider-agnostic failure kinds a ProviderAdapter can classify a caught
# exception into, mapped to the fixed vocabulary above (spec §9) plus NOVA's
# retry eligibility (spec §8 row 4). This is "the only place that translates
# 'Anthropic raised X' into 'NOVA means Y'" (spec §6.1) — it takes plain
# strings, not SDK exception types, so this module never needs to import a
# provider SDK. retryable is decided here, not by the gateway, so gateway.py
# can apply NOVA's retry policy from err.retryable alone, with no
# provider-specific knowledge.
_PROVIDER_ERROR_KINDS: dict[str, ProviderErrorClassification] = {
    'missing_config': ProviderErrorClassification(IntelligenceErrorCode.PROVIDER_NOT_CONFIGURED, False),
    'authentication': ProviderErrorClassification(IntelligenceErrorCode.AUTH_FAILED, False),
    'permission_denied_billing': ProviderErrorClassification(IntelligenceErrorCode.INSUFFICIENT_CREDITS, False),
    'permission_denied_other': ProviderErrorClassification(IntelligenceErrorCode.AUTH_FAILED, False),
    'rate_limited': ProviderErrorClassification(IntelligenceErrorCode.RATE_LIMITED, False),
    'timeout': ProviderErrorClassification(IntelligenceErrorCode.TIMEOUT, True),
    'connection_error': ProviderErrorClassification(IntelligenceErrorCode.INVALID_PROVIDER_RESPONSE, True),
    'not_found': ProviderErrorClassification(IntelligenceErrorCode.INVALID_PROVIDER_RESPONSE, False),
    'status_error_retryable': ProviderErrorClassification(IntelligenceErrorCode.INVALID_PROVIDER_RESPONSE, True),
    'status_error_permanent': ProviderErrorClassification(IntelligenceErrorCode.INVALID_PROVIDER_RESPONSE, False),
}


def classify_provider_error(kind: str) -> ProviderErrorClassification:
    try:
        return _PROVIDER_ERROR_KINDS[kind]
    except KeyError:
        raise ValueError(f'unrecognized provider-error kind: {kind!r}') from None
