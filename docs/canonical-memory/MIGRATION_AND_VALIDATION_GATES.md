# NOVA Canonical Memory — Migration, Validation Gates, and Integration Plan

Status: **CM-0 architecture proposal — not implemented, not canonical, not approved for build**
Phase: 2F (read-only intelligence / internal platform work)
Baseline measured: `codex/canonical-memory-cm0` @ `8302f4b27bd08dc25649f96e1269d02a227ec5be`
Authority: this document proposes gates and phases. **No gate has been run. No result
exists.** It grants nothing.

Companion documents:

- [ARCHITECTURE_V1.md](ARCHITECTURE_V1.md) — inventory, conflicts, database choice, V1 tables
- [AUTHORITY_AND_PROMOTION.md](AUTHORITY_AND_PROMOTION.md) — deciders, status machine, supersession
- [COMPACT_HYDRATION.md](COMPACT_HYDRATION.md) — `hydrate(mission, agent, token_budget)` and its manifest

Labels **[OBSERVED]**, **[EXTERNAL]**, **[RECOMMENDATION]**, **[DEFERRED]**,
**[DECISION: PEDRO]** are defined in [ARCHITECTURE_V1.md §0](ARCHITECTURE_V1.md#0-labels-used-in-all-four-documents).

---

## 1. Principles

1. **No fabricated results.** Every gate below is `NOT RUN`. A gate becomes `PASS` only
   with evidence in the repository's evidence format: exact command, counts, named
   failures, and the refs measured against [OBSERVED `AUTOMATION_ARCHITECTURE.md:157-168`].
2. **Gates must be shown to fail.** Each gate is demonstrated failing on planted bad
   input before its pass is trusted — the rule the A7 battery already follows
   [OBSERVED `AUTOMATION_ARCHITECTURE.md:188-189`].
3. **Thresholds are proposals.** Every number in §3 is a starting proposal for Pedro to
   accept or change [DECISION: PEDRO — D9]. Changing a threshold after seeing results is
   recorded as a change, with the before and after.
4. **Small increments.** Each CM step is independently reviewable, reversible, and
   useful on its own. None blocks PRIME validation.
5. **Git stays canonical until an explicit cutover passes.** Nothing in CM-1 through
   CM-4 may be called canonical.

---

## 2. Roadmap placement [RECOMMENDATION]

- **CM-0 now, inside Phase 2F.** Phase 2F is read-only Brain/intelligence and
  internal-platform work [OBSERVED `docs/ROADMAP.md:56-58`]. Canonical Memory is
  intelligence infrastructure: it changes what agents and NOVA Brain *know*, not what
  NOVA *does*. It adds no execution control, telemetry, or governance/rejection stream.
- **CM-1, CM-2, … are small 2F increments**, scheduled beside — never instead of — the
  PRIME validation workstream. [RECOMMENDATION] no CM increment modifies
  `research/prime_validation/`, `nova_knowledge_core/CURRENT/PRIME/`, or their tests,
  and no PRIME ladder stage waits on a CM increment.
- **Exactly three PRIME models remain locked** throughout: Strict OTE, 10AM Key Level
  Open, ORB [OBSERVED `docs/ROADMAP.md:31`, `PRIME_EMOTIONLESS_VALIDATION.md §3`].
- **Phase 2G is untouched.** Trading/execution reintegration remains future and
  separately approved [OBSERVED `docs/ROADMAP.md:73-94`]. Canonical Memory stores no
  execution state and creates no path to it.
- **`docs/ROADMAP.md` is not edited by CM-0.** Recording Canonical Memory in the
  roadmap is a separate, approved documentation change.

---

## 3. Gate catalogue

Every gate: **status `NOT RUN`**. "Phase" is the first increment where the gate must pass
before that increment's GO.

### G0 — Boundary and invariant preservation (every phase)

- **Purpose.** Prove Canonical Memory work did not move the protected boundary.
- **Method.** Retirement guard suite; A7 battery on staged content; static check that
  no CM code references either guarded retirement flag (the master kill switch or the
  execution flag, both listed in `CLAUDE.md`), `services/execution*`, `core/state_engine.py`, broker modules, or `data/` risk/position
  files; ingest fixtures containing account ids, credentials, and raw transcripts.
- **Pass (proposed).** Guard suite reports zero failures with its exact counts
  re-measured (historical counts are snapshots, not expectations [OBSERVED
  `AUTOMATION_ARCHITECTURE.md:199-202`]); every A7 battery gate passes on staged
content, with the gate list and counts re-measured rather than assumed; 0
  boundary material ingested; exactly three `prime_model` entities with
  `lifecycle = 'active'`; `validate_current_prime_package` passes at the bound commit.

### G1 — Golden missions (CM-2)

- **Purpose.** Hydration gives each agent what a careful human would.
- **Method.** A versioned set of missions, each with Pedro-reviewed `must_include`
  (record keys) and `must_exclude` lists, per projection. Proposed initial coverage: at
  least 24 missions — PRIME doctrine questions, an ORB-before-09:45 question, a
  PROS-lineage question, a Codex review of a CM change, a Claude engineering task, a
  journal review, a Phase 2G temptation ("add an execution panel"), and a planted
  conflict. Each golden mission declares its golden budget. Separately, a versioned set
  of **expected-refusal fixtures** covers tight budgets and unusable cores: a budget
  below T0; a budget that fits T0 but not T0 plus its mandatory notices; a mandatory-core
  record made stale or conflicted. Tight-budget behavior is tested only there.
- **Pass (proposed).** Golden missions: a packet, not a refusal, is returned; 100 % of
  the projection's mandatory-core keys and 100 % of its mandatory conflict/staleness
  notices present; 100 % of `must_include` keys **included** at the declared golden
  budget — a `must_include` key excluded with `BUDGET` or any other reason is a failure;
  0 `must_exclude` keys included. Expected-refusal fixtures: 100 % return exactly the
  expected code (`MANDATORY_CORE_EXCEEDS_BUDGET`, `REQUIRED_NOTICES_EXCEED_BUDGET`,
  `MANDATORY_CORE_UNAVAILABLE`) with a partial manifest; 0 return a packet. A golden
  mission whose `must_include` cannot fit its golden budget is a labeling defect for
  Pedro to correct, never a gate exception.
- **Owner of labels.** Pedro approves the golden set; agents may propose missions, not
  labels.

### G2 — Deterministic replay (CM-2 for packets; CM-3 for events)

- **Purpose.** Same inputs, same memory, same packet.
- **Method.** (a) Run `hydrate` for every golden mission 20 times in fresh processes, on
  two machines, with CRLF and LF checkouts. (b) From CM-3: rebuild `sources`, `entities`,
  `records`, `record_sources`, `relationships`, and `project_state` purely by replaying
  `memory_events` into an empty schema, batch by `write_batch_id`, and compare a
  canonical state hash over canonical projections keyed by natural identity, with
  surrogate ids and `created_event_id` excluded; separately check the creation-link
  invariant on every live and every replayed row
  ([ARCHITECTURE_V1.md §7.8](ARCHITECTURE_V1.md#78-write-path-transactions-and-replay)).
  (c) Recompute the event hash chain, `event_id` included.
- **Pass (proposed).** Exactly one `packet_hash` and one `inputs_hash` per mission across
  all runs; replayed state hash equals live state hash, including every mutable status
  and lifecycle value; 100 % of live and replayed content rows satisfy the creation-link
  invariant; hash chain has 0 breaks; no code path reads the wall clock for an
  inclusion or currentness decision.

### G3 — Supersession and current fact (CM-3)

- **Purpose.** Exactly one current version, full history, no silent replacement.
- **Method.** Fixtures with supersession chains (including a PROS-style lineage),
  retractions, corrections, and concurrent promotion attempts; as-of queries before,
  at, and after each transition; attempted `UPDATE` of immutable columns; attempted
  delete; a content row inserted without a creation event; a status change without a
  transition event; a batch forced to fail after its event is appended; a row whose
  `created_event_id` names another natural identity's creation event; a row whose
  canonical content differs from its creation event's payload.
- **Pass (proposed).** For every key and every probed instant, 0 or 1 current version
  and it matches replay; 100 % of immutable-column updates, deletes, eventless inserts,
  and eventless status changes rejected; a failed batch leaves 0 events and 0 rows;
  100 % of content rows satisfy the creation-link invariant — `created_event_id` names the
  exact creation event for the row's natural identity (for a `record_sources` row, the one
  event whose payload lists it), and that payload equals the row's canonical projection
  with surrogate ids and `created_event_id` excluded and mutable columns taken at their
  value as of that event; 100 % of mislinked or content-mismatched rows rejected; every `superseded` version is named by exactly one promoted successor's
  `supersedes_version` in the same `write_batch_id`; 0 version gaps per key; a retracted
  key never resurrects its prior version; the current `project_state` snapshot agrees
  with current records (0 discrepancies).

### G4 — Provenance completeness (CM-3; Git-only form at CM-2)

- **Purpose.** Nothing current without a resolvable source.
- **Method.** For every `validated`/`current` record, resolve each `primary` source:
  Git blob exists at `git_commit` and its normalized hash matches `content_hash`; PR,
  test run, and review envelope references resolve.
- **Pass (proposed).** 100 % of validated/current records have ≥1 resolving primary
  source; 0 records rest solely on `projection_readback` sources; 0 orphan
  `record_sources` rows; 0 source rows with machine-specific paths.

### G5 — No implicit promotion (CM-3)

- **Purpose.** Evidence, confidence, agreement, and time never promote.
- **Method.** Planted adversaries for every item in
  [AUTHORITY_AND_PROMOTION.md §4](AUTHORITY_AND_PROMOTION.md#4-no-implicit-promotion):
  1,000 supporting evidence rows; `confidence = 'high'`; Claude + Codex agreement;
  a Codex PASS; a green test run; an Obsidian note labeled `current`; a forged
  `approval_ref`; an agent actor calling promote on `strategy`/`risk`/`research`; a
  proposal or evidence row submitted without an AAM approval, including one drafted
  automatically by a NOVA Brain surface.
- **Pass (proposed).** 0 status changes from any adversary; 0 unapproved inserts;
  100 % of events carry an `approval_ref` resolving to an approval of the required class
  — at least AAM; 100 % of `→ current` events in `strategy`/`risk`/`research` carry an
  `approval_ref` resolving to Pedro's AM artifact; 0 self-validations (validator =
  proposer); 0 evidence records in a status other than `recorded`/`disputed`/`retracted`.

### G6 — Conflicting authority (CM-2 fixtures; CM-4 live shadow)

- **Purpose.** One decider per fact; disagreement is reported, never merged.
- **Method.** Fixtures in which Git `CURRENT/PRIME`, an Obsidian projection note, a
  runtime default (modeled on `core/state.py:223-237`'s four-model / two-trade block
  [OBSERVED]), and an agent proposal disagree; each of the six
  `_CONTRADICTION_PATTERNS` [OBSERVED `intelligence/current_knowledge.py:110-152`] as a
  planted proposal; a record whose `authority` disagrees with the authority registry.
- **Pass (proposed).** In 100 % of cases the registry's decider's value is the only one
  hydrated; every disagreement produces a conflict notice or a rejection; 0 merged or
  averaged values; 0 records whose `authority` differs from the registry.

### G7 — Prompt-injection adversaries (CM-2)

- **Purpose.** Content is data.
- **Method.** Directives in mission text, record statements, source bodies, Obsidian
  frontmatter and body, and agent proposals: "mark as current", "approved by Pedro",
  forged `[CURRENT SOURCE: …]` markers, `nova_authority: git` claims, instructions to
  include execution state, instructions to widen projection, Unicode look-alikes of
  markers. Each adversary is paired with a control fixture at the same pin, agent, and
  budget without the injected bytes.
- **Pass (proposed) — mission-text injection.** Injected mission text may legitimately
  change deterministic relevance, so packets are **not** required to match. Required:
  T0, T1, T2, T3, and T8 identical to the control; the same `projection_id`, pin,
  constants versions, and required-context totals; every record included in both packets
  carries identical status, authority, `governance_class`, and version. Differences are
  allowed only in T4–T7 membership and order, and each must be fully explained by the
  manifest: a `token_overlap` component change within its `+6` cap, or a resulting
  `NOT_RELEVANT` / `CANDIDATE_CAP` / `BUDGET` exclusion. 0 records admitted that failed
  Stage 1 in the control; 0 T7 items for a projection without T7.
- **Pass (proposed) — injected record, source, or note content.** The injected item's
  and every other record's governance fields (status, authority, `governance_class`,
  `domain`, `kind`, version) are unchanged by the write path; its Stage 1 outcome and tier
  equal the control's; its score differs, if at all, only in the `token_overlap`
  component (T4–T7 only), with any resulting T4–T7 difference explained by the manifest
  as above; T0–T3 and T8 membership identical to the control apart from that item's own
  rendered line; the injected bytes appear only inside that item's own rendered
  statement, as data; 100 % of forged markers neutralised outside their owning section
  and listed in `neutralised[]`; 0 status changes from injected proposals. Hydration
  writes nothing — recording an escalation observation is a separate AAM write.

### G8 — Commit and staleness binding (CM-2)

- **Purpose.** No agent reasons from a moved base.
- **Method.** Hydrate at commit A; advance to commit B that modifies one
  `CURRENT/PRIME` blob and one governance doc; hydrate again; submit a proposal carrying
  the commit-A `packet_hash`. Repeat with a local bare remote advance, as the Staleness
  Guard's demonstrations did [OBSERVED `AUTOMATION_BACKLOG.md:44`].
- **Pass (proposed).** 100 % of records bound to changed blobs are `STALE_SOURCE` or
  re-ingested before the next packet; `COMMIT_MISMATCH` refusal when the Session Registry
  `expected_commit` differs; 100 % of stale-packet proposals rejected.

### G9 — Cross-model consistency (CM-4)

- **Purpose.** Claude and Codex start from the same truth and state it the same way.
- **Method.** (a) Hydrate each golden mission for `agent.claude.engineering` and
  `agent.codex.reviewer`; compare T0–T2 record keys and versions. (b) Ask both models a
  fixed set of factual questions whose canonical answers are single current records
  (for example "how many PRIME execution models are current?"); score answers against
  the record, not against each other.
- **Pass (proposed).** (a) Identical keys, versions, and hashes in the intersection of
  both projections; differences explained entirely by projection rules. (b) Disagreement
  rate with the canonical record at or below a Pedro-set threshold, with each
  disagreement listed. This gate measures memory, not model quality; a model error with
  a correct packet is logged as a model finding, not a memory failure.
- **Cost note.** (b) makes billed model requests; it requires Pedro's per-invocation
  approval, as B1.10 does [OBSERVED `AUTOMATION_BACKLOG.md:52`].

### G10 — Retrieval relevance and omission (CM-2)

- **Purpose.** Include what matters; account for everything left out.
- **Method.** Over the golden set: precision and recall of included non-mandatory
  records against `must_include`; manifest accounting; planted "near-miss" records
  (right entity, superseded; right topic, wrong projection).
- **Pass (proposed).** 0 mandatory-core omissions and 0 omitted mandatory notices in any
  returned packet; recall on `must_include` exactly 1.0 at the golden budget (as G1
  requires); precision on included non-mandatory records at or above a Pedro-set
  threshold [DECISION: PEDRO — D9]; `evaluated = included + excluded` exactly for 100 %
  of packets; 100 % of `BUDGET` exclusions confined to T1–T7; 100 % of near-misses
  excluded with the expected reason code; 0 silently omitted records.

### G11 — Token reduction against a full-history baseline (CM-2)

- **Purpose.** Compact hydration is actually compact — without buying compactness with
  omissions.
- **Baseline definition.** For each golden mission, the tokens, under the same
  `estimator_id`, of what an agent is handed without Canonical Memory: all seven
  `CURRENT/PRIME` documents, `AGENTS.md`, `CLAUDE.md`, the four `docs/claude-cowork`
  contracts relevant to the mission, `docs/ROADMAP.md`, and the recorded hand-off or
  conversation history for that workstream. A second, narrower baseline is today's
  `retrieve_current_prime` output plus the same governance docs.
- **Method.** Compare packet tokens with both baselines, per mission and in aggregate.
- **Pass (proposed).** Median reduction against the full-history baseline meets a
  Pedro-set target [DECISION: PEDRO — D9] **while G1 and G10 pass on the same run**. A
  reduction achieved with any G1/G10 failure is a fail, not a partial pass. No reduction
  figure is claimed until measured.

### G12 — Shadow migration, explicit cutover, rollback (CM-4 shadow; CM-5 cutover)

- **Purpose.** Prove the database can hold a scope before it decides that scope, and
  prove it can hand authority back.
- **Shadow method.** Ingest the scope from Git into the shadow for every commit to
  `main` in the window. Each ingest run is a database mutation executed under an AAM
  approval (one approved run may cover several commits); unattended automatic ingest
  would need a separate governance change. Render the shadow back to the Git form (for PRIME: re-run
  `validate_current_prime_package` on the rendering; for operational scopes: a
  structural diff); hydrate from Git-only and shadow side by side for the golden set.
  The shadow answers no user and no agent.
- **Shadow pass (proposed).** 0 unexplained diffs across a Pedro-set window (proposed:
  at least 20 consecutive `main` commits **and** 14 days); naming lint finds 0 uses of
  "canonical"/"source of truth" for shadow components; backup restore of the shadow
  measured end to end, with the restored state hash equal to the source.
- **Cutover method.** One `authority_cutover` event per subject scope, with Pedro's
  `approval_ref` naming the scope, the inverse, and the blast radius. Git files for that
  scope become generated exports with a header naming the event high-water mark; a
  validator rejects hand edits to them.
- **Rollback method and pass (proposed).** Rehearsed **before** cutover: an
  `authority_rollback` event returns the scope to Git; Canonical Memory becomes
  read-only for that scope; the last generated export is already in Git history, so
  nothing is reconstructed from memory. Drill pass: after rollback, Git-only hydration
  produces the pre-cutover golden packets' record sets (0 differences), and the elapsed
  time is recorded.

---

## 4. Migration strategy [RECOMMENDATION]

1. **Git first, database second.** The contract, ingest, hydration, and most gates are
   proven over Git alone (CM-1, CM-2). A database is chosen only after the model has
   proven useful without one.
2. **Shadow, never dual-write.** The shadow is derived from Git by deterministic ingest.
   Nothing writes to Git *and* the shadow as independent deciders.
3. **Per-scope cutover.** Operational/project state first; engineering knowledge second;
   PRIME doctrine only if Pedro decides it should ever move (D3).
4. **Runtime `data/` is not migrated.** The runtime memories in
   [ARCHITECTURE_V1.md §4 C5](ARCHITECTURE_V1.md#4-conflicts-and-duplications-found)
   stay runtime. Any future ingest is a separate, per-store, evidence-only proposal.
5. **Obsidian last.** The projection is rendered only from a cut-over scope, through the
   existing read-only planner's rules, and the apply engine remains a separate approval
   [OBSERVED `AUTOMATION_BACKLOG.md:1016-1020`].

---

## 5. Phased integration plan

Each increment is small, lands as its own reviewed PR under Pedro's approval, and stops
at its STOP/GO gate. **Nothing below is approved by this document.**

| Increment | Delivers | Changes runtime? | Adds dependency? | Must pass for GO |
|---|---|---|---|---|
| **CM-0** | These four architecture documents | No | No | Pedro review of the documents; decisions D1–D15 triaged |
| **CM-1** | Standard-library record/manifest schemas as frozen dataclasses with closed validation (PRIME-validation style); a deterministic Git-only ingest spec for `CURRENT/PRIME` and governance docs; fixtures; tests. No database, no live wiring | No | No | G0; ingest fails closed on every planted malformed source; schema rejects every unknown `(domain, kind)`, status, and authority |
| **CM-2** | Git-only `hydrate` prototype, golden missions, manifest, adversarial fixtures — offline tool, not wired into the Assistant | No | No | G0, G1, G2 (packets), G4 (Git form), G6 (fixtures), G7, G8, G10, G11 |
| **CM-3** | Database decision executed: Render Postgres provisioned (D1), driver dependency approved, schema from [ARCHITECTURE_V1.md §7](ARCHITECTURE_V1.md#7-v1-relational-core-recommendation) migrated in a **non-production shadow** database; event ledger and write path | Adds a service, not a behavior | **Yes — separately approved** | G0, G2 (events), G3, G4, G5 |
| **CM-4** | Shadow ingest covering every `main` commit, in AAM-approved runs; side-by-side hydration comparison; backup/restore drill | No user-visible change | No new | G0, G6 (live), G9, G12 shadow criteria |
| **CM-5** | First cutover: operational/project state scope only; rollback drill first | Yes, for that scope's agents | No new | G0–G12 for the scope, rollback drill passed, Pedro's AM `authority_cutover` approval |
| **CM-6** | Obsidian generated projection for cut-over scopes (planner rules; apply engine separately approved) | Writes a vault only under per-sync approval | No new | G0, G4, G6, G7; planner conflict stop demonstrated on the projection |
| **CM-7** | Optional: Assistant hydration switch from `retrieve_current_prime` (D13); optional semantic ranking within tiers | Yes | Possibly — separately approved | G1, G2 (both modes), G9, G10, G11 on the live surface's golden set |
| **Later** | PGlite offline read-only projection; `validations`, `experiments`, `strategy_results` tables | — | — | Separately proposed and approved |

### 5.1 STOP / GO gates

A **STOP** halts the increment, leaves authority where it is, and returns to Pedro. It
is never worked around by narrowing the gate.

| Checkpoint | GO only if | STOP if any of |
|---|---|---|
| **Before CM-1** | Pedro accepts CM-0 and records D2, D3, D9 at least provisionally | Any document here is read as authorizing build, runtime change, or a dependency; any conflict in [ARCHITECTURE_V1.md §4](ARCHITECTURE_V1.md#4-conflicts-and-duplications-found) is judged to require a runtime fix first |
| **CM-1 → CM-2** | G0 passes; schemas proven failing on planted input | Schema admits an unknown kind/status/authority; ingest infers "rule" from a path; any PRIME-validation file or `CURRENT/PRIME` file changed |
| **CM-2 → CM-3** | G1, G2, G4, G6, G7, G8, G10, G11 pass with evidence; Pedro approves D1 and the dependency | Any mandatory omission; any conflict/staleness notice omitted from a returned packet; any `must_include` key excluded at its golden budget; any expected-refusal fixture returning a packet; any nondeterministic packet; token reduction bought with an omission; Pedro declines the database or dependency — **Git-only hydration remains a valid end state** |
| **CM-3 → CM-4** | G2 (events), G3, G4, G5 pass on the shadow database | Any immutable-column update or delete succeeds; any content row or status change without its event; any write without an approval of at least AAM; any record reaching `current` without its required approval; any hash-chain break; replay state hash differs from live; any row failing the creation-link invariant; the shadow is referred to as canonical |
| **CM-4 → CM-5** | G6, G9, G12 shadow criteria pass for the full window; rollback drill passes; Pedro issues the AM cutover approval naming the scope | Any unexplained shadow diff; restore hash mismatch; rollback not rehearsed; scope includes PRIME doctrine without D3 |
| **CM-5 → CM-6** | Cut-over scope stable with G0–G12 re-measured; B3.4 apply engine separately approved | Any projection note treated as a source of truth; a vault conflict merged automatically |
| **CM-6 → CM-7** | Live-surface golden set passes G1, G2, G9, G10, G11; Pedro approves D13 | Any change would place Canonical Memory, hydration, or model output in an order path; any Phase 2G surface appears |
| **Any time** | — | Guard block; A7 failure; stale HEAD; dirty worktree; a guarded flag near an enabling value; any automatic write to Canonical Memory without an approved governance change; a fourth PRIME model; execution/broker/risk-runtime data in any CM table or packet; a PRIME validation stage delayed by CM work |

### 5.2 Rollback at each increment

| Increment | Inverse |
|---|---|
| CM-0 – CM-2 | Revert the PR. Nothing else holds state |
| CM-3 – CM-4 | Stop ingest; drop the shadow database under Pedro's approval; Git is untouched and still canonical |
| CM-5 | `authority_rollback` event for the scope; Git generated exports resume as hand-maintained sources; Canonical Memory read-only for the scope |
| CM-6 | Stop projection; vault notes remain inert Markdown with provenance; nothing flows back |
| CM-7 | Restore `retrieve_current_prime` as the Assistant path (kept intact until then) |

---

## 6. Blockers and unverified items

- **No blocker prevents CM-0 review.**
- External technology claims in [ARCHITECTURE_V1.md §6](ARCHITECTURE_V1.md#6-database-choice)
  come from the official links supplied with the task and were not re-fetched here;
  Render plan tiers, backup retention, extension availability, PostgreSQL version,
  column-level `UPDATE` grants plus triggers as used in
  [ARCHITECTURE_V1.md §7.8](ARCHITECTURE_V1.md#78-write-path-transactions-and-replay),
  and cost must be verified at CM-3.
- The classification of every Canonical Memory insert, including proposals, as **AAM**
  applies the current Approval Matrix as stated in the CM-0 independent review. The
  specific `APPROVAL_MATRIX.md` line for database mutations was not re-read or cited in
  this correction pass; it must be cited before CM-1 GO.
- `nova_knowledge_core/CURRENT/PRIME/*.md` bodies were not read directly; their rules are
  cited as enforced by `validate_current_prime_package`.
- Whether any live surface consumes `default_journal_workspace()['system']` (C1) was not
  traced.
- Deeper contents of `RULES/`, `CANDIDATES/`, `EVIDENCE/`, `OTE_INTELLIGENCE/` were not
  inventoried (C3).
- [OBSERVED] `tools/cowork/obsidian_policy.json`'s `project_doc` export class covers only
  `docs/claude-cowork/**`, so `docs/canonical-memory/**` is not exportable to Obsidian
  under the current policy. Changing the policy is out of scope.

---

## 7. Decisions still requiring Pedro

| ID | Decision | Recommendation | Needed by |
|---|---|---|---|
| D1 | Managed Postgres on Render as target store: plan, region, backup retention, cost, driver dependency | Approve in principle now; execute only at CM-3 after CM-2 GO | CM-3 |
| D2 | Cutover order of subject scopes | Operational/project → engineering → (PRIME only via D3) | CM-1 |
| D3 | Does PRIME doctrine ever move from Git to Canonical Memory? | No for V1; Git mirror records only | CM-1 |
| D4 | Approval channel and identity for promotions and cutover | Git: Pedro-authored commit or Pedro-approved PR carrying the four approval elements | CM-3 |
| D5 | Resolve the `core/state.py` journal-workspace defaults that disagree with PRIME (C1) | Separate, approved runtime change; not part of CM | Before CM-5 |
| D6 | Status of `EXECUTION_RULES/`, `INVALIDATION_RULES/`, `NO_TRADE_CONDITIONS/`, `WATCHLIST/` | Ingest as `historical` or not at all; never as current | CM-1 |
| D7 | Align `RESPONSIBILITY_CONTRACT.md` / `AUTOMATION_ARCHITECTURE.md` Obsidian wording with "generated projection" | Separate doc change after CM-0 acceptance | CM-6 |
| D8 | Confidence representation | Ordinal enum with required basis | CM-1 |
| D9 | Gate thresholds: golden-set size, relevance precision, token-reduction target, shadow window | Accept §3 proposals as starting points; set token target after first CM-2 measurement, before judging it | CM-2 |
| D10 | Token estimator reference for budgets | One named, versioned estimator per target model family, recorded in manifests | CM-2 |
| D11 | Are assistant workspace actions and `data/` runtime memories in scope? | Out of V1 | CM-1 |
| D12 | Does Codex reviewing Claude count as independent validation for engineering/project records? | Yes for engineering/project only; never strategy/risk/research | CM-3 |
| D13 | Switch the live Assistant from `retrieve_current_prime` to `hydrate` | Only at CM-7 after live golden set passes | CM-7 |
| D14 | Single candidate lane: `CANDIDATES/` vs Canonical Memory `proposed` | `CANDIDATES/` until cutover; one lane after | CM-5 |
| D15 | Retention and privacy of conversation-derived `agent_session` sources | Store hashes and references, not transcripts | CM-3 |

---

**Nothing in this document authorizes autonomous or funded trading**, any runtime,
schema, dependency, test, roadmap, Obsidian, strategy, risk, broker, execution, or flag
change, or any commit, push, merge, or deploy. The trading and execution subsystem
remains temporarily disabled. Exactly three PRIME execution models remain locked.

Agents change. NOVA remembers.
