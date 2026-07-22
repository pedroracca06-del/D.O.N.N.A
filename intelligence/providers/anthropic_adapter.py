"""intelligence/providers/anthropic_adapter.py — the one V1 provider adapter (spec §5/§13 decision 9, §6.1).

The only file in the codebase permitted to `import anthropic` or construct
an Anthropic client (spec §6.1, §10). Configuration is read through
intelligence.config, never via a fresh os.getenv call here. Makes exactly
one provider attempt per call() — no retry loop; NOVA's own single
controlled retry (spec §8 row 4) is gateway-level orchestration, added in a
later commit.
"""
from __future__ import annotations

import anthropic

from .. import config
from ..errors import classify_provider_error
from .base import AdapterResult, ProviderAdapter, ProviderError


def _raise_provider_error(kind: str, cause: BaseException) -> None:
    classification = classify_provider_error(kind)
    raise ProviderError(classification.error_code, classification.retryable) from cause


class AnthropicAdapter(ProviderAdapter):
    def call(self, prompt: str, max_tokens: int, timeout: float) -> AdapterResult:
        if not config.ANTHROPIC_API_KEY:
            classification = classify_provider_error('missing_config')
            raise ProviderError(classification.error_code, classification.retryable)

        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=0)
        try:
            response = client.with_options(timeout=timeout).messages.create(
                model=config.NOVA_AI_MODEL,
                max_tokens=max_tokens,
                messages=[{'role': 'user', 'content': prompt}],
            )
        except anthropic.AuthenticationError as exc:
            _raise_provider_error('authentication', exc)
        except anthropic.PermissionDeniedError as exc:
            kind = 'permission_denied_billing' if getattr(exc, 'type', None) == 'billing_error' else 'permission_denied_other'
            _raise_provider_error(kind, exc)
        except anthropic.RateLimitError as exc:
            _raise_provider_error('rate_limited', exc)
        except anthropic.NotFoundError as exc:
            _raise_provider_error('not_found', exc)
        except anthropic.APIStatusError as exc:
            status = getattr(exc, 'status_code', None)
            # 529 (overloaded) keeps the existing RATE_LIMITED mapping, never
            # the 5xx-retryable path. Anything that isn't a genuine int in
            # 500-599 fails safely as permanent/non-retryable — an unknown or
            # missing status must never be assumed retryable.
            if status == 529:
                kind = 'rate_limited'
            elif isinstance(status, int) and not isinstance(status, bool) and 500 <= status <= 599:
                kind = 'status_error_retryable'
            else:
                kind = 'status_error_permanent'
            _raise_provider_error(kind, exc)
        except anthropic.APITimeoutError as exc:
            _raise_provider_error('timeout', exc)
        except anthropic.APIConnectionError as exc:
            _raise_provider_error('connection_error', exc)

        text = ''.join(block.text for block in response.content if block.type == 'text')
        return AdapterResult(
            text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=response.model,
        )
