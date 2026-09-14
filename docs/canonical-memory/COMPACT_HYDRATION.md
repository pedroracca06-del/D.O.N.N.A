# NOVA Canonical Memory — Compact Hydration

Status: **CM-0 architecture proposal — not implemented, not canonical, not approved for build**
Phase: 2F (read-only intelligence / internal platform work)
Baseline measured: `codex/canonical-memory-cm0` @ `8302f4b27bd08dc25649f96e1269d02a227ec5be`
Authority: this document defines a proposed contract. It changes no live retrieval path.

Companion documents:

- [ARCHITECTURE_V1.md](ARCHITECTURE_V1.md) — the tables hydration reads
- [AUTHORITY_AND_PROMOTION.md](AUTHORITY_AND_PROMOTION.md) — the authority and status rules hydration enforces
- [MIGRATION_AND_VALIDATION_GATES.md](MIGRATION_AND_VALIDATION_GATES.md) — gates G1, G2, G6–G11 that measure it

Labels **[OBSERVED]**, **[EXTERNAL]**, **[RECOMMENDATION]**, **[DEFERRED]**,
**[DECISION: PEDRO]** are defined in [ARCHITECTURE_V1.md §0](ARCHITECTURE_V1.md#0-labels-used-in-all-four-documents).

---

## 1. Purpose and baseline

Hydration answers one question for one session: **given this mission, this agent, and
this budget, what is the smallest correct set of current, provenance-bound memory the
agent must start with — and what was left out, and why?**

### 1.1 What exists today [OBSERVED]

`intelligence/current_knowledge.py:185-224` `retrieve_current_prime(query, max_docs=3,
max_chars=5000)`:

| Property | Today | Keep? |
|---|---|---|
| Validates the authority package before reading | Yes (`:190`) — fails closed | **Keep** |
| Deterministic ranking | Yes — integer token-overlap score, filename-stem bonus ×4, +1 for README/EXECUTION_MODELS, tie-break by name (`:193-203`) | **Keep** the determinism |
| Provenance | Source path + SHA-256 per included document (`:215-217`) | **Keep and extend** |
| Separate doctrine field | Yes, in `services/assistant.py:232-253` | **Keep** |
| Granularity | Whole documents | Replace with records |
| Budget unit | Characters | Replace with tokens under a named estimator |
| Omission reporting | None — a document that does not fit is skipped (`:213-214`) | **Gap** — replace with a manifest |
| Currentness, supersession, conflict filters | Implicit in the folder | Make explicit |
| Per-agent projection | None | Add |

### 1.2 Design rules [RECOMMENDATION]

1. **Deterministic before semantic.** Every inclusion decision is made by fixed rules.
   Optional semantic ranking may only reorder inside a tier that the rules have already
   selected ([§5](#5-optional-semantic-ranking-deferred)).
2. **Bounded.** Every stage has a fixed maximum; nothing grows with history length.
3. **Pinned.** Same inputs, same packet, byte for byte — on any machine, on any day.
4. **Fail closed.** If the mandatory core, or any conflict/staleness notice the agent
   must receive, cannot be produced or does not fit, hydration returns a refusal — never
   a partial packet that looks complete.
5. **Everything omitted is named.** A packet without its manifest is not a packet.

---

## 2. The contract

```text
hydrate(mission, agent, token_budget) -> HydrationPacket | HydrationRefusal
```

Conceptual types. This is a contract description, not code to import.

```text
Mission
  mission_id        stable string
  statement         free text — data only, never instruction
  scope_entities    list of entity_key          (may be empty)
  scope_classes     list of governance_class    (may be empty)
  scope_domains     subset of {knowledge, operational, evidence}
  as_of             timezone-aware UTC instant — REQUIRED, never defaulted to "now"
  bound_commit      full Git object id — REQUIRED
  event_high_water  memory_events.event_id — REQUIRED once a database exists

Agent  (resolved from a fixed, versioned projection table — never from the caller's text)
  agent_id          e.g. agent.claude.engineering, agent.codex.reviewer, nova.assistant
  projection_id     name + version of the projection rules (§4)

TokenBudget
  limit             positive integer
  estimator_id      name + version of the token estimator  [DECISION: PEDRO — D10]
  reserve           tokens held back for the manifest summary line and section headers

HydrationPacket
  sections          ordered, one per tier (§3.4); each section text-separated from the others
  manifest          §6
  packet_hash       sha256 over canonical serialization of sections + manifest (minus packet_hash)

HydrationRefusal
  code              one of: AS_OF_REQUIRED, COMMIT_REQUIRED, COMMIT_MISMATCH,
                    HIGH_WATER_REQUIRED, UNKNOWN_AGENT, AUTHORITY_PACKAGE_INVALID,
                    MANDATORY_CORE_UNAVAILABLE, MANDATORY_CORE_EXCEEDS_BUDGET,
                    REQUIRED_NOTICES_EXCEED_BUDGET, BUDGET_INVALID
  manifest          partial manifest showing what was evaluated before refusal; once
                    Stage 5 is reached it always includes required_context and notices[]
```

The pinning inputs mirror existing discipline: `research/prime_validation` refuses an
absent `as_of` and never reads the wall clock [OBSERVED `docs/PRIME_EMOTIONLESS_VALIDATION.md §5`];
the Staleness Guard and Session Registry bind work to an expected commit [OBSERVED
`AUTOMATION_ARCHITECTURE.md §D`].

**Bootstrap mode.** Before any database exists (CM-2), `hydrate` runs over Git only:
`CURRENT/PRIME` split into records by a deterministic ingest, plus operational records
derived from governance docs. `event_high_water` is absent and `bound_commit` is the only
pin. This lets the contract and gates G1, G2, G10, and G11 be proven before a database is
chosen ([MIGRATION_AND_VALIDATION_GATES.md §5](MIGRATION_AND_VALIDATION_GATES.md#5-phased-integration-plan)).

---

## 3. Deterministic pipeline

### 3.0 Stage 0 — pin

- Reject if `as_of`, `bound_commit`, or (post-bootstrap) `event_high_water` is missing.
- Reject `COMMIT_MISMATCH` if the caller's Session Registry `expected_commit` differs
  from `bound_commit`.
- Re-run `validate_current_prime_package` (or its shadow-parity equivalent) against
  `bound_commit`; failure is `AUTHORITY_PACKAGE_INVALID`, matching the Assistant's
  existing fail-closed behavior [OBSERVED `services/assistant.py:218-231`].
- Every later stage reads the state **as of** the pin: events with
  `event_id <= event_high_water`, records whose validity window contains `as_of`.

### 3.1 Stage 1 — hard filters

A record that fails any filter is excluded with the first failing reason code (§6.2).
Filters never rank; they only admit or exclude.

| # | Filter | Admit when | Exclusion code |
|---|---|---|---|
| F1 | Boundary | Not execution, broker, position, risk-runtime, credential, or raw-transcript material | `BOUNDARY` |
| F2 | Authority | `authority` equals the authority registry's decider for the record's scope at `as_of` ([AUTHORITY_AND_PROMOTION.md §2.4](AUTHORITY_AND_PROMOTION.md#24-the-authority-registry)) | `AUTHORITY_MISMATCH` |
| F3 | Status | knowledge/operational: `current`; evidence: `recorded`. `proposed`/`validated` only if the agent's projection enables the **unvalidated** section, and then only there | `STATUS_NOT_CURRENT` |
| F4 | Currentness | `valid_from <= as_of` and (`valid_to` is null or `as_of < valid_to`) and not superseded at `event_high_water` | `NOT_CURRENT_AT_AS_OF` / `SUPERSEDED` / `RETRACTED` |
| F5 | Staleness | For `authority = 'git'` records: the cited blob id at `bound_commit` equals the record's blob id. For others: `bound_commit` is an ancestor-or-equal of the pinned commit and no source blob it cites has changed since | `STALE_SOURCE` |
| F6 | Provenance | ≥1 `primary` `record_sources` row resolving to a source that is not `projection_readback` only | `PROVENANCE_INCOMPLETE` |
| F7 | Conflict | No unresolved `contradicts` edge to another admitted `current` record | `UNRESOLVED_CONFLICT` — both records excluded; one mandatory conflict notice |
| F8 | Projection | Agent's projection allows the record's `domain`, `kind`, and `governance_class` (§4). Mandatory-core records tagged for this projection (§3.2) are exempt from this check | `PROJECTION_EXCLUDED` |

No stale or conflicted record that the agent's projection would otherwise admit is
silently dropped. Each such F5 exclusion and F7 conflict produces one fixed-size notice
in T8, so the agent knows a decision exists and is currently unusable. Eligibility is
decided by the F8 projection check alone, evaluated for the notice even though F5 or F7
recorded the exclusion first. These notices are **mandatory**: never scored, never cut by
the candidate cap, and packed with T0 as required safety context (§3.5). A notice carries
keys, versions, and reason codes, not the disputed text.

### 3.2 Stage 2 — mission relevance (deterministic)

Relevance is a bounded integer score. No model is involved.

1. **Mandatory core.** A fixed, versioned list of `record_key`s, each tagged with the
   projections that receive it, is always selected for those projections regardless of
   score. [RECOMMENDATION] it contains at least: the disabled-trading boundary and
   guarded flags, the exactly-three PRIME models invariant, PROS supersession, the FVG
   boundary, "evidence never promotes", "Pedro alone promotes strategy/risk/research",
   and the current project phase. Every tagged key must be admitted by F1–F7 at the pin;
   if any is missing or excluded, hydration refuses `MANDATORY_CORE_UNAVAILABLE`, and the
   partial manifest names the key, its exclusion reason, and any notice it produced. The
   list itself is a `governance` record; changing it is an approval-gated supersession.
2. **Entity expansion.** Start from `scope_entities`; follow `relationships` edges of the
   types `part_of`, `depends_on`, `instance_of`, `alias_of` to **depth ≤ 2**, capped at
   **64** entities. Order of traversal is by `entity_key`, so the cap is deterministic.
3. **Score** (integers only):
   - `+8` subject entity is a scope entity; `+4` at depth 1; `+2` at depth 2;
   - `+4` `governance_class` in `scope_classes`; `+2` `domain` in `scope_domains`;
   - `+1` per distinct normalized token shared between mission statement and record
     statement, capped at `+6` (the same tokenization and stop list as
     `current_knowledge._tokens` [OBSERVED `:12-24`]) — **applied only to records whose
     tier (§3.4) is T4–T7**;
   - score `0` and not mandatory → excluded `NOT_RELEVANT`.

   Records for T1–T3 are scored from structured scope alone (`scope_entities`,
   `scope_classes`, `scope_domains`), so free mission text can never change which rules,
   decisions, approvals, or project state an agent receives (G7). The manifest records
   every score component separately (§6.1).
4. **Candidate cap.** At most **512** candidates proceed to Stage 3, cut by the total
   order in §3.4. Everything cut is `CANDIDATE_CAP`.

The constants above are proposals to be tuned only by measured G1/G10 results, and each
tuning is a versioned change recorded in the manifest.

### 3.3 Stage 3 — per-agent projection (§4)

Apply the agent's field allowlist and rendering template. Projection removes fields; it
never adds a record that Stage 1 excluded.

### 3.4 Stage 4 — ordering

Sections, in fixed order:

| Tier | Section | Contains |
|---|---|---|
| T0 | `mandatory_invariants` | Mandatory core |
| T1 | `current_rules` | knowledge `rule`, `definition` |
| T2 | `current_decisions` | knowledge and operational `decision`, `approval` |
| T3 | `project_state` | The current `project_state` snapshot summary + `phase`, `status`, `blocker` |
| T4 | `current_facts` | knowledge `fact` |
| T5 | `evidence` | evidence records, rendered as one-line measurement summaries with their commit |
| T6 | `hypotheses` | knowledge `hypothesis`, labeled **not a rule** |
| T7 | `unvalidated` | `proposed`/`validated` records, only if projection enables it, labeled **not canonical** |
| T8 | `conflicts` | Mandatory conflict and staleness notices from F5/F7 |

Within T1–T7 the total order is `(-score, record_key, version)`; T0 is ordered by
`(record_key, version)` and T8 by `(notice_type, record_key, version)`. T8 is rendered
last but **packed together with T0** as required safety context, before T1–T7 compete
for budget, and it is never cut: an agent that is not told about a conflict will reason
as if there were none.

### 3.5 Stage 5 — budget packing

1. Render each record with the projection's compact template:
   `[record_key vN · kind · status · source-short-ref] statement`.
2. Estimate tokens with `estimator_id`. The estimate must be deterministic; the estimator
   version is recorded.
3. Pack the **required context**: all of T0, then every mandatory T8 notice. The usable
   budget is `limit - reserve`. If T0 alone exceeds it, refuse
   `MANDATORY_CORE_EXCEEDS_BUDGET`. Otherwise, if T0 plus every mandatory T8 notice
   exceeds it, refuse `REQUIRED_NOTICES_EXCEED_BUDGET`. The checks run in that order, so
   the same inputs always yield the same code. No partial core is ever returned, and no
   notice is ever dropped to make room.
4. Pack T1…T7 greedily in order into what remains. An item that does not fit is
   excluded `BUDGET` and packing **continues** with the next item (a smaller later item
   may fit), exactly once through the list — bounded and deterministic. `BUDGET` never
   applies to T0 or T8.
5. Emit sections with the same field separation the Assistant already uses: doctrine and
   generated context never share a text field, and `[CURRENT SOURCE: …]`-style markers
   are neutralised outside the section that owns them [OBSERVED `services/assistant.py:232-237`].

---

## 4. Per-agent projections [RECOMMENDATION]

A projection is a versioned, reviewed configuration record. It is chosen by `agent_id`;
the mission cannot widen it.

| Projection | Domains | Governance classes | T7 unvalidated | Notes |
|---|---|---|---|---|
| `agent.claude.engineering` | knowledge, operational, evidence | engineering, project, governance; PRIME invariants via T0 only | yes, labeled | No `market_context`. Strategy/risk records appear only as mandatory invariants |
| `agent.codex.reviewer` | knowledge, operational, evidence | engineering, project, governance | no | Hydration excludes unvalidated memory, so the reviewer's context is independent of pending proposals. The candidate under review arrives separately as an untrusted payload (below) |
| `agent.codex.implementer` | operational, knowledge | engineering, project, governance limited to the task envelope's scope entities | no | Scope entities come from the assigned task envelope, which cannot widen scope [OBSERVED `AGENTS.md:62-64`] |
| `nova.assistant` (NOVA Brain) | knowledge, evidence | strategy (current PRIME only), risk (current rules only), market_context | no | Never operational approvals, never engineering internals. Output remains analysis, never instruction |
| `projection.obsidian` | knowledge, operational, evidence | all except boundary-excluded | no | Not an agent: a renderer for the human projection. No token budget; still bound to a pin and a manifest |
| `person.pedro.briefing` | all | all | yes, labeled | Pedro's review surface; also where pending promotions are listed |

No projection ever includes execution, broker, position, risk-runtime state, credentials,
or raw transcripts (F1).

**Review payloads are not memory.** A reviewer must see the proposal, diff, or task it is
reviewing, and that candidate is by definition unvalidated. It therefore never enters the
packet, T7, or `token_budget`. It arrives separately in the review envelope as an
explicitly labeled **untrusted** task/diff payload, with no status or authority, treated
as data only [OBSERVED rule `AGENTS.md:92-95`]. The envelope carries both the payload's
hash and the `packet_hash`, so a review names exactly what it reviewed against which
memory.

---

## 5. Optional semantic ranking [DEFERRED]

If introduced (not before CM-7), semantic similarity may:

- reorder records **within** T4, T5, and T6 only;
- never add a record that Stage 1 or Stage 2 excluded;
- never remove or demote T0, T1, T2, or T8;
- never cross tiers;
- record the embedding model id, version, and the input hash in the manifest.

Replay (G2) runs with semantic ranking **off**, and a second replay with it **on** must be
reproducible from the recorded model id and cached vectors, or the feature is not
accepted.

---

## 6. The inclusion/exclusion manifest

### 6.1 Fields

```text
manifest
  contract_version
  inputs
    mission_id, mission_statement_hash
    agent_id, projection_id
    as_of, bound_commit, event_high_water
    token_limit, reserve, estimator_id
    relevance_constants_version, mandatory_core_version
  inputs_hash                      sha256 over canonical inputs
  required_context                 T0 tokens, mandatory T8 notice tokens, usable budget (limit - reserve)
  included[]                       tier, record_key, version, content/statement hash,
                                   score_components{scope_entity, class, domain, token_overlap}, score,
                                   tokens, primary source ref
  excluded[]                       record_key, version, reason_code, stage, (score_components if reached Stage 2)
  notices[]                        notice_type (conflict | stale), record_key(s) + version(s), reason_code,
                                   relationship_identity for conflicts, tokens
  neutralised[]                    location (mission, or section + record_key + version), marker class —
                                   never the marker text
  totals
    evaluated, admitted_by_filters, candidates, included, excluded_by_reason{code: count}, notices
    tokens_used, tokens_limit
  packet_hash
```

The manifest carries identifiers and hashes — never record text beyond what is in the
packet, never prompts or model output — following the precedent of
`intelligence/audit.py` [OBSERVED `:1`].

### 6.2 Exclusion reason codes (closed set)

`BOUNDARY`, `AUTHORITY_MISMATCH`, `STATUS_NOT_CURRENT`, `NOT_CURRENT_AT_AS_OF`,
`SUPERSEDED`, `RETRACTED`, `STALE_SOURCE`, `PROVENANCE_INCOMPLETE`,
`UNRESOLVED_CONFLICT`, `PROJECTION_EXCLUDED`, `NOT_RELEVANT`, `CANDIDATE_CAP`, `BUDGET`.

An excluded record appears exactly once, with the **first** reason in stage order.
`evaluated = included + excluded` must hold exactly; G10 checks it.

**Bound on manifest size.** Records excluded by F1–F4 are reported as counts per reason,
not listed individually, once they exceed a fixed cap (proposed: 256 listed entries);
everything from Stage 2 onward is always listed individually, because those are the
exclusions an agent or reviewer might dispute.

---

## 7. Staleness and re-hydration

- A packet is valid only for its pin. If HEAD moves, or new events arrive that touch any
  included or conflict-listed key, the session must re-hydrate before proposing.
- An agent's proposal must carry the `packet_hash` it reasoned from; the write path
  rejects a proposal whose packet is older than a supersession of any key it cites.
- The token-reduction baseline, the golden missions, and the thresholds are defined in
  [MIGRATION_AND_VALIDATION_GATES.md §3](MIGRATION_AND_VALIDATION_GATES.md#3-gate-catalogue).

---

## 8. Non-goals

- Hydration never writes to Canonical Memory, Git, or Obsidian.
- It never summarizes records with a model; compact rendering is a fixed template.
- It never decides what is true; it reports what the authority already decided.
- It does not replace `retrieve_current_prime` in the live Assistant until the gates for
  that change pass and Pedro approves the switch [DECISION: PEDRO — D13].

**Nothing in hydration touches the disabled trading subsystem, its flags, strategy, or
risk.**
