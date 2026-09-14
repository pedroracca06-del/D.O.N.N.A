# NOVA Canonical Memory — Architecture Assessment and V1 Design

Status: **CM-0 architecture proposal — not implemented, not canonical, not approved for build**
Phase: 2F (read-only intelligence / internal platform work)
Baseline measured: `codex/canonical-memory-cm0` @ `8302f4b27bd08dc25649f96e1269d02a227ec5be`
Authority: this document describes a proposed design. It grants nothing, changes no
runtime, and adds no dependency.

Companion documents:

- [AUTHORITY_AND_PROMOTION.md](AUTHORITY_AND_PROMOTION.md) — who decides each fact, the status machine, promotion and supersession
- [COMPACT_HYDRATION.md](COMPACT_HYDRATION.md) — `hydrate(mission, agent, token_budget)` and the inclusion/exclusion manifest
- [MIGRATION_AND_VALIDATION_GATES.md](MIGRATION_AND_VALIDATION_GATES.md) — phases CM-1…, measurable gates, cutover, rollback, STOP/GO

---

## 0. Labels used in all four documents

| Label | Meaning |
|---|---|
| **[OBSERVED]** | Read directly in this repository at the baseline commit above. File and line references are given. Nothing was executed — no test, shell, Git, or network call was made to produce these observations |
| **[EXTERNAL]** | A claim about third-party technology, taken from the official documentation links supplied with the CM-0 task. Not re-fetched in this session |
| **[RECOMMENDATION]** | Proposed design. Not built, not approved |
| **[DEFERRED]** | Deliberately outside V1. Named so that it is not silently assumed |
| **[DECISION: PEDRO]** | Cannot be settled by an agent. Collected with IDs in [MIGRATION_AND_VALIDATION_GATES.md §7](MIGRATION_AND_VALIDATION_GATES.md#7-decisions-still-requiring-pedro) |

No gate result, benchmark, token count, or performance figure appears anywhere in this
document set, because none has been measured.

---

## 1. The problem Canonical Memory solves

NOVA is now worked on by more than one agent (Claude Code / Cowork, Codex in review and
bounded-implementation modes) and reasons through NOVA Brain surfaces (Assistant,
Journal Review, Market Summary). Each session begins without memory. What it knows is
whatever it is handed, and today "what it is handed" is assembled from several places
that were never designed to agree with each other:

- Git-authoritative Markdown doctrine (`nova_knowledge_core/CURRENT/PRIME/`);
- governance and project documents (`docs/claude-cowork/**`, `docs/ROADMAP.md`);
- runtime JSON under `data/` (session memory, market memory, reasoning trace, journal
  workspace, assistant state);
- planned Obsidian namespaces;
- conversation history and hand-off prose that lives nowhere durable.

There is no structured record of *which statement is currently true, who decided it,
what it replaced, and what evidence it rests on*. The consequence is predictable:
facts get re-derived per session, stale statements survive next to their replacements,
and two stores can each believe they decide the same fact.

Canonical Memory is the proposed answer: **one structured, versioned, provenance-bound
record of promoted knowledge and operational state, from which every agent is hydrated
deterministically, with Git remaining the authority for code and its history and
Obsidian becoming a generated human-readable projection.**

**Agents change. NOVA remembers.**

---

## 2. Current architecture inventory [OBSERVED]

| Component | What it does today | Authority it holds | Relevance to Canonical Memory |
|---|---|---|---|
| `nova_knowledge_core/CURRENT/PRIME/` (7 Markdown files) | Current PRIME doctrine: README, framework, execution models, Strict OTE, 10AM Key Level Open, ORB, risk and session rules | Git-authoritative (`docs/ROADMAP.md:5`, `AGENTS.md:110`) | The only formally validated knowledge package. Bootstrap source of truth |
| `intelligence/current_knowledge.py` `validate_current_prime_package` (`:43-102`) | Fails closed if the package loses its exact file set, `Status: CURRENT` / `Authority:` metadata, the exactly-three-models invariant and order, explicit PROS supersession, the FVG boundary, one-trade/`$500`/09:45/ORB-only rules | Enforces Git authority at read time | A ready-made invariant set — reused as an ingest precondition and a shadow-parity check |
| `intelligence/current_knowledge.py` `_CONTRADICTION_PATTERNS` (`:110-152`) | Bounded regex set detecting explicit contradictions (fourth model, PROS reactivated, FVG as entry, second trade, other risk ceiling, early non-ORB) with same-sentence negation handling | Detection only | Seed fixtures for the conflicting-authority and prompt-injection gates |
| `intelligence/current_knowledge.py` `retrieve_current_prime` (`:185-224`) | Token-overlap ranking over whole documents, `max_docs=3`, `max_chars=5000`, stable tie-break by filename, returns text + sources + SHA-256 per source | Read-only | Today's hydration baseline: deterministic and provenance-bearing, but document-granular, character-budgeted, and silent about what it omitted (a document that does not fit is skipped by `continue` at `:213-214` with no record) |
| `services/assistant.py` `call_assistant_llm` (`:193-300`) | Keeps doctrine in its own `current_knowledge` field, separate from generated `system_context`; returns `knowledge_provenance` (source + sha256) and `knowledge_authority`; fails closed to `unavailable` on integrity error | Consumer | Proven separation-of-sections pattern and fail-closed behavior to carry into hydration |
| `services/assistant.py` `apply_assistant_action` (`:171-190`) | Applies model-returned `set_focus` / `add_task` / `add_reminder` / clear actions to assistant state in `data/` | Model output mutates runtime workspace state (the docstring at `:209` says only the `ok` outcome may act) | A live instance of agent output becoming state without independent validation. Scoped out of V1 — see §4 C10 |
| `core/config.py` `_data_file` (`:57-101`) and `DATA_DIR` (`:41`) | ~30 runtime JSON files under `NOVA_DATA_DIR` / legacy `DONNA_DATA_DIR`, with nova/donna filename fallback | Runtime, git-ignored | Includes several "memory-like" stores (session memory, market memory, reasoning trace, intelligence log) that are **not** Canonical Memory |
| `core/state.py` (`:17-38`, `:83-91`, `:141-142`) | Atomic tmp+replace JSON writes; several stores are truncated on save (alerts to 50, rejections to 200) | Runtime | Overwrite-and-truncate, no provenance, no event history — suitable for runtime, unsuitable for memory |
| `intelligence/audit.py` (`:1-8`, `:21-22`) | Ring-buffer usage log capped at 5,000 entries; never stores prompts, responses, or keys | Observability | Confirms a precedent: logs record *that* something happened, not the content. Hydration manifests should follow the same rule |
| `core/state_engine.py` (`:1-7`) | Calls itself the "single source of truth for all execution state"; notes a future Redis/Postgres swap | Disabled execution subsystem; listed as prohibited in the Obsidian policy (`obsidian_policy.json:137-146`) | **Excluded** from Canonical Memory entirely (§4 C9) |
| `requirements.txt` | `fastapi`, `uvicorn`, `anthropic`, `httpx`, `openai`, `requests`, `python-dotenv`, `beautifulsoup4`, `yfinance`, and one broker SDK package belonging to the disabled execution subsystem | — | **No database driver exists.** Adding one is a later, separately approved step |
| `render.yaml` | One Python web service; `DONNA_DATA_DIR=/data`; a 1 GB persistent disk mounted at `/data`; the execution retirement flag listed in `CLAUDE.md` pinned `"false"` | Deployment | No managed database is provisioned today |
| `tools/cowork/obsidian_policy.json` + `obsidian_sync_planner.py` | Read-only planner: stable IDs `nova-<16 hex of sha256(authority NUL path)>` (`planner:614-623`), LF/BOM-normalized content hash plus Git blob id (`:626-634`), claimed IDs always recomputed, conflicts stop, imports land only in `nova_knowledge_core/CANDIDATES`, no apply engine (`AUTOMATION_BACKLOG.md:1016-1020`) | Git authoritative; Obsidian non-executing (`policy:5-13`) | Directly reusable identity, hashing, provenance and conflict discipline for sources and for the Obsidian projection |
| `research/prime_validation/` (per `docs/PRIME_EMOTIONLESS_VALIDATION.md`) | Closed, fail-closed schema; `source_id` + `source_sha256`; required explicit UTC `as_of`; no wall-clock reads; deterministic ordering; `MIXED_PROVENANCE` rejection | Research tool; grants nothing | The validation philosophy V1 records should follow. Also a workstream Canonical Memory must not interrupt |
| Governance documents | Promotion flow `research → Obsidian review → Pedro approval → Git spec → tests → implementation` where no step advances on its own and each requires an explicit act (`AUTOMATION_ARCHITECTURE.md:56-68`, paraphrased); promotion of research is **AM** (`APPROVAL_MATRIX.md:57`) and prohibited for Claude without Pedro (`:67`) | Contract | The promotion model in [AUTHORITY_AND_PROMOTION.md](AUTHORITY_AND_PROMOTION.md) is a structured restatement of these, not a new policy |
| Trust-layer tools (B1.1–B1.9) | Evidence Formatter, Staleness Guard, A7 battery, Session Registry with `expected_commit`, Codex relay and runner | Read-only / approval-gated | Commit binding, staleness detection, and "PASS is not approval" carry straight over |

---

## 3. Reusable components [RECOMMENDATION]

Canonical Memory should be assembled from disciplines NOVA already has, not invented beside them.

| Existing component | Reused as | How |
|---|---|---|
| `validate_current_prime_package` | Bootstrap ingest precondition; shadow-parity invariant | Ingest from `CURRENT/PRIME` refuses to run if validation fails. Every shadow snapshot must re-satisfy the same invariants when rendered back out |
| `_CONTRADICTION_PATTERNS` and their negation rule | Adversarial fixtures | Each pattern becomes a planted conflicting proposal in gates G6/G7 |
| `KnowledgeSelection` (text + sources + hashes) | Shape of the hydration packet | Extended with an explicit **exclusion** list and a packet hash ([COMPACT_HYDRATION.md §6](COMPACT_HYDRATION.md#6-the-inclusionexclusion-manifest)) |
| Assistant doctrine-in-its-own-field | Hydration sections | Authority tiers never share a text field; source markers are neutralized outside their section |
| Planner stable ID, normalized hash, blob id, "never trust a claimed id" | `sources` identity and Obsidian projection identity | Same algorithm, recomputed on every read |
| Planner conflict states and exit-5 approval | Projection and candidate-import semantics | Projection conflicts stop; they are never merged |
| PRIME validation schema discipline | Record validation | Closed schemas per `(domain, kind)`, required `as_of`, no wall clock, stable rejection codes |
| Staleness Guard + Session Registry `expected_commit` | Commit binding | Every validated record and every hydration names the commit it was measured against |
| Evidence format (`AUTOMATION_ARCHITECTURE.md §E`) | Gate results | No gate is reported without command, counts, failures, refs |
| FA / AR / AAM / AM classes | Write and transition permissions | Every write-path mutation — including inserting a proposal — and every status transition maps to one class, never below AAM ([AUTHORITY_AND_PROMOTION.md §5](AUTHORITY_AND_PROMOTION.md#5-status-machine)) |

---

## 4. Conflicts and duplications found

Each item is **[OBSERVED]**. None is fixed by CM-0 — this task changes no runtime.

**C1. A second, disagreeing statement of PRIME rules lives in runtime defaults.**
`core/state.py:223-237` `default_journal_workspace()` declares
`approved_models: ['KLR', 'OTE', 'ORB', 'POWELL_10AM']`, `max_trades_per_day: 2`,
`max_losses_per_day: 2`, `daily_risk_pct: 1.0`. The Git-authoritative package, as
enforced by `validate_current_prime_package`, requires exactly three models (Strict OTE,
10AM Key Level Open, ORB), one real trade per day, and a `$500` ceiling. That is two
independent deciders for the same facts — the precise failure Canonical Memory exists
to prevent. Whether any active surface still consumes this block was **not traced** in
this assessment. [DECISION: PEDRO — D5]

**C2. Rule-shaped legacy directories have implicit status.**
`nova_knowledge_core/EXECUTION_RULES/`, `INVALIDATION_RULES/` (including
`pros_invalidation.md`), `NO_TRADE_CONDITIONS/`, and `WATCHLIST/` hold rule-like
Markdown outside `CURRENT/`. They are neither validated by `current_knowledge.py` nor
covered by an export class in `obsidian_policy.json`. Their status is inferred from
location only. Ingest must never infer "rule" from a filename or folder. [DECISION: PEDRO — D6]

**C3. Policy names paths the inventory did not observe.**
A depth-one listing (`nova_knowledge_core/*/*.md`) found no Markdown directly beneath
`RULES/`, `CANDIDATES/`, `EVIDENCE/`, or `OTE_INTELLIGENCE/`, all of which the Obsidian
policy names. Deeper contents were not inventoried, so this is a finding to re-measure,
not a claim that they are empty.

**C4. Two content-hash conventions.**
`current_knowledge.py:217` hashes text decoded by `Path.read_text` (universal newlines;
a UTF-8 BOM would survive as U+FEFF). The planner (`obsidian_sync_planner.py:626-634`)
hashes bytes with the BOM removed and CR/CRLF folded to LF. By reading the code these
agree for BOM-less UTF-8 files and disagree for a BOM-bearing one; this was not
measured. Canonical Memory must pick one. [RECOMMENDATION] adopt the planner's
normalized content hash **and** record the Git blob id, exactly as the planner does.

**C5. Several runtime "memories" that are not memory.**
`SESSION_MEMORY_FILE`, `MARKET_MEMORY_FILE`, `REASONING_TRACE_FILE`,
`INTELLIGENCE_LOG_FILE`, `ASSISTANT_FILE` (`core/config.py:72-99`) are capped or
overwritten JSON without provenance or history. They are operational runtime, not
promoted knowledge. [RECOMMENDATION] V1 does not ingest them. Any future ingest is per
store, as **evidence**, with an explicit source row.

**C6. Obsidian's stated role differs between contracts.**
`RESPONSIBILITY_CONTRACT.md:13` gives Obsidian "durable curated knowledge, human-readable
project memory, decision records"; `AGENTS.md:110-111` and the policy call it
non-authoritative. The CM-0 intent is stronger still: a **generated projection**.
Reconciling the contract wording is a separate, approved documentation change.
[DECISION: PEDRO — D7]

**C7. Two candidate lanes would appear.**
The planner routes vault imports to `nova_knowledge_core/CANDIDATES`. A Canonical Memory
`proposed` status is a second queue for the same kind of thing. [RECOMMENDATION] until
cutover, `CANDIDATES/` in Git stays the only lane; after cutover, one lane only.
[DECISION: PEDRO — D14]

**C8. Today's hydration omits silently and budgets characters.**
`retrieve_current_prime` skips a document that does not fit and reports nothing about
the skip, and its budget is characters, not model tokens.

**C9. Execution state claims "single source of truth".**
`core/state_engine.py:2-3`. Execution, broker, position, and risk-runtime state belong to
the disabled subsystem and Phase 2G. [RECOMMENDATION] Canonical Memory never stores or
projects them, and the ingest boundary rejects them (gate G0).

**C10. Model output mutates workspace state.**
`apply_assistant_action` (§2). Focus, tasks, and reminders are a personal workspace
rather than canonical knowledge. [RECOMMENDATION] out of V1 scope; not changed here.
[DECISION: PEDRO — D11]

**C11. Persistence risk is already known.**
`docs/ROADMAP.md:176` records journal data loss on deploy with persistent-disk
configuration pending; `render.yaml:14-17` mounts a single 1 GB disk. No backup
mechanism for `data/` is described in the repository files read.

---

## 5. Target model: three planes [RECOMMENDATION]

Canonical Memory separates what NOVA **believes**, what NOVA **is doing**, and what NOVA
**saw**. They are different kinds of truth with different write rules, so they are
different planes, sharing one table layout but never one status vocabulary.

| Plane (`domain`) | Holds | Example | Can it become a rule? |
|---|---|---|---|
| **knowledge** | Facts, rules, hypotheses, definitions, knowledge decisions | "PRIME has exactly three execution models"; "FVG is confluence metadata, not an entry model"; a hypothesis awaiting study | Only by the promotion path in [AUTHORITY_AND_PROMOTION.md](AUTHORITY_AND_PROMOTION.md) |
| **operational** | Project state, engineering decisions, blockers, phase, approval records | "CM-0 approved inside Phase 2F"; "B3.4 apply engine not authorized" | No. Operational records describe work, not doctrine |
| **evidence** | Observations, measurements, test results, review findings | "Command X reported N passed / M failed at commit Y"; "Codex returned PASS on relay envelope Z" | **Never.** Evidence may *support* a proposal; it never promotes one |

### 5.1 Record kinds (`domain`, `kind`) — closed set for V1

| domain | allowed kinds |
|---|---|
| knowledge | `fact`, `rule`, `hypothesis`, `definition`, `decision` |
| operational | `decision`, `status`, `blocker`, `approval`, `phase` |
| evidence | `observation`, `measurement`, `test_result`, `review_finding` |

An unknown pair is a rejection, not a default. Adding a kind is a schema change.

### 5.2 Governance class

Every record carries a `governance_class` that decides who may promote it:
`strategy`, `risk`, `research`, `engineering`, `project`, `market_context`, `governance`.
**`strategy`, `risk`, and `research` records reach `current` only by Pedro's explicit act.**

### 5.3 Confidence

`confidence` is descriptive only — `low`, `medium`, `high`, or `not_applicable` — with a
required `confidence_basis` text when not `not_applicable`. It is never an input to any
status transition, ranking tier, or promotion. [DECISION: PEDRO — D8] whether an ordinal
enum (recommended: no false precision) or a number is preferred.

---

## 6. Database choice

### 6.1 Requirements drawn from the model

1. Enforced invariants, not conventions: "one current version per record key",
   "evidence cannot be `current` as a rule", closed `(domain, kind)` pairs, foreign-keyed
   provenance.
2. Append-only event history that can be replayed deterministically.
3. Concurrent readers and serialized writers across Render, local Claude sessions, and
   Codex coordinators.
4. Python/FastAPI compatibility without a second language runtime.
5. Managed durability: backups and restore, because this becomes the record of what
   NOVA decided.
6. Flexible kind-specific payloads without hiding governance fields inside them.

### 6.2 Options

| Option | Fit | Verdict |
|---|---|---|
| Keep Git Markdown + `data/` JSON only | Git is excellent for specs and history, but cannot enforce "one current fact", cannot answer as-of queries structurally, and `data/` JSON is overwritten and truncated (C5, C11) | **Keep for bootstrap; insufficient as the long-term structured store** |
| SQLite file on the Render disk | Relational constraints and zero dependency on a service, but tied to one instance's 1 GB disk, single-writer, backup and restore are self-built, and remote agents cannot share it safely | Not recommended as the canonical store |
| **Managed PostgreSQL on Render** | [EXTERNAL] Render offers managed Postgres with backups, high availability, connection pooling and extensions (https://render.com/docs/postgresql). [EXTERNAL] PostgreSQL enforces relational constraints — primary, foreign, unique, check (https://www.postgresql.org/docs/current/ddl-constraints.html) — and stores `jsonb` with GIN indexing (https://www.postgresql.org/docs/current/datatype-json.html). Partial unique indexes express "one current per key" directly | **Recommended** |
| PGlite | [EXTERNAL] A JavaScript build of Postgres for Node/Bun/Deno/browser with filesystem or IndexedDB persistence and a single exclusive connection (https://pglite.dev/docs/). NOVA's backend is Python; using it would add a JS runtime to the service, and one exclusive connection conflicts with requirement 3 | **Not a canonical store.** Possible future *offline read-only projection* only (§6.4) |
| Graph or vector database as primary | Relationships in V1 are shallow and few; semantic ranking is deferred and must never decide inclusion ([COMPACT_HYDRATION.md §5](COMPACT_HYDRATION.md#5-optional-semantic-ranking-deferred)) | Not justified for V1 |

### 6.3 Recommendation

Managed PostgreSQL on Render as the **target** store for Canonical Memory, reached only
after the gates in [MIGRATION_AND_VALIDATION_GATES.md](MIGRATION_AND_VALIDATION_GATES.md)
allow it. **No dependency is added now.** Choosing a driver, plan tier, region, backup
retention, and cost is [DECISION: PEDRO — D1] at CM-3; none of those details was
verified in this assessment.

### 6.4 PGlite's permitted future role [DEFERRED]

If an offline or local agent cache is later wanted, PGlite may hold a **generated,
read-only projection** built from a named Canonical Memory event high-water mark, stamped
with that mark and its packet hash. It accepts no writes that flow back. A projection
that disagrees with its source is wrong by definition and is discarded, never
reconciled. It is never a second truth.

---

## 7. V1 relational core [RECOMMENDATION]

Seven tables. Small, normalized, and deliberately missing anything not needed to prove
the gates. Types are PostgreSQL types. **This is a field specification, not a
migration**; no DDL is executable from this document.

Conventions for all tables:

- Surrogate primary keys are `bigint GENERATED ALWAYS AS IDENTITY`, internal only. They
  never appear in an event payload, manifest, projection, or replay comparison. Every
  row has an immutable **natural identity**, and that is what those things refer to:

  | Table | Natural identity |
  |---|---|
  | `sources` | `source_identity` |
  | `entities` | `entity_key` |
  | `records` | (`record_key`, `version`) |
  | `record_sources` | (`record_key`, `version`, `source_identity`, `role`) |
  | `relationships` | `relationship_identity` |
  | `project_state` | (project `entity_key`, `snapshot_version`) |
  | `memory_events` | `event_id` — the one ordinal that is itself part of the hashed ledger |

- **Canonical content.** For each content table (`sources`, `entities`, `records`,
  `record_sources`, `relationships`, `project_state`), a row's *canonical content* is
  every domain field plus every reference written as the referenced row's natural
  identity (`subject_entity_key`, `source_identity`, project `entity_key`, relationship
  endpoints, `record_key` + `version`). It explicitly **excludes** the database-generated
  surrogate primary key, every surrogate foreign-key value (carried instead as the
  natural identity it resolves to), and `created_event_id`. Mutable columns are part of
  it: a creation event carries their initial value; live and replayed rows carry their
  current value. A row's *canonical projection* is its canonical content in canonical
  serialization. An event payload is canonical content, never the physical row;
  `created_event_id` is audited separately by the creation-link invariant (§7.8).
- Every timestamp is `timestamptz`, stored UTC. No column defaults to wall-clock time
  inside validation logic; `memory_events.recorded_at` is the only server-assigned
  instant, is audit-only, and is never used for currentness decisions. Content rows
  carry no server clock of their own.
- Hashes are 64 lowercase hex characters, enforced with `CHECK (x ~ '^[0-9a-f]{64}$')`.
- Git object ids are enforced as 40 or 64 lowercase hex.
- **References point one way.** Every content row points at the event that created it
  (`created_event_id`, FK → `memory_events`) and at other content rows by FK.
  `memory_events` holds **no** foreign key to any content table; it names its target by
  natural identity. There is no FK cycle and no deferred constraint (§7.8).
- **Exactly three columns are mutable:** `records.status`, `project_state.status`, and
  `entities.lifecycle`. Every other column is immutable after insert. A mutable column
  changes only in the same transaction as the `memory_events` row recording that
  transition (§7.8).

### 7.1 `entities`

Things that knowledge is *about*: the three PRIME models, symbols, roadmap phases,
components, documents, agents, people.

| Field | Type | Null | Constraint / note |
|---|---|---|---|
| `entity_id` | bigint identity | no | PK |
| `entity_key` | text | no | UNIQUE; `CHECK (entity_key ~ '^[a-z0-9][a-z0-9._-]{0,127}$')`, e.g. `prime.model.strict_ote`, `phase.2f`, `agent.codex` |
| `entity_type` | text | no | CHECK in (`prime_model`, `symbol`, `phase`, `component`, `document`, `agent`, `person`, `project`, `concept`) |
| `display_name` | text | no | |
| `lifecycle` | text | no | CHECK in (`active`, `historical`, `superseded`). PROS may exist only as `historical`/`superseded`. Mutable only via an `entity_lifecycle_changed` event (§7.8) |
| `attributes` | jsonb | no | default `'{}'`; descriptive only, never governance |
| `created_event_id` | bigint | no | FK → `memory_events`; the `entity_created` event whose payload is this row's canonical content |

**Invariant, enforced by gate not by constraint:** exactly three `prime_model` entities
with `lifecycle = 'active'`, matching `research/prime_validation`'s locked universe. A
fourth is an unapproved system change and fails G0.

### 7.2 `sources`

Where a record came from. Every validated or current record must have at least one.

| Field | Type | Null | Constraint / note |
|---|---|---|---|
| `source_id` | bigint identity | no | PK |
| `source_kind` | text | no | CHECK in (`git_blob`, `git_commit`, `pull_request`, `test_run`, `review_envelope`, `obsidian_note`, `external_document`, `agent_session`, `pedro_statement`) |
| `stable_ref` | text | no | Planner-style `nova-<16 hex>` over `source_kind` NUL normalized locator; recomputed, never trusted from input |
| `source_identity` | text | no | UNIQUE; the natural identity. SHA-256 over canonical serialization of (`source_kind`, `stable_ref`, `git_commit`, `content_hash`), absent values encoded explicitly; recomputed by the write path, never trusted from input |
| `repo_path` | text | yes | Repository-relative only; `CHECK` rejects drive letters, UNC, home paths, `..` |
| `git_commit` | text | yes | Required when `source_kind` in (`git_blob`, `git_commit`, `test_run`) |
| `git_blob_oid` | text | yes | Required when `source_kind = 'git_blob'` |
| `content_hash` | text | yes | Normalized SHA-256 (C4); required for `git_blob`, `obsidian_note`, `external_document` |
| `locator` | text | yes | PR number, relay envelope digest, URL for external documents |
| `observed_at` | timestamptz | no | When the source was read |
| `trust_class` | text | no | CHECK in (`authoritative_git`, `measured`, `agent_generated`, `human_owner`, `external_unverified`, `projection_readback`) |
| `copyright_restricted` | boolean | no | `true` forbids storing body text; raw third-party transcripts are never ingested at all |
| `created_event_id` | bigint | no | FK → `memory_events`; the `source_registered` event whose payload is this row's canonical content |

`obsidian_note` sources carry `trust_class = 'projection_readback'`: they can explain a
proposal but can never be the sole support of a `validated` record.

### 7.3 `records` — assertions in all three planes

| Field | Type | Null | Constraint / note |
|---|---|---|---|
| `record_id` | bigint identity | no | PK |
| `record_key` | text | no | Stable logical identity across versions, e.g. `prime.models.count`; same key pattern as `entity_key` |
| `version` | integer | no | `CHECK (version >= 1)`; UNIQUE (`record_key`, `version`) |
| `domain` | text | no | CHECK in (`knowledge`, `operational`, `evidence`) |
| `kind` | text | no | CHECK that (`domain`, `kind`) is one of the pairs in §5.1 |
| `governance_class` | text | no | CHECK in §5.2 set |
| `status` | text | no | CHECK per domain — knowledge/operational: (`proposed`, `validated`, `current`, `superseded`, `rejected`, `retracted`); evidence: (`recorded`, `disputed`, `retracted`) |
| `authority` | text | no | CHECK in (`git`, `canonical_memory`). Which store decides this subject ([AUTHORITY_AND_PROMOTION.md §2](AUTHORITY_AND_PROMOTION.md#2-authority-by-phase)) |
| `subject_entity_id` | bigint | yes | FK → `entities`; event payloads carry `subject_entity_key` instead |
| `statement` | text | no | Human-readable canonical assertion; treated as data, never instruction |
| `statement_hash` | text | no | SHA-256 of normalized `statement` |
| `body` | jsonb | no | Kind-specific payload; must carry `schema_version`; never holds status, authority, or approval |
| `confidence` | text | no | CHECK in (`low`, `medium`, `high`, `not_applicable`) |
| `confidence_basis` | text | yes | `CHECK (confidence = 'not_applicable' OR confidence_basis IS NOT NULL)` |
| `valid_from` | timestamptz | no | Business-time start |
| `valid_to` | timestamptz | yes | `CHECK (valid_to IS NULL OR valid_to > valid_from)` |
| `bound_commit` | text | no | Commit the record was proposed or measured against (the proposer's hydration pin). Immutable. A later `record_validated` event names its own `bound_commit`, which must equal this one or descend from it with every cited Git source unchanged |
| `supersedes_version` | integer | yes | Version of the same `record_key` that was `current` when this version was proposed; null when none was. `CHECK (supersedes_version IS NULL OR supersedes_version < version)`. Promotion is rejected unless that version is still `current`, and marks it `superseded` in the same write batch (§7.8) |
| `proposed_by` | text | no | Actor identity, e.g. `agent.claude`, `agent.codex`, `person.pedro`, `tool.current_knowledge_ingest`; equals the creation event's `actor` |
| `created_event_id` | bigint | no | FK → `memory_events`; the `record_proposed` or `evidence_recorded` event whose payload is this row's canonical content |

Constraints and indexes:

- **One current per key:** UNIQUE (`record_key`) WHERE `status = 'current'` (partial unique index).
- **Evidence never rules:** `CHECK (NOT (domain = 'evidence' AND kind IN ('rule','fact','decision')))` is already implied by §5.1; additionally `CHECK (domain <> 'evidence' OR status IN ('recorded','disputed','retracted'))`.
- **Contiguous versions:** the write path allocates `version` as the key's highest existing version + 1 under the serialized writer; G3 checks for gaps.
- **Superseded at most once:** implied by the one-current index — only a version that is still `current` can be named by a promotable successor.
- Index (`domain`, `kind`, `status`).
- Index (`subject_entity_id`) WHERE `status = 'current'`.
- Index (`governance_class`, `status`).
- Index (`bound_commit`) for staleness sweeps.
- GIN on `body` using `jsonb_path_ops` **only if** a measured query needs it. [DEFERRED]

Why governance fields are columns and not JSONB: status, authority, domain, and version
are exactly the facts that must be constrained and indexed. JSONB is for the payload
that varies by kind, never for the fields that decide what is true.

### 7.4 `record_sources`

| Field | Type | Null | Constraint / note |
|---|---|---|---|
| `record_id` | bigint | no | FK → `records` |
| `source_id` | bigint | no | FK → `sources` |
| `role` | text | no | CHECK in (`primary`, `supporting`, `contradicting`, `derived_from`) |
| `excerpt_hash` | text | yes | Hash of the cited span, not the span |
| `created_event_id` | bigint | no | FK → `memory_events`; the `record_proposed`, `evidence_recorded`, `record_validated`, or `evidence_disputed` event whose payload lists this link's canonical content |
| — | | | PK (`record_id`, `source_id`, `role`) |

Provenance completeness (G4) is measured over this table: every `validated` or `current`
record has at least one `primary` row whose source resolves.

### 7.5 `relationships`

Typed edges with real foreign keys. One table, two exclusive shapes.

| Field | Type | Null | Constraint / note |
|---|---|---|---|
| `relationship_id` | bigint identity | no | PK |
| `relation_type` | text | no | Entity edges: `part_of`, `depends_on`, `instance_of`, `alias_of`. Record edges: `supports`, `contradicts`, `refines`, `derived_from` |
| `from_entity_id` / `to_entity_id` | bigint | yes | FK → `entities` |
| `from_record_id` / `to_record_id` | bigint | yes | FK → `records` |
| `relationship_identity` | text | no | UNIQUE; the natural identity. SHA-256 over canonical serialization of (`relation_type`, from natural identity, to natural identity), where an endpoint is an `entity_key` or a (`record_key`, `version`); recomputed by the write path, never trusted from input |
| `created_event_id` | bigint | no | FK → `memory_events`; the `relationship_added` event whose payload is this row's canonical content |
| — | | | `CHECK` exactly one shape is populated and the `relation_type` matches that shape; `CHECK` no self-edge |

**Supersession is not stored here, and not in `memory_events` either.** It has one
representation: the successor's immutable `records.supersedes_version`, materialized from
that successor's creation event. The prior version's `current → superseded` change is an
ordinary status event in the same write batch and carries no successor pointer of its
own — so there is never a second place to disagree. An unresolved `contradicts` edge between two `current` records is a conflict
that hydration surfaces and never resolves ([COMPACT_HYDRATION.md §3.1](COMPACT_HYDRATION.md#31-stage-1--hard-filters)).

### 7.6 `project_state` — immutable snapshots

| Field | Type | Null | Constraint / note |
|---|---|---|---|
| `snapshot_id` | bigint identity | no | PK |
| `project_entity_id` | bigint | no | FK → `entities` (`entity_type = 'project'`); event payloads carry the project `entity_key` |
| `snapshot_version` | integer | no | `CHECK (snapshot_version >= 1)`; UNIQUE (`project_entity_id`, `snapshot_version`); allocated as highest + 1 |
| `as_of` | timestamptz | no | Explicit; never wall clock |
| `git_commit` | text | no | The measured HEAD |
| `branch` | text | no | |
| `roadmap_phase` | text | no | e.g. `2F` |
| `status` | text | no | CHECK in (`proposed`, `current`, `superseded`) |
| `payload` | jsonb | no | Closed schema with `schema_version`: active increments, open decisions (by `record_key`), blockers, gate statuses **as recorded**, locked invariants |
| `payload_hash` | text | no | Hash of canonical JSON serialization |
| `supersedes_snapshot_version` | integer | yes | Snapshot version of the same project that was `current` when this one was recorded; same promotion condition as `records.supersedes_version` |
| `created_event_id` | bigint | no | FK → `memory_events`; the `snapshot_recorded` event whose payload is this row's canonical content |
| — | | | UNIQUE (`project_entity_id`) WHERE `status = 'current'` |

A snapshot summarizes; it never overrides a record. If a snapshot and a current record
disagree, the snapshot is stale and the discrepancy is a G3 failure.

### 7.7 `memory_events` — append-only ledger

| Field | Type | Null | Constraint / note |
|---|---|---|---|
| `event_id` | bigint identity | no | PK; monotonic high-water mark used by replay and hydration |
| `write_batch_id` | uuid | no | Assigned by the write path once per transaction and shared by every event in it; replay applies a batch all-or-nothing |
| `event_type` | text | no | CHECK in — **creation:** `source_registered`, `entity_created`, `record_proposed`, `evidence_recorded`, `relationship_added`, `snapshot_recorded`; **transition:** `entity_lifecycle_changed`, `record_validated`, `record_promoted`, `record_superseded`, `record_rejected`, `record_retracted`, `evidence_disputed`, `evidence_dispute_resolved`, `snapshot_promoted`, `snapshot_superseded`; **authority:** `authority_cutover`, `authority_rollback` |
| `actor` | text | no | Actor identity |
| `actor_kind` | text | no | CHECK in (`pedro`, `agent`, `deterministic_tool`, `migration`) |
| `target_type` | text | no | CHECK in (`source`, `entity`, `record`, `relationship`, `snapshot`, `authority_scope`); `CHECK` it matches `event_type` |
| `target_key` | text | no | Natural identity of the target: `source_identity`, `entity_key`, `record_key`, `relationship_identity`, the project `entity_key`, or the authority scope id. **Not a foreign key** |
| `target_version` | integer | yes | `CHECK ((target_type IN ('record','snapshot')) = (target_version IS NOT NULL))` |
| `from_status` / `to_status` | text | yes | Creation events of records and snapshots carry `to_status` (the initial status) only; every transition event carries both |
| `approval_ref` | text | no | Every write-path mutation is at least AAM ([AUTHORITY_AND_PROMOTION.md §5.1](AUTHORITY_AND_PROMOTION.md#51-knowledge-and-operational-records)), so every event names the approval it ran under, resolved by the write path. For `→ current` in `strategy` / `risk` / `research`, and for `authority_cutover` / `authority_rollback`, it must resolve to Pedro's AM approval naming exactly this target |
| `bound_commit` | text | yes | Required for creation of records and snapshots and for `record_validated` |
| `reason` | text | no | Non-empty |
| `payload` | jsonb | no | Closed schema per `event_type`, with `schema_version`. A creation event's payload is the **canonical content (§7) of the row it creates**, every reference written as a natural identity (`subject_entity_key`, `source_identity`, link lists, `supersedes_version`); it never contains the row's surrogate ids or `created_event_id`, which do not exist until after this event is inserted. A transition event's payload carries the canonical content of any links it adds. Never credentials, prompts, or model responses |
| `recorded_at` | timestamptz | no | Server-assigned; audit only |
| `prev_event_hash` | text | yes | Hash chain; null only for the first event |
| `event_hash` | text | no | SHA-256 over canonical serialization of this row minus `event_hash`; `event_id` is included |
| — | | | UNIQUE (`target_type`, `target_key`, `COALESCE(target_version, 0)`) WHERE `event_type` is a creation type — a natural identity is created exactly once |

Append-only is enforced three ways, because one layer is not enough: the application role
has `INSERT` and `SELECT` only on `memory_events`; a trigger rejects `UPDATE`, `DELETE`,
and `TRUNCATE` on it; and G2 recomputes the hash chain.

### 7.8 Write path, transactions, and replay

**One transaction per write batch.** The single write path serializes writers and, inside
one database transaction:

1. resolves every natural identity the batch references to an existing row, or to a row
   created earlier in the same batch, and rejects the batch otherwise;
2. for each row to create, appends its **creation event first**, with the row's
   canonical content (§7) as payload, and obtains the `event_id` the database returns for
   that insert (`record_sources` links ride on the event whose payload lists them);
3. inserts the row with `created_event_id` set to that returned id, resolving surrogate
   FKs from the payload's natural identities, and checks that the row's canonical
   projection — surrogate ids and `created_event_id` excluded — equals the payload, and
   that the row satisfies the creation-link invariant below;
4. for each status or lifecycle transition, appends the transition event, changes the
   mutable column, and inserts any links the event's payload lists with
   `created_event_id` set to that event's returned id, checked the same way;
5. commits. Any failure rolls back the whole batch: no event without its row, no row
   without its event, no status value without its transition event.

Identity values flow one way — event, then row — so each is available at the moment it is
referenced; no deferrable constraint is needed. Supersession is one batch:
`record_promoted` for the successor and `record_superseded` for the version its
`supersedes_version` names.

**Creation-link invariant.** Every content row's `created_event_id` names exactly one
event, and it is the right one: for a `sources`, `entities`, `records`, `relationships`,
or `project_state` row, the unique creation event whose (`target_type`, `target_key`,
`target_version`) equals the row's natural identity; for a `record_sources` row, the one
event whose target is that link's record and whose payload lists that link. That
event's payload must equal the row's canonical content, with each mutable column compared
at its value as of that event; later values are proved by replaying transition events.
The write path checks this at insert, and G2/G3 check it over live and replayed state.
`created_event_id` is audited only here — never folded into a content-equality check or a
state hash.

**Replay.** Inside the database the ledger is primary and the six other tables are a
materialization of it. Replay copies `memory_events` verbatim into an empty schema, reads it
in `event_id` order, applies each `write_batch_id` all-or-nothing, and rebuilds `sources`,
`entities`, `records`, `record_sources`, `relationships`, and `project_state` from event
payloads and transitions alone, setting each rebuilt row's `created_event_id` from the
copied event exactly as the write path does. Rebuilt surrogate ids may differ; every
`event_id`, and with it ledger order and the hash chain, is identical because events are
copied verbatim. The canonical state hash serializes each content table's canonical
projections ordered by natural identity — surrogate ids and `created_event_id` excluded,
current mutable values included. The replayed hash must equal the live hash, and every
live and replayed row must satisfy the creation-link invariant (G2).

**Enforcement.** Events are append-only (§7.7). Content tables accept `UPDATE` only on the
three mutable columns — a trigger rejects any other column change — and only the write
path holds that grant. G2 and G3 prove every mutable column equals what the ledger replays
to.

### 7.9 Deliberately not in V1 [DEFERRED]

| Deferred | Why it can wait | Where it lives meanwhile |
|---|---|---|
| `validations` | A validation is an event (`record_validated`) with an actor, commit, and evidence links. A table adds nothing the gates need yet | `memory_events` + `record_sources` role `supporting` |
| `experiments` | No experiment workflow exists in Canonical Memory; PRIME research runs in `research/prime_validation` under its own ladder | Git |
| `strategy_results` | No dataset or result exists (`PRIME_EMOTIONLESS_VALIDATION.md §1.1`). Storing results before the ladder produces them would invite reading fields as findings | Nowhere yet |
| Approvals table | `approval_ref` on events points to one approval channel ([AUTHORITY_AND_PROMOTION.md §7](AUTHORITY_AND_PROMOTION.md#7-how-pedros-approval-is-recorded)) | Events |
| Embeddings / vector index | Semantic ranking is optional and may only reorder within a tier | — |
| Agent session table | The Session Registry already exists machine-locally | Session Registry |
| Persisted hydration manifests | V1 returns and hashes them; persistence arrives with CM-5 if needed | Returned to caller |
| Runtime `data/` ingest, execution state, broker data | Out of scope (C5, C9) | `data/`, disabled subsystem |

---

## 8. Git and Obsidian relationship [RECOMMENDATION]

```
                 code, tests, specs, commits, PRs, implementation history
   Git  ───────────────────────────────────────────────────────────────►  (authority)
    │  sources (blob id + normalized hash + commit)
    ▼
   Canonical Memory  ── promoted knowledge + operational state + evidence ──►  (authority, after cutover only)
    │  generated, read-only, stamped with event high-water mark
    ▼
   Obsidian projection  ── human reading ──►  (never authority)
    │  edits read back as proposals only, via the existing candidate lane
    └──────────────────────────────────────────────────────────────►  proposed
```

- **Git** keeps code, tests, commits, PRs, technical and architecture documents, and
  implementation history, permanently. Canonical Memory references Git; it never
  replaces it.
- **Obsidian** receives a generated projection: every note stamped with the planner's
  provenance fields plus the Canonical Memory event high-water mark it was rendered
  from. A vault edit is never truth; the planner's import path turns it into a
  *proposal* at most. The existing planner remains read-only; the apply engine stays
  unauthorized until separately approved.
- During bootstrap nothing in this diagram's lower half exists. Git `CURRENT/PRIME`
  is canonical.

---

## 9. Codex + Claude with one truth [RECOMMENDATION]

1. **One read path.** Every agent session starts from `hydrate(mission, agent,
   token_budget)` pinned to a commit and an event high-water mark. No agent reads the
   tables directly for reasoning context. A reviewer's candidate (proposal, diff, or
   task) is not memory: it arrives beside the packet as an explicitly labeled untrusted
   payload ([COMPACT_HYDRATION.md §4](COMPACT_HYDRATION.md#4-per-agent-projections-recommendation)).
2. **One write path, proposals only.** Agents submit `proposed` records and `evidence`
   rows through the one write path (§7.8). Each insert is a database mutation classed
   **AAM**: a proposal holds no authority and changes no current fact, but it changes
   stored state, so no agent or NOVA Brain surface writes automatically. No agent writes
   `validated` or `current` for its own proposal.
3. **Independent validation.** A proposal is validated by an actor other than its
   proposer: a deterministic tool, a different agent, or Pedro. Claude validating
   Claude is not independent, including across sessions. Whether Codex reviewing
   Claude counts as independent for **engineering and project** records is
   [DECISION: PEDRO — D12]; it never counts for `strategy`, `risk`, or `research`.
4. **PASS is evidence, not approval.** A Codex relay verdict is stored as an
   `evidence/review_finding`. It supports; it never promotes (`AGENTS.md:80-82`).
5. **Commit binding.** A session's Session Registry `expected_commit` must equal the
   hydration's `bound_commit`; if HEAD moves, the session re-hydrates before
   proposing.
6. **Codex never commits and never writes Canonical Memory directly** — the
   coordinator submits its proposals under AAM, mirroring `AGENTS.md:58-60`.
7. **Bootstrap.** Until CM-3 there is no database. Proposals travel as they do today:
   Git branches, PRs, and `CANDIDATES/`.

---

## 10. Minimal V1 scope

**In:** the seven tables of §7; ingest of `CURRENT/PRIME` as `authority = 'git'`
knowledge records; operational records for roadmap phase, CM increments, and approvals;
evidence records for measured test runs and review findings supplied with evidence
format; deterministic `hydrate`; Obsidian projection *planning* (not applying).

**Out:** execution, broker, and risk-runtime state; `data/` runtime stores; strategy
results; semantic ranking; PGlite; any UI; any change to the Assistant's live retrieval
until the gates pass; any fourth PRIME model; any trading authority of any kind.

Roadmap placement, increments, and STOP/GO gates:
[MIGRATION_AND_VALIDATION_GATES.md](MIGRATION_AND_VALIDATION_GATES.md).

**Nothing in this document authorizes autonomous or funded trading**, changes the
disabled trading subsystem, or touches either of its two guarded activation flags (the
master kill switch and the execution flag, both listed in `CLAUDE.md`).
