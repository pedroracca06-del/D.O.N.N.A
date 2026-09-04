# NOVA Claude/Cowork — Operating Architecture

## Purpose

This directory defines how Claude Code (and any future "Cowork" automation) is
allowed to operate on the NOVA repository: what runs unattended, what requires an
approval naming exact targets, what is always Pedro's decision, and what is never
permitted at all.

The governing rule is one sentence:

> Automation may **observe, analyse, propose, and verify** without asking.
> It may **mutate** only after an explicit approval that names exactly what will
> change. It may **never** perform an outward-facing or irreversible action.

Everything in these documents is an application of that rule.

## Document index

| Document | Answers |
|---|---|
| [APPROVAL_MATRIX.md](APPROVAL_MATRIX.md) | For a given action, what approval is required? |
| [AUTOMATION_ARCHITECTURE.md](AUTOMATION_ARCHITECTURE.md) | Actors, source-of-truth split, worktree model, session registry, evidence gates, Obsidian, Brain/Trader handoff |
| [AUTOMATION_BACKLOG.md](AUTOMATION_BACKLOG.md) | What is built, what is next, and each item's approval gate |
| [PHASED_IMPLEMENTATION_ORDER.md](PHASED_IMPLEMENTATION_ORDER.md) | In what order, with what exit criteria |
| [RESPONSIBILITY_CONTRACT.md](RESPONSIBILITY_CONTRACT.md) | Who owns what, and the invariants that never bend |

## Completed foundation

The following is done and verified. Each claim below was measured, not assumed.

| Item | State |
|---|---|
| Retirement guard | Installed at `.claude/hooks/nova_guard_hook.py`, wired via `.claude/settings.json`, **committed and pushed** to `retirement/disable-legacy-trading` |
| Guard test suite | **188 checks, 188 passed, 0 failed** (`python -B .claude/hooks/test_nova_guard_hook.py`) |
| Local permissions | Reduced to **338 allow / 31 ask / 8 deny**, installed and validated in two stages |
| Runtime artifacts | Ignored via `.gitignore` — runtime JSON, `data/` scratch files, and raw transcripts are hidden but **preserved on disk** |
| Primary checkout | Clean — `git status --porcelain` and `-uall` both empty |
| Foundation worktree | Created as a sibling of the primary checkout, on branch `integration/nova-foundation` |
| Knowledge-core casing | Normalized to lowercase `nova_knowledge_core/` — 69 path-only renames, zero content change |
| `CLAUDE.md` | Refreshed: retirement boundary, modular UI, `intelligence/`, test commands, worktree and permission guidance, responsibility boundaries |
| Pytest discovery | `pytest.ini` pins `testpaths = tests`; collection parity verified at 926 node IDs |

**The casing normalization, `CLAUDE.md` refresh, and `pytest.ini` exist only on
`integration/nova-foundation`. That branch has not been merged and has not been
pushed.** Only the guard and the ignore rules are on a remote branch.

## Immediate next automation sequence

1. ~~**Evidence Formatter**~~ — **implemented locally** as `tools/cowork/evidence_formatter.py` (53 tests). Deterministic, executes nothing, writes no file, derives overall status from the checks rather than trusting a caller. See [AUTOMATION_BACKLOG.md](AUTOMATION_BACKLOG.md#b11-evidence-formatter--implemented).
2. ~~**Staleness Guard**~~ — **implemented locally** as `tools/cowork/staleness_guard.py` (61 tests). Re-measures branch, HEAD, refs, index, worktree, tracked blobs, permission hash and counts, gitlinks, and worktree identity against an explicit baseline. Local-only by default; `--check-remote` reads refs via `git ls-remote` without fetching, proven not to touch FETCH_HEAD, refs, index, or config. See [AUTOMATION_BACKLOG.md](AUTOMATION_BACKLOG.md#b12-staleness-guard--implemented).
3. ~~**A7 battery**~~ — **implemented locally** as `tools/cowork/a7_battery.py` with the versioned `a7_policy.json` (84 tests). Seven gates: scope integrity, secrets, machine paths, protected boundary, runtime/generated/copyright, baseline staleness, and test-evidence parity. Every gate was demonstrated **failing** on planted input. A declared protected change yields exit 5 (approval required) rather than a silent pass. See [AUTOMATION_BACKLOG.md](AUTOMATION_BACKLOG.md#b13-a7-battery--implemented).
4. ~~**Session Registry**~~ — **implemented locally** as `tools/cowork/session_registry.py` (104 tests). Detects worktree, branch, and scope collisions between concurrent sessions; live collisions block, stale or ambiguous ones escalate to you. It never deletes a record — `close` marks history. `advance` moves an active session's pinned commit forward after a reviewed local commit: the destination is always the verified HEAD, it must be a descendant of the recorded commit, and there is no force or rewind. Advancing records where a session sits — it approves nothing and never pushes, merges, or deploys. The real registry has been initialized under separate approval; each write remains your decision. See [AUTOMATION_BACKLOG.md](AUTOMATION_BACKLOG.md#b14-session-registry--implemented-tool-only-registry-not-initialized).
5. ~~**Worktree bootstrap validator**~~ — **implemented locally** as `tools/cowork/worktree_bootstrap_validator.py` (86 tests). Answers one question before an automated session begins: is this worktree safely configured for its declared role? It checks identity, cleanliness, tracked content, local and permission state, path casing, submodules, forbidden inherited artifacts, and registry compatibility against an explicit manifest. Tracked files are compared **by Git blob id**, so `core.autocrlf` cannot cause a false failure. It observes only — it never creates, removes, repairs, populates, or registers anything, and every Git call reuses the A7 battery's existing read-only allowlist rather than adding a new capability. Nine planted cases were demonstrated, and against the real foundation worktree it returns exit 0 with 30 checks passing. See [AUTOMATION_BACKLOG.md](AUTOMATION_BACKLOG.md#b15-worktree-bootstrap-validator--implemented-tool-local-only).

6. ~~**Change Classifier**~~ — **implemented locally** as `tools/cowork/change_classifier.py` with the pure-data `change_policy.json` (216 tests). Answers what *minimum* approval class a change requires, and **never approves anything**. See below.

7. ~~**Test Selector**~~ — **implemented locally** as `tools/cowork/test_selector.py` with the pure-data `test_selection_policy.json` (201 tests). Proposes a focused test list from changed paths and **never replaces the full regression suite**. See below.

8. ~~**Codex relay transport**~~ — **implemented locally** as `tools/cowork/codex_relay.py` with the pure-data `relay_policy.json` and the strict `relay_verdict_schema.json`. Carries one completed phase report to Codex and one structured verdict back, and **invokes nothing**. See below.

All eight are read-only in effect. Items 1-3 and 5-8 are done locally, and item 4's tool is done locally with its registry initialized under separate approval. **Tier 1 — the read-only trust layer — is now complete.** Item 8 is the transport only: the one-shot Codex runner, a first live review, and the real mailbox are all still TODO and unauthorized. Nothing beyond this is scheduled, and nothing here is pushed or merged.

## The Test Selector: fast feedback, never evidence

`tools/cowork/test_selector.py` maps changed paths to the tests worth running first.
It is an aid while working, not a gate.

- **It never replaces anything.** Every report carries `full_regression_required: true`
  and `collection_parity_required: true`, unconditionally. A focused selection cannot
  satisfy A7.7, cannot replace collection parity, cannot replace the complete
  regression suite required before a commit, makes no claim about the tests it did
  not select, and authorizes nothing.
- **It imports nothing and runs nothing** — not even `pytest --collect-only`, which
  would import every test module and conftest and execute their module-level code.
  Mapping is built by parsing tracked blobs with `ast`. A planted module whose top
  level writes a file was mapped correctly and never executed.
- **It proposes, it does not invoke.** The output is a structured argument array,
  `["python", "-B", "-m", "pytest", <targets>, "-q"]`, emitted as evidence. The
  policy may contain only those fixed tokens — no arbitrary flags, plugins,
  environment assignments, or shell fragments.
- **Six read-only modes**: `select-worktree`, `select-staged`, `select-commit`,
  `select-range`, `select-manifest`, `validate-policy`.
- **Mapping sources**: self, direct import, transitive import, conftest scope,
  explicit policy, dynamic-test safety inclusion, global fallback.
- **Ambiguity escalates, never narrows.** An unmapped path, a global-impact path, an
  unparseable file, a **changed source** with unresolved dynamic imports, an
  ambiguous module name, or a binary change all produce "full suite required"
  (exit 5). **"No focused test" never means "no testing required"** — a
  documentation-only change says so explicitly.
- **Dynamic tests are included, not a reason to give up.** A *test* file whose own
  imports cannot be read statically is added to **every** focused selection rather
  than collapsing the whole repository to the full suite. The selection only gets
  broader, never narrower. The concession is test-side only: a changed *source* with
  unresolved dynamic imports still escalates. Detection is general and AST-based, and
  the inclusion cannot be switched off by policy or manifest.
- **Collection counts are snapshots.** 926 (P0.9) and 1722 (Phase 3U) are history,
  not expectations; collection is re-measured against the current pinned HEAD and
  compared as exact node-ID sets.

**Phase 3W refinement (2026-09-03) — B1.7 remains DONE (tool) — local only.**
`tests/test_ui_modularization.py` uses `exec(compile(...))` and
`importlib.import_module`, so its imports cannot be read statically. That used to
force **every** selection on this repository to the full suite. It no longer does:
the file is now included conservatively in every focused selection instead. Measured
on this tree at HEAD `4d7807a`, a change to `tools/cowork/evidence_formatter.py`
returns **9** focused test files out of 54, and a change to `ui/styles.py` returns
**12** — where both previously returned "full suite required".

Nothing about the contract moved. Full regression before every commit and collection
parity both remain **mandatory and unconditional**, a focused selection remains
**preliminary feedback only**, source-side ambiguity still escalates, and **a focused
selection is never test coverage**.

See [AUTOMATION_BACKLOG.md](AUTOMATION_BACKLOG.md#b17-test-selector--implemented-tool-local-only).

## The Codex relay: a mailbox, not an agent

`tools/cowork/codex_relay.py` carries one completed Claude phase report to Codex
and one structured verdict back. **It is transport only.**

- **It invokes nothing.** No Codex call, no model request, no subprocess of its
  own, no shell, no socket, no environment discovery. Git is read through the A7
  read-only allowlist (`rev-parse`, `status` only); the Session Registry is read,
  never mutated.
- **PASS is not approval.** `PASS` means only that a second reader found no
  objection. Every verdict must carry the exact sentence *"This verdict grants no
  permission to modify, commit, push, merge, deploy, trade, alter risk, or enable
  execution"* or it is rejected. AAM and AM work still needs Pedro's named
  approval.
- **Codex never writes the mailbox.** Its output goes to a private temporary file;
  the relay validates it and records a relay-authored envelope. Codex's bytes are
  nested as data.
- **Logical identity, not machine paths.** Envelopes carry
  `repository_identity` and `worktree_identity`; the real path is supplied at the
  command line and verified against Git and the registry there.
- **Input is data.** Reports, notes, findings, and summaries are never executed
  and no instruction inside them is followed. Shell payloads, command-bearing
  field names, credentials, machine paths, traversal, replays, stale HEAD, a dirty
  tree, and prohibited intent are all refused — as failures, never warnings.
- **One review per `(phase, head)`, no automatic retry.** A `REVISE` verdict ends
  the exchange and returns the decision to Pedro.
- **Seven operations, no aliases**: `validate-policy`, `validate-request`,
  `validate-response`, `submit`, `ingest-response`, `inspect`, `verify-chain`.
  Twenty-five action verbs exit 2.
- **Honest about the archive.** Append-only *by this tool* and hash chained, which
  detects corruption or partial rewriting. It is **not** tamper-proof against
  someone who can rewrite the mailbox and archive together, and the policy says so.

### The one-shot runner

`tools/cowork/codex_review_runner.py` is the only component that may start a model,
and it may do so **exactly once** per pending request. Three operations
(`validate-policy`, `inspect`, `review-once`), no aliases. It accepts no prompt, no
model, no executable path, no output destination, no retry count, and no sandbox or
approval override — all fixed by `codex_runner_policy.json`.

The invocation is fixed: `codex exec -C <repo> -s read-only
-c approval_policy="never" -m gpt-5.6-luna -c model_reasoning_effort="low" --ephemeral --ignore-user-config
--output-schema <schema> -o <private temp> -`, with the prompt on **stdin** (the
`-` form, proven from local `codex exec --help` on 0.153.0). Only ten allowlisted
environment names reach the child; planted API, broker, Anthropic, and trading
variables are proven excluded. **The attempt is consumed the moment the child
starts** — success, failure, or timeout — so there is no retry and no usage
runaway.

On Windows a global npm install ships only shims — an extension-less POSIX shell
script, a `.cmd`, and a `.ps1` — and none of them can be started with
`shell=False`. The runner therefore prefers a real `codex.exe` on the search path
and otherwise uses the shim **only as a locator**, walking the validated
`@openai/codex` package to the bundled native binary that the official launcher
would itself have started. No shell, no command interpreter, and no Node process
sits between the runner and that binary.

**Still to do, and not authorized:** a controlled first live review, and
initializing the real mailbox at `${HOME}/.claude/nova-relay/`. **No live review has
ever been performed, and automatic Claude/Codex communication is not
operational.**

See [CODEX_RELAY_CONTRACT.md](CODEX_RELAY_CONTRACT.md).

## The Change Classifier: minimum approval, never approval

`tools/cowork/change_classifier.py` reports the **minimum approval class** an observed
or proposed change requires. It is the answer to "how carefully must this be handled?",
never to "may this proceed?".

| Class | Meaning | Exit |
|---|---|---|
| `FA_AR` | fully automated / automated read-only; no approval | 0 |
| `AAM` | automated, with an approval naming exact targets | 5 |
| `AM` | always manual; you perform it or explicitly command it | 6 |
| `PROHIBITED` | must not proceed under any approval | 7 |

- **It never outputs "approved".** No class, status, exit code, or policy field can
  produce that. It reports scope, minimum class, reasons, ambiguity, and the
  escalation required — and authorizes nothing.
- **Every repository write is at least AAM.** A write is never FA/AR just because its
  content is documentation. FA/AR needs a read-only operation that changes no path.
- **The overall result is the most restrictive class present.** Aggregation only ever
  moves upward.
- **Unknown escalates.** An unrecognized path or change kind, unscannable content, or
  any ambiguity becomes AM. A deletion is never below a modification, both sides of a
  rename are classified, binaries escalate, gitlinks are AM, and raw transcripts and
  runtime artefacts are prohibited as tracked content.
- **Six read-only modes**: `classify-worktree`, `classify-staged`, `classify-commit`,
  `classify-range`, `classify-manifest`, `validate-policy`.
- **A clean tree is `stopped`, not passed** — there is nothing to classify, and
  nothing is approved.
- **Semantic scanning is defence in depth.** It can raise a class; it *cannot prove
  the absence* of dangerous behaviour, and matched text is never printed.

See [AUTOMATION_BACKLOG.md](AUTOMATION_BACKLOG.md#b16-change-classifier--implemented-tool-local-only).

## Obsidian: the planning half only

`tools/cowork/obsidian_sync_planner.py`, with the fixed `obsidian_policy.json`, plans
and validates a controlled synchronization between Git and an Obsidian vault (185
tests). **Only the read-only half exists.** It answers what a synchronization would
propose and whether every proposed item is provably safe; it writes nothing, in the
repository or in a vault.

- **Git is the authority** for approved specifications and promoted knowledge.
  Obsidian is a non-executing knowledge and working-note surface, and its content is
  never executable instruction. It cannot modify strategy, risk, broker, execution,
  kill-switch, guard, permission, deployment, or runtime state.
- **Five read-only operations**: `validate-policy`, `inventory`, `plan-export`,
  `plan-import`, `check-plan`. There is no apply, sync, watch, write, copy, move,
  delete, rename, install, repair, force, override, or plugin management.
- **A vault is never discovered.** Its root is supplied explicitly or nothing is
  read. No environment, no Documents folder, no cloud-drive folder, no Obsidian
  configuration, no installed-application lookup, and no vault is ever created.
- **No auto-merge, no deletion, no two-way sync.** Conflicts stop planning. When
  Git and a note both changed, that is a conflict a person resolves.
- **An import plan is never approval.** Any candidate import exits 5 and waits for
  Pedro's separate, named approval.

**The apply engine is not built and not authorized** — writing a note into a vault,
promoting a candidate into the repository, a sync ledger, and any scheduling are all
separate future work. See [AUTOMATION_BACKLOG.md](AUTOMATION_BACKLOG.md#b34-obsidian-sync-planner--read-only-half-implemented-local-only).

No real Obsidian vault has been discovered, inspected, created, or modified.

## What this documentation does not do

Nothing here authorizes trading, deployment, merging, pushing, or autonomous
execution. These documents describe boundaries; they grant no permission. Every
mutating or outward-facing action still requires Pedro's approval at the moment it
is proposed.
