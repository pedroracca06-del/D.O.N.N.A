# NOVA Canonical Memory — CM-1 Schema and Git-Mirror Ingest

Status: **CM-1 implementation — Git-mirroring infrastructure only. Not canonical. No gate result is claimed.**
Phase: 2F (read-only intelligence / internal platform work)
Base: `codex/canonical-memory-cm1` @ `7313d12a546f9591aa008a3745efc00e83a82036`
Authority: this document describes a read-only code package. It grants nothing.

Companion documents (unchanged by CM-1):
[ARCHITECTURE_V1.md](ARCHITECTURE_V1.md) ·
[AUTHORITY_AND_PROMOTION.md](AUTHORITY_AND_PROMOTION.md) ·
[COMPACT_HYDRATION.md](COMPACT_HYDRATION.md) ·
[MIGRATION_AND_VALIDATION_GATES.md](MIGRATION_AND_VALIDATION_GATES.md)

---

## 0. What this is, and what it is not

CM-1 is a **standard-library-only, read-only Python package**,
`intelligence/canonical_memory/`. Given a full Git commit id, it reads a fixed set of
eleven Git blobs through read-only `git cat-file`, verifies every object
cryptographically, and returns immutable records that **mirror what Git currently
says**. Each record is bound to the commit, the blob id, and the normalized content
hash, and is linked to its source.

**This is Git-mirroring infrastructure only.** Git remains the only authority for every
subject. Nothing in CM-1 is canonical. It grants no runtime authority, no trading
authority, and no approval of any kind. It does not change what NOVA does. It
authorizes no autonomous or funded trading, and execution stays disabled.

CM-1 does **not** contain, and must not be extended into, any of the following without
a separate approved increment:

| Out of scope | Where it belongs |
|---|---|
| Any database, driver, schema migration, or dependency | CM-3 (decision D1) |
| `hydrate()`, golden missions, manifests, token budgets | CM-2 |
| Assistant or any live-surface wiring; replacing `retrieve_current_prime` | CM-7 (D13) |
| Obsidian projection or apply | CM-6 |
| Runtime state under `data/`; assistant workspace actions | Not in V1 (D11) |
| Status transitions, promotion, supersession, cutover API | CM-3+ |
| Evidence records | CM-3 (write path) |
| Execution, broker, position, or risk-runtime state; the guarded flags | Never |

---

## 1. Approved decisions this increment relies on

Recorded by Pedro before CM-1 (see [MIGRATION_AND_VALIDATION_GATES.md §7](MIGRATION_AND_VALIDATION_GATES.md#7-decisions-still-requiring-pedro)):

| ID | Decision as approved | How CM-1 honors it |
|---|---|---|
| **D2** | Cutover order: operational/project first, then engineering. PRIME only by separate approval | CM-1 performs no cutover. The three roadmap records are `operational`/`project`, so they are the first scope a future CM-5 could name. PRIME records are never scheduled for cutover |
| **D3** | PRIME stays Git-authoritative in V1 | The bootstrap authority enum is **`git` only**. `canonical_memory` is rejected (`AUTHORITY`). Every record has `authority = "git"` |
| **D9** | CM-0 gate thresholds provisionally accepted; token-reduction target deferred to CM-2 | CM-1 claims no gate result and measures no tokens |
| — | The missing `APPROVAL_MATRIX.md` citation for database mutations is deferred to CM-3 | CM-1 performs no database mutation, so the citation is not needed yet. It stays open for CM-3 |

Decisions that are **still open** and are not assumed: D1, D4–D8, D10–D15. For D6
(legacy rule-shaped folders), CM-1 takes the safest position: those folders are
**not ingested at all**. For D8 (confidence), the schema carries the recommended ordinal
enum with a required basis, and every ingested record uses `not_applicable`.

---

## 2. Exact boundary

### 2.1 Source allowlist — exactly eleven paths

Byte-exact membership. Nothing is normalized, case-folded, or globbed.

| # | Path | Group |
|---|---|---|
| 1 | `nova_knowledge_core/CURRENT/PRIME/README.md` | PRIME |
| 2 | `nova_knowledge_core/CURRENT/PRIME/PRIME_FRAMEWORK.md` | PRIME |
| 3 | `nova_knowledge_core/CURRENT/PRIME/EXECUTION_MODELS.md` | PRIME |
| 4 | `nova_knowledge_core/CURRENT/PRIME/STRICT_OTE.md` | PRIME |
| 5 | `nova_knowledge_core/CURRENT/PRIME/10AM_KEY_LEVEL_OPEN.md` | PRIME |
| 6 | `nova_knowledge_core/CURRENT/PRIME/ORB.md` | PRIME |
| 7 | `nova_knowledge_core/CURRENT/PRIME/RISK_AND_SESSION_RULES.md` | PRIME |
| 8 | `AGENTS.md` | Governance |
| 9 | `docs/claude-cowork/RESPONSIBILITY_CONTRACT.md` | Governance |
| 10 | `docs/claude-cowork/APPROVAL_MATRIX.md` | Governance |
| 11 | `docs/ROADMAP.md` | Project |

**Everything else is denied** (`PATH_NOT_ALLOWED`). That includes `CLAUDE.md`, the
CM-0 documents, `EXECUTION_RULES/`, `INVALIDATION_RULES/`, `NO_TRADE_CONDITIONS/`,
`WATCHLIST/`, `PROS_EVAN_INVESTING/`, `CANDIDATES/`, `data/`, and any variant of an
allowed path that differs by case, separator, or dot segment, or carries padding.

### 2.2 No inference

Kind, status, governance class, authority, domain, and subject come **only** from the
literal specs in `ingest_spec.py`. The ingest never reads them from a path, folder,
heading, front matter, `Status:` line, or body text. A spec anchors each record to one
or more **exact whole lines**. These lines must occur **exactly once, consecutively**,
in that record's own source. The record's `statement` is that excerpt, byte for byte
after BOM and newline normalization. Adding, moving, or reclassifying a record is a
reviewed code change to `ingest_spec.py`.

### 2.3 Locked invariants

- Exactly three active `prime_model` entities: `prime.model.strict_ote` (Strict OTE),
  `prime.model.10am_key_level_open` (10AM Key Level Open), and `prime.model.orb` (ORB).
  An unknown `prime_model` key is `PRIME_MODEL_UNKNOWN`. A set that is not exactly
  those three is `PRIME_MODEL_SET`.
- **FVG** is the entity `prime.concept.fvg` of type `concept`, never a model. Its record
  `prime.fvg.confluence_only` states that it is confluence only.
- **PROS** is `prime.lineage.pros`, lifecycle `superseded`. An active PROS entity is
  `PROS_LIFECYCLE`.
- **Evidence never changes rules.** Evidence kinds cannot be `rule`, `fact`, or
  `decision` (`KIND`). Evidence statuses are only `recorded`, `disputed`, and
  `retracted` (`STATUS`). Evidence cannot share a key with a decision record
  (`EVIDENCE_KEY_COLLISION`). The bootstrap spec contains no evidence
  (`SPEC_EVIDENCE`).
- The PRIME tree at the commit must hold exactly the seven Markdown files
  (`PRIME_PACKAGE_FILESET`), and the seven blobs must pass
  `validate_current_prime_package` (`PRIME_PACKAGE_INVALID`) before any record
  exists.

### 2.4 Process, file, clock, environment, network

| Concern | CM-1 behavior | Enforced by |
|---|---|---|
| Processes | Only `git --no-optional-locks --no-replace-objects -C <repo> cat-file --batch`, as an argument array, never with a shell, and only with a full 40- or 64-hex id on stdin | `git_reader.build_cat_file_argv`; boundary and ingest tests |
| Refs | `HEAD`, branch names, abbreviated ids, and revision expressions are refused before any process starts | `OID_INVALID` |
| Writes | None, except the seven verified PRIME blobs written into a private `tempfile.TemporaryDirectory` for the validator, removed on exit | Boundary test (`write_bytes` only there); scratch-removal test |
| Clock | Never read | AST test |
| Environment | Never read, never passed (`env=`) | AST test |
| Network | No network module imported; importing the package in a fresh isolated interpreter loads no network or live module | Boundary tests |
| Live surfaces | No import of `services`, `core`, `main`, `engines`, `delivery`, `ui`, the intelligence gateway, or providers | Boundary tests |

### 2.5 Trust in bytes

The reader is untrusted. `git_objects` re-hashes every object as
`hash("<type> <size>\0" + body)` with SHA-1 (40-hex) or SHA-256 (64-hex) before using
it. A forged blob, a redirected tree, a type-confused object, an answer for another
commit, or a replaced object is refused with `OBJECT_HASH_MISMATCH`. Trees are parsed
strictly: known modes only, no empty, dot, or `.git` names, no duplicates, canonical
Git order, and no case-folded twin of a looked-up name. A source must be a regular
file (`100644`), never a symlink, submodule, executable, or directory.

---

## 3. Schema v1 (`schema.py`)

Frozen, slotted dataclasses. Construction is validation. `from_mapping` is closed
(`UNKNOWN_FIELD`, `MISSING_FIELD`) and never normalizes case or whitespace. Payload
mappings are deep-copied into read-only views.

| Enum | Values |
|---|---|
| `DOMAINS` | `knowledge`, `operational`, `evidence` |
| `KIND_PAIRS` | knowledge: `fact` `rule` `hypothesis` `definition` `decision` · operational: `decision` `status` `blocker` `approval` `phase` · evidence: `observation` `measurement` `test_result` `review_finding` |
| `GOVERNANCE_CLASSES` | `strategy`, `risk`, `research`, `engineering`, `project`, `market_context`, `governance` |
| `STATUSES_BY_DOMAIN` | knowledge/operational: `proposed` `validated` `current` `superseded` `rejected` `retracted` · evidence: `recorded` `disputed` `retracted` |
| `AUTHORITIES` | **`git` only** (bootstrap) |
| `CONFIDENCE_LEVELS` | `low`, `medium`, `high`, `not_applicable` |
| `ENTITY_TYPES` | `prime_model`, `symbol`, `phase`, `component`, `document`, `agent`, `person`, `project`, `concept` |
| `LIFECYCLES` | `active`, `historical`, `superseded` |
| `SOURCE_KINDS` / `TRUST_CLASSES` | `git_blob` / `authoritative_git` only (bootstrap) |
| `LINK_ROLES` | `primary`, `supporting`, `contradicting`, `derived_from` |

| Type | Fields |
|---|---|
| `SourceRef` | `source_kind`, `repo_path`, `git_commit`, `git_blob_oid`, `content_hash`, `trust_class`, `copyright_restricted`, `stable_ref`, `source_identity` |
| `EntityRecord` | `entity_key`, `entity_type`, `display_name`, `lifecycle`, `attributes` |
| `MemoryRecord` | `record_key`, `version`, `domain`, `kind`, `governance_class`, `status`, `authority`, `subject_entity_key`, `statement`, `statement_hash`, `body`, `confidence`, `confidence_basis`, `bound_commit`, `supersedes_version`, `proposed_by` |
| `RecordSourceLink` | `record_key`, `version`, `source_identity`, `role`, `excerpt_hash` |

**Claimed identities are never trusted.** `stable_ref`, `source_identity`, and
`statement_hash` are recomputed on construction. A mismatch is
`STABLE_REF_MISMATCH`, `SOURCE_IDENTITY_MISMATCH`, or `STATEMENT_HASH_MISMATCH`.
Bodies and attributes may not carry governance keys (`status`, `authority`,
`approval`, `approval_ref`, `domain`, `kind`, `governance_class`, `lifecycle`,
`record_key`, `version`).

**Statements are data.** They are bounded (4,000 characters) and refuse C0 controls
except LF, DEL, C1, zero-width, bidirectional, and BOM characters
(`STATEMENT_CONTROL_CHARACTER`). They also refuse a `[CURRENT SOURCE:` marker,
including full-width look-alikes after NFKC folding (`STATEMENT_MARKER`).

**Deferred fields.** `valid_from`/`valid_to` and `sources.observed_at` from
ARCHITECTURE_V1 §7 are not in schema v1. Both need an instant, and CM-1 reads no clock.
In bootstrap mode, currentness is defined by `bound_commit` alone (COMPACT_HYDRATION
§2). Surrogate ids, `created_event_id`, and events do not exist without a database.

### 3.1 Hashing (`hashing.py`)

| Function | Definition |
|---|---|
| `normalize_bytes` | Remove one leading UTF-8 BOM; fold CRLF and CR to LF |
| `content_hash` | SHA-256 of normalized bytes (planner-compatible, resolves CM-0 conflict C4) |
| `text_hash` | `content_hash` of UTF-8 text |
| `canonical_json` | Sorted keys, compact separators, UTF-8, no NaN; refuses floats and non-JSON types |
| `stable_ref(kind, locator)` | `nova-` + first 16 hex of SHA-256(`kind` NUL `locator`) |
| `source_identity` | SHA-256 of canonical JSON of `source_kind`, `stable_ref`, `git_commit`, `content_hash`; absent values are explicit `null` |

---

## 4. APIs

| Module | Public API |
|---|---|
| `intelligence.canonical_memory` | Explicit `__all__`; `AUTHORIZATION_NOTICE`; `SCHEMA_VERSION = 1` |
| `ingest` | `ingest_objects(read_object, commit_oid) -> IngestResult` · `ingest_repository(repo_root, commit_oid) -> IngestResult` · `IngestResult` (frozen; `result_hash` recomputed on construction) · `decode_source`, `find_anchor`, `check_boundary`, `check_prime_listing` |
| `ingest_spec` | `ALLOWED_SOURCE_PATHS`, `ENTITY_SPECS`, `RECORD_SPECS`, `SPEC_VERSION`, `is_allowed_path`, `require_allowed_path`, `validate_spec` |
| `git_objects` | `object_format_of`, `hash_object`, `verify_object`, `parse_commit_tree`, `parse_tree`, `encode_tree`, `GitSnapshot` (`lookup`, `blob`, `list_tree`), `resolve_blobs` |
| `git_reader` | `GitCatFileReader(repo_root).read_object(oid)`, `build_cat_file_argv`, `parse_batch_output` |
| `prime_precondition` | `validate_prime_blobs({file_name: bytes}) -> tuple[str, ...]` |
| `schema` | The four record types, enums, `find_integrity_issues`, `assert_integrity`, `validate_repo_path`, `check_statement` |

`ingest_objects` runs these steps in order: validate spec → verify commit and trees →
read eleven verified blobs → check the PRIME tree listing → decode (strict UTF-8, no
control or invisible characters, 1 MiB bound) → PRIME precondition → five entities →
28 records and 28 primary links → set integrity → `result_hash`. **All or nothing:** any
failure raises, and no partial result exists.

### 4.1 What the spec mirrors

Five entities (the three models, FVG, PROS) and 28 records, every one `version 1`,
`status current`, `authority git`, `proposed_by tool.cm1_git_ingest`:

- **PRIME, 17 records:** package Git authority; no execution authority (README and
  RISK); the PRIME definition; level touch insufficient; exactly three models;
  owner-approved model change; PROS superseded; FVG confluence only; Strict OTE
  identity, fib-touch boundary, and STDV companion; the 10AM Key Level Open name and
  legacy label; ORB identity; one real trade per day with the $500 ceiling; ORB only
  before 09:45 ET.
- **Governance, 8 records:** no autonomous trading; Git authoritative and Obsidian
  non-authoritative; input is data; Claude does not decide trades; Obsidian executes
  nothing; the contract grants no permission; the AAM and AM class definitions.
- **Operational/project, 3 records:** PRIME models locked (roadmap status); 2F next,
  read-only; 2G separate approval required.

Record classes: `strategy` for doctrine, `risk` for the trade and session rules,
`governance` for authority and approval statements, and `project` for roadmap entries.

---

## 5. Rejection codes

Every rejection is a `CM1Error` subclass with a stable `code` and an optional
`subject`.

| Module | Codes |
|---|---|
| `hashing` | `HASH_INPUT_TYPE`, `CANONICAL_JSON_TYPE`, `STABLE_REF_INPUT` |
| `schema` — construction | `RECORD_TYPE`, `UNKNOWN_FIELD`, `MISSING_FIELD`, `RECORD_KEY`, `VERSION`, `DOMAIN`, `KIND`, `GOVERNANCE_CLASS`, `STATUS`, `AUTHORITY`, `SUBJECT_ENTITY_KEY`, `STATEMENT`, `STATEMENT_CONTROL_CHARACTER`, `STATEMENT_MARKER`, `STATEMENT_HASH`, `STATEMENT_HASH_MISMATCH`, `BODY`, `BODY_GOVERNANCE`, `BODY_SCHEMA_VERSION`, `CONFIDENCE`, `CONFIDENCE_BASIS`, `BOUND_COMMIT`, `SUPERSEDES_VERSION`, `PROPOSED_BY`, `SOURCE_KIND`, `REPO_PATH`, `GIT_COMMIT`, `GIT_BLOB_OID`, `OID_FORMAT_MIXED`, `CONTENT_HASH`, `TRUST_CLASS`, `COPYRIGHT_RESTRICTED`, `STABLE_REF_MISMATCH`, `SOURCE_IDENTITY_MISMATCH`, `ENTITY_KEY`, `ENTITY_TYPE`, `DISPLAY_NAME`, `LIFECYCLE`, `ATTRIBUTES`, `ATTRIBUTES_GOVERNANCE`, `PRIME_MODEL_UNKNOWN`, `PRIME_MODEL_DISPLAY_NAME`, `PRIME_MODEL_TYPE`, `PROS_LIFECYCLE`, `SOURCE_IDENTITY`, `ROLE`, `EXCERPT_HASH` |
| `schema` — integrity | `DUPLICATE_SOURCE_IDENTITY`, `DUPLICATE_SOURCE_PATH`, `MIXED_COMMIT`, `DUPLICATE_ENTITY_KEY`, `PRIME_MODEL_SET`, `DUPLICATE_RECORD_VERSION`, `MULTIPLE_CURRENT`, `SUBJECT_UNRESOLVED`, `RECORD_COMMIT_MISMATCH`, `EVIDENCE_KEY_COLLISION`, `DUPLICATE_LINK`, `LINK_RECORD_UNRESOLVED`, `LINK_SOURCE_UNRESOLVED`, `PROVENANCE_INCOMPLETE` |
| `git_objects` | `OID_INVALID`, `OBJECT_FORMAT`, `OBJECT_TYPE_INVALID`, `OBJECT_TYPE_MISMATCH`, `OBJECT_BODY_TYPE`, `OBJECT_TOO_LARGE`, `OBJECT_HASH_MISMATCH`, `OBJECT_READER_RESULT`, `COMMIT_MALFORMED`, `TREE_MALFORMED`, `TREE_MODE_INVALID`, `TREE_ENTRY_NAME`, `TREE_DUPLICATE_ENTRY`, `TREE_NOT_SORTED`, `TREE_PATH_INVALID`, `TREE_PATH_MISSING`, `TREE_CASE_COLLISION`, `TREE_PATH_NOT_TREE`, `TREE_ENTRY_MODE` |
| `git_reader` | `REPO_ROOT`, `GIT_TIMEOUT`, `GIT_UNAVAILABLE`, `GIT_FAILED`, `OBJECT_MISSING`, `OBJECT_TOO_LARGE`, `BATCH_MALFORMED`, `BATCH_OID_MISMATCH` |
| `ingest_spec` | `PATH_NOT_ALLOWED`, `SPEC_TYPE`, `SPEC_DUPLICATE_KEY`, `SPEC_PATH_NOT_ALLOWED`, `SPEC_ANCHOR`, `SPEC_ENUM`, `SPEC_EVIDENCE`, `SPEC_AUTHORITY`, `SPEC_STATUS`, `SPEC_SUBJECT_UNRESOLVED`, `SPEC_SOURCE_UNUSED` |
| `prime_precondition` | `PRIME_PACKAGE_TYPE`, `PRIME_PACKAGE_FILESET`, `PRIME_PACKAGE_ENCODING`, `PRIME_PACKAGE_INVALID` |
| `ingest` | `INGEST_SOURCE_SET`, `SOURCE_TOO_LARGE`, `SOURCE_NOT_UTF8`, `SOURCE_CONTROL_CHARACTER`, `ANCHOR_MISSING`, `ANCHOR_AMBIGUOUS`, `BOUNDARY_MATERIAL`, `RESULT_HASH_MISMATCH` |

`BOUNDARY_MATERIAL` covers statements that contain environment-variable-shaped
identifiers (which covers both guarded flags without naming them), credential-shaped
assignments, private-key blocks, or machine-specific paths.

---

## 6. Evidence contract

**No test result is recorded in this document.** The test modules were written with
the package and had not been run when this document was written. Per `CLAUDE.md` and
[MIGRATION_AND_VALIDATION_GATES.md §1](MIGRATION_AND_VALIDATION_GATES.md#1-principles),
a CM-1 → CM-2 GO requires evidence in the repository's evidence format: the exact
command, counts, named failures, and the ref measured against.

```bash
# CM-1 focused suite
python -B -m pytest tests/test_canonical_memory_schema.py tests/test_canonical_memory_git_objects.py tests/test_canonical_memory_ingest.py tests/test_canonical_memory_boundary.py -q

# Full regression (required before any commit, regardless of the focused result)
python -B -m pytest tests -q

# Retirement guard suite (G0)
python -B .claude/hooks/test_nova_guard_hook.py
```

| Module | Covers |
|---|---|
| `test_canonical_memory_schema.py` | Every enum; every field rejection; unknown (domain, kind); evidence never a rule or current; immutability and read-only payloads; closed `from_mapping`; claimed-identity mismatch; repo-path attacks; the exact model set, FVG, and PROS; set integrity and provenance; hashing and canonical JSON |
| `test_canonical_memory_git_objects.py` | SHA-1 vectors and SHA-256 headers; object forgery and type confusion; strict tree modes, names, order, and truncation; symlink, submodule, executable, and directory refusal; path and case-collision attacks; batch-output parsing; reader argv, full ids only, and failure codes |
| `test_canonical_memory_ingest.py` | Synthetic end-to-end ingest; deterministic and order-independent output; CRLF, BOM, and SHA-256 repositories; allowlist denial and decoys; no inference from headings, front matter, or copied anchors; spec literal refusals; malformed PRIME package and extra PRIME Markdown; anchor missing and ambiguous; prompt, marker, control-character, and boundary injection; no partial output; no socket or process during object ingest; cat-file-only repository ingest; **live read-only ingest at the pinned commit** |
| `test_canonical_memory_boundary.py` | Exact module set; per-module stdlib import allowlist; no I/O, eval, or print calls; no clock, environment, network, or extra process primitives; writes only in the temporary precondition; no `shell`; subprocess only in `git_reader`; no mutating Git word; no guarded flag name in source (names loaded from `tools/cowork/a7_policy.json`); fresh isolated import loads no live or network module; no hydration, transition, or database export; authorization notice |

The live test needs the pinned commit object in the local object store. A shallow clone
without it fails with `OBJECT_MISSING`, which is a correct fail-closed outcome rather
than a skip.

CM-1 STOP conditions (from §5.1) that this suite is built to catch: the schema admits
an unknown kind, status, or authority; ingest infers "rule" from a path; any file under
`research/prime_validation/` or `CURRENT/PRIME` changed.

---

## 7. Rollback

CM-1 holds no state: no database, no runtime file, no generated export, no
configuration change, no dependency. **Rollback is reverting the PR** that adds these
thirteen paths:

```
intelligence/canonical_memory/__init__.py
intelligence/canonical_memory/git_objects.py
intelligence/canonical_memory/git_reader.py
intelligence/canonical_memory/hashing.py
intelligence/canonical_memory/ingest.py
intelligence/canonical_memory/ingest_spec.py
intelligence/canonical_memory/prime_precondition.py
intelligence/canonical_memory/schema.py
tests/test_canonical_memory_boundary.py
tests/test_canonical_memory_git_objects.py
tests/test_canonical_memory_ingest.py
tests/test_canonical_memory_schema.py
docs/canonical-memory/CM1_SCHEMA_AND_INGEST.md
```

No existing file is modified, so the revert touches nothing else. The blast radius is
local: nothing imports the package outside its own tests.

---

## 8. Authority statement

- Git is the only authority for every subject CM-1 reads. A CM-1 record that disagrees
  with its blob is stale by definition. Git wins, and the fix is to re-run the ingest,
  never to edit the record.
- CM-1 output is not canonical, hydrates no agent, and answers no user.
- Nothing here promotes research, changes strategy or risk, or touches the disabled
  execution subsystem or either guarded activation flag.
- Exactly three PRIME execution models remain locked: Strict OTE, 10AM Key Level Open,
  ORB.

**This increment is Git-mirroring infrastructure only. It grants no runtime authority
and no trading authority, and nothing in it authorizes autonomous or funded trading.**
