"""intelligence/config.py — the only module that reads intelligence/*'s env vars (spec §10). No AI SDK import here."""
from __future__ import annotations

import os


def _env_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    return raw.strip() if raw and raw.strip() else default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except (TypeError, ValueError):
        print(f'[intelligence.config] {name}="{raw}" is not a valid int — using default {default}')
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw.strip())
    except (TypeError, ValueError):
        print(f'[intelligence.config] {name}="{raw}" is not a valid float — using default {default}')
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


# Locked V1 values per spec §10 / §13.
NOVA_AI_PROVIDER = _env_str('NOVA_AI_PROVIDER', 'anthropic')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')  # secret — no default
NOVA_AI_MODEL = _env_str('NOVA_AI_MODEL', 'claude-haiku-4-5-20251001')
NOVA_AI_DAILY_REQUEST_LIMIT = _env_int('NOVA_AI_DAILY_REQUEST_LIMIT', 20)
NOVA_AI_DAILY_COST_LIMIT_USD = _env_float('NOVA_AI_DAILY_COST_LIMIT_USD', 0.25)
NOVA_AI_REQUEST_TIMEOUT_SECONDS = _env_int('NOVA_AI_REQUEST_TIMEOUT_SECONDS', 30)
NOVA_AI_CACHE_ENABLED = _env_bool('NOVA_AI_CACHE_ENABLED', True)
NOVA_AI_LOG_LEVEL = _env_str('NOVA_AI_LOG_LEVEL', 'INFO')
