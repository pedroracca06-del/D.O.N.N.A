"""intelligence/audit.py — usage/observability log (spec §12). Never stores prompts, responses, API keys, or raw exception text.

Ring-buffer JSON file at DATA_DIR/nova_intelligence_usage_log.json, following
the existing delivery/signal_log.py convention (threading.Lock, capped
entry count). Atomic tmp-file + os.replace writes. A write failure is
swallowed -- an audit-logging bug must never take down the request it is
trying to record, and must never leak record content into an exception.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.config import DATA_DIR

AUDIT_FILE: Path = DATA_DIR / 'nova_intelligence_usage_log.json'
_MAX_ENTRIES = 5_000

_lock = threading.Lock()


@dataclass
class AuditRecord:
    request_id: str
    feature: str
    provider: str
    model: str
    cached: bool
    success: bool
    error_code: Optional[str]
    input_tokens_estimate: Optional[int]
    input_tokens_actual: Optional[int]
    output_tokens: Optional[int]
    estimated_cost_usd: Optional[float]
    latency_ms: int
    timestamp: str
    malformed_response_length: Optional[int] = None
    malformed_response_hash: Optional[str] = None


def _load(path: Path) -> list:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def _save(path: Path, entries: list) -> None:
    tmp = path.with_suffix('.tmp')
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(entries, f, indent=2, default=str)
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def write_record(record: AuditRecord, path: Optional[Path] = None) -> None:
    path = path or AUDIT_FILE
    try:
        with _lock:
            entries = _load(path)
            entries.append(asdict(record))
            if len(entries) > _MAX_ENTRIES:
                entries = entries[-_MAX_ENTRIES:]
            _save(path, entries)
    except Exception:
        # Never let an audit-log failure surface as an unhandled exception or
        # take down the request it is trying to record.
        pass


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
