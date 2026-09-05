"""intelligence/cache.py — input-hash keyed response cache (spec §6.1, §8 rows 6-7).

Reuses core.config's existing in-memory CACHE / cache_get / cache_set TTL
pattern. Intentionally ephemeral -- not held to §8.1's durability
requirement, and never touches budget state (a cache hit is not a provider
attempt).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional

from core.config import cache_get, cache_set


@dataclass(frozen=True)
class CachedResponse:
    content: str
    structured_data: Optional[dict]
    model: str
    input_tokens: int
    output_tokens: int


def build_cache_key(feature: str, input_data: dict, provider: str = '', model: str = '') -> str:
    """Key on what produced the content, not only on what was asked.

    A cached entry carries the provider and model that generated it. Keying on
    feature and input alone means changing NOVA_AI_MODEL keeps serving text the
    previous model wrote, under the new model's name -- so the identity of the
    producer belongs in the key.
    """
    normalized = json.dumps(input_data, sort_keys=True, default=str)
    digest = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    return f'intelligence:{feature}:{provider}:{model}:{digest}'


def get_cached_response(feature: str, input_data: dict, provider: str = '', model: str = '') -> Optional[CachedResponse]:
    cached = cache_get(build_cache_key(feature, input_data, provider, model))
    if cached is None:
        return None
    # The key already separates models, but an entry written before this change
    # -- or by a different code path -- is still checked rather than trusted.
    if model and getattr(cached, 'model', model) != model:
        return None
    return cached


def store_cached_response(feature: str, input_data: dict, value: CachedResponse, ttl_seconds: int,
                          provider: str = '', model: str = '') -> None:
    cache_set(build_cache_key(feature, input_data, provider, model), value, ttl_seconds)
