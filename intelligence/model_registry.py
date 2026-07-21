"""intelligence/model_registry.py — reviewed table of supported NOVA_AI_MODEL values + per-token pricing (spec §8.2).

An unregistered NOVA_AI_MODEL must fail closed (MODEL_NOT_SUPPORTED) rather than
proceed with an unverified cost estimate — "unknown cost" is never "assume zero".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ModelPricing:
    input_price_per_mtok: float
    output_price_per_mtok: float


# Reviewed against platform.claude.com/docs/en/pricing. Update only after
# manually re-checking published pricing for the model added.
MODEL_REGISTRY: dict[str, ModelPricing] = {
    'claude-haiku-4-5-20251001': ModelPricing(
        input_price_per_mtok=1.00,
        output_price_per_mtok=5.00,
    ),
}


def get_model_pricing(model_id: str) -> Optional[ModelPricing]:
    return MODEL_REGISTRY.get(model_id)
