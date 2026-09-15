"""Closed agent projections. Mission text cannot widen these sets."""

from .constants import PROJECTIONS


def projection_for(agent_id: str) -> tuple[str, frozenset[str]]:
    try:
        return agent_id, PROJECTIONS[agent_id]
    except (KeyError, TypeError) as exc:
        raise ValueError("UNKNOWN_AGENT") from exc


__all__ = ["projection_for"]
