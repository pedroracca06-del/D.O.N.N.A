"""intelligence/gateway.py — request_intelligence(), the only function application code will call (spec §6.1, §7.1).

Structural skeleton only (spec §14 commit #2): validates the feature name
against the registry and stops there. Budget checks, cache checks, and the
provider adapter are wired in by commits #3-#4 — until then this makes no
live provider call and no feature calls it.
"""
from __future__ import annotations

from .registry import FEATURE_REGISTRY


def request_intelligence(feature: str, input_data: dict, user_id: str, request_id: str) -> dict:
    if feature not in FEATURE_REGISTRY:
        raise ValueError(f'unknown feature "{feature}" — must be one of {sorted(FEATURE_REGISTRY)}')
    raise NotImplementedError(
        'intelligence.gateway.request_intelligence is not wired to a provider yet '
        '(spec §14 commits #3-#4 add the adapter, budget, and cache).'
    )
