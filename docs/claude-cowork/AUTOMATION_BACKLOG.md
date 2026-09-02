# Automation Backlog

Every item carries an ID, owner, automation class, mutation scope, prerequisites,
evidence required, approval gate, and status.

Classes are defined in [APPROVAL_MATRIX.md](APPROVAL_MATRIX.md): **FA** fully
automatic · **AR** automatic read-only · **AAM** approval before mutation ·
**AM** always manual.

---

## Tier 0 — Completed foundation

| ID | Item | Owner | Class | Mutation scope | Prerequisites | Evidence required | Approval gate | Status |
|---|---|---|---|---|---|---|---|---|
| P0.1 | Install the corrected retirement guard | Claude | AAM | `.claude/hooks/**` | Validated candidate | Guard suite counts; installed hashes | Per-commit | **DONE** — installed, committed, **pushed** |
| P0.2 | Guard test harness | Claude | AR | none | P0.1 | **188 checks, 188 passed, 0 failed** | none | **DONE** |
| P0.3 | Permission cleanup | Claude | AAM | `settings.local.json` | Snapshot + manifest | Hash + counts before/after | Per-stage | **DONE** — now **338 allow / 31 ask / 8 deny** |
| P0.4 | Runtime-artifact ignore rules | Claude | AAM | `.gitignore` | Validated candidate | Ignore validation; files preserved on disk | Per-commit | **DONE** — committed and pushed |
| P0.5 | Triage the dirty working tree | Claude | AAM | working tree | P0.4 | Preservation manifest; clean status | Per-action | **DONE** — primary checkout clean, nothing deleted |
| P0.6 | Foundation worktree | Claude | AAM | new worktree | Clean tree | Worktree list; secured config verified | Named approval | **DONE** — local only |
| P0.7 | Knowledge-core casing normalization | Claude | AAM | 69 tracked paths | P0.6 | 69 R100 renames; blob identity; test parity | Per-commit | **DONE** — local only |
| P0.8 | Refresh `CLAUDE.md` | Claude | AAM | `CLAUDE.md` | P0.7 | Path existence; guard + suite results | Per-commit | **DONE** — local only |
| P0.9 | Pytest discovery defaults | Claude | AAM | `pytest.ini` | P0.8 | Collection parity (926 node IDs) | Per-commit | **DONE** — local only |
| P0.10 | Install these documents | Claude | AAM | `docs/claude-cowork/**` | P0.9 | Six files; guard suite | Per-commit | **DONE** — local only |

> Items P0.6–P0.10 exist **only on `integration/nova-foundation`**, which is
> neither merged nor pushed.

### Remaining prerequisites

| ID | Item | Owner | Class | Mutation scope | Prerequisites | Evidence required | Approval gate | Status |
|---|---|---|---|---|---|---|---|---|
| P0.11 | Raw-transcript copyright policy | Pedro | AM | policy | — | Decision recorded | Pedro only | **OPEN** |
| P0.12 | Decide Execution Phase 8 disposition | Pedro | AM | archived work | — | Decision recorded | Pedro only | **OPEN** |

---

## Tier 1 — Read-only trust layer

| ID | Item | Owner | Class | Mutation scope | Prerequisites | Evidence required | Approval gate | Status |
|---|---|---|---|---|---|---|---|---|
| B1.1 | **Evidence Formatter** — no claim without command + counts | Claude | FA | none (stdout only) | — | 53 formatter tests; guard 188/188; full suite 2 failed / 964 passed / 13 skipped | Per-commit | **DONE** — local only |
| B1.2 | **Staleness Guard** — re-read HEAD/hashes before reporting | Claude | FA | none (stdout only) | B1.1 | 61 guard tests incl. a local-bare-remote advance detected with no fetch; guard 188/188; full suite 2 failed / 1025 passed / 13 skipped | Per-commit | **DONE** — local only |
| B1.3 | **A7 battery** — seven gates: scope, secrets, machine paths, protected boundary, runtime/generated/copyright, baseline staleness, test-evidence parity | Claude | AR | none (stdout only) | B1.1, B1.2 | 84 battery tests; all seven gates demonstrated **failing** on planted input; guard 188/188 | Per-commit | **DONE** — local only |
| B1.4 | **Session Registry** — machine-local, outside every repo | Claude | AR→FA | registry file outside every repo | B1.2 | 104 registry tests (incl. 23 for `advance`); 10 planted demonstrations; collision, stale approval, lock contention, moved HEAD | **Named approval required for each real write** | **DONE** — local only; real registry initialized under separate approval; `advance` lifecycle correction added |
| B1.5 | **Worktree bootstrap validator** — verify a new worktree is secured | Claude | AR | none | B1.3, B1.4 | 86 validator tests; 9 planted demonstrations; tracked blobs, permission hash/counts, casing, submodule state, forbidden artifacts, registry compatibility | none | **DONE (tool)** — local only |
| B1.6 | **Change Classifier** — determine the minimum approval class a change requires | Claude | AR | none | B1.3 | 216 classifier tests; 10 planted demonstrations; every class, every mode, most-restrictive aggregation, semantic escalation | none | **DONE (tool) — local only** |
| B1.7 | **Test Selector** — changed paths → test list | Claude | AR | none | P0.9 | Selection matches Pedro's choice on repeated trials | none | TODO |

---

### B1.1 Evidence Formatter — implemented

`tools/cowork/evidence_formatter.py`, tested by `tests/test_cowork_evidence_formatter.py`.

**Purpose.** Render a JSON evidence document as Markdown or normalized JSON so
that no claim about repository or test state can be made without the command,
the counts, and the failures behind it.

**Contract.** Input is one UTF-8 JSON document (`schema_version: 1`) with
`phase`, `scope`, `checks`, and optional `tests`, `changes`, `repository_state`,
`permission_state`, `notes`. Output is deterministic: stable key and ID
ordering, explicit UTF-8 bytes, exactly one trailing newline.

**Derived status.** Overall status is computed from the check statuses, never
from a caller-supplied claim: any `fail` -> `failed`; else any `stopped` ->
`stopped`; else any `warning` -> `passed_with_warnings`; else `passed`. **Zero
checks can never yield `passed`.**

**Read-only boundary.** Executes nothing — command strings are data and are
never passed to a shell, a subprocess, `eval`, or `exec`. Writes no file. No
network. Reads no environment variable and no clock; a timestamp appears only if
supplied in the input. Standard library only.

**CLI.**

```bash
python -B tools/cowork/evidence_formatter.py --format markdown
python -B tools/cowork/evidence_formatter.py --format json
python -B tools/cowork/evidence_formatter.py --format markdown --input evidence.json
```

Output is stdout only; there is deliberately no output-file option.

**Exit codes.** `0` valid input formatted (whatever the checks reported) ·
`2` invalid usage or validation failure · `3` safety-limit rejection
(1 MiB size, depth 32, 1000-item collections).

**Privacy.** Values under credential-shaped keys are replaced wholesale;
recognizable credential formats are replaced without echoing the match; home
directories are rewritten to `${HOME}` by pattern, so no username reaches the
output. Ordinary prose such as "tokenizer" or "secret scan" is not redacted.
Errors are sanitized and never contain the rejected payload.

**Status.** Implemented locally on `integration/nova-foundation`. **Not pushed,
not merged.**

### B1.2 Staleness Guard — implemented

`tools/cowork/staleness_guard.py`, tested by `tests/test_cowork_staleness_guard.py`.

**Purpose.** Re-measure live repository state and compare it with an explicit
baseline, so a report can never assert a HEAD, ref, blob, permission count, or
worktree that was not observed at the moment of reporting.

**Baseline contract.** One UTF-8 JSON document (`schema_version: 1`) requiring
`expected_branch` and `expected_head`, with optional `expected_local_refs`,
`expected_remote_refs`, `require_clean_index`, `require_clean_worktree`,
`expected_tracked_blobs`, `expected_permission_state`,
`expected_submodule_gitlinks`, `expected_worktree_identity`, and `notes`.
Unknown fields are **rejected**, not ignored — a baseline can never smuggle in a
command, script, hook, environment value, or Git argument. Paths must be
repository-relative with no traversal; object IDs must be full and well-formed;
keys that collide after case normalization are rejected.

**Local-only by default.** No network unless `--check-remote <name>` is given
explicitly.

**Read-only Git allowlist.** Only `rev-parse`, `status`, `ls-files`, `ls-tree`,
`show-ref`, `remote`, `diff`, and `ls-remote` may ever run. Every invocation
uses an argument array; `shell=True` is never used; `--no-optional-locks`
prevents index refresh. No fetch, pull, push, merge, rebase, checkout, switch,
reset, restore, clean, add, commit, tag/branch mutation, submodule update,
config write, maintenance, or gc appears anywhere in command construction.

**Remote-truth mode.** `--check-remote <name>` adds exactly one command,
`git ls-remote --heads <validated-remote>`. The value must be a configured
remote **name** — a URL is rejected. Heads only; tags are not inspected. It
reads refs and updates nothing: FETCH_HEAD, refs, index, config, and the working
tree are proven unchanged by test. An unreachable remote is reported as
**stopped**, never as passed.

**Exit codes.** `0` fresh · `1` staleness detected · `2` invalid usage or
baseline validation failure · `3` safety-limit rejection · `4` observation
stopped or unavailable. Output is still rendered for `1` and `4`.

**Evidence Formatter integration.** The overall result is derived by
`evidence_formatter.derive_overall` through `normalize`, so the guard cannot
report "fresh" when a check failed. Rendering reuses the formatter's Markdown
and JSON writers rather than duplicating them.

**Privacy.** The repository root is normalized to `${REPO}`, home paths to
`${HOME}`; remote URLs and usernames are never printed. The permission file is
inspected only for its SHA-256 and parsed array lengths, never its entries.
Tracked files are compared by **Git blob ID**, not on-disk hash, so
`core.autocrlf` cannot cause a false alarm. Ignored files never count as drift.

**Status.** Implemented locally on `integration/nova-foundation`. **Not pushed,
not merged.**

### B1.3 A7 battery — implemented

`tools/cowork/a7_battery.py` with `tools/cowork/a7_policy.json`, tested by
`tests/test_cowork_a7_battery.py`.

**Purpose.** One reusable pre-mutation gate set. A candidate change set is
described by a manifest; the battery observes the repository and reports whether
the candidate is safe to offer.

**The seven gates.**

| Gate | Checks |
|---|---|
| **A1** Scope integrity | Observed changed paths equal the manifest's expectation. Detects missing, extra, duplicate, case-conflicting, and traversal entries; distinguishes staged, unstaged, untracked, committed, and submodule paths. Zero declared paths cannot pass when changes exist. |
| **A2** Secret / credential scan | Credential-shaped keys and recognized secret formats in candidate text. Binary files are classified, never decoded. Reports sanitized path, line, category, and a finding hash — **never a matched value**. |
| **A3** Machine-specific paths | Windows user profiles, Git-Bash user paths, home directories, temp/scratch, absolute drive paths. Portable placeholders (`${HOME}`, `${REPO}`, `${CLAUDE_PROJECT_DIR}`) are allowed. Usernames are never emitted. |
| **A4** Protected boundary | Retirement Tier 1, kill-switch files, hooks, settings, permissions, risk limits, strategy specs, broker/execution paths, and activation flags. Classification does not authorize: an **undeclared** protected change fails; a **declared** one produces a warning carrying its AAM/AM classification and never passes silently. |
| **A5** Runtime / generated / copyright | Runtime JSON, logs, caches, bytecode, temp output, credential files, and raw third-party transcripts are prohibited. `data/donna_settings.json` is the explicit tracked exception; original summaries and mockups are not prohibited; submodule gitlinks are classified separately. |
| **A6** Baseline staleness | Reuses the Staleness Guard's observations for branch, HEAD, refs, index/worktree, tracked blobs, permission hash and counts, gitlinks, and worktree identity. A stale required baseline fails; a stopped observation stops the battery. **Never fetches.** |
| **A7** Evidence / test parity | Validates **supplied** test evidence: commands recorded as data, expected vs observed passed/failed/skipped/errors/collected, new failures, missing suites, weakened expectations, and unsupported "all passed" prose. Absent evidence stops; it never passes. **No test is executed.** |

Worktree-session collision detection is deliberately **not** here; it belongs to
the Session Registry phase.

**Manifest contract.** UTF-8 JSON, `schema_version: 1`, requiring `phase`,
`change_scope`, `expected_paths`, `baseline`, and `required_test_suites`;
optionally `declared_protected_changes`, `stricter_protected_paths`,
`expected_submodule_gitlinks`, `notes`. Unknown fields, commands, scripts,
absolute or traversal paths, duplicates, unsupported scopes, abbreviated commit
IDs, and negation-style ("weakening") entries are all rejected.

**Scopes.** `staged` inspects only the index candidate; `worktree` distinguishes
tracked, staged, unstaged, and visible untracked changes; `commit` requires an
explicit **full** commit ID.

**Fixed minimum policy.** `a7_policy.json` is versioned data — no executable
content, no machine path, no secret, no permission entry. A manifest may add
`stricter_protected_paths`; it can never remove or weaken a minimum, and there
is no "disable this gate" option.

**Read-only boundary.** A fixed allowlist (`rev-parse`, `status`, `diff`,
`diff-tree`, `show`, `ls-files`, `ls-tree`, `cat-file`, `check-ignore`,
`show-ref`, `remote`) run as argument arrays with `--no-optional-locks`.
`shell=True` is never used, no mutating Git command can be constructed, and
`ls-remote` is reachable only through the Staleness Guard's explicit mode.
Machine-readable NUL-delimited Git output is used throughout; human-formatted
`git status` is never parsed.

**Exit codes.** `0` all gates pass · `1` one or more gates fail · `2` invalid
CLI/manifest/policy · `3` safety-limit rejection · `4` required observation
stopped/unavailable · **`5` gates pass but approval-required warnings exist**.

**Integration.** The overall result is derived through the Evidence Formatter,
so the battery cannot report a pass when a gate failed; rendering reuses the
formatter's writers, and A6 reuses the Staleness Guard's observer.

**Status.** Implemented locally on `integration/nova-foundation`. **Not pushed,
not merged.**

### B1.4 Session Registry — implemented (tool only; registry not initialized)

`tools/cowork/session_registry.py`, tested by `tests/test_cowork_session_registry.py`.

**Purpose.** Let one session discover that another already holds the same
worktree, branch, or file scope before it starts an audit or a staging plan.

> **The real registry does not exist.** Its designed location is
> `${HOME}/.claude/nova-session-registry.json`. The tool never creates it or its
> parent directory: `list` and `check` report "uninitialized" safely, and every
> mutating operation stops with exit 4. **The first real write requires Pedro's
> explicit approval as a separate step.**

**Schema.** Registry: `schema_version`, monotonic `revision`, `sessions`. Each
session carries exactly `session_id`, `worktree_identity`,
`canonical_worktree_path`, `branch`, `task`, `read_scope`, `write_scope`,
`protected_scope`, `started_at`, `heartbeat_at`, `status`, `owner`,
`expected_commit`. Status is `active` · `paused` · `closing` · `closed`.
Timestamps are RFC3339 UTC; scopes are repository-relative with no traversal, no
duplicates, and no case conflicts; commits are full object IDs; unknown fields,
NaN/infinity, and credential-shaped content are rejected.

**Operations.** `list` and `check` are read-only. `register`, `heartbeat`,
`pause`, `resume`, and `close` mutate and increment the revision. There is
deliberately **no prune, delete, clear, force, override, repair, or patch** —
`close` marks history and **no record is ever deleted**.

**Collision rules.** Same worktree where either session writes; same branch in a
different worktree where either writes; write/write, write/read, and
write/protected scope overlap; parent/child path overlap; Windows
case-equivalent scopes; expected-commit mismatch on the same worktree; duplicate
session id. Two genuinely read-only sessions, disjoint scopes, and closed records
do **not** collide.

*Documented limitation:* arbitrary glob intersection is not decidable. Only a
single trailing `/**` or `/*` is treated exactly; anything more complex is
**conservatively escalated to approval** rather than assumed disjoint.

**Stale model.** Default threshold 30 minutes, configurable. `active` within
threshold is live; `active`/`paused` beyond it is stale; `closing` stays visible;
`closed` is historical and non-colliding. A **live** collision blocks (exit 1); a
**stale or ambiguous** one requires Pedro's decision (exit 5) and never silently
permits. A heartbeat later than the observation time is reported as a backward
clock. Stale records are never removed automatically.

**Atomic write.** An `O_CREAT|O_EXCL` sibling lock — atomic on Windows as well as
POSIX, no advisory locking — with a finite timeout. A lock this process did not
create is **never broken**. After acquiring it the registry is re-read and its
revision compared to prevent lost updates; a complete temporary sibling is
written, flushed, fsynced, and atomically replaced with restrictive permissions.
If anything fails the original is preserved byte-for-byte and no temporary file
or foreign lock is left behind.

**Worktree verification.** `--repo` on `check`/`register`/`resume` reuses the
Staleness Guard's read-only observer to confirm worktree identity, branch, and
HEAD against `expected_commit`. It never fetches; a mismatch blocks.

**Exit codes.** `0` read or safe mutation · `1` live collision or rejected
transition · `2` invalid CLI/schema/record · `3` safety-limit rejection ·
`4` registry unavailable, corrupt, or locked, or worktree observation failed ·
`5` stale/ambiguous collision requiring Pedro's decision.

**Privacy.** Rendered through the Evidence Formatter. No machine path, username,
environment value, or credential appears in output, and registry contents are
never dumped wholesale — only sanitized identifiers, statuses, and collision
categories.

#### Lifecycle correction: `advance`

**Why it is necessary.** A registered session pins `expected_commit`. The moment
that session makes an approved local commit, its own registry record is stale
against the worktree it is working in — every later `check`, `resume`, or
worktree verification reports a mismatch, and the registry starts arguing with
reality. Without a safe way to move the pin forward, the only alternatives were
editing the JSON by hand or closing and re-registering the session, both of which
defeat the point of the record.

**What it does.** `advance` moves one **active** session's `expected_commit` from
the commit it currently records to the repository's **current HEAD**, and updates
`heartbeat_at`. Nothing else changes.

```bash
python -B tools/cowork/session_registry.py advance \
  --registry <path> --format json \
  --session-id <id> --previous-commit <full-oid> --repo <worktree>
```

**Gates — all must hold, or the registry is left byte-identical.**

| Gate | Rule |
|---|---|
| Status | the session must be `active`; `paused`, `closing`, and `closed` are refused |
| Previous commit | must be supplied as a **full** object id and match the stored value exactly |
| Repository | `--repo` is mandatory; its worktree identity must match the record |
| Branch | HEAD's branch must match the record; **detached HEAD is refused** |
| Movement | HEAD must differ from the previous commit — nothing to advance to otherwise |
| **Ancestry** | the previous commit must be an **ancestor** of HEAD |
| Revision | compare-and-swap under the lock; a registry that moved is refused |
| Lock | a foreign lock stops the operation (exit 4) and is never broken |
| Fields | only `expected_commit` and `heartbeat_at` may differ afterwards |

**The destination can never be supplied.** It is derived exclusively from the
verified repository HEAD. There is no `--target`, `--new-commit`, `--force`,
`--rewind`, or `--override`, and `--previous-commit` is rejected on every other
operation.

**Forward-only.** Because the recorded commit must be an ancestor of HEAD, a
rewind, an amend, or a rebase that rewrites the recorded commit is refused rather
than absorbed. Re-running an advance after it succeeded is refused too, since
HEAD has not moved again.

**No automatic advancement.** Nothing advances on its own. It runs only after a
reviewed local commit, as an explicit step.

**Advancing approves nothing.** It records where a session now sits. It does not
push, merge, deploy, or endorse the commit, and it grants no permission.

**Ancestry implementation.** `merge-base` was added to the Staleness Guard's
read-only allowlist for this single purpose. Only the exact
`merge-base --is-ancestor <full-oid> <full-oid>` form is accepted — enforced
inside `_git`, not at the call site, so no caller can construct another shape.
Plain `merge-base`, `--all`, `--fork-point`, `--octopus`, ref names, and
abbreviations are all refused. Argument arrays only, no shell, no fetch, and no
ref or index mutation.

**Status.** Tool implemented locally on `integration/nova-foundation`, with the
lifecycle correction above. **B1.4 remains DONE locally. Not pushed, not merged.**
The real registry was initialized under separate approval; the first real write
remains a decision Pedro makes, not one automation takes.

### B1.5 Worktree bootstrap validator — implemented (tool; local only)

`tools/cowork/worktree_bootstrap_validator.py`, with
`tests/test_cowork_worktree_bootstrap_validator.py` (86 tests).

**The one question it answers.** Is this Git worktree safely configured for its
declared role *before* an automated session begins? It compares an explicit
manifest against what the worktree actually is, and reports.

**What it will not do.** It never creates or removes a worktree, creates or
switches a branch, copies or edits a file, initializes or updates a submodule,
installs settings or hooks, stages, commits, fetches, contacts a remote, runs a
test command, mutates the Session Registry, or repairs any mismatch it finds.
It writes only to stdout and stderr. A static test proves the source contains no
mutating Git verb, no write-mode `open`, no deletion helper, and no environment
read.

**No new capability.** Every Git call is routed through the A7 battery's existing
fixed read-only allowlist, so the validator can ask Git nothing that A7 could not
already ask. Rendering goes through the Evidence Formatter, so the verdict is
derived from the checks and cannot be asserted by a caller.

**Gates.**

| Gate | Question |
|---|---|
| A | Identity — resolves as a worktree, expected name, branch, HEAD, common Git directory, and the supplied path *is* the top level |
| B | Cleanliness — index, worktree, and no interrupted Git operation |
| C | Tracked content — declared files compared **by Git blob id** |
| D/E | Local state — declared ignored files present, hashed, JSON, ignored, untracked; permission file counts and uniqueness |
| F | Casing — required and forbidden tracked prefixes, case-normalized collisions |
| G | Submodules — gitlink identity and declared population state |
| H | Forbidden artifacts — inherited runtime state, transcripts, Cowork lock/temp residue |
| I | Registry compatibility — the declared session is present, active, fresh, pinned to this worktree/branch/commit, and collision-free |

**Why blob ids.** Under `core.autocrlf` a fresh checkout stores CRLF while an
older one holds LF, so identical content has different file hashes. Blob identity
is the only comparison stable across worktrees. A planted CRLF worktree passes
while its on-disk sha256 differs from the blob id.

**Demonstrated.** Nine planted cases, each producing the intended outcome: a
valid worktree (exit 0), stale HEAD, a wrong permission-file hash, an uppercase
`NOVA_KNOWLEDGE_CORE/` tracked path, a wrong gitlink, an accepted *unpopulated*
submodule (exit 0 — matching the real `mcp/tradingview`), a live registry
collision, a forbidden raw transcript, and the CRLF case above. The registry was
byte-identical before and after every run.

**Measured against the real worktree.** Run against `nova-foundation` itself the
validator returns exit 0 with 30 checks passing, including 338/31/8 permission
counts, the `.claude/settings.local.json` hash, 69 lowercase knowledge-core
paths with zero uppercase, the unpopulated `mcp/tradingview` gitlink, and the
live `claude-foundation-improvements` registry session.

**Status.** Implemented locally on `integration/nova-foundation`. **DONE (tool)
— local only. Not pushed, not merged.** It grants no permission; a failing or
approval-required verdict is information for Pedro, not a gate automation may
clear on its own.

### B1.6 Change Classifier — implemented (tool; local only)

`tools/cowork/change_classifier.py` with the pure-data `change_policy.json`
(sha256 `febb9138a313f61ca09f8aac7d286ec0cb8637fd40d47d9c334769fe38635b99`), and
`tests/test_cowork_change_classifier.py` (216 tests).

**The one question it answers.** What is the *minimum* approval class an observed
or proposed change requires?

**It never approves.** There is no output value meaning "approved", no class named
for it, no exit code carrying it, and no flag, policy field, or input that can
produce one. It reports observed scope, minimum required class, reasons and the
policy rules behind them, unresolved ambiguity, and what escalation is required.
Classification authorizes nothing: it does not stage, commit, push, merge, deploy,
mutate a registry, or execute a proposed command.

**Classes and ordering.**

| Class | Meaning | Exit |
|---|---|---|
| `FA_AR` | fully automated / automated read-only; no approval | 0 |
| `AAM` | automated with an approval naming exact targets | 5 |
| `AM` | always manual; Pedro performs or explicitly commands it | 6 |
| `PROHIBITED` | must not proceed under any approval | 7 |

Each path is classified independently and the overall result is the **most
restrictive class present**. Aggregation can only ever move upward.

**The repository-write floor.** Any change to a repository path is at least AAM.
A repository write is never FA/AR merely because its content is documentation;
FA/AR is reachable only by a declared read-only operation that changes no path.
Policy validation refuses a policy that tries to lower this floor.

**Fail-safe.** An unrecognized path, an unrecognized change kind, unscannable
content, or any ambiguity escalates to AM. Nothing resolves downward by default.
A deletion is never classified below a modification of the same path. Both sides
of a rename are classified, so a destination can never soften its source. Binaries
escalate to at least AAM, and to AM inside a sensitive area, because they cannot be
read for intent. Submodule gitlinks are AM. Raw transcripts and runtime or
generated artefacts are PROHIBITED as tracked content. Ignored files never enter a
Git-mode classification; they are classified only when a manifest names them
explicitly. That a path is already tracked authorizes nothing about changing it now.

**Modes.** Six, all read-only: `classify-worktree`, `classify-staged`,
`classify-commit`, `classify-range`, `classify-manifest`, `validate-policy`.
Git object ids are validated before use, and `--expected-head` / `--expected-branch`
stop the run when the baseline has moved. HEAD is re-read after observation, so a
commit landing mid-run stops rather than producing a stale answer.

**Semantic escalation — and its limits.** Eleven indicators: retirement-flag
activation, guard bypass, LLM-to-order-path wiring, autonomous order submission,
credential material, and automatic research promotion (all PROHIBITED); risk-limit
change, kill-switch change, broker order API, research-authority promotion, and
deployment or history-rewrite intent (all AM). A finding may **raise** a path's
class and can never lower one. Matched text is never captured or printed — only the
indicator identifier, its class, and its declared reason.

> Semantic scanning is defence in depth. **It cannot prove the absence of dangerous
> behaviour.** A file that trips no indicator has not been shown to be safe; it has
> only failed to match a known pattern. Path rules and the declared operation remain
> the primary controls.

**Pure-data policy.** The policy carries identifiers, classes, and human-readable
reasons only — no regular expression, no command, no machine path, no credential,
and no disable switch. Detection patterns live in the classifier source, which is
fixed and reviewable. Validation refuses a policy whose declared indicator set
disagrees with the implemented one, so neither half can drift unnoticed.

**Manifest mode.** Proposed paths, change kinds, optional old/new content hashes,
optional sanitized semantic finding identifiers, and a declared operation. Executable
commands, scripts, environment values, credentials, URLs carrying secrets, traversal,
absolute paths, and unknown fields are all rejected at exit 2.

**Exit codes.** 0 FA/AR only, 5 AAM, 6 AM, 7 PROHIBITED, 2 invalid input/usage/
policy, 3 safety limit, 4 stopped. **A clean or zero-change input is `stopped`, not
passed and not approved.**

**Demonstrated.** Ten planted cases, each producing the intended verdict: a
read-only evidence operation (FA/AR), a Cowork documentation edit (AAM), an ordinary
UI edit (AAM), a strategy/risk change (AM), a submodule pointer (AM), retirement-flag
activation (PROHIBITED), LLM order-path wiring (PROHIBITED), mixed AAM + AM (AM),
mixed AM + prohibited (PROHIBITED), and zero changes (stopped).

**Static safety.** Standard library only; no `eval`, `exec`, or bare `compile`; no
subprocess or shell of its own; no network library; no environment reads; no
write-mode `open`; no deletion, move, or rename; no mutating Git verb; no Session
Registry mutation. Its only writes are to stdout and stderr. Every Git call routes
through the A7 battery's read-only allowlist and asks only for `rev-parse`, `diff`,
`diff-tree`, `ls-files`, and `cat-file`. All output goes through the Evidence
Formatter.

**Known limitations.** Semantic scanning is pattern-based and defeatable by
obfuscation; it is a second line, never the first. Classification is per-path and
does not reason about interactions between files. Binary intent is not analysed at
all, only escalated. The policy's path rules encode this repository's layout, so a
significant reorganisation needs a policy review. And the tool reports a *minimum* —
a change may still warrant more caution than any rule captures.

**Status.** Implemented locally on `integration/nova-foundation`. **DONE (tool) —
local only. Not pushed, not merged.**

## Tier 2 — Proposal layer

| ID | Item | Owner | Class | Mutation scope | Prerequisites | Evidence required | Approval gate | Status |
|---|---|---|---|---|---|---|---|---|
| B2.1 | Staging Plan Builder | Claude | AAM | index | B1.3, B1.6 | Literal path list shown in full | Per-plan | TODO |
| B2.2 | Staged Diff Reviewer | Claude | AR | none | B2.1 | Full cached diff | none | TODO |
| B2.3 | Commit Executor | Claude | AAM | commits | B2.2 | Paths + message + tests + audit together | Per-commit | TODO |
| B2.4 | Doc Staleness Detector | Claude | AR | none | P0.8 | Mechanically checkable claims only | none | TODO |
| B2.5 | Retirement-Boundary Linter | Claude | AR | none | — | Flags a planted stale reference | none | TODO |
| B2.6 | **Knowledge provenance validator** — every note has source, date, and observation-vs-rule status | Claude | AR | none | B1.3 | Validation over the knowledge core | none | TODO |

---

## Tier 3 — Knowledge and research

| ID | Item | Owner | Class | Mutation scope | Prerequisites | Evidence required | Approval gate | Status |
|---|---|---|---|---|---|---|---|---|
| B3.1 | Three-layer extraction template (source claims / interpretation / approved rules) | Claude | AR | none | P0.11 | Approved layer left empty | none | TODO |
| B3.2 | Source acquisition with lineage recording | Claude | AAM | research files | P0.11 | Provenance + stated limitations | Before any network fetch | TODO |
| B3.3 | Conflict detector across sources | Claude | AR | none | B3.1 | Conflicts tabulated, not reconciled | none | TODO |
| B3.4 | **Obsidian adapter** — manual, approval-gated, configurable vault path | Claude | AAM | vault files | B2.6, B3.1 | 185 planner tests; 9 planted demonstrations; stable IDs, provenance, conflict stop, exit-5 approval gate | Per-sync | **IN PROGRESS — read-only planner complete locally; apply engine not authorized** |

### B3.4 Obsidian sync planner — read-only half implemented (local only)

`tools/cowork/obsidian_sync_planner.py` with the fixed `obsidian_policy.json`
(sha256 `a39de8e4ba247944797ceef105ba30a6be4a71ebfc59c48d3aaeba3c41237221`), and
`tests/test_cowork_obsidian_sync_planner.py` (185 tests).

**Authority model.** Git is authoritative for approved specifications and promoted
knowledge. Obsidian is a non-executing knowledge and working-note surface. Obsidian
content is never executable instruction, and it can never modify strategy, risk,
broker, execution, kill-switch, guard, permission, deployment, or runtime state.
There is no automatic two-way synchronization. Conflicts stop planning; they are
never silently merged. Nothing is ever deleted. Research stays observation until
separately promoted, raw third-party transcripts stay local and excluded, and
credentials, account data, broker data, runtime state, and secrets never enter a
plan. The policy declares `execution_authority: none` and carries no disable switch;
validation refuses a policy that tries to set any of those the other way.

**Read-only operations.** Exactly five: `validate-policy`, `inventory`,
`plan-export`, `plan-import`, `check-plan`. There is no `apply`, `sync`, `watch`,
`daemon`, `write`, `copy`, `move`, `delete`, `rename`, `install`, `initialize-vault`,
`create-vault`, `repair`, `force`, `override`, `merge`, `resolve`, or plugin
management — driving the parser with any of those verbs exits 2, and a test asserts
it for every one of them.

**No vault discovery.** The vault root is supplied explicitly on the command line
or it is not used at all. There is no read of `HOME`, Documents, OneDrive, Dropbox,
drives, Obsidian configuration, the process environment, or installed applications;
static tests assert the module references no such name. A vault is never created.

**Stable identity.** `nova-<first 16 hex of sha256(authority + NUL + normalized
source path)>`. Deterministic and documented, containing no username and no machine
path, stable for the same source identity. A note claiming an id is never believed —
the id is always recomputed and a mismatch is a conflict. Because the path is the
input, a rename changes the id, which is deliberate: renames require an explicit
migration and there is no automatic rename detection.

**Provenance.** Eight required fields: `nova_id`, `nova_schema`, `nova_source`,
`nova_source_blob`, `nova_source_hash`, `nova_classification`, `nova_authority`,
`nova_sync_state`, with optional `nova_title`, `nova_last_sync_hash`, and
`nova_approval`. All vault metadata is untrusted: duplicate keys, unknown `nova_*`
control keys, missing fields, malformed values, absolute paths, traversal,
credential-shaped values, executable directives, and authority claims beyond policy
are all rejected.

**Metadata parser.** A deliberately tiny fixed-scalar subset, not YAML. A `---`
block of `key: value` lines, lowercase identifier keys, plain or simply double-quoted
scalars, and **every value stays a string** — nothing is coerced. Anchors, aliases,
tags, block and folded scalars, flow collections, directives, merge keys, comments,
blank lines, indentation, single quotes, multiple documents, and a byte-order mark
are each rejected by name rather than guessed at.

**Export classifications.** Exactly one of `create`, `unchanged`, `update-safe`,
`conflict`, `excluded`, `stopped`. `update-safe` requires validated provenance
proving the note corresponds to the previously synchronized source *and* that its
body has not independently changed; a note carrying no recorded body hash cannot
prove that, so it is a conflict rather than a safe update. Both sides changed is a
conflict. Tracked status is never approval, and a tracked file beneath an excluded
path stays excluded.

**Import classifications.** Strictly more restrictive: `no-change`,
`candidate-import`, `conflict`, `excluded`, `stopped`. A candidate requires validated
identity and provenance, an already-authorized source mapping, a permitted
classification, an explicitly permitted candidate destination, no authority
escalation, and no prohibited or executable content. An approved classification can
never originate in the vault. **An import plan is never approval and never writes a
repository file** — any candidate exits 5 and waits for Pedro.

**Why two hashes.** The Git blob id is the exact identity of a source; the content
hash is taken after folding CRLF/CR to LF and dropping a byte-order mark, so a CRLF
checkout and an LF checkout plan identically. A note records the hash of its *body*,
never of its whole file, because a file cannot contain its own hash.

**Markdown is data.** Wiki links, embeds, templates, Dataview syntax, code fences,
and plugin syntax are read as bytes and never executed. Forms the policy prohibits
are rejected; everything else is preserved inertly. A planted note containing a
shell substitution wrote nothing.

**Limits.** Implementation maximums: 1 MiB input, 512 KiB per Markdown file, 1000
collection items, depth 32, 512-character paths, 32 frontmatter fields, 1000 plan
items. A policy may lower any of them; raising one is a safety-limit rejection at
exit 3, proven for every limit.

**Exit codes.** 0 valid, 1 conflict or policy violation, 2 invalid input/policy/
metadata/usage, 3 safety limit, 4 stopped, 5 approval required. Evidence is rendered
for 1, 4, and 5 as well as 0. Secret values, usernames, raw absolute paths, excluded
document bodies, permission entries, and raw registry contents are never printed.

**Demonstrated.** Nine planted cases: eligible create, unchanged note, safe update,
both-sides-changed conflict, tracked raw transcript excluded, candidate import at
exit 5, authority escalation denied, a junction escaping the vault root stopped, and
twenty repeated runs producing exactly one digest per operation and format.

**Static safety.** Standard library only; no `eval`, `exec`, or `compile` of input;
no subprocess or shell of its own; no network library; no environment or vault
discovery; no write-mode `open`; no deletion, replacement, move, or rename; no
Obsidian configuration or plugin access; no repository mutation; no Session Registry
mutation. Every Git call routes through the A7 battery's existing read-only
allowlist and asks only for `rev-parse`, `ls-files`, and `cat-file`. All rendering
goes through the Evidence Formatter.

**Remaining work — not authorized.** The apply engine does not exist: writing an
exported note into a vault, promoting an approved candidate into the repository, a
sync ledger, conflict presentation UI, and any scheduling. Each of those is a
separate, separately approved piece of work. Nothing here grants permission to write
to a vault or to the repository.

**Status.** Implemented locally on `integration/nova-foundation`. **Not pushed, not
merged.** No real Obsidian vault has been discovered, inspected, created, or
modified at any point.

---

## Tier 4 — Intelligence and future trading contracts

| ID | Item | Owner | Class | Mutation scope | Prerequisites | Evidence required | Approval gate | Status |
|---|---|---|---|---|---|---|---|---|
| B4.1 | **NOVA Brain output contract** — schema for structured analysis, explicitly non-instructional | Pedro + Claude | AAM | spec + tests | B2.6, B3.1 | Schema, tests, worked examples | Pedro approves the contract | TODO |
| B4.2 | Brain implementation against the contract | Claude | AAM | source | B4.1 | Contract conformance tests | Per-commit | TODO |
| B4.3 | **Risk engine interface contract** — independent veto, non-overridable | Pedro + Claude | AAM | spec + tests | B4.1 | Veto demonstrated to win | Pedro only | TODO |
| B4.4 | **Execution engine interface contract** — mechanics only, originates nothing | Pedro + Claude | AAM | spec + tests | B4.3 | No decision path in the interface | Pedro only | TODO |
| B4.5 | **NOVA Trader architecture** — deterministic policy, approved strategies only | Pedro | AM | spec | B4.1–B4.4 | Full staged ladder defined | Pedro only | **BLOCKED** |

---

## Tier 5 — Multi-worktree structure

| ID | Item | Owner | Class | Mutation scope | Prerequisites | Evidence required | Approval gate | Status |
|---|---|---|---|---|---|---|---|---|
| B5.1 | Integrate with current remote `main` | Pedro + Claude | AM | branches | P0.10, B1.5 | Re-measured divergence; conflict review | Pedro only | TODO |
| B5.2 | `nova-development` worktree | Claude | AAM | new worktree | B1.5, B5.1 | Bootstrap validator pass | Named approval | TODO |
| B5.3 | `nova-research` worktree | Claude | AAM | new worktree | B5.2 | Bootstrap validator pass | Named approval | TODO |
| B5.4 | `nova-indicator` worktree | Claude | AAM | new worktree | B5.2 | Bootstrap validator pass | Named approval | TODO |
| B5.5 | Cross-worktree transfer discipline (patch/cherry-pick only) | Claude | AM | commits | B5.2 | Transfer demonstrated without file copying | Pedro only | TODO |

---

## Deliberately excluded

| Item | Why |
|---|---|
| Auto-push / auto-deploy | Reaches other machines. Permanently manual |
| Auto-merge / auto-rebase | Silent conflict resolution on shared branches |
| Auto-`restore` / auto-`clean` | Destroys uncommitted work |
| Auto-fix failing tests | Turns a verification signal into a moving target |
| Auto-promote research to rules | Violates the standing strategy-approval rule |
| Auto-edit trading specifications | Pedro's authority |
| Auto-rotate credentials | Outside remit |
| A "commit when tests pass" loop | Removes the approval that makes the system safe |
| Any automated order submission | Prohibited without exception |

---

## Note on counts

Figures such as test totals and file counts are **snapshots at the time of
measurement**, not invariants. Re-measure before relying on any of them. Where
this backlog states a count (188 guard checks; 338/31/8 permissions), it reflects
the verified state at the time these documents were installed.
