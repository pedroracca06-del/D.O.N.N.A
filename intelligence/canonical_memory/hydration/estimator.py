"""Exact deterministic byte accounting for CM-2."""

from .constants import BUDGET_UNIT, ESTIMATOR_ID


def normalize_rendered(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("rendered value must be text")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def estimate(text: str, estimator_id: str = ESTIMATOR_ID) -> int:
    if estimator_id != ESTIMATOR_ID:
        raise ValueError("ESTIMATOR_UNKNOWN")
    return len(normalize_rendered(text).encode("utf-8"))


__all__ = ["BUDGET_UNIT", "ESTIMATOR_ID", "estimate", "normalize_rendered"]
