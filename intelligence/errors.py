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
