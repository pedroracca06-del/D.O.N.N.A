"""intelligence/envelope.py — shared response envelope shape (spec §11). Every gateway call returns this, success or failure."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class UsageInfo:
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None


@dataclass
class IntelligenceResponse:
    success: bool
    feature: str
    provider: str
    model: str
    request_id: str
    cached: bool
    latency_ms: int
    content: Optional[str] = None
    structured_data: Optional[dict] = None
    error_code: Optional[str] = None
    user_message: Optional[str] = None
    usage: UsageInfo = field(default_factory=UsageInfo)

    def to_dict(self) -> dict:
        return asdict(self)
