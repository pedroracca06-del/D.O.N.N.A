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
| B1.7 | **Test Selector** — changed paths → focused test list, advisory only | Claude | AR | none | P0.9, B1.1, B1.2, B1.3, B1.4 (optional collision check), B1.6 | 201 selector tests (167 + 34 from the Phase 3W refinement); self / direct / transitive / relative / conftest-subtree / policy / dynamic-safety mapping, deletion, rename, case-only rename, escalation on unmapped-wildcard-unresolved-syntax-binary and on a changed **source** with unresolved dynamic imports, a recomputed proof that no statically discovered test importing a changed module is omitted, and five real-tree demonstrations showing an ordinary source change now returns a focused subset | none | **DONE (tool) — local only** |
| B1.8 | **Codex relay transport** — carry one report and one verdict, locally | Claude | AR | machine-local mailbox outside every repository (NOT created) | B1.1, B1.2, B1.3, B1.4 (read-only) | Relay test suite; seven fixed operations and 25 refused action verbs; canonical serialization and recomputed evidence digest; all four verdicts; planted false-PASS, prompt-injection, shell-payload, command-smuggling, traversal, machine-path, credential, replay, chain-corruption, stale-HEAD, dirty-tree, foreign-lock, archive-collision and simulated-replace-failure demonstrations | none — it approves nothing | **DONE (transport tool) — local only** |
| B1.9 | **One-shot Codex runner** — invoke Codex read-only, once, per completed phase | Claude | AAM | reads the repository read-only; writes one private temporary file | B1.8 | Runner test suite against a fake Codex: fixed three-operation CLI, exact argument array, proven stdin prompt, deterministic prompt bytes, one spawn only, no retry after success/non-zero/timeout/invalid-JSON/schema-failure/missing-output/drift, attempt consumed on start, allowlisted child environment with planted secrets excluded, stdout/stderr canaries contained, executable name/type/version/symlink/reparse refused, a real Windows junction escape refused, every precondition demonstrated, **zero skips** | **Pedro, per invocation** | **DONE (tool) — local only; never run against a real model** |
| B1.10 | **Controlled first live review** — one billed Codex review | Pedro | AM | one model request | B1.9 | Not started | **Pedro, every time** | **TODO — not authorized** |
| B1.11 | **Real mailbox initialization** at `${HOME}/.claude/nova-relay/` | Claude | AAM | creates a directory outside every repository | B1.8 | Not started | **Named approval required** | **TODO — not created** |

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

### B1.7 Test Selector — implemented (tool; local only)

`tools/cowork/test_selector.py` with the pure-data `test_selection_policy.json`
(sha256 `5cf3a817854c2c898d544e653b47c5799c81d76804bc8b3d6b753e5d45abf87c`), and
`tests/test_cowork_test_selector.py` (201 tests).

> **Phase 3W refinement (2026-09-03).** The dynamic-import rule below was narrowed so
> the tool is actually usable on this repository. Its status is unchanged:
> **DONE (tool) — local only**. See *Phase 3W refinement* at the end of this section.

**The governing rule, stated in every report.** A focused selection is a **fast
local feedback aid only**. It can never satisfy A7.7 by itself, replace collection
parity, replace the full regression suite required before a commit, claim that the
unselected tests would pass, or authorize staging, committing, pushing, merging, or
deployment. Every report carries `full_regression_required: true` and
`collection_parity_required: true` unconditionally, and policy validation refuses a
policy that tries to set either false or to claim any of those capabilities.

**Acceptance criteria — replacing the earlier unmeasurable wording.** The row
previously required "selection matches Pedro's choice on repeated trials", which
specified no trial count, no agreement threshold, and no tie-break, and could not be
satisfied in a test suite. It is replaced by mechanically verifiable evidence:

| Evidence | Result |
|---|---|
| Countable focused test suite | 201 tests (snapshot of 2026-09-03, not a constant) |
| Planted mapping demonstrations | 10, all as intended |
| Direct-import coverage | a changed module selects its direct importers |
| Transitive-import coverage | `core/base` → `core/middle` → `engines/top` → its test |
| Relative-import coverage | `from .sibling import …` resolved |
| Changed-test self-selection | a changed test selects itself |
| Conftest subtree selection | root and nested scopes, each limited to its own subtree |
| Policy/data mapping | a non-Python file maps through explicit policy |
| Deletion handling | the pre-change path's prior dependents are selected |
| Unmappable-path escalation | exit 5, full suite required |
| **Closure proof** | for every changed module, every statically discovered test that imports it directly or transitively is in the selection — recomputed independently from the reverse index, so a bug in the selection loop cannot hide behind itself |

**Corrected prerequisites.** P0.9, plus **B1.1** (all output through the Evidence
Formatter), **B1.2** (pinned baseline and staleness), **B1.3** (every Git call
through the A7 read-only allowlist), **B1.4** (optional read-only registry collision
check), and **B1.6** (changed-path observation, reused rather than duplicated). The
old row declared only P0.9 and so predated all of them.

**It imports and runs nothing.** It does not import an application or test module,
and it does not invoke pytest — **not even `--collect-only`**, which imports every
test module and conftest and would execute their module-level code. Mapping is built
by parsing tracked blobs with `ast` alone. A planted module whose top level writes a
marker file was mapped correctly and the marker was never created; no
`.pytest_cache` appeared. The selector owns no subprocess.

**Modes.** Six, all read-only: `select-worktree`, `select-staged`, `select-commit`,
`select-range`, `select-manifest`, `validate-policy`.

**Mapping sources.** `self`, `direct import`, `transitive import`, `conftest scope`,
`explicit policy`, `dynamic-test safety inclusion`, `global fallback`. A direct edge
is never downgraded to transitive, and a genuine mapping always outranks the safety
inclusion in the reported source.

**Escalation to full suite (exit 5).** An unmapped path, a global-impact path, a
Python file that will not parse, a **changed source file** whose own imports cannot
be read statically, a star import from an unresolvable module in a changed source, an
import that looks internal but resolves to no tracked file, an ambiguous bare module
name matching several tracked files, a binary change, a deleted test file, an
explicit mapping that declares no target, or a dynamic-test inventory that could not
be completed. **It never silently produces an empty or narrow selection.**

**Bare-module resolution.** The Cowork tools are imported by bare module name after a
`sys.path` insertion, which package paths cannot express, so a single-segment name
also resolves against tracked file basenames. A name matching more than one tracked
file is ambiguous and escalates rather than being guessed. A false positive here can
only make a selection **broader**, never narrower, so it cannot cause an omission.

**Proposed invocation.** A structured argument array — `["python", "-B", "-m",
"pytest", <validated targets>, "-q"]` — emitted as evidence and **never executed**.
The policy's argument template may contain only the fixed tokens `python`, `-B`,
`-m`, `pytest`, `-q`; arbitrary pytest flags, plugin arguments, environment
assignments, and shell fragments are refused.

**Documentation-only changes** report **no focused pytest target** and exit 0 while
stating explicitly that this does **not** mean no testing is required. Zero changed
paths is `stopped` (exit 4), with no testing conclusion implied.

**Collection counts are snapshots, never expectations.** 926 was the P0.9 snapshot
and 1722 the Phase 3U observation. Collection must be re-measured against the current
pinned HEAD and compared as exact node-ID sets; the selector never invokes collection
itself, and its source contains no expected collection constant.

**Static safety.** Standard library only; the dynamic names above appear only as
data strings for AST comparison — no `eval`, `exec`, bare `compile`, `__import__`,
`importlib`, or `runpy` is ever called; no subprocess, shell, or network; no
environment reads; no write-mode `open`; no deletion, move, or rename; no Session
Registry mutation. Its only writes are to stdout and stderr. Every Git call routes
through the A7 read-only allowlist and asks only for `rev-parse`, `ls-files`, and
`cat-file`. All output goes through the Evidence Formatter.

### Phase 3W refinement — dynamic tests are included, not an excuse to give up

The limitation recorded above has been corrected under explicit approval. It read:
`tests/test_ui_modularization.py` uses `exec(compile(...))` and
`importlib.import_module`, so its import set cannot be known by reading, and under
the old rule that made **every** selection on this repository escalate to the full
suite. The tool was correct and honest, and completely unusable here.

**What changed.** A test file whose own imports cannot be read statically is now
added to **every** focused selection instead of forcing a global full-suite fallback.
The selection can only get **broader**, never narrower, so nothing that should have
run is dropped — and one such file no longer makes focused feedback impossible for
every other change in the repository.

**What did not change. None of the governing rules moved:**

- Full regression before every commit remains **mandatory**. Every report still
  carries `full_regression_required: true`.
- Collection parity remains **mandatory** — `collection_parity_required: true`.
- A focused selection is still **preliminary feedback only**. It never satisfies
  A7.7 by itself, replaces nothing, and authorizes nothing.
- Unresolved changed **source** code still escalates.
- The selector still never invokes pytest and never imports a repository module.
- The selector still never claims that unselected tests would pass.

**Source-side ambiguity still escalates.** The concession is strictly test-side. If a
*changed source file* uses unresolved dynamic imports, dependency discovery from it
is unknowable — tests that should have been selected may be invisible — so it exits 5
and requires the full suite. A source-side unknown is never converted into an
always-include shortcut. Escalation is also unchanged for an unresolvable internal
import, an ambiguous module name, unparseable changed Python, a binary or unmapped
path, a changed or deleted test that cannot be identified, a global-impact policy
path, and a dynamic-test inventory that could not be completed.

**Detection is general and AST-based**, never a hard-coded filename. A test file is
inventoried as dynamic when its AST shows `importlib` / `import_module`,
`__import__`, `exec` or `eval`, `exec(compile(...))`, a dynamically constructed
module name, a loader or finder call (`SourceFileLoader`, `spec_from_file_location`,
`module_from_spec`, `exec_module`, `load_module`, `pkgutil`, `runpy`), an
unresolvable star import, or a `sys.path` mutation that **leaves an import
unresolved**. That last qualifier matters: the Cowork tools mutate `sys.path` and
then import a sibling by bare name, which the tracked-basename fallback resolves
exactly; treating every path mutation as unknowable would mark 54 of this
repository's files dynamic and destroy the usefulness this refinement exists for.
`re.compile` is deliberately *not* a trigger for the same reason.

**The inclusion cannot be switched off.** Four contract values are fixed and a policy
that disagrees is refused: `dynamic_test_safety_inclusion_enabled: true`,
`source_side_dynamic_ambiguity_escalates: true`, `dynamic_tests_can_be_excluded:
false`, `policy_can_downgrade_an_escalation: false`. Policy validation additionally
refuses any `exclusions` entry that names a test file or a test pattern under a test
root, and at runtime any tracked test file the scan could not classify is reported
and escalates rather than being silently dropped. A manifest has no field that can
remove a selected test; one that invents such a field is rejected as invalid.

**Evidence added to every report.** A `Y0` line gives the number of dynamic tests
detected and the number that could not be classified; one `Y###` line per dynamic
test gives its sanitized repository-relative path and why it was included; `Y_ADD`
records how many joined a focused selection versus how many were already selected by
a stronger mapping. Each selected test still reports which mapping produced it.

**Real-tree demonstrations (read-only, 2026-09-03, HEAD `4d7807a`).** Run against
synthetic change manifests; no real file was modified. 54 tracked test files exist,
one is dynamic (`tests/test_ui_modularization.py`), and none could not be classified.

| Changed path (synthetic) | Exit | Result |
|---|---|---|
| `tools/cowork/evidence_formatter.py` | 0 | **9** focused targets — 1 direct, 7 transitive, plus the dynamic test added by safety inclusion |
| `ui/styles.py` | 0 | **12** focused targets; the dynamic test was already selected by a genuine direct import, so 0 were added |
| `docs/NOVA_KNOWLEDGE_MAP.md` | 0 | **no focused pytest target**, full regression still required |
| `scripts/validate_alerts.py` | 5 | full suite — the changed Python file will not parse |
| `pytest.ini` | 5 | full suite — a global-impact path |
| `strange/thing.xyz` | 5 | full suite — the path is not mapped by any rule |
| `engines/synthesis.py` | 5 | full suite — a changed **source** with unresolved dynamic imports |

Before this refinement every one of those rows returned exit 5. The tool is now
useful for ordinary mapped changes, and **a focused selection is still not test
coverage** — it is preliminary feedback, and the full suite still runs before the
commit.

**Other limitations.** Mapping is static, so runtime-only coupling (fixtures
resolved by name, plugin hooks, data loaded by path at runtime) is invisible unless
declared in the policy. The explicit mappings encode this repository's layout and
need review after a reorganisation. And the tool proposes; it never runs.

**Status.** Implemented locally on `integration/nova-foundation`. **DONE (tool) —
local only. Not pushed, not merged.**

### B1.8 Codex relay transport — implemented (transport tool; local only)

`tools/cowork/codex_relay.py`, with the pure-data `relay_policy.json` and the
strict `relay_verdict_schema.json`, tested by `tests/test_cowork_codex_relay.py`.
Full contract: [CODEX_RELAY_CONTRACT.md](CODEX_RELAY_CONTRACT.md).

**What is done.** The local message transport: schema-versioned envelopes, hash
chaining, canonical serialization, a recomputed evidence digest, atomic
lock-protected mailbox updates, an append-only archive, and validation that
refuses unknown fields, traversal, machine paths, credentials, command-bearing
field names, replays, stale state, and prohibited intent.

**What is NOT done, and is not claimed.** Automatic Claude/Codex communication is
**not** complete. The transport does not invoke Codex, and no review has run. Three
separate items remain, each with its own approval: the one-shot runner (B1.9), the
first live review (B1.10), and real mailbox initialization (B1.11).

**Design corrections carried in from the Phase 3X audit.**

- Automated review will use `-a never`, not `-a on-request`. With `-s read-only`
  there is no prompt to socially engineer, and failures return to the model
  instead of to a human who might click through.
- **Codex never writes the authoritative mailbox.** Its output goes to a private
  temporary file; the relay validates it and then records a *relay-authored*
  response envelope. Codex's bytes are nested as data and never become an envelope.
- **No canonical machine path inside an envelope.** An earlier sketch bound each
  message to `canonical_worktree`, while also forbidding machine paths — the tool
  would have been exempting itself from its own rule. Envelopes now carry logical
  `repository_identity` and `worktree_identity`; the real path is supplied at the
  command line and verified against Git and the Session Registry there.
- **The archive is not called tamper-proof.** It is append-only *by this tool*,
  and the hash chain detects corruption, truncation, reordering, or partial
  rewriting. It cannot defeat someone who rewrites mailbox and archive together.
  The policy records this as
  `archive_is_cryptographically_tamper_proof: false`, and a policy claiming
  otherwise is refused.
- **PASS means "no objection found," never authorization.**

**Operations — exactly seven, no aliases.** `validate-policy`,
`validate-request`, `validate-response`, `submit`, `ingest-response`, `inspect`,
`verify-chain`. Twenty-five action verbs (`run`, `exec`, `review`, `retry`,
`approve`, `authorize`, `apply`, `edit`, `stage`, `commit`, `push`, `merge`,
`deploy`, `trade`, `sync`, `watch`, `daemon`, `force`, `override`, `repair`,
`delete`, `prune`, `clear`, `reset`, `resume`) exit 2 with an explanation.

**It invokes nothing.** Standard library only. No subprocess of its own, no
shell, no socket, no environment discovery, no model call. Git is reached only
through the A7 read-only allowlist and asks only for `rev-parse` and `status`.
The Session Registry is reached only through `read_registry` and `classify` — a
static test proves no mutating registry helper is called.

**Authorization behaviour.** A verdict must carry the exact non-authorization
sentence or it is rejected. `PASS` never appears as approval language in a
report. AAM and AM work still requires Pedro's named approval. The cap is one
review per `(phase, head)`; a `REVISE` verdict does not authorize resubmission
and there is no retry operation.

**Atomicity.** Sibling lock (`O_CREAT | O_EXCL`, bounded 5 s, never stolen),
re-read under the lock, same-directory temp file, `flush`, `fsync`,
`os.replace`. A validation or replacement failure leaves the prior mailbox
byte-identical, and an archive name collision stops rather than overwriting.

**Two bugs found by the tests and fixed before the commit.** The prohibited-intent
scanner matched the fixed non-authorization sentence itself — it ends "or enable
execution" — so every correct verdict was being rejected by its own disclaimer;
the sentence is now removed before that scan and still checked for exact
equality. And the command-key blocklist matched `path` and `allow`, which are
legitimate structural names in `diff_numstat` and `permission_state`; both were
removed from the blocklist, with path *values* still validated as
repository-relative.

---

### B1.9 One-shot Codex review runner — implemented (tool; local only)

`tools/cowork/codex_review_runner.py` with the pure-data
`codex_runner_policy.json`, tested by `tests/test_cowork_codex_review_runner.py`.
Full contract: [CODEX_RELAY_CONTRACT.md](CODEX_RELAY_CONTRACT.md).

**No live review has ever run.** Every test uses a generated fake Codex executable
under `tmp_path`. B1.10 (a controlled first live review) and B1.11 (real mailbox
initialization) remain TODO and unauthorized, and automatic Claude/Codex
communication is **not** operational.

**The stdin form was proven locally, not assumed.** `codex exec --help` on
codex-cli 0.153.0 states that the PROMPT argument reads from stdin when it is
omitted *or* when `-` is used. The runner uses the explicit `-` so the argument
array shows the intent and the prompt never touches a command line.

**Fixed invocation.** `codex exec -C <repo> -s read-only -a never -m gpt-5.6-luna
-c model_reasoning_effort="low" --ephemeral --ignore-user-config --output-schema
<committed schema> -o <private temp> -`. `--json` is omitted on purpose: local help
shows it only adds a stdout event stream the runner does not need. `--add-dir`,
`--approve-for-me`, both `--dangerously-bypass-*`, `--ignore-rules`,
`--skip-git-repo-check`, `resume`, `fork`, and `review` are never used, and a
policy naming any of them is refused.

**One attempt, consumed on start.** The review opportunity for a `(phase, head)`
is spent the moment the child process starts — success, failure, timeout, or
garbage alike. There is no retry flag, no loop, and no path that re-invokes
`review-once`; a static test proves the string never appears in a constructed
argument list. A precondition failure stops *before* the spawn and does not consume
the attempt.

**Environment minimization.** Ten allowlisted names, forwarded only when already
present. Tests plant `ANTHROPIC_API_KEY`, `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`,
`OPENAI_API_KEY`, `GITHUB_TOKEN`, `NOVA_AUTO_EXECUTE`, and
`NOVA_TRADING_SUBSYSTEM_ENABLED`, and assert the fake child's observed environment
contains none of them. No value is ever printed.

**Registry is read, never written.** A static test asserts the only
`session_registry` calls are `read_registry` and `classify`. The runner never
pauses, registers, closes, resumes, or advances a session — those stay manual.

**Ingest goes through the transport.** A valid response is recorded by calling
`codex_relay.main(["ingest-response", ...])`. The runner never opens the mailbox
for writing; a static test bounds every `codex_relay` call it makes.

**Zero skips, including the link branches.** The suite adds no permanent skip and
does not move the repository's skipped baseline. This machine grants junction
creation but refuses symbolic links without elevation, so the link branches are
covered three ways rather than skipped: a **real Windows junction** pointing
outside the mailbox root is created with `mklink /J` and refused; the
symlink branches are driven through the one path primitive they depend on; and
the file-shaped reparse point -- which a real junction cannot represent, since
junctions are directories and `S_ISREG` rejects them first -- is supplied as
controlled stat metadata. To make that last branch reachable at all,
`FILE_ATTRIBUTE_REPARSE_POINT` is now taken from `stat` when defined and pinned
to the Win32 value `0x400` otherwise, and the temporary directory refuses a
reparse point **by name** as well as by destination. Both are strengthenings; no
production check was relaxed to remove a skip.

**Windows test seam, disclosed.** Windows cannot execute an extension-less file, so
a portable fake Codex must run through an interpreter. Two module-level seams
(`_TEST_EXECUTABLE_OVERRIDE`, `_TEST_SPAWN_PREFIX`) exist for that. They are
`None` in production, no CLI option sets either, no envelope can reach them, an
autouse fixture asserts they are `None` before and after every test, and the spawn
seam *substitutes the executable* while leaving the production argument tail intact
— so the argument-contract tests assert on the real array.

---

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
