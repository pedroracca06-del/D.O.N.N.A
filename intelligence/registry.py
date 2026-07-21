"""intelligence/registry.py — the one place a V1 feature is "turned on" (spec §6.1). Exactly the three V1 features (spec §3) — nothing else.

prompt_module names the module that will hold the feature's prompt template
(spec §6's prompts/ package) as a string, not an import — those modules land
in their own migration commits (spec §14 commits #5-#7), not this one.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class FeatureConfig:
    name: str
    prompt_module: str
    max_output_tokens: int
    cache_ttl_seconds: Optional[int]  # None means no caching (spec §8 row 7)
    timeout_seconds: int


FEATURE_REGISTRY: dict[str, FeatureConfig] = {
    'assistant': FeatureConfig(
        name='assistant',
        prompt_module='intelligence.prompts.assistant',
        max_output_tokens=400,
        cache_ttl_seconds=None,
        timeout_seconds=30,
    ),
    'journal_review': FeatureConfig(
        name='journal_review',
        prompt_module='intelligence.prompts.journal_review',
        max_output_tokens=800,
        cache_ttl_seconds=24 * 60 * 60,
        timeout_seconds=30,
    ),
    'market_summary': FeatureConfig(
        name='market_summary',
        prompt_module='intelligence.prompts.market_summary',
        max_output_tokens=500,
        cache_ttl_seconds=30 * 60,
        timeout_seconds=30,
    ),
}
