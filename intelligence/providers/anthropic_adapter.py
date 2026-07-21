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


class AnthropicAdapter(ProviderAdapter):
    def call(self, prompt: str, max_tokens: int, timeout: float) -> AdapterResult:
        if not config.ANTHROPIC_API_KEY:
            raise ProviderError(classify_provider_error('missing_config'))

        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=0)
        try:
            response = client.with_options(timeout=timeout).messages.create(
                model=config.NOVA_AI_MODEL,
                max_tokens=max_tokens,
                messages=[{'role': 'user', 'content': prompt}],
            )
        except anthropic.AuthenticationError as exc:
            raise ProviderError(classify_provider_error('authentication')) from exc
        except anthropic.PermissionDeniedError as exc:
            kind = 'permission_denied_billing' if getattr(exc, 'type', None) == 'billing_error' else 'permission_denied_other'
            raise ProviderError(classify_provider_error(kind)) from exc
        except anthropic.RateLimitError as exc:
            raise ProviderError(classify_provider_error('rate_limited')) from exc
        except anthropic.NotFoundError as exc:
            raise ProviderError(classify_provider_error('not_found')) from exc
        except anthropic.APIStatusError as exc:
            kind = 'rate_limited' if getattr(exc, 'status_code', None) == 529 else 'status_error'
            raise ProviderError(classify_provider_error(kind)) from exc
        except anthropic.APITimeoutError as exc:
            raise ProviderError(classify_provider_error('timeout')) from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError(classify_provider_error('connection_error')) from exc

        text = ''.join(block.text for block in response.content if block.type == 'text')
        return AdapterResult(
            text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=response.model,
        )
