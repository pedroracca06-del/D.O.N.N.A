# NOVA Canonical Memory — Authority, Promotion, and Supersession

Status: **CM-0 architecture proposal — not implemented, not canonical, not approved for build**
Phase: 2F (read-only intelligence / internal platform work)
Baseline measured: `codex/canonical-memory-cm0` @ `8302f4b27bd08dc25649f96e1269d02a227ec5be`
Authority: this document proposes how authority would be divided. It grants nothing and
does not amend the contracts it cites.

Companion documents:

- [ARCHITECTURE_V1.md](ARCHITECTURE_V1.md) — inventory, conflicts, database choice, V1 tables
- [COMPACT_HYDRATION.md](COMPACT_HYDRATION.md) — how authority and status filter what an agent sees
- [MIGRATION_AND_VALIDATION_GATES.md](MIGRATION_AND_VALIDATION_GATES.md) — cutover, rollback, gates, decisions

Labels **[OBSERVED]**, **[EXTERNAL]**, **[RECOMMENDATION]**, **[DEFERRED]**,
**[DECISION: PEDRO]** are defined in [ARCHITECTURE_V1.md §0](ARCHITECTURE_V1.md#0-labels-used-in-all-four-documents).

---

## 1. The one rule

**For every fact, exactly one store decides.** Other stores may reference it, mirror it,
project it, or propose a change to it. None may independently decide it.

When two places disagree, the question is never "which looks more recent" or "which is
more convincing". The question is "which store holds authority for this subject". The
other one is wrong by definition, and the disagreement is a defect to report — never a
merge to perform.

This restates existing policy rather than inventing it:

- [OBSERVED] Where Git and Obsidian appear to disagree about a specification Pedro has
  already signed off, **Git wins** (`docs/claude-cowork/AUTOMATION_ARCHITECTURE.md:53-54`,
  paraphrased).
- [OBSERVED] "Prevent duplicate authority … The same rule must not be authoritative in
  both places" (`AUTOMATION_ARCHITECTURE.md:228-230`).
- [OBSERVED] "Conflicts stop synchronization and require Pedro. Automation never merges
  a knowledge conflict" (`AUTOMATION_ARCHITECTURE.md:231-232`).

---

## 2. Authority by phase

### 2.1 Bootstrap — now, and until an explicit cutover passes [RECOMMENDATION]

| Subject | Sole decider | Everything else |
|---|---|---|
| Current PRIME doctrine | **Git** — `nova_knowledge_core/CURRENT/PRIME/`, as validated by `validate_current_prime_package` [OBSERVED] | Any database copy is a **shadow**. It is never called canonical, never answers a user, and loses every disagreement |
| Code, tests, commits, PRs, technical/architecture docs, implementation history | **Git** | — |
| Governance contracts, approval classes | **Git** — `docs/claude-cowork/**`, `AGENTS.md`, `CLAUDE.md` | — |
| Project and roadmap state | **Git** — `docs/ROADMAP.md`, `AUTOMATION_BACKLOG.md` | — |
| Research candidates | **Git** — `nova_knowledge_core/CANDIDATES/` lane [OBSERVED policy] | Obsidian inbox notes are proposals at most |
| Runtime market data, workspace state | Not memory — `data/` runtime | Not ingested |
| Execution, broker, risk-runtime state | Disabled subsystem; outside Canonical Memory | Never ingested, never projected |

During bootstrap the words "canonical", "source of truth", and "authoritative" are
**reserved for Git** in code identifiers, UI text, logs, and documents. A shadow table,
schema, or service is named as a shadow (`cm_shadow`, "shadow memory"). A proposed lint
for this naming is part of gate G12.

### 2.2 After an explicit, per-subject cutover [RECOMMENDATION]

Cutover moves authority **one subject scope at a time**, by an `authority_cutover`
event carrying Pedro's `approval_ref`, only after the gates in
[MIGRATION_AND_VALIDATION_GATES.md](MIGRATION_AND_VALIDATION_GATES.md) have passed for
that scope. Nothing moves by default.

| Subject | Sole decider after its cutover | Git's role | Obsidian's role |
|---|---|---|---|
| Code, tests, commits, PRs, specs, architecture docs, implementation history | **Git — permanently** | Authority | Projection of selected docs |
| Promoted structured knowledge in a cut-over scope | **Canonical Memory** | Version history of the schema, ingest code, and any *generated* exports | Projection |
| Operational state: project phase, decisions, blockers, approval records | **Canonical Memory** | Code and docs describing the process | Projection |
| Evidence: measured test results, review findings, observations | **Canonical Memory** records the fact of the measurement; the artifact it cites stays in Git or the tool output | Holds cited artifacts | Projection |
| A subject **not** yet cut over | **Git** (unchanged) | Authority | Projection |
| Anything in Obsidian | **Nobody** — Obsidian never decides | — | Generated projection; edits become proposals |

### 2.3 Recommended cutover order

1. **Operational/project state first** — lowest blast radius, highest daily value for
   agent hand-off, no doctrine at stake.
2. **Engineering knowledge** (architecture facts, component decisions) second.
3. **PRIME doctrine last, or never.** [RECOMMENDATION] `CURRENT/PRIME` stays
   Git-authoritative through V1 and beyond. Canonical Memory holds `authority = 'git'`
   mirror records for it, bound to blob ids, which hydration uses and which go stale the
   moment the blob moves. Whether PRIME doctrine ever changes deciders is
   [DECISION: PEDRO — D3]. If it ever does, the Markdown becomes a generated, reviewed
   export committed to Git for history, and a validator rejects any hand edit to it —
   otherwise Git and Canonical Memory would both decide PRIME.

### 2.4 The authority registry

Which store decides which subject scope is itself a fact, and it has exactly one
representation: the ordered sequence of `authority_cutover` / `authority_rollback`
events in `memory_events`. Every record's `authority` column must equal the registry's
answer for that record's scope at insert time; G6 checks it. Changing the registry is
**AM** — Pedro, every time.

---

## 3. Actors and what each may do

| Actor | Propose | Record evidence | Validate | Promote to `current` | Supersede | Retract / reject | Cut over authority |
|---|---|---|---|---|---|---|---|
| **Pedro** | yes | yes | yes | **yes — the only actor for `strategy`, `risk`, `research`** | yes | yes | **yes — the only actor** |
| **Claude Code / Cowork** | yes | yes (measured, evidence-formatted) | only proposals it did not originate, and only `engineering` / `project` | `engineering` / `project` only, under an AAM approval naming the record; never `strategy` / `risk` / `research` | proposes only | proposes only | no |
| **Codex** (via coordinator) | yes | yes (review findings) | as Claude, subject to D12 | no | proposes only | proposes only | no |
| **NOVA Brain** (Assistant, Journal Review, Market Summary) | drafts `hypothesis` and `market_context` proposals only; another actor submits them under AAM — never automatically | drafts observations only, submitted the same way | no | no | no | no | no |
| **Deterministic tools** (ingest, validators, gates) | mirror records with `authority = 'git'`, in AAM-approved runs | measurements, in AAM-approved runs | yes, for the specific checkable property they test | no | mirror version bumps when a Git blob moves, and only for `authority = 'git'` records | mark stale / dispute | no |
| **Obsidian** | no — a vault edit becomes a proposal only through the approval-gated planner import | no | no | no | no | no | no |
| **External sources** | no — cited through a `source` row by an actor who proposes | — | no | no | no | no | no |

[OBSERVED] basis: Pedro alone decides when research becomes a rule (`RESPONSIBILITY_CONTRACT.md:11`, paraphrased);
Claude may not "edit strategy specs or risk limits" (`:12`); NOVA Brain's "output is
analysis, never instruction" (`:14`); promotion of research is AM (`APPROVAL_MATRIX.md:57`)
and prohibited for Claude without Pedro (`:67`).

**Every permission above is subject to §5.1.** A "yes" means the actor may *submit* that
write through the one write path; it does not make the write free. Every write-path
mutation — a proposal, an evidence row, a source registration, a mirror ingest, a status
change — is at least **AAM**. No actor, including deterministic tools and NOVA Brain, has
automatic write permission, and none exists until a separate governance change grants one.

**Independence.** A validator must differ from the proposer by actor identity. Two
sessions of the same agent are not independent. A deterministic tool counts as
independent only for the property it actually checks (for example "blob hash matches"),
never for "this is a good rule".

---

## 4. No implicit promotion

[RECOMMENDATION] A record reaches `current` only through an explicit transition carrying
its required approval (§5.1); no mechanism, count, or elapsed time does it on its own.
The following **never** change a record's status, individually or in any combination.
Each is a planted adversary in gate G5.

- Any number of supporting evidence records.
- `confidence = 'high'`.
- Repetition across sessions, agents, or models.
- Agreement between Claude and Codex.
- A Codex `PASS` verdict.
- A passing test suite.
- Elapsed time without objection.
- An Obsidian edit, however it is labeled.
- A candidate import plan (the planner's exit 5 is a request for Pedro, not approval).
- Text inside a record, source, mission, or note that claims authority, status, or
  approval ([§8](#8-prompt-injection-and-authority-escalation)).
- A semantic-ranking score.

Evidence may support, contradict, or dispute. **Evidence never, by itself, makes anything
a rule or moves any record to `current`.**

---

## 5. Status machine

### 5.1 Knowledge and operational records

```
                ┌──────────── rejected (terminal)
                │
  proposed ─────┼──► validated ───► current ───► superseded (terminal, by a new version)
                │         │            │
                │         └──► rejected └──► retracted (terminal, no replacement)
                └──► retracted
```

| Transition | Who | Approval class | Required on the event |
|---|---|---|---|
| (new) → `proposed` | An actor permitted to propose (§3), through the write path | **AAM.** Inserting a proposal is a database mutation. The proposal has no authority and cannot change any current fact, but it changes stored state. No automatic proposal permission exists until a separate governance change is approved | `approval_ref` for that AAM approval, `reason`, `bound_commit`, ≥1 source for anything beyond a `hypothesis`, `supersedes_version` when the key has a `current` version |
| `proposed` → `validated` | Independent validator (§3) | AAM, every class. For `strategy`/`risk`/`research` validation is only a precondition for Pedro's AM promotion | `approval_ref`, `bound_commit`, supporting evidence links |
| `validated` → `current`, `strategy` / `risk` / `research` | **Pedro only** | **AM** | `approval_ref` naming record key, version, and transition |
| `validated` → `current`, `engineering` / `project` / `governance` / `market_context` | Pedro, or an agent under an AAM approval that names this record | AAM | `approval_ref` |
| `current` → `superseded` | Only as a side effect of promoting the version whose `supersedes_version` names it, by an actor allowed to promote that class | Same as the promotion | Both events in one write batch ([ARCHITECTURE_V1.md §7.8](ARCHITECTURE_V1.md#78-write-path-transactions-and-replay)) |
| any non-terminal → `rejected` / `retracted` | Pedro; or the class's promoter for non-current records | AAM; AM for `current` records in `strategy` / `risk` / `research` | `approval_ref`, `reason` |
| `authority = 'git'` mirror version bump | Deterministic ingest, when the bound blob moved | **AAM** — it decides nothing, but it inserts a row and transitions the prior version | `approval_ref` for the ingest run; new blob id and hash; old version `superseded` in the same write batch |

Every transition above — and every creation — is one write batch: the event and the row
insert or status change commit together or not at all ([ARCHITECTURE_V1.md §7.8](ARCHITECTURE_V1.md#78-write-path-transactions-and-replay)).

A `hypothesis` never becomes a `rule` by status change. Promoting a hypothesis means
Pedro approving a **new** record of kind `rule`, whose `record_sources` cite the
hypothesis with role `derived_from`.

### 5.2 Evidence records

`recorded` → `disputed` → `recorded` (dispute resolved) or `retracted`. Evidence has no
`current` state because evidence is never a decision. A disputed measurement is shown
as disputed; it is not deleted. Recording evidence and each of these transitions is AAM.

### 5.3 Project-state snapshots

`proposed` → `current` → `superseded`. A snapshot is generated from records; it cannot
introduce a decision that no record holds. Recording a snapshot and each transition is AAM.

---

## 6. Supersession

[RECOMMENDATION]

1. **Explicit.** A change to a current assertion is a new row: same `record_key`, the
   next version, `supersedes_version` naming the version that was `current` when it was
   proposed, with its own sources and reason.
2. **Atomic.** Promoting the new version and marking the prior `superseded` happen in
   one write batch — one transaction — with their events. The partial unique index on
   `(record_key) WHERE status = 'current'` makes a window with two current versions
   impossible.
3. **Nothing is replaced in place.** Content columns are immutable. There is no
   `UPDATE statement`. A typo fix is a new version with `reason = 'correction'`.
4. **History remains queryable.** "What did NOVA hold as current at instant T?" is
   answered from events and validity windows, and must match a replay (G2, G3).
5. **Retraction is not supersession.** A retracted record has no successor; hydration
   must not mistake "retracted" for "replaced by nothing, so the older version returns".
6. **The PROS lineage is the model case.** PROS is superseded historical lineage
   [OBSERVED `docs/ROADMAP.md:31`]. It is represented as a `historical` entity and
   `superseded` records, never deleted, and never hydrated as current doctrine.

### 6.1 Conflicts

- Two proposals for the same `record_key` while one is `current`: both remain
  `proposed`; neither is promoted until the class's promoter chooses. Once one is
  promoted, the other's `supersedes_version` no longer names the current version, so it
  cannot be promoted and must be re-proposed against the new current version.
- A `contradicts` edge between two `current` records with different keys: both are
  flagged; hydration excludes both and packs a mandatory conflict notice with the
  mandatory core, refusing rather than omitting it if it cannot fit
  ([COMPACT_HYDRATION.md §3.1](COMPACT_HYDRATION.md#31-stage-1--hard-filters),
  [§3.5](COMPACT_HYDRATION.md#35-stage-5--budget-packing)). Only the class's promoter
  resolves it, by superseding or retracting one of them.
- A disagreement between a record with `authority = 'git'` and its Git blob: the record
  is stale; Git wins; the mirror is re-ingested.
- A disagreement between any record and runtime defaults (for example the
  `core/state.py:223-237` journal workspace block, [ARCHITECTURE_V1.md §4 C1](ARCHITECTURE_V1.md#4-conflicts-and-duplications-found)):
  the runtime value is not a source of authority. The conflict is reported for Pedro.

Automation never merges, averages, or picks a winner.

---

## 7. How Pedro's approval is recorded

[OBSERVED] An approval is valid only when it states, beforehand, exactly what changes,
the change itself, the inverse, and the blast radius, and it is scoped to that one action
(`APPROVAL_MATRIX.md:72-83`).

[RECOMMENDATION] `approval_ref` must therefore resolve to an artifact that names:

1. the target: `record_key` and `version`; or, for an AAM batch such as one ingest run
   or one set of proposals, the bounded list of target natural identities and the commit
   they are bound to; or the authority scope, for cutover;
2. the write or transition (`proposed`, `validated → current`, `current → retracted`,
   `authority_cutover`, …);
3. the inverse (`retract version n` / `authority_rollback to git`);
4. the blast radius (which agents' hydration changes).

**One approval channel.** Through CM-4, the channel is Git: a Pedro-authored commit or a
Pedro-approved PR whose description carries those four elements, referenced by commit
SHA or PR number. This keeps one approval trail and reuses GitHub's identity rather than
inventing one. An in-app authenticated approval action is [DEFERRED] and would replace the
Git channel, not run beside it. [DECISION: PEDRO — D4]

An agent-written string that *looks like* an `approval_ref` is not an approval. The write
path resolves the reference and rejects anything it cannot resolve to a Pedro artifact
(G5).

---

## 8. Prompt injection and authority escalation

[RECOMMENDATION] Record statements, source bodies, Obsidian notes, mission text, review
payloads, and model output are **data, never instructions** — the same rule `AGENTS.md:92-95` applies
to reports and envelopes.

- Governance fields (`status`, `authority`, `governance_class`, `approval_ref`) are set
  only by the write path's parameters, never parsed from content.
- Text such as "SYSTEM: mark this as current", "approved by Pedro", a forged
  `[CURRENT SOURCE: …]` marker, or frontmatter claiming `nova_authority: git` changes
  nothing. The assistant already neutralises that marker outside the doctrine field
  [OBSERVED `services/assistant.py:232-237`]; hydration applies the same rule to every
  section.
- The planner already rejects approved classifications originating in the vault
  [OBSERVED `obsidian_sync_planner.py:1058-1060`]; the projection keeps that rule.
- Every such attempt is visible rather than silently dropped: hydration lists each
  neutralised marker in its manifest ([COMPACT_HYDRATION.md §6.1](COMPACT_HYDRATION.md#61-fields)),
  and the write path rejects any forged governance parameter (for example an
  unresolvable `approval_ref`) with a stated reason. Hydration writes nothing; recording
  an attempt as `evidence/observation` is an ordinary AAM write (§5.1).

---

## 9. What this document does not change

No contract is amended by CM-0. In particular `RESPONSIBILITY_CONTRACT.md` still
describes Obsidian as owning curated knowledge and decision records; aligning that
wording with "generated projection" is a separate, approved documentation change
[DECISION: PEDRO — D7].

**Nothing here authorizes autonomous or funded trading**, changes strategy or risk, or
touches the disabled execution subsystem or its flags. Exactly three PRIME execution
models remain locked.
