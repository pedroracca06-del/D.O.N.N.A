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
    """Read the log, preserving anything unreadable instead of dropping it.

    Returning an empty list for content that could not be parsed meant the very
    next write replaced the file, and whatever it held was gone. An audit log
    that quietly discards its own contents when they look wrong is the one that
    matters least when something has gone wrong. Unreadable content is moved
    aside under a timestamped name so it survives for inspection.
    """
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(data, list):
            return data
    except Exception:
        pass
    if not _quarantine(path):
        # The content could not be preserved. The write MUST NOT go ahead:
        # _save replaces the file via os.replace, which would succeed and
        # destroy the very evidence that could not be moved aside.
        raise _EvidenceAtRisk(
            'unreadable audit content could not be preserved; refusing to '
            'overwrite it')
    return []


class _EvidenceAtRisk(Exception):
    """Raised when writing would destroy content that could not be preserved."""


def _quarantine(path: Path) -> bool:
    """Move unreadable log content aside. True when it is safely preserved."""
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    try:
        os.replace(path, path.with_name(path.name + '.unreadable-' + stamp))
        return True
    except OSError:
        return False


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
                # A bounded ring buffer is deliberate -- this is an
                # observability log, not the execution trace -- but the
                # overflow is recorded so a reader can tell truncation from an
                # empty history.
                dropped = len(entries) - _MAX_ENTRIES
                entries = entries[-_MAX_ENTRIES:]
                entries[0] = dict(entries[0], _truncated_before=dropped)
            _save(path, entries)
    except Exception:
        # Never let an audit-log failure surface as an unhandled exception or
        # take down the request it is trying to record. Losing THIS record is
        # the accepted cost; losing records already written is not, which is
        # why the path above refuses to write rather than overwrite.
        pass


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
