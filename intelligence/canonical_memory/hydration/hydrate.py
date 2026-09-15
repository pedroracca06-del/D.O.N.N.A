"""Pure staged CM-2 hydration over an immutable snapshot."""

from collections import defaultdict
import unicodedata

from intelligence.canonical_memory import hashing, schema as cm1_schema
from .constants import CANDIDATE_CAP, CURRENTNESS_MODEL, MANDATORY_CORE_KEYS, SPEC_VERSION, TIERS
from .estimator import estimate
from .projections import projection_for
from .relevance import score, tier_for
from .render import notice_line, packet_hash, record_line, render_sections
from .schema import Budget, Exclusion, HydrationError, HydrationPacket, HydrationRefusal, MemorySnapshot, Mission, Notice


def _refuse(code: str, detail: str) -> HydrationRefusal:
    return HydrationRefusal(code, detail)


def _source_indexes(snapshot):
    sources = {source.source_identity: source for source in snapshot.sources}
    primary = {}
    for link in snapshot.links:
        if link.role == cm1_schema.ROLE_PRIMARY and link.source_identity in sources:
            primary[(link.record_key, link.version)] = sources[link.source_identity]
    return primary


def _notices(snapshot):
    return tuple(
        Notice(rel.relationship_type, tuple(sorted(rel.record_keys)))
        for rel in sorted(snapshot.relationships, key=lambda r: (r.relationship_type, r.record_keys))
    )


def _base_manifest(snapshot, mission, agent_id, budget):
    inputs = {
        "agent_id": agent_id, "as_of": mission.as_of,
        "bound_commit": snapshot.commit_oid, "budget_limit": budget.limit,
        "budget_reserve": budget.reserve, "budget_unit": budget.unit,
        "currentness_model": CURRENTNESS_MODEL, "estimator_id": budget.estimator_id,
        "ingest_result_hash": snapshot.ingest_result_hash,
        "mission_id": mission.mission_id,
        "mission_statement_hash": hashing.text_hash(mission.statement),
        "schema_version": snapshot.schema_version, "snapshot_spec_version": snapshot.spec_version,
        "tree_oid": snapshot.tree_oid,
    }
    return inputs, hashing.canonical_hash(inputs)


def hydrate(snapshot: MemorySnapshot, mission: Mission, agent_id: str, budget: Budget):
    if not isinstance(snapshot, MemorySnapshot) or not isinstance(mission, Mission) or not isinstance(budget, Budget):
        raise HydrationError("INPUT_TYPE", "hydrate requires validated CM-2 types")
    if mission.bound_commit != snapshot.commit_oid:
        return _refuse("COMMIT_MISMATCH", "mission and snapshot commits differ")
    if not snapshot.authority_package_valid:
        return _refuse("AUTHORITY_PACKAGE_INVALID", "authority package failed validation")
    if not (mission.scope_entities or mission.scope_classes or mission.scope_domains):
        return _refuse("SCOPE_EMPTY", "all structured scope collections are empty")
    try:
        projection_id, allowed_classes = projection_for(agent_id)
    except ValueError:
        return _refuse("UNKNOWN_AGENT", "agent has no closed projection")

    current_by_key = {}
    for record in snapshot.records:
        if record.status == "current":
            prior = current_by_key.get(record.record_key)
            if prior is None or record.version > prior.version:
                current_by_key[record.record_key] = record
    missing = tuple(key for key in MANDATORY_CORE_KEYS if key not in current_by_key)
    if missing:
        return _refuse("MANDATORY_CORE_UNAVAILABLE", ",".join(missing))
    primary = _source_indexes(snapshot)
    conflicted = {key for rel in snapshot.relationships for key in rel.record_keys}
    excluded = []
    admitted = []
    mandatory = set(MANDATORY_CORE_KEYS)
    mandatory_identities = {(key, current_by_key[key].version) for key in mandatory}

    for record in snapshot.records:
        code = None
        ident = (record.record_key, record.version)
        if record.authority != "git": code = "AUTHORITY_MISMATCH"
        elif record.status == "superseded": code = "SUPERSEDED"
        elif record.status == "retracted": code = "RETRACTED"
        elif record.status not in {"current", "recorded"}: code = "STATUS_NOT_CURRENT"
        elif ident not in primary: code = "PROVENANCE_INCOMPLETE"
        elif record.record_key in conflicted: code = "UNRESOLVED_CONFLICT"
        elif record.record_key not in mandatory and record.governance_class not in allowed_classes: code = "PROJECTION_EXCLUDED"
        else:
            value = score(record, mission)
            if record.record_key not in mandatory and value == 0: code = "NOT_RELEVANT"
            else: admitted.append((record, value, primary[ident]))
        is_mandatory = ident in mandatory_identities
        if code:
            if is_mandatory:
                return _refuse("MANDATORY_CORE_UNAVAILABLE", f"{record.record_key}:{code}")
            excluded.append(Exclusion(record.record_key, record.version, code))

    admitted.sort(key=lambda item: (
        0 if (item[0].record_key, item[0].version) in mandatory_identities else 1,
        TIERS.index(tier_for(item[0])), -item[1], item[0].record_key, item[0].version,
    ))
    if len(admitted) > CANDIDATE_CAP:
        for record, _, _ in admitted[CANDIDATE_CAP:]:
            excluded.append(Exclusion(record.record_key, record.version, "CANDIDATE_CAP"))
        admitted = admitted[:CANDIDATE_CAP]

    notices = _notices(snapshot)
    available = budget.limit - budget.reserve
    chosen = []
    header_cost = sum(estimate(f"## {tier}\n") for tier in TIERS)
    notice_cost = sum(estimate(notice_line(n) + "\n") for n in notices)
    mandatory_rows = [item for item in admitted if (item[0].record_key, item[0].version) in mandatory_identities]
    mandatory_cost = sum(estimate(record_line(record, source) + "\n") for record, _, source in mandatory_rows)
    if header_cost + mandatory_cost > available:
        return _refuse("MANDATORY_CORE_EXCEEDS_BUDGET", "mandatory core and section framing do not fit")
    if header_cost + mandatory_cost + notice_cost > available:
        return _refuse("REQUIRED_NOTICES_EXCEED_BUDGET", "mandatory notices do not fit")
    used = header_cost + notice_cost
    for record, value, source in admitted:
        line = record_line(record, source)
        cost = estimate(line + "\n")
        if used + cost > available:
            excluded.append(Exclusion(record.record_key, record.version, "BUDGET"))
            continue
        chosen.append((record, value, source, line, cost))
        used += cost
    rows = defaultdict(list)
    included = []
    for record, value, source, line, cost in chosen:
        tier = "mandatory_invariants" if (record.record_key, record.version) in mandatory_identities else tier_for(record)
        rows[tier].append(line)
        included.append({"record_key": record.record_key, "version": record.version, "tier": tier, "score": value, "bytes": cost})
    sections, rendered = render_sections(rows, notices)
    inputs, inputs_hash = _base_manifest(snapshot, mission, projection_id, budget)
    manifest = {
        "spec_version": SPEC_VERSION, "inputs": inputs, "inputs_hash": inputs_hash,
        "included": included,
        "excluded": [{"record_key": e.record_key, "version": e.version, "code": e.code} for e in sorted(excluded, key=lambda e: (e.record_key, e.version))],
        "notices": [{"type": n.notice_type, "record_keys": list(n.record_keys)} for n in notices],
        "evaluated": len(snapshot.records), "included_count": len(included),
        "excluded_count": len(excluded), "rendered_bytes": estimate(rendered),
        "neutralised": ["mission_statement"] if cm1_schema.SOURCE_MARKER_RE.search(unicodedata.normalize("NFKC", mission.statement)) else [],
    }
    if manifest["rendered_bytes"] > available:
        raise HydrationError("BUDGET_ACCOUNTING", "rendered packet exceeded validated budget")
    return HydrationPacket(sections, manifest, rendered, packet_hash(manifest, rendered))


def is_packet_fresh(packet: HydrationPacket, commit_oid: str) -> bool:
    return packet.manifest["inputs"]["bound_commit"] == commit_oid


__all__ = ["hydrate", "is_packet_fresh"]
