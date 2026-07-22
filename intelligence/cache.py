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


def build_cache_key(feature: str, input_data: dict) -> str:
    normalized = json.dumps(input_data, sort_keys=True, default=str)
    digest = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    return f'intelligence:{feature}:{digest}'


def get_cached_response(feature: str, input_data: dict) -> Optional[CachedResponse]:
    return cache_get(build_cache_key(feature, input_data))


def store_cached_response(feature: str, input_data: dict, value: CachedResponse, ttl_seconds: int) -> None:
    cache_set(build_cache_key(feature, input_data), value, ttl_seconds)
