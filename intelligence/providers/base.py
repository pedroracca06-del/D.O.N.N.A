"""intelligence/providers/base.py — ProviderAdapter interface every adapter must implement (spec §6.1). Provider-independent; no SDK import."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..errors import IntelligenceErrorCode


@dataclass(frozen=True)
class AdapterResult:
    text: str
    input_tokens: int
    output_tokens: int
    model: str


class ProviderError(Exception):
    """Raised by a ProviderAdapter on a failed call attempt.

    error_code is one of errors.IntelligenceErrorCode (spec §9). retryable is
    decided by the adapter's error classification (errors.classify_provider_error),
    never inferred downstream — gateway.py reads err.retryable directly and
    stays provider-agnostic (spec §8 row 4).
    """

    def __init__(self, error_code: IntelligenceErrorCode, retryable: bool):
        self.error_code = error_code
        self.retryable = retryable
        super().__init__(error_code.value)


class ProviderAdapter(ABC):
    @abstractmethod
    def call(self, prompt: str, max_tokens: int, timeout: float) -> AdapterResult:
        """Make exactly one provider attempt. Raises ProviderError on failure — never returns a partial/error result."""
        raise NotImplementedError
