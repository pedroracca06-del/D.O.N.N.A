"""Deterministic, provenance-bearing packet rendering."""

from intelligence.canonical_memory import hashing
from .constants import TIERS


def record_line(record, source) -> str:
    statement = record.statement.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ")
    return f"- {record.record_key}@{record.version} | {statement} | {source.stable_ref}"


def notice_line(notice) -> str:
    return f"- {notice.notice_type}: {', '.join(sorted(notice.record_keys))}"


def render_sections(rows_by_tier, notices) -> tuple[tuple[tuple[str, tuple[str, ...]], ...], str]:
    sections = []
    rendered = []
    for tier in TIERS:
        if tier == "conflicts":
            lines = tuple(notice_line(n) for n in notices)
        else:
            lines = tuple(rows_by_tier.get(tier, ()))
        sections.append((tier, lines))
        rendered.append(f"## {tier}")
        rendered.extend(lines)
    text = "\n".join(rendered) + "\n"
    return tuple(sections), text


def packet_hash(manifest, rendered: str) -> str:
    return hashing.canonical_hash({"manifest": manifest, "rendered": rendered})


__all__ = ["notice_line", "packet_hash", "record_line", "render_sections"]
